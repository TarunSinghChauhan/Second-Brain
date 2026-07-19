import httpx
from app.config import OLLAMA_URL, LLM_MODEL, EMBED_MODEL

TIMEOUT = httpx.Timeout(120.0)


async def embed_text(text: str) -> list[float]:
    """Get an embedding vector from the local Ollama embedding model."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embedding"]


async def generate_answer(question: str, context_chunks: list[dict]) -> str:
    """Generate an answer grounded in retrieved context chunks, using a local LLM."""
    context_block = "\n\n".join(
        f"[Source: {c['title']} ({c['path']})]\n{c['content']}" for c in context_chunks
    )

    system_prompt = (
        "You are a personal knowledge assistant. Answer the user's question using ONLY "
        "the context provided below, which comes from their personal notes. If the context "
        "doesn't contain the answer, say so plainly instead of guessing. Cite which note(s) "
        "you used by title."
    )

    prompt = f"{system_prompt}\n\nCONTEXT:\n{context_block}\n\nQUESTION: {question}\n\nANSWER:"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["response"].strip()


async def check_ollama_ready() -> dict:
    """Check that Ollama is reachable and required models are pulled."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        try:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {
                "reachable": True,
                "models_available": models,
                "llm_ready": any(LLM_MODEL in m for m in models),
                "embed_ready": any(EMBED_MODEL in m for m in models),
            }
        except Exception as e:
            return {"reachable": False, "error": str(e)}
