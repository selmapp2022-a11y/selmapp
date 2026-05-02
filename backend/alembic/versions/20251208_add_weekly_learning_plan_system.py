"""add weekly learning plan system tables

Revision ID: 20251208_weekly_plan
Revises: 20251027_add_cache_daily_plan
Create Date: 2025-12-08 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20251208_weekly_plan'
down_revision = '20251027_add_cache_daily_plan'
branch_labels = None
depends_on = None


def upgrade():
    # Create weekly_learning_plans table
    op.create_table(
        'weekly_learning_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('plan_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('days_content_ready', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('generation_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('current_day', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('days_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('user_progress_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('generation_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('generation_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_weekly_learning_plans_id', 'weekly_learning_plans', ['id'], unique=False)
    op.create_index('ix_weekly_learning_plans_user', 'weekly_learning_plans', ['user_id'], unique=False)
    op.create_index('uq_weekly_plan_user_week', 'weekly_learning_plans', ['user_id', 'week_number'], unique=True)
    op.create_index('idx_weekly_plan_status', 'weekly_learning_plans', ['user_id', 'status'], unique=False)

    # Create user_weekly_progress table
    op.create_table(
        'user_weekly_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('current_week_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('current_day_in_week', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_weeks_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_days_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skill_scores', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('weak_areas', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('strong_areas', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('progress_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_day_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_weekly_progress_id', 'user_weekly_progress', ['id'], unique=False)
    op.create_index('ix_user_weekly_progress_user', 'user_weekly_progress', ['user_id'], unique=False)
    op.create_index('uq_user_weekly_progress_user', 'user_weekly_progress', ['user_id'], unique=True)

    # Create day_completion_records table
    op.create_table(
        'day_completion_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('day_number', sa.Integer(), nullable=False),
        sa.Column('exercises_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_answers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('accuracy', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('time_spent_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skill_results', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('content_types_completed', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_day_completion_records_id', 'day_completion_records', ['id'], unique=False)
    op.create_index('ix_day_completion_records_user', 'day_completion_records', ['user_id'], unique=False)
    op.create_index('uq_day_completion_user_week_day', 'day_completion_records', ['user_id', 'week_number', 'day_number'], unique=True)
    op.create_index('idx_day_completion_user_week', 'day_completion_records', ['user_id', 'week_number'], unique=False)


def downgrade():
    # Drop day_completion_records
    op.drop_index('idx_day_completion_user_week', table_name='day_completion_records')
    op.drop_index('uq_day_completion_user_week_day', table_name='day_completion_records')
    op.drop_index('ix_day_completion_records_user', table_name='day_completion_records')
    op.drop_index('ix_day_completion_records_id', table_name='day_completion_records')
    op.drop_table('day_completion_records')

    # Drop user_weekly_progress
    op.drop_index('uq_user_weekly_progress_user', table_name='user_weekly_progress')
    op.drop_index('ix_user_weekly_progress_user', table_name='user_weekly_progress')
    op.drop_index('ix_user_weekly_progress_id', table_name='user_weekly_progress')
    op.drop_table('user_weekly_progress')

    # Drop weekly_learning_plans
    op.drop_index('idx_weekly_plan_status', table_name='weekly_learning_plans')
    op.drop_index('uq_weekly_plan_user_week', table_name='weekly_learning_plans')
    op.drop_index('ix_weekly_learning_plans_user', table_name='weekly_learning_plans')
    op.drop_index('ix_weekly_learning_plans_id', table_name='weekly_learning_plans')
    op.drop_table('weekly_learning_plans')
