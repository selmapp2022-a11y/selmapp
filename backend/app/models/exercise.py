from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class ExerciseType(str, enum.Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_blank"
    MATCHING = "matching"
    LISTENING = "listening"
    SPEAKING = "speaking"
    TRANSLATION = "translation"
    PRONUNCIATION = "pronunciation"
    WRITING = "writing"

class DifficultyLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    exercise_type = Column(Enum(ExerciseType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Exercise content
    question = Column(Text, nullable=False)
    options = Column(JSON)  # For multiple choice, matching, etc.
    correct_answer = Column(JSON)  # Can be string, array, or object
    explanation = Column(Text)  # Explanation of the correct answer
    
    # Media
    audio_url = Column(String(500))
    image_url = Column(String(500))
    
    # Metadata
    points = Column(Integer, default=10)  # Points awarded for correct answer
    time_limit_seconds = Column(Integer)  # Optional time limit
    order_index = Column(Integer, default=0)
    
    # Relationships
    content_id = Column(Integer, ForeignKey("content.id"), nullable=True)
    content = relationship("Content", back_populates="exercises")
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    attempts = relationship("ExerciseAttempt", back_populates="exercise", cascade="all, delete-orphan")

class ExerciseAttempt(Base):
    __tablename__ = "exercise_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    
    # Attempt data
    user_answer = Column(JSON)  # User's answer
    is_correct = Column(Boolean, nullable=False)
    score = Column(Float, default=0.0)  # Score for this attempt (0.0 to 1.0)
    time_taken_seconds = Column(Integer)
    
    # AI feedback (if applicable)
    ai_feedback = Column(Text)
    pronunciation_score = Column(Float)  # For speaking exercises
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="exercise_attempts")
    exercise = relationship("Exercise", back_populates="attempts")

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Quiz settings
    time_limit_minutes = Column(Integer)
    passing_score = Column(Float, default=0.7)  # 70% to pass
    max_attempts = Column(Integer, default=3)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    quiz_exercises = relationship("QuizExercise", back_populates="quiz", cascade="all, delete-orphan")
    quiz_attempts = relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")

class QuizExercise(Base):
    __tablename__ = "quiz_exercises"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False)
    order_index = Column(Integer, default=0)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="quiz_exercises")
    exercise = relationship("Exercise")

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    
    # Attempt data
    score = Column(Float, nullable=False)  # Final score (0.0 to 1.0)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    time_taken_minutes = Column(Integer)
    passed = Column(Boolean, nullable=False)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User")
    quiz = relationship("Quiz", back_populates="quiz_attempts") 