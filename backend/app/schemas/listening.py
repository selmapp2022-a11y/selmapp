from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class DifficultyLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class AudioType(str, Enum):
    CONVERSATION = "conversation"
    MONOLOGUE = "monologue"
    INTERVIEW = "interview"
    LECTURE = "lecture"
    NEWS = "news"
    STORY = "story"
    DIALOGUE = "dialogue"
    PRONUNCIATION = "pronunciation"

class ExerciseType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    ORDERING = "ordering"
    MATCHING = "matching"
    SHORT_ANSWER = "short_answer"
    DICTATION = "dictation"

# Audio Content Schemas
class AudioContentBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    audio_type: AudioType
    difficulty_level: DifficultyLevel
    audio_url: str = Field(..., max_length=500)
    duration_seconds: int = Field(..., gt=0)
    transcript: Optional[str] = None
    topic: Optional[str] = Field(None, max_length=100)
    keywords: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    is_active: bool = True
    is_premium: bool = False

class AudioContentCreate(AudioContentBase):
    pass

class AudioContentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    audio_type: Optional[AudioType] = None
    difficulty_level: Optional[DifficultyLevel] = None
    audio_url: Optional[str] = Field(None, max_length=500)
    duration_seconds: Optional[int] = Field(None, gt=0)
    transcript: Optional[str] = None
    topic: Optional[str] = Field(None, max_length=100)
    keywords: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_premium: Optional[bool] = None

class AudioContentResponse(AudioContentBase):
    id: int
    play_count: int
    average_score: float
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Listening Exercise Schemas
class ListeningExerciseBase(BaseModel):
    audio_content_id: int
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    time_limit_minutes: Optional[int] = Field(None, gt=0)
    is_active: bool = True

class ListeningExerciseCreate(ListeningExerciseBase):
    pass

class ListeningExerciseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    instructions: Optional[str] = None
    time_limit_minutes: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None

class ListeningExerciseResponse(ListeningExerciseBase):
    id: int
    audio_content: AudioContentResponse
    total_questions: int
    average_score: float
    completion_rate: float
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Question Schemas
class QuestionBase(BaseModel):
    exercise_id: int
    question_text: str
    question_type: ExerciseType
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: Optional[str] = None
    audio_timestamp: Optional[float] = None
    points: int = Field(1, ge=1)
    order_index: int = Field(1, ge=1)

class QuestionCreate(QuestionBase):
    pass

class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[ExerciseType] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    audio_timestamp: Optional[float] = None
    points: Optional[int] = Field(None, ge=1)
    order_index: Optional[int] = Field(None, ge=1)

class QuestionResponse(QuestionBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Answer Schemas
class AnswerBase(BaseModel):
    question_id: int
    user_answer: str
    is_correct: bool
    points_earned: int = Field(0, ge=0)
    time_taken_seconds: Optional[int] = None

class AnswerCreate(BaseModel):
    question_id: int
    user_answer: str

class AnswerResponse(AnswerBase):
    id: int
    question: QuestionResponse
    created_at: datetime

    class Config:
        from_attributes = True

# Listening Attempt Schemas
class ListeningAttemptBase(BaseModel):
    exercise_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_score: float = Field(0.0, ge=0.0, le=100.0)
    max_possible_score: int = Field(0, ge=0)
    completion_percentage: float = Field(0.0, ge=0.0, le=100.0)
    time_taken_minutes: Optional[int] = None
    is_completed: bool = False

class ListeningAttemptCreate(BaseModel):
    exercise_id: int

class ListeningAttemptUpdate(BaseModel):
    completed_at: Optional[datetime] = None
    total_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    completion_percentage: Optional[float] = Field(None, ge=0.0, le=100.0)
    time_taken_minutes: Optional[int] = None
    is_completed: Optional[bool] = None

class ListeningAttemptResponse(ListeningAttemptBase):
    id: int
    user_id: int
    exercise: ListeningExerciseResponse
    answers: List[AnswerResponse]
    created_at: datetime

    class Config:
        from_attributes = True

# Progress Schemas
class ListeningProgressBase(BaseModel):
    current_level: DifficultyLevel
    total_listening_time: int = Field(0, ge=0)
    total_exercises_completed: int = Field(0, ge=0)
    total_attempts: int = Field(0, ge=0)
    average_score: float = Field(0.0, ge=0.0, le=100.0)
    content_type_performance: Optional[Dict[str, float]] = None
    difficulty_level_performance: Optional[Dict[str, float]] = None
    current_streak_days: int = Field(0, ge=0)
    longest_streak_days: int = Field(0, ge=0)
    daily_goal_minutes: int = Field(15, gt=0)
    weekly_goal_exercises: int = Field(5, gt=0)

class ListeningProgressCreate(BaseModel):
    current_level: DifficultyLevel

class ListeningProgressUpdate(BaseModel):
    current_level: Optional[DifficultyLevel] = None
    daily_goal_minutes: Optional[int] = Field(None, gt=0)
    weekly_goal_exercises: Optional[int] = Field(None, gt=0)

class ListeningProgressResponse(ListeningProgressBase):
    id: int
    user_id: int
    listening_trends: Optional[Dict[str, Any]] = None
    weak_areas: Optional[List[str]] = None
    strong_areas: Optional[List[str]] = None
    last_activity_date: Optional[datetime] = None
    last_level_up_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Session Schemas
class ListeningSessionBase(BaseModel):
    session_type: str = Field(..., max_length=50)
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    exercises_completed: int = Field(0, ge=0)
    total_listening_time: int = Field(0, ge=0)
    average_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    best_score: Optional[float] = Field(None, ge=0.0, le=100.0)

class ListeningSessionCreate(BaseModel):
    session_type: str = Field(..., max_length=50)

class ListeningSessionUpdate(BaseModel):
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    exercises_completed: Optional[int] = Field(None, ge=0)
    total_listening_time: Optional[int] = Field(None, ge=0)
    average_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    best_score: Optional[float] = Field(None, ge=0.0, le=100.0)

class ListeningSessionResponse(ListeningSessionBase):
    id: int
    user_id: int
    improvement_from_last: Optional[float] = None
    session_goals: Optional[List[str]] = None
    goals_achieved: Optional[List[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Analytics and Dashboard Schemas
class ListeningAnalytics(BaseModel):
    total_listening_time: int
    exercises_completed: int
    average_score: float
    improvement_rate: float
    streak_days: int
    favorite_content_types: List[str]
    performance_by_level: Dict[str, float]
    recent_activity: List[Dict[str, Any]]

class ListeningDashboard(BaseModel):
    user_progress: ListeningProgressResponse
    recent_attempts: List[ListeningAttemptResponse]
    recommended_exercises: List[ListeningExerciseResponse]
    analytics: ListeningAnalytics
    daily_goal_progress: Dict[str, Any]
    achievements: List[Dict[str, Any]]

# Audio Playback Schemas
class AudioPlaybackEvent(BaseModel):
    audio_content_id: int
    position_seconds: float
    action: str  # play, pause, seek, complete
    session_id: Optional[str] = None

class AudioPlaybackResponse(BaseModel):
    success: bool
    message: str
    current_position: Optional[float] = None

# Exercise Submission Schemas
class ExerciseSubmission(BaseModel):
    exercise_id: int
    answers: List[Dict[str, Any]]  # question_id and user_answer pairs
    time_taken_minutes: Optional[int] = None

class ExerciseSubmissionResponse(BaseModel):
    attempt_id: int
    total_score: float
    max_possible_score: int
    completion_percentage: float
    correct_answers: int
    total_questions: int
    detailed_results: List[Dict[str, Any]]
    feedback: Optional[str] = None
    next_recommendations: Optional[List[int]] = None

# Statistics Schemas
class ListeningStatistics(BaseModel):
    user_id: int
    total_time_minutes: int
    exercises_completed: int
    average_score: float
    best_score: float
    current_streak: int
    level_distribution: Dict[str, int]
    monthly_progress: Dict[str, Dict[str, Any]]
    weak_areas: List[str]
    strong_areas: List[str] 