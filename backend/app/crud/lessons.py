from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.crud.base import CRUDBase
from app.models.lessons import AIGeneratedLesson, LessonProgress, LessonGenerationAnalytics, LessonTemplate
from app.schemas.lessons import (
    AILessonCreate, AILessonUpdate,
    LessonProgressCreate, LessonProgressUpdate,
    LessonTemplateCreate, LessonTemplateUpdate
)


class _SyncMixin:
    """Provides synchronous get/create/update/remove for CRUD classes whose
    custom methods already use the synchronous ORM API (``db.query(...)``).

    The async ``CRUDBase`` parent class is kept for endpoints that use
    ``AsyncSession``, but the lesson and lesson-progress endpoints currently
    pass a *sync* ``Session`` — so we need these helpers.
    """

    def get_sync(self, db: Session, *, id: Any) -> Optional[Any]:
        return db.query(self.model).filter(self.model.id == id).first()

    def create_sync(self, db: Session, *, obj_in) -> Any:
        if isinstance(obj_in, BaseModel):
            obj_data = obj_in.model_dump()
        else:
            obj_data = obj_in if isinstance(obj_in, dict) else {}
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update_sync(self, db: Session, *, db_obj, obj_in: Union[dict, BaseModel]) -> Any:
        if isinstance(obj_in, BaseModel):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove_sync(self, db: Session, *, id: int) -> Optional[Any]:
        obj = self.get_sync(db, id=id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj


class CRUDLesson(_SyncMixin, CRUDBase[AIGeneratedLesson, AILessonCreate, AILessonUpdate]):
    def get_user_cached_lessons(
        self,
        db: Session,
        *,
        user_id: int,
        lesson_type: Optional[str] = None,
        difficulty_level: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AIGeneratedLesson]:
        """Get user's cached lessons with optional filtering"""
        query = db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.is_active == True,
                or_(
                    self.model.expires_at.is_(None),
                    self.model.expires_at > func.now()
                )
            )
        )

        if lesson_type:
            query = query.filter(self.model.lesson_type == lesson_type)

        if difficulty_level:
            query = query.filter(self.model.difficulty_level == difficulty_level)

        return query.order_by(desc(self.model.last_accessed_at), desc(self.model.created_at))\
                   .offset(skip)\
                   .limit(limit)\
                   .all()

    def get_cached_lesson(
        self,
        db: Session,
        *,
        user_id: int,
        lesson_type: str,
        difficulty_level: str,
        topic: Optional[str] = None
    ) -> Optional[AIGeneratedLesson]:
        """Get a specific cached lesson"""
        query = db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.lesson_type == lesson_type,
                self.model.difficulty_level == difficulty_level,
                self.model.is_active == True,
                or_(
                    self.model.expires_at.is_(None),
                    self.model.expires_at > func.now()
                )
            )
        )

        if topic:
            query = query.filter(self.model.topic == topic)

        return query.order_by(desc(self.model.last_accessed_at)).first()

    def update_access_time(self, db: Session, *, lesson_id: int) -> AIGeneratedLesson:
        """Update last accessed time for a lesson"""
        lesson = self.get(db, id=lesson_id)
        if lesson:
            lesson.last_accessed_at = func.now()
            db.commit()
            db.refresh(lesson)
        return lesson

    def increment_usage_count(self, db: Session, *, lesson_id: int) -> AIGeneratedLesson:
        """Increment usage count for a lesson"""
        lesson = self.get(db, id=lesson_id)
        if lesson:
            lesson.usage_count += 1
            db.commit()
            db.refresh(lesson)
        return lesson

    def cleanup_expired_lessons(self, db: Session, *, user_id: Optional[int] = None) -> int:
        """Clean up expired lessons, optionally for a specific user"""
        query = db.query(self.model).filter(
            and_(
                self.model.expires_at.is_not(None),
                self.model.expires_at <= func.now(),
                self.model.is_active == True
            )
        )

        if user_id:
            query = query.filter(self.model.user_id == user_id)

        expired_count = query.update({"is_active": False})
        db.commit()

        return expired_count

class CRUDLessonProgress(_SyncMixin, CRUDBase[LessonProgress, LessonProgressCreate, LessonProgressUpdate]):
    def get_user_lesson_progress(
        self,
        db: Session,
        *,
        user_id: int,
        lesson_id: int
    ) -> Optional[LessonProgress]:
        """Get user's progress for a specific lesson"""
        return db.query(self.model).filter(
            and_(
                self.model.user_id == user_id,
                self.model.lesson_id == lesson_id
            )
        ).first()

    def get_user_recent_progress(
        self,
        db: Session,
        *,
        user_id: int,
        limit: int = 10
    ) -> List[LessonProgress]:
        """Get user's recent lesson progress"""
        return db.query(self.model).filter(
            self.model.user_id == user_id
        ).order_by(desc(self.model.last_activity_at))\
         .limit(limit)\
         .all()

    def get_user_completion_stats(
        self,
        db: Session,
        *,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user's lesson completion statistics"""
        result = db.query(
            func.count(self.model.id).label('total_started'),
            func.count(func.nullif(self.model.is_completed, False)).label('total_completed'),
            func.avg(self.model.accuracy_score).label('avg_accuracy'),
            func.avg(self.model.performance_score).label('avg_performance'),
            func.sum(self.model.time_spent_minutes).label('total_time_spent')
        ).filter(self.model.user_id == user_id).first()

        return {
            'total_started': result.total_started or 0,
            'total_completed': result.total_completed or 0,
            'completion_rate': (result.total_completed / result.total_started) if result.total_started > 0 else 0.0,
            'avg_accuracy': float(result.avg_accuracy) if result.avg_accuracy else 0.0,
            'avg_performance': float(result.avg_performance) if result.avg_performance else 0.0,
            'total_time_spent_minutes': result.total_time_spent or 0
        }

class CRUDLessonAnalytics(CRUDBase[LessonGenerationAnalytics, Any, Any]):
    def record_generation(
        self,
        db: Session,
        *,
        user_id: int,
        lesson_type: str,
        generation_time_seconds: float
    ) -> LessonGenerationAnalytics:
        """Record lesson generation analytics"""
        # This would be implemented to track generation metrics
        # For now, return a placeholder
        pass

class CRUDLessonTemplate(CRUDBase[LessonTemplate, LessonTemplateCreate, LessonTemplateUpdate]):
    def get_by_criteria(
        self,
        db: Session,
        *,
        lesson_type: str,
        difficulty_level: str,
        topic_category: Optional[str] = None
    ) -> List[LessonTemplate]:
        """Get templates matching criteria"""
        query = db.query(self.model).filter(
            and_(
                self.model.lesson_type == lesson_type,
                self.model.difficulty_level == difficulty_level,
                self.model.is_active == True
            )
        )

        if topic_category:
            query = query.filter(self.model.topic_category == topic_category)

        return query.order_by(desc(self.model.usage_count)).all()

    def increment_usage(self, db: Session, *, template_id: int) -> LessonTemplate:
        """Increment usage count for a template"""
        template = self.get(db, id=template_id)
        if template:
            template.usage_count += 1
            db.commit()
            db.refresh(template)
        return template

# Global instances
crud_ai_lesson = CRUDLesson(AIGeneratedLesson)
crud_lesson_progress = CRUDLessonProgress(LessonProgress)
crud_lesson_analytics = CRUDLessonAnalytics(LessonGenerationAnalytics)
crud_lesson_template = CRUDLessonTemplate(LessonTemplate)















