import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func, select, and_, or_, case, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.api.deps import (
    get_db,
    get_sync_db,
    get_current_admin_user,
    get_developer_admin_user,
    get_owner_admin_user,
)
from app.models.user import User
from app.models.progress import (
    UserProgress,
    DailyProgress,
    DayCompletionRecord,
    UserWeeklyProgress,
)
from app.models.exercise import ExerciseAttempt
from app.models.payment import Payment, PaymentStatus
from app.models.lessons import AIGeneratedLesson, LessonProgress
from app.models.personalization import UserLearningProfile, UserOnboarding
from app.models.settings import SettingCategory
from app.crud.settings import settings_crud
from app.crud.user import user_crud
from app.schemas.admin import (
    SystemStats,
    AdminUserListItem,
    AdminUserDetail,
    AdminUserUpdate,
    AdminUserListResponse,
    UserActivityReport,
    UserActivityListResponse,
    ContentStats,
    AdminDashboard,
    UserActivitySummary,
    SystemReport,
)
from app.schemas.settings import (
    AppSettingsResponse,
    PaymentSettingsUpdate,
    PaymentSettingsResponse,
    ContentSettingsUpdate,
    ContentSettingsResponse,
    FeatureSettingsUpdate,
    FeatureSettingsResponse,
    AllSettingsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_owner_admin(current_admin: User) -> bool:
    return str(getattr(current_admin, "admin_role", "") or "") == "owner"


def _visible_user_condition(current_admin: Optional[User]):
    if current_admin and _is_owner_admin(current_admin):
        return or_(User.admin_role.is_(None), User.admin_role != "developer")
    return None


def _apply_user_visibility_filter(query, current_admin: Optional[User]):
    condition = _visible_user_condition(current_admin)
    if condition is not None:
        return query.where(condition)
    return query


def _ensure_admin_can_access_user(current_admin: User, target_user: User) -> None:
    if _is_owner_admin(current_admin) and str(getattr(target_user, "admin_role", "") or "") == "developer":
        raise HTTPException(status_code=404, detail="User not found")


# ═══════════════════════════════════════════════════════════════════════
# Dashboard & System Stats  (async — uses the async session)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=AdminDashboard)
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """Get the full admin dashboard with system stats, content stats, recent users, and daily activity."""
    system_stats = await _compute_system_stats(db, current_admin=current_admin)
    content_stats = await _compute_content_stats(db)
    recent_users = await _get_recent_users(db, current_admin=current_admin, limit=10)
    daily_activity = await _get_daily_activity(db, days=7, current_admin=current_admin)

    return AdminDashboard(
        system_stats=system_stats,
        content_stats=content_stats,
        recent_users=recent_users,
        daily_activity=daily_activity,
    )


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """Get system-wide statistics."""
    return await _compute_system_stats(db, current_admin=current_admin)


@router.get("/reports", response_model=SystemReport)
async def get_system_report(
    period: str = Query("weekly", regex="^(daily|weekly|monthly)$"),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """Generate a system report for a given period."""
    days_map = {"daily": 1, "weekly": 7, "monthly": 30}
    days = days_map.get(period, 7)
    stats = await _compute_system_stats(db, current_admin=current_admin)
    daily_activity = await _get_daily_activity(db, days=days, current_admin=current_admin)

    return SystemReport(
        generated_at=datetime.utcnow(),
        period=period,
        stats=stats,
        daily_activity=daily_activity,
    )


# ═══════════════════════════════════════════════════════════════════════
# User Management  (async)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_premium: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    level: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|email|username|last_login)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """List users with search, filter, and pagination."""
    # Build base query
    query = select(User).where(User.deleted_at.is_(None))
    query = _apply_user_visibility_filter(query, current_admin)

    # Apply filters
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                User.email.ilike(search_term),
                User.username.ilike(search_term),
                User.full_name.ilike(search_term),
            )
        )
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if is_premium is not None:
        query = query.where(User.is_premium == is_premium)
    if is_admin is not None:
        query = query.where(User.is_admin == is_admin)
    if level:
        query = query.where(cast(User.current_level, String) == level)

    # Count total
    count_query = select(sa_func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply sorting
    sort_col = getattr(User, sort_by, User.created_at)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

    # Pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    users = result.scalars().all()

    return AdminUserListResponse(
        users=[AdminUserListItem.model_validate(u) for u in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """Get detailed user info including progress summary."""
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_admin_can_access_user(current_admin, user)

    # Build the detail dict from user model
    detail_data = AdminUserDetail.model_validate(user)

    # Fetch progress summary
    progress_query = select(UserProgress).where(UserProgress.user_id == user_id)
    progress_result = await db.execute(progress_query)
    progress = progress_result.scalars().first()

    if progress:
        detail_data.total_study_time_minutes = progress.total_study_time_minutes or 0
        detail_data.total_exercises_completed = progress.total_exercises_completed or 0
        detail_data.average_accuracy = progress.average_accuracy or 0.0
        detail_data.current_streak_days = progress.current_streak_days or 0

    return detail_data


@router.put("/users/{user_id}", response_model=AdminUserDetail)
async def update_user(
    user_id: int,
    user_update: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_owner_admin_user),
):
    """Update a user's profile (owner or developer admins only)."""
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_admin_can_access_user(current_admin, user)

    # Prevent non-developer admins from granting admin privileges
    if user_update.is_admin is not None or user_update.admin_role is not None:
        if current_admin.admin_role != "developer":
            raise HTTPException(
                status_code=403,
                detail="Only developer admins can change admin privileges",
            )

    update_data = user_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated_user = await user_crud.update(db, db_obj=user, obj_in=update_data)
    return await get_user_detail(user_id, db, current_admin)


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_owner_admin_user),
):
    """Deactivate a user account (soft — sets is_active=False)."""
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_admin_can_access_user(current_admin, user)

    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot deactivate an admin user")

    await user_crud.update(db, db_obj=user, obj_in={"is_active": False})
    return {"message": f"User {user_id} deactivated"}


@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_owner_admin_user),
):
    """Re-activate a previously deactivated user account."""
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _ensure_admin_can_access_user(current_admin, user)

    await user_crud.update(db, db_obj=user, obj_in={"is_active": True})
    return {"message": f"User {user_id} activated"}


# ═══════════════════════════════════════════════════════════════════════
# User Activity Reports  (async)
# ═══════════════════════════════════════════════════════════════════════

@router.get("/activity-reports", response_model=UserActivityListResponse)
async def get_user_activity_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("last_login", regex="^(last_login|total_exercises_completed|average_accuracy)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    """Get activity reports for all users."""
    # Subquery for progress stats
    progress_sq = (
        select(
            UserProgress.user_id,
            UserProgress.total_study_time_minutes,
            UserProgress.total_exercises_completed,
            UserProgress.average_accuracy,
            UserProgress.current_streak_days,
            UserProgress.last_study_date,
        )
        .subquery()
    )

    query = (
        select(
            User.id,
            User.email,
            User.username,
            User.last_login,
            User.onboarding_completed,
            cast(User.current_level, String).label("current_level"),
            progress_sq.c.total_study_time_minutes,
            progress_sq.c.total_exercises_completed,
            progress_sq.c.average_accuracy,
            progress_sq.c.current_streak_days,
            progress_sq.c.last_study_date,
        )
        .outerjoin(progress_sq, User.id == progress_sq.c.user_id)
        .where(User.deleted_at.is_(None))
    )
    query = _apply_user_visibility_filter(query, current_admin)

    # Count total
    count_base = select(User.id).where(User.deleted_at.is_(None))
    count_base = _apply_user_visibility_filter(count_base, current_admin)
    count_query = select(sa_func.count()).select_from(count_base.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sorting
    sort_mapping = {
        "last_login": User.last_login,
        "total_exercises_completed": progress_sq.c.total_exercises_completed,
        "average_accuracy": progress_sq.c.average_accuracy,
    }
    sort_col = sort_mapping.get(sort_by, User.last_login)
    if sort_col is not None:
        query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    activities = []
    for row in rows:
        # Count completed lessons for each user
        lesson_count_q = select(sa_func.count()).where(
            and_(
                LessonProgress.user_id == row.id,
                LessonProgress.is_completed == True,
            )
        )
        lesson_result = await db.execute(lesson_count_q)
        lessons_completed = lesson_result.scalar() or 0

        activities.append(
            UserActivityReport(
                user_id=row.id,
                email=row.email,
                username=row.username,
                total_study_time_minutes=row.total_study_time_minutes or 0,
                total_exercises_completed=row.total_exercises_completed or 0,
                average_accuracy=row.average_accuracy or 0.0,
                current_streak_days=row.current_streak_days or 0,
                last_login=row.last_login,
                last_study_date=row.last_study_date,
                lessons_completed=lessons_completed,
                onboarding_completed=row.onboarding_completed or False,
                current_level=row.current_level,
            )
        )

    return UserActivityListResponse(
        activities=activities,
        total=total,
        page=page,
        per_page=per_page,
    )


# ═══════════════════════════════════════════════════════════════════════
# Settings Management  (sync — uses get_sync_db like the original)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/initialize-settings")
async def initialize_default_settings(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Initialize default application settings (admin only)"""
    try:
        settings_crud.initialize_default_settings(db)
        return {"message": "Default settings initialized successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize settings: {str(e)}",
        )


@router.get("/settings/payment", response_model=PaymentSettingsResponse)
async def get_payment_settings(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Get payment settings (admin only)"""
    try:
        payment_settings = settings_crud.get_payment_settings(db)
        return PaymentSettingsResponse(
            payment_enabled=payment_settings.get("payment_enabled", False),
            content_lock_enabled=payment_settings.get("content_lock_enabled", False),
            free_cefr_levels=payment_settings.get("free_cefr_levels", ["A1"]),
            free_modules=payment_settings.get("free_modules", ["reading"]),
            free_lessons_quota=payment_settings.get("free_lessons_quota", 7),
            premium_price_monthly=payment_settings.get("premium_price_monthly", 9.99),
            premium_price_yearly=payment_settings.get("premium_price_yearly", 99.99),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get payment settings: {str(e)}",
        )


@router.put("/settings/payment", response_model=PaymentSettingsResponse)
async def update_payment_settings(
    settings_update: PaymentSettingsUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Update payment settings (admin only)"""
    try:
        if settings_update.payment_enabled is not None:
            settings_crud.set_value(
                db, SettingCategory.PAYMENT.value, "payment_enabled",
                settings_update.payment_enabled,
            )
        if settings_update.content_lock_enabled is not None:
            settings_crud.set_value(
                db, SettingCategory.PAYMENT.value, "content_lock_enabled",
                settings_update.content_lock_enabled,
            )
        if settings_update.free_cefr_levels is not None:
            settings_crud.set_value(
                db, SettingCategory.PAYMENT.value, "free_cefr_levels",
                settings_update.free_cefr_levels,
            )
        if settings_update.free_modules is not None:
            settings_crud.set_value(
                db, SettingCategory.PAYMENT.value, "free_modules",
                settings_update.free_modules,
            )
        if settings_update.free_lessons_quota is not None:
            settings_crud.set_value(
                db, SettingCategory.PAYMENT.value, "free_lessons_quota",
                settings_update.free_lessons_quota,
            )
        if settings_update.premium_price_monthly is not None:
            settings_crud.set_value(
                db, SettingCategory.PAYMENT.value, "premium_price_monthly",
                settings_update.premium_price_monthly,
            )
        if settings_update.premium_price_yearly is not None:
            settings_crud.set_value(
                db, SettingCategory.PAYMENT.value, "premium_price_yearly",
                settings_update.premium_price_yearly,
            )
        return await get_payment_settings(current_admin, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment settings: {str(e)}",
        )


@router.get("/settings/content", response_model=ContentSettingsResponse)
async def get_content_settings(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Get content settings (admin only)"""
    try:
        content_settings = settings_crud.get_content_settings(db)
        return ContentSettingsResponse(
            max_daily_exercises=content_settings.get("max_daily_exercises", 50),
            ai_feedback_enabled=content_settings.get("ai_feedback_enabled", True),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get content settings: {str(e)}",
        )


@router.put("/settings/content", response_model=ContentSettingsResponse)
async def update_content_settings(
    settings_update: ContentSettingsUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Update content settings (admin only)"""
    try:
        if settings_update.max_daily_exercises is not None:
            settings_crud.set_value(
                db, SettingCategory.CONTENT.value, "max_daily_exercises",
                settings_update.max_daily_exercises,
            )
        if settings_update.ai_feedback_enabled is not None:
            settings_crud.set_value(
                db, SettingCategory.CONTENT.value, "ai_feedback_enabled",
                settings_update.ai_feedback_enabled,
            )
        return await get_content_settings(current_admin, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update content settings: {str(e)}",
        )


@router.get("/settings/features", response_model=FeatureSettingsResponse)
async def get_feature_settings(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Get feature settings (admin only)"""
    try:
        feature_settings = settings_crud.get_by_category(db, SettingCategory.FEATURES.value)
        settings_dict = {
            setting.key: settings_crud._parse_value(setting.value, setting.value_type)
            for setting in feature_settings
        }
        return FeatureSettingsResponse(
            speech_recognition_enabled=settings_dict.get("speech_recognition_enabled", True),
            gamification_enabled=settings_dict.get("gamification_enabled", True),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get feature settings: {str(e)}",
        )


@router.put("/settings/features", response_model=FeatureSettingsResponse)
async def update_feature_settings(
    settings_update: FeatureSettingsUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Update feature settings (admin only)"""
    try:
        if settings_update.speech_recognition_enabled is not None:
            settings_crud.set_value(
                db, SettingCategory.FEATURES.value, "speech_recognition_enabled",
                settings_update.speech_recognition_enabled,
            )
        if settings_update.gamification_enabled is not None:
            settings_crud.set_value(
                db, SettingCategory.FEATURES.value, "gamification_enabled",
                settings_update.gamification_enabled,
            )
        return await get_feature_settings(current_admin, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update feature settings: {str(e)}",
        )


@router.get("/settings/all", response_model=AllSettingsResponse)
async def get_all_settings(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Get all application settings (admin only)"""
    try:
        payment_settings = await get_payment_settings(current_admin, db)
        content_settings = await get_content_settings(current_admin, db)
        feature_settings = await get_feature_settings(current_admin, db)
        return AllSettingsResponse(
            payment=payment_settings,
            content=content_settings,
            features=feature_settings,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get all settings: {str(e)}",
        )


@router.get("/settings/raw", response_model=List[AppSettingsResponse])
async def get_all_raw_settings(
    category: str = None,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Get raw settings data (admin only)"""
    try:
        if category:
            settings = settings_crud.get_by_category(db, category)
        else:
            settings = (
                db.query(settings_crud.model)
                .filter(settings_crud.model.is_active == True)
                .order_by(settings_crud.model.category, settings_crud.model.key)
                .all()
            )
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get raw settings: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════════
# Payment System Control  (sync)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/payment/enable")
async def enable_payment_system(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Enable the payment system (admin only)"""
    try:
        settings_crud.set_value(db, SettingCategory.PAYMENT.value, "payment_enabled", True)
        return {"message": "Payment system enabled successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable payment system: {str(e)}",
        )


@router.post("/payment/disable")
async def disable_payment_system(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Disable the payment system (admin only)"""
    try:
        settings_crud.set_value(db, SettingCategory.PAYMENT.value, "payment_enabled", False)
        settings_crud.set_value(db, SettingCategory.PAYMENT.value, "content_lock_enabled", False)
        return {"message": "Payment system disabled successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable payment system: {str(e)}",
        )


@router.post("/content/lock/enable")
async def enable_content_locking(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Enable content locking (admin only)"""
    try:
        payment_enabled = settings_crud.get_value(
            db, SettingCategory.PAYMENT.value, "payment_enabled", False
        )
        if not payment_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment system must be enabled before enabling content locking",
            )
        settings_crud.set_value(db, SettingCategory.PAYMENT.value, "content_lock_enabled", True)
        return {"message": "Content locking enabled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable content locking: {str(e)}",
        )


@router.post("/content/lock/disable")
async def disable_content_locking(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_sync_db),
):
    """Disable content locking (admin only)"""
    try:
        settings_crud.set_value(db, SettingCategory.PAYMENT.value, "content_lock_enabled", False)
        return {"message": "Content locking disabled successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable content locking: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════

async def _compute_system_stats(db: AsyncSession, current_admin: Optional[User] = None) -> SystemStats:
    """Compute aggregate system statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    thirty_days_ago = now - timedelta(days=30)

    visibility_condition = _visible_user_condition(current_admin)

    def _visible_user_predicate(extra=None):
        clauses = [User.deleted_at.is_(None)]
        if visibility_condition is not None:
            clauses.append(visibility_condition)
        if extra is not None:
            clauses.append(extra)
        return and_(*clauses)

    # Total users (not deleted)
    total_q = select(sa_func.count()).where(_visible_user_predicate())
    total_users = (await db.execute(total_q)).scalar() or 0

    # Active users (logged in within 30 days)
    active_q = select(sa_func.count()).where(_visible_user_predicate(User.last_login >= thirty_days_ago))
    active_users = (await db.execute(active_q)).scalar() or 0

    # Premium users
    premium_q = select(sa_func.count()).where(_visible_user_predicate(User.is_premium == True))
    premium_users = (await db.execute(premium_q)).scalar() or 0

    # New users today / this week / this month
    new_today_q = select(sa_func.count()).where(_visible_user_predicate(User.created_at >= today_start))
    new_today = (await db.execute(new_today_q)).scalar() or 0

    new_week_q = select(sa_func.count()).where(_visible_user_predicate(User.created_at >= week_start))
    new_week = (await db.execute(new_week_q)).scalar() or 0

    new_month_q = select(sa_func.count()).where(_visible_user_predicate(User.created_at >= month_start))
    new_month = (await db.execute(new_month_q)).scalar() or 0

    # Total lessons generated
    lessons_q = select(sa_func.count()).select_from(AIGeneratedLesson)
    if visibility_condition is not None:
        lessons_q = (
            lessons_q
            .join(User, User.id == AIGeneratedLesson.user_id)
            .where(_visible_user_predicate())
        )
    total_lessons = (await db.execute(lessons_q)).scalar() or 0

    # Total exercises completed
    exercises_q = select(sa_func.count()).select_from(ExerciseAttempt)
    if visibility_condition is not None:
        exercises_q = (
            exercises_q
            .join(User, User.id == ExerciseAttempt.user_id)
            .where(_visible_user_predicate())
        )
    total_exercises = (await db.execute(exercises_q)).scalar() or 0

    # Average accuracy across all attempts
    avg_acc_q = select(sa_func.avg(ExerciseAttempt.score))
    if visibility_condition is not None:
        avg_acc_q = (
            avg_acc_q
            .join(User, User.id == ExerciseAttempt.user_id)
            .where(_visible_user_predicate())
        )
    avg_accuracy = (await db.execute(avg_acc_q)).scalar() or 0.0

    # Total payments and revenue from completed payments
    payments_count_q = select(sa_func.count()).select_from(Payment).where(
        Payment.status == PaymentStatus.COMPLETED
    )
    total_payments = (await db.execute(payments_count_q)).scalar() or 0

    revenue_q = select(sa_func.coalesce(sa_func.sum(Payment.amount), 0)).where(
        Payment.status == PaymentStatus.COMPLETED
    )
    total_revenue = float((await db.execute(revenue_q)).scalar() or 0.0)

    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        premium_users=premium_users,
        new_users_today=new_today,
        new_users_this_week=new_week,
        new_users_this_month=new_month,
        total_lessons_generated=total_lessons,
        total_exercises_completed=total_exercises,
        average_accuracy=round(float(avg_accuracy), 4),
        total_payments=total_payments,
        total_revenue=total_revenue,
    )


async def _compute_content_stats(db: AsyncSession) -> ContentStats:
    """Compute content-related statistics."""
    total_lessons_q = select(sa_func.count()).select_from(AIGeneratedLesson)
    total_ai_lessons = (await db.execute(total_lessons_q)).scalar() or 0

    # Lessons by type
    type_q = (
        select(
            cast(AIGeneratedLesson.lesson_type, String).label("lt"),
            sa_func.count().label("cnt"),
        )
        .group_by(AIGeneratedLesson.lesson_type)
    )
    type_result = await db.execute(type_q)
    lessons_by_type = {str(row.lt): row.cnt for row in type_result.all()}

    # Lessons by level
    level_q = (
        select(
            AIGeneratedLesson.difficulty_level,
            sa_func.count().label("cnt"),
        )
        .group_by(AIGeneratedLesson.difficulty_level)
    )
    level_result = await db.execute(level_q)
    lessons_by_level = {str(row.difficulty_level): row.cnt for row in level_result.all()}

    return ContentStats(
        total_ai_lessons=total_ai_lessons,
        total_reading_texts=lessons_by_type.get("reading", 0),
        total_vocabulary_sets=lessons_by_type.get("vocabulary", 0),
        lessons_by_type=lessons_by_type,
        lessons_by_level=lessons_by_level,
    )


async def _get_recent_users(
    db: AsyncSession,
    current_admin: Optional[User] = None,
    limit: int = 10,
) -> List[AdminUserListItem]:
    """Get most recently registered users."""
    query = (
        select(User)
        .where(User.deleted_at.is_(None))
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    query = _apply_user_visibility_filter(query, current_admin)
    result = await db.execute(query)
    users = result.scalars().all()
    return [AdminUserListItem.model_validate(u) for u in users]


async def _get_daily_activity(
    db: AsyncSession,
    days: int = 7,
    current_admin: Optional[User] = None,
) -> List[UserActivitySummary]:
    """Get daily activity summary for the last N days."""
    now = datetime.utcnow()
    activity: List[UserActivitySummary] = []
    visibility_condition = _visible_user_condition(current_admin)

    def _visible_user_predicate(extra=None):
        clauses = []
        if visibility_condition is not None:
            clauses.append(visibility_condition)
        if extra is not None:
            clauses.append(extra)
        if not clauses:
            return None
        return and_(*clauses)

    for i in range(days):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Active users that day (logged in)
        active_q = select(sa_func.count()).where(and_(User.last_login >= day_start, User.last_login < day_end))
        active_predicate = _visible_user_predicate()
        if active_predicate is not None:
            active_q = active_q.where(active_predicate)
        active = (await db.execute(active_q)).scalar() or 0

        # New registrations
        new_q = select(sa_func.count()).where(and_(User.created_at >= day_start, User.created_at < day_end))
        new_predicate = _visible_user_predicate()
        if new_predicate is not None:
            new_q = new_q.where(new_predicate)
        new_reg = (await db.execute(new_q)).scalar() or 0

        # Lessons completed
        lessons_q = select(sa_func.count()).where(
            and_(
                LessonProgress.is_completed == True,
                LessonProgress.completed_at >= day_start,
                LessonProgress.completed_at < day_end,
            )
        )
        lesson_predicate = _visible_user_predicate()
        if lesson_predicate is not None:
            lessons_q = lessons_q.join(User, User.id == LessonProgress.user_id).where(lesson_predicate)
        lessons = (await db.execute(lessons_q)).scalar() or 0

        # Exercises completed
        exercises_q = select(sa_func.count()).where(
            and_(
                ExerciseAttempt.created_at >= day_start,
                ExerciseAttempt.created_at < day_end,
            )
        )
        exercise_predicate = _visible_user_predicate()
        if exercise_predicate is not None:
            exercises_q = exercises_q.join(User, User.id == ExerciseAttempt.user_id).where(exercise_predicate)
        exercises = (await db.execute(exercises_q)).scalar() or 0

        activity.append(
            UserActivitySummary(
                date=day_start.strftime("%Y-%m-%d"),
                active_users=active,
                new_registrations=new_reg,
                lessons_completed=lessons,
                exercises_completed=exercises,
            )
        )

    return activity
