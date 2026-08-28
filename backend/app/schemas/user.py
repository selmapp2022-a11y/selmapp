from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.models.user import UserLevel

class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    current_level: UserLevel = UserLevel.A1
    # native_language is optional and unset by default — SELM is global.
    # Only stored when the user explicitly tells us.
    native_language: Optional[str] = None
    daily_goal_minutes: int = 30
    preferred_study_time: Optional[str] = None
    notification_enabled: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    current_level: Optional[UserLevel] = None
    native_language: Optional[str] = None
    daily_goal_minutes: Optional[int] = None
    preferred_study_time: Optional[str] = None
    notification_enabled: Optional[bool] = None
    password: Optional[str] = None
    onboarding_completed: Optional[bool] = None

class OAuth2AccountInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    provider: str
    provider_user_id: str
    provider_email: Optional[str] = None
    provider_name: Optional[str] = None
    provider_avatar_url: Optional[str] = None
    created_at: datetime

class UserInDBBase(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool
    is_verified: bool
    is_premium: bool
    is_admin: bool = False
    admin_role: Optional[str] = None
    has_password: bool
    onboarding_completed: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

class User(UserInDBBase):
    oauth_accounts: Optional[List[OAuth2AccountInfo]] = None

class UserInDB(UserInDBBase):
    hashed_password: Optional[str] = None 