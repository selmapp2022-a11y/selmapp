from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text, JSON, DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum
from datetime import datetime
from typing import Optional


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    PAYPAL = "paypal"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class ContentType(str, enum.Enum):
    MODULE = "module"  # listening, speaking, reading, writing
    CEFR_LEVEL = "cefr_level"  # A1, A2, B1, B2, C1, C2
    FEATURE = "feature"  # specific features
    FULL_ACCESS = "full_access"


# Payment Models
class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Payment Details
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.PAYPAL, nullable=False)
    
    # PayPal Integration
    paypal_payment_id = Column(String(255), unique=True, index=True)
    paypal_payer_id = Column(String(255))
    paypal_order_id = Column(String(255))
    paypal_capture_id = Column(String(255))
    
    # Transaction Details
    description = Column(Text)
    payment_metadata = Column(JSON)  # Store additional payment data
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="payments")
    subscription_payments = relationship("SubscriptionPayment", back_populates="payment")


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False)
    
    # Period this payment covers
    billing_period_start = Column(DateTime(timezone=True), nullable=False)
    billing_period_end = Column(DateTime(timezone=True), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    subscription = relationship("Subscription", back_populates="payments")
    payment = relationship("Payment", back_populates="subscription_payments")


# Subscription Models
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Subscription Details
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.INACTIVE, nullable=False)
    
    # PayPal Subscription Integration (legacy)
    paypal_subscription_id = Column(String(255), unique=True, index=True)
    paypal_plan_id = Column(String(255))

    # RevenueCat Subscription Integration
    provider = Column(String(20), default="paypal", nullable=False)  # paypal | revenuecat
    rc_app_user_id = Column(String(255), index=True)                 # RevenueCat App User ID
    rc_entitlement = Column(String(100))                              # e.g. "selm_pro"
    rc_product_id = Column(String(255))                               # e.g. "selm_monthly"
    rc_period_type = Column(String(20))                               # NORMAL | TRIAL | INTRO | PROMOTIONAL
    rc_store = Column(String(20))                                     # APP_STORE | PLAY_STORE | STRIPE | RC_BILLING

    # Billing Details
    amount = Column(DECIMAL(10, 2), nullable=False, default=0.00)
    currency = Column(String(3), default="USD", nullable=False)
    billing_cycle = Column(String(20), default="monthly")  # monthly, yearly
    
    # Subscription Period
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True))
    next_billing_date = Column(DateTime(timezone=True))
    
    # Trial Period
    trial_start = Column(DateTime(timezone=True))
    trial_end = Column(DateTime(timezone=True))
    is_trial = Column(Boolean, default=False)
    
    # Cancellation
    cancelled_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payments = relationship("SubscriptionPayment", back_populates="subscription")
    content_access = relationship("ContentAccess", back_populates="subscription")


# Content Access Control Models
class ContentAccess(Base):
    __tablename__ = "content_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    
    # Content Access Details
    content_type = Column(Enum(ContentType), nullable=False)
    content_identifier = Column(String(100), nullable=False)  # e.g., "listening", "A2", "advanced_grammar"
    
    # Access Control
    is_locked = Column(Boolean, default=False, nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)
    requires_subscription = Column(Boolean, default=False, nullable=False)
    
    # Access Period
    access_granted_at = Column(DateTime(timezone=True))
    access_expires_at = Column(DateTime(timezone=True))
    
    # Admin Controls
    manually_granted = Column(Boolean, default=False)
    granted_by_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="content_access")
    subscription = relationship("Subscription", back_populates="content_access")
    granted_by_admin = relationship("User", foreign_keys=[granted_by_admin_id])
    
    # Unique constraint to prevent duplicate access records
    __table_args__ = (
        {"extend_existing": True},
    )


# Admin Content Lock Configuration
class ContentLockConfig(Base):
    __tablename__ = "content_lock_config"

    id = Column(Integer, primary_key=True, index=True)
    
    # Content Identification
    content_type = Column(Enum(ContentType), nullable=False)
    content_identifier = Column(String(100), nullable=False)
    
    # Lock Configuration
    is_locked = Column(Boolean, default=False, nullable=False)
    required_plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False)
    
    # Pricing (if sold individually)
    individual_price = Column(DECIMAL(10, 2))
    individual_currency = Column(String(3), default="USD")
    
    # Admin Details
    created_by_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text)
    admin_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    created_by_admin = relationship("User", foreign_keys=[created_by_admin_id])
    
    # Unique constraint for content type and identifier
    __table_args__ = (
        {"extend_existing": True},
    )


# Payment Webhook Events (for PayPal webhooks)
class PaymentWebhook(Base):
    __tablename__ = "payment_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    
    # Webhook Details
    webhook_id = Column(String(255), nullable=False)
    event_type = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    
    # PayPal Data
    paypal_event_id = Column(String(255), unique=True, index=True)
    paypal_resource_id = Column(String(255))
    
    # Processing Status
    processed = Column(Boolean, default=False, nullable=False)
    processing_error = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Webhook Payload
    payload = Column(JSON, nullable=False)
    headers = Column(JSON)
    
    # Timestamps
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    
    # Related Payment
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    payment = relationship("Payment")


# Refund Model
class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False)
    
    # Refund Details
    amount = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    reason = Column(Text)
    
    # PayPal Integration
    paypal_refund_id = Column(String(255), unique=True, index=True)
    
    # Processing
    status = Column(String(50), default="pending")
    processed_at = Column(DateTime(timezone=True))
    
    # Admin Details
    requested_by_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_notes = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    payment = relationship("Payment")
    requested_by_admin = relationship("User", foreign_keys=[requested_by_admin_id]) 