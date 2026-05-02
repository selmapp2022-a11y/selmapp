"""merge heads and add soft delete fields to users table

Revision ID: merge_soft_delete_001
Revises: 86763ed51fd0, 20251208_weekly_plan
Create Date: 2024-12-21

This migration:
1. Merges the existing multiple heads
2. Adds fields required for proper soft delete functionality:
   - deleted_at: Timestamp when user was deleted
   - original_email_hash: SHA256 hash of original email for audit purposes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_soft_delete_001'
down_revision: Union[str, Sequence[str]] = ('86763ed51fd0', '20251208_weekly_plan')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add soft delete columns to users table
    # Use batch mode for better compatibility
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('original_email_hash', sa.String(64), nullable=True))
    
    # Create index on deleted_at for efficient queries
    op.create_index('ix_users_deleted_at', 'users', ['deleted_at'], unique=False)
    
    # Create index on original_email_hash for audit lookups
    op.create_index('ix_users_original_email_hash', 'users', ['original_email_hash'], unique=False)


def downgrade() -> None:
    # Remove indexes first
    op.drop_index('ix_users_original_email_hash', table_name='users')
    op.drop_index('ix_users_deleted_at', table_name='users')
    
    # Remove columns
    op.drop_column('users', 'original_email_hash')
    op.drop_column('users', 'deleted_at')





