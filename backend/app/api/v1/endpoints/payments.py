from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from app.api.deps import get_sync_db, get_current_user, get_current_admin_user
from app.models.user import User
from app.models.payment import PaymentStatus, SubscriptionStatus, ContentType
from app.schemas.payment import (
    PaymentCreate, PaymentResponse, PaymentUpdate,
    PayPalOrderCreate, PayPalOrderResponse, PayPalCaptureRequest,
    SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate,
    ContentAccessCreate, ContentAccessResponse, ContentAccessCheck, ContentAccessResult,
    ContentLockConfigCreate, ContentLockConfigResponse, ContentLockConfigUpdate,
    PaymentWebhookCreate, RefundCreate, RefundResponse,
    PaymentAnalytics, SubscriptionAnalytics, BulkContentLockUpdate, BulkContentAccessGrant
)
from app.crud.payment import (
    payment_crud, subscription_crud, content_access_crud, 
    content_lock_config_crud, payment_webhook_crud, refund_crud
)
from app.services.paypal_service import paypal_service
from app.core.config import settings
from app.models.settings import SettingCategory
from app.crud.settings import settings_crud

logger = logging.getLogger(__name__)
router = APIRouter()


def _ensure_payment_enabled(db: Session) -> None:
    """Guard: raise 403 if the payment system is disabled in admin settings."""
    enabled = settings_crud.get_value(db, SettingCategory.PAYMENT.value, "payment_enabled", False)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payment system is currently disabled",
        )


# Payment Endpoints
@router.post("/orders", response_model=PayPalOrderResponse)
async def create_payment_order(
    order_data: PayPalOrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Create a PayPal order for one-time payment"""
    try:
        _ensure_payment_enabled(db)

        # Create PayPal order
        paypal_order = await paypal_service.create_order(
            amount=order_data.amount,
            currency=order_data.currency,
            description=order_data.description,
            return_url=order_data.return_url,
            cancel_url=order_data.cancel_url
        )
        
        # Create payment record in database
        payment_data = PaymentCreate(
            amount=order_data.amount,
            currency=order_data.currency,
            description=order_data.description
        )
        
        db_payment = payment_crud.create_payment(
            db=db,
            user_id=current_user.id,
            payment_data=payment_data
        )
        
        # Update payment with PayPal order ID
        payment_crud.update_payment_status(
            db=db,
            payment_id=db_payment.id,
            status=PaymentStatus.PENDING,
            paypal_data={"paypal_order_id": paypal_order["order_id"]}
        )
        
        return PayPalOrderResponse(
            order_id=paypal_order["order_id"],
            approval_url=paypal_order["approval_url"],
            status=paypal_order["status"]
        )
        
    except Exception as e:
        logger.error(f"Failed to create PayPal order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order"
        )


@router.post("/orders/{order_id}/capture")
async def capture_payment_order(
    order_id: str,
    capture_data: PayPalCaptureRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Capture a PayPal order"""
    try:
        _ensure_payment_enabled(db)

        # Get payment record
        payment = payment_crud.get_by_paypal_order_id(db=db, paypal_order_id=order_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Verify payment belongs to current user
        if payment.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to capture this payment"
            )
        
        # Capture PayPal order
        capture_result = await paypal_service.capture_order(order_id)
        
        # Update payment status
        paypal_data = {
            "paypal_capture_id": capture_result["capture_id"],
            "paypal_payer_id": capture_result["payer_id"]
        }
        
        if capture_result["status"] == "COMPLETED":
            payment_status = PaymentStatus.COMPLETED
        else:
            payment_status = PaymentStatus.FAILED
        
        updated_payment = payment_crud.update_payment_status(
            db=db,
            payment_id=payment.id,
            status=payment_status,
            paypal_data=paypal_data
        )
        
        return {
            "payment_id": updated_payment.id,
            "status": updated_payment.status,
            "capture_id": capture_result["capture_id"],
            "amount": capture_result["amount"],
            "currency": capture_result["currency"]
        }
        
    except Exception as e:
        logger.error(f"Failed to capture PayPal order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to capture payment"
        )


@router.get("/payments", response_model=List[PaymentResponse])
async def get_user_payments(
    skip: int = 0,
    limit: int = 100,
    status: Optional[PaymentStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get user's payment history"""
    payments = payment_crud.get_user_payments(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        status=status
    )
    return payments


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get specific payment details"""
    payment = payment_crud.get(db=db, id=payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this payment"
        )
    
    return payment


# Subscription Endpoints
@router.post("/subscriptions", response_model=SubscriptionResponse)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Create a new subscription"""
    try:
        _ensure_payment_enabled(db)

        # Check if user already has an active subscription
        existing_subscription = subscription_crud.get_user_active_subscription(
            db=db, user_id=current_user.id
        )
        if existing_subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has an active subscription"
            )
        
        # Create subscription plan in PayPal
        plan_name = f"SelmApp {subscription_data.plan.title()} Plan"
        plan_description = f"SelmApp {subscription_data.plan} subscription - {subscription_data.billing_cycle}"
        
        paypal_plan = await paypal_service.create_subscription_plan(
            name=plan_name,
            description=plan_description,
            amount=subscription_data.amount,
            currency=subscription_data.currency,
            billing_cycle=subscription_data.billing_cycle
        )
        
        # Create PayPal subscription
        paypal_subscription = await paypal_service.create_subscription(
            plan_id=paypal_plan["id"]
        )
        
        # Create subscription record in database
        db_subscription = subscription_crud.create_subscription(
            db=db,
            user_id=current_user.id,
            subscription_data=subscription_data
        )
        
        # Update subscription with PayPal IDs
        subscription_crud.update(
            db=db,
            db_obj=db_subscription,
            obj_in=SubscriptionUpdate(
                paypal_subscription_id=paypal_subscription["subscription_id"],
                paypal_plan_id=paypal_plan["id"]
            )
        )
        
        return {
            **db_subscription.__dict__,
            "approval_url": paypal_subscription["approval_url"]
        }
        
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription"
        )


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def get_user_subscriptions(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get user's subscriptions"""
    subscriptions = subscription_crud.get_user_subscriptions(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return subscriptions


@router.get("/subscriptions/active", response_model=Optional[SubscriptionResponse])
async def get_active_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get user's active subscription"""
    subscription = subscription_crud.get_user_active_subscription(
        db=db, user_id=current_user.id
    )
    return subscription


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Cancel a subscription"""
    try:
        # Get subscription
        subscription = subscription_crud.get(db=db, id=subscription_id)
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )
        
        if subscription.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this subscription"
            )
        
        # Cancel PayPal subscription
        if subscription.paypal_subscription_id:
            await paypal_service.cancel_subscription(
                subscription.paypal_subscription_id,
                reason or "User requested cancellation"
            )
        
        # Update subscription status
        cancelled_subscription = subscription_crud.cancel_subscription(
            db=db,
            subscription_id=subscription_id,
            reason=reason
        )
        
        return {
            "message": "Subscription cancelled successfully",
            "subscription_id": cancelled_subscription.id,
            "status": cancelled_subscription.status
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


# Content Access Endpoints
@router.post("/content/access/check", response_model=ContentAccessResult)
async def check_content_access(
    access_check: ContentAccessCheck,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Check if user has access to specific content"""
    access_result = content_access_crud.check_access(
        db=db,
        user_id=current_user.id,
        content_type=access_check.content_type,
        content_identifier=access_check.content_identifier
    )
    
    # Add upgrade URL if access is denied
    if not access_result["has_access"]:
        frontend_url = getattr(settings, "FRONTEND_URL", "") or ""
        if frontend_url:
            access_result["upgrade_url"] = f"{frontend_url.rstrip('/')}/upgrade"
    
    return ContentAccessResult(**access_result)


@router.get("/content/access", response_model=List[ContentAccessResponse])
async def get_user_content_access(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get user's content access permissions"""
    access_list = content_access_crud.get_user_content_access(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return access_list


# Admin Endpoints
@router.get("/admin/payments", response_model=List[PaymentResponse])
async def get_all_payments(
    skip: int = 0,
    limit: int = 100,
    status: Optional[PaymentStatus] = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Get all payments (admin only)"""
    query = db.query(payment_crud.model)
    
    if status:
        query = query.filter(payment_crud.model.status == status)
    
    payments = query.offset(skip).limit(limit).all()
    return payments


@router.get("/admin/analytics/payments", response_model=PaymentAnalytics)
async def get_payment_analytics(
    start_date: datetime,
    end_date: datetime,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Get payment analytics (admin only)"""
    analytics = payment_crud.get_payment_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date
    )
    return PaymentAnalytics(**analytics)


@router.get("/admin/analytics/subscriptions", response_model=SubscriptionAnalytics)
async def get_subscription_analytics(
    start_date: datetime,
    end_date: datetime,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Get subscription analytics (admin only)"""
    analytics = subscription_crud.get_subscription_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date
    )
    return SubscriptionAnalytics(**analytics)


@router.post("/admin/content/lock", response_model=ContentLockConfigResponse)
async def create_content_lock(
    lock_config: ContentLockConfigCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Create content lock configuration (admin only)"""
    db_config = content_lock_config_crud.create_lock_config(
        db=db,
        config_data=lock_config,
        created_by_admin_id=current_admin.id
    )
    return db_config


@router.get("/admin/content/locks", response_model=List[ContentLockConfigResponse])
async def get_content_locks(
    skip: int = 0,
    limit: int = 100,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Get all content lock configurations (admin only)"""
    locks = content_lock_config_crud.get_locked_content(
        db=db,
        skip=skip,
        limit=limit
    )
    return locks


@router.put("/admin/content/locks/{lock_id}", response_model=ContentLockConfigResponse)
async def update_content_lock(
    lock_id: int,
    lock_update: ContentLockConfigUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Update content lock configuration (admin only)"""
    lock_config = content_lock_config_crud.get(db=db, id=lock_id)
    if not lock_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content lock configuration not found"
        )
    
    updated_config = content_lock_config_crud.update(
        db=db,
        db_obj=lock_config,
        obj_in=lock_update
    )
    return updated_config


@router.post("/admin/content/bulk-lock")
async def bulk_update_content_locks(
    bulk_update: BulkContentLockUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Bulk update content lock configurations (admin only)"""
    try:
        content_items = [item.model_dump() for item in bulk_update.content_items]
        
        results = content_lock_config_crud.bulk_update_locks(
            db=db,
            content_items=content_items,
            admin_id=current_admin.id
        )
        
        return {
            "message": f"Successfully updated {len(results)} content lock configurations",
            "updated_items": len(results)
        }
        
    except Exception as e:
        logger.error(f"Failed to bulk update content locks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update content locks"
        )


@router.post("/admin/content/grant-access")
async def bulk_grant_content_access(
    bulk_grant: BulkContentAccessGrant,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Bulk grant content access (admin only)"""
    try:
        granted_count = 0
        
        for user_id in bulk_grant.user_ids:
            for content_item in bulk_grant.content_items:
                content_access_crud.grant_access(
                    db=db,
                    user_id=user_id,
                    content_type=content_item.content_type,
                    content_identifier=content_item.content_identifier,
                    granted_by_admin_id=current_admin.id,
                    access_data=content_item
                )
                granted_count += 1
        
        return {
            "message": f"Successfully granted access to {granted_count} content items",
            "granted_items": granted_count
        }
        
    except Exception as e:
        logger.error(f"Failed to bulk grant content access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to grant content access"
        )


@router.post("/admin/refunds", response_model=RefundResponse)
async def create_refund(
    refund_data: RefundCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Create a refund (admin only)"""
    try:
        # Get payment
        payment = payment_crud.get(db=db, id=refund_data.payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Create refund record
        db_refund = refund_crud.create_refund(
            db=db,
            refund_data=refund_data,
            requested_by_admin_id=current_admin.id
        )
        
        # Process refund with PayPal
        if payment.paypal_capture_id:
            paypal_refund = await paypal_service.create_refund(
                capture_id=payment.paypal_capture_id,
                amount=refund_data.amount,
                currency=payment.currency,
                note=refund_data.reason
            )
            
            # Update refund with PayPal refund ID
            refund_crud.update_refund_status(
                db=db,
                refund_id=db_refund.id,
                status="completed",
                paypal_refund_id=paypal_refund.get("id")
            )
            
            # Update payment status
            payment_crud.update_payment_status(
                db=db,
                payment_id=payment.id,
                status=PaymentStatus.REFUNDED
            )
        
        return db_refund
        
    except Exception as e:
        logger.error(f"Failed to create refund: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create refund"
        )


# Webhook Endpoints
@router.post("/webhooks/paypal")
async def handle_paypal_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_sync_db)
):
    """Handle PayPal webhook events"""
    try:
        # Get request body and headers
        body = await request.body()
        headers = dict(request.headers)
        
        # Parse webhook payload
        import json
        payload = json.loads(body.decode())
        
        # Verify webhook signature
        webhook_id = settings.PAYPAL_WEBHOOK_ID
        if webhook_id:
            is_valid = await paypal_service.verify_webhook_signature(
                webhook_id=webhook_id,
                headers=headers,
                body=body.decode()
            )
            
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid webhook signature"
                )
        
        # Create webhook record
        webhook_data = PaymentWebhookCreate(
            webhook_id=webhook_id or "unknown",
            event_type=payload.get("event_type", "unknown"),
            resource_type=payload.get("resource_type", "unknown"),
            paypal_event_id=payload.get("id", "unknown"),
            paypal_resource_id=payload.get("resource", {}).get("id"),
            payload=payload,
            headers=headers
        )
        
        webhook_record = payment_webhook_crud.create_webhook_event(
            db=db,
            webhook_data=webhook_data
        )
        
        # Process webhook in background
        background_tasks.add_task(
            process_paypal_webhook,
            webhook_record.id,
            payload
        )
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Failed to handle PayPal webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


async def process_paypal_webhook(webhook_id: int, payload: Dict[str, Any]):
    """Process PayPal webhook event in background"""
    try:
        # This would contain the logic to process different webhook events
        # For now, we'll just mark it as processed
        
        # Get database session
        from app.core.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Mark webhook as processed
            payment_webhook_crud.mark_processed(
                db=db,
                webhook_id=webhook_id
            )
            
            logger.info(f"Processed PayPal webhook {webhook_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to process PayPal webhook {webhook_id}: {e}")


# Settings Endpoints
@router.get("/settings")
async def get_payment_settings(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Get payment system settings (admin only)"""
    payment_settings = settings_crud.get_payment_settings(db)
    return {
        "payment_enabled": payment_settings.get("payment_enabled", False),
        "content_lock_enabled": payment_settings.get("content_lock_enabled", False),
        "free_cefr_levels": payment_settings.get("free_cefr_levels", ["A1"]),
        "free_modules": payment_settings.get("free_modules", ["reading"]),
        "free_lessons_quota": payment_settings.get("free_lessons_quota", 7),
        "payment_currency": settings.PAYMENT_CURRENCY,
        "paypal_mode": settings.PAYPAL_MODE
    }


@router.put("/settings")
async def update_payment_settings(
    content_lock_enabled: Optional[bool] = None,
    free_cefr_levels: Optional[List[str]] = None,
    free_modules: Optional[List[str]] = None,
    free_lessons_quota: Optional[int] = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db)
):
    """Update payment system settings (admin only)"""
    if content_lock_enabled is not None:
        settings_crud.set_value(
            db,
            SettingCategory.PAYMENT.value,
            "content_lock_enabled",
            content_lock_enabled,
        )
    if free_cefr_levels is not None:
        settings_crud.set_value(
            db,
            SettingCategory.PAYMENT.value,
            "free_cefr_levels",
            free_cefr_levels,
        )
    if free_modules is not None:
        settings_crud.set_value(
            db,
            SettingCategory.PAYMENT.value,
            "free_modules",
            free_modules,
        )
    if free_lessons_quota is not None:
        settings_crud.set_value(
            db,
            SettingCategory.PAYMENT.value,
            "free_lessons_quota",
            free_lessons_quota,
        )

    updated = settings_crud.get_payment_settings(db)
    return {
        "payment_enabled": updated.get("payment_enabled", False),
        "content_lock_enabled": updated.get("content_lock_enabled", False),
        "free_cefr_levels": updated.get("free_cefr_levels", ["A1"]),
        "free_modules": updated.get("free_modules", ["reading"]),
        "free_lessons_quota": updated.get("free_lessons_quota", 7),
        "message": "Settings updated successfully",
    }