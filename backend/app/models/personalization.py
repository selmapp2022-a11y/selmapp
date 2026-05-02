from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.core.database import Base

# Enums for Personalization System
class LearningStyle(str, Enum):
    VISUAL = "visual"
    AUDITORY = "auditory"
    KINESTHETIC = "kinesthetic"
    READING_WRITING = "reading_writing"
    MIXED = "mixed"

class PersonalityType(str, Enum):
    COMPETITIVE = "competitive"
    COLLABORATIVE = "collaborative"
    INDEPENDENT = "independent"
    GUIDED = "guided"

class RecommendationType(str, Enum):
    CONTENT = "content"
    EXERCISE = "exercise"
    SKILL_FOCUS = "skill_focus"
    LEARNING_PATH = "learning_path"
    PRACTICE_TIME = "practice_time"

class TrainerInteractionType(str, Enum):
    GREETING = "greeting"
    MOTIVATION = "motivation"
    FEEDBACK = "feedback"
    SUGGESTION = "suggestion"
    CORRECTION = "correction"
    ENCOURAGEMENT = "encouragement"
    CHALLENGE = "challenge"
    ASSESSMENT = "assessment"

class LearningGoalType(str, Enum):
    FLUENCY = "fluency"
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    PRONUNCIATION = "pronunciation"
    LISTENING = "listening"
    SPEAKING = "speaking"
    READING = "reading"
    WRITING = "writing"
    EXAM_PREP = "exam_prep"
    BUSINESS = "business"
    TRAVEL = "travel"
    ACADEMIC = "academic"

# Add new enums for onboarding categories
class LearningCategory(str, Enum):
    GENERAL_ENGLISH = "general_english"
    BUSINESS_ENGLISH = "business_english"
    TRAVEL_ENGLISH = "travel_english"
    ACADEMIC_ENGLISH = "academic_english"
    EXAM_PREPARATION = "exam_preparation"
    CONVERSATION_PRACTICE = "conversation_practice"
    GRAMMAR_FOCUS = "grammar_focus"
    VOCABULARY_BUILDING = "vocabulary_building"
    PRONUNCIATION_IMPROVEMENT = "pronunciation_improvement"
    WRITING_SKILLS = "writing_skills"
    READING_COMPREHENSION = "reading_comprehension"
    LISTENING_SKILLS = "listening_skills"

class OnboardingStep(str, Enum):
    WELCOME = "welcome"
    LEVEL_ASSESSMENT = "level_assessment"
    CATEGORY_SELECTION = "category_selection"
    GOALS_SETTING = "goals_setting"
    PREFERENCES_SETUP = "preferences_setup"
    LEARNING_PATH_GENERATION = "learning_path_generation"
    COMPLETED = "completed"

# User Learning Profile
class UserLearningProfile(Base):
    __tablename__ = "user_learning_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Learning Preferences
    learning_style = Column(
        SQLEnum(LearningStyle, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        default=LearningStyle.MIXED
    )
    personality_type = Column(
        SQLEnum(PersonalityType, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        default=PersonalityType.INDEPENDENT
    )
    preferred_session_duration = Column(Integer, default=30)  # minutes
    preferred_difficulty_progression = Column(Float, default=0.1)  # 0.1 = gradual, 0.5 = moderate, 1.0 = aggressive
    
    # Learning Goals
    primary_goal = Column(
        SQLEnum(LearningGoalType, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=False
    )
    secondary_goals = Column(JSON, default=list)  # List of LearningGoalType
    target_cefr_level = Column(String(2), nullable=False)  # A1, A2, B1, B2, C1, C2
    target_completion_date = Column(DateTime, nullable=True)
    
    # Skill Weights (how much focus on each skill)
    listening_weight = Column(Float, default=0.25)
    speaking_weight = Column(Float, default=0.25)
    reading_weight = Column(Float, default=0.25)
    writing_weight = Column(Float, default=0.25)
    
    # Learning Patterns
    optimal_study_times = Column(JSON, default=list)  # ["morning", "afternoon", "evening"]
    preferred_content_types = Column(JSON, default=list)  # Content type preferences
    motivation_triggers = Column(JSON, default=list)  # What motivates the user
    
    # Adaptive Parameters
    learning_rate = Column(Float, default=1.0)  # How fast user learns (adaptive)
    retention_rate = Column(Float, default=0.8)  # How well user retains info
    challenge_preference = Column(Float, default=0.5)  # 0=easy, 1=very challenging
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="learning_profile")
    learning_paths = relationship("PersonalizedLearningPath", back_populates="user_profile")
    recommendations = relationship("ContentRecommendation", back_populates="user_profile")
    trainer_interactions = relationship("PersonalTrainerInteraction", back_populates="user_profile")

# Personalized Learning Path
class PersonalizedLearningPath(Base):
    __tablename__ = "personalized_learning_paths"
    
    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_learning_profiles.id"), nullable=False)
    
    # Path Details
    name = Column(String(200), nullable=False)
    description = Column(Text)
    estimated_duration_weeks = Column(Integer, nullable=False)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, nullable=False)
    
    # Path Configuration
    path_data = Column(JSON, nullable=False)  # Detailed learning path structure
    adaptive_adjustments = Column(JSON, default=dict)  # Real-time adjustments
    
    # Progress Tracking
    completion_percentage = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    
    # Performance Metrics
    average_performance = Column(Float, default=0.0)
    predicted_completion_date = Column(DateTime)
    last_activity_date = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_profile = relationship("UserLearningProfile", back_populates="learning_paths")
    milestones = relationship("LearningPathMilestone", back_populates="learning_path")

# Learning Path Milestones
class LearningPathMilestone(Base):
    __tablename__ = "learning_path_milestones"
    
    id = Column(Integer, primary_key=True, index=True)
    learning_path_id = Column(Integer, ForeignKey("personalized_learning_paths.id"), nullable=False)
    
    # Milestone Details
    step_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    skill_focus = Column(String(50), nullable=False)  # listening, speaking, reading, writing
    
    # Requirements
    required_activities = Column(JSON, nullable=False)  # List of required activities
    mastery_threshold = Column(Float, default=0.8)  # Required performance level
    
    # Progress
    is_completed = Column(Boolean, default=False)
    completion_date = Column(DateTime, nullable=True)
    performance_score = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    learning_path = relationship("PersonalizedLearningPath", back_populates="milestones")

# Content Recommendations
class ContentRecommendation(Base):
    __tablename__ = "content_recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_learning_profiles.id"), nullable=False)
    
    # Recommendation Details
    recommendation_type = Column(
        SQLEnum(RecommendationType, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=False
    )
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Content References
    content_type = Column(String(50), nullable=False)  # reading, listening, speaking, writing
    content_id = Column(Integer, nullable=True)  # Reference to specific content
    content_metadata = Column(JSON, default=dict)  # Additional content info
    
    # Recommendation Scoring
    relevance_score = Column(Float, nullable=False)  # 0-1 relevance to user
    confidence_score = Column(Float, nullable=False)  # 0-1 confidence in recommendation
    priority_score = Column(Float, nullable=False)  # 0-1 priority level
    
    # Recommendation Context
    reasoning = Column(Text)  # Why this was recommended
    expected_benefit = Column(Text)  # What user will gain
    estimated_time_minutes = Column(Integer, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_accepted = Column(Boolean, nullable=True)  # User's response
    is_completed = Column(Boolean, default=False)
    
    # Feedback
    user_rating = Column(Integer, nullable=True)  # 1-5 rating
    user_feedback = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    user_profile = relationship("UserLearningProfile", back_populates="recommendations")

# Personal Trainer Interactions
class PersonalTrainerInteraction(Base):
    __tablename__ = "personal_trainer_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_learning_profiles.id"), nullable=False)
    
    # Interaction Details
    interaction_type = Column(
        SQLEnum(TrainerInteractionType, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=False
    )
    trigger_event = Column(String(100), nullable=True)  # What triggered this interaction
    
    # Content
    trainer_message = Column(Text, nullable=False)
    user_response = Column(Text, nullable=True)
    context_data = Column(JSON, default=dict)  # Additional context
    
    # Personalization
    tone = Column(String(50), default="encouraging")  # encouraging, professional, friendly, etc.
    formality_level = Column(String(20), default="casual")  # formal, casual, mixed
    
    # Interaction Metadata
    session_id = Column(String(100), nullable=True)  # For grouping related interactions
    is_proactive = Column(Boolean, default=False)  # Trainer-initiated vs user-initiated
    
    # Response Tracking
    user_engagement_score = Column(Float, nullable=True)  # How engaged was the user
    interaction_effectiveness = Column(Float, nullable=True)  # How effective was the interaction
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    responded_at = Column(DateTime, nullable=True)
    
    # Relationships
    user_profile = relationship("UserLearningProfile", back_populates="trainer_interactions")

# Learning Analytics
class LearningAnalytics(Base):
    __tablename__ = "learning_analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_learning_profiles.id"), nullable=False)
    
    # Time Period
    date = Column(DateTime, nullable=False)
    period_type = Column(String(20), nullable=False)  # daily, weekly, monthly
    
    # Learning Metrics
    study_time_minutes = Column(Integer, default=0)
    activities_completed = Column(Integer, default=0)
    exercises_completed = Column(Integer, default=0)
    
    # Performance Metrics
    average_accuracy = Column(Float, default=0.0)
    improvement_rate = Column(Float, default=0.0)
    consistency_score = Column(Float, default=0.0)
    
    # Skill-specific Metrics
    listening_score = Column(Float, default=0.0)
    speaking_score = Column(Float, default=0.0)
    reading_score = Column(Float, default=0.0)
    writing_score = Column(Float, default=0.0)
    
    # Engagement Metrics
    session_count = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    motivation_level = Column(Float, default=0.5)  # 0-1 scale
    
    # Additional Data
    analytics_data = Column(JSON, default=dict)  # Flexible analytics storage
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Adaptive Learning Rules
class AdaptiveLearningRule(Base):
    __tablename__ = "adaptive_learning_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Rule Definition
    name = Column(String(100), nullable=False)
    description = Column(Text)
    rule_type = Column(String(50), nullable=False)  # difficulty_adjustment, content_recommendation, etc.
    
    # Rule Logic
    conditions = Column(JSON, nullable=False)  # Conditions that trigger the rule
    actions = Column(JSON, nullable=False)  # Actions to take when triggered
    
    # Rule Configuration
    priority = Column(Integer, default=0)  # Higher priority rules execute first
    is_active = Column(Boolean, default=True)
    
    # Performance Tracking
    trigger_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# User Onboarding Model
class UserOnboarding(Base):
    __tablename__ = "user_onboarding"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Onboarding Progress
    current_step = Column(
        SQLEnum(OnboardingStep, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        default=OnboardingStep.WELCOME
    )
    is_completed = Column(Boolean, default=False)
    completion_percentage = Column(Float, default=0.0)
    
    # Level Assessment Results
    assessed_level = Column(String(2), nullable=True)  # A1, A2, B1, B2, C1, C2
    assessment_score = Column(Float, nullable=True)
    assessment_details = Column(JSON, default=dict)
    
    # Category Selection
    selected_categories = Column(JSON, default=list)  # List of LearningCategory
    primary_category = Column(
        SQLEnum(LearningCategory, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=True
    )
    category_priorities = Column(JSON, default=dict)  # Category -> priority mapping
    
    # Goals and Motivations
    learning_goals = Column(JSON, default=list)  # List of specific goals
    motivation_factors = Column(JSON, default=list)  # What motivates the user
    target_timeline = Column(String(50), nullable=True)  # "3_months", "6_months", "1_year"
    daily_study_commitment = Column(Integer, default=30)  # minutes per day
    
    # Preferences Collected During Onboarding
    preferred_learning_style = Column(
        SQLEnum(LearningStyle, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=True
    )
    preferred_difficulty = Column(String(20), default="gradual")  # gradual, moderate, challenging
    preferred_content_types = Column(JSON, default=list)  # video, audio, text, interactive
    
    # Onboarding Metadata
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    last_step_completed_at = Column(DateTime, nullable=True)
    
    # User Feedback
    onboarding_feedback = Column(Text, nullable=True)
    onboarding_rating = Column(Integer, nullable=True)  # 1-5 rating
    
    # Relationships
    user = relationship("User", back_populates="user_onboarding")

# Category-Based Learning Templates
class CategoryLearningTemplate(Base):
    __tablename__ = "category_learning_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Template Details
    category = Column(
        SQLEnum(LearningCategory, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=False
    )
    name = Column(String(200), nullable=False)
    description = Column(Text)
    target_levels = Column(JSON, nullable=False)  # List of CEFR levels this template supports
    
    # Template Structure
    template_data = Column(JSON, nullable=False)  # Complete learning path template
    estimated_duration_weeks = Column(Integer, nullable=False)
    total_milestones = Column(Integer, nullable=False)
    
    # Skill Distribution
    listening_percentage = Column(Float, default=25.0)
    speaking_percentage = Column(Float, default=25.0)
    reading_percentage = Column(Float, default=25.0)
    writing_percentage = Column(Float, default=25.0)
    
    # Content Requirements
    required_vocabulary_topics = Column(JSON, default=list)
    required_grammar_points = Column(JSON, default=list)
    recommended_content_types = Column(JSON, default=list)
    
    # Template Metadata
    difficulty_level = Column(String(20), default="moderate")
    is_active = Column(Boolean, default=True)
    created_by = Column(String(100), default="system")
    
    # Performance Tracking
    usage_count = Column(Integer, default=0)
    average_completion_rate = Column(Float, default=0.0)
    average_satisfaction_rating = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# User Category Preferences
class UserCategoryPreference(Base):
    __tablename__ = "user_category_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Category Information
    category = Column(
        SQLEnum(LearningCategory, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=False
    )
    priority_level = Column(Integer, default=1)  # 1=highest, 5=lowest
    interest_score = Column(Float, default=0.5)  # 0-1 scale
    
    # Learning Preferences for this Category
    preferred_focus_areas = Column(JSON, default=list)  # Specific areas within category
    preferred_content_difficulty = Column(String(20), default="moderate")
    preferred_session_duration = Column(Integer, default=30)  # minutes
    
    # Progress Tracking
    time_spent_minutes = Column(Integer, default=0)
    activities_completed = Column(Integer, default=0)
    average_performance = Column(Float, default=0.0)
    
    # User Feedback
    satisfaction_rating = Column(Float, nullable=True)  # 1-5 rating
    feedback_notes = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    last_activity_date = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="user_category_preferences") 