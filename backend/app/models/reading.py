from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class ReadingTextType(str, enum.Enum):
    ARTICLE = "article"
    STORY = "story"
    NEWS = "news"
    LETTER = "letter"
    ESSAY = "essay"
    DIALOGUE = "dialogue"
    INSTRUCTION = "instruction"

# Import DifficultyLevel from content models to reuse existing enum
from app.models.content import DifficultyLevel

class ReadingText(Base):
    """Reading texts for comprehension exercises"""
    __tablename__ = "reading_texts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    text_type = Column(Enum(ReadingTextType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    word_count = Column(Integer, nullable=False)
    estimated_reading_time = Column(Integer)  # in minutes
    
    # Metadata
    source = Column(String(200))
    author = Column(String(200))
    topic = Column(String(100))
    keywords = Column(JSON)  # List of key vocabulary words
    
    # Settings
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    reading_exercises = relationship("ReadingExercise", back_populates="reading_text")
    reading_attempts = relationship("ReadingAttempt", back_populates="reading_text")
    vocabulary_highlights = relationship("VocabularyHighlight", back_populates="reading_text")

class ReadingExercise(Base):
    """Comprehension exercises for reading texts"""
    __tablename__ = "reading_exercises"

    id = Column(Integer, primary_key=True, index=True)
    reading_text_id = Column(Integer, ForeignKey("reading_texts.id"), nullable=False)
    title = Column(String(300), nullable=False)
    question = Column(Text, nullable=False)
    exercise_type = Column(String(50), nullable=False)  # multiple_choice, true_false, short_answer, essay
    options = Column(JSON)  # For multiple choice questions
    correct_answer = Column(Text, nullable=False)
    explanation = Column(Text)
    points = Column(Integer, default=1)
    order_index = Column(Integer, default=0)
    
    # Settings
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    reading_text = relationship("ReadingText", back_populates="reading_exercises")
    reading_attempts = relationship("ReadingAttempt", back_populates="reading_exercise")

class ReadingAttempt(Base):
    """User attempts at reading exercises"""
    __tablename__ = "reading_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reading_text_id = Column(Integer, ForeignKey("reading_texts.id"), nullable=False)
    reading_exercise_id = Column(Integer, ForeignKey("reading_exercises.id"), nullable=True)
    
    # Reading metrics
    reading_time_seconds = Column(Integer)  # Time spent reading
    words_per_minute = Column(Float)  # Reading speed
    
    # Exercise response (if applicable)
    user_answer = Column(Text)
    is_correct = Column(Boolean)
    score = Column(Float, default=0.0)
    
    # Progress tracking
    comprehension_score = Column(Float)  # Overall comprehension percentage
    vocabulary_learned = Column(JSON)  # List of vocabulary words learned
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    reading_text = relationship("ReadingText", back_populates="reading_attempts")
    reading_exercise = relationship("ReadingExercise", back_populates="reading_attempts")

class VocabularyHighlight(Base):
    """Vocabulary words highlighted in reading texts"""
    __tablename__ = "vocabulary_highlights"

    id = Column(Integer, primary_key=True, index=True)
    reading_text_id = Column(Integer, ForeignKey("reading_texts.id"), nullable=False)
    word = Column(String(100), nullable=False)
    definition = Column(Text, nullable=False)
    part_of_speech = Column(String(50))
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Position in text
    start_position = Column(Integer)  # Character position where word starts
    end_position = Column(Integer)    # Character position where word ends
    
    # Additional info
    phonetic = Column(String(200))
    example_sentence = Column(Text)
    translation = Column(JSON)  # Multiple language translations
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    reading_text = relationship("ReadingText", back_populates="vocabulary_highlights")

class ReadingProgress(Base):
    """User's reading progress tracking"""
    __tablename__ = "reading_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Overall reading metrics
    total_texts_read = Column(Integer, default=0)
    total_reading_time_minutes = Column(Integer, default=0)
    average_reading_speed_wpm = Column(Float, default=0.0)
    
    # Comprehension metrics
    average_comprehension_score = Column(Float, default=0.0)
    total_exercises_completed = Column(Integer, default=0)
    total_exercises_correct = Column(Integer, default=0)
    
    # Level progress
    current_level = Column(Enum(DifficultyLevel), default=DifficultyLevel.A1)
    texts_completed_by_level = Column(JSON, default={})  # {"A1": 5, "A2": 3, ...}
    
    # Vocabulary acquisition
    total_vocabulary_learned = Column(Integer, default=0)
    vocabulary_by_level = Column(JSON, default={})
    
    # Streaks and consistency
    current_reading_streak = Column(Integer, default=0)
    longest_reading_streak = Column(Integer, default=0)
    last_reading_date = Column(DateTime(timezone=True))
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User") 