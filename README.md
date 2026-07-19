# AI Second Brain (Local, Zero-Cost)

A retrieval-augmented "second brain" over your Obsidian vault — runs fully
locally, no API keys, no cloud costs. Auto re-indexes changed notes,
answers questions grounded in your notes with cited sources, and includes
a retrieval-quality eval so you're not just trusting a demo.

**Stack:** FastAPI · PostgreSQL + pgvector · Ollama (local LLM + embeddings) · Docker Compose

---

## 0. Check your RAM first

Run this in WSL2:

```bash
free -h
```

- **16GB+ total** → use the default model (`llama3.1:8b`), already set in `docker-compose.yml`.
- **8GB** → switch to a smaller model. Edit `LLM_MODEL` in `docker-compose.yml` to `qwen2.5:3b` or `phi3:mini`, and update the `ollama pull` command in step 2 to match.

---

## 1. Install Ollama

Ollama is what runs the LLM and embedding model locally — no API key needed.

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify it installed:

```bash
ollama --version
```

You don't need to run `ollama serve` manually — the Docker Compose setup runs
Ollama as a container. But if you'd rather run Ollama natively on your host
instead of in Docker (sometimes faster, especially on WSL2 with GPU passthrough
issues), you can — just change `OLLAMA_URL` in `docker-compose.yml` to
`http://host.docker.internal:11434` and remove the `ollama` service block.

---

## 2. Pull the models

Once Ollama is installed (native) or the Ollama container is up (see step 3),
pull the two models this project needs:

```bash
# If running Ollama natively:
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# If using the Docker Compose ollama service, pull inside the container instead:
docker exec -it secondbrain-ollama ollama pull llama3.1:8b
docker exec -it secondbrain-ollama ollama pull nomic-embed-text
```

This downloads a few GB — one-time, then fully offline after.

---

## 3. Point it at your real Obsidian vault

By default, `docker-compose.yml` mounts the included `vault_example/` folder.
To use your actual Obsidian vault, set an environment variable before starting:

```bash
export VAULT_HOST_PATH="/mnt/c/Users/<you>/Documents/YourObsidianVault"
```

(Adjust the path — this is the WSL2 path to your Windows Obsidian folder.)

---

## 4. Start everything

```bash
docker compose up --build
```

This starts:
- `postgres` (with pgvector) on port `5433`
- `ollama` on port `11434`
- `backend` (FastAPI) on port `8000`

First boot: the backend auto-creates the DB tables. It does **not** auto-ingest
on startup — trigger the first index manually (step 5), so you control when the
(one-time, slower) full scan happens.

---

## 5. Index your vault

```bash
curl -X POST http://localhost:8000/ingest
```

After this, any file you edit/add in your vault is **automatically detected
and re-indexed** by the background file watcher — no need to re-run this
manually again. Only changed files get re-embedded (content hash comparison),
so this stays fast as your vault grows.

---

## 6. Use it

Open `frontend/index.html` directly in your browser (no build step needed —
it's a static file that talks to `localhost:8000`).

Or hit the API directly:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is my educational background?"}'
```

Check indexing status any time:

```bash
curl http://localhost:8000/status
```

---

## 7. Run the retrieval eval

This is the part that makes it more than a toy demo — it scores whether
retrieval actually pulls the right note for a given question.

```bash
curl -X POST http://localhost:8000/eval \
  -H "Content-Type: application/json" \
  -d @eval_set_example.json
```

Replace `eval_set_example.json` with your own `{question, expected_path}`
pairs as your vault grows, to track retrieval quality over time — a good
thing to screenshot/write up for a portfolio case study.

---

## Architecture notes (for your case study / interviews)

- **Incremental indexing**: files are hashed on ingest; unchanged files are
  skipped on re-index, and a background `watchdog` observer auto re-embeds
  only the file that changed, the moment you save it in Obsidian.
- **Grounded generation**: the LLM is prompted to answer *only* from
  retrieved chunks and to say when it doesn't know, with source citations
  returned separately from the answer text (shown as chips in the UI).
- **Retrieval eval**: separate from generation quality — this isolates
  whether the vector search is pulling the right notes at all, independent
  of how the LLM phrases the answer.
- **Zero cost / zero key**: Ollama replaces any hosted LLM API; pgvector
  replaces a hosted vector DB (e.g. Pinecone); everything runs in Docker
  on your own machine.

## Known limitations (worth stating honestly in a write-up)

- Chunking is character-based, not semantic — fine for short notes, less
  precise for long documents. A future iteration could chunk by heading/section.
- No auth — this is a single-user local tool, not deployed publicly.
- Local models trade some answer quality for zero cost vs. hosted models
  like GPT-4/Claude — worth benchmarking and writing up the comparison.
