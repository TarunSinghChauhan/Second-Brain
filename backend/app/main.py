import asyncio
import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.config import TOP_K
from app.db import init_db, get_db, Document, Chunk
from app.ingest import ingest_vault
from app.llm import generate_answer, embed_text, check_ollama_ready
from app.watcher import start_watcher
from app.eval import run_eval

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(title="AI Second Brain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_observer = None


@app.on_event("startup")
async def startup():
    init_db()
    global _observer
    loop = asyncio.get_event_loop()
    _observer = start_watcher(loop)
    logger.info("AI Second Brain backend started.")


@app.on_event("shutdown")
def shutdown():
    if _observer:
        _observer.stop()
        _observer.join()


class ChatRequest(BaseModel):
    question: str


class EvalRequest(BaseModel):
    eval_set: list[dict]  # [{"question": str, "expected_path": str}, ...]


@app.get("/status")
async def status(db: Session = Depends(get_db)):
    ollama_status = await check_ollama_ready()
    doc_count = db.query(Document).count()
    chunk_count = db.query(Chunk).count()
    return {
        "ollama": ollama_status,
        "documents_indexed": doc_count,
        "chunks_indexed": chunk_count,
    }


@app.post("/ingest")
async def ingest(force: bool = False, db: Session = Depends(get_db)):
    """Manually trigger a full vault scan. Only new/changed files get re-embedded unless force=True."""
    results = await ingest_vault(db, force=force)
    return results


@app.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    query_vector = await embed_text(req.question)

    rows = db.execute(
        sql_text("""
            SELECT path, title, content, embedding <=> CAST(:qvec AS vector) AS distance
            FROM chunks
            ORDER BY embedding <=> CAST(:qvec AS vector)
            LIMIT :k
        """),
        {"qvec": str(query_vector), "k": TOP_K},
    ).fetchall()

    context_chunks = [{"path": r.path, "title": r.title, "content": r.content} for r in rows]
    answer = await generate_answer(req.question, context_chunks)

    return {
        "answer": answer,
        "sources": [
            {"title": r.title, "path": r.path, "distance": float(r.distance)} for r in rows
        ],
    }


@app.post("/eval")
async def eval_endpoint(req: EvalRequest, db: Session = Depends(get_db)):
    return await run_eval(db, req.eval_set)


@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).all()
    return [{"path": d.path, "title": d.title, "updated_at": d.updated_at} for d in docs]
