"""add assessment_jobs table

Revision ID: 7f1e3b2c1abc
Revises: fed4031d5a4c
Create Date: 2025-10-13 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7f1e3b2c1abc'
down_revision: Union[str, None] = 'fed4031d5a4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assessment_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('question_count', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('user_preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('personalized', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_assessment_jobs_user_id_users')),
    )
    op.create_index(op.f('ix_assessment_jobs_user_id'), 'assessment_jobs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_assessment_jobs_user_id'), table_name='assessment_jobs')
    op.drop_table('assessment_jobs')



