import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Se existir DATABASE_URL, usa Postgres (produção).
# Se não existir, usa SQLite local (desenvolvimento).
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DATABASE_URL:
    # Render/Supabase normalmente já vem ok como postgresql://...
    # SQLAlchemy prefere postgresql+psycopg2://, mas psycopg2 aceita ambos.
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
else:
    # SQLite local (arquivo no projeto)
    SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_sqlite_migrations():
    # Placeholder (se você tinha isso antes). Em Postgres não precisa.
    return
