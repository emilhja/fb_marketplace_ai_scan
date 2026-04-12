"""Baseline: existing schema is owned by pg_cache.ensure_database().

Run ``alembic stamp head`` once after first setup to record this baseline
in the alembic_version table without executing any DDL statements.
"""
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No DDL — the real schema is created/migrated by pg_cache.ensure_database().
    pass


def downgrade() -> None:
    pass
