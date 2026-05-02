"""add_listening_and_speaking_modules

Revision ID: 02fc56850fd3
Revises: 1ecf4c2abd15
Create Date: 2025-06-22 00:12:53.041880

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02fc56850fd3'
down_revision: Union[str, None] = '1ecf4c2abd15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create new enums only if they don't exist
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audiotype') THEN
                CREATE TYPE audiotype AS ENUM ('CONVERSATION', 'MONOLOGUE', 'INTERVIEW', 'LECTURE', 'NEWS', 'STORY', 'DIALOGUE', 'PRONUNCIATION');
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'speakingexercisetype') THEN
                CREATE TYPE speakingexercisetype AS ENUM ('WORD_PRONUNCIATION', 'SENTENCE_READING', 'CONVERSATION', 'STORYTELLING', 'DESCRIPTION', 'ROLE_PLAY', 'PRESENTATION', 'PRONUNCIATION_DRILL', 'FLUENCY_PRACTICE');
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pronunciationfocus') THEN
                CREATE TYPE pronunciationfocus AS ENUM ('PHONEMES', 'WORD_STRESS', 'SENTENCE_STRESS', 'INTONATION', 'RHYTHM', 'LINKING', 'REDUCTION');
            END IF;
        END $$;
    """)
    
    # Create tables
    op.execute("""
        CREATE TABLE audio_contents (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            audio_type audiotype NOT NULL,
            difficulty_level difficultylevel NOT NULL,
            duration_seconds INTEGER NOT NULL,
            audio_url VARCHAR(500) NOT NULL,
            slow_audio_url VARCHAR(500),
            transcript TEXT,
            topic VARCHAR(100),
            accent VARCHAR(50),
            speaker_count INTEGER,
            tts_voice VARCHAR(100),
            tts_speed FLOAT,
            tts_generated BOOLEAN DEFAULT FALSE,
            keywords JSON,
            learning_objectives JSON,
            is_active BOOLEAN DEFAULT TRUE,
            is_premium BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE pronunciation_exercises (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            pronunciation_focus pronunciationfocus NOT NULL,
            difficulty_level difficultylevel NOT NULL,
            target_words JSON NOT NULL,
            target_phonemes JSON,
            practice_sentences JSON,
            reference_audio_url VARCHAR(500),
            slow_audio_url VARCHAR(500),
            instructions TEXT,
            tips JSON,
            visual_aids JSON,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE speaking_prompts (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            exercise_type speakingexercisetype NOT NULL,
            difficulty_level difficultylevel NOT NULL,
            pronunciation_focus pronunciationfocus,
            prompt_text TEXT NOT NULL,
            sample_audio_url VARCHAR(500),
            target_phonemes JSON,
            instructions TEXT,
            tips JSON,
            common_mistakes JSON,
            assessment_criteria JSON,
            target_duration_seconds INTEGER,
            topic VARCHAR(100),
            keywords JSON,
            learning_objectives JSON,
            is_active BOOLEAN DEFAULT TRUE,
            is_premium BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE audio_playlists (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name VARCHAR(200) NOT NULL,
            description TEXT,
            difficulty_level difficultylevel,
            audio_type audiotype,
            is_public BOOLEAN DEFAULT FALSE,
            is_system_generated BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE listening_attempts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            audio_content_id INTEGER NOT NULL REFERENCES audio_contents(id),
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE,
            total_duration_seconds INTEGER,
            play_count INTEGER DEFAULT 0,
            total_listen_time INTEGER DEFAULT 0,
            replay_segments JSON,
            playback_speed FLOAT DEFAULT 1.0,
            total_exercises INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            score_percentage FLOAT,
            comprehension_score FLOAT,
            listening_efficiency FLOAT,
            is_completed BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    op.execute("""
        CREATE TABLE listening_exercises (
            id SERIAL PRIMARY KEY,
            audio_content_id INTEGER NOT NULL REFERENCES audio_contents(id),
            title VARCHAR(200) NOT NULL,
            instructions TEXT NOT NULL,
            exercise_type exercisetype NOT NULL,
            question_text TEXT,
            options JSON,
            correct_answer JSON,
            explanation TEXT,
            start_time FLOAT,
            end_time FLOAT,
            points INTEGER DEFAULT 1,
            order_index INTEGER,
            difficulty_level difficultylevel NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE listening_progress (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) UNIQUE,
            current_level difficultylevel NOT NULL,
            total_listening_time INTEGER DEFAULT 0,
            total_exercises_completed INTEGER DEFAULT 0,
            total_audio_content_completed INTEGER DEFAULT 0,
            average_comprehension_score FLOAT,
            average_listening_efficiency FLOAT,
            current_streak_days INTEGER DEFAULT 0,
            longest_streak_days INTEGER DEFAULT 0,
            level_progress JSON,
            audio_type_performance JSON,
            accent_familiarity JSON,
            daily_goal_minutes INTEGER DEFAULT 30,
            weekly_goal_exercises INTEGER DEFAULT 50,
            last_activity_date TIMESTAMP WITH TIME ZONE,
            last_level_up_date TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE pronunciation_attempts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            exercise_id INTEGER NOT NULL REFERENCES pronunciation_exercises(id),
            audio_url VARCHAR(500) NOT NULL,
            duration_seconds FLOAT NOT NULL,
            overall_score FLOAT,
            phoneme_accuracy JSON,
            word_accuracy JSON,
            mispronounced_phonemes JSON,
            correct_phonemes JSON,
            improvement_suggestions JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    op.execute("""
        CREATE TABLE speaking_attempts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            prompt_id INTEGER NOT NULL REFERENCES speaking_prompts(id),
            audio_url VARCHAR(500) NOT NULL,
            duration_seconds FLOAT NOT NULL,
            recording_quality FLOAT,
            transcribed_text TEXT,
            recognition_confidence FLOAT,
            pronunciation_score FLOAT,
            accuracy_score FLOAT,
            fluency_score FLOAT,
            completeness_score FLOAT,
            phoneme_scores JSON,
            word_scores JSON,
            stress_pattern_score FLOAT,
            intonation_score FLOAT,
            pace_score FLOAT,
            strengths JSON,
            areas_for_improvement JSON,
            specific_feedback JSON,
            ai_overall_score FLOAT,
            ai_feedback TEXT,
            ai_suggestions JSON,
            manual_score FLOAT,
            manual_feedback TEXT,
            reviewed_by INTEGER REFERENCES users(id),
            reviewed_at TIMESTAMP WITH TIME ZONE,
            attempt_number INTEGER DEFAULT 1,
            is_practice BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    op.execute("""
        CREATE TABLE speaking_progress (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) UNIQUE,
            current_level difficultylevel NOT NULL,
            total_speaking_time INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            total_prompts_completed INTEGER DEFAULT 0,
            average_pronunciation_score FLOAT,
            average_fluency_score FLOAT,
            average_accuracy_score FLOAT,
            phoneme_progress JSON,
            stress_pattern_progress FLOAT,
            intonation_progress FLOAT,
            fluency_progress FLOAT,
            exercise_type_performance JSON,
            current_streak_days INTEGER DEFAULT 0,
            longest_streak_days INTEGER DEFAULT 0,
            daily_goal_minutes INTEGER DEFAULT 15,
            weekly_goal_attempts INTEGER DEFAULT 20,
            pronunciation_trends JSON,
            weak_areas JSON,
            strong_areas JSON,
            last_activity_date TIMESTAMP WITH TIME ZONE,
            last_level_up_date TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE speaking_sessions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            session_type VARCHAR(50),
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            ended_at TIMESTAMP WITH TIME ZONE,
            duration_minutes INTEGER,
            prompts_attempted INTEGER DEFAULT 0,
            total_speaking_time INTEGER DEFAULT 0,
            average_score FLOAT,
            best_score FLOAT,
            improvement_from_last FLOAT,
            session_goals JSON,
            goals_achieved JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    op.execute("""
        CREATE TABLE voice_profiles (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) UNIQUE,
            fundamental_frequency FLOAT,
            speech_rate FLOAT,
            voice_quality_score FLOAT,
            detected_accent VARCHAR(50),
            pronunciation_patterns JSON,
            preferred_microphone_settings JSON,
            noise_threshold FLOAT,
            calibration_completed BOOLEAN DEFAULT FALSE,
            calibration_date TIMESTAMP WITH TIME ZONE,
            calibration_samples JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    
    op.execute("""
        CREATE TABLE audio_playlist_items (
            id SERIAL PRIMARY KEY,
            playlist_id INTEGER NOT NULL REFERENCES audio_playlists(id),
            audio_content_id INTEGER NOT NULL REFERENCES audio_contents(id),
            order_index INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    op.execute("""
        CREATE TABLE listening_exercise_attempts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            exercise_id INTEGER NOT NULL REFERENCES listening_exercises(id),
            listening_attempt_id INTEGER NOT NULL REFERENCES listening_attempts(id),
            user_answer JSON,
            is_correct BOOLEAN NOT NULL,
            score FLOAT,
            time_taken_seconds INTEGER,
            replays_count INTEGER DEFAULT 0,
            segment_replays JSON,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    
    # Create indexes
    op.execute("CREATE INDEX ix_audio_contents_id ON audio_contents(id);")
    op.execute("CREATE INDEX ix_pronunciation_exercises_id ON pronunciation_exercises(id);")
    op.execute("CREATE INDEX ix_speaking_prompts_id ON speaking_prompts(id);")
    op.execute("CREATE INDEX ix_audio_playlists_id ON audio_playlists(id);")
    op.execute("CREATE INDEX ix_listening_attempts_id ON listening_attempts(id);")
    op.execute("CREATE INDEX ix_listening_exercises_id ON listening_exercises(id);")
    op.execute("CREATE INDEX ix_listening_progress_id ON listening_progress(id);")
    op.execute("CREATE INDEX ix_pronunciation_attempts_id ON pronunciation_attempts(id);")
    op.execute("CREATE INDEX ix_speaking_attempts_id ON speaking_attempts(id);")
    op.execute("CREATE INDEX ix_speaking_progress_id ON speaking_progress(id);")
    op.execute("CREATE INDEX ix_speaking_sessions_id ON speaking_sessions(id);")
    op.execute("CREATE INDEX ix_voice_profiles_id ON voice_profiles(id);")
    op.execute("CREATE INDEX ix_audio_playlist_items_id ON audio_playlist_items(id);")
    op.execute("CREATE INDEX ix_listening_exercise_attempts_id ON listening_exercise_attempts(id);")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order (respecting foreign key constraints)
    op.execute("DROP TABLE IF EXISTS listening_exercise_attempts;")
    op.execute("DROP TABLE IF EXISTS audio_playlist_items;")
    op.execute("DROP TABLE IF EXISTS voice_profiles;")
    op.execute("DROP TABLE IF EXISTS speaking_sessions;")
    op.execute("DROP TABLE IF EXISTS speaking_progress;")
    op.execute("DROP TABLE IF EXISTS speaking_attempts;")
    op.execute("DROP TABLE IF EXISTS pronunciation_attempts;")
    op.execute("DROP TABLE IF EXISTS listening_progress;")
    op.execute("DROP TABLE IF EXISTS listening_exercises;")
    op.execute("DROP TABLE IF EXISTS listening_attempts;")
    op.execute("DROP TABLE IF EXISTS audio_playlists;")
    op.execute("DROP TABLE IF EXISTS speaking_prompts;")
    op.execute("DROP TABLE IF EXISTS pronunciation_exercises;")
    op.execute("DROP TABLE IF EXISTS audio_contents;")
    
    # Drop new enums (keep existing ones)
    op.execute("DROP TYPE IF EXISTS pronunciationfocus;")
    op.execute("DROP TYPE IF EXISTS speakingexercisetype;")
    op.execute("DROP TYPE IF EXISTS audiotype;")
