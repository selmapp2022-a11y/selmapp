from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.progress import (
    UserProgress, DailyProgress, Achievement, UserAchievement, 
    StudySession, LearningGoal, DifficultyLevel
)
from app.schemas.progress import (
    UserProgressCreate, UserProgressUpdate, DailyProgressCreate,
    AchievementCreate, StudySessionCreate, LearningGoalCreate, LearningGoalUpdate
)

class CRUDUserProgress(CRUDBase[UserProgress, UserProgressCreate, UserProgressUpdate]):
    async def get_by_user(self, db: AsyncSession, *, user_id: int) -> Optional[UserProgress]:
        """Get user progress by user ID"""
        result = await db.execute(
            select(UserProgress).where(UserProgress.user_id == user_id).order_by(UserProgress.id.desc()).limit(1)
        )
        # Use scalars().first() instead of scalar_one_or_none() to handle potential duplicates gracefully
        return result.scalars().first()

    async def create_or_update(
        self, db: AsyncSession, *, user_id: int, progress_data: Dict[str, Any]
    ) -> UserProgress:
        """Create or update user progress"""
        existing = await self.get_by_user(db, user_id=user_id)
        
        if existing:
            return await self.update(db, db_obj=existing, obj_in=progress_data)
        else:
            progress_data["user_id"] = user_id
            create_obj = UserProgressCreate(**progress_data)
            return await self.create(db, obj_in=create_obj)

    async def update_study_time(
        self, db: AsyncSession, *, user_id: int, minutes: int
    ) -> UserProgress:
        """Update user's total study time"""
        progress = await self.get_by_user(db, user_id=user_id)
        if progress:
            progress.total_study_time_minutes += minutes
            progress.last_study_date = datetime.utcnow()
            await db.commit()
            await db.refresh(progress)
        return progress

    async def update_streak(
        self, db: AsyncSession, *, user_id: int, study_date: date
    ) -> UserProgress:
        """Update user's study streak"""
        progress = await self.get_by_user(db, user_id=user_id)
        if progress:
            last_study = progress.last_study_date.date() if progress.last_study_date else None
            
            if last_study:
                days_diff = (study_date - last_study).days
                if days_diff == 1:
                    # Consecutive day
                    progress.current_streak_days += 1
                elif days_diff > 1:
                    # Streak broken
                    progress.current_streak_days = 1
                # Same day - no change
            else:
                # First study session
                progress.current_streak_days = 1
            
            # Update longest streak
            if progress.current_streak_days > progress.longest_streak_days:
                progress.longest_streak_days = progress.current_streak_days
            
            progress.last_study_date = datetime.combine(study_date, datetime.min.time())
            await db.commit()
            await db.refresh(progress)
        return progress

class CRUDDailyProgress(CRUDBase[DailyProgress, DailyProgressCreate, DailyProgressCreate]):
    async def get_by_user_and_date(
        self, db: AsyncSession, *, user_id: int, date: date
    ) -> Optional[DailyProgress]:
        """Get daily progress by user and date"""
        result = await db.execute(
            select(DailyProgress).where(
                and_(
                    DailyProgress.user_id == user_id,
                    func.date(DailyProgress.date) == date
                )
            ).order_by(DailyProgress.id.desc()).limit(1)
        )
        # Use scalars().first() to handle potential duplicates gracefully
        return result.scalars().first()

    async def get_user_progress_range(
        self, db: AsyncSession, *, user_id: int, start_date: date, end_date: date
    ) -> List[DailyProgress]:
        """Get user's daily progress for a date range"""
        result = await db.execute(
            select(DailyProgress)
            .where(
                and_(
                    DailyProgress.user_id == user_id,
                    func.date(DailyProgress.date) >= start_date,
                    func.date(DailyProgress.date) <= end_date
                )
            )
            .order_by(DailyProgress.date)
        )
        return result.scalars().all()

    async def create_or_update_daily(
        self, db: AsyncSession, *, user_id: int, date: date, progress_data: Dict[str, Any]
    ) -> DailyProgress:
        """Create or update daily progress"""
        existing = await self.get_by_user_and_date(db, user_id=user_id, date=date)
        
        if existing:
            for key, value in progress_data.items():
                if hasattr(existing, key):
                    current_value = getattr(existing, key, 0)
                    if key in ['study_time_minutes', 'exercises_completed', 'points_earned']:
                        setattr(existing, key, current_value + value)
                    else:
                        setattr(existing, key, value)
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            progress_data.update({
                "user_id": user_id,
                "date": datetime.combine(date, datetime.min.time())
            })
            create_obj = DailyProgressCreate(**progress_data)
            return await self.create(db, obj_in=create_obj)

class CRUDAchievement(CRUDBase[Achievement, AchievementCreate, AchievementCreate]):
    async def get_active_achievements(self, db: AsyncSession) -> List[Achievement]:
        """Get all active achievements"""
        result = await db.execute(
            select(Achievement).where(Achievement.is_active == True)
        )
        return result.scalars().all()

    async def get_by_criteria(
        self, db: AsyncSession, *, criteria_type: str
    ) -> List[Achievement]:
        """Get achievements by criteria type"""
        result = await db.execute(
            select(Achievement).where(
                and_(
                    Achievement.criteria_type == criteria_type,
                    Achievement.is_active == True
                )
            )
        )
        return result.scalars().all()

class CRUDUserAchievement(CRUDBase[UserAchievement, Dict, Dict]):
    async def get_user_achievements(
        self, db: AsyncSession, *, user_id: int
    ) -> List[UserAchievement]:
        """Get all achievements earned by user"""
        result = await db.execute(
            select(UserAchievement)
            .options(selectinload(UserAchievement.achievement))
            .where(UserAchievement.user_id == user_id)
            .order_by(desc(UserAchievement.earned_at))
        )
        return result.scalars().all()

    async def has_achievement(
        self, db: AsyncSession, *, user_id: int, achievement_id: int
    ) -> bool:
        """Check if user has earned specific achievement"""
        result = await db.execute(
            select(UserAchievement).where(
                and_(
                    UserAchievement.user_id == user_id,
                    UserAchievement.achievement_id == achievement_id
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def award_achievement(
        self, db: AsyncSession, *, user_id: int, achievement_id: int, progress_value: int
    ) -> UserAchievement:
        """Award achievement to user"""
        if not await self.has_achievement(db, user_id=user_id, achievement_id=achievement_id):
            user_achievement = UserAchievement(
                user_id=user_id,
                achievement_id=achievement_id,
                progress_value=progress_value
            )
            db.add(user_achievement)
            await db.commit()
            await db.refresh(user_achievement)
            return user_achievement
        return None

class CRUDStudySession(CRUDBase[StudySession, StudySessionCreate, StudySessionCreate]):
    async def get_user_sessions(
        self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[StudySession]:
        """Get user's study sessions"""
        result = await db.execute(
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .order_by(desc(StudySession.started_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_active_session(
        self, db: AsyncSession, *, user_id: int
    ) -> Optional[StudySession]:
        """Get user's active (ongoing) study session"""
        result = await db.execute(
            select(StudySession).where(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.ended_at.is_(None)
                )
            )
        )
        return result.scalar_one_or_none()

    async def end_session(
        self, db: AsyncSession, *, session_id: int, end_data: Dict[str, Any]
    ) -> StudySession:
        """End a study session"""
        session = await self.get(db, id=session_id)
        if session:
            session.ended_at = datetime.utcnow()
            for key, value in end_data.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            await db.commit()
            await db.refresh(session)
        return session

class CRUDLearningGoal(CRUDBase[LearningGoal, LearningGoalCreate, LearningGoalUpdate]):
    async def get_user_goals(
        self, db: AsyncSession, *, user_id: int, active_only: bool = True
    ) -> List[LearningGoal]:
        """Get user's learning goals"""
        filters = [LearningGoal.user_id == user_id]
        if active_only:
            filters.append(LearningGoal.is_active == True)
        
        result = await db.execute(
            select(LearningGoal)
            .where(and_(*filters))
            .order_by(LearningGoal.created_at)
        )
        return result.scalars().all()

    async def update_goal_progress(
        self, db: AsyncSession, *, goal_id: int, progress_value: int
    ) -> LearningGoal:
        """Update goal progress"""
        goal = await self.get(db, id=goal_id)
        if goal:
            goal.current_value = progress_value
            if progress_value >= goal.target_value and not goal.is_completed:
                goal.is_completed = True
                goal.completed_at = datetime.utcnow()
            await db.commit()
            await db.refresh(goal)
        return goal

# Create instances
user_progress_crud = CRUDUserProgress(UserProgress)
daily_progress_crud = CRUDDailyProgress(DailyProgress)
achievement_crud = CRUDAchievement(Achievement)
user_achievement_crud = CRUDUserAchievement(UserAchievement)
study_session_crud = CRUDStudySession(StudySession)
learning_goal_crud = CRUDLearningGoal(LearningGoal) 