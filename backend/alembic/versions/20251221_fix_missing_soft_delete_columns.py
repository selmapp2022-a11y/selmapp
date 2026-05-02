"""Ensure soft-delete columns exist on users table.

Revision ID: 20251221_soft_delete_fix
Revises: merge_soft_delete_001
Create Date: 2025-12-21

Why this exists:
- Some databases ended up stamped at `merge_soft_delete_001` without actually
  having the `users.deleted_at` / `users.original_email_hash` columns (and
  their indexes). This causes runtime 500s on login because SQLAlchemy selects
  model columns that don't exist in the DB schema.

This migration is defensive/idempotent:
- It checks existing columns/indexes before adding them.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
# NOTE: alembic_version.version_num is VARCHAR(32) in this project, so keep IDs <= 32 chars.
revision: str = "20251221_soft_delete_fix"
down_revision: Union[str, Sequence[str]] = "merge_soft_delete_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return any(col["name"] == column for col in inspector.get_columns(table))


def _has_index(table: str, index_name: str) -> bool:
    conn = op.get_bind()
    inspector = inspect(conn)
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table))


def upgrade() -> None:
    # Columns
    if not _has_column("users", "deleted_at"):
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    if not _has_column("users", "original_email_hash"):
        op.add_column("users", sa.Column("original_email_hash", sa.String(64), nullable=True))

    # Indexes (create only if missing)
    if _has_column("users", "deleted_at") and not _has_index("users", "ix_users_deleted_at"):
        op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)

    if _has_column("users", "original_email_hash") and not _has_index(
        "users", "ix_users_original_email_hash"
    ):
        op.create_index(
            "ix_users_original_email_hash",
            "users",
            ["original_email_hash"],
            unique=False,
        )


def downgrade() -> None:
    # Drop indexes first (if present)
    if _has_index("users", "ix_users_original_email_hash"):
        op.drop_index("ix_users_original_email_hash", table_name="users")

    if _has_index("users", "ix_users_deleted_at"):
        op.drop_index("ix_users_deleted_at", table_name="users")

    # Drop columns (if present)
    if _has_column("users", "original_email_hash"):
        op.drop_column("users", "original_email_hash")

    if _has_column("users", "deleted_at"):
        op.drop_column("users", "deleted_at")






