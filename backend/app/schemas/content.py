"""
Content schemas for SelmApp API
Pydantic models for content-related API requests and responses
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.content import ContentType, DifficultyLevel, VocabularyStatus

class ContentBase(BaseModel):
    title: str = Field(..., max_length=300)
    description: Optional[str] = None
    content_type: ContentType
    difficulty_level: DifficultyLevel
    content_data: Optional[Dict[str, Any]] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    tags: Optional[List[str]] = None
    estimated_duration: Optional[int] = None
    is_active: bool = True
    is_featured: bool = False

class ContentCreate(ContentBase):
    pass

class ContentUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    content_type: Optional[ContentType] = None
    difficulty_level: Optional[DifficultyLevel] = None
    content_data: Optional[Dict[str, Any]] = None
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    tags: Optional[List[str]] = None
    estimated_duration: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None

class ContentResponse(ContentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VocabularyBase(BaseModel):
    word: str = Field(..., max_length=100)
    pronunciation: Optional[str] = None
    definition: str
    example_sentence: Optional[str] = None
    translation: Optional[str] = None
    part_of_speech: Optional[str] = None
    difficulty_level: DifficultyLevel
    frequency_rank: Optional[int] = None
    
    # Enhanced fields
    synonyms: Optional[List[str]] = None
    antonyms: Optional[List[str]] = None
    word_family: Optional[Dict[str, str]] = None  # {"noun": "happiness", "adjective": "happy"}
    collocations: Optional[List[str]] = None
    usage_notes: Optional[str] = None
    etymology: Optional[str] = None
    
    # CEFR-specific
    cefr_source: str = "official"
    is_core_vocabulary: bool = False
    topic_categories: Optional[List[str]] = None
    
    # Media
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True

class VocabularyCreate(VocabularyBase):
    pass

class VocabularyUpdate(BaseModel):
    word: Optional[str] = Field(None, max_length=100)
    pronunciation: Optional[str] = None
    definition: Optional[str] = None
    example_sentence: Optional[str] = None
    translation: Optional[str] = None
    part_of_speech: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None
    frequency_rank: Optional[int] = None
    
    # Enhanced fields
    synonyms: Optional[List[str]] = None
    antonyms: Optional[List[str]] = None
    word_family: Optional[Dict[str, str]] = None
    collocations: Optional[List[str]] = None
    usage_notes: Optional[str] = None
    etymology: Optional[str] = None
    
    # CEFR-specific
    cefr_source: Optional[str] = None
    is_core_vocabulary: Optional[bool] = None
    topic_categories: Optional[List[str]] = None
    
    # Media
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None

class VocabularyResponse(VocabularyBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class GrammarBase(BaseModel):
    title: str = Field(..., max_length=300)
    rule: str
    explanation: str
    examples: Optional[List[str]] = None
    difficulty_level: DifficultyLevel
    is_active: bool = True

class GrammarCreate(GrammarBase):
    pass

class GrammarUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    rule: Optional[str] = None
    explanation: Optional[str] = None
    examples: Optional[List[str]] = None
    difficulty_level: Optional[DifficultyLevel] = None
    is_active: Optional[bool] = None

class GrammarResponse(GrammarBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DailyContentResponse(BaseModel):
    sentences: List[ContentResponse]
    vocabulary: List[VocabularyResponse]
    grammar: List[GrammarResponse]

class LearningPathResponse(BaseModel):
    current_level: str
    vocabulary: List[VocabularyResponse]
    grammar: List[GrammarResponse]
    reading: List[ContentResponse]
    listening: List[ContentResponse]
    next_level_preview: List[ContentResponse]

class ContentStatistics(BaseModel):
    A1_count: int
    A2_count: int
    B1_count: int
    B2_count: int
    C1_count: int
    C2_count: int
    vocabulary_count: int
    grammar_count: int
    listening_count: int
    reading_count: int
    speaking_count: int
    writing_count: int
    total_content: int
    total_vocabulary: int
    total_grammar: int

class SentenceResponse(BaseModel):
    id: int
    sentence: str
    level: str
    source: str
    audio_url: Optional[str] = None
    translation: Optional[str] = None
    difficulty_score: Optional[float] = None

    class Config:
        from_attributes = True

# User Vocabulary Tracking Schemas
class UserVocabularyBase(BaseModel):
    vocabulary_id: int
    status: VocabularyStatus = VocabularyStatus.NEW
    mastery_level: float = Field(0.0, ge=0.0, le=1.0)
    
    # Spaced repetition
    ease_factor: float = 2.5
    interval_days: int = 1
    next_review_date: Optional[datetime] = None
    
    # Statistics
    times_seen: int = 0
    times_correct: int = 0
    times_incorrect: int = 0
    streak_count: int = 0
    
    # Context
    last_seen_in_context: Optional[str] = None
    user_notes: Optional[str] = None
    personal_examples: Optional[List[str]] = None

class UserVocabularyCreate(UserVocabularyBase):
    pass

class UserVocabularyUpdate(BaseModel):
    status: Optional[VocabularyStatus] = None
    mastery_level: Optional[float] = Field(None, ge=0.0, le=1.0)
    ease_factor: Optional[float] = None
    interval_days: Optional[int] = None
    next_review_date: Optional[datetime] = None
    times_seen: Optional[int] = None
    times_correct: Optional[int] = None
    times_incorrect: Optional[int] = None
    streak_count: Optional[int] = None
    last_seen_in_context: Optional[str] = None
    user_notes: Optional[str] = None
    personal_examples: Optional[List[str]] = None

class UserVocabularyResponse(UserVocabularyBase):
    id: int
    user_id: int
    vocabulary: VocabularyResponse
    first_encountered_date: datetime
    last_reviewed_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Vocabulary Set Schemas
class VocabularySetBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    difficulty_level: DifficultyLevel
    topic: Optional[str] = None
    estimated_study_time: Optional[int] = None
    is_public: bool = True
    is_featured: bool = False
    is_active: bool = True

class VocabularySetCreate(VocabularySetBase):
    vocabulary_ids: Optional[List[int]] = None  # IDs of vocabulary to include

class VocabularySetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None
    topic: Optional[str] = None
    estimated_study_time: Optional[int] = None
    is_public: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None

class VocabularySetItemResponse(BaseModel):
    id: int
    vocabulary: VocabularyResponse
    order_index: int
    is_priority: bool
    custom_definition: Optional[str] = None
    custom_example: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class VocabularySetResponse(VocabularySetBase):
    id: int
    word_count: int
    created_by_user_id: Optional[int] = None
    vocabulary_items: Optional[List[VocabularySetItemResponse]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Vocabulary Exercise Schemas
class VocabularyExerciseBase(BaseModel):
    vocabulary_id: int
    exercise_type: str = Field(..., max_length=50)
    question: str
    correct_answer: str = Field(..., max_length=500)
    user_answer: Optional[str] = Field(None, max_length=500)
    is_correct: Optional[bool] = None
    points_earned: int = 0
    time_taken_seconds: Optional[int] = None
    exercise_context: Optional[str] = None

class VocabularyExerciseCreate(VocabularyExerciseBase):
    pass

class VocabularyExerciseResponse(VocabularyExerciseBase):
    id: int
    user_id: int
    vocabulary: VocabularyResponse
    difficulty_at_time: Optional[DifficultyLevel] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Bulk Import Schemas
class VocabularyBulkImport(BaseModel):
    vocabulary_items: List[VocabularyCreate]
    source: str = "import"
    overwrite_existing: bool = False

class VocabularyImportResult(BaseModel):
    total_processed: int
    successful_imports: int
    skipped_duplicates: int
    errors: List[str]
    imported_ids: List[int]

# Learning Analytics Schemas
class VocabularyLearningStats(BaseModel):
    total_words: int
    words_by_level: Dict[str, int]
    words_by_status: Dict[str, int]
    mastery_average: float
    daily_review_count: int
    streak_days: int
    next_review_words: int

class VocabularyReviewSession(BaseModel):
    words_to_review: List[UserVocabularyResponse]
    session_type: str  # "daily_review", "new_words", "reinforcement"
    estimated_duration_minutes: int

# Search and Filter Schemas
class VocabularySearchRequest(BaseModel):
    query: Optional[str] = None
    difficulty_levels: Optional[List[DifficultyLevel]] = None
    topics: Optional[List[str]] = None
    part_of_speech: Optional[List[str]] = None
    mastery_status: Optional[List[VocabularyStatus]] = None
    include_mastered: bool = True
    sort_by: str = "word"  # "word", "frequency", "difficulty", "date_added"
    sort_order: str = "asc"  # "asc", "desc"
    skip: int = 0
    limit: int = 100

class VocabularySearchResponse(BaseModel):
    items: List[VocabularyResponse]
    total_count: int
    has_more: bool 