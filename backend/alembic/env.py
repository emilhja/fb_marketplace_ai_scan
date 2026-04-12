"""Alembic environment — DB URL is loaded from AIMM_DATABASE_URL / DATABASE_URL.

DDL for all existing tables is OWNED by pg_cache.ensure_database().
This Alembic setup is baseline-only: run `alembic stamp head` once after
initial setup, then use real revisions only for future dashboard-specific tables.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Ensure repo root .env is loaded so env vars are available.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env")

# Add backend/ to sys.path so models can be imported.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Base  # noqa: E402

config = context.config

# Override sqlalchemy.url from environment (never use the placeholder in alembic.ini).
def _db_url() -> str:
    url = os.environ.get("AIMM_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


url = _db_url()
if url:
    config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
