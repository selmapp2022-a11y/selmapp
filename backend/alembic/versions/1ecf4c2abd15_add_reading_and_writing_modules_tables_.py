"""Add Reading and Writing modules tables manually

Revision ID: 1ecf4c2abd15
Revises: b15a7c44a2cb
Create Date: 2025-06-21 20:35:25.847064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1ecf4c2abd15'
down_revision: Union[str, None] = 'b15a7c44a2cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create new enums for Reading and Writing modules (with IF NOT EXISTS)
    op.execute("DO $$ BEGIN CREATE TYPE readingtexttype AS ENUM ('ARTICLE', 'STORY', 'NEWS', 'LETTER', 'ESSAY', 'DIALOGUE', 'INSTRUCTION'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE writingtype AS ENUM ('ESSAY', 'LETTER', 'EMAIL', 'STORY', 'REPORT', 'REVIEW', 'DESCRIPTION', 'DIALOGUE', 'SUMMARY'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE writingskilllevel AS ENUM ('BEGINNER', 'INTERMEDIATE', 'ADVANCED'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Create reading_texts table
    op.create_table('reading_texts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        # IMPORTANT: use postgresql.ENUM(create_type=False) so Alembic/SQLAlchemy
        # does NOT try to auto-create the enum type during table creation.
        # The enum is created explicitly above via op.execute(...).
        sa.Column('text_type', postgresql.ENUM('ARTICLE', 'STORY', 'NEWS', 'LETTER', 'ESSAY', 'DIALOGUE', 'INSTRUCTION', name='readingtexttype', create_type=False), nullable=False),
        sa.Column('difficulty_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=False),
        sa.Column('estimated_reading_time', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=200), nullable=True),
        sa.Column('author', sa.String(length=200), nullable=True),
        sa.Column('topic', sa.String(length=100), nullable=True),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reading_texts_id', 'reading_texts', ['id'], unique=False)
    
    # Create reading_exercises table
    op.create_table('reading_exercises',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reading_text_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('exercise_type', sa.String(length=50), nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('correct_answer', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('points', sa.Integer(), nullable=True, default=1),
        sa.Column('order_index', sa.Integer(), nullable=True, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['reading_text_id'], ['reading_texts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reading_exercises_id', 'reading_exercises', ['id'], unique=False)
    
    # Create reading_attempts table
    op.create_table('reading_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reading_text_id', sa.Integer(), nullable=False),
        sa.Column('reading_exercise_id', sa.Integer(), nullable=True),
        sa.Column('reading_time_seconds', sa.Integer(), nullable=True),
        sa.Column('words_per_minute', sa.Float(), nullable=True),
        sa.Column('user_answer', sa.Text(), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('score', sa.Float(), nullable=True, default=0.0),
        sa.Column('comprehension_score', sa.Float(), nullable=True),
        sa.Column('vocabulary_learned', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reading_text_id'], ['reading_texts.id'], ),
        sa.ForeignKeyConstraint(['reading_exercise_id'], ['reading_exercises.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reading_attempts_id', 'reading_attempts', ['id'], unique=False)
    
    # Create vocabulary_highlights table
    op.create_table('vocabulary_highlights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reading_text_id', sa.Integer(), nullable=False),
        sa.Column('word', sa.String(length=100), nullable=False),
        sa.Column('definition', sa.Text(), nullable=False),
        sa.Column('part_of_speech', sa.String(length=50), nullable=True),
        sa.Column('difficulty_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False), nullable=False),
        sa.Column('start_position', sa.Integer(), nullable=True),
        sa.Column('end_position', sa.Integer(), nullable=True),
        sa.Column('phonetic', sa.String(length=200), nullable=True),
        sa.Column('example_sentence', sa.Text(), nullable=True),
        sa.Column('translation', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['reading_text_id'], ['reading_texts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_vocabulary_highlights_id', 'vocabulary_highlights', ['id'], unique=False)
    
    # Create reading_progress table
    op.create_table('reading_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_texts_read', sa.Integer(), nullable=True, default=0),
        sa.Column('total_reading_time_minutes', sa.Integer(), nullable=True, default=0),
        sa.Column('average_reading_speed_wpm', sa.Float(), nullable=True, default=0.0),
        sa.Column('average_comprehension_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_exercises_completed', sa.Integer(), nullable=True, default=0),
        sa.Column('total_exercises_correct', sa.Integer(), nullable=True, default=0),
        sa.Column('current_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False), nullable=True),
        sa.Column('texts_completed_by_level', sa.JSON(), nullable=True, default='{}'),
        sa.Column('total_vocabulary_learned', sa.Integer(), nullable=True, default=0),
        sa.Column('vocabulary_by_level', sa.JSON(), nullable=True, default='{}'),
        sa.Column('current_reading_streak', sa.Integer(), nullable=True, default=0),
        sa.Column('longest_reading_streak', sa.Integer(), nullable=True, default=0),
        sa.Column('last_reading_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reading_progress_id', 'reading_progress', ['id'], unique=False)
    
    # Create writing_prompts table
    op.create_table('writing_prompts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('writing_type', postgresql.ENUM('ESSAY', 'LETTER', 'EMAIL', 'STORY', 'REPORT', 'REVIEW', 'DESCRIPTION', 'DIALOGUE', 'SUMMARY', name='writingtype', create_type=False), nullable=False),
        sa.Column('difficulty_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False), nullable=False),
        sa.Column('skill_level', postgresql.ENUM('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='writingskilllevel', create_type=False), nullable=False),
        sa.Column('min_words', sa.Integer(), nullable=True, default=50),
        sa.Column('max_words', sa.Integer(), nullable=True, default=500),
        sa.Column('time_limit_minutes', sa.Integer(), nullable=True),
        sa.Column('required_vocabulary', sa.JSON(), nullable=True),
        sa.Column('grammar_focus', sa.JSON(), nullable=True),
        sa.Column('topic_keywords', sa.JSON(), nullable=True),
        sa.Column('scoring_rubric', sa.JSON(), nullable=True),
        sa.Column('max_points', sa.Integer(), nullable=True, default=100),
        sa.Column('topic', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_writing_prompts_id', 'writing_prompts', ['id'], unique=False)
    
    # Create writing_submissions table
    op.create_table('writing_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('writing_prompt_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=False),
        sa.Column('time_spent_minutes', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('original_content', sa.Text(), nullable=True),
        sa.Column('corrected_content', sa.Text(), nullable=True),
        sa.Column('spelling_errors', sa.JSON(), nullable=True),
        sa.Column('grammar_errors', sa.JSON(), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('grammar_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('vocabulary_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('coherence_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('task_achievement_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('ai_feedback', sa.Text(), nullable=True),
        sa.Column('suggestions', sa.JSON(), nullable=True),
        sa.Column('strengths', sa.JSON(), nullable=True),
        sa.Column('weaknesses', sa.JSON(), nullable=True),
        sa.Column('is_draft', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_evaluated', sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['writing_prompt_id'], ['writing_prompts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_writing_submissions_id', 'writing_submissions', ['id'], unique=False)
    
    # Create writing_feedback table
    op.create_table('writing_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('writing_submission_id', sa.Integer(), nullable=False),
        sa.Column('content_organization', sa.Float(), nullable=True, default=0.0),
        sa.Column('language_accuracy', sa.Float(), nullable=True, default=0.0),
        sa.Column('vocabulary_range', sa.Float(), nullable=True, default=0.0),
        sa.Column('sentence_structure', sa.Float(), nullable=True, default=0.0),
        sa.Column('punctuation_mechanics', sa.Float(), nullable=True, default=0.0),
        sa.Column('positive_aspects', sa.JSON(), nullable=True),
        sa.Column('areas_for_improvement', sa.JSON(), nullable=True),
        sa.Column('specific_errors', sa.JSON(), nullable=True),
        sa.Column('vocabulary_suggestions', sa.JSON(), nullable=True),
        sa.Column('next_steps', sa.JSON(), nullable=True),
        sa.Column('recommended_exercises', sa.JSON(), nullable=True),
        sa.Column('feedback_type', sa.String(length=50), nullable=True, default='automated'),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['writing_submission_id'], ['writing_submissions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_writing_feedback_id', 'writing_feedback', ['id'], unique=False)
    
    # Create writing_templates table
    op.create_table('writing_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('writing_type', postgresql.ENUM('ESSAY', 'LETTER', 'EMAIL', 'STORY', 'REPORT', 'REVIEW', 'DESCRIPTION', 'DIALOGUE', 'SUMMARY', name='writingtype', create_type=False), nullable=False),
        sa.Column('difficulty_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False), nullable=False),
        sa.Column('structure', sa.JSON(), nullable=True),
        sa.Column('sample_phrases', sa.JSON(), nullable=True),
        sa.Column('transition_words', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('example_text', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_writing_templates_id', 'writing_templates', ['id'], unique=False)
    
    # Create writing_progress table
    op.create_table('writing_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('total_submissions', sa.Integer(), nullable=True, default=0),
        sa.Column('total_words_written', sa.Integer(), nullable=True, default=0),
        sa.Column('total_writing_time_minutes', sa.Integer(), nullable=True, default=0),
        sa.Column('average_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('best_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('average_grammar_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('average_vocabulary_score', sa.Float(), nullable=True, default=0.0),
        sa.Column('grammar_improvement_rate', sa.Float(), nullable=True, default=0.0),
        sa.Column('vocabulary_improvement_rate', sa.Float(), nullable=True, default=0.0),
        sa.Column('writing_speed_wpm', sa.Float(), nullable=True, default=0.0),
        sa.Column('current_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False), nullable=True),
        sa.Column('submissions_by_level', sa.JSON(), nullable=True, default='{}'),
        sa.Column('submissions_by_type', sa.JSON(), nullable=True, default='{}'),
        sa.Column('common_grammar_errors', sa.JSON(), nullable=True, default='[]'),
        sa.Column('common_spelling_errors', sa.JSON(), nullable=True, default='[]'),
        sa.Column('error_reduction_rate', sa.Float(), nullable=True, default=0.0),
        sa.Column('current_writing_streak', sa.Integer(), nullable=True, default=0),
        sa.Column('longest_writing_streak', sa.Integer(), nullable=True, default=0),
        sa.Column('last_writing_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_writing_progress_id', 'writing_progress', ['id'], unique=False)
    
    # Create grammar_rules table
    op.create_table('grammar_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('difficulty_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False), nullable=False),
        sa.Column('rule_description', sa.Text(), nullable=False),
        sa.Column('pattern', sa.String(length=500), nullable=True),
        sa.Column('correct_examples', sa.JSON(), nullable=True),
        sa.Column('incorrect_examples', sa.JSON(), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('correction_suggestion', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('priority', sa.Integer(), nullable=True, default=1),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_grammar_rules_id', 'grammar_rules', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_index('ix_grammar_rules_id', table_name='grammar_rules')
    op.drop_table('grammar_rules')
    
    op.drop_index('ix_writing_progress_id', table_name='writing_progress')
    op.drop_table('writing_progress')
    
    op.drop_index('ix_writing_templates_id', table_name='writing_templates')
    op.drop_table('writing_templates')
    
    op.drop_index('ix_writing_feedback_id', table_name='writing_feedback')
    op.drop_table('writing_feedback')
    
    op.drop_index('ix_writing_submissions_id', table_name='writing_submissions')
    op.drop_table('writing_submissions')
    
    op.drop_index('ix_writing_prompts_id', table_name='writing_prompts')
    op.drop_table('writing_prompts')
    
    op.drop_index('ix_reading_progress_id', table_name='reading_progress')
    op.drop_table('reading_progress')
    
    op.drop_index('ix_vocabulary_highlights_id', table_name='vocabulary_highlights')
    op.drop_table('vocabulary_highlights')
    
    op.drop_index('ix_reading_attempts_id', table_name='reading_attempts')
    op.drop_table('reading_attempts')
    
    op.drop_index('ix_reading_exercises_id', table_name='reading_exercises')
    op.drop_table('reading_exercises')
    
    op.drop_index('ix_reading_texts_id', table_name='reading_texts')
    op.drop_table('reading_texts')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS readingtexttype")
    op.execute("DROP TYPE IF EXISTS writingtype")
    op.execute("DROP TYPE IF EXISTS writingskilllevel")
