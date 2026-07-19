import hashlib
import os
from pathlib import Path

import frontmatter
from sqlalchemy.orm import Session

from app.config import VAULT_PATH, CHUNK_SIZE, CHUNK_OVERLAP
from app.db import Document, Chunk
from app.llm import embed_text


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Simple sliding-window chunking by characters."""
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def list_vault_files() -> list[Path]:
    vault = Path(VAULT_PATH)
    return list(vault.rglob("*.md"))


async def ingest_file(db: Session, filepath: Path, force: bool = False) -> str:
    """
    Ingest a single markdown file. Returns 'skipped', 'created', or 'updated'.
    This is the incremental piece: unchanged files are skipped via content hash,
    so a re-index doesn't re-embed the whole vault every time.
    """
    raw = filepath.read_text(encoding="utf-8", errors="ignore")
    post = frontmatter.loads(raw)
    content = post.content.strip()
    title = post.get("title") or filepath.stem

    if not content:
        return "skipped"

    rel_path = str(filepath.relative_to(VAULT_PATH))
    new_hash = hash_content(content)

    existing = db.query(Document).filter(Document.path == rel_path).first()

    if existing and existing.content_hash == new_hash and not force:
        return "skipped"

    # (re)create document row
    if existing:
        existing.content_hash = new_hash
        existing.title = title
        db.query(Chunk).filter(Chunk.document_id == existing.id).delete()
        document = existing
        status = "updated"
    else:
        document = Document(path=rel_path, title=title, content_hash=new_hash)
        db.add(document)
        db.flush()  # get document.id
        status = "created"

    pieces = chunk_text(content)
    for idx, piece in enumerate(pieces):
        vector = await embed_text(piece)
        chunk = Chunk(
            document_id=document.id,
            path=rel_path,
            title=title,
            chunk_index=idx,
            content=piece,
            embedding=vector,
        )
        db.add(chunk)

    db.commit()
    return status


async def ingest_vault(db: Session, force: bool = False) -> dict:
    """Walk the whole vault and ingest any new/changed files."""
    files = list_vault_files()
    results = {"created": 0, "updated": 0, "skipped": 0, "total_files": len(files)}

    for f in files:
        status = await ingest_file(db, f, force=force)
        results[status] += 1

    # Remove documents whose source file no longer exists
    existing_paths = {str(f.relative_to(VAULT_PATH)) for f in files}
    stale_docs = db.query(Document).filter(~Document.path.in_(existing_paths)).all() if existing_paths else db.query(Document).all()
    for doc in stale_docs:
        db.query(Chunk).filter(Chunk.document_id == doc.id).delete()
        db.delete(doc)
    db.commit()
    results["removed"] = len(stale_docs)

    return results
