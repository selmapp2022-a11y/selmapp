from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from app.models.progress import DifficultyLevel

# User Progress Schemas
class UserProgressBase(BaseModel):
    current_level: DifficultyLevel
    level_progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    total_study_time_minutes: int = 0
    total_exercises_completed: int = 0
    total_points_earned: int = 0
    current_streak_days: int = 0
    longest_streak_days: int = 0
    vocabulary_mastered: int = 0
    grammar_rules_learned: int = 0
    listening_hours: float = 0.0
    speaking_sessions: int = 0
    average_accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    exercises_per_day_average: float = 0.0

class UserProgressCreate(UserProgressBase):
    user_id: int

class UserProgressUpdate(BaseModel):
    current_level: Optional[DifficultyLevel] = None
    level_progress_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    total_study_time_minutes: Optional[int] = None
    total_exercises_completed: Optional[int] = None
    total_points_earned: Optional[int] = None
    current_streak_days: Optional[int] = None
    longest_streak_days: Optional[int] = None
    vocabulary_mastered: Optional[int] = None
    grammar_rules_learned: Optional[int] = None
    listening_hours: Optional[float] = None
    speaking_sessions: Optional[int] = None
    average_accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    exercises_per_day_average: Optional[float] = None

class UserProgressResponse(UserProgressBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    last_study_date: Optional[datetime] = None
    last_level_up_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# Daily Progress Schemas
class DailyProgressBase(BaseModel):
    study_time_minutes: int = 0
    exercises_completed: int = 0
    points_earned: int = 0
    accuracy_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    daily_goal_met: bool = False

class DailyProgressCreate(DailyProgressBase):
    user_id: int
    date: datetime

class DailyProgressResponse(DailyProgressBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    date: datetime
    created_at: datetime

# Achievement Schemas
class AchievementBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: str
    icon_url: Optional[str] = None
    criteria_type: str = Field(..., max_length=50)
    criteria_value: int
    points_reward: int = 0
    is_active: bool = True

class AchievementCreate(AchievementBase):
    pass

class AchievementUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    criteria_value: Optional[int] = None
    points_reward: Optional[int] = None
    is_active: Optional[bool] = None

class AchievementResponse(AchievementBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime

# User Achievement Schemas
class UserAchievementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    achievement_id: int
    earned_at: datetime
    progress_value: Optional[int] = None
    achievement: AchievementResponse

# Study Session Schemas
class StudySessionBase(BaseModel):
    session_type: Optional[str] = Field(None, max_length=50)

class StudySessionCreate(StudySessionBase):
    user_id: int

class StudySessionUpdate(BaseModel):
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    exercises_completed: Optional[int] = None
    points_earned: Optional[int] = None
    accuracy_rate: Optional[float] = Field(None, ge=0.0, le=1.0)

class StudySessionResponse(StudySessionBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    exercises_completed: int = 0
    points_earned: int = 0
    accuracy_rate: float = 0.0

# Learning Goal Schemas
class LearningGoalBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    target_level: Optional[DifficultyLevel] = None
    target_date: Optional[datetime] = None
    target_value: int
    goal_type: str = Field(..., max_length=50)
    is_active: bool = True

class LearningGoalCreate(LearningGoalBase):
    user_id: int

class LearningGoalUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    target_level: Optional[DifficultyLevel] = None
    target_date: Optional[datetime] = None
    target_value: Optional[int] = None
    current_value: Optional[int] = None
    is_active: Optional[bool] = None

class LearningGoalResponse(LearningGoalBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    current_value: int = 0
    is_completed: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

# Progress Dashboard Schemas
class ProgressDashboardResponse(BaseModel):
    user_progress: UserProgressResponse
    recent_achievements: List[UserAchievementResponse]
    daily_progress: List[DailyProgressResponse]
    active_goals: List[LearningGoalResponse]
    study_streak: Dict[str, Any]
    level_progress: Dict[str, Any]

class WeeklyProgressResponse(BaseModel):
    week_start: date
    week_end: date
    total_study_time: int
    total_exercises: int
    total_points: int
    average_accuracy: float
    days_studied: int
    daily_breakdown: List[DailyProgressResponse]

class LevelProgressResponse(BaseModel):
    current_level: DifficultyLevel
    progress_percentage: float
    vocabulary_mastered: int
    grammar_completed: int
    exercises_completed: int
    next_level_requirements: Dict[str, Any]
    estimated_completion_date: Optional[date] = None

class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_study_date: Optional[date] = None
    streak_milestones: List[Dict[str, Any]]

class LearningAnalyticsResponse(BaseModel):
    total_study_time: int
    total_exercises: int
    accuracy_trend: List[Dict[str, Any]]
    daily_activity: List[Dict[str, Any]]
    skill_breakdown: Dict[str, float]
    level_progression: List[Dict[str, Any]]
    achievements_earned: int
    goals_completed: int 