from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from app.models.exercise import ExerciseType, DifficultyLevel

# Exercise Schemas
class ExerciseBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    exercise_type: ExerciseType
    difficulty_level: DifficultyLevel
    question: str
    options: Optional[Dict[str, Any]] = None
    correct_answer: Dict[str, Any]
    explanation: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    points: int = 10
    time_limit_seconds: Optional[int] = None
    order_index: int = 0
    is_active: bool = True

class ExerciseCreate(ExerciseBase):
    content_id: Optional[int] = None

class ExerciseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    question: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    correct_answer: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    points: Optional[int] = None
    time_limit_seconds: Optional[int] = None
    order_index: Optional[int] = None
    is_active: Optional[bool] = None

class ExerciseResponse(ExerciseBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    content_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# Exercise for practice (without correct answer)
class ExercisePracticeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    description: Optional[str] = None
    exercise_type: ExerciseType
    difficulty_level: DifficultyLevel
    question: str
    options: Optional[Dict[str, Any]] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    points: int
    time_limit_seconds: Optional[int] = None

# Exercise Attempt Schemas
class ExerciseAttemptBase(BaseModel):
    user_answer: Dict[str, Any]
    time_taken_seconds: Optional[int] = None

class ExerciseAttemptCreate(ExerciseAttemptBase):
    user_id: int
    exercise_id: int

class ExerciseAttemptResponse(ExerciseAttemptBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    exercise_id: int
    is_correct: bool
    score: float
    ai_feedback: Optional[str] = None
    pronunciation_score: Optional[float] = None
    created_at: datetime
    exercise: Optional[ExerciseResponse] = None

# Exercise Statistics
class ExerciseStatisticsResponse(BaseModel):
    total_attempts: int
    correct_attempts: int
    accuracy_rate: float
    average_score: float
    average_time: float

class ExercisePerformanceResponse(BaseModel):
    date: datetime
    attempts: int
    correct: int
    accuracy: float
    average_score: float

# Quiz Schemas
class QuizBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    difficulty_level: DifficultyLevel
    time_limit_minutes: Optional[int] = None
    passing_score: float = Field(default=0.7, ge=0.0, le=1.0)
    max_attempts: int = 3
    is_active: bool = True

class QuizCreate(QuizBase):
    exercise_ids: Optional[List[int]] = []

class QuizUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    passing_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_attempts: Optional[int] = None
    is_active: Optional[bool] = None

class QuizResponse(QuizBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

class QuizWithExercisesResponse(QuizResponse):
    exercises: List[ExercisePracticeResponse] = []

# Quiz Attempt Schemas
class QuizAttemptBase(BaseModel):
    pass

class QuizAttemptCreate(QuizAttemptBase):
    user_id: int
    quiz_id: int

class QuizAttemptUpdate(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0)
    total_questions: int
    correct_answers: int
    time_taken_minutes: Optional[int] = None
    passed: bool
    completed_at: datetime

class QuizAttemptResponse(QuizAttemptBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    quiz_id: int
    score: float
    total_questions: int
    correct_answers: int
    time_taken_minutes: Optional[int] = None
    passed: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    quiz: Optional[QuizResponse] = None

# Exercise Submission for API
class ExerciseSubmissionRequest(BaseModel):
    exercise_id: int
    user_answer: Dict[str, Any]
    time_taken_seconds: Optional[int] = None

class ExerciseSubmissionResponse(BaseModel):
    is_correct: bool
    score: float
    points_earned: int
    correct_answer: Dict[str, Any]
    explanation: Optional[str] = None
    ai_feedback: Optional[str] = None
    pronunciation_score: Optional[float] = None

# Quiz Submission
class QuizSubmissionRequest(BaseModel):
    quiz_id: int
    answers: List[Dict[str, Any]]  # List of {exercise_id, user_answer, time_taken}

class QuizSubmissionResponse(BaseModel):
    quiz_attempt_id: int
    score: float
    total_questions: int
    correct_answers: int
    passed: bool
    time_taken_minutes: int
    points_earned: int
    detailed_results: List[Dict[str, Any]]

# Learning Path Exercise Response
class LearningPathExerciseResponse(BaseModel):
    level: DifficultyLevel
    vocabulary_exercises: List[ExercisePracticeResponse]
    grammar_exercises: List[ExercisePracticeResponse]
    listening_exercises: List[ExercisePracticeResponse]
    reading_exercises: List[ExercisePracticeResponse]
    speaking_exercises: List[ExercisePracticeResponse]
    writing_exercises: List[ExercisePracticeResponse]

# Exercise Generation Request (for AI)
class ExerciseGenerationRequest(BaseModel):
    topic: str
    difficulty_level: DifficultyLevel
    exercise_type: ExerciseType
    count: int = Field(default=5, ge=1, le=20)
    content_id: Optional[int] = None

class ExerciseGenerationResponse(BaseModel):
    success: bool
    exercises: List[ExerciseCreate] = []
    error_message: Optional[str] = None 