"""add_enhanced_vocabulary_system

Revision ID: ce3b8ec7e9a
Revises: 02fc56850fd3
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ce3b8ec7e9a'
down_revision: Union[str, None] = '02fc56850fd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to existing vocabulary table
    op.add_column('vocabulary', sa.Column('synonyms', sa.JSON(), nullable=True))
    op.add_column('vocabulary', sa.Column('antonyms', sa.JSON(), nullable=True))
    op.add_column('vocabulary', sa.Column('word_family', sa.JSON(), nullable=True))
    op.add_column('vocabulary', sa.Column('collocations', sa.JSON(), nullable=True))
    op.add_column('vocabulary', sa.Column('usage_notes', sa.Text(), nullable=True))
    op.add_column('vocabulary', sa.Column('etymology', sa.String(length=500), nullable=True))
    op.add_column('vocabulary', sa.Column('cefr_source', sa.String(length=100), nullable=True, default='official'))
    op.add_column('vocabulary', sa.Column('is_core_vocabulary', sa.Boolean(), nullable=True, default=False))
    op.add_column('vocabulary', sa.Column('topic_categories', sa.JSON(), nullable=True))
    
    # Create vocabulary status enum (idempotent)
    #
    # IMPORTANT:
    # - Postgres ENUM types are schema objects.
    # - If you create an enum type explicitly and then use a SQLAlchemy Enum
    #   column type with `create_type=True` (default), SQLAlchemy will try to
    #   CREATE TYPE again during table creation and crash with DuplicateObjectError.
    #
    # We create the type once (with a duplicate-safe block) and then always
    # reference it using postgresql.ENUM(create_type=False).
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE vocabularystatus AS ENUM ('NEW', 'LEARNING', 'REVIEW', 'MASTERED'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$;"
    )
    vocabularystatus = postgresql.ENUM(
        'NEW', 'LEARNING', 'REVIEW', 'MASTERED',
        name='vocabularystatus',
        create_type=False,
    )
    
    # Create user_vocabulary table
    op.create_table('user_vocabulary',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('vocabulary_id', sa.Integer(), nullable=False),
        sa.Column('status', vocabularystatus, nullable=True, default='NEW'),
        sa.Column('mastery_level', sa.Float(), nullable=True, default=0.0),
        sa.Column('ease_factor', sa.Float(), nullable=True, default=2.5),
        sa.Column('interval_days', sa.Integer(), nullable=True, default=1),
        sa.Column('next_review_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('times_seen', sa.Integer(), nullable=True, default=0),
        sa.Column('times_correct', sa.Integer(), nullable=True, default=0),
        sa.Column('times_incorrect', sa.Integer(), nullable=True, default=0),
        sa.Column('streak_count', sa.Integer(), nullable=True, default=0),
        sa.Column('first_encountered_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_reviewed_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen_in_context', sa.String(length=500), nullable=True),
        sa.Column('user_notes', sa.Text(), nullable=True),
        sa.Column('personal_examples', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vocabulary_id'], ['vocabulary.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_user_vocabulary_id', 'user_vocabulary', ['id'], unique=False)
    op.create_index('idx_user_vocabulary_user_status', 'user_vocabulary', ['user_id', 'status'], unique=False)
    op.create_index('idx_user_vocabulary_review_date', 'user_vocabulary', ['next_review_date'], unique=False)
    op.create_index('idx_user_vocabulary_user_word', 'user_vocabulary', ['user_id', 'vocabulary_id'], unique=True)
    
    # Create vocabulary_sets table
    op.create_table('vocabulary_sets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'difficulty_level',
            postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False),
            nullable=False,
        ),
        sa.Column('topic', sa.String(length=100), nullable=True),
        sa.Column('estimated_study_time', sa.Integer(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True, default=0),
        sa.Column('is_public', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_featured', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vocabulary_sets_id', 'vocabulary_sets', ['id'], unique=False)
    
    # Create vocabulary_set_items table
    op.create_table('vocabulary_set_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vocabulary_set_id', sa.Integer(), nullable=False),
        sa.Column('vocabulary_id', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=True, default=0),
        sa.Column('is_priority', sa.Boolean(), nullable=True, default=False),
        sa.Column('custom_definition', sa.Text(), nullable=True),
        sa.Column('custom_example', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['vocabulary_id'], ['vocabulary.id'], ),
        sa.ForeignKeyConstraint(['vocabulary_set_id'], ['vocabulary_sets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vocabulary_set_items_id', 'vocabulary_set_items', ['id'], unique=False)
    op.create_index('idx_vocabulary_set_items_order', 'vocabulary_set_items', ['vocabulary_set_id', 'order_index'], unique=False)
    
    # Create vocabulary_exercises table
    op.create_table('vocabulary_exercises',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vocabulary_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exercise_type', sa.String(length=50), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('correct_answer', sa.String(length=500), nullable=False),
        sa.Column('user_answer', sa.String(length=500), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('points_earned', sa.Integer(), nullable=True, default=0),
        sa.Column('time_taken_seconds', sa.Integer(), nullable=True),
        sa.Column(
            'difficulty_at_time',
            postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel', create_type=False),
            nullable=True,
        ),
        sa.Column('exercise_context', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vocabulary_id'], ['vocabulary.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vocabulary_exercises_id', 'vocabulary_exercises', ['id'], unique=False)
    op.create_index('idx_vocabulary_exercises_user_date', 'vocabulary_exercises', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_vocabulary_exercises_vocab_type', 'vocabulary_exercises', ['vocabulary_id', 'exercise_type'], unique=False)
    
    # Add new indexes for vocabulary table
    op.create_index('idx_vocabulary_level_word', 'vocabulary', ['difficulty_level', 'word'], unique=False)
    op.create_index('idx_vocabulary_frequency', 'vocabulary', ['frequency_rank'], unique=False)


def downgrade() -> None:
    # Drop new indexes
    op.drop_index('idx_vocabulary_frequency', table_name='vocabulary')
    op.drop_index('idx_vocabulary_level_word', table_name='vocabulary')
    
    # Drop vocabulary_exercises table
    op.drop_index('idx_vocabulary_exercises_vocab_type', table_name='vocabulary_exercises')
    op.drop_index('idx_vocabulary_exercises_user_date', table_name='vocabulary_exercises')
    op.drop_index('idx_vocabulary_exercises_id', table_name='vocabulary_exercises')
    op.drop_table('vocabulary_exercises')
    
    # Drop vocabulary_set_items table
    op.drop_index('idx_vocabulary_set_items_order', table_name='vocabulary_set_items')
    op.drop_index('idx_vocabulary_set_items_id', table_name='vocabulary_set_items')
    op.drop_table('vocabulary_set_items')
    
    # Drop vocabulary_sets table
    op.drop_index('idx_vocabulary_sets_id', table_name='vocabulary_sets')
    op.drop_table('vocabulary_sets')
    
    # Drop user_vocabulary table
    op.drop_index('idx_user_vocabulary_user_word', table_name='user_vocabulary')
    op.drop_index('idx_user_vocabulary_review_date', table_name='user_vocabulary')
    op.drop_index('idx_user_vocabulary_user_status', table_name='user_vocabulary')
    op.drop_index('idx_user_vocabulary_id', table_name='user_vocabulary')
    op.drop_table('user_vocabulary')
    
    # Drop vocabulary status enum
    op.execute("DROP TYPE IF EXISTS vocabularystatus")
    
    # Remove new columns from vocabulary table
    op.drop_column('vocabulary', 'topic_categories')
    op.drop_column('vocabulary', 'is_core_vocabulary')
    op.drop_column('vocabulary', 'cefr_source')
    op.drop_column('vocabulary', 'etymology')
    op.drop_column('vocabulary', 'usage_notes')
    op.drop_column('vocabulary', 'collocations')
    op.drop_column('vocabulary', 'word_family')
    op.drop_column('vocabulary', 'antonyms')
    op.drop_column('vocabulary', 'synonyms') 