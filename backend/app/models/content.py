from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, JSON, ForeignKey, Float, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class ContentType(str, enum.Enum):
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    LISTENING = "listening"
    READING = "reading"
    SPEAKING = "speaking"
    WRITING = "writing"

class DifficultyLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class VocabularyStatus(str, enum.Enum):
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    MASTERED = "mastered"

class Content(Base):
    __tablename__ = "content"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    content_type = Column(Enum(ContentType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    content_data = Column(JSON)  # Flexible content storage
    
    # Metadata
    tags = Column(JSON)  # List of tags
    estimated_duration = Column(Integer)  # in minutes
    
    # Status
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    exercises = relationship("Exercise", back_populates="content")

class Grammar(Base):
    __tablename__ = "grammar"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    rule = Column(Text, nullable=False)
    explanation = Column(Text, nullable=False)
    examples = Column(JSON)  # List of example sentences
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False, index=True)
    pronunciation = Column(String(200))
    definition = Column(Text, nullable=False)
    example_sentence = Column(Text)
    translation = Column(String(200))  # Translation to native language
    
    # Enhanced CEFR-specific fields
    part_of_speech = Column(String(50))  # noun, verb, adjective, etc.
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    frequency_rank = Column(Integer)  # Word frequency ranking
    
    # Additional vocabulary fields
    synonyms = Column(JSON)  # List of synonyms
    antonyms = Column(JSON)  # List of antonyms
    word_family = Column(JSON)  # Related words (noun, verb, adjective forms)
    collocations = Column(JSON)  # Common word combinations
    usage_notes = Column(Text)  # Special usage notes
    etymology = Column(String(500))  # Word origin
    
    # CEFR-specific metadata
    cefr_source = Column(String(100), default="official")  # Source of CEFR classification
    is_core_vocabulary = Column(Boolean, default=False)  # Essential words for the level
    # Use JSONB for efficient containment queries and GIN indexing
    topic_categories = Column(JSONB)  # Topics this word relates to (family, work, etc.)
    
    # Media
    audio_url = Column(String(500))
    image_url = Column(String(500))
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user_vocabulary = relationship("UserVocabulary", back_populates="vocabulary")
    vocabulary_exercises = relationship("VocabularyExercise", back_populates="vocabulary")

# Index for efficient queries
Index('idx_vocabulary_level_word', Vocabulary.difficulty_level, Vocabulary.word)
Index('idx_vocabulary_frequency', Vocabulary.frequency_rank)

class UserVocabulary(Base):
    """Track user's progress with individual vocabulary words"""
    __tablename__ = "user_vocabulary"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vocabulary_id = Column(Integer, ForeignKey("vocabulary.id"), nullable=False)
    
    # Learning progress
    status = Column(Enum(VocabularyStatus), default=VocabularyStatus.NEW)
    mastery_level = Column(Float, default=0.0)  # 0.0 to 1.0
    
    # Spaced repetition system
    ease_factor = Column(Float, default=2.5)  # Anki-style ease factor
    interval_days = Column(Integer, default=1)  # Days until next review
    next_review_date = Column(DateTime(timezone=True))
    
    # Statistics
    times_seen = Column(Integer, default=0)
    times_correct = Column(Integer, default=0)
    times_incorrect = Column(Integer, default=0)
    streak_count = Column(Integer, default=0)  # Consecutive correct answers
    
    # Learning context
    first_encountered_date = Column(DateTime(timezone=True), server_default=func.now())
    last_reviewed_date = Column(DateTime(timezone=True))
    last_seen_in_context = Column(String(500))  # Where they last saw this word
    
    # Personal notes
    user_notes = Column(Text)  # User's personal notes about the word
    personal_examples = Column(JSON)  # User's own example sentences
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vocabulary = relationship("Vocabulary", back_populates="user_vocabulary")
    user = relationship("User", back_populates="user_vocabulary")

# Indexes for efficient queries
Index('idx_user_vocabulary_user_status', UserVocabulary.user_id, UserVocabulary.status)
Index('idx_user_vocabulary_review_date', UserVocabulary.next_review_date)
Index('idx_user_vocabulary_user_word', UserVocabulary.user_id, UserVocabulary.vocabulary_id, unique=True)

class VocabularySet(Base):
    """Curated sets of vocabulary for specific topics or levels"""
    __tablename__ = "vocabulary_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    
    # Metadata
    topic = Column(String(100))  # Theme (e.g., "Travel", "Business", "Daily Life")
    estimated_study_time = Column(Integer)  # Minutes to master this set
    word_count = Column(Integer, default=0)
    
    # Settings
    is_public = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Creator info
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    vocabulary_items = relationship("VocabularySetItem", back_populates="vocabulary_set")
    creator = relationship("User", back_populates="created_vocabulary_sets")

class VocabularySetItem(Base):
    """Individual words in a vocabulary set"""
    __tablename__ = "vocabulary_set_items"

    id = Column(Integer, primary_key=True, index=True)
    vocabulary_set_id = Column(Integer, ForeignKey("vocabulary_sets.id"), nullable=False)
    vocabulary_id = Column(Integer, ForeignKey("vocabulary.id"), nullable=False)
    
    # Order and priority
    order_index = Column(Integer, default=0)
    is_priority = Column(Boolean, default=False)  # High-priority words to learn first
    
    # Custom content for this set
    custom_definition = Column(Text)  # Set-specific definition
    custom_example = Column(Text)  # Set-specific example
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    vocabulary_set = relationship("VocabularySet", back_populates="vocabulary_items")
    vocabulary = relationship("Vocabulary")

# Index for efficient ordering
Index('idx_vocabulary_set_items_order', VocabularySetItem.vocabulary_set_id, VocabularySetItem.order_index)

class VocabularyExercise(Base):
    """Vocabulary-specific exercises and their results"""
    __tablename__ = "vocabulary_exercises"

    id = Column(Integer, primary_key=True, index=True)
    vocabulary_id = Column(Integer, ForeignKey("vocabulary.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Exercise details
    exercise_type = Column(String(50), nullable=False)  # "definition", "translation", "sentence_completion", etc.
    question = Column(Text, nullable=False)
    correct_answer = Column(String(500), nullable=False)
    user_answer = Column(String(500))
    
    # Scoring
    is_correct = Column(Boolean)
    points_earned = Column(Integer, default=0)
    time_taken_seconds = Column(Integer)
    
    # Context
    difficulty_at_time = Column(Enum(DifficultyLevel))
    exercise_context = Column(String(100))  # "daily_review", "new_word", "reinforcement"
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    vocabulary = relationship("Vocabulary", back_populates="vocabulary_exercises")
    user = relationship("User", back_populates="vocabulary_exercises")

# Indexes for analytics
Index('idx_vocabulary_exercises_user_date', VocabularyExercise.user_id, VocabularyExercise.created_at)
Index('idx_vocabulary_exercises_vocab_type', VocabularyExercise.vocabulary_id, VocabularyExercise.exercise_type) 