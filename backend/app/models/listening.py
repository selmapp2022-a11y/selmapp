from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class DifficultyLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class AudioType(str, enum.Enum):
    CONVERSATION = "conversation"
    MONOLOGUE = "monologue"
    INTERVIEW = "interview"
    LECTURE = "lecture"
    NEWS = "news"
    STORY = "story"
    DIALOGUE = "dialogue"
    PRONUNCIATION = "pronunciation"

class ExerciseType(str, enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    ORDERING = "ordering"
    MATCHING = "matching"
    SHORT_ANSWER = "short_answer"
    DICTATION = "dictation"

class AudioContent(Base):
    __tablename__ = "audio_contents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Audio metadata
    audio_type = Column(Enum(AudioType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    
    # Audio files
    audio_url = Column(String(500), nullable=False)  # Main audio file
    slow_audio_url = Column(String(500))  # Slower version for beginners
    transcript = Column(Text)  # Full transcript
    
    # Content details
    topic = Column(String(100))
    accent = Column(String(50))  # American, British, Australian, etc.
    speaker_count = Column(Integer, default=1)
    
    # TTS settings (if generated)
    tts_voice = Column(String(100))  # Voice used for TTS
    tts_speed = Column(Float, default=1.0)  # Speech rate
    tts_generated = Column(Boolean, default=False)
    tts_model = Column(String(100))  # TTS model used (gemini-2.5-flash-preview-tts, gtts, etc.)
    tts_speakers = Column(JSON)  # Speaker configuration for multi-speaker audio
    tts_engine = Column(String(50))  # TTS engine (gemini, gtts, pyttsx3)
    
    # Metadata
    keywords = Column(JSON)  # Array of keywords
    learning_objectives = Column(JSON)  # Array of learning goals
    
    # Status
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    exercises = relationship("ListeningExercise", back_populates="audio_content", cascade="all, delete-orphan")
    attempts = relationship("ListeningAttempt", back_populates="audio_content", cascade="all, delete-orphan")

class ListeningExercise(Base):
    __tablename__ = "listening_exercises"

    id = Column(Integer, primary_key=True, index=True)
    audio_content_id = Column(Integer, ForeignKey("audio_contents.id"), nullable=False)
    
    # Exercise details
    title = Column(String(200), nullable=False)
    instructions = Column(Text, nullable=False)
    exercise_type = Column(Enum(ExerciseType), nullable=False)
    
    # Question data
    question_text = Column(Text)
    options = Column(JSON)  # For multiple choice, matching, etc.
    correct_answer = Column(JSON)  # Can be string, array, or object
    explanation = Column(Text)
    
    # Audio segments (for specific parts of the audio)
    start_time = Column(Float)  # Start time in seconds
    end_time = Column(Float)    # End time in seconds
    
    # Metadata
    points = Column(Integer, default=10)
    order_index = Column(Integer, default=0)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    audio_content = relationship("AudioContent", back_populates="exercises")
    attempts = relationship("ListeningExerciseAttempt", back_populates="exercise", cascade="all, delete-orphan")

class ListeningAttempt(Base):
    __tablename__ = "listening_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    audio_content_id = Column(Integer, ForeignKey("audio_contents.id"), nullable=False)
    
    # Session data
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    total_duration_seconds = Column(Integer)
    
    # Audio interaction
    play_count = Column(Integer, default=0)
    total_listen_time = Column(Integer, default=0)  # Total time spent listening
    replay_segments = Column(JSON)  # Array of replayed segments
    playback_speed = Column(Float, default=1.0)
    
    # Performance
    total_exercises = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    score_percentage = Column(Float, default=0.0)
    
    # Comprehension metrics
    comprehension_score = Column(Float)  # Overall comprehension score
    listening_efficiency = Column(Float)  # Score vs time spent ratio
    
    # Status
    is_completed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    audio_content = relationship("AudioContent", back_populates="attempts")
    exercise_attempts = relationship("ListeningExerciseAttempt", back_populates="listening_attempt", cascade="all, delete-orphan")

class ListeningExerciseAttempt(Base):
    __tablename__ = "listening_exercise_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("listening_exercises.id"), nullable=False)
    listening_attempt_id = Column(Integer, ForeignKey("listening_attempts.id"), nullable=False)
    
    # Answer data
    user_answer = Column(JSON)
    is_correct = Column(Boolean, nullable=False)
    score = Column(Float, default=0.0)
    time_taken_seconds = Column(Integer)
    
    # Audio interaction for this exercise
    replays_count = Column(Integer, default=0)
    segment_replays = Column(JSON)  # Specific segments replayed
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    exercise = relationship("ListeningExercise", back_populates="attempts")
    listening_attempt = relationship("ListeningAttempt", back_populates="exercise_attempts")

class ListeningProgress(Base):
    __tablename__ = "listening_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Overall progress
    current_level = Column(Enum(DifficultyLevel), nullable=False)
    total_listening_time = Column(Integer, default=0)  # Total minutes
    total_exercises_completed = Column(Integer, default=0)
    total_audio_content_completed = Column(Integer, default=0)
    
    # Performance metrics
    average_comprehension_score = Column(Float, default=0.0)
    average_listening_efficiency = Column(Float, default=0.0)
    current_streak_days = Column(Integer, default=0)
    longest_streak_days = Column(Integer, default=0)
    
    # Level-specific progress
    level_progress = Column(JSON)  # Progress per CEFR level
    
    # Audio type preferences and performance
    audio_type_performance = Column(JSON)  # Performance by audio type
    accent_familiarity = Column(JSON)  # Familiarity with different accents
    
    # Goals and achievements
    daily_goal_minutes = Column(Integer, default=30)
    weekly_goal_exercises = Column(Integer, default=20)
    
    # Last activity
    last_activity_date = Column(DateTime(timezone=True))
    last_level_up_date = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")

class AudioPlaylist(Base):
    __tablename__ = "audio_playlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Playlist details
    name = Column(String(200), nullable=False)
    description = Column(Text)
    difficulty_level = Column(Enum(DifficultyLevel))
    audio_type = Column(Enum(AudioType))
    
    # Metadata
    is_public = Column(Boolean, default=False)
    is_system_generated = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    playlist_items = relationship("AudioPlaylistItem", back_populates="playlist", cascade="all, delete-orphan")

class AudioPlaylistItem(Base):
    __tablename__ = "audio_playlist_items"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("audio_playlists.id"), nullable=False)
    audio_content_id = Column(Integer, ForeignKey("audio_contents.id"), nullable=False)
    
    # Order in playlist
    order_index = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    playlist = relationship("AudioPlaylist", back_populates="playlist_items")
    audio_content = relationship("AudioContent") 