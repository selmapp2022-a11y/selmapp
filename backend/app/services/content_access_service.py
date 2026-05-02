from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func as sa_func
from app.models.user import User
from app.models.content import Content, DifficultyLevel
from app.models.lessons import LessonProgress
from app.models.progress import DayCompletionRecord
from app.models.settings import SettingCategory
from app.crud.settings import settings_crud
from app.crud.payment import subscription_crud
import logging

logger = logging.getLogger(__name__)

class ContentAccessService:
    """Service to handle content access control based on payment settings"""
    
    def __init__(self):
        self.free_cefr_levels_default = ["A1"]
        self.free_modules_default = ["reading"]
        self.free_lessons_quota_default = 7
    
    def is_payment_enabled(self, db: Session) -> bool:
        """Check if payment system is enabled"""
        return settings_crud.get_value(db, SettingCategory.PAYMENT.value, "payment_enabled", False)
    
    def is_content_lock_enabled(self, db: Session) -> bool:
        """Check if content locking is enabled"""
        return settings_crud.get_value(db, SettingCategory.PAYMENT.value, "content_lock_enabled", False)
    
    def get_free_cefr_levels(self, db: Session) -> List[str]:
        """Get CEFR levels available to free users"""
        return settings_crud.get_value(db, SettingCategory.PAYMENT.value, "free_cefr_levels", self.free_cefr_levels_default)
    
    def get_free_modules(self, db: Session) -> List[str]:
        """Get learning modules available to free users"""
        return settings_crud.get_value(db, SettingCategory.PAYMENT.value, "free_modules", self.free_modules_default)

    def get_free_lessons_quota(self, db: Session) -> int:
        """Get number of free completed lessons allowed before requiring payment."""
        value = settings_crud.get_value(
            db,
            SettingCategory.PAYMENT.value,
            "free_lessons_quota",
            self.free_lessons_quota_default,
        )
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return self.free_lessons_quota_default

    @staticmethod
    def _normalize_enum_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    def get_completed_lessons_count(self, db: Session, user: User) -> int:
        """Count completed lessons across both journey days and AI lesson sessions."""
        day_count = (
            db.query(sa_func.count(DayCompletionRecord.id))
            .filter(DayCompletionRecord.user_id == user.id)
            .scalar()
            or 0
        )
        ai_lesson_count = (
            db.query(sa_func.count(LessonProgress.id))
            .filter(
                and_(
                    LessonProgress.user_id == user.id,
                    LessonProgress.is_completed == True,
                )
            )
            .scalar()
            or 0
        )
        return int(day_count) + int(ai_lesson_count)
    
    def user_has_premium_access(self, db: Session, user: User) -> bool:
        """Check if user has premium access"""
        if not self.is_payment_enabled(db):
            return True  # If payment is disabled, everyone has premium access
        
        # Check if user has premium subscription
        if user.is_premium:
            return True
        
        # Check if user has active subscription
        active_subscription = subscription_crud.get_user_active_subscription(db=db, user_id=user.id)
        if active_subscription:
            return True
        
        return False
    
    def can_start_new_lesson(
        self,
        db: Session,
        user: User,
        *,
        module: Optional[str] = None,
        cefr_level: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Hybrid access check for lesson/content delivery:
        1) CEFR/module free access rules
        2) free lesson quota rule
        """
        if not self.is_content_lock_enabled(db):
            return True, "Content locking disabled"

        if getattr(user, "is_admin", False):
            return True, "Admin access"

        if self.user_has_premium_access(db, user):
            return True, "Premium access"

        normalized_level = self._normalize_enum_value(cefr_level)
        normalized_module = self._normalize_enum_value(module)

        if normalized_level:
            free_levels = self.get_free_cefr_levels(db)
            if normalized_level not in free_levels:
                return False, f"CEFR level {normalized_level} requires premium subscription"

        if normalized_module:
            free_modules = self.get_free_modules(db)
            if normalized_module not in free_modules:
                return False, f"Module {normalized_module} requires premium subscription"

        free_quota = self.get_free_lessons_quota(db)
        completed_lessons = self.get_completed_lessons_count(db, user)
        if completed_lessons >= free_quota:
            return (
                False,
                f"Free lesson quota reached ({completed_lessons}/{free_quota}). Premium subscription required",
            )

        return True, "Free access allowed"

    def can_access_content(self, db: Session, user: User, content: Content) -> tuple[bool, str]:
        """
        Check if user can access specific content
        Returns (can_access, reason)
        """
        cefr_level = getattr(content, "cefr_level", None)
        if cefr_level is None:
            cefr_level = getattr(content, "difficulty_level", None)

        module = getattr(content, "content_type", None)

        return self.can_start_new_lesson(
            db,
            user,
            module=module,
            cefr_level=cefr_level,
        )
    
    def can_access_cefr_level(self, db: Session, user: User, cefr_level: str) -> tuple[bool, str]:
        """Check if user can access specific CEFR level"""
        return self.can_start_new_lesson(db, user, cefr_level=cefr_level)
    
    def can_access_module(self, db: Session, user: User, module: str) -> tuple[bool, str]:
        """Check if user can access specific learning module"""
        return self.can_start_new_lesson(db, user, module=module)
    
    def get_accessible_content_filter(self, db: Session, user: User) -> Dict[str, Any]:
        """Get filter conditions for accessible content"""
        if not self.is_content_lock_enabled(db):
            return {}  # No filtering needed
        
        if getattr(user, 'is_admin', False) or self.user_has_premium_access(db, user):
            return {}  # No filtering needed for premium users
        
        # Build filter for free users
        free_levels = self.get_free_cefr_levels(db)
        free_modules = self.get_free_modules(db)
        
        return {
            "cefr_level": free_levels,
            "content_type": free_modules
        }
    
    def get_user_access_summary(self, db: Session, user: User) -> Dict[str, Any]:
        """Get summary of user's access permissions"""
        payment_enabled = self.is_payment_enabled(db)
        content_lock_enabled = self.is_content_lock_enabled(db)
        has_premium = self.user_has_premium_access(db, user)
        is_admin = getattr(user, 'is_admin', False)
        
        if not payment_enabled:
            access_level = "full"
            reason = "Payment system disabled"
        elif is_admin:
            access_level = "full"
            reason = "Admin access"
        elif has_premium:
            access_level = "full"
            reason = "Premium subscription"
        elif not content_lock_enabled:
            access_level = "full"
            reason = "Content locking disabled"
        else:
            access_level = "limited"
            reason = "Free user with content restrictions"
        
        return {
            "access_level": access_level,
            "reason": reason,
            "payment_enabled": payment_enabled,
            "content_lock_enabled": content_lock_enabled,
            "has_premium": has_premium,
            "is_admin": is_admin,
            "free_cefr_levels": self.get_free_cefr_levels(db) if access_level == "limited" else None,
            "free_modules": self.get_free_modules(db) if access_level == "limited" else None,
            "free_lessons_quota": self.get_free_lessons_quota(db) if access_level == "limited" else None,
            "completed_lessons": self.get_completed_lessons_count(db, user) if access_level == "limited" else None,
        }

# Create service instance
content_access_service = ContentAccessService() 