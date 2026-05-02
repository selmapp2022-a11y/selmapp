from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.orm import selectinload, joinedload
from datetime import datetime, timedelta

from app.crud.base import CRUDBase
from app.models.listening import (
    AudioContent, ListeningExercise, ListeningAttempt, ListeningExerciseAttempt,
    ListeningProgress, AudioPlaylist, AudioPlaylistItem,
    AudioType, DifficultyLevel, ExerciseType
)
from app.schemas.listening import (
    AudioContentCreate, AudioContentUpdate,
    ListeningExerciseCreate, ListeningExerciseUpdate,
    ListeningAttemptCreate, ListeningAttemptUpdate,
    ListeningProgressCreate, ListeningProgressUpdate
)

class CRUDAudioContent(CRUDBase[AudioContent, AudioContentCreate, AudioContentUpdate]):
    async def get_by_audio_type(
        self, 
        db: AsyncSession, 
        audio_type: AudioType,
        skip: int = 0,
        limit: int = 100
    ) -> List[AudioContent]:
        """Get audio content by type"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.audio_type == audio_type,
                self.model.is_active == True
            ))
            .offset(skip)
            .limit(limit)
            .order_by(desc(self.model.created_at))
        )
        return result.scalars().all()

    async def get_by_difficulty_level(
        self, 
        db: AsyncSession, 
        difficulty_level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[AudioContent]:
        """Get audio content by difficulty level"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.difficulty_level == difficulty_level,
                self.model.is_active == True
            ))
            .offset(skip)
            .limit(limit)
            .order_by(desc(self.model.created_at))
        )
        return result.scalars().all()

    async def search_content(
        self, 
        db: AsyncSession, 
        query: str,
        audio_type: Optional[AudioType] = None,
        difficulty_level: Optional[DifficultyLevel] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AudioContent]:
        """Search audio content by title, description, or keywords"""
        conditions = [self.model.is_active == True]
        
        # Add search conditions
        search_conditions = [
            self.model.title.ilike(f"%{query}%"),
            self.model.description.ilike(f"%{query}%"),
            self.model.topic.ilike(f"%{query}%")
        ]
        conditions.append(or_(*search_conditions))
        
        # Add filters
        if audio_type:
            conditions.append(self.model.audio_type == audio_type)
        if difficulty_level:
            conditions.append(self.model.difficulty_level == difficulty_level)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .order_by(desc(self.model.created_at))
        )
        return result.scalars().all()

class CRUDListeningExercise(CRUDBase[ListeningExercise, ListeningExerciseCreate, ListeningExerciseUpdate]):
    async def get_by_audio_content(
        self, 
        db: AsyncSession, 
        audio_content_id: int
    ) -> List[ListeningExercise]:
        """Get exercises for specific audio content"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.audio_content_id == audio_content_id,
                self.model.is_active == True
            ))
            .options(selectinload(self.model.audio_content))
            .order_by(asc(self.model.order_index))
        )
        return result.scalars().all()

    async def get_by_exercise_type(
        self, 
        db: AsyncSession, 
        exercise_type: ExerciseType,
        skip: int = 0,
        limit: int = 100
    ) -> List[ListeningExercise]:
        """Get exercises by type"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.exercise_type == exercise_type,
                self.model.is_active == True
            ))
            .options(selectinload(self.model.audio_content))
            .offset(skip)
            .limit(limit)
            .order_by(desc(self.model.created_at))
        )
        return result.scalars().all()

class CRUDListeningAttempt(CRUDBase[ListeningAttempt, ListeningAttemptCreate, ListeningAttemptUpdate]):
    async def get_user_attempts(
        self, 
        db: AsyncSession, 
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[ListeningAttempt]:
        """Get all attempts for a user"""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .options(
                selectinload(self.model.audio_content),
                selectinload(self.model.exercise_attempts)
            )
            .offset(skip)
            .limit(limit)
            .order_by(desc(self.model.created_at))
        )
        return result.scalars().all()

    async def get_audio_content_attempts(
        self, 
        db: AsyncSession, 
        user_id: int,
        audio_content_id: int
    ) -> List[ListeningAttempt]:
        """Get all attempts for specific audio content by user"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.user_id == user_id,
                self.model.audio_content_id == audio_content_id
            ))
            .options(selectinload(self.model.exercise_attempts))
            .order_by(desc(self.model.created_at))
        )
        return result.scalars().all()

    async def get_user_statistics(
        self, 
        db: AsyncSession, 
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user listening statistics"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Total attempts
        total_attempts = await db.execute(
            select(func.count(self.model.id))
            .where(and_(
                self.model.user_id == user_id,
                self.model.created_at >= since_date
            ))
        )
        
        # Completed attempts
        completed_attempts = await db.execute(
            select(func.count(self.model.id))
            .where(and_(
                self.model.user_id == user_id,
                self.model.is_completed == True,
                self.model.created_at >= since_date
            ))
        )
        
        # Average score
        avg_score = await db.execute(
            select(func.avg(self.model.score_percentage))
            .where(and_(
                self.model.user_id == user_id,
                self.model.is_completed == True,
                self.model.created_at >= since_date
            ))
        )
        
        # Total listening time
        total_time = await db.execute(
            select(func.sum(self.model.total_listen_time))
            .where(and_(
                self.model.user_id == user_id,
                self.model.is_completed == True,
                self.model.created_at >= since_date
            ))
        )
        
        return {
            "total_attempts": total_attempts.scalar() or 0,
            "completed_attempts": completed_attempts.scalar() or 0,
            "average_score": round(avg_score.scalar() or 0.0, 2),
            "total_time_minutes": round((total_time.scalar() or 0) / 60, 2),
            "completion_rate": round(
                (completed_attempts.scalar() or 0) / max(total_attempts.scalar() or 1, 1) * 100, 2
            )
        }

class CRUDListeningExerciseAttempt(CRUDBase[ListeningExerciseAttempt, None, None]):
    async def get_by_listening_attempt(
        self, 
        db: AsyncSession, 
        listening_attempt_id: int
    ) -> List[ListeningExerciseAttempt]:
        """Get all exercise attempts for a listening attempt"""
        result = await db.execute(
            select(self.model)
            .where(self.model.listening_attempt_id == listening_attempt_id)
            .options(selectinload(self.model.exercise))
            .order_by(asc(self.model.exercise_id))
        )
        return result.scalars().all()

    async def create_with_validation(
        self, 
        db: AsyncSession, 
        user_id: int,
        exercise_id: int,
        listening_attempt_id: int,
        user_answer: Any,
        time_taken_seconds: Optional[int] = None
    ) -> ListeningExerciseAttempt:
        """Create exercise attempt with automatic validation"""
        # Get the exercise to validate answer
        exercise_result = await db.execute(
            select(ListeningExercise).where(ListeningExercise.id == exercise_id)
        )
        exercise = exercise_result.scalars().first()
        
        if not exercise:
            raise ValueError("Exercise not found")
        
        # Validate answer based on exercise type
        is_correct = self._validate_answer(exercise, user_answer)
        score = exercise.points if is_correct else 0
        
        # Create exercise attempt
        exercise_attempt = ListeningExerciseAttempt(
            user_id=user_id,
            exercise_id=exercise_id,
            listening_attempt_id=listening_attempt_id,
            user_answer=user_answer,
            is_correct=is_correct,
            score=score,
            time_taken_seconds=time_taken_seconds
        )
        
        db.add(exercise_attempt)
        await db.commit()
        await db.refresh(exercise_attempt)
        return exercise_attempt

    def _validate_answer(self, exercise: ListeningExercise, user_answer: Any) -> bool:
        """Validate user answer against correct answer"""
        correct_answer = exercise.correct_answer
        
        if exercise.exercise_type == ExerciseType.MULTIPLE_CHOICE:
            return str(user_answer).strip().lower() == str(correct_answer).strip().lower()
        elif exercise.exercise_type == ExerciseType.TRUE_FALSE:
            return str(user_answer).lower() in ['true', 'false'] and str(user_answer).lower() == str(correct_answer).lower()
        elif exercise.exercise_type == ExerciseType.FILL_BLANK:
            # Allow some flexibility for fill-in-the-blank
            user_str = str(user_answer).strip().lower()
            correct_str = str(correct_answer).strip().lower()
            return user_str == correct_str or user_str in correct_str
        else:
            # For other types, use exact match for now
            return str(user_answer).strip().lower() == str(correct_answer).strip().lower()

class CRUDListeningProgress(CRUDBase[ListeningProgress, ListeningProgressCreate, ListeningProgressUpdate]):
    async def get_by_user(
        self, 
        db: AsyncSession, 
        user_id: int
    ) -> Optional[ListeningProgress]:
        """Get progress for a user"""
        result = await db.execute(
            select(self.model).where(self.model.user_id == user_id)
        )
        return result.scalars().first()

    async def update_progress(
        self, 
        db: AsyncSession, 
        user_id: int,
        attempt: ListeningAttempt
    ) -> ListeningProgress:
        """Update user progress based on attempt"""
        progress = await self.get_by_user(db, user_id)
        
        if not progress:
            # Create initial progress
            progress = ListeningProgress(
                user_id=user_id,
                current_level=DifficultyLevel.A1
            )
            db.add(progress)
        
        # Update metrics
        if attempt.is_completed:
            progress.total_exercises_completed += attempt.total_exercises
            progress.total_audio_content_completed += 1
            
            if attempt.total_listen_time:
                progress.total_listening_time += int(attempt.total_listen_time / 60)
            
            # Update average comprehension score
            if attempt.comprehension_score:
                current_total = progress.average_comprehension_score * (progress.total_audio_content_completed - 1)
                progress.average_comprehension_score = (current_total + attempt.comprehension_score) / progress.total_audio_content_completed
            
            # Update last activity
            progress.last_activity_date = datetime.utcnow()
            
            # Check for level up
            if progress.average_comprehension_score >= 80 and progress.total_audio_content_completed >= 10:
                await self._check_level_up(db, progress)
        
        await db.commit()
        await db.refresh(progress)
        return progress

    async def _check_level_up(self, db: AsyncSession, progress: ListeningProgress):
        """Check if user should level up"""
        level_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        current_index = level_order.index(progress.current_level.value)
        
        if current_index < len(level_order) - 1:
            next_level = DifficultyLevel(level_order[current_index + 1])
            progress.current_level = next_level
            progress.last_level_up_date = datetime.utcnow()

# Create CRUD instances
crud_audio_content = CRUDAudioContent(AudioContent)
crud_listening_exercise = CRUDListeningExercise(ListeningExercise)
crud_listening_attempt = CRUDListeningAttempt(ListeningAttempt)
crud_listening_exercise_attempt = CRUDListeningExerciseAttempt(ListeningExerciseAttempt)
crud_listening_progress = CRUDListeningProgress(ListeningProgress) 