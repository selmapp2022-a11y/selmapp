from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: dict  # User data as dictionary

class TokenPayload(BaseModel):
    sub: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    native_language: Optional[str] = "Persian"
    target_language: Optional[str] = "English"

class OAuth2UserCreate(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    native_language: Optional[str] = "Persian"
    target_language: Optional[str] = "English"
    provider: str
    provider_user_id: str
    provider_email: Optional[str] = None
    provider_name: Optional[str] = None
    provider_avatar_url: Optional[str] = None

class OAuth2LoginRequest(BaseModel):
    provider: str
    code: str
    state: Optional[str] = None

class OAuth2AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    provider: str
    provider_user_id: str
    provider_email: Optional[str] = None
    provider_name: Optional[str] = None
    provider_avatar_url: Optional[str] = None
    created_at: datetime

class OAuth2AuthURL(BaseModel):
    auth_url: str
    state: str

class PasswordReset(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# Level Assessment Schemas
class AssessmentQuestion(BaseModel):
    id: int
    skill: str  # grammar, vocabulary, reading, listening
    difficulty_level: str  # A1, A2, B1, B2, C1, C2
    question_type: str  # multiple_choice, true_false, fill_in_blank
    question: str
    passage: Optional[str] = None  # Optional reading passage text
    audio_url: Optional[str] = None  # Optional listening audio URL
    audio_text: Optional[str] = None  # Optional listening TTS text fallback
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: str
    points: int

class LevelAssessmentQuiz(BaseModel):
    quiz_metadata: Dict[str, Any]
    questions: List[AssessmentQuestion]

class LevelAssessmentResponse(BaseModel):
    quiz_data: LevelAssessmentQuiz
    assessment_id: str
    message: str

class LevelAssessmentSubmission(BaseModel):
    assessment_id: Optional[str] = None
    answers: List[Dict[str, Any]]  # flexible answer payload from frontend
    total_time_taken_minutes: Optional[int] = None

class LevelAssessmentResult(BaseModel):
    old_level: str
    new_level: str
    score: float
    level_changed: bool
    skill_breakdown: Dict[str, float]
    recommendations: List[str]
    message: str

# Async Level Assessment Job Schemas
class LevelAssessmentStartRequest(BaseModel):
    user_preferences: Optional[List[str]] = None
    question_count: Optional[int] = 20
    personalized: Optional[bool] = True

class LevelAssessmentJobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int
    message: Optional[str] = None
    quiz_data: Optional[Dict[str, Any]] = None

# Personal Trainer Schemas
class TrainerInteractionRequest(BaseModel):
    message: str
    lesson_context: Optional[Dict[str, Any]] = None

class TrainerCorrection(BaseModel):
    original: str
    corrected: str
    explanation: str

class SuggestedAction(BaseModel):
    action: str
    description: str
    estimated_time_minutes: int

class VocabularyHighlight(BaseModel):
    word: str
    definition: str
    example: str

class TrainerInteractionResponse(BaseModel):
    trainer_response: str
    message_type: str  # encouragement, correction, explanation, instruction, assessment
    corrections: List[TrainerCorrection]
    suggested_actions: List[SuggestedAction]
    follow_up_questions: List[str]
    vocabulary_highlights: List[VocabularyHighlight]
    interaction_id: int

# Content Generation Schemas
class PersonalizedContentRequest(BaseModel):
    content_type: str  # reading, vocabulary, grammar, speaking, writing
    topic: Optional[str] = None
    difficulty_override: Optional[str] = None  # Override user's level if needed
    word_count: Optional[int] = None
    include_audio: bool = False

class ContentRecommendation(BaseModel):
    topic: str
    content_type: str
    reason: str
    learning_outcome: str
    estimated_time_minutes: int

class PersonalizedContentResponse(BaseModel):
    generated_content: Dict[str, Any]
    recommendations: List[ContentRecommendation]
    learning_path_update: Optional[Dict[str, Any]] = None 