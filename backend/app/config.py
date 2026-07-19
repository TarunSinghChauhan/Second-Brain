import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://secondbrain:secondbrain@localhost:5433/secondbrain")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
VAULT_PATH = os.getenv("VAULT_PATH", "/vault")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))

CHUNK_SIZE = 800       # characters per chunk
CHUNK_OVERLAP = 150    # characters of overlap between chunks
TOP_K = 5              # chunks retrieved per query
