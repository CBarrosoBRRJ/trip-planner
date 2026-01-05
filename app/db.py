import os
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# =========================
# Config
# =========================
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()

# Se não tiver DATABASE_URL, cai em SQLite local (NÃO PERSISTE no Render free).
DEFAULT_SQLITE_URL = "sqlite:///./trip_planner.db"

def _build_db_url() -> str:
    if DATABASE_URL:
        # Render/Supabase costumam exigir SSL. Se já tiver sslmode, não duplica.
        if DATABASE_URL.startswith("postgres://"):
            url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        else:
            url = DATABASE_URL

        if "sslmode=" not in url:
            joiner = "&" if "?" in url else "?"
            url = url + f"{joiner}sslmode=require"
        return url

    return DEFAULT_SQLITE_URL


SQLALCHEMY_DATABASE_URL = _build_db_url()

# =========================
# SQLAlchemy
# =========================
connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_db_ready(max_wait_seconds: int = 40, sleep_seconds: float = 1.5):
    """
    Tenta conectar no banco por até max_wait_seconds.
    Útil no cold start (Render + Postgres/Supabase).
    NÃO levanta ImportError nem faz circular import.
    """
    deadline = time.time() + max_wait_seconds
    last_err = None

    while time.time() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            last_err = e
            time.sleep(sleep_seconds)

    raise RuntimeError(f"Banco não ficou pronto em {max_wait_seconds}s. Erro: {last_err}")
