from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

from app.models.content import DifficultyLevel

class MobileSessionStart(BaseModel):
    """Mobile session start request"""
    context: str = Field(..., description="Conversation context (daily_life, business, etc.)")
    mode: str = Field(default="practice", description="Session mode (practice, assessment, etc.)")
    difficulty_level: Optional[str] = Field(None, description="Override user's difficulty level")
    topic: Optional[str] = Field(None, description="Specific topic within context")
    estimated_duration: Optional[int] = Field(15, description="Estimated session duration in minutes")
    enable_auto_feedback: bool = Field(True, description="Enable automatic AI feedback")
    pronunciation_focus: Optional[List[str]] = Field(None, description="Pronunciation aspects to focus on")
    real_time_corrections: bool = Field(True, description="Enable real-time corrections")

class MobileSessionResponse(BaseModel):
    """Mobile session start response"""
    session_id: str
    initial_message: str
    conversation_starters: List[str]
    user_level: str
    estimated_duration: int
    offline_content: Dict[str, Any]
    session_config: Dict[str, Any]

class MobileAudioUpload(BaseModel):
    """Mobile audio upload data"""
    session_id: str
    expected_text: Optional[str] = None
    analysis_type: str = Field(default="quick", description="quick or comprehensive")
    format: str = Field(default="webm", description="Audio format")
    duration_seconds: Optional[float] = None

class MobileAudioResponse(BaseModel):
    """Mobile audio processing response"""
    transcript: str
    confidence: float
    pronunciation_analysis: Optional[Dict[str, Any]] = None
    processing_type: str
    detailed_analysis_pending: bool
    suggestions: Optional[List[str]] = None
    scores: Optional[Dict[str, float]] = None

class MobileWritingSubmission(BaseModel):
    """Mobile writing submission"""
    text: str = Field(..., min_length=10, max_length=10000)
    writing_type: str = Field(default="essay", description="Type of writing")
    session_id: Optional[str] = None
    prompt: Optional[str] = None
    target_word_count: Optional[int] = None
    focus_areas: Optional[List[str]] = None

    @validator('text')
    def validate_text(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()

class MobileWritingResponse(BaseModel):
    """Mobile writing analysis response"""
    analysis_id: str
    quick_feedback: Dict[str, Any]
    comprehensive_analysis_pending: bool
    estimated_completion_seconds: int
    suggestions: Optional[List[str]] = None

class MobileOfflineSession(BaseModel):
    """Offline session data for sync"""
    session_id: str
    context: str
    mode: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    messages: List[Dict[str, Any]]
    user_rating: Optional[int] = None
    duration_minutes: Optional[int] = None

class MobileExerciseCompletion(BaseModel):
    """Exercise completion data for sync"""
    exercise_id: str
    exercise_type: str
    completed_at: datetime
    score: float
    time_taken_seconds: int
    user_answer: Dict[str, Any]
    is_correct: bool

class MobileProgressSync(BaseModel):
    """Mobile progress synchronization data"""
    last_sync_timestamp: Optional[str] = None
    offline_sessions: List[MobileOfflineSession] = []
    exercise_completions: List[MobileExerciseCompletion] = []
    study_time_minutes: int = 0
    device_info: Optional[Dict[str, str]] = None

class MobileProgressResponse(BaseModel):
    """Mobile progress sync response"""
    sync_successful: bool
    synced_activities: int
    conflicts_resolved: int
    server_updates: List[Dict[str, Any]]
    next_sync_recommended: datetime

class MobileContentRequest(BaseModel):
    """Mobile offline content request"""
    max_conversations: int = Field(default=10, ge=1, le=50)
    max_exercises: int = Field(default=25, ge=1, le=100)
    max_vocabulary_items: int = Field(default=100, ge=1, le=500)
    max_ai_responses: int = Field(default=20, ge=1, le=100)
    include_audio: bool = Field(default=True)
    content_types: Optional[List[str]] = None
    difficulty_levels: Optional[List[str]] = None

class MobileOfflineData(BaseModel):
    """Offline content package data"""
    conversations: List[Dict[str, Any]]
    exercises: List[Dict[str, Any]]
    vocabulary: List[Dict[str, Any]]
    audio_samples: List[Dict[str, Any]]
    ai_responses: List[Dict[str, Any]]

class MobileOfflineResponse(BaseModel):
    """Mobile offline content response"""
    content_package: MobileOfflineData
    package_size_mb: float
    expires_at: datetime
    sync_required_by: datetime

class MobileContentResponse(BaseModel):
    """Mobile content response"""
    content_type: str
    content_data: Dict[str, Any]
    difficulty_level: str
    estimated_duration: int
    metadata: Optional[Dict[str, Any]] = None
    offline_available: bool = False

class MobilePracticeSession(BaseModel):
    """Quick mobile practice session"""
    type: str = Field(..., description="vocabulary, pronunciation, grammar, etc.")
    content: str = Field(..., description="Practice content")
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio for pronunciation")
    expected_response: Optional[str] = None
    difficulty: Optional[str] = None

class MobilePracticeResponse(BaseModel):
    """Mobile practice session response"""
    practice_type: str
    feedback: str
    score: int
    suggestions: List[str]
    next_practice_suggestion: Optional[str] = None

class MobileQuickFeedback(BaseModel):
    """Quick feedback request"""
    type: str = Field(..., description="text, pronunciation, grammar")
    content: str = Field(..., description="Content to analyze")
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio")
    context: Optional[str] = Field(None, description="Context for better feedback")

class MobileQuickFeedbackResponse(BaseModel):
    """Quick feedback response"""
    feedback_message: str
    score: int
    quick_tips: List[str]
    encouragement: str
    response_time_ms: int

class MobileNotificationSettings(BaseModel):
    """Mobile notification settings"""
    push_notifications_enabled: bool = True
    daily_reminders_enabled: bool = True
    reminder_time: str = Field(default="18:00", description="Time in HH:MM format")
    achievement_notifications: bool = True
    progress_notifications: bool = True
    conversation_reminders: bool = True
    study_streak_reminders: bool = True
    notification_sound: Optional[str] = None
    quiet_hours_start: Optional[str] = Field(None, description="Quiet hours start time")
    quiet_hours_end: Optional[str] = Field(None, description="Quiet hours end time")

    @validator('reminder_time', 'quiet_hours_start', 'quiet_hours_end')
    def validate_time_format(cls, v):
        if v is None:
            return v
        try:
            hours, minutes = v.split(':')
            if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
                raise ValueError('Invalid time format')
            return v
        except (ValueError, AttributeError):
            raise ValueError('Time must be in HH:MM format')

class MobileNotificationResponse(BaseModel):
    """Mobile notification settings response"""
    settings_updated: bool
    daily_reminders_scheduled: bool
    push_notifications_enabled: bool
    next_reminder: Optional[datetime] = None

class MobileTaskStatus(BaseModel):
    """Background task status for mobile"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress_percentage: Optional[int] = None
    estimated_completion: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class MobileTaskStatusResponse(BaseModel):
    """Mobile task status response"""
    task: MobileTaskStatus
    can_retry: bool
    retry_after_seconds: Optional[int] = None

class MobileBatchRequest(BaseModel):
    """Batch request for multiple operations"""
    operations: List[Dict[str, Any]] = Field(..., max_items=10)
    batch_id: Optional[str] = None
    priority: str = Field(default="normal", description="low, normal, high")

class MobileBatchResponse(BaseModel):
    """Batch operation response"""
    batch_id: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    results: List[Dict[str, Any]]
    processing_time_ms: int

class MobileDeviceInfo(BaseModel):
    """Mobile device information"""
    platform: str = Field(..., description="iOS, Android")
    version: str = Field(..., description="OS version")
    app_version: str = Field(..., description="App version")
    device_model: Optional[str] = None
    screen_size: Optional[str] = None
    language: str = Field(default="en", description="Device language")
    timezone: Optional[str] = None
    connection_type: Optional[str] = Field(None, description="wifi, cellular, etc.")

class MobileAnalytics(BaseModel):
    """Mobile analytics data"""
    session_duration: int = Field(..., description="Session duration in seconds")
    features_used: List[str] = []
    errors_encountered: List[Dict[str, str]] = []
    performance_metrics: Optional[Dict[str, float]] = None
    user_interactions: List[Dict[str, Any]] = []
    offline_time: Optional[int] = Field(None, description="Time spent offline in seconds")

class MobileAnalyticsResponse(BaseModel):
    """Mobile analytics submission response"""
    analytics_recorded: bool
    insights: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None

class MobileConfigRequest(BaseModel):
    """Mobile app configuration request"""
    app_version: str
    platform: str
    user_tier: Optional[str] = "free"

class MobileConfigResponse(BaseModel):
    """Mobile app configuration response"""
    features_enabled: Dict[str, bool]
    rate_limits: Dict[str, int]
    cache_settings: Dict[str, Any]
    ui_config: Dict[str, Any]
    api_endpoints: Dict[str, str]
    update_required: bool
    min_supported_version: str

class MobileErrorReport(BaseModel):
    """Mobile error report"""
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    user_action: str
    timestamp: datetime
    device_info: MobileDeviceInfo
    app_state: Optional[Dict[str, Any]] = None

class MobileErrorResponse(BaseModel):
    """Mobile error report response"""
    error_recorded: bool
    ticket_id: Optional[str] = None
    suggested_solution: Optional[str] = None
    should_retry: bool
    contact_support: bool

# Specialized mobile responses for different content types
class MobileVocabularyResponse(BaseModel):
    """Mobile vocabulary practice response"""
    word: str
    definition: str
    pronunciation: Optional[str] = None
    example_sentences: List[str]
    difficulty_level: str
    audio_url: Optional[str] = None
    related_words: List[str] = []
    practice_exercises: List[Dict[str, Any]] = []

class MobileGrammarResponse(BaseModel):
    """Mobile grammar practice response"""
    rule_title: str
    explanation: str
    examples: List[str]
    common_mistakes: List[str]
    practice_exercises: List[Dict[str, Any]]
    difficulty_level: str
    related_topics: List[str] = []

class MobilePronunciationResponse(BaseModel):
    """Mobile pronunciation practice response"""
    target_word: str
    phonetic_transcription: str
    audio_reference: Optional[str] = None
    pronunciation_tips: List[str]
    common_errors: List[str]
    practice_sentences: List[str]
    difficulty_level: str
    focus_sounds: List[str] = []

# Mobile-specific conversation models
class MobileConversationMessage(BaseModel):
    """Mobile conversation message"""
    id: str
    content: str
    is_from_user: bool
    timestamp: datetime
    message_type: str  # text, audio, image
    metadata: Optional[Dict[str, Any]] = None
    feedback: Optional[Dict[str, Any]] = None

class MobileConversationState(BaseModel):
    """Mobile conversation state"""
    session_id: str
    context: str
    current_topic: Optional[str] = None
    message_count: int
    user_engagement_level: str  # low, medium, high
    suggested_responses: List[str] = []
    conversation_flow: str  # structured, free_form
    difficulty_adjustment: Optional[str] = None

class MobileConversationResponse(BaseModel):
    """Mobile conversation response"""
    message: MobileConversationMessage
    conversation_state: MobileConversationState
    ai_feedback: Optional[Dict[str, Any]] = None
    next_suggestions: List[str] = []
