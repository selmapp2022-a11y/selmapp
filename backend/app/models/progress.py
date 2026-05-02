from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum, JSON, ForeignKey, Float, Index
from sqlalchemy.dialects.postgresql import JSONB
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

class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Level progress
    current_level = Column(Enum(DifficultyLevel), nullable=False)
    level_progress_percentage = Column(Float, default=0.0)  # 0.0 to 100.0
    
    # Overall statistics
    total_study_time_minutes = Column(Integer, default=0)
    total_exercises_completed = Column(Integer, default=0)
    total_points_earned = Column(Integer, default=0)
    current_streak_days = Column(Integer, default=0)
    longest_streak_days = Column(Integer, default=0)
    
    # Skill-specific progress
    vocabulary_mastered = Column(Integer, default=0)
    grammar_rules_learned = Column(Integer, default=0)
    listening_hours = Column(Float, default=0.0)
    speaking_sessions = Column(Integer, default=0)
    
    # Performance metrics
    average_accuracy = Column(Float, default=0.0)  # 0.0 to 1.0
    exercises_per_day_average = Column(Float, default=0.0)
    
    # Last activity
    last_study_date = Column(DateTime(timezone=True))
    last_level_up_date = Column(DateTime(timezone=True))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="progress")

class DailyProgress(Base):
    __tablename__ = "daily_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    
    # Daily statistics
    study_time_minutes = Column(Integer, default=0)
    exercises_completed = Column(Integer, default=0)
    points_earned = Column(Integer, default=0)
    accuracy_rate = Column(Float, default=0.0)
    
    # Goal achievement
    daily_goal_met = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")

class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    icon_url = Column(String(500))
    
    # Achievement criteria
    criteria_type = Column(String(50), nullable=False)  # streak, exercises, points, etc.
    criteria_value = Column(Integer, nullable=False)
    
    # Metadata
    points_reward = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user_achievements = relationship("UserAchievement", back_populates="achievement")

class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    
    # Achievement data
    earned_at = Column(DateTime(timezone=True), server_default=func.now())
    progress_value = Column(Integer)  # The value that triggered the achievement
    
    # Relationships
    user = relationship("User", back_populates="achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")

class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Session data
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)
    
    # Session statistics
    exercises_completed = Column(Integer, default=0)
    points_earned = Column(Integer, default=0)
    accuracy_rate = Column(Float, default=0.0)
    
    # Session type
    session_type = Column(String(50))  # practice, quiz, review, etc.
    
    # Relationships
    user = relationship("User")

class LearningGoal(Base):
    __tablename__ = "learning_goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Goal details
    title = Column(String(200), nullable=False)
    description = Column(Text)
    target_level = Column(Enum(DifficultyLevel))
    target_date = Column(DateTime(timezone=True))
    
    # Goal metrics
    target_value = Column(Integer, nullable=False)
    current_value = Column(Integer, default=0)
    goal_type = Column(String(50), nullable=False)  # vocabulary, exercises, study_time, etc.
    
    # Status
    is_completed = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User")


class UserWeeklyProgress(Base):
    """
    Track user's progress through weekly learning plans.
    Used to determine when to trigger next week generation.
    """
    __tablename__ = "user_weekly_progress"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Current week tracking
    current_week_number = Column(Integer, default=1)
    current_day_in_week = Column(Integer, default=1)  # 1-7
    
    # Total progress
    total_weeks_completed = Column(Integer, default=0)
    total_days_completed = Column(Integer, default=0)
    
    # Performance tracking per skill (updated after each day)
    skill_scores = Column(JSONB, default=dict)  # {"vocabulary": 0.8, "grammar": 0.7, ...}
    weak_areas = Column(JSONB, default=list)  # ["grammar", "listening"]
    strong_areas = Column(JSONB, default=list)  # ["vocabulary", "reading"]
    
    # For next week generation - stores analysis from completed days
    progress_analysis = Column(JSONB, nullable=True)
    
    # Timestamps
    last_day_completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")


Index("uq_user_weekly_progress_user", UserWeeklyProgress.user_id, unique=True)


class DayCompletionRecord(Base):
    """
    Record each day's completion with performance data.
    Used to analyze progress and generate next week's plan.
    """
    __tablename__ = "day_completion_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Day identification
    week_number = Column(Integer, nullable=False)
    day_number = Column(Integer, nullable=False)  # 1-7
    
    # Performance metrics
    exercises_completed = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    accuracy = Column(Float, default=0.0)
    time_spent_minutes = Column(Integer, default=0)
    
    # Skill-specific results
    skill_results = Column(JSONB, default=dict)  # {"vocabulary": {"correct": 8, "total": 10}, ...}
    
    # Content completed
    content_types_completed = Column(JSONB, default=list)  # ["reading", "vocabulary", "listening"]
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User")


Index("uq_day_completion_user_week_day", DayCompletionRecord.user_id, DayCompletionRecord.week_number, DayCompletionRecord.day_number, unique=True)
Index("idx_day_completion_user_week", DayCompletionRecord.user_id, DayCompletionRecord.week_number)