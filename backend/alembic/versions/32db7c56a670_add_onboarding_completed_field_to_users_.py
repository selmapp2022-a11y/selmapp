"""Add onboarding_completed field to users table

Revision ID: 32db7c56a670
Revises: d7e0bc2c8d4d
Create Date: 2025-09-11 15:35:07.314998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32db7c56a670'
down_revision: Union[str, None] = 'd7e0bc2c8d4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add onboarding_completed column to users table
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove onboarding_completed column from users table
    op.drop_column('users', 'onboarding_completed')
