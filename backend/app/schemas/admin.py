"""Admin-specific Pydantic schemas for the admin panel API."""
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── System Statistics ──────────────────────────────────────────────────
class SystemStats(BaseModel):
    total_users: int = 0
    active_users: int = 0  # logged in within last 30 days
    premium_users: int = 0
    new_users_today: int = 0
    new_users_this_week: int = 0
    new_users_this_month: int = 0
    total_lessons_generated: int = 0
    total_exercises_completed: int = 0
    average_accuracy: float = 0.0
    total_payments: int = 0
    total_revenue: float = 0.0


class UserActivitySummary(BaseModel):
    date: str
    active_users: int = 0
    new_registrations: int = 0
    lessons_completed: int = 0
    exercises_completed: int = 0


class SystemReport(BaseModel):
    generated_at: datetime
    period: str  # "daily", "weekly", "monthly"
    stats: SystemStats
    daily_activity: List[UserActivitySummary] = []


# ── User Management ───────────────────────────────────────────────────
class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    current_level: Optional[str] = None
    is_active: bool = True
    is_verified: bool = False
    is_premium: bool = False
    is_admin: bool = False
    admin_role: Optional[str] = None
    onboarding_completed: bool = False
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class AdminUserDetail(AdminUserListItem):
    avatar_url: Optional[str] = None
    native_language: Optional[str] = None
    target_language: Optional[str] = None
    has_password: bool = True
    daily_goal_minutes: int = 30
    preferred_study_time: Optional[str] = None
    notification_enabled: bool = True
    updated_at: Optional[datetime] = None

    # Progress summary (populated separately)
    total_study_time_minutes: int = 0
    total_exercises_completed: int = 0
    average_accuracy: float = 0.0
    current_streak_days: int = 0


class AdminUserUpdate(BaseModel):
    """Fields an admin can update on a user."""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    current_level: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_premium: Optional[bool] = None
    is_admin: Optional[bool] = None
    admin_role: Optional[str] = None
    onboarding_completed: Optional[bool] = None
    daily_goal_minutes: Optional[int] = None


class AdminUserListResponse(BaseModel):
    users: List[AdminUserListItem]
    total: int
    page: int = 1
    per_page: int = 20


# ── User Activity Report ──────────────────────────────────────────────
class UserActivityReport(BaseModel):
    user_id: int
    email: str
    username: str
    total_study_time_minutes: int = 0
    total_exercises_completed: int = 0
    average_accuracy: float = 0.0
    current_streak_days: int = 0
    last_login: Optional[datetime] = None
    last_study_date: Optional[datetime] = None
    lessons_completed: int = 0
    onboarding_completed: bool = False
    current_level: Optional[str] = None


class UserActivityListResponse(BaseModel):
    activities: List[UserActivityReport]
    total: int
    page: int = 1
    per_page: int = 20


# ── Content Statistics ─────────────────────────────────────────────────
class ContentStats(BaseModel):
    total_ai_lessons: int = 0
    total_reading_texts: int = 0
    total_vocabulary_sets: int = 0
    lessons_by_type: Dict[str, int] = {}
    lessons_by_level: Dict[str, int] = {}


# ── Admin Dashboard ───────────────────────────────────────────────────
class AdminDashboard(BaseModel):
    system_stats: SystemStats
    content_stats: ContentStats
    recent_users: List[AdminUserListItem] = []
    daily_activity: List[UserActivitySummary] = []
