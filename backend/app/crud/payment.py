from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from app.crud.base import CRUDBase
from app.models.payment import (
    Payment, Subscription, ContentAccess, ContentLockConfig, 
    PaymentWebhook, Refund, SubscriptionPayment,
    PaymentStatus, SubscriptionStatus, SubscriptionPlan, ContentType
)
from app.schemas.payment import (
    PaymentCreate, PaymentUpdate, SubscriptionCreate, SubscriptionUpdate,
    ContentAccessCreate, ContentAccessUpdate, ContentLockConfigCreate, ContentLockConfigUpdate,
    PaymentWebhookCreate, RefundCreate
)


class CRUDPayment(CRUDBase[Payment, PaymentCreate, PaymentUpdate]):
    def create_payment(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        payment_data: PaymentCreate
    ) -> Payment:
        """Create a new payment"""
        db_payment = Payment(
            user_id=user_id,
            **payment_data.model_dump()
        )
        db.add(db_payment)
        db.commit()
        db.refresh(db_payment)
        return db_payment

    def get_by_paypal_payment_id(self, db: Session, *, paypal_payment_id: str) -> Optional[Payment]:
        """Get payment by PayPal payment ID"""
        return db.query(Payment).filter(Payment.paypal_payment_id == paypal_payment_id).first()

    def get_by_paypal_order_id(self, db: Session, *, paypal_order_id: str) -> Optional[Payment]:
        """Get payment by PayPal order ID"""
        return db.query(Payment).filter(Payment.paypal_order_id == paypal_order_id).first()

    def get_user_payments(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[PaymentStatus] = None
    ) -> List[Payment]:
        """Get payments for a specific user"""
        query = db.query(Payment).filter(Payment.user_id == user_id)
        
        if status:
            query = query.filter(Payment.status == status)
            
        return query.order_by(desc(Payment.created_at)).offset(skip).limit(limit).all()

    def update_payment_status(
        self, 
        db: Session, 
        *, 
        payment_id: int, 
        status: PaymentStatus,
        paypal_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Payment]:
        """Update payment status and PayPal data"""
        payment = self.get(db, id=payment_id)
        if not payment:
            return None

        payment.status = status
        
        if paypal_data:
            if "paypal_payment_id" in paypal_data:
                payment.paypal_payment_id = paypal_data["paypal_payment_id"]
            if "paypal_payer_id" in paypal_data:
                payment.paypal_payer_id = paypal_data["paypal_payer_id"]
            if "paypal_order_id" in paypal_data:
                payment.paypal_order_id = paypal_data["paypal_order_id"]
            if "paypal_capture_id" in paypal_data:
                payment.paypal_capture_id = paypal_data["paypal_capture_id"]

        if status == PaymentStatus.COMPLETED:
            payment.paid_at = datetime.utcnow()

        db.commit()
        db.refresh(payment)
        return payment

    def get_payment_analytics(
        self, 
        db: Session, 
        *, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get payment analytics for a date range"""
        payments = db.query(Payment).filter(
            and_(
                Payment.created_at >= start_date,
                Payment.created_at <= end_date
            )
        ).all()

        total_revenue = sum(p.amount for p in payments if p.status == PaymentStatus.COMPLETED)
        total_payments = len(payments)
        successful_payments = len([p for p in payments if p.status == PaymentStatus.COMPLETED])
        failed_payments = len([p for p in payments if p.status == PaymentStatus.FAILED])
        pending_payments = len([p for p in payments if p.status == PaymentStatus.PENDING])
        refunded_amount = sum(p.amount for p in payments if p.status == PaymentStatus.REFUNDED)
        
        avg_payment = total_revenue / successful_payments if successful_payments > 0 else Decimal('0')

        return {
            "total_revenue": total_revenue,
            "total_payments": total_payments,
            "successful_payments": successful_payments,
            "failed_payments": failed_payments,
            "pending_payments": pending_payments,
            "refunded_amount": refunded_amount,
            "average_payment_amount": avg_payment,
            "period_start": start_date,
            "period_end": end_date
        }


class CRUDSubscription(CRUDBase[Subscription, SubscriptionCreate, SubscriptionUpdate]):
    def create_subscription(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        subscription_data: SubscriptionCreate
    ) -> Subscription:
        """Create a new subscription"""
        start_date = datetime.utcnow()
        
        # Calculate trial period
        trial_start = None
        trial_end = None
        if hasattr(subscription_data, 'trial_days') and subscription_data.trial_days:
            trial_start = start_date
            trial_end = start_date + timedelta(days=subscription_data.trial_days)

        db_subscription = Subscription(
            user_id=user_id,
            start_date=start_date,
            trial_start=trial_start,
            trial_end=trial_end,
            is_trial=trial_start is not None,
            **subscription_data.model_dump(exclude={'trial_days'})
        )
        
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        return db_subscription

    def get_user_active_subscription(self, db: Session, *, user_id: int) -> Optional[Subscription]:
        """Get user's active subscription"""
        return db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        ).first()

    def get_user_subscriptions(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Subscription]:
        """Get all subscriptions for a user"""
        return db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).order_by(desc(Subscription.created_at)).offset(skip).limit(limit).all()

    def cancel_subscription(
        self, 
        db: Session, 
        *, 
        subscription_id: int, 
        reason: Optional[str] = None
    ) -> Optional[Subscription]:
        """Cancel a subscription"""
        subscription = self.get(db, id=subscription_id)
        if not subscription:
            return None

        subscription.status = SubscriptionStatus.CANCELLED
        subscription.cancelled_at = datetime.utcnow()
        subscription.cancellation_reason = reason

        db.commit()
        db.refresh(subscription)
        return subscription

    def get_expiring_subscriptions(
        self, 
        db: Session, 
        *, 
        days_ahead: int = 7
    ) -> List[Subscription]:
        """Get subscriptions expiring in the next N days"""
        expiry_date = datetime.utcnow() + timedelta(days=days_ahead)
        
        return db.query(Subscription).filter(
            and_(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.end_date <= expiry_date,
                Subscription.end_date >= datetime.utcnow()
            )
        ).all()

    def get_subscription_analytics(
        self, 
        db: Session, 
        *, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get subscription analytics for a date range"""
        subscriptions = db.query(Subscription).filter(
            and_(
                Subscription.created_at >= start_date,
                Subscription.created_at <= end_date
            )
        ).all()

        total_subscriptions = len(subscriptions)
        active_subscriptions = len([s for s in subscriptions if s.status == SubscriptionStatus.ACTIVE])
        cancelled_subscriptions = len([s for s in subscriptions if s.status == SubscriptionStatus.CANCELLED])
        trial_subscriptions = len([s for s in subscriptions if s.is_trial])

        # Calculate MRR and ARR
        active_monthly_subs = [s for s in subscriptions 
                              if s.status == SubscriptionStatus.ACTIVE and s.billing_cycle == "monthly"]
        active_yearly_subs = [s for s in subscriptions 
                             if s.status == SubscriptionStatus.ACTIVE and s.billing_cycle == "yearly"]

        mrr = sum(s.amount for s in active_monthly_subs)
        arr = sum(s.amount for s in active_yearly_subs) + (mrr * 12)

        # Calculate churn rate
        churn_rate = (cancelled_subscriptions / total_subscriptions * 100) if total_subscriptions > 0 else 0

        return {
            "total_subscriptions": total_subscriptions,
            "active_subscriptions": active_subscriptions,
            "cancelled_subscriptions": cancelled_subscriptions,
            "trial_subscriptions": trial_subscriptions,
            "monthly_recurring_revenue": mrr,
            "annual_recurring_revenue": arr,
            "churn_rate": churn_rate,
            "period_start": start_date,
            "period_end": end_date
        }


class CRUDContentAccess(CRUDBase[ContentAccess, ContentAccessCreate, ContentAccessUpdate]):
    def grant_access(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        content_type: ContentType, 
        content_identifier: str,
        subscription_id: Optional[int] = None,
        granted_by_admin_id: Optional[int] = None,
        access_data: Optional[ContentAccessCreate] = None
    ) -> ContentAccess:
        """Grant content access to a user"""
        # Check if access already exists
        existing_access = db.query(ContentAccess).filter(
            and_(
                ContentAccess.user_id == user_id,
                ContentAccess.content_type == content_type,
                ContentAccess.content_identifier == content_identifier
            )
        ).first()

        if existing_access:
            # Update existing access
            existing_access.access_granted_at = datetime.utcnow()
            existing_access.subscription_id = subscription_id
            existing_access.granted_by_admin_id = granted_by_admin_id
            
            if access_data:
                for field, value in access_data.model_dump(exclude_unset=True).items():
                    setattr(existing_access, field, value)
            
            db.commit()
            db.refresh(existing_access)
            return existing_access

        # Create new access
        access_dict = access_data.model_dump() if access_data else {}
        access_dict.update({
            "user_id": user_id,
            "content_type": content_type,
            "content_identifier": content_identifier,
            "subscription_id": subscription_id,
            "granted_by_admin_id": granted_by_admin_id,
            "access_granted_at": datetime.utcnow()
        })

        db_access = ContentAccess(**access_dict)
        db.add(db_access)
        db.commit()
        db.refresh(db_access)
        return db_access

    def check_access(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        content_type: ContentType, 
        content_identifier: str
    ) -> Dict[str, Any]:
        """Check if user has access to specific content"""
        # Get content lock configuration
        lock_config = db.query(ContentLockConfig).filter(
            and_(
                ContentLockConfig.content_type == content_type,
                ContentLockConfig.content_identifier == content_identifier
            )
        ).first()

        # If no lock configuration exists, content is free
        if not lock_config or not lock_config.is_locked:
            return {
                "has_access": True,
                "is_locked": False,
                "reason": "Content is free"
            }

        # Check user's content access
        user_access = db.query(ContentAccess).filter(
            and_(
                ContentAccess.user_id == user_id,
                ContentAccess.content_type == content_type,
                ContentAccess.content_identifier == content_identifier
            )
        ).first()

        # Check if user has direct access
        if user_access and user_access.access_granted_at:
            # Check if access has expired
            if user_access.access_expires_at and user_access.access_expires_at < datetime.utcnow():
                return {
                    "has_access": False,
                    "is_locked": True,
                    "required_plan": lock_config.required_plan,
                    "individual_price": lock_config.individual_price,
                    "reason": "Access expired"
                }
            
            return {
                "has_access": True,
                "is_locked": False,
                "reason": "Direct access granted"
            }

        # Check subscription-based access
        user_subscription = db.query(Subscription).filter(
            and_(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            )
        ).first()

        if user_subscription:
            # Check if subscription plan meets requirements
            plan_hierarchy = {
                SubscriptionPlan.FREE: 0,
                SubscriptionPlan.BASIC: 1,
                SubscriptionPlan.PREMIUM: 2,
                SubscriptionPlan.ENTERPRISE: 3
            }
            
            required_level = plan_hierarchy.get(lock_config.required_plan, 0)
            user_level = plan_hierarchy.get(user_subscription.plan, 0)
            
            if user_level >= required_level:
                return {
                    "has_access": True,
                    "is_locked": False,
                    "reason": f"Access via {user_subscription.plan} subscription"
                }

        return {
            "has_access": False,
            "is_locked": True,
            "required_plan": lock_config.required_plan,
            "individual_price": lock_config.individual_price,
            "reason": "Insufficient subscription level or no subscription"
        }

    def get_user_content_access(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ContentAccess]:
        """Get all content access for a user"""
        return db.query(ContentAccess).filter(
            ContentAccess.user_id == user_id
        ).order_by(desc(ContentAccess.created_at)).offset(skip).limit(limit).all()

    def revoke_access(
        self, 
        db: Session, 
        *, 
        user_id: int, 
        content_type: ContentType, 
        content_identifier: str
    ) -> bool:
        """Revoke content access from a user"""
        access = db.query(ContentAccess).filter(
            and_(
                ContentAccess.user_id == user_id,
                ContentAccess.content_type == content_type,
                ContentAccess.content_identifier == content_identifier
            )
        ).first()

        if access:
            db.delete(access)
            db.commit()
            return True
        return False


class CRUDContentLockConfig(CRUDBase[ContentLockConfig, ContentLockConfigCreate, ContentLockConfigUpdate]):
    def create_lock_config(
        self, 
        db: Session, 
        *, 
        config_data: ContentLockConfigCreate,
        created_by_admin_id: int
    ) -> ContentLockConfig:
        """Create content lock configuration"""
        db_config = ContentLockConfig(
            created_by_admin_id=created_by_admin_id,
            **config_data.model_dump()
        )
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return db_config

    def get_by_content(
        self, 
        db: Session, 
        *, 
        content_type: ContentType, 
        content_identifier: str
    ) -> Optional[ContentLockConfig]:
        """Get lock configuration for specific content"""
        return db.query(ContentLockConfig).filter(
            and_(
                ContentLockConfig.content_type == content_type,
                ContentLockConfig.content_identifier == content_identifier
            )
        ).first()

    def get_locked_content(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ContentLockConfig]:
        """Get all locked content configurations"""
        return db.query(ContentLockConfig).filter(
            ContentLockConfig.is_locked == True
        ).order_by(ContentLockConfig.content_type, ContentLockConfig.content_identifier).offset(skip).limit(limit).all()

    def bulk_update_locks(
        self, 
        db: Session, 
        *, 
        content_items: List[Dict[str, Any]],
        admin_id: int
    ) -> List[ContentLockConfig]:
        """Bulk update content lock configurations"""
        results = []
        
        for item in content_items:
            existing = self.get_by_content(
                db,
                content_type=item["content_type"],
                content_identifier=item["content_identifier"]
            )
            
            if existing:
                # Update existing
                for field, value in item.items():
                    if hasattr(existing, field):
                        setattr(existing, field, value)
                results.append(existing)
            else:
                # Create new
                new_config = ContentLockConfig(
                    created_by_admin_id=admin_id,
                    **item
                )
                db.add(new_config)
                results.append(new_config)
        
        db.commit()
        for result in results:
            db.refresh(result)
        
        return results


class CRUDPaymentWebhook(CRUDBase[PaymentWebhook, PaymentWebhookCreate, None]):
    def create_webhook_event(
        self, 
        db: Session, 
        *, 
        webhook_data: PaymentWebhookCreate
    ) -> PaymentWebhook:
        """Create webhook event record"""
        db_webhook = PaymentWebhook(**webhook_data.model_dump())
        db.add(db_webhook)
        db.commit()
        db.refresh(db_webhook)
        return db_webhook

    def mark_processed(
        self, 
        db: Session, 
        *, 
        webhook_id: int, 
        payment_id: Optional[int] = None,
        error: Optional[str] = None
    ) -> Optional[PaymentWebhook]:
        """Mark webhook as processed"""
        webhook = self.get(db, id=webhook_id)
        if not webhook:
            return None

        webhook.processed = True
        webhook.processed_at = datetime.utcnow()
        webhook.payment_id = payment_id
        
        if error:
            webhook.processing_error = error
            webhook.retry_count += 1
        
        db.commit()
        db.refresh(webhook)
        return webhook

    def get_unprocessed_webhooks(self, db: Session, *, limit: int = 100) -> List[PaymentWebhook]:
        """Get unprocessed webhook events"""
        return db.query(PaymentWebhook).filter(
            PaymentWebhook.processed == False
        ).order_by(PaymentWebhook.received_at).limit(limit).all()


class CRUDRefund(CRUDBase[Refund, RefundCreate, None]):
    def create_refund(
        self, 
        db: Session, 
        *, 
        refund_data: RefundCreate,
        requested_by_admin_id: int
    ) -> Refund:
        """Create a refund request"""
        # Get the payment to determine currency and amount
        payment = db.query(Payment).filter(Payment.id == refund_data.payment_id).first()
        if not payment:
            raise ValueError("Payment not found")

        refund_amount = refund_data.amount or payment.amount

        db_refund = Refund(
            payment_id=refund_data.payment_id,
            amount=refund_amount,
            currency=payment.currency,
            reason=refund_data.reason,
            requested_by_admin_id=requested_by_admin_id,
            admin_notes=refund_data.admin_notes
        )
        
        db.add(db_refund)
        db.commit()
        db.refresh(db_refund)
        return db_refund

    def get_payment_refunds(self, db: Session, *, payment_id: int) -> List[Refund]:
        """Get all refunds for a payment"""
        return db.query(Refund).filter(Refund.payment_id == payment_id).all()

    def update_refund_status(
        self, 
        db: Session, 
        *, 
        refund_id: int, 
        status: str,
        paypal_refund_id: Optional[str] = None
    ) -> Optional[Refund]:
        """Update refund status"""
        refund = self.get(db, id=refund_id)
        if not refund:
            return None

        refund.status = status
        if paypal_refund_id:
            refund.paypal_refund_id = paypal_refund_id
        
        if status == "completed":
            refund.processed_at = datetime.utcnow()

        db.commit()
        db.refresh(refund)
        return refund


# Create instances
payment_crud = CRUDPayment(Payment)
subscription_crud = CRUDSubscription(Subscription)
content_access_crud = CRUDContentAccess(ContentAccess)
content_lock_config_crud = CRUDContentLockConfig(ContentLockConfig)
payment_webhook_crud = CRUDPaymentWebhook(PaymentWebhook)
refund_crud = CRUDRefund(Refund) 