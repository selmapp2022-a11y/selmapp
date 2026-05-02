from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update

from app.models.cache import GeneratedContentCache, DailyLearningPlan, WeeklyLearningPlan
from app.models.progress import UserWeeklyProgress, DayCompletionRecord


class CRUDGeneratedContentCache:
    def __init__(self, model: type[GeneratedContentCache]):
        self.model = model

    async def get_by_key(self, db: AsyncSession, *, cache_key: str) -> Optional[GeneratedContentCache]:
        result = await db.execute(select(self.model).where(self.model.cache_key == cache_key))
        obj = result.scalars().first()
        if not obj:
            return None
        if obj.expires_at and obj.expires_at < datetime.utcnow():
            return None
        return obj

    async def create(self, db: AsyncSession, *, data: Dict[str, Any]) -> GeneratedContentCache:
        obj = self.model(**data)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj


class CRUDDailyLearningPlan:
    def __init__(self, model: type[DailyLearningPlan]):
        self.model = model

    async def get_by_user_and_date(self, db: AsyncSession, *, user_id: int, date_str: str) -> Optional[DailyLearningPlan]:
        result = await db.execute(
            select(self.model).where(
                and_(self.model.user_id == user_id, self.model.date == date_str)
            )
        )
        plan = result.scalars().first()
        if not plan:
            return None
        if plan.expires_at and plan.expires_at < datetime.utcnow():
            return None
        return plan

    async def upsert(self, db: AsyncSession, *, user_id: int, date_str: str, plan: Dict[str, Any], expires_at: Optional[datetime] = None) -> DailyLearningPlan:
        existing = await self.get_by_user_and_date(db, user_id=user_id, date_str=date_str)
        if existing:
            existing.plan = plan
            existing.expires_at = expires_at
            await db.commit()
            await db.refresh(existing)
            return existing
        obj = self.model(user_id=user_id, date=date_str, plan=plan, expires_at=expires_at)
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj


generated_content_cache_crud = CRUDGeneratedContentCache(GeneratedContentCache)
daily_learning_plan_crud = CRUDDailyLearningPlan(DailyLearningPlan)


class CRUDWeeklyLearningPlan:
    """CRUD operations for WeeklyLearningPlan"""
    
    def __init__(self, model: type[WeeklyLearningPlan]):
        self.model = model

    async def get(self, db: AsyncSession, *, id: int) -> Optional[WeeklyLearningPlan]:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def get_by_user_and_week(
        self, db: AsyncSession, *, user_id: int, week_number: int
    ) -> Optional[WeeklyLearningPlan]:
        result = await db.execute(
            select(self.model).where(
                and_(self.model.user_id == user_id, self.model.week_number == week_number)
            )
        )
        return result.scalars().first()

    async def get_current_week(self, db: AsyncSession, *, user_id: int) -> Optional[WeeklyLearningPlan]:
        """Get user's current active week (most recent with status 'ready')"""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.user_id == user_id, self.model.status == "ready"))
            .order_by(self.model.week_number.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_all_by_user(
        self, db: AsyncSession, *, user_id: int
    ) -> List[WeeklyLearningPlan]:
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.week_number)
        )
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        week_number: int,
        plan_data: Optional[Dict[str, Any]] = None,
        user_progress_snapshot: Optional[Dict[str, Any]] = None,
        status: str = "pending"
    ) -> WeeklyLearningPlan:
        obj = self.model(
            user_id=user_id,
            week_number=week_number,
            plan_data=plan_data,
            user_progress_snapshot=user_progress_snapshot,
            status=status,
            days_content_ready=[],
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def update_status(
        self,
        db: AsyncSession,
        *,
        plan_id: int,
        status: str,
        error: Optional[str] = None
    ) -> Optional[WeeklyLearningPlan]:
        plan = await self.get(db, id=plan_id)
        if not plan:
            return None
        
        plan.status = status
        if error:
            plan.last_error = error
        if status == "generating":
            plan.generation_started_at = datetime.utcnow()
            plan.generation_attempts += 1
        elif status == "ready":
            plan.generation_completed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(plan)
        return plan

    async def update_plan_data(
        self,
        db: AsyncSession,
        *,
        plan_id: int,
        plan_data: Dict[str, Any]
    ) -> Optional[WeeklyLearningPlan]:
        plan = await self.get(db, id=plan_id)
        if not plan:
            return None
        
        plan.plan_data = plan_data
        await db.commit()
        await db.refresh(plan)
        return plan

    async def mark_day_content_ready(
        self,
        db: AsyncSession,
        *,
        plan_id: int,
        day_number: int
    ) -> Optional[WeeklyLearningPlan]:
        plan = await self.get(db, id=plan_id)
        if not plan:
            return None
        
        days_ready = list(plan.days_content_ready or [])
        if day_number not in days_ready:
            days_ready.append(day_number)
            days_ready.sort()
        plan.days_content_ready = days_ready
        
        # If all 7 days are ready, mark as ready
        if len(days_ready) >= 7:
            plan.status = "ready"
            plan.generation_completed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(plan)
        return plan

    async def update_day_progress(
        self,
        db: AsyncSession,
        *,
        plan_id: int,
        current_day: int,
        days_completed: int
    ) -> Optional[WeeklyLearningPlan]:
        plan = await self.get(db, id=plan_id)
        if not plan:
            return None
        
        plan.current_day = current_day
        plan.days_completed = days_completed
        await db.commit()
        await db.refresh(plan)
        return plan

    async def increment_attempts(
        self,
        db: AsyncSession,
        *,
        plan_id: int,
        error: Optional[str] = None
    ) -> Optional[WeeklyLearningPlan]:
        plan = await self.get(db, id=plan_id)
        if not plan:
            return None
        
        plan.generation_attempts += 1
        if error:
            plan.last_error = error
        
        # Mark as failed if max attempts reached
        if plan.generation_attempts >= plan.max_attempts:
            plan.status = "failed"
        
        await db.commit()
        await db.refresh(plan)
        return plan


class CRUDUserWeeklyProgress:
    """CRUD operations for UserWeeklyProgress"""
    
    def __init__(self, model: type[UserWeeklyProgress]):
        self.model = model

    async def get(self, db: AsyncSession, *, id: int) -> Optional[UserWeeklyProgress]:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def get_by_user(self, db: AsyncSession, *, user_id: int) -> Optional[UserWeeklyProgress]:
        result = await db.execute(
            select(self.model).where(self.model.user_id == user_id)
        )
        return result.scalars().first()

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        current_week_number: int = 1,
        current_day_in_week: int = 1
    ) -> UserWeeklyProgress:
        obj = self.model(
            user_id=user_id,
            current_week_number=current_week_number,
            current_day_in_week=current_day_in_week,
            skill_scores={},
            weak_areas=[],
            strong_areas=[],
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def get_or_create(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> UserWeeklyProgress:
        existing = await self.get_by_user(db, user_id=user_id)
        if existing:
            return existing
        return await self.create(db, user_id=user_id)

    async def update_day_completed(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        day_in_week: int
    ) -> Optional[UserWeeklyProgress]:
        """Update progress when a day is completed"""
        progress = await self.get_by_user(db, user_id=user_id)
        if not progress:
            return None
        
        progress.current_day_in_week = day_in_week + 1 if day_in_week < 7 else 1
        progress.total_days_completed += 1
        progress.last_day_completed_at = datetime.utcnow()
        
        # If completed day 7, increment weeks completed
        if day_in_week >= 7:
            progress.total_weeks_completed += 1
            progress.current_week_number += 1
            progress.current_day_in_week = 1
        
        await db.commit()
        await db.refresh(progress)
        return progress

    async def update_skill_scores(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skill_scores: Dict[str, float],
        weak_areas: List[str],
        strong_areas: List[str]
    ) -> Optional[UserWeeklyProgress]:
        progress = await self.get_by_user(db, user_id=user_id)
        if not progress:
            return None
        
        progress.skill_scores = skill_scores
        progress.weak_areas = weak_areas
        progress.strong_areas = strong_areas
        
        await db.commit()
        await db.refresh(progress)
        return progress

    async def set_progress_analysis(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        analysis: Dict[str, Any]
    ) -> Optional[UserWeeklyProgress]:
        progress = await self.get_by_user(db, user_id=user_id)
        if not progress:
            return None
        
        progress.progress_analysis = analysis
        await db.commit()
        await db.refresh(progress)
        return progress


class CRUDDayCompletionRecord:
    """CRUD operations for DayCompletionRecord"""
    
    def __init__(self, model: type[DayCompletionRecord]):
        self.model = model

    async def get(self, db: AsyncSession, *, id: int) -> Optional[DayCompletionRecord]:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def get_by_user_week_day(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        week_number: int,
        day_number: int
    ) -> Optional[DayCompletionRecord]:
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.user_id == user_id,
                    self.model.week_number == week_number,
                    self.model.day_number == day_number
                )
            )
        )
        return result.scalars().first()

    async def get_week_records(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        week_number: int
    ) -> List[DayCompletionRecord]:
        result = await db.execute(
            select(self.model)
            .where(
                and_(self.model.user_id == user_id, self.model.week_number == week_number)
            )
            .order_by(self.model.day_number)
        )
        return result.scalars().all()

    async def get_recent_records(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = 14
    ) -> List[DayCompletionRecord]:
        """Get recent completion records for progress analysis"""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .order_by(self.model.completed_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        week_number: int,
        day_number: int,
        exercises_completed: int = 0,
        correct_answers: int = 0,
        total_questions: int = 0,
        time_spent_minutes: int = 0,
        skill_results: Optional[Dict[str, Any]] = None,
        content_types_completed: Optional[List[str]] = None,
        started_at: Optional[datetime] = None
    ) -> DayCompletionRecord:
        accuracy = correct_answers / total_questions if total_questions > 0 else 0.0
        
        obj = self.model(
            user_id=user_id,
            week_number=week_number,
            day_number=day_number,
            exercises_completed=exercises_completed,
            correct_answers=correct_answers,
            total_questions=total_questions,
            accuracy=accuracy,
            time_spent_minutes=time_spent_minutes,
            skill_results=skill_results or {},
            content_types_completed=content_types_completed or [],
            started_at=started_at,
        )
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def upsert(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        week_number: int,
        day_number: int,
        **kwargs
    ) -> DayCompletionRecord:
        existing = await self.get_by_user_week_day(
            db, user_id=user_id, week_number=week_number, day_number=day_number
        )
        if existing:
            # Update existing record
            for key, value in kwargs.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            
            # Recalculate accuracy
            if existing.total_questions > 0:
                existing.accuracy = existing.correct_answers / existing.total_questions
            
            await db.commit()
            await db.refresh(existing)
            return existing
        
        return await self.create(
            db,
            user_id=user_id,
            week_number=week_number,
            day_number=day_number,
            **kwargs
        )

    async def get_days_completed_in_week(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        week_number: int
    ) -> int:
        """Count how many days are completed in a week"""
        records = await self.get_week_records(db, user_id=user_id, week_number=week_number)
        return len(records)


# Global instances
weekly_learning_plan_crud = CRUDWeeklyLearningPlan(WeeklyLearningPlan)
user_weekly_progress_crud = CRUDUserWeeklyProgress(UserWeeklyProgress)
day_completion_record_crud = CRUDDayCompletionRecord(DayCompletionRecord)





















