"""
Retrieval quality eval.

This exists because "it works in a demo" isn't the same as "retrieval is good."
You give it a small set of (question, expected_source_file) pairs, and it checks
whether the expected file actually shows up in the top-K retrieved chunks.

Usage: put questions in eval_set.json (see example), then hit POST /eval
"""
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from app.db import EvalResult
from app.llm import embed_text
from app.config import TOP_K


async def run_eval(db: Session, eval_set: list[dict]) -> dict:
    """
    eval_set: list of {"question": str, "expected_path": str}
    Returns aggregate hit rate plus per-question results.
    """
    results = []
    hits = 0

    for item in eval_set:
        question = item["question"]
        expected_path = item["expected_path"]

        query_vector = await embed_text(question)

        rows = db.execute(
            sql_text("""
                SELECT path, title, content, embedding <=> CAST(:qvec AS vector) AS distance
                FROM chunks
                ORDER BY embedding <=> CAST(:qvec AS vector)
                LIMIT :k
            """),
            {"qvec": str(query_vector), "k": TOP_K},
        ).fetchall()

        retrieved_paths = [r.path for r in rows]
        hit = 1 if expected_path in retrieved_paths else 0
        hits += hit

        top_score = float(rows[0].distance) if rows else None

        eval_row = EvalResult(
            question=question,
            expected_path=expected_path,
            retrieved_paths=",".join(retrieved_paths),
            hit=hit,
            top_score=top_score,
        )
        db.add(eval_row)

        results.append({
            "question": question,
            "expected_path": expected_path,
            "retrieved_paths": retrieved_paths,
            "hit": bool(hit),
        })

    db.commit()

    total = len(eval_set)
    hit_rate = hits / total if total else 0.0

    return {"hit_rate": hit_rate, "total_questions": total, "hits": hits, "results": results}
