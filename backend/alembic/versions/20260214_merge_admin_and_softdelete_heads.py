"""Merge admin-fix and soft-delete-fix heads.

Revision ID: 20260214_merge_heads
Revises: 20251221_soft_delete_fix, 20260214_admin_fix
Create Date: 2026-02-14

This is a no-op merge migration to keep Alembic history linear
for production operations.
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260214_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20251221_soft_delete_fix",
    "20260214_admin_fix",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op by design: this revision only merges two concurrent heads
    # into a single linear migration history.
    pass


def downgrade() -> None:
    # No-op by design for the same reason as `upgrade()`.
    pass
