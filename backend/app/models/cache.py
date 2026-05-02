from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class GeneratedContentCache(Base):
    __tablename__ = "generated_content_cache"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Deterministic cache key
    cache_key = Column(String(512), nullable=False, unique=True, index=True)

    # Scope fields for convenience querying
    content_type = Column(String(50), nullable=False)
    topic = Column(String(200), nullable=True)
    level = Column(String(8), nullable=True)
    day_number = Column(Integer, nullable=True)

    # Request/response payloads
    params = Column(JSONB, nullable=True)
    content = Column(JSONB, nullable=True)
    content_refs = Column(JSONB, nullable=True)  # e.g., {"reading_text_id": 1, "audio_content_id": 2}

    # Generation metadata
    model_used = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="ready")  # pending|ready|failed
    error = Column(Text, nullable=True)

    # Lifecycle
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")


Index("idx_generated_content_cache_user_type_day", GeneratedContentCache.user_id, GeneratedContentCache.content_type, GeneratedContentCache.day_number)


class DailyLearningPlan(Base):
    __tablename__ = "daily_learning_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Plan date (UTC date string in ISO or date-only semantics controlled by app)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD

    # Plan payload
    plan = Column(JSONB, nullable=False)

    # Status
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")


Index("uq_daily_learning_plan_user_date", DailyLearningPlan.user_id, DailyLearningPlan.date, unique=True)


class WeeklyLearningPlan(Base):
    """
    Stores weekly learning plans (7 days each).
    Content is generated in background after assessment.
    Next week is triggered when user completes day 5.
    """
    __tablename__ = "weekly_learning_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Week identifier (1, 2, 3, ...)
    week_number = Column(Integer, nullable=False)
    
    # Generation status: pending, generating, ready, failed
    status = Column(String(20), nullable=False, default="pending")
    
    # 7-day plan structure (days 1-7 with topics, skills, etc.)
    plan_data = Column(JSONB, nullable=True)
    
    # Track which days have content generated
    days_content_ready = Column(JSONB, default=list)  # e.g., [1, 2, 3] means days 1-3 ready
    
    # Generation tracking
    generation_attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    last_error = Column(Text, nullable=True)
    
    # User progress within this week
    current_day = Column(Integer, default=1)
    days_completed = Column(Integer, default=0)
    
    # Based on user's progress data from previous week
    user_progress_snapshot = Column(JSONB, nullable=True)
    
    # Timestamps
    generation_started_at = Column(DateTime(timezone=True), nullable=True)
    generation_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")


Index("uq_weekly_plan_user_week", WeeklyLearningPlan.user_id, WeeklyLearningPlan.week_number, unique=True)
Index("idx_weekly_plan_status", WeeklyLearningPlan.user_id, WeeklyLearningPlan.status)





















