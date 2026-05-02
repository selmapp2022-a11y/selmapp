"""merge all heads and add admin_role column

Revision ID: merge_add_admin_role
Revises: 0f1e2d3c4b5a, 20251229_add_personalization, merge_soft_delete_001
Create Date: 2026-02-14

This migration:
1. Merges the three existing heads into a single head
2. Adds admin_role VARCHAR(20) column to the users table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_add_admin_role'
down_revision: Union[str, Sequence[str]] = (
    '0f1e2d3c4b5a',
    '20251229_add_personalization',
    'merge_soft_delete_001',
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add admin_role column to users table
    # Values: 'developer' or 'owner', nullable for non-admin users
    op.add_column(
        'users',
        sa.Column('admin_role', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'admin_role')
