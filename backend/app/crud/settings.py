from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.crud.base import CRUDBase
from app.models.settings import AppSettings, SettingCategory
from app.schemas.settings import AppSettingsCreate, AppSettingsUpdate
import json

class CRUDSettings(CRUDBase[AppSettings, AppSettingsCreate, AppSettingsUpdate]):
    
    def get_by_key(self, db: Session, category: str, key: str) -> Optional[AppSettings]:
        """Get a setting by category and key"""
        return db.query(AppSettings).filter(
            and_(
                AppSettings.category == category,
                AppSettings.key == key,
                AppSettings.is_active == True
            )
        ).first()
    
    def get_by_category(self, db: Session, category: str) -> List[AppSettings]:
        """Get all settings in a category"""
        return db.query(AppSettings).filter(
            and_(
                AppSettings.category == category,
                AppSettings.is_active == True
            )
        ).order_by(AppSettings.key).all()
    
    def get_value(self, db: Session, category: str, key: str, default: Any = None) -> Any:
        """Get the parsed value of a setting"""
        setting = self.get_by_key(db, category, key)
        if not setting:
            return default
        
        return self._parse_value(setting.value, setting.value_type)
    
    def set_value(self, db: Session, category: str, key: str, value: Any, 
                  display_name: Optional[str] = None, description: Optional[str] = None) -> AppSettings:
        """Set a setting value, creating if it doesn't exist"""
        setting = self.get_by_key(db, category, key)
        
        # Determine value type and convert to string
        value_type, str_value = self._serialize_value(value)
        
        if setting:
            # Update existing setting
            setting.value = str_value
            setting.value_type = value_type
            if display_name:
                setting.display_name = display_name
            if description:
                setting.description = description
            db.commit()
            db.refresh(setting)
        else:
            # Create new setting
            setting_data = AppSettingsCreate(
                category=category,
                key=key,
                value=str_value,
                value_type=value_type,
                display_name=display_name or key.replace('_', ' ').title(),
                description=description
            )
            setting = self.create(db, obj_in=setting_data)
        
        return setting
    
    def get_payment_settings(self, db: Session) -> Dict[str, Any]:
        """Get all payment-related settings"""
        settings = self.get_by_category(db, SettingCategory.PAYMENT.value)
        return {setting.key: self._parse_value(setting.value, setting.value_type) for setting in settings}
    
    def get_content_settings(self, db: Session) -> Dict[str, Any]:
        """Get all content-related settings"""
        settings = self.get_by_category(db, SettingCategory.CONTENT.value)
        return {setting.key: self._parse_value(setting.value, setting.value_type) for setting in settings}
    
    def initialize_default_settings(self, db: Session) -> None:
        """Initialize default application settings"""
        default_settings = [
            # Payment Settings
            {
                "category": SettingCategory.PAYMENT.value,
                "key": "payment_enabled",
                "value": False,
                "display_name": "Payment System Enabled",
                "description": "Enable or disable the payment system globally"
            },
            {
                "category": SettingCategory.PAYMENT.value,
                "key": "content_lock_enabled",
                "value": False,
                "display_name": "Content Locking Enabled",
                "description": "Enable content access restrictions based on payment"
            },
            {
                "category": SettingCategory.PAYMENT.value,
                "key": "free_cefr_levels",
                "value": ["A1"],
                "display_name": "Free CEFR Levels",
                "description": "CEFR levels available to free users"
            },
            {
                "category": SettingCategory.PAYMENT.value,
                "key": "free_modules",
                "value": ["reading"],
                "display_name": "Free Learning Modules",
                "description": "Learning modules available to free users"
            },
            {
                "category": SettingCategory.PAYMENT.value,
                "key": "free_lessons_quota",
                "value": 7,
                "display_name": "Free Lessons Quota",
                "description": "Maximum number of completed free lessons before payment is required"
            },
            {
                "category": SettingCategory.PAYMENT.value,
                "key": "premium_price_monthly",
                "value": 9.99,
                "display_name": "Monthly Premium Price",
                "description": "Monthly subscription price in USD"
            },
            {
                "category": SettingCategory.PAYMENT.value,
                "key": "premium_price_yearly",
                "value": 99.99,
                "display_name": "Yearly Premium Price",
                "description": "Yearly subscription price in USD"
            },
            
            # Content Settings
            {
                "category": SettingCategory.CONTENT.value,
                "key": "max_daily_exercises",
                "value": 50,
                "display_name": "Max Daily Exercises",
                "description": "Maximum exercises a user can complete per day"
            },
            {
                "category": SettingCategory.CONTENT.value,
                "key": "ai_feedback_enabled",
                "value": True,
                "display_name": "AI Feedback Enabled",
                "description": "Enable AI-powered feedback for exercises"
            },
            
            # Feature Settings
            {
                "category": SettingCategory.FEATURES.value,
                "key": "speech_recognition_enabled",
                "value": True,
                "display_name": "Speech Recognition Enabled",
                "description": "Enable speech recognition features"
            },
            {
                "category": SettingCategory.FEATURES.value,
                "key": "gamification_enabled",
                "value": True,
                "display_name": "Gamification Enabled",
                "description": "Enable gamification features like points and badges"
            }
        ]
        
        for setting_data in default_settings:
            existing = self.get_by_key(db, setting_data["category"], setting_data["key"])
            if not existing:
                self.set_value(
                    db,
                    category=setting_data["category"],
                    key=setting_data["key"],
                    value=setting_data["value"],
                    display_name=setting_data["display_name"],
                    description=setting_data["description"]
                )
    
    def _parse_value(self, value: str, value_type: str) -> Any:
        """Parse string value based on type"""
        if value is None:
            return None
        
        try:
            if value_type == "boolean":
                return value.lower() in ("true", "1", "yes", "on")
            elif value_type == "integer":
                return int(value)
            elif value_type == "float":
                return float(value)
            elif value_type == "json":
                return json.loads(value)
            else:  # string
                return value
        except (ValueError, json.JSONDecodeError):
            return value  # Return as string if parsing fails
    
    def _serialize_value(self, value: Any) -> tuple[str, str]:
        """Serialize value to string and determine type"""
        if isinstance(value, bool):
            return "boolean", str(value).lower()
        elif isinstance(value, int):
            return "integer", str(value)
        elif isinstance(value, float):
            return "float", str(value)
        elif isinstance(value, (list, dict)):
            return "json", json.dumps(value)
        else:
            return "string", str(value)

# Create CRUD instance
settings_crud = CRUDSettings(AppSettings) 