from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class ReadingTextType(str, Enum):
    ARTICLE = "article"
    STORY = "story"
    NEWS = "news"
    LETTER = "letter"
    ESSAY = "essay"
    DIALOGUE = "dialogue"
    INSTRUCTION = "instruction"

class DifficultyLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

# Reading Text Schemas
class ReadingTextBase(BaseModel):
    title: str = Field(..., max_length=300)
    content: str
    text_type: ReadingTextType
    difficulty_level: DifficultyLevel
    word_count: int
    estimated_reading_time: Optional[int] = None
    source: Optional[str] = Field(None, max_length=200)
    author: Optional[str] = Field(None, max_length=200)
    topic: Optional[str] = Field(None, max_length=100)
    keywords: Optional[List[str]] = None

class ReadingTextCreate(ReadingTextBase):
    pass

class ReadingTextUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    content: Optional[str] = None
    text_type: Optional[ReadingTextType] = None
    difficulty_level: Optional[DifficultyLevel] = None
    word_count: Optional[int] = None
    estimated_reading_time: Optional[int] = None
    source: Optional[str] = Field(None, max_length=200)
    author: Optional[str] = Field(None, max_length=200)
    topic: Optional[str] = Field(None, max_length=100)
    keywords: Optional[List[str]] = None
    is_active: Optional[bool] = None

class ReadingTextResponse(ReadingTextBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

class ReadingTextWithExercises(ReadingTextResponse):
    reading_exercises: List["ReadingExerciseResponse"] = []
    vocabulary_highlights: List["VocabularyHighlightResponse"] = []

class ReadingTextPractice(BaseModel):
    """Reading text for practice (simplified view)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    content: str
    text_type: ReadingTextType
    difficulty_level: DifficultyLevel
    word_count: int
    estimated_reading_time: Optional[int] = None
    topic: Optional[str] = None
    keywords: Optional[List[str]] = None

# Reading Exercise Schemas
class ReadingExerciseBase(BaseModel):
    title: str = Field(..., max_length=300)
    question: str
    exercise_type: str = Field(..., description="multiple_choice, true_false, short_answer, essay")
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: Optional[str] = None
    points: int = Field(default=1, ge=1)
    order_index: int = Field(default=0, ge=0)

class ReadingExerciseCreate(ReadingExerciseBase):
    reading_text_id: int

class ReadingExerciseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    question: Optional[str] = None
    exercise_type: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    points: Optional[int] = Field(None, ge=1)
    order_index: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class ReadingExerciseResponse(ReadingExerciseBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reading_text_id: int
    is_active: bool
    created_at: datetime

class ReadingExercisePractice(BaseModel):
    """Exercise for practice (without correct answer)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reading_text_id: int
    title: str
    question: str
    exercise_type: str
    options: Optional[List[str]] = None
    points: int
    order_index: int

# Reading Attempt Schemas
class ReadingAttemptCreate(BaseModel):
    reading_text_id: int
    reading_exercise_id: Optional[int] = None
    reading_time_seconds: Optional[int] = None
    user_answer: Optional[str] = None

class ReadingAttemptSubmit(BaseModel):
    reading_text_id: int
    reading_exercise_id: int
    user_answer: str
    reading_time_seconds: int

class ReadingAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    reading_text_id: int
    reading_exercise_id: Optional[int] = None
    reading_time_seconds: Optional[int] = None
    words_per_minute: Optional[float] = None
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    score: float
    comprehension_score: Optional[float] = None
    vocabulary_learned: Optional[List[str]] = None
    created_at: datetime

class ReadingAttemptFeedback(BaseModel):
    is_correct: bool
    score: float
    correct_answer: str
    explanation: Optional[str] = None
    reading_speed_wpm: Optional[float] = None
    comprehension_score: Optional[float] = None
    vocabulary_learned: Optional[List[str]] = None
    feedback: Optional[str] = None

# Vocabulary Highlight Schemas
class VocabularyHighlightBase(BaseModel):
    word: str = Field(..., max_length=100)
    definition: str
    part_of_speech: Optional[str] = Field(None, max_length=50)
    difficulty_level: DifficultyLevel
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    phonetic: Optional[str] = Field(None, max_length=200)
    example_sentence: Optional[str] = None
    translation: Optional[Dict[str, str]] = None

class VocabularyHighlightCreate(VocabularyHighlightBase):
    reading_text_id: int

class VocabularyHighlightUpdate(BaseModel):
    word: Optional[str] = Field(None, max_length=100)
    definition: Optional[str] = None
    part_of_speech: Optional[str] = Field(None, max_length=50)
    difficulty_level: Optional[DifficultyLevel] = None
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    phonetic: Optional[str] = Field(None, max_length=200)
    example_sentence: Optional[str] = None
    translation: Optional[Dict[str, str]] = None

class VocabularyHighlightResponse(VocabularyHighlightBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    reading_text_id: int
    created_at: datetime

# Reading Progress Schemas
class ReadingProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    total_texts_read: int
    total_reading_time_minutes: int
    average_reading_speed_wpm: float
    average_comprehension_score: float
    total_exercises_completed: int
    total_exercises_correct: int
    current_level: DifficultyLevel
    texts_completed_by_level: Dict[str, int]
    total_vocabulary_learned: int
    vocabulary_by_level: Dict[str, int]
    current_reading_streak: int
    longest_reading_streak: int
    last_reading_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ReadingProgressUpdate(BaseModel):
    total_texts_read: Optional[int] = None
    total_reading_time_minutes: Optional[int] = None
    average_reading_speed_wpm: Optional[float] = None
    average_comprehension_score: Optional[float] = None
    total_exercises_completed: Optional[int] = None
    total_exercises_correct: Optional[int] = None
    current_level: Optional[DifficultyLevel] = None
    texts_completed_by_level: Optional[Dict[str, int]] = None
    total_vocabulary_learned: Optional[int] = None
    vocabulary_by_level: Optional[Dict[str, int]] = None

# Reading Statistics and Analytics
class ReadingStatistics(BaseModel):
    total_texts_read: int
    total_reading_time_hours: float
    average_reading_speed_wpm: float
    average_comprehension_score: float
    total_exercises_completed: int
    accuracy_rate: float
    vocabulary_learned: int
    reading_streak: int
    favorite_text_types: List[Dict[str, Any]]
    current_level: DifficultyLevel

class ReadingAnalytics(BaseModel):
    daily_reading_activity: List[Dict[str, Any]]  # Last 30 days
    comprehension_trends: List[Dict[str, Any]]  # Progress over time
    reading_speed_trends: List[Dict[str, Any]]  # Speed improvement
    text_type_performance: Dict[str, Any]  # Performance by text type
    vocabulary_growth: List[Dict[str, Any]]  # Words learned over time

class ReadingDashboard(BaseModel):
    current_stats: ReadingStatistics
    recent_attempts: List[ReadingAttemptResponse]
    recommended_texts: List[ReadingTextResponse]
    reading_goals: List[Dict[str, Any]]

# Reading Session Schemas
class ReadingSessionStart(BaseModel):
    reading_text_id: int

class ReadingSessionEnd(BaseModel):
    reading_text_id: int
    reading_time_seconds: int
    comprehension_exercises: List[Dict[str, Any]]  # Exercise attempts

class ReadingSessionSave(BaseModel):
    content_progress: Dict[str, Any]
    time_spent_seconds: int

class ReadingSessionResponse(BaseModel):
    reading_text: ReadingTextWithExercises
    vocabulary_highlights: List[VocabularyHighlightResponse]
    session_started_at: datetime 