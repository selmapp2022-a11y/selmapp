"""add_onboarding_and_category_system

Revision ID: db8ca0b68629
Revises: ce3b8ec7e9a
Create Date: 2025-06-23 01:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'db8ca0b68629'
down_revision: Union[str, None] = 'ce3b8ec7e9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    
    # Create enums if they don't exist
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE learningcategory AS ENUM (
                'GENERAL_ENGLISH', 'BUSINESS_ENGLISH', 'TRAVEL_ENGLISH', 'ACADEMIC_ENGLISH',
                'EXAM_PREPARATION', 'CONVERSATION_PRACTICE', 'GRAMMAR_FOCUS', 'VOCABULARY_BUILDING',
                'PRONUNCIATION_IMPROVEMENT', 'WRITING_SKILLS', 'READING_COMPREHENSION', 'LISTENING_SKILLS'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE onboardingstep AS ENUM (
                'WELCOME', 'LEVEL_ASSESSMENT', 'CATEGORY_SELECTION', 'GOALS_SETTING',
                'PREFERENCES_SETUP', 'LEARNING_PATH_GENERATION', 'COMPLETED'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE learningstyle AS ENUM (
                'VISUAL', 'AUDITORY', 'KINESTHETIC', 'READING_WRITING', 'MIXED'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    # Create category_learning_templates table
    op.create_table('category_learning_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', postgresql.ENUM('GENERAL_ENGLISH', 'BUSINESS_ENGLISH', 'TRAVEL_ENGLISH', 'ACADEMIC_ENGLISH', 'EXAM_PREPARATION', 'CONVERSATION_PRACTICE', 'GRAMMAR_FOCUS', 'VOCABULARY_BUILDING', 'PRONUNCIATION_IMPROVEMENT', 'WRITING_SKILLS', 'READING_COMPREHENSION', 'LISTENING_SKILLS', name='learningcategory', create_type=False), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_levels', sa.JSON(), nullable=False),
        sa.Column('template_data', sa.JSON(), nullable=False),
        sa.Column('estimated_duration_weeks', sa.Integer(), nullable=False),
        sa.Column('total_milestones', sa.Integer(), nullable=False),
        sa.Column('listening_percentage', sa.Float(), nullable=True),
        sa.Column('speaking_percentage', sa.Float(), nullable=True),
        sa.Column('reading_percentage', sa.Float(), nullable=True),
        sa.Column('writing_percentage', sa.Float(), nullable=True),
        sa.Column('required_vocabulary_topics', sa.JSON(), nullable=True),
        sa.Column('required_grammar_points', sa.JSON(), nullable=True),
        sa.Column('recommended_content_types', sa.JSON(), nullable=True),
        sa.Column('difficulty_level', sa.String(length=20), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True, default=0),
        sa.Column('average_completion_rate', sa.Float(), nullable=True),
        sa.Column('average_satisfaction_rating', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_category_learning_templates'))
    )
    op.create_index(op.f('ix_category_learning_templates_id'), 'category_learning_templates', ['id'], unique=False)
    
    # Create user_category_preferences table
    op.create_table('user_category_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category', postgresql.ENUM('GENERAL_ENGLISH', 'BUSINESS_ENGLISH', 'TRAVEL_ENGLISH', 'ACADEMIC_ENGLISH', 'EXAM_PREPARATION', 'CONVERSATION_PRACTICE', 'GRAMMAR_FOCUS', 'VOCABULARY_BUILDING', 'PRONUNCIATION_IMPROVEMENT', 'WRITING_SKILLS', 'READING_COMPREHENSION', 'LISTENING_SKILLS', name='learningcategory', create_type=False), nullable=False),
        sa.Column('priority_level', sa.Integer(), nullable=True, default=3),
        sa.Column('interest_score', sa.Float(), nullable=True, default=0.5),
        sa.Column('preferred_focus_areas', sa.JSON(), nullable=True),
        sa.Column('preferred_content_difficulty', sa.String(length=20), nullable=True),
        sa.Column('preferred_session_duration', sa.Integer(), nullable=True),
        sa.Column('time_spent_minutes', sa.Integer(), nullable=True, default=0),
        sa.Column('activities_completed', sa.Integer(), nullable=True, default=0),
        sa.Column('average_performance', sa.Float(), nullable=True),
        sa.Column('satisfaction_rating', sa.Float(), nullable=True),
        sa.Column('feedback_notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_activity_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_category_preferences_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_category_preferences'))
    )
    op.create_index(op.f('ix_user_category_preferences_id'), 'user_category_preferences', ['id'], unique=False)
    
    # Create user_onboarding table
    op.create_table('user_onboarding',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('current_step', postgresql.ENUM('WELCOME', 'LEVEL_ASSESSMENT', 'CATEGORY_SELECTION', 'GOALS_SETTING', 'PREFERENCES_SETUP', 'LEARNING_PATH_GENERATION', 'COMPLETED', name='onboardingstep', create_type=False), nullable=True, default='WELCOME'),
        sa.Column('is_completed', sa.Boolean(), nullable=True, default=False),
        sa.Column('completion_percentage', sa.Float(), nullable=True, default=0.0),
        sa.Column('assessed_level', sa.String(length=2), nullable=True),
        sa.Column('assessment_score', sa.Float(), nullable=True),
        sa.Column('assessment_details', sa.JSON(), nullable=True),
        sa.Column('selected_categories', sa.JSON(), nullable=True),
        sa.Column('primary_category', postgresql.ENUM('GENERAL_ENGLISH', 'BUSINESS_ENGLISH', 'TRAVEL_ENGLISH', 'ACADEMIC_ENGLISH', 'EXAM_PREPARATION', 'CONVERSATION_PRACTICE', 'GRAMMAR_FOCUS', 'VOCABULARY_BUILDING', 'PRONUNCIATION_IMPROVEMENT', 'WRITING_SKILLS', 'READING_COMPREHENSION', 'LISTENING_SKILLS', name='learningcategory', create_type=False), nullable=True),
        sa.Column('category_priorities', sa.JSON(), nullable=True),
        sa.Column('learning_goals', sa.JSON(), nullable=True),
        sa.Column('motivation_factors', sa.JSON(), nullable=True),
        sa.Column('target_timeline', sa.String(length=50), nullable=True),
        sa.Column('daily_study_commitment', sa.Integer(), nullable=True),
        sa.Column('preferred_learning_style', postgresql.ENUM('VISUAL', 'AUDITORY', 'KINESTHETIC', 'READING_WRITING', 'MIXED', name='learningstyle', create_type=False), nullable=True),
        sa.Column('preferred_difficulty', sa.String(length=20), nullable=True),
        sa.Column('preferred_content_types', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_step_completed_at', sa.DateTime(), nullable=True),
        sa.Column('onboarding_feedback', sa.Text(), nullable=True),
        sa.Column('onboarding_rating', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_onboarding_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_user_onboarding')),
        sa.UniqueConstraint('user_id', name=op.f('uq_user_onboarding_user_id'))
    )
    op.create_index(op.f('ix_user_onboarding_id'), 'user_onboarding', ['id'], unique=False)
    
    # ------------------------------------------------------------------
    # Content table rename / normalization
    #
    # Older schema used `contents` (plural). Current SQLAlchemy models use
    # `content` (singular). On a fresh database this migration must create the
    # new `content` table BEFORE switching the FK on `exercises`, otherwise the
    # FK creation fails with:
    #   UndefinedTableError: relation "content" does not exist
    # ------------------------------------------------------------------

    # Create new `content` table if it doesn't exist (idempotent for safety).
    # Use existing enums created earlier (contenttype, difficultylevel).
    connection.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema='public' AND table_name='content'
            ) THEN
                CREATE TABLE content (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(300) NOT NULL,
                    description TEXT,
                    content_type contenttype NOT NULL,
                    difficulty_level difficultylevel NOT NULL,
                    content_data JSON,
                    tags JSON,
                    estimated_duration INTEGER,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_featured BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                    updated_at TIMESTAMP WITH TIME ZONE
                );
                CREATE INDEX IF NOT EXISTS ix_content_id ON content (id);
            END IF;
        END $$;
    """))

    # If `contents` exists, copy any rows into `content` preserving ids.
    # This is safe for fresh installs (usually empty) and for upgrades.
    connection.execute(sa.text("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema='public' AND table_name='contents'
            ) THEN
                INSERT INTO content (
                    id, title, description, content_type, difficulty_level,
                    content_data, tags, estimated_duration, is_active, created_at, updated_at
                )
                SELECT
                    id,
                    title,
                    description,
                    content_type,
                    difficulty_level,
                    content_data,
                    tags,
                    duration_minutes,  -- legacy name
                    COALESCE(is_active, TRUE),
                    created_at,
                    updated_at
                FROM contents
                ON CONFLICT (id) DO NOTHING;
            END IF;
        END $$;
    """))

    # Fix foreign key reference from exercises to content (not contents)
    # Drop the old FK only if it exists (fresh/new DBs may differ).
    try:
        op.drop_constraint(op.f('fk_exercises_content_id_contents'), 'exercises', type_='foreignkey')
    except Exception:
        pass
    op.create_foreign_key(op.f('fk_exercises_content_id_content'), 'exercises', 'content', ['content_id'], ['id'])
    
    # Update grammar table structure
    op.add_column('grammar', sa.Column('rule', sa.Text(), nullable=False, server_default=''))
    op.add_column('grammar', sa.Column('explanation', sa.Text(), nullable=False, server_default=''))
    op.alter_column('grammar', 'title',
                   existing_type=sa.VARCHAR(length=200),
                   type_=sa.String(length=300),
                   existing_nullable=False)
    
    # Remove old grammar columns
    op.drop_column('grammar', 'order_index')
    op.drop_column('grammar', 'category')
    op.drop_column('grammar', 'description')
    op.drop_column('grammar', 'rule_explanation')
    
    # Remove server defaults after adding columns
    op.alter_column('grammar', 'rule', server_default=None)
    op.alter_column('grammar', 'explanation', server_default=None)
    
    # ------------------------------------------------------------------
    # Index/constraint normalization (idempotent)
    #
    # This migration historically ran against multiple legacy schemas.
    # On a fresh install, earlier migrations may already create the desired
    # indexes (and some legacy constraints may never exist). Use IF EXISTS /
    # IF NOT EXISTS to avoid hard failures like:
    #   UndefinedObjectError: constraint "..."" does not exist
    #   DuplicateObjectError: relation/index already exists
    # ------------------------------------------------------------------

    # Progress tables created via raw SQL earlier used `user_id UNIQUE`, which
    # creates default unique constraints named like `*_user_id_key`. Drop if present.
    connection.execute(sa.text(
        "ALTER TABLE listening_progress DROP CONSTRAINT IF EXISTS listening_progress_user_id_key;"
    ))
    connection.execute(sa.text(
        "ALTER TABLE speaking_progress DROP CONSTRAINT IF EXISTS speaking_progress_user_id_key;"
    ))

    # Older schemas may have had a unique constraint on (user_id, vocabulary_id).
    # Newer schemas use a named unique index instead.
    connection.execute(sa.text(
        "ALTER TABLE user_vocabulary DROP CONSTRAINT IF EXISTS user_vocabulary_user_id_vocabulary_id_key;"
    ))

    # Ensure the desired unique index exists.
    connection.execute(sa.text(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_vocabulary_user_word "
        "ON user_vocabulary (user_id, vocabulary_id);"
    ))
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_user_vocabulary_id ON user_vocabulary (id);"
    ))

    # Update vocabulary exercises indexes (drop legacy index if it existed in older schemas)
    connection.execute(sa.text("DROP INDEX IF EXISTS idx_vocabulary_exercises_user_vocab;"))
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_vocabulary_exercises_user_date "
        "ON vocabulary_exercises (user_id, created_at);"
    ))
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_vocabulary_exercises_vocab_type "
        "ON vocabulary_exercises (vocabulary_id, exercise_type);"
    ))
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_vocabulary_exercises_id ON vocabulary_exercises (id);"
    ))

    # Update vocabulary set items indexes
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_vocabulary_set_items_order "
        "ON vocabulary_set_items (vocabulary_set_id, order_index);"
    ))
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_vocabulary_set_items_id ON vocabulary_set_items (id);"
    ))
    connection.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_vocabulary_sets_id ON vocabulary_sets (id);"
    ))

    # Update voice profiles constraint (old schema used `user_id UNIQUE`)
    connection.execute(sa.text(
        "ALTER TABLE voice_profiles DROP CONSTRAINT IF EXISTS voice_profiles_user_id_key;"
    ))
    connection.execute(sa.text(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_voice_profiles_user_id'
            ) THEN
                ALTER TABLE voice_profiles
                ADD CONSTRAINT uq_voice_profiles_user_id UNIQUE (user_id);
            END IF;
        END $$;
        """
    ))
    
    # Drop old `contents` table (legacy) if it exists now that everything points to `content`
    # Use raw SQL with IF EXISTS because Alembic's drop_table isn't conditional.
    connection.execute(sa.text("DROP TABLE IF EXISTS contents CASCADE;"))


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate contents table
    op.create_table('contents',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('title', sa.VARCHAR(length=200), autoincrement=False, nullable=False),
        sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True),
        sa.Column('content_type', postgresql.ENUM('VOCABULARY', 'GRAMMAR', 'LISTENING', 'READING', 'SPEAKING', 'WRITING', name='contenttype'), autoincrement=False, nullable=False),
        sa.Column('difficulty_level', postgresql.ENUM('A1', 'A2', 'B1', 'B2', 'C1', 'C2', name='difficultylevel'), autoincrement=False, nullable=False),
        sa.Column('content_data', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
        sa.Column('audio_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column('image_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column('video_url', sa.VARCHAR(length=500), autoincrement=False, nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True),
        sa.Column('duration_minutes', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('order_index', sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('is_active', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('is_premium', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_contents'))
    )
    op.create_index(op.f('ix_contents_id'), 'contents', ['id'], unique=False)
    
    # Revert foreign key
    op.drop_constraint(op.f('fk_exercises_content_id_content'), 'exercises', type_='foreignkey')
    op.create_foreign_key(op.f('fk_exercises_content_id_contents'), 'exercises', 'contents', ['content_id'], ['id'])
    
    # Revert voice profiles constraint
    op.drop_constraint(op.f('uq_voice_profiles_user_id'), 'voice_profiles', type_='unique')
    op.create_unique_constraint(op.f('voice_profiles_user_id_key'), 'voice_profiles', ['user_id'])
    
    # Revert vocabulary indexes
    op.drop_index(op.f('ix_vocabulary_sets_id'), table_name='vocabulary_sets')
    op.drop_index(op.f('ix_vocabulary_set_items_id'), table_name='vocabulary_set_items')
    op.drop_index('idx_vocabulary_set_items_order', table_name='vocabulary_set_items')
    op.drop_index(op.f('ix_vocabulary_exercises_id'), table_name='vocabulary_exercises')
    op.drop_index('idx_vocabulary_exercises_vocab_type', table_name='vocabulary_exercises')
    op.drop_index('idx_vocabulary_exercises_user_date', table_name='vocabulary_exercises')
    op.create_index(op.f('idx_vocabulary_exercises_user_vocab'), 'vocabulary_exercises', ['user_id', 'vocabulary_id'], unique=False)
    
    # Revert user vocabulary indexes
    op.drop_index(op.f('ix_user_vocabulary_id'), table_name='user_vocabulary')
    op.drop_index('idx_user_vocabulary_user_word', table_name='user_vocabulary')
    op.create_unique_constraint(op.f('user_vocabulary_user_id_vocabulary_id_key'), 'user_vocabulary', ['user_id', 'vocabulary_id'])
    
    # Revert progress constraints
    op.create_unique_constraint(op.f('speaking_progress_user_id_key'), 'speaking_progress', ['user_id'])
    op.create_unique_constraint(op.f('listening_progress_user_id_key'), 'listening_progress', ['user_id'])
    
    # Revert grammar table
    op.add_column('grammar', sa.Column('rule_explanation', sa.TEXT(), autoincrement=False, nullable=False))
    op.add_column('grammar', sa.Column('description', sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column('grammar', sa.Column('category', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    op.add_column('grammar', sa.Column('order_index', sa.INTEGER(), autoincrement=False, nullable=True))
    op.alter_column('grammar', 'title',
                   existing_type=sa.String(length=300),
                   type_=sa.VARCHAR(length=200),
                   existing_nullable=False)
    op.drop_column('grammar', 'explanation')
    op.drop_column('grammar', 'rule')
    
    # Drop onboarding tables
    op.drop_index(op.f('ix_user_onboarding_id'), table_name='user_onboarding')
    op.drop_table('user_onboarding')
    op.drop_index(op.f('ix_user_category_preferences_id'), table_name='user_category_preferences')
    op.drop_table('user_category_preferences')
    op.drop_index(op.f('ix_category_learning_templates_id'), table_name='category_learning_templates')
    op.drop_table('category_learning_templates')
    
    # Drop enums
    connection = op.get_bind()
    connection.execute(sa.text("DROP TYPE IF EXISTS learningcategory CASCADE"))
    connection.execute(sa.text("DROP TYPE IF EXISTS onboardingstep CASCADE"))
    connection.execute(sa.text("DROP TYPE IF EXISTS learningstyle CASCADE"))
