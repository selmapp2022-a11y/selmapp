from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class AssessmentJob(Base):
    __tablename__ = "assessment_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(String(32), nullable=False, default="pending")  # pending|processing|completed|failed
    progress = Column(Integer, nullable=False, default=0)
    message = Column(String(500), nullable=True)

    # Personalization inputs
    question_count = Column(Integer, nullable=False, default=20)
    user_preferences = Column(JSONB, nullable=True)
    personalized = Column(Boolean, nullable=False, default=True)

    # Result / error
    result = Column(JSONB, nullable=True)  # stores quiz_data
    error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)



