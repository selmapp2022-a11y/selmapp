from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

class LessonType(str, Enum):
    CONVERSATION = "conversation"
    WRITING = "writing"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    PRONUNCIATION = "pronunciation"
    COMPREHENSION = "comprehension"
    MIXED = "mixed"

class DifficultyLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

# Base schemas
class AILessonBase(BaseModel):
    lesson_type: LessonType
    difficulty_level: DifficultyLevel
    topic: Optional[str] = None
    title: str
    description: Optional[str] = None
    content: Dict[str, Any]  # Full lesson content structure
    estimated_duration_minutes: int = 15
    expires_at: Optional[datetime] = None
    tags: List[str] = []

class AILessonCreate(AILessonBase):
    user_id: int

class AILessonUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    estimated_duration_minutes: Optional[int] = None
    expires_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None

class AILesson(AILessonBase):
    id: int
    user_id: int
    is_active: bool = True
    generated_by: str = "ai"
    version: str = "1.0"
    usage_count: int = 0
    average_rating: Optional[float] = None
    total_completions: int = 0
    last_accessed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at < datetime.utcnow()

    @property
    def days_until_expiry(self) -> int:
        if self.expires_at is None:
            return -1
        diff = self.expires_at - datetime.utcnow()
        return max(0, diff.days)

    class Config:
        from_attributes = True

# Progress schemas
class LessonProgressBase(BaseModel):
    time_spent_minutes: int = 0
    progress_percentage: float = 0.0
    current_step: int = 0
    total_steps: int = 1
    accuracy_score: Optional[float] = None
    engagement_score: Optional[float] = None
    performance_score: Optional[float] = None
    is_completed: bool = False
    completion_rating: Optional[int] = None
    feedback_text: Optional[str] = None
    session_data: Dict[str, Any] = {}
    answers_data: Dict[str, Any] = {}

class LessonProgressCreate(LessonProgressBase):
    user_id: int
    lesson_id: int

class LessonProgressUpdate(BaseModel):
    time_spent_minutes: Optional[int] = None
    progress_percentage: Optional[float] = None
    current_step: Optional[int] = None
    total_steps: Optional[int] = None
    accuracy_score: Optional[float] = None
    engagement_score: Optional[float] = None
    performance_score: Optional[float] = None
    is_completed: Optional[bool] = None
    completion_rating: Optional[int] = None
    feedback_text: Optional[str] = None
    session_data: Optional[Dict[str, Any]] = None
    answers_data: Optional[Dict[str, Any]] = None

class LessonProgress(LessonProgressBase):
    id: int
    user_id: int
    lesson_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    last_activity_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Request/Response schemas
class GenerateLessonRequest(BaseModel):
    lesson_type: LessonType
    difficulty_level: DifficultyLevel
    topic: Optional[str] = None
    user_preferences: Optional[Dict[str, Any]] = None

class LessonResponse(BaseModel):
    lesson: AILesson
    progress: Optional[LessonProgress] = None
    is_cached: bool = False
    generated_at: datetime
    cache_age_hours: Optional[float] = None
    progress_based_adjustments: Optional[Dict[str, Any]] = None

class CachedLessonResponse(BaseModel):
    lesson: AILesson
    progress: Optional[LessonProgress] = None
    is_expired: bool
    days_until_expiry: int

class LessonRecommendation(BaseModel):
    lesson: AILesson
    relevance_score: float  # 0-1
    reasoning: str
    estimated_benefit: str

class LessonAnalytics(BaseModel):
    total_lessons_generated: int = 0
    total_cache_hits: int = 0
    cache_hit_rate: float = 0.0
    average_generation_time_seconds: float = 0.0
    lessons_by_type: Dict[str, int] = {}
    lessons_by_difficulty: Dict[str, int] = {}
    top_topics: List[str] = []
    average_completion_rate: float = 0.0
    expired_lessons_cleaned: int = 0

# Template schemas
class LessonTemplateBase(BaseModel):
    name: str
    lesson_type: LessonType
    difficulty_level: DifficultyLevel
    topic_category: str
    template_structure: Dict[str, Any]
    content_placeholders: Dict[str, Any] = {}
    estimated_duration_minutes: int = 15
    personalization_rules: Dict[str, Any] = {}
    difficulty_scaling: Dict[str, Any] = {}

class LessonTemplateCreate(LessonTemplateBase):
    pass

class LessonTemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_structure: Optional[Dict[str, Any]] = None
    content_placeholders: Optional[Dict[str, Any]] = None
    estimated_duration_minutes: Optional[int] = None
    personalization_rules: Optional[Dict[str, Any]] = None
    difficulty_scaling: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class LessonTemplate(LessonTemplateBase):
    id: int
    is_active: bool = True
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
