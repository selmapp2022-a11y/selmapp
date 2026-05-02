from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


# Enums
class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethodEnum(str, Enum):
    PAYPAL = "paypal"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"


class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class SubscriptionPlanEnum(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class ContentTypeEnum(str, Enum):
    MODULE = "module"
    CEFR_LEVEL = "cefr_level"
    FEATURE = "feature"
    FULL_ACCESS = "full_access"


# Base Schemas
class PaymentBase(BaseModel):
    amount: Decimal = Field(..., description="Payment amount")
    currency: str = Field(default="USD", description="Payment currency")
    description: Optional[str] = Field(None, description="Payment description")
    payment_method: PaymentMethodEnum = Field(default=PaymentMethodEnum.PAYPAL)


class PaymentCreate(PaymentBase):
    """Schema for creating a new payment"""
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional payment metadata")


class PaymentUpdate(BaseModel):
    """Schema for updating payment status"""
    status: Optional[PaymentStatusEnum] = None
    paypal_payment_id: Optional[str] = None
    paypal_payer_id: Optional[str] = None
    paypal_order_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class PaymentResponse(PaymentBase):
    """Schema for payment response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    status: PaymentStatusEnum
    paypal_payment_id: Optional[str] = None
    paypal_payer_id: Optional[str] = None
    paypal_order_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


# PayPal specific schemas
class PayPalOrderCreate(BaseModel):
    """Schema for creating PayPal order"""
    amount: Decimal = Field(..., description="Order amount")
    currency: str = Field(default="USD", description="Order currency")
    description: str = Field(..., description="Order description")
    return_url: Optional[str] = Field(None, description="Return URL after payment")
    cancel_url: Optional[str] = Field(None, description="Cancel URL")


class PayPalOrderResponse(BaseModel):
    """Schema for PayPal order response"""
    order_id: str = Field(..., description="PayPal order ID")
    approval_url: str = Field(..., description="PayPal approval URL")
    status: str = Field(..., description="Order status")


class PayPalCaptureRequest(BaseModel):
    """Schema for capturing PayPal payment"""
    order_id: str = Field(..., description="PayPal order ID")
    payer_id: Optional[str] = Field(None, description="PayPal payer ID")


# Subscription Schemas
class SubscriptionBase(BaseModel):
    plan: SubscriptionPlanEnum = Field(..., description="Subscription plan")
    billing_cycle: str = Field(default="monthly", description="Billing cycle")
    amount: Decimal = Field(..., description="Subscription amount")
    currency: str = Field(default="USD", description="Subscription currency")


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a new subscription"""
    trial_days: Optional[int] = Field(None, description="Trial period in days")


class SubscriptionUpdate(BaseModel):
    """Schema for updating subscription"""
    status: Optional[SubscriptionStatusEnum] = None
    plan: Optional[SubscriptionPlanEnum] = None
    paypal_subscription_id: Optional[str] = None
    paypal_plan_id: Optional[str] = None
    end_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None


class SubscriptionResponse(SubscriptionBase):
    """Schema for subscription response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    status: SubscriptionStatusEnum
    paypal_subscription_id: Optional[str] = None
    paypal_plan_id: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    is_trial: bool = False
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Content Access Schemas
class ContentAccessBase(BaseModel):
    content_type: ContentTypeEnum = Field(..., description="Type of content")
    content_identifier: str = Field(..., description="Content identifier")
    is_locked: bool = Field(default=False, description="Whether content is locked")
    is_premium: bool = Field(default=False, description="Whether content is premium")
    requires_subscription: bool = Field(default=False, description="Whether content requires subscription")


class ContentAccessCreate(ContentAccessBase):
    """Schema for creating content access"""
    access_expires_at: Optional[datetime] = Field(None, description="Access expiration date")
    manually_granted: bool = Field(default=False, description="Whether access was manually granted")
    admin_notes: Optional[str] = Field(None, description="Admin notes")


class ContentAccessUpdate(BaseModel):
    """Schema for updating content access"""
    is_locked: Optional[bool] = None
    is_premium: Optional[bool] = None
    requires_subscription: Optional[bool] = None
    access_granted_at: Optional[datetime] = None
    access_expires_at: Optional[datetime] = None
    manually_granted: Optional[bool] = None
    admin_notes: Optional[str] = None


class ContentAccessResponse(ContentAccessBase):
    """Schema for content access response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    subscription_id: Optional[int] = None
    access_granted_at: Optional[datetime] = None
    access_expires_at: Optional[datetime] = None
    manually_granted: bool = False
    granted_by_admin_id: Optional[int] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Content Lock Configuration Schemas
class ContentLockConfigBase(BaseModel):
    content_type: ContentTypeEnum = Field(..., description="Type of content")
    content_identifier: str = Field(..., description="Content identifier")
    is_locked: bool = Field(default=False, description="Whether content is locked")
    required_plan: SubscriptionPlanEnum = Field(default=SubscriptionPlanEnum.FREE, description="Required subscription plan")
    individual_price: Optional[Decimal] = Field(None, description="Individual purchase price")
    individual_currency: str = Field(default="USD", description="Individual purchase currency")
    description: Optional[str] = Field(None, description="Content description")


class ContentLockConfigCreate(ContentLockConfigBase):
    """Schema for creating content lock configuration"""
    admin_notes: Optional[str] = Field(None, description="Admin notes")


class ContentLockConfigUpdate(BaseModel):
    """Schema for updating content lock configuration"""
    is_locked: Optional[bool] = None
    required_plan: Optional[SubscriptionPlanEnum] = None
    individual_price: Optional[Decimal] = None
    individual_currency: Optional[str] = None
    description: Optional[str] = None
    admin_notes: Optional[str] = None


class ContentLockConfigResponse(ContentLockConfigBase):
    """Schema for content lock configuration response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_by_admin_id: Optional[int] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Webhook Schemas
class PaymentWebhookCreate(BaseModel):
    """Schema for creating payment webhook record"""
    webhook_id: str = Field(..., description="Webhook ID")
    event_type: str = Field(..., description="Event type")
    resource_type: str = Field(..., description="Resource type")
    paypal_event_id: str = Field(..., description="PayPal event ID")
    paypal_resource_id: Optional[str] = Field(None, description="PayPal resource ID")
    payload: Dict[str, Any] = Field(..., description="Webhook payload")
    headers: Optional[Dict[str, str]] = Field(None, description="Webhook headers")


class PaymentWebhookResponse(BaseModel):
    """Schema for payment webhook response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    webhook_id: str
    event_type: str
    resource_type: str
    paypal_event_id: str
    paypal_resource_id: Optional[str] = None
    processed: bool = False
    processing_error: Optional[str] = None
    retry_count: int = 0
    payload: Dict[str, Any]
    headers: Optional[Dict[str, str]] = None
    received_at: datetime
    processed_at: Optional[datetime] = None
    payment_id: Optional[int] = None


# Refund Schemas
class RefundCreate(BaseModel):
    """Schema for creating a refund"""
    payment_id: int = Field(..., description="Payment ID to refund")
    amount: Optional[Decimal] = Field(None, description="Refund amount (full refund if not specified)")
    reason: Optional[str] = Field(None, description="Refund reason")
    admin_notes: Optional[str] = Field(None, description="Admin notes")


class RefundResponse(BaseModel):
    """Schema for refund response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    payment_id: int
    amount: Decimal
    currency: str
    reason: Optional[str] = None
    paypal_refund_id: Optional[str] = None
    status: str
    processed_at: Optional[datetime] = None
    requested_by_admin_id: Optional[int] = None
    admin_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# Dashboard and Analytics Schemas
class PaymentAnalytics(BaseModel):
    """Schema for payment analytics"""
    total_revenue: Decimal
    total_payments: int
    successful_payments: int
    failed_payments: int
    pending_payments: int
    refunded_amount: Decimal
    average_payment_amount: Decimal
    period_start: datetime
    period_end: datetime


class SubscriptionAnalytics(BaseModel):
    """Schema for subscription analytics"""
    total_subscriptions: int
    active_subscriptions: int
    cancelled_subscriptions: int
    trial_subscriptions: int
    monthly_recurring_revenue: Decimal
    annual_recurring_revenue: Decimal
    churn_rate: float
    period_start: datetime
    period_end: datetime


class ContentAccessCheck(BaseModel):
    """Schema for checking content access"""
    content_type: ContentTypeEnum = Field(..., description="Type of content")
    content_identifier: str = Field(..., description="Content identifier")


class ContentAccessResult(BaseModel):
    """Schema for content access result"""
    has_access: bool = Field(..., description="Whether user has access")
    is_locked: bool = Field(..., description="Whether content is locked")
    required_plan: Optional[SubscriptionPlanEnum] = Field(None, description="Required plan for access")
    individual_price: Optional[Decimal] = Field(None, description="Individual purchase price")
    reason: str = Field(..., description="Reason for access status")
    upgrade_url: Optional[str] = Field(None, description="URL to upgrade subscription")


# Bulk operations
class BulkContentLockUpdate(BaseModel):
    """Schema for bulk content lock updates"""
    content_items: List[ContentLockConfigCreate] = Field(..., description="List of content items to update")
    apply_to_existing_users: bool = Field(default=False, description="Whether to apply to existing users")


class BulkContentAccessGrant(BaseModel):
    """Schema for bulk content access grants"""
    user_ids: List[int] = Field(..., description="List of user IDs")
    content_items: List[ContentAccessCreate] = Field(..., description="List of content items to grant access to")
    admin_notes: Optional[str] = Field(None, description="Admin notes") 