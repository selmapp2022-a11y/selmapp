from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class WritingType(str, Enum):
    ESSAY = "essay"
    LETTER = "letter"
    EMAIL = "email"
    STORY = "story"
    REPORT = "report"
    REVIEW = "review"
    DESCRIPTION = "description"
    DIALOGUE = "dialogue"
    SUMMARY = "summary"

class WritingSkillLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class DifficultyLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

# Writing Prompt Schemas
class WritingPromptBase(BaseModel):
    title: str = Field(..., max_length=300)
    prompt_text: str
    instructions: Optional[str] = None
    writing_type: WritingType
    difficulty_level: DifficultyLevel
    skill_level: WritingSkillLevel
    min_words: int = Field(default=50, ge=10)
    max_words: int = Field(default=500, ge=50)
    time_limit_minutes: Optional[int] = Field(None, ge=5)
    required_vocabulary: Optional[List[str]] = None
    grammar_focus: Optional[List[str]] = None
    topic_keywords: Optional[List[str]] = None
    scoring_rubric: Optional[Dict[str, Any]] = None
    max_points: int = Field(default=100, ge=1)
    topic: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None

class WritingPromptCreate(WritingPromptBase):
    pass

class WritingPromptUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=300)
    prompt_text: Optional[str] = None
    instructions: Optional[str] = None
    writing_type: Optional[WritingType] = None
    difficulty_level: Optional[DifficultyLevel] = None
    skill_level: Optional[WritingSkillLevel] = None
    min_words: Optional[int] = Field(None, ge=10)
    max_words: Optional[int] = Field(None, ge=50)
    time_limit_minutes: Optional[int] = Field(None, ge=5)
    required_vocabulary: Optional[List[str]] = None
    grammar_focus: Optional[List[str]] = None
    topic_keywords: Optional[List[str]] = None
    scoring_rubric: Optional[Dict[str, Any]] = None
    max_points: Optional[int] = Field(None, ge=1)
    topic: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None

class WritingPromptResponse(WritingPromptBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

class WritingPromptPractice(BaseModel):
    """Writing prompt for practice (simplified view)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    prompt_text: str
    instructions: Optional[str] = None
    writing_type: WritingType
    difficulty_level: DifficultyLevel
    min_words: int
    max_words: int
    time_limit_minutes: Optional[int] = None
    required_vocabulary: Optional[List[str]] = None
    grammar_focus: Optional[List[str]] = None
    topic_keywords: Optional[List[str]] = None

# Writing Submission Schemas
class WritingSubmissionCreate(BaseModel):
    writing_prompt_id: int
    content: str
    time_spent_minutes: Optional[int] = None
    is_draft: bool = Field(default=False)

class WritingSubmissionUpdate(BaseModel):
    content: Optional[str] = None
    time_spent_minutes: Optional[int] = None
    is_draft: Optional[bool] = None

class WritingSubmissionSubmit(BaseModel):
    writing_prompt_id: int
    content: str
    time_spent_minutes: int
    started_at: Optional[datetime] = None

class WritingSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    writing_prompt_id: int
    content: str
    word_count: int
    time_spent_minutes: Optional[int] = None
    started_at: Optional[datetime] = None
    submitted_at: datetime
    
    # Auto-correction results
    original_content: Optional[str] = None
    corrected_content: Optional[str] = None
    spelling_errors: Optional[List[Dict[str, Any]]] = None
    grammar_errors: Optional[List[Dict[str, Any]]] = None
    
    # Assessment results
    overall_score: float
    grammar_score: float
    vocabulary_score: float
    coherence_score: float
    task_achievement_score: float
    
    # AI feedback
    ai_feedback: Optional[str] = None
    suggestions: Optional[List[str]] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    
    # Status
    is_draft: bool
    is_evaluated: bool

class WritingSubmissionWithFeedback(WritingSubmissionResponse):
    writing_feedback: Optional["WritingFeedbackResponse"] = None
    writing_prompt: WritingPromptResponse

# Writing Feedback Schemas
class WritingFeedbackCreate(BaseModel):
    writing_submission_id: int
    content_organization: float = Field(default=0.0, ge=0.0, le=100.0)
    language_accuracy: float = Field(default=0.0, ge=0.0, le=100.0)
    vocabulary_range: float = Field(default=0.0, ge=0.0, le=100.0)
    sentence_structure: float = Field(default=0.0, ge=0.0, le=100.0)
    punctuation_mechanics: float = Field(default=0.0, ge=0.0, le=100.0)
    positive_aspects: Optional[List[str]] = None
    areas_for_improvement: Optional[List[str]] = None
    specific_errors: Optional[List[Dict[str, Any]]] = None
    vocabulary_suggestions: Optional[List[Dict[str, Any]]] = None
    next_steps: Optional[List[str]] = None
    recommended_exercises: Optional[List[str]] = None
    feedback_type: str = Field(default="automated")

class WritingFeedbackUpdate(BaseModel):
    content_organization: Optional[float] = Field(None, ge=0.0, le=100.0)
    language_accuracy: Optional[float] = Field(None, ge=0.0, le=100.0)
    vocabulary_range: Optional[float] = Field(None, ge=0.0, le=100.0)
    sentence_structure: Optional[float] = Field(None, ge=0.0, le=100.0)
    punctuation_mechanics: Optional[float] = Field(None, ge=0.0, le=100.0)
    positive_aspects: Optional[List[str]] = None
    areas_for_improvement: Optional[List[str]] = None
    specific_errors: Optional[List[Dict[str, Any]]] = None
    vocabulary_suggestions: Optional[List[Dict[str, Any]]] = None
    next_steps: Optional[List[str]] = None
    recommended_exercises: Optional[List[str]] = None
    feedback_type: Optional[str] = None

class WritingFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    writing_submission_id: int
    
    # Detailed scores
    content_organization: float
    language_accuracy: float
    vocabulary_range: float
    sentence_structure: float
    punctuation_mechanics: float
    
    # Specific feedback
    positive_aspects: Optional[List[str]] = None
    areas_for_improvement: Optional[List[str]] = None
    specific_errors: Optional[List[Dict[str, Any]]] = None
    vocabulary_suggestions: Optional[List[Dict[str, Any]]] = None
    
    # Recommendations
    next_steps: Optional[List[str]] = None
    recommended_exercises: Optional[List[str]] = None
    
    feedback_type: str
    generated_at: datetime

# Writing Assessment Schemas
class WritingAssessmentRequest(BaseModel):
    submission_id: int
    assessment_type: str = Field(default="automated", description="automated, human, hybrid")

class WritingAssessmentResponse(BaseModel):
    submission_id: int
    overall_score: float
    detailed_scores: Dict[str, float]
    feedback: WritingFeedbackResponse
    corrections: List[Dict[str, Any]]
    suggestions: List[str]
    estimated_level: DifficultyLevel

# Writing Template Schemas
class WritingTemplateBase(BaseModel):
    name: str = Field(..., max_length=200)
    writing_type: WritingType
    difficulty_level: DifficultyLevel
    structure: Optional[Dict[str, Any]] = None
    sample_phrases: Optional[List[str]] = None
    transition_words: Optional[List[str]] = None
    description: Optional[str] = None
    example_text: Optional[str] = None

class WritingTemplateCreate(WritingTemplateBase):
    pass

class WritingTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    writing_type: Optional[WritingType] = None
    difficulty_level: Optional[DifficultyLevel] = None
    structure: Optional[Dict[str, Any]] = None
    sample_phrases: Optional[List[str]] = None
    transition_words: Optional[List[str]] = None
    description: Optional[str] = None
    example_text: Optional[str] = None
    is_active: Optional[bool] = None

class WritingTemplateResponse(WritingTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime

# Writing Progress Schemas
class WritingProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    total_submissions: int
    total_words_written: int
    total_writing_time_minutes: int
    average_score: float
    best_score: float
    average_grammar_score: float
    average_vocabulary_score: float
    grammar_improvement_rate: float
    vocabulary_improvement_rate: float
    writing_speed_wpm: float
    current_level: DifficultyLevel
    submissions_by_level: Dict[str, int]
    submissions_by_type: Dict[str, int]
    common_grammar_errors: List[str]
    common_spelling_errors: List[str]
    error_reduction_rate: float
    current_writing_streak: int
    longest_writing_streak: int
    last_writing_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class WritingProgressUpdate(BaseModel):
    total_submissions: Optional[int] = None
    total_words_written: Optional[int] = None
    total_writing_time_minutes: Optional[int] = None
    average_score: Optional[float] = None
    best_score: Optional[float] = None
    average_grammar_score: Optional[float] = None
    average_vocabulary_score: Optional[float] = None
    writing_speed_wpm: Optional[float] = None
    current_level: Optional[DifficultyLevel] = None

# Writing Statistics and Analytics
class WritingStatistics(BaseModel):
    total_submissions: int
    total_words_written: int
    total_writing_time_hours: float
    average_score: float
    grammar_accuracy: float
    vocabulary_diversity: float
    writing_speed_wpm: float
    favorite_writing_types: List[Dict[str, Any]]
    writing_streak: int
    level_distribution: Dict[str, int]
    improvement_trends: Dict[str, float]

class WritingAnalytics(BaseModel):
    daily_writing_activity: List[Dict[str, Any]]  # Last 30 days
    score_trends: List[Dict[str, Any]]  # Progress over time
    grammar_improvement: List[Dict[str, Any]]  # Grammar accuracy trends
    vocabulary_growth: List[Dict[str, Any]]  # Vocabulary usage over time
    writing_speed_trends: List[Dict[str, Any]]  # Speed improvement
    error_patterns: Dict[str, List[Dict[str, Any]]]  # Common errors analysis
    writing_type_performance: Dict[str, Dict[str, float]]

class WritingDashboard(BaseModel):
    current_stats: WritingStatistics
    recent_submissions: List[WritingSubmissionResponse]
    recommended_prompts: List[WritingPromptResponse]
    achievements: List[Dict[str, Any]]
    improvement_goals: List[Dict[str, Any]]
    error_focus_areas: List[str]

# Grammar Rule Schemas
class GrammarRuleBase(BaseModel):
    name: str = Field(..., max_length=200)
    category: str = Field(..., max_length=100)
    difficulty_level: DifficultyLevel
    rule_description: str
    pattern: Optional[str] = Field(None, max_length=500)
    correct_examples: Optional[List[str]] = None
    incorrect_examples: Optional[List[str]] = None
    explanation: Optional[str] = None
    correction_suggestion: Optional[str] = None
    priority: int = Field(default=1, ge=1)

class GrammarRuleCreate(GrammarRuleBase):
    pass

class GrammarRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = Field(None, max_length=100)
    difficulty_level: Optional[DifficultyLevel] = None
    rule_description: Optional[str] = None
    pattern: Optional[str] = Field(None, max_length=500)
    correct_examples: Optional[List[str]] = None
    incorrect_examples: Optional[List[str]] = None
    explanation: Optional[str] = None
    correction_suggestion: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None

class GrammarRuleResponse(GrammarRuleBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    created_at: datetime

# Writing Session Schemas
class WritingSessionStart(BaseModel):
    writing_prompt_id: int

class WritingSessionSave(BaseModel):
    content: str
    time_spent_minutes: int

class WritingSessionResponse(BaseModel):
    session_id: str
    writing_prompt: WritingPromptPractice
    started_at: datetime
    auto_save_enabled: bool = True
    templates: List[WritingTemplateResponse]
    grammar_rules: List[GrammarRuleResponse]

# Auto-correction Schemas
class AutoCorrectionRequest(BaseModel):
    content: str
    check_spelling: bool = True
    check_grammar: bool = True
    suggest_improvements: bool = True

class AutoCorrectionResponse(BaseModel):
    original_content: str
    corrected_content: str
    spelling_corrections: List[Dict[str, Any]]
    grammar_corrections: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    confidence_score: float 