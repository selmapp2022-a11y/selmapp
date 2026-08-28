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

class SpeakingExerciseType(str, Enum):
    WORD_PRONUNCIATION = "word_pronunciation"
    SENTENCE_READING = "sentence_reading"
    CONVERSATION = "conversation"
    STORYTELLING = "storytelling"
    DESCRIPTION = "description"
    ROLE_PLAY = "role_play"
    PRESENTATION = "presentation"
    PRONUNCIATION_DRILL = "pronunciation_drill"
    FLUENCY_PRACTICE = "fluency_practice"

class PronunciationFocus(str, Enum):
    PHONEMES = "phonemes"
    WORD_STRESS = "word_stress"
    SENTENCE_STRESS = "sentence_stress"
    INTONATION = "intonation"
    RHYTHM = "rhythm"
    LINKING = "linking"
    REDUCTION = "reduction"

# Speaking Prompt Schemas
class SpeakingPromptBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    exercise_type: SpeakingExerciseType
    difficulty_level: DifficultyLevel
    pronunciation_focus: Optional[PronunciationFocus] = None
    prompt_text: str
    sample_audio_url: Optional[str] = Field(None, max_length=500)
    target_phonemes: Optional[List[str]] = None
    instructions: Optional[str] = None
    tips: Optional[List[str]] = None
    common_mistakes: Optional[List[str]] = None
    assessment_criteria: Optional[Dict[str, Any]] = None
    target_duration_seconds: Optional[int] = Field(None, gt=0)
    topic: Optional[str] = Field(None, max_length=100)
    keywords: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    is_active: bool = True
    is_premium: bool = False

class SpeakingPromptCreate(SpeakingPromptBase):
    pass

class SpeakingPromptUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    exercise_type: Optional[SpeakingExerciseType] = None
    difficulty_level: Optional[DifficultyLevel] = None
    pronunciation_focus: Optional[PronunciationFocus] = None
    prompt_text: Optional[str] = None
    sample_audio_url: Optional[str] = Field(None, max_length=500)
    target_phonemes: Optional[List[str]] = None
    instructions: Optional[str] = None
    tips: Optional[List[str]] = None
    common_mistakes: Optional[List[str]] = None
    assessment_criteria: Optional[Dict[str, Any]] = None
    target_duration_seconds: Optional[int] = Field(None, gt=0)
    topic: Optional[str] = Field(None, max_length=100)
    keywords: Optional[List[str]] = None
    learning_objectives: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_premium: Optional[bool] = None

class SpeakingPromptResponse(SpeakingPromptBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Speaking Attempt Schemas
class SpeakingAttemptBase(BaseModel):
    prompt_id: int
    audio_url: str = Field(..., max_length=500)
    duration_seconds: float = Field(..., gt=0)
    recording_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    transcribed_text: Optional[str] = None
    recognition_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    pronunciation_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    accuracy_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    fluency_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    completeness_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    phoneme_scores: Optional[Dict[str, float]] = None
    word_scores: Optional[Dict[str, float]] = None
    stress_pattern_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    intonation_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    pace_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    strengths: Optional[List[str]] = None
    areas_for_improvement: Optional[List[str]] = None
    specific_feedback: Optional[Dict[str, Any]] = None
    attempt_number: int = Field(1, ge=1)
    is_practice: bool = True

class SpeakingAttemptCreate(BaseModel):
    prompt_id: int
    audio_url: str = Field(..., max_length=500)
    duration_seconds: float = Field(..., gt=0)

class SpeakingAttemptUpdate(BaseModel):
    recording_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    transcribed_text: Optional[str] = None
    recognition_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    pronunciation_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    accuracy_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    fluency_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    completeness_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    phoneme_scores: Optional[Dict[str, float]] = None
    word_scores: Optional[Dict[str, float]] = None
    stress_pattern_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    intonation_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    pace_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    strengths: Optional[List[str]] = None
    areas_for_improvement: Optional[List[str]] = None
    specific_feedback: Optional[Dict[str, Any]] = None

class SpeakingAttemptResponse(SpeakingAttemptBase):
    id: int
    user_id: int
    prompt: SpeakingPromptResponse
    ai_overall_score: Optional[float] = None
    ai_feedback: Optional[str] = None
    ai_suggestions: Optional[List[str]] = None
    manual_score: Optional[float] = None
    manual_feedback: Optional[str] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Pronunciation Exercise Schemas
class PronunciationExerciseBase(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    pronunciation_focus: PronunciationFocus
    difficulty_level: DifficultyLevel
    target_words: List[str]
    target_phonemes: Optional[List[str]] = None
    practice_sentences: Optional[List[str]] = None
    reference_audio_url: Optional[str] = Field(None, max_length=500)
    slow_audio_url: Optional[str] = Field(None, max_length=500)
    instructions: Optional[str] = None
    tips: Optional[List[str]] = None
    visual_aids: Optional[Dict[str, Any]] = None
    is_active: bool = True

class PronunciationExerciseCreate(PronunciationExerciseBase):
    pass

class PronunciationExerciseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    pronunciation_focus: Optional[PronunciationFocus] = None
    difficulty_level: Optional[DifficultyLevel] = None
    target_words: Optional[List[str]] = None
    target_phonemes: Optional[List[str]] = None
    practice_sentences: Optional[List[str]] = None
    reference_audio_url: Optional[str] = Field(None, max_length=500)
    slow_audio_url: Optional[str] = Field(None, max_length=500)
    instructions: Optional[str] = None
    tips: Optional[List[str]] = None
    visual_aids: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class PronunciationExerciseResponse(PronunciationExerciseBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Pronunciation Attempt Schemas
class PronunciationAttemptBase(BaseModel):
    exercise_id: int
    audio_url: str = Field(..., max_length=500)
    duration_seconds: float = Field(..., gt=0)
    overall_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    phoneme_accuracy: Optional[Dict[str, float]] = None
    word_accuracy: Optional[Dict[str, float]] = None
    mispronounced_phonemes: Optional[List[str]] = None
    correct_phonemes: Optional[List[str]] = None
    improvement_suggestions: Optional[List[str]] = None

class PronunciationAttemptCreate(BaseModel):
    exercise_id: int
    audio_url: str = Field(..., max_length=500)
    duration_seconds: float = Field(..., gt=0)

class PronunciationAttemptUpdate(BaseModel):
    overall_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    phoneme_accuracy: Optional[Dict[str, float]] = None
    word_accuracy: Optional[Dict[str, float]] = None
    mispronounced_phonemes: Optional[List[str]] = None
    correct_phonemes: Optional[List[str]] = None
    improvement_suggestions: Optional[List[str]] = None

class PronunciationAttemptResponse(PronunciationAttemptBase):
    id: int
    user_id: int
    exercise: PronunciationExerciseResponse
    created_at: datetime

    class Config:
        from_attributes = True

# Speaking Progress Schemas
class SpeakingProgressBase(BaseModel):
    current_level: DifficultyLevel
    total_speaking_time: int = Field(0, ge=0)
    total_attempts: int = Field(0, ge=0)
    total_prompts_completed: int = Field(0, ge=0)
    average_pronunciation_score: float = Field(0.0, ge=0.0, le=100.0)
    average_fluency_score: float = Field(0.0, ge=0.0, le=100.0)
    average_accuracy_score: float = Field(0.0, ge=0.0, le=100.0)
    phoneme_progress: Optional[Dict[str, float]] = None
    stress_pattern_progress: float = Field(0.0, ge=0.0, le=100.0)
    intonation_progress: float = Field(0.0, ge=0.0, le=100.0)
    fluency_progress: float = Field(0.0, ge=0.0, le=100.0)
    exercise_type_performance: Optional[Dict[str, float]] = None
    current_streak_days: int = Field(0, ge=0)
    longest_streak_days: int = Field(0, ge=0)
    daily_goal_minutes: int = Field(15, gt=0)
    weekly_goal_attempts: int = Field(10, gt=0)

class SpeakingProgressCreate(BaseModel):
    current_level: DifficultyLevel

class SpeakingProgressUpdate(BaseModel):
    current_level: Optional[DifficultyLevel] = None
    daily_goal_minutes: Optional[int] = Field(None, gt=0)
    weekly_goal_attempts: Optional[int] = Field(None, gt=0)

class SpeakingProgressResponse(SpeakingProgressBase):
    id: int
    user_id: int
    pronunciation_trends: Optional[Dict[str, Any]] = None
    weak_areas: Optional[List[str]] = None
    strong_areas: Optional[List[str]] = None
    last_activity_date: Optional[datetime] = None
    last_level_up_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Speaking Session Schemas
class SpeakingSessionBase(BaseModel):
    session_type: str = Field(..., max_length=50)
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    prompts_attempted: int = Field(0, ge=0)
    total_speaking_time: int = Field(0, ge=0)
    average_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    best_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    session_goals: Optional[List[str]] = None
    goals_achieved: Optional[List[str]] = None

class SpeakingSessionCreate(BaseModel):
    session_type: str = Field(..., max_length=50)
    session_goals: Optional[List[str]] = None

class SpeakingSessionUpdate(BaseModel):
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    prompts_attempted: Optional[int] = Field(None, ge=0)
    total_speaking_time: Optional[int] = Field(None, ge=0)
    average_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    best_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    goals_achieved: Optional[List[str]] = None

class SpeakingSessionResponse(SpeakingSessionBase):
    id: int
    user_id: int
    improvement_from_last: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Voice Profile Schemas
class VoiceProfileBase(BaseModel):
    fundamental_frequency: Optional[float] = None
    speech_rate: Optional[float] = None
    voice_quality_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    detected_accent: Optional[str] = Field(None, max_length=50)
    pronunciation_patterns: Optional[Dict[str, Any]] = None
    preferred_microphone_settings: Optional[Dict[str, Any]] = None
    noise_threshold: Optional[float] = None
    calibration_completed: bool = False
    calibration_samples: Optional[List[str]] = None

class VoiceProfileCreate(VoiceProfileBase):
    pass

class VoiceProfileUpdate(BaseModel):
    fundamental_frequency: Optional[float] = None
    speech_rate: Optional[float] = None
    voice_quality_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    detected_accent: Optional[str] = Field(None, max_length=50)
    pronunciation_patterns: Optional[Dict[str, Any]] = None
    preferred_microphone_settings: Optional[Dict[str, Any]] = None
    noise_threshold: Optional[float] = None
    calibration_completed: Optional[bool] = None
    calibration_samples: Optional[List[str]] = None

class VoiceProfileResponse(VoiceProfileBase):
    id: int
    user_id: int
    calibration_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Audio Recording Schemas
class AudioRecordingStart(BaseModel):
    prompt_id: Optional[int] = None
    exercise_id: Optional[int] = None
    session_id: Optional[str] = None
    recording_type: str = Field(..., max_length=50)  # prompt, exercise, calibration

class AudioRecordingStop(BaseModel):
    recording_id: str
    audio_url: str = Field(..., max_length=500)
    duration_seconds: float = Field(..., gt=0)

class AudioRecordingResponse(BaseModel):
    recording_id: str
    status: str
    message: str
    audio_url: Optional[str] = None

# Speech Assessment Schemas
class SpeechAssessmentRequest(BaseModel):
    audio_url: str = Field(..., max_length=500)
    prompt_text: Optional[str] = None
    target_phonemes: Optional[List[str]] = None
    assessment_type: str = Field(..., max_length=50)  # pronunciation, fluency, comprehensive
    # From the goal's exam. This endpoint is currently unused (the live
    # speaking path is /speech/evaluate, already dialect-aware), but the
    # hard-coded en-US below was a latent trap, so language is a field here
    # and routed through profile_for rather than pinned in code.
    language: str = "en"

class SpeechAssessmentResponse(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=100.0)
    pronunciation_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    fluency_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    accuracy_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    transcribed_text: Optional[str] = None
    phoneme_scores: Optional[Dict[str, float]] = None
    word_scores: Optional[Dict[str, float]] = None
    feedback: Optional[str] = None
    suggestions: Optional[List[str]] = None
    confidence: float = Field(..., ge=0.0, le=1.0)

# Analytics and Dashboard Schemas
class SpeakingAnalytics(BaseModel):
    total_speaking_time: int
    prompts_completed: int
    average_pronunciation_score: float
    average_fluency_score: float
    improvement_rate: float
    streak_days: int
    favorite_exercise_types: List[str]
    performance_by_level: Dict[str, float]
    phoneme_accuracy: Dict[str, float]
    recent_activity: List[Dict[str, Any]]

class SpeakingDashboard(BaseModel):
    user_progress: SpeakingProgressResponse
    recent_attempts: List[SpeakingAttemptResponse]
    recommended_prompts: List[SpeakingPromptResponse]
    analytics: SpeakingAnalytics
    daily_goal_progress: Dict[str, Any]
    voice_profile: Optional[VoiceProfileResponse]
    achievements: List[Dict[str, Any]]

# Audio Conversation Schemas (Gemini Flash-Lite)
class AudioConversationRequest(BaseModel):
    audio_data: bytes
    conversation_context: str = Field(..., max_length=200)
    exercise_type: Optional[str] = Field(None, max_length=50)
    prompt_text: Optional[str] = None

class PronunciationAnalysis(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=100.0)
    fluency_score: float = Field(..., ge=0.0, le=100.0)
    pronunciation_score: float = Field(..., ge=0.0, le=100.0)
    word_count: int
    avg_word_length: float
    audio_features: Dict[str, Any]
    feedback: str

class ExerciseAnalysis(BaseModel):
    completeness_score: float = Field(..., ge=0.0, le=100.0)
    relevance_score: float = Field(..., ge=0.0, le=100.0)
    exercise_specific_feedback: str
    improvement_suggestions: List[str]

class AudioConversationResponse(BaseModel):
    success: bool
    transcription: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    ai_response: str
    response_type: str
    follow_up_questions: List[str] = []
    pronunciation_analysis: PronunciationAnalysis
    exercise_analysis: Optional[ExerciseAnalysis] = None
    conversation_context: str
    exercise_type: Optional[str] = None
    prompt_text: Optional[str] = None
    metadata: Dict[str, Any]
    error: Optional[str] = None

# Statistics Schemas
class SpeakingStatistics(BaseModel):
    user_id: int
    total_time_minutes: int
    prompts_completed: int
    average_pronunciation_score: float
    average_fluency_score: float
    best_pronunciation_score: float
    current_streak: int
    level_distribution: Dict[str, int]
    exercise_type_performance: Dict[str, float]
    monthly_progress: Dict[str, Dict[str, Any]]
    phoneme_strengths: List[str]
    phoneme_weaknesses: List[str]

# Real-time Feedback Schemas
class RealTimeFeedback(BaseModel):
    timestamp: float
    feedback_type: str  # pronunciation, pace, volume
    message: str
    severity: str  # info, warning, error
    suggestions: Optional[List[str]] = None

class LiveAssessmentUpdate(BaseModel):
    session_id: str
    current_score: float
    real_time_feedback: List[RealTimeFeedback]
    transcription_progress: Optional[str] = None 