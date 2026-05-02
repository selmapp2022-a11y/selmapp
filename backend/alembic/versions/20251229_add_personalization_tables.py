"""add_personalization_tables

Revision ID: 20251229_add_personalization
Revises: 7f1e3b2c1abc
Create Date: 2025-12-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251229_add_personalization'
down_revision: Union[str, None] = '7f1e3b2c1abc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing personalization tables."""
    connection = op.get_bind()
    
    # Create enums if they don't exist
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE learningstyle AS ENUM (
                'visual', 'auditory', 'kinesthetic', 'reading_writing', 'mixed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE personalitytype AS ENUM (
                'competitive', 'collaborative', 'independent', 'guided'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE learninggoaltype AS ENUM (
                'fluency', 'vocabulary', 'grammar', 'pronunciation', 
                'listening', 'speaking', 'reading', 'writing',
                'exam_prep', 'business', 'travel', 'academic'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE recommendationtype AS ENUM (
                'content', 'exercise', 'skill_focus', 'learning_path', 'practice_time'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE trainerinteractiontype AS ENUM (
                'greeting', 'motivation', 'feedback', 'suggestion', 
                'correction', 'encouragement', 'challenge', 'assessment'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # If enums already existed (from a previous migration/attempt), they may be missing
    # some values. Adding enum values should be executed outside a transaction block in
    # many Postgres versions, so use Alembic's autocommit block.
    with op.get_context().autocommit_block():
        def _ensure_enum_values(enum_name: str, values: list[str]) -> None:
            for v in values:
                # Use a DO block to be compatible with Postgres versions that don't support
                # "ADD VALUE IF NOT EXISTS", while still being idempotent.
                connection.execute(sa.text(f"""
                    DO $$ BEGIN
                        ALTER TYPE {enum_name} ADD VALUE '{v}';
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
                """))

        _ensure_enum_values(
            "learningstyle",
            ["visual", "auditory", "kinesthetic", "reading_writing", "mixed"],
        )
        _ensure_enum_values(
            "personalitytype",
            ["competitive", "collaborative", "independent", "guided"],
        )
        _ensure_enum_values(
            "learninggoaltype",
            [
                "fluency",
                "vocabulary",
                "grammar",
                "pronunciation",
                "listening",
                "speaking",
                "reading",
                "writing",
                "exam_prep",
                "business",
                "travel",
                "academic",
            ],
        )
        _ensure_enum_values(
            "recommendationtype",
            ["content", "exercise", "skill_focus", "learning_path", "practice_time"],
        )
        _ensure_enum_values(
            "trainerinteractiontype",
            [
                "greeting",
                "motivation",
                "feedback",
                "suggestion",
                "correction",
                "encouragement",
                "challenge",
                "assessment",
            ],
        )
    
    # Create user_learning_profiles table if it doesn't exist
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS user_learning_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            
            -- Learning Preferences
            learning_style learningstyle DEFAULT 'mixed',
            personality_type personalitytype DEFAULT 'independent',
            preferred_session_duration INTEGER DEFAULT 30,
            preferred_difficulty_progression FLOAT DEFAULT 0.1,
            
            -- Learning Goals
            primary_goal learninggoaltype NOT NULL DEFAULT 'fluency',
            secondary_goals JSON DEFAULT '[]',
            target_cefr_level VARCHAR(2) NOT NULL DEFAULT 'B1',
            target_completion_date TIMESTAMP,
            
            -- Skill Weights
            listening_weight FLOAT DEFAULT 0.25,
            speaking_weight FLOAT DEFAULT 0.25,
            reading_weight FLOAT DEFAULT 0.25,
            writing_weight FLOAT DEFAULT 0.25,
            
            -- Learning Patterns
            optimal_study_times JSON DEFAULT '[]',
            preferred_content_types JSON DEFAULT '[]',
            motivation_triggers JSON DEFAULT '[]',
            
            -- Adaptive Parameters
            learning_rate FLOAT DEFAULT 1.0,
            retention_rate FLOAT DEFAULT 0.8,
            challenge_preference FLOAT DEFAULT 0.5,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_learning_profiles_id ON user_learning_profiles(id);"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_user_learning_profiles_user_id ON user_learning_profiles(user_id);"))
    
    # Create personalized_learning_paths table if it doesn't exist
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS personalized_learning_paths (
            id SERIAL PRIMARY KEY,
            user_profile_id INTEGER NOT NULL REFERENCES user_learning_profiles(id) ON DELETE CASCADE,
            
            -- Path Details
            name VARCHAR(200) NOT NULL,
            description TEXT,
            estimated_duration_weeks INTEGER NOT NULL,
            current_step INTEGER DEFAULT 0,
            total_steps INTEGER NOT NULL,
            
            -- Path Configuration
            path_data JSON NOT NULL,
            adaptive_adjustments JSON DEFAULT '{}',
            
            -- Progress Tracking
            completion_percentage FLOAT DEFAULT 0.0,
            is_active BOOLEAN DEFAULT TRUE,
            is_completed BOOLEAN DEFAULT FALSE,
            
            -- Performance Metrics
            average_performance FLOAT DEFAULT 0.0,
            predicted_completion_date TIMESTAMP,
            last_activity_date TIMESTAMP,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_personalized_learning_paths_id ON personalized_learning_paths(id);"))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_personalized_learning_paths_user_profile_id ON personalized_learning_paths(user_profile_id);"))
    
    # Create learning_path_milestones table if it doesn't exist
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS learning_path_milestones (
            id SERIAL PRIMARY KEY,
            learning_path_id INTEGER NOT NULL REFERENCES personalized_learning_paths(id) ON DELETE CASCADE,
            
            -- Milestone Details
            step_number INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            skill_focus VARCHAR(50) NOT NULL,
            
            -- Requirements
            required_activities JSON NOT NULL,
            mastery_threshold FLOAT DEFAULT 0.8,
            
            -- Progress
            is_completed BOOLEAN DEFAULT FALSE,
            completion_date TIMESTAMP,
            performance_score FLOAT,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_learning_path_milestones_id ON learning_path_milestones(id);"))
    
    # Create content_recommendations table if it doesn't exist
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS content_recommendations (
            id SERIAL PRIMARY KEY,
            user_profile_id INTEGER NOT NULL REFERENCES user_learning_profiles(id) ON DELETE CASCADE,
            
            -- Recommendation Details
            recommendation_type recommendationtype NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            
            -- Content References
            content_type VARCHAR(50) NOT NULL,
            content_id INTEGER,
            content_metadata JSON DEFAULT '{}',
            
            -- Recommendation Scoring
            relevance_score FLOAT NOT NULL,
            confidence_score FLOAT NOT NULL,
            priority_score FLOAT NOT NULL,
            
            -- Recommendation Context
            reasoning TEXT,
            expected_benefit TEXT,
            estimated_time_minutes INTEGER,
            
            -- Status
            is_active BOOLEAN DEFAULT TRUE,
            is_accepted BOOLEAN,
            is_completed BOOLEAN DEFAULT FALSE,
            
            -- Feedback
            user_rating INTEGER,
            user_feedback TEXT,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT now(),
            expires_at TIMESTAMP
        );
    """))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_content_recommendations_id ON content_recommendations(id);"))
    
    # Create personal_trainer_interactions table if it doesn't exist
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS personal_trainer_interactions (
            id SERIAL PRIMARY KEY,
            user_profile_id INTEGER NOT NULL REFERENCES user_learning_profiles(id) ON DELETE CASCADE,
            
            -- Interaction Details
            interaction_type trainerinteractiontype NOT NULL,
            trigger_event VARCHAR(100),
            
            -- Content
            trainer_message TEXT NOT NULL,
            user_response TEXT,
            context_data JSON DEFAULT '{}',
            
            -- Personalization
            tone VARCHAR(50) DEFAULT 'encouraging',
            formality_level VARCHAR(20) DEFAULT 'casual',
            
            -- Interaction Metadata
            session_id VARCHAR(100),
            is_proactive BOOLEAN DEFAULT FALSE,
            
            -- Response Tracking
            user_engagement_score FLOAT,
            interaction_effectiveness FLOAT,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT now(),
            responded_at TIMESTAMP
        );
    """))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_personal_trainer_interactions_id ON personal_trainer_interactions(id);"))
    
    # Create learning_analytics table if it doesn't exist
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS learning_analytics (
            id SERIAL PRIMARY KEY,
            user_profile_id INTEGER NOT NULL REFERENCES user_learning_profiles(id) ON DELETE CASCADE,
            
            -- Time Period
            date TIMESTAMP NOT NULL,
            period_type VARCHAR(20) NOT NULL,
            
            -- Learning Metrics
            study_time_minutes INTEGER DEFAULT 0,
            activities_completed INTEGER DEFAULT 0,
            exercises_completed INTEGER DEFAULT 0,
            
            -- Performance Metrics
            average_accuracy FLOAT DEFAULT 0.0,
            improvement_rate FLOAT DEFAULT 0.0,
            consistency_score FLOAT DEFAULT 0.0,
            
            -- Skill-specific Metrics
            listening_score FLOAT DEFAULT 0.0,
            speaking_score FLOAT DEFAULT 0.0,
            reading_score FLOAT DEFAULT 0.0,
            writing_score FLOAT DEFAULT 0.0,
            
            -- Engagement Metrics
            session_count INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            motivation_level FLOAT DEFAULT 0.5,
            
            -- Additional Data
            analytics_data JSON DEFAULT '{}',
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_learning_analytics_id ON learning_analytics(id);"))
    
    # Create adaptive_learning_rules table if it doesn't exist
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS adaptive_learning_rules (
            id SERIAL PRIMARY KEY,
            
            -- Rule Definition
            name VARCHAR(100) NOT NULL,
            description TEXT,
            rule_type VARCHAR(50) NOT NULL,
            
            -- Rule Logic
            conditions JSON NOT NULL,
            actions JSON NOT NULL,
            
            -- Rule Configuration
            priority INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            
            -- Performance Tracking
            trigger_count INTEGER DEFAULT 0,
            success_rate FLOAT DEFAULT 0.0,
            
            -- Timestamps
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """))
    connection.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_adaptive_learning_rules_id ON adaptive_learning_rules(id);"))
    
    # Add learning_profile relationship to users table if not exists
    # This is handled via SQLAlchemy relationships, no column changes needed


def downgrade() -> None:
    """Remove personalization tables."""
    connection = op.get_bind()
    
    # Drop tables in reverse order of dependencies
    connection.execute(sa.text("DROP TABLE IF EXISTS adaptive_learning_rules CASCADE;"))
    connection.execute(sa.text("DROP TABLE IF EXISTS learning_analytics CASCADE;"))
    connection.execute(sa.text("DROP TABLE IF EXISTS personal_trainer_interactions CASCADE;"))
    connection.execute(sa.text("DROP TABLE IF EXISTS content_recommendations CASCADE;"))
    connection.execute(sa.text("DROP TABLE IF EXISTS learning_path_milestones CASCADE;"))
    connection.execute(sa.text("DROP TABLE IF EXISTS personalized_learning_paths CASCADE;"))
    connection.execute(sa.text("DROP TABLE IF EXISTS user_learning_profiles CASCADE;"))
    
    # Drop enums
    connection.execute(sa.text("DROP TYPE IF EXISTS trainerinteractiontype CASCADE;"))
    connection.execute(sa.text("DROP TYPE IF EXISTS recommendationtype CASCADE;"))
    connection.execute(sa.text("DROP TYPE IF EXISTS learninggoaltype CASCADE;"))
    connection.execute(sa.text("DROP TYPE IF EXISTS personalitytype CASCADE;"))
    connection.execute(sa.text("DROP TYPE IF EXISTS learningstyle CASCADE;"))

