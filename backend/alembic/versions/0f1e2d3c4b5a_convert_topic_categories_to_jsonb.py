"""convert_topic_categories_to_jsonb

Revision ID: 0f1e2d3c4b5a
Revises: ce3b8ec7e9a
Create Date: 2025-10-18 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0f1e2d3c4b5a'
down_revision: Union[str, None] = 'ce3b8ec7e9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert topic_categories from JSON to JSONB for proper containment ops and indexing
    op.alter_column(
        'vocabulary',
        'topic_categories',
        type_=postgresql.JSONB(astext_type=sa.Text()),
        postgresql_using='topic_categories::jsonb'
    )

    # Create GIN index for fast @> queries on topic_categories
    op.create_index(
        'ix_vocabulary_topic_categories_gin',
        'vocabulary',
        ['topic_categories'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    # Drop GIN index
    op.drop_index('ix_vocabulary_topic_categories_gin', table_name='vocabulary')

    # Convert back to JSON (not recommended, but for completeness)
    op.alter_column(
        'vocabulary',
        'topic_categories',
        type_=sa.JSON(),
        postgresql_using='topic_categories::json'
    )





