from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from app.core.database import Base


def _current_content_version() -> str:
    """Read the current content-generation version on demand.

    Imported lazily inside the helper so this module doesn't pull
    ``app.services.content_cache_service`` at import time (the services
    layer in turn imports models, so an eager import here would cycle).
    """
    from app.services.content_cache_service import CONTENT_GENERATION_VERSION
    return CONTENT_GENERATION_VERSION


class LessonType(str, PyEnum):
    CONVERSATION = "conversation"
    WRITING = "writing"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    PRONUNCIATION = "pronunciation"
    COMPREHENSION = "comprehension"
    MIXED = "mixed"

class DifficultyLevel(str, PyEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

# AI-Generated Lesson Cache
class AIGeneratedLesson(Base):
    __tablename__ = "ai_generated_lessons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Lesson identification
    lesson_type = Column(Enum(LessonType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    topic = Column(String(200), nullable=True)

    # Content
    title = Column(String(300), nullable=False)
    description = Column(Text)
    content = Column(JSON, nullable=False)  # Full lesson content structure
    estimated_duration_minutes = Column(Integer, default=15)

    # Caching
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)

    # Metadata
    generated_by = Column(String(50), default="ai")  # ai, system, manual
    # 2026-05-13: ``version`` now mirrors CONTENT_GENERATION_VERSION at
    # insert time so we can invalidate every old lesson by bumping that
    # single constant. ``crud.lessons.get_cached_lesson`` filters by
    # this value, so a code-level prompt change reaches the iPhone on
    # next request without us having to TRUNCATE the table.
    #
    # The default uses a callable + lazy import so we avoid a
    # services → models import cycle at module load.
    version = Column(String(20), default=lambda: _current_content_version())
    tags = Column(JSON, default=list)  # Search tags

    # Performance tracking
    usage_count = Column(Integer, default=0)
    average_rating = Column(Float, nullable=True)
    total_completions = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="ai_lessons")
    progress_entries = relationship("LessonProgress", back_populates="lesson", cascade="all, delete-orphan")

    @property
    def is_expired(self) -> bool:
        """Check if lesson has expired"""
        if self.expires_at is None:
            return False
        return self.expires_at < func.now()

    @property
    def days_until_expiry(self) -> int:
        """Calculate days until expiry"""
        if self.expires_at is None:
            return -1  # Never expires
        from datetime import datetime
        diff = self.expires_at - datetime.utcnow()
        return max(0, diff.days)

# User Progress Tracking
class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lesson_id = Column(Integer, ForeignKey("ai_generated_lessons.id"), nullable=False)

    # Session tracking
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Progress metrics
    time_spent_minutes = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=1)

    # Performance
    accuracy_score = Column(Float, nullable=True)  # 0-1 scale
    engagement_score = Column(Float, nullable=True)  # 0-1 scale
    performance_score = Column(Float, nullable=True)  # Overall 0-1

    # Completion
    is_completed = Column(Boolean, default=False)
    completion_rating = Column(Integer, nullable=True)  # 1-5 user rating
    feedback_text = Column(Text, nullable=True)

    # Session data
    session_data = Column(JSON, default=dict)  # Additional session metrics
    answers_data = Column(JSON, default=dict)  # User answers and corrections

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="lesson_progress")
    lesson = relationship("AIGeneratedLesson", back_populates="progress_entries")

# Lesson Generation Analytics
class LessonGenerationAnalytics(Base):
    __tablename__ = "lesson_generation_analytics"

    id = Column(Integer, primary_key=True, index=True)

    # Time period
    date = Column(DateTime, nullable=False)
    period_type = Column(String(20), nullable=False)  # daily, weekly, monthly

    # Generation metrics
    lessons_generated = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)
    total_generation_time_seconds = Column(Float, default=0.0)
    average_generation_time_seconds = Column(Float, default=0.0)

    # Content metrics
    lessons_by_type = Column(JSON, default=dict)  # {conversation: 10, writing: 5, ...}
    lessons_by_difficulty = Column(JSON, default=dict)  # {A1: 5, B1: 10, ...}
    top_topics = Column(JSON, default=dict)  # Most generated topics

    # Cache performance
    cache_hit_rate = Column(Float, default=0.0)  # 0-1 scale
    expired_lessons_cleaned = Column(Integer, default=0)

    # User engagement
    average_completion_rate = Column(Float, default=0.0)
    average_session_duration_minutes = Column(Float, default=0.0)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Lesson Templates for Quick Generation
class LessonTemplate(Base):
    __tablename__ = "lesson_templates"

    id = Column(Integer, primary_key=True, index=True)

    # Template identification
    name = Column(String(200), nullable=False)
    lesson_type = Column(Enum(LessonType), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevel), nullable=False)
    topic_category = Column(String(100), nullable=False)

    # Template content
    template_structure = Column(JSON, nullable=False)  # Lesson structure template
    content_placeholders = Column(JSON, default=dict)  # Dynamic content slots
    estimated_duration_minutes = Column(Integer, default=15)

    # Template metadata
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # User completion/satisfaction rate

    # Generation rules
    personalization_rules = Column(JSON, default=dict)  # How to adapt for user
    difficulty_scaling = Column(JSON, default=dict)  # How to scale difficulty

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())















