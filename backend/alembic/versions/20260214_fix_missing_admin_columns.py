"""Ensure admin columns exist on users table.

Revision ID: 20260214_admin_fix
Revises: merge_add_admin_role
Create Date: 2026-02-14

Why this exists:
- Some environments may be stamped or partially migrated, leaving `users`
  without `admin_role` and/or `is_admin` despite ORM expecting them.
- Missing columns cause runtime failures (e.g., UndefinedColumnError) when
  SQLAlchemy selects `User`.

This migration is defensive/idempotent and only adds missing columns.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
# Keep <= 32 chars because alembic_version.version_num is VARCHAR(32)
revision: str = "20260214_admin_fix"
down_revision: Union[str, Sequence[str], None] = "merge_add_admin_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    if not _has_column("users", "is_admin"):
        op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=True))

    if not _has_column("users", "admin_role"):
        op.add_column("users", sa.Column("admin_role", sa.String(length=20), nullable=True))


def downgrade() -> None:
    # This is a repair migration. Avoid destructive drops in downgrade.
    pass
