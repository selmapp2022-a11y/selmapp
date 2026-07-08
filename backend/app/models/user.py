from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base

class UserLevel(str, enum.Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class AdminRole(str, enum.Enum):
    DEVELOPER = "developer"
    OWNER = "owner"

class OAuthProvider(str, enum.Enum):
    GOOGLE = "google"
    GITHUB = "github"
    FACEBOOK = "facebook"
    # APPLE added 2026-07-07 to fix Apple rejection (Guideline 2.1a).
    # Sign in with Apple was throwing 500 because the DB enum
    # `oauthprovider` didn't include 'apple'. The paired migration
    # `20260707_add_apple_to_oauthprovider.py` runs `ALTER TYPE
    # oauthprovider ADD VALUE 'apple'` on the database. Both must ship
    # together — Python enum and DB enum have to agree, or SQLAlchemy
    # will complain about unknown values on read.
    APPLE = "apple"

class OAuth2Account(Base):
    __tablename__ = "oauth2_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Use values_callable to ensure PostgreSQL enum uses lowercase values
    provider = Column(
        Enum(OAuthProvider, values_callable=lambda e: [m.value for m in e], native_enum=True, create_constraint=False),
        nullable=False
    )
    provider_user_id = Column(String(255), nullable=False)
    provider_email = Column(String(255), nullable=True)
    provider_name = Column(String(255), nullable=True)
    provider_avatar_url = Column(String(500), nullable=True)
    access_token = Column(String(1000), nullable=True)  # Store encrypted if needed
    refresh_token = Column(String(1000), nullable=True)  # Store encrypted if needed
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="oauth_accounts")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Made nullable for OAuth2 users
    full_name = Column(String(100))
    avatar_url = Column(String(500), nullable=True)  # Added for OAuth2 profile pictures
    
    # Profile information
    current_level = Column(Enum(UserLevel), default=UserLevel.A1)
    # native_language is NULL by default — SELM is global and we do not
    # presume a learner's L1. If the user sets it later we use it as a
    # hint for L1-interference patterns; otherwise prompts stay neutral.
    native_language = Column(String(50), nullable=True, default=None)
    target_language = Column(String(50), default="English")
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    admin_role = Column(String(20), nullable=True)  # 'developer' or 'owner'
    
    # Authentication method tracking
    has_password = Column(Boolean, default=True)  # Track if user has password or OAuth2 only
    
    # Soft delete fields - allows users to re-register with same email
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # When the account was deleted
    original_email_hash = Column(String(64), nullable=True)  # SHA256 hash of original email for audit
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Learning preferences
    daily_goal_minutes = Column(Integer, default=30)
    preferred_study_time = Column(String(20))  # morning, afternoon, evening
    notification_enabled = Column(Boolean, default=True)

    # Onboarding status
    onboarding_completed = Column(Boolean, default=False)
    
    # Relationships
    progress = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    exercise_attempts = relationship("ExerciseAttempt", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    
    # OAuth2 relationships
    oauth_accounts = relationship("OAuth2Account", back_populates="user", cascade="all, delete-orphan")
    
    # Vocabulary relationships
    user_vocabulary = relationship("UserVocabulary", back_populates="user", cascade="all, delete-orphan")
    vocabulary_exercises = relationship("VocabularyExercise", back_populates="user", cascade="all, delete-orphan")
    created_vocabulary_sets = relationship("VocabularySet", back_populates="creator", cascade="all, delete-orphan")
    
    # Personalization relationships
    learning_profile = relationship("UserLearningProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    user_onboarding = relationship("UserOnboarding", back_populates="user", uselist=False, cascade="all, delete-orphan")
    user_category_preferences = relationship("UserCategoryPreference", back_populates="user", cascade="all, delete-orphan")
    
    # Payment and Subscription relationships
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    content_access = relationship("ContentAccess", foreign_keys="ContentAccess.user_id", back_populates="user", cascade="all, delete-orphan")
    
    # AI lesson relationships
    ai_lessons = relationship("AIGeneratedLesson", back_populates="user", cascade="all, delete-orphan")
    lesson_progress = relationship("LessonProgress", back_populates="user", cascade="all, delete-orphan")