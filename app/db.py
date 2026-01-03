import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = Path(__file__).resolve().parent  # .../app
DEFAULT_SQLITE = f"sqlite:///{(BASE_DIR / 'app.db').as_posix()}"

def _normalize_db_url(url: str) -> str:
    """
    Render/Supabase às vezes fornecem 'postgres://' mas SQLAlchemy quer 'postgresql://'
    """
    url = (url or "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

DATABASE_URL = _normalize_db_url(os.getenv("DATABASE_URL")) or DEFAULT_SQLITE

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def ensure_db_ready():
    """
    Mantém a lógica simples: cria tabelas (para MVP).
    Se você quiser migração real depois, a gente coloca Alembic.
    """
    Base.metadata.create_all(bind=engine)
