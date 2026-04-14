"""Database bootstrap and session helpers for the dashboard API."""

from __future__ import annotations

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Load repo-root .env so DATABASE_URL / AIMM_DATABASE_URL is available when
# running uvicorn from the backend/ directory.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _db_url() -> str:
    """Return the SQLAlchemy connection URL derived from local environment variables."""
    url = os.environ.get("AIMM_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Set AIMM_DATABASE_URL or DATABASE_URL before starting the API server.")
    # SQLAlchemy 2.x with psycopg3 needs postgresql+psycopg:// driver prefix.
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


_engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False)


def get_engine() -> Engine:
    """Create the SQLAlchemy engine lazily so imports do not require a live DB driver."""
    global _engine
    if _engine is None:
        _engine = create_engine(_db_url(), pool_pre_ping=True)
    return _engine


def configure_session_local() -> sessionmaker:
    """Bind the shared sessionmaker to the lazily created engine and return it."""
    SessionLocal.configure(bind=get_engine())
    return SessionLocal


def ensure_dashboard_schema() -> None:
    """Apply dashboard-specific additive schema changes if they do not exist yet."""
    with get_engine().begin() as conn:
        conn.execute(text("""
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS user_note TEXT NOT NULL DEFAULT '';
                """))
        conn.execute(text("""
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS user_feedback TEXT;
                """))
        conn.execute(text("""
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS vram_override TEXT;
                """))
        conn.execute(text("""
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS contacted_seller BOOLEAN NOT NULL DEFAULT FALSE;
                """))
        conn.execute(text("""
                CREATE TABLE IF NOT EXISTS listing_rerun_queue (
                    id BIGSERIAL PRIMARY KEY,
                    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'pending',
                    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    started_at TIMESTAMPTZ NULL,
                    finished_at TIMESTAMPTZ NULL,
                    error_message TEXT NULL
                );
                """))
        conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_listing_rerun_queue_status_requested_at
                ON listing_rerun_queue (status, requested_at, id);
                """))
        conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_listing_rerun_queue_active_listing
                ON listing_rerun_queue (listing_id)
                WHERE status IN ('pending', 'running');
                """))


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session for request handlers and close it afterwards."""
    db = configure_session_local()()
    try:
        yield db
    finally:
        db.close()
