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

class SpeakingExerciseType(str, enum.Enum):
    WORD_PRONUNCIATION = "word_pronunciation"
    SENTENCE_READING = "sentence_reading"
    CONVERSATION = "conversation"
    STORYTELLING = "storytelling"
    DESCRIPTION = "description"
    ROLE_PLAY = "role_play"
    PRESENTATION = "presentation"
    PRONUNCIATION_DRILL = "pronunciation_drill"
    FLUENCY_PRACTICE = "fluency_practice"

class PronunciationFocus(str, enum.Enum):
    PHONEMES = "phonemes"
    WORD_STRESS = "word_stress"
    SENTENCE_STRESS = "sentence_stress"
    INTONATION = "intonation"
    RHYTHM = "rhythm"
    LINKING = "linking"
    REDUCTION = "reduction"

class AudioFormat(str, enum.Enum):
    WAV = "wav"
    MP3 = "mp3"
    WEBM = "webm"
    OGG = "ogg"
    M4A = "m4a"
    FLAC = "flac"

class AudioQuality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class SpeakingPrompt(Base):
    __tablename__ = "speaking_prompts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Prompt details
    exercise_type = Column(Enum(SpeakingExerciseType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    pronunciation_focus = Column(Enum(PronunciationFocus))
    
    # Content
    prompt_text = Column(Text, nullable=False)
    sample_audio_url = Column(String(500))  # Reference pronunciation
    target_phonemes = Column(JSON)  # Specific sounds to practice
    
    # Instructions and guidance
    instructions = Column(Text)
    tips = Column(JSON)  # Array of helpful tips
    common_mistakes = Column(JSON)  # Common pronunciation errors
    
    # Assessment criteria
    assessment_criteria = Column(JSON)  # What to evaluate
    target_duration_seconds = Column(Integer)  # Expected speaking time
    
    # Metadata
    topic = Column(String(100))
    keywords = Column(JSON)
    learning_objectives = Column(JSON)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    attempts = relationship("SpeakingAttempt", back_populates="prompt", cascade="all, delete-orphan")

class SpeakingAttempt(Base):
    __tablename__ = "speaking_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    prompt_id = Column(Integer, ForeignKey("speaking_prompts.id"), nullable=False)
    
    # Recording data
    audio_url = Column(String(500), nullable=False)  # User's recording
    duration_seconds = Column(Float, nullable=False)
    recording_quality = Column(Float)  # Audio quality score
    
    # Speech recognition results
    transcribed_text = Column(Text)  # What the user actually said
    recognition_confidence = Column(Float)  # STT confidence score
    
    # Pronunciation assessment
    pronunciation_score = Column(Float)  # Overall pronunciation score (0-100)
    accuracy_score = Column(Float)  # Pronunciation accuracy
    fluency_score = Column(Float)  # Speaking fluency
    completeness_score = Column(Float)  # How much of the prompt was covered
    
    # Detailed analysis
    phoneme_scores = Column(JSON)  # Score for each phoneme
    word_scores = Column(JSON)  # Score for each word
    stress_pattern_score = Column(Float)  # Word/sentence stress accuracy
    intonation_score = Column(Float)  # Intonation pattern accuracy
    pace_score = Column(Float)  # Speaking pace appropriateness
    
    # Feedback data
    strengths = Column(JSON)  # Array of positive aspects
    areas_for_improvement = Column(JSON)  # Areas needing work
    specific_feedback = Column(JSON)  # Detailed feedback per word/phoneme
    
    # AI assessment (if available)
    ai_overall_score = Column(Float)
    ai_feedback = Column(Text)
    ai_suggestions = Column(JSON)
    
    # Manual assessment (teacher/expert review)
    manual_score = Column(Float)
    manual_feedback = Column(Text)
    reviewed_by = Column(Integer, ForeignKey("users.id"))  # Teacher/reviewer ID
    reviewed_at = Column(DateTime(timezone=True))
    
    # Metadata
    attempt_number = Column(Integer, default=1)  # Which attempt for this prompt
    is_practice = Column(Boolean, default=True)  # Practice vs assessment
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    prompt = relationship("SpeakingPrompt", back_populates="attempts")
    reviewer = relationship("User", foreign_keys=[reviewed_by])

class PronunciationExercise(Base):
    __tablename__ = "pronunciation_exercises"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Exercise focus
    pronunciation_focus = Column(Enum(PronunciationFocus), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Content
    target_words = Column(JSON, nullable=False)  # Words to practice
    target_phonemes = Column(JSON)  # Specific sounds
    practice_sentences = Column(JSON)  # Sentences containing target words
    
    # Reference audio
    reference_audio_url = Column(String(500))  # Model pronunciation
    slow_audio_url = Column(String(500))  # Slower version
    
    # Instructions
    instructions = Column(Text)
    tips = Column(JSON)
    visual_aids = Column(JSON)  # Mouth position diagrams, etc.
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    attempts = relationship("PronunciationAttempt", back_populates="exercise", cascade="all, delete-orphan")

class PronunciationAttempt(Base):
    __tablename__ = "pronunciation_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("pronunciation_exercises.id"), nullable=False)
    
    # Recording data
    audio_url = Column(String(500), nullable=False)
    duration_seconds = Column(Float, nullable=False)
    
    # Assessment results
    overall_score = Column(Float)  # 0-100
    phoneme_accuracy = Column(JSON)  # Accuracy per phoneme
    word_accuracy = Column(JSON)  # Accuracy per word
    
    # Detailed analysis
    mispronounced_phonemes = Column(JSON)
    correct_phonemes = Column(JSON)
    improvement_suggestions = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    exercise = relationship("PronunciationExercise", back_populates="attempts")

class SpeakingProgress(Base):
    __tablename__ = "speaking_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Overall progress
    current_level = Column(Enum(DifficultyLevel), nullable=False)
    total_speaking_time = Column(Integer, default=0)  # Total minutes
    total_attempts = Column(Integer, default=0)
    total_prompts_completed = Column(Integer, default=0)
    
    # Performance metrics
    average_pronunciation_score = Column(Float, default=0.0)
    average_fluency_score = Column(Float, default=0.0)
    average_accuracy_score = Column(Float, default=0.0)
    
    # Pronunciation focus areas
    phoneme_progress = Column(JSON)  # Progress per phoneme
    stress_pattern_progress = Column(Float, default=0.0)
    intonation_progress = Column(Float, default=0.0)
    fluency_progress = Column(Float, default=0.0)
    
    # Exercise type performance
    exercise_type_performance = Column(JSON)  # Performance by exercise type
    
    # Streaks and consistency
    current_streak_days = Column(Integer, default=0)
    longest_streak_days = Column(Integer, default=0)
    
    # Goals
    daily_goal_minutes = Column(Integer, default=15)
    weekly_goal_attempts = Column(Integer, default=10)
    
    # Improvement tracking
    pronunciation_trends = Column(JSON)  # Historical improvement data
    weak_areas = Column(JSON)  # Areas needing more practice
    strong_areas = Column(JSON)  # Areas of strength
    
    # Last activity
    last_activity_date = Column(DateTime(timezone=True))
    last_level_up_date = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")

class SpeakingSession(Base):
    __tablename__ = "speaking_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Session details
    session_type = Column(String(50))  # practice, assessment, conversation
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)
    
    # Session content
    prompts_attempted = Column(Integer, default=0)
    total_speaking_time = Column(Integer, default=0)  # Seconds
    
    # Performance summary
    average_score = Column(Float)
    best_score = Column(Float)
    improvement_from_last = Column(Float)
    
    # Session goals
    session_goals = Column(JSON)  # What user wanted to practice
    goals_achieved = Column(JSON)  # Which goals were met
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")

class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Voice characteristics
    fundamental_frequency = Column(Float)  # Voice pitch
    speech_rate = Column(Float)  # Words per minute
    voice_quality_score = Column(Float)
    
    # Accent and pronunciation patterns
    detected_accent = Column(String(50))
    pronunciation_patterns = Column(JSON)  # Common pronunciation tendencies
    
    # Audio quality preferences
    preferred_microphone_settings = Column(JSON)
    noise_threshold = Column(Float)
    
    # Calibration data
    calibration_completed = Column(Boolean, default=False)
    calibration_date = Column(DateTime(timezone=True))
    calibration_samples = Column(JSON)  # Reference recordings
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User") 