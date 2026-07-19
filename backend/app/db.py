from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, func
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector

from app.config import DATABASE_URL, EMBED_DIM

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Document(Base):
    """One row per source file in the vault."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)   # used to detect changes, avoids re-embedding unchanged files
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Chunk(Base):
    """One row per embedded chunk of a document."""
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, nullable=False, index=True)
    path = Column(String, nullable=False)
    title = Column(String, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBED_DIM), nullable=False)


class EvalResult(Base):
    """Retrieval eval runs, so quality is tracked over time instead of assumed."""
    __tablename__ = "eval_results"

    id = Column(Integer, primary_key=True)
    run_at = Column(DateTime(timezone=True), server_default=func.now())
    question = Column(Text, nullable=False)
    expected_path = Column(String, nullable=False)
    retrieved_paths = Column(Text, nullable=False)  # comma-separated, top-k paths returned
    hit = Column(Integer, nullable=False)            # 1 if expected_path was in retrieved set, else 0
    top_score = Column(Float, nullable=True)


def init_db():
    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
