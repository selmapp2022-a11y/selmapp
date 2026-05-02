"""add generated content cache and daily learning plan tables

Revision ID: 20251027_add_cache_daily_plan
Revises: 
Create Date: 2025-10-27 19:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20251027_add_cache_daily_plan'
down_revision = '0f1e2d3c4b5a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'generated_content_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cache_key', sa.String(length=512), nullable=False),
        sa.Column('content_type', sa.String(length=50), nullable=False),
        sa.Column('topic', sa.String(length=200), nullable=True),
        sa.Column('level', sa.String(length=8), nullable=True),
        sa.Column('day_number', sa.Integer(), nullable=True),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('content_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ready'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_generated_content_cache_id', 'generated_content_cache', ['id'], unique=False)
    op.create_index('ix_generated_content_cache_user', 'generated_content_cache', ['user_id'], unique=False)
    op.create_index('ix_generated_content_cache_key', 'generated_content_cache', ['cache_key'], unique=True)
    op.create_index('idx_generated_content_cache_user_type_day', 'generated_content_cache', ['user_id', 'content_type', 'day_number'], unique=False)

    op.create_table(
        'daily_learning_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.String(length=10), nullable=False),
        sa.Column('plan', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_daily_learning_plans_id', 'daily_learning_plans', ['id'], unique=False)
    op.create_index('ix_daily_learning_plans_user', 'daily_learning_plans', ['user_id'], unique=False)
    op.create_index('uq_daily_learning_plan_user_date', 'daily_learning_plans', ['user_id', 'date'], unique=True)


def downgrade():
    op.drop_index('uq_daily_learning_plan_user_date', table_name='daily_learning_plans')
    op.drop_index('ix_daily_learning_plans_user', table_name='daily_learning_plans')
    op.drop_index('ix_daily_learning_plans_id', table_name='daily_learning_plans')
    op.drop_table('daily_learning_plans')

    op.drop_index('idx_generated_content_cache_user_type_day', table_name='generated_content_cache')
    op.drop_index('ix_generated_content_cache_key', table_name='generated_content_cache')
    op.drop_index('ix_generated_content_cache_user', table_name='generated_content_cache')
    op.drop_index('ix_generated_content_cache_id', table_name='generated_content_cache')
    op.drop_table('generated_content_cache')


