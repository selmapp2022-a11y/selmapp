from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
import enum
from app.core.database import Base

class SettingCategory(str, enum.Enum):
    PAYMENT = "payment"
    CONTENT = "content"
    FEATURES = "features"
    GENERAL = "general"

class AppSettings(Base):
    """Application settings for persistent configuration"""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    
    # Setting identification
    category = Column(String(50), nullable=False)  # payment, content, features, etc.
    key = Column(String(100), nullable=False)  # setting key name
    value = Column(Text)  # setting value (stored as string, parsed as needed)
    value_type = Column(String(20), default="string")  # string, boolean, integer, float, json
    
    # Setting metadata
    display_name = Column(String(200))  # Human-readable name
    description = Column(Text)  # Description of what this setting does
    default_value = Column(Text)  # Default value for this setting
    
    # Validation and constraints
    allowed_values = Column(JSON)  # List of allowed values (for enum-like settings)
    min_value = Column(String(50))  # Minimum value (for numeric settings)
    max_value = Column(String(50))  # Maximum value (for numeric settings)
    
    # Setting status
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)  # System settings that shouldn't be deleted
    requires_restart = Column(Boolean, default=False)  # Whether changing this requires app restart
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Unique constraint for category + key
    __table_args__ = (
        {"extend_existing": True},
    )

# Create indexes for efficient queries
from sqlalchemy import Index
Index('idx_app_settings_category_key', AppSettings.category, AppSettings.key, unique=True)
Index('idx_app_settings_category', AppSettings.category) 