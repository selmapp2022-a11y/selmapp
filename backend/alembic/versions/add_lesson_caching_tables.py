"""add lesson caching tables

Revision ID: add_lesson_caching
Revises: [latest_revision_id]
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_lesson_caching'
down_revision: Union[str, None] = '20251027_add_cache_daily_plan'   # Update this with actual previous revision
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create ai_generated_lessons table
    op.create_table('ai_generated_lessons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('lesson_type', sa.Enum('CONVERSATION', 'WRITING', 'GRAMMAR', 'VOCABULARY', 'PRONUNCIATION', 'COMPREHENSION', 'MIXED', name='lessontype'), nullable=False),
        sa.Column('difficulty_level', sa.Enum('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel'), nullable=False),
        sa.Column('topic', sa.String(length=200), nullable=True),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('generated_by', sa.String(length=50), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('average_rating', sa.Float(), nullable=True),
        sa.Column('total_completions', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create lesson_progress table
    op.create_table('lesson_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=True),
        sa.Column('time_spent_minutes', sa.Integer(), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('current_step', sa.Integer(), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=True),
        sa.Column('accuracy_score', sa.Float(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('performance_score', sa.Float(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=True),
        sa.Column('completion_rating', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('session_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('answers_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['lesson_id'], ['ai_generated_lessons.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create lesson_generation_analytics table
    op.create_table('lesson_generation_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('lessons_generated', sa.Integer(), nullable=True),
        sa.Column('unique_users', sa.Integer(), nullable=True),
        sa.Column('total_generation_time_seconds', sa.Float(), nullable=True),
        sa.Column('average_generation_time_seconds', sa.Float(), nullable=True),
        sa.Column('lessons_by_type', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('lessons_by_difficulty', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('top_topics', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('cache_hit_rate', sa.Float(), nullable=True),
        sa.Column('expired_lessons_cleaned', sa.Integer(), nullable=True),
        sa.Column('average_completion_rate', sa.Float(), nullable=True),
        sa.Column('average_session_duration_minutes', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create lesson_templates table
    op.create_table('lesson_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('lesson_type', sa.Enum('CONVERSATION', 'WRITING', 'GRAMMAR', 'VOCABULARY', 'PRONUNCIATION', 'COMPREHENSION', 'MIXED', name='lessontype'), nullable=False),
        sa.Column('difficulty_level', sa.Enum('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel'), nullable=False),
        sa.Column('topic_category', sa.String(length=100), nullable=False),
        sa.Column('template_structure', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('content_placeholders', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('personalization_rules', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('difficulty_scaling', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for better performance
    op.create_index(op.f('ix_ai_generated_lessons_user_id'), 'ai_generated_lessons', ['user_id'], unique=False)
    op.create_index(op.f('ix_ai_generated_lessons_lesson_type'), 'ai_generated_lessons', ['lesson_type'], unique=False)
    op.create_index(op.f('ix_ai_generated_lessons_difficulty_level'), 'ai_generated_lessons', ['difficulty_level'], unique=False)
    op.create_index(op.f('ix_ai_generated_lessons_is_active'), 'ai_generated_lessons', ['is_active'], unique=False)
    op.create_index(op.f('ix_ai_generated_lessons_expires_at'), 'ai_generated_lessons', ['expires_at'], unique=False)

    op.create_index(op.f('ix_lesson_progress_user_id'), 'lesson_progress', ['user_id'], unique=False)
    op.create_index(op.f('ix_lesson_progress_lesson_id'), 'lesson_progress', ['lesson_id'], unique=False)
    op.create_index(op.f('ix_lesson_progress_is_completed'), 'lesson_progress', ['is_completed'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_lesson_progress_is_completed'), table_name='lesson_progress')
    op.drop_index(op.f('ix_lesson_progress_lesson_id'), table_name='lesson_progress')
    op.drop_index(op.f('ix_lesson_progress_user_id'), table_name='lesson_progress')

    op.drop_index(op.f('ix_ai_generated_lessons_expires_at'), table_name='ai_generated_lessons')
    op.drop_index(op.f('ix_ai_generated_lessons_is_active'), table_name='ai_generated_lessons')
    op.drop_index(op.f('ix_ai_generated_lessons_difficulty_level'), table_name='ai_generated_lessons')
    op.drop_index(op.f('ix_ai_generated_lessons_lesson_type'), table_name='ai_generated_lessons')
    op.drop_index(op.f('ix_ai_generated_lessons_user_id'), table_name='ai_generated_lessons')

    # Drop tables
    op.drop_table('lesson_templates')
    op.drop_table('lesson_generation_analytics')
    op.drop_table('lesson_progress')
    op.drop_table('ai_generated_lessons')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS lessontype")
    op.execute("DROP TYPE IF EXISTS difficultylevel")















