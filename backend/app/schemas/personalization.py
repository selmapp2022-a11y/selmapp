from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Import enums from models
from app.models.personalization import (
    LearningStyle, PersonalityType, RecommendationType, 
    TrainerInteractionType, LearningGoalType, LearningCategory, OnboardingStep
)

# Base Schemas
class PersonalizationBase(BaseModel):
    class Config:
        from_attributes = True

# User Learning Profile Schemas
class UserLearningProfileBase(BaseModel):
    learning_style: LearningStyle = LearningStyle.MIXED
    personality_type: PersonalityType = PersonalityType.INDEPENDENT
    preferred_session_duration: int = Field(30, ge=5, le=180)
    preferred_difficulty_progression: float = Field(0.1, ge=0.0, le=1.0)
    primary_goal: LearningGoalType
    secondary_goals: List[LearningGoalType] = []
    target_cefr_level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$")
    target_completion_date: Optional[datetime] = None
    listening_weight: float = Field(0.25, ge=0.0, le=1.0)
    speaking_weight: float = Field(0.25, ge=0.0, le=1.0)
    reading_weight: float = Field(0.25, ge=0.0, le=1.0)
    writing_weight: float = Field(0.25, ge=0.0, le=1.0)
    optimal_study_times: List[str] = []
    preferred_content_types: List[str] = []
    motivation_triggers: List[str] = []
    challenge_preference: float = Field(0.5, ge=0.0, le=1.0)

    @validator('listening_weight', 'speaking_weight', 'reading_weight', 'writing_weight')
    def validate_weights(cls, v, values):
        # Ensure weights sum to 1.0 (will be validated in API)
        return v

class UserLearningProfileCreate(UserLearningProfileBase):
    user_id: int

class UserLearningProfileUpdate(BaseModel):
    learning_style: Optional[LearningStyle] = None
    personality_type: Optional[PersonalityType] = None
    preferred_session_duration: Optional[int] = Field(None, ge=5, le=180)
    preferred_difficulty_progression: Optional[float] = Field(None, ge=0.0, le=1.0)
    primary_goal: Optional[LearningGoalType] = None
    secondary_goals: Optional[List[LearningGoalType]] = None
    target_cefr_level: Optional[str] = Field(None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    target_completion_date: Optional[datetime] = None
    listening_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    speaking_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    reading_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    writing_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    optimal_study_times: Optional[List[str]] = None
    preferred_content_types: Optional[List[str]] = None
    motivation_triggers: Optional[List[str]] = None
    challenge_preference: Optional[float] = Field(None, ge=0.0, le=1.0)

class UserLearningProfile(UserLearningProfileBase):
    id: int
    user_id: int
    learning_rate: float
    retention_rate: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Personalized Learning Path Schemas
class LearningPathMilestoneBase(BaseModel):
    step_number: int
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    skill_focus: str = Field(..., max_length=50)
    required_activities: List[Dict[str, Any]]
    mastery_threshold: float = Field(0.8, ge=0.0, le=1.0)

class LearningPathMilestoneCreate(LearningPathMilestoneBase):
    learning_path_id: int

class LearningPathMilestone(LearningPathMilestoneBase):
    id: int
    learning_path_id: int
    is_completed: bool
    completion_date: Optional[datetime]
    performance_score: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PersonalizedLearningPathBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    estimated_duration_weeks: int = Field(..., ge=1)
    total_steps: int = Field(..., ge=1)
    path_data: Dict[str, Any]

class PersonalizedLearningPathCreate(PersonalizedLearningPathBase):
    user_profile_id: int

class PersonalizedLearningPathUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    current_step: Optional[int] = Field(None, ge=0)
    path_data: Optional[Dict[str, Any]] = None
    adaptive_adjustments: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class PersonalizedLearningPath(PersonalizedLearningPathBase):
    id: int
    user_profile_id: int
    current_step: int
    completion_percentage: float
    is_active: bool
    is_completed: bool
    average_performance: float
    predicted_completion_date: Optional[datetime]
    last_activity_date: Optional[datetime]
    adaptive_adjustments: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    milestones: List[LearningPathMilestone] = []

    class Config:
        from_attributes = True

# Content Recommendation Schemas
class ContentRecommendationBase(BaseModel):
    recommendation_type: RecommendationType
    title: str = Field(..., max_length=200)
    description: Optional[str] = None
    content_type: str = Field(..., max_length=50)
    content_id: Optional[int] = None
    content_metadata: Dict[str, Any] = {}
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    priority_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    expected_benefit: Optional[str] = None
    estimated_time_minutes: Optional[int] = Field(None, ge=1)
    expires_at: Optional[datetime] = None

class ContentRecommendationCreate(ContentRecommendationBase):
    user_profile_id: int

class ContentRecommendationUpdate(BaseModel):
    is_accepted: Optional[bool] = None
    is_completed: Optional[bool] = None
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    user_feedback: Optional[str] = None

class ContentRecommendation(ContentRecommendationBase):
    id: int
    user_profile_id: int
    is_active: bool
    is_accepted: Optional[bool]
    is_completed: bool
    user_rating: Optional[int]
    user_feedback: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Personal Trainer Interaction Schemas
class PersonalTrainerInteractionBase(BaseModel):
    interaction_type: TrainerInteractionType
    trigger_event: Optional[str] = Field(None, max_length=100)
    trainer_message: str
    context_data: Dict[str, Any] = {}
    tone: str = Field("encouraging", max_length=50)
    formality_level: str = Field("casual", max_length=20)
    session_id: Optional[str] = Field(None, max_length=100)
    is_proactive: bool = False

class PersonalTrainerInteractionCreate(PersonalTrainerInteractionBase):
    user_profile_id: int

class PersonalTrainerInteractionUpdate(BaseModel):
    user_response: Optional[str] = None
    user_engagement_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    interaction_effectiveness: Optional[float] = Field(None, ge=0.0, le=1.0)
    responded_at: Optional[datetime] = None

class PersonalTrainerInteraction(PersonalTrainerInteractionBase):
    id: int
    user_profile_id: int
    user_response: Optional[str]
    user_engagement_score: Optional[float]
    interaction_effectiveness: Optional[float]
    created_at: datetime
    responded_at: Optional[datetime]

    class Config:
        from_attributes = True

# Learning Analytics Schemas
class LearningAnalyticsBase(BaseModel):
    date: datetime
    period_type: str = Field(..., max_length=20)
    study_time_minutes: int = Field(0, ge=0)
    activities_completed: int = Field(0, ge=0)
    exercises_completed: int = Field(0, ge=0)
    average_accuracy: float = Field(0.0, ge=0.0, le=1.0)
    improvement_rate: float = Field(0.0, ge=-1.0, le=1.0)
    consistency_score: float = Field(0.0, ge=0.0, le=1.0)
    listening_score: float = Field(0.0, ge=0.0, le=1.0)
    speaking_score: float = Field(0.0, ge=0.0, le=1.0)
    reading_score: float = Field(0.0, ge=0.0, le=1.0)
    writing_score: float = Field(0.0, ge=0.0, le=1.0)
    session_count: int = Field(0, ge=0)
    streak_days: int = Field(0, ge=0)
    motivation_level: float = Field(0.5, ge=0.0, le=1.0)
    analytics_data: Dict[str, Any] = {}

class LearningAnalyticsCreate(LearningAnalyticsBase):
    user_profile_id: int

class LearningAnalytics(LearningAnalyticsBase):
    id: int
    user_profile_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Adaptive Learning Rule Schemas
class AdaptiveLearningRuleBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    rule_type: str = Field(..., max_length=50)
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    priority: int = Field(0, ge=0)
    is_active: bool = True

class AdaptiveLearningRuleCreate(AdaptiveLearningRuleBase):
    pass

class AdaptiveLearningRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    actions: Optional[Dict[str, Any]] = None
    priority: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class AdaptiveLearningRule(AdaptiveLearningRuleBase):
    id: int
    trigger_count: int
    success_rate: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Special Response Schemas
class LearningPathRecommendation(BaseModel):
    recommended_path: PersonalizedLearningPath
    reasoning: str
    confidence_score: float
    estimated_completion_weeks: int
    key_milestones: List[str]

class PersonalTrainerResponse(BaseModel):
    message: str
    interaction_type: TrainerInteractionType
    context: Dict[str, Any]
    suggested_actions: List[str] = []
    follow_up_questions: List[str] = []

class LearningInsights(BaseModel):
    user_profile_id: int
    current_level: str
    progress_summary: Dict[str, Any]
    strengths: List[str]
    areas_for_improvement: List[str]
    recommendations: List[ContentRecommendation]
    motivation_tips: List[str]
    next_milestones: List[LearningPathMilestone]

class AdaptiveAdjustment(BaseModel):
    adjustment_type: str
    old_value: Union[str, int, float]
    new_value: Union[str, int, float]
    reasoning: str
    confidence: float

class PersonalizationDashboard(BaseModel):
    user_profile: UserLearningProfile
    active_learning_path: Optional[PersonalizedLearningPath]
    recent_recommendations: List[ContentRecommendation]
    recent_trainer_interactions: List[PersonalTrainerInteraction]
    learning_analytics: List[LearningAnalytics]
    insights: LearningInsights
    adaptive_adjustments: List[AdaptiveAdjustment]

# API Request/Response Schemas
class ChatWithTrainerRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = {}

class ChatWithTrainerResponse(BaseModel):
    trainer_response: PersonalTrainerResponse
    interaction_id: int
    suggestions: List[str] = []

class GenerateLearningPathRequest(BaseModel):
    user_goals: List[LearningGoalType]
    target_level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$")
    available_time_per_week: int = Field(..., ge=1, le=50)
    preferred_focus_areas: List[str] = []

class UpdateLearningProgressRequest(BaseModel):
    activity_type: str
    performance_score: float = Field(..., ge=0.0, le=1.0)
    time_spent_minutes: int = Field(..., ge=1)
    difficulty_level: str
    user_feedback: Optional[str] = None

# Onboarding Schemas
class UserOnboardingBase(BaseModel):
    current_step: Optional[OnboardingStep] = OnboardingStep.WELCOME
    assessed_level: Optional[str] = None
    selected_categories: List[str] = []
    primary_category: Optional[LearningCategory] = None
    learning_goals: List[str] = []
    motivation_factors: List[str] = []
    target_timeline: Optional[str] = Field(None, pattern="^(1_month|3_months|6_months|1_year|flexible)$")
    daily_study_commitment: Optional[int] = Field(None, ge=5, le=180)  # 5 minutes to 3 hours
    preferred_learning_style: Optional[LearningStyle] = None
    preferred_difficulty: str = Field("gradual", pattern="^(gradual|moderate|challenging)$")
    preferred_content_types: List[str] = []

class UserOnboardingCreate(UserOnboardingBase):
    user_id: int

class UserOnboardingUpdate(BaseModel):
    current_step: Optional[OnboardingStep] = None
    assessed_level: Optional[str] = None
    selected_categories: Optional[List[str]] = None
    primary_category: Optional[LearningCategory] = None
    learning_goals: Optional[List[str]] = None
    motivation_factors: Optional[List[str]] = None
    target_timeline: Optional[str] = Field(None, pattern="^(1_month|3_months|6_months|1_year|flexible)$")
    daily_study_commitment: Optional[int] = Field(None, ge=5, le=180)
    preferred_learning_style: Optional[LearningStyle] = None
    preferred_difficulty: Optional[str] = Field(None, pattern="^(gradual|moderate|challenging)$")
    preferred_content_types: Optional[List[str]] = None
    is_completed: Optional[bool] = None
    completion_percentage: Optional[float] = None
    assessment_score: Optional[float] = None
    assessment_details: Optional[Dict[str, Any]] = None
    category_priorities: Optional[Dict[str, int]] = None
    onboarding_feedback: Optional[str] = None
    onboarding_rating: Optional[int] = Field(None, ge=1, le=5)

class UserOnboarding(UserOnboardingBase):
    id: int
    user_id: int
    is_completed: bool = False
    completion_percentage: float = 0.0
    assessment_score: Optional[float] = None
    assessment_details: Optional[Dict[str, Any]] = None
    category_priorities: Optional[Dict[str, int]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_step_completed_at: Optional[datetime] = None
    onboarding_feedback: Optional[str] = None
    onboarding_rating: Optional[int] = None

    class Config:
        from_attributes = True

# Category Learning Template Schemas
class CategoryLearningTemplateBase(BaseModel):
    category: LearningCategory
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    target_levels: List[str] = Field(..., min_items=1)
    template_data: Dict[str, Any] = {}
    estimated_duration_weeks: int = Field(..., ge=1, le=52)
    total_milestones: int = Field(..., ge=1, le=50)
    listening_percentage: Optional[float] = Field(None, ge=0, le=100)
    speaking_percentage: Optional[float] = Field(None, ge=0, le=100)
    reading_percentage: Optional[float] = Field(None, ge=0, le=100)
    writing_percentage: Optional[float] = Field(None, ge=0, le=100)
    required_vocabulary_topics: Optional[List[str]] = []
    required_grammar_points: Optional[List[str]] = []
    recommended_content_types: Optional[List[str]] = []
    difficulty_level: str = Field("moderate", pattern="^(easy|moderate|challenging)$")
    is_active: bool = True

    @validator('listening_percentage', 'speaking_percentage', 'reading_percentage', 'writing_percentage')
    def validate_skill_percentages(cls, v, values):
        # Ensure percentages sum to 100 (will be validated in API)
        return v

class CategoryLearningTemplateCreate(CategoryLearningTemplateBase):
    created_by: Optional[str] = None

class CategoryLearningTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    target_levels: Optional[List[str]] = None
    template_data: Optional[Dict[str, Any]] = None
    estimated_duration_weeks: Optional[int] = Field(None, ge=1, le=52)
    total_milestones: Optional[int] = Field(None, ge=1, le=50)
    listening_percentage: Optional[float] = Field(None, ge=0, le=100)
    speaking_percentage: Optional[float] = Field(None, ge=0, le=100)
    reading_percentage: Optional[float] = Field(None, ge=0, le=100)
    writing_percentage: Optional[float] = Field(None, ge=0, le=100)
    required_vocabulary_topics: Optional[List[str]] = None
    required_grammar_points: Optional[List[str]] = None
    recommended_content_types: Optional[List[str]] = None
    difficulty_level: Optional[str] = Field(None, pattern="^(easy|moderate|challenging)$")
    is_active: Optional[bool] = None

class CategoryLearningTemplate(CategoryLearningTemplateBase):
    id: int
    created_by: Optional[str] = None
    usage_count: int = 0
    average_completion_rate: Optional[float] = None
    average_satisfaction_rating: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# User Category Preference Schemas
class UserCategoryPreferenceBase(BaseModel):
    category: LearningCategory
    priority_level: int = Field(3, ge=1, le=5)  # 1=highest, 5=lowest
    interest_score: float = Field(0.5, ge=0.0, le=1.0)
    preferred_focus_areas: Optional[List[str]] = []
    preferred_content_difficulty: str = Field("moderate", pattern="^(easy|moderate|challenging)$")
    preferred_session_duration: Optional[int] = Field(None, ge=5, le=120)  # minutes

class UserCategoryPreferenceCreate(UserCategoryPreferenceBase):
    user_id: int

class UserCategoryPreferenceUpdate(BaseModel):
    priority_level: Optional[int] = Field(None, ge=1, le=5)
    interest_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    preferred_focus_areas: Optional[List[str]] = None
    preferred_content_difficulty: Optional[str] = Field(None, pattern="^(easy|moderate|challenging)$")
    preferred_session_duration: Optional[int] = Field(None, ge=5, le=120)
    satisfaction_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    feedback_notes: Optional[str] = None

class UserCategoryPreference(UserCategoryPreferenceBase):
    id: int
    user_id: int
    time_spent_minutes: int = 0
    activities_completed: int = 0
    average_performance: Optional[float] = None
    satisfaction_rating: Optional[float] = None
    feedback_notes: Optional[str] = None
    is_active: bool = True
    last_activity_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Onboarding Flow Schemas
class OnboardingStepRequest(BaseModel):
    step: OnboardingStep
    data: Optional[Dict[str, Any]] = {}

class OnboardingStepResponse(BaseModel):
    current_step: OnboardingStep
    completion_percentage: float
    next_step: Optional[OnboardingStep] = None
    step_data: Optional[Dict[str, Any]] = {}
    message: str

class CategorySelectionRequest(BaseModel):
    selected_categories: List[str] = Field(..., min_items=1, max_items=5)
    primary_category: str
    category_priorities: Dict[str, int] = {}
    learning_goals: List[str] = []
    target_timeline: str = Field(..., pattern="^(1_month|3_months|6_months|1_year|flexible)$")
    daily_study_commitment: int = Field(..., ge=5, le=180)

class LevelAssessmentRequest(BaseModel):
    assessment_answers: Dict[str, Any]
    self_reported_level: Optional[str] = Field(None, pattern="^(A1|A2|B1|B2|C1|C2)$")
    previous_experience: Optional[str] = None

class LevelAssessmentResult(BaseModel):
    assessed_level: str
    confidence_score: float
    assessment_score: float
    skill_breakdown: Dict[str, float]
    recommendations: List[str]
    next_steps: List[str]

class GeneratedLearningPath(BaseModel):
    learning_path: PersonalizedLearningPath
    category_templates_used: List[CategoryLearningTemplate]
    customizations_applied: List[str]
    estimated_completion_date: datetime
    key_milestones: List[str]
    initial_recommendations: List[ContentRecommendation]

class OnboardingCompletionSummary(BaseModel):
    user_profile: UserLearningProfile
    onboarding_data: UserOnboarding
    generated_learning_path: PersonalizedLearningPath
    category_preferences: List[UserCategoryPreference]
    initial_recommendations: List[ContentRecommendation]
    next_actions: List[str]
    welcome_message: str

# Learning Journey Request Schema
class LearningJourneyRequest(BaseModel):
    """Request model for creating a personalized learning journey using assessment data"""
    user_level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$", description="Current CEFR level")
    preferred_categories: List[str] = Field(..., description="List of preferred learning category IDs")
    learning_pace: str = Field(..., pattern="^(relaxed|steady|intensive)$", description="Learning pace preference")
    daily_study_time_minutes: int = Field(..., ge=5, le=180, description="Daily study time commitment in minutes")
    assessment_results: Optional[Dict[str, Any]] = Field(None, description="Assessment results JSON")
    journey_duration_days: int = Field(30, ge=7, le=1000, description="Duration of learning journey in days")

    class Config:
        json_schema_extra = {
            "example": {
                "user_level": "B1",
                "preferred_categories": ["daily_life", "travel", "business"],
                "learning_pace": "steady",
                "daily_study_time_minutes": 25,
                "assessment_results": {
                    "determined_level": "B1",
                    "skill_scores": {"grammar": 0.75, "vocabulary": 0.8},
                    "overall_score": 78.5
                },
                "journey_duration_days": 60
            }
        } 

# Learning Session Schemas
class LearningSessionRequest(BaseModel):
    module_id: str
    day_number: Optional[int] = Field(1, ge=1)
    context: Dict[str, Any] = {}

class LessonStep(BaseModel):
    step_type: str = Field(
        ..., pattern="^(reading|listening|vocabulary|grammar|exercise|quiz|speaking)$"
    )
    title: str
    content: Optional[str] = None
    # Structured content payload for clients (Flutter reads this as `contentJson`)
    content_json: Optional[Dict[str, Any]] = None
    media_url: Optional[str] = None
    questions: Optional[List[Dict[str, Any]]] = None
    estimated_minutes: Optional[int] = Field(5, ge=1, le=60)

class LearningSessionResponse(BaseModel):
    session_id: str
    module_id: str
    day_number: int
    steps: List[LessonStep]
    total_estimated_minutes: int

# Learning Session Completion
class LearningSessionCompleteRequest(BaseModel):
    session_id: str
    module_id: str
    day_number: int = Field(1, ge=1)
    results: Dict[str, Any] = {}
    time_spent_minutes: int = Field(1, ge=1)

class LearningSessionCompleteResponse(BaseModel):
    module_id: str
    day_number: int
    updated_progress_percentage: float = Field(..., ge=0.0, le=100.0)
    unlocked_next_module: bool = False