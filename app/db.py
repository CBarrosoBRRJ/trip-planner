import os
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


def _normalize_db_url(url: str) -> str:
    """
    Render/Supabase às vezes entregam DATABASE_URL com prefixo postgres://
    SQLAlchemy prefere postgresql://
    """
    if not url:
        return ""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def _sqlite_url_from_env() -> str:
    """
    Fallback local (Windows / Docker) quando não existir DATABASE_URL.
    Usa DB_PATH se existir; senão cria em ./data/app.db
    """
    db_path = os.getenv("DB_PATH", "").strip()
    if db_path:
        p = Path(db_path)
    else:
        p = Path("data") / "app.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    # sqlite URL precisa de path absoluto em alguns ambientes
    return f"sqlite:///{p.resolve().as_posix()}"


DATABASE_URL = _normalize_db_url(os.getenv("DATABASE_URL", "").strip())

if DATABASE_URL:
    # Postgres (Render/Supabase)
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    )
else:
    # SQLite local
    engine = create_engine(
        _sqlite_url_from_env(),
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_db_ready(max_wait_seconds: int = 30) -> None:
    """
    Em cloud, o Postgres pode demorar alguns segundos para aceitar conexão.
    Esta função tenta pingar o DB (SELECT 1) até passar ou estourar timeout.
    """
    start = time.time()
    last_err = None

    while time.time() - start < max_wait_seconds:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as e:
            last_err = e
            time.sleep(1)

    # se chegou aqui, falhou
    raise RuntimeError(f"Banco não ficou pronto em {max_wait_seconds}s. Erro: {last_err}")
