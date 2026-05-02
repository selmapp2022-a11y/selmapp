"""merge multiple migration heads

Revision ID: 86763ed51fd0
Revises: 32db7c56a670, 7f1e3b2c1abc, add_lesson_caching
Create Date: 2025-11-03 18:21:02.262276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86763ed51fd0'
down_revision: Union[str, None] = ('32db7c56a670', '7f1e3b2c1abc', 'add_lesson_caching')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
