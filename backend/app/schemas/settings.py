from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class AppSettingsBase(BaseModel):
    category: str = Field(..., max_length=50)
    key: str = Field(..., max_length=100)
    value: Optional[str] = None
    value_type: str = Field(default="string", max_length=20)
    display_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    default_value: Optional[str] = None
    allowed_values: Optional[List[Any]] = None
    min_value: Optional[str] = Field(None, max_length=50)
    max_value: Optional[str] = Field(None, max_length=50)
    is_active: bool = True
    is_system: bool = False
    requires_restart: bool = False

class AppSettingsCreate(AppSettingsBase):
    pass

class AppSettingsUpdate(BaseModel):
    value: Optional[str] = None
    value_type: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    default_value: Optional[str] = None
    allowed_values: Optional[List[Any]] = None
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    is_active: Optional[bool] = None
    requires_restart: Optional[bool] = None

class AppSettingsResponse(AppSettingsBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class PaymentSettingsUpdate(BaseModel):
    payment_enabled: Optional[bool] = None
    content_lock_enabled: Optional[bool] = None
    free_cefr_levels: Optional[List[str]] = None
    free_modules: Optional[List[str]] = None
    free_lessons_quota: Optional[int] = None
    premium_price_monthly: Optional[float] = None
    premium_price_yearly: Optional[float] = None

class PaymentSettingsResponse(BaseModel):
    payment_enabled: bool
    content_lock_enabled: bool
    free_cefr_levels: List[str]
    free_modules: List[str]
    free_lessons_quota: int
    premium_price_monthly: float
    premium_price_yearly: float

class ContentSettingsUpdate(BaseModel):
    max_daily_exercises: Optional[int] = None
    ai_feedback_enabled: Optional[bool] = None

class ContentSettingsResponse(BaseModel):
    max_daily_exercises: int
    ai_feedback_enabled: bool

class FeatureSettingsUpdate(BaseModel):
    speech_recognition_enabled: Optional[bool] = None
    gamification_enabled: Optional[bool] = None

class FeatureSettingsResponse(BaseModel):
    speech_recognition_enabled: bool
    gamification_enabled: bool

class AllSettingsResponse(BaseModel):
    payment: PaymentSettingsResponse
    content: ContentSettingsResponse
    features: FeatureSettingsResponse 