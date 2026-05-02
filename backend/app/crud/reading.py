from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.reading import (
    ReadingText, ReadingExercise, ReadingAttempt, 
    VocabularyHighlight, ReadingProgress, ReadingTextType
)
from app.models.content import DifficultyLevel
from app.schemas.reading import (
    ReadingTextCreate, ReadingTextUpdate,
    ReadingExerciseCreate, ReadingExerciseUpdate,
    ReadingAttemptCreate, ReadingAttemptSubmit,
    VocabularyHighlightCreate, VocabularyHighlightUpdate,
    ReadingProgressUpdate
)


class CRUDReadingText(CRUDBase[ReadingText, ReadingTextCreate, ReadingTextUpdate]):
    async def get_by_level(
        self, db: AsyncSession, *, level: DifficultyLevel, skip: int = 0, limit: int = 100
    ) -> List[ReadingText]:
        """Get reading texts by difficulty level"""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.difficulty_level == level, self.model.is_active == True))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_type(
        self, db: AsyncSession, *, text_type: ReadingTextType, skip: int = 0, limit: int = 100
    ) -> List[ReadingText]:
        """Get reading texts by type"""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.text_type == text_type, self.model.is_active == True))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_level_and_type(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel, 
        text_type: ReadingTextType,
        skip: int = 0, 
        limit: int = 100
    ) -> List[ReadingText]:
        """Get reading texts by level and type"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.difficulty_level == level,
                self.model.text_type == text_type,
                self.model.is_active == True
            ))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def search_texts(
        self, 
        db: AsyncSession, 
        *, 
        query: str, 
        level: Optional[DifficultyLevel] = None,
        text_type: Optional[ReadingTextType] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[ReadingText]:
        """Search reading texts by title, content, or keywords"""
        conditions = [self.model.is_active == True]
        
        # Add search condition
        search_condition = or_(
            self.model.title.ilike(f"%{query}%"),
            self.model.content.ilike(f"%{query}%"),
            self.model.topic.ilike(f"%{query}%")
        )
        conditions.append(search_condition)
        
        # Add optional filters
        if level:
            conditions.append(self.model.difficulty_level == level)
        if text_type:
            conditions.append(self.model.text_type == text_type)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_with_exercises(self, db: AsyncSession, *, id: int) -> Optional[ReadingText]:
        """Get reading text with its exercises"""
        result = await db.execute(
            select(self.model)
            .options(selectinload(self.model.reading_exercises))
            .where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_with_vocabulary(self, db: AsyncSession, *, id: int) -> Optional[ReadingText]:
        """Get reading text with vocabulary highlights"""
        result = await db.execute(
            select(self.model)
            .options(selectinload(self.model.vocabulary_highlights))
            .where(self.model.id == id)
        )
        return result.scalar_one_or_none()


class CRUDReadingExercise(CRUDBase[ReadingExercise, ReadingExerciseCreate, ReadingExerciseUpdate]):
    async def get_by_text(
        self, db: AsyncSession, *, reading_text_id: int
    ) -> List[ReadingExercise]:
        """Get exercises for a specific reading text"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.reading_text_id == reading_text_id,
                self.model.is_active == True
            ))
            .order_by(self.model.order_index, self.model.id)
        )
        return result.scalars().all()

    async def get_by_type(
        self, 
        db: AsyncSession, 
        *, 
        exercise_type: str, 
        reading_text_id: Optional[int] = None
    ) -> List[ReadingExercise]:
        """Get exercises by type"""
        conditions = [
            self.model.exercise_type == exercise_type,
            self.model.is_active == True
        ]
        
        if reading_text_id:
            conditions.append(self.model.reading_text_id == reading_text_id)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.order_index, self.model.id)
        )
        return result.scalars().all()


class CRUDReadingAttempt(CRUDBase[ReadingAttempt, ReadingAttemptCreate, ReadingAttemptSubmit]):
    async def get_user_attempts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ReadingAttempt]:
        """Get user's reading attempts"""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_text_attempts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        reading_text_id: int
    ) -> List[ReadingAttempt]:
        """Get user's attempts for a specific text"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.user_id == user_id,
                self.model.reading_text_id == reading_text_id
            ))
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_exercise_attempt(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        reading_exercise_id: int
    ) -> Optional[ReadingAttempt]:
        """Get user's attempt for a specific exercise"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.user_id == user_id,
                self.model.reading_exercise_id == reading_exercise_id
            ))
            .order_by(self.model.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def get_user_stats(self, db: AsyncSession, *, user_id: int) -> Dict[str, Any]:
        """Get user's reading statistics"""
        # Total attempts
        total_attempts = await db.execute(
            select(func.count(self.model.id))
            .where(self.model.user_id == user_id)
        )
        
        # Correct attempts
        correct_attempts = await db.execute(
            select(func.count(self.model.id))
            .where(and_(
                self.model.user_id == user_id,
                self.model.is_correct == True
            ))
        )
        
        # Average comprehension score
        avg_comprehension = await db.execute(
            select(func.avg(self.model.comprehension_score))
            .where(self.model.user_id == user_id)
        )
        
        # Average reading speed
        avg_speed = await db.execute(
            select(func.avg(self.model.words_per_minute))
            .where(and_(
                self.model.user_id == user_id,
                self.model.words_per_minute.is_not(None)
            ))
        )
        
        # Total reading time
        total_time = await db.execute(
            select(func.sum(self.model.reading_time_seconds))
            .where(self.model.user_id == user_id)
        )
        
        return {
            "total_attempts": total_attempts.scalar() or 0,
            "correct_attempts": correct_attempts.scalar() or 0,
            "accuracy_rate": (correct_attempts.scalar() or 0) / max(total_attempts.scalar() or 1, 1) * 100,
            "average_comprehension_score": float(avg_comprehension.scalar() or 0),
            "average_reading_speed_wpm": float(avg_speed.scalar() or 0),
            "total_reading_time_seconds": int(total_time.scalar() or 0)
        }


class CRUDVocabularyHighlight(CRUDBase[VocabularyHighlight, VocabularyHighlightCreate, VocabularyHighlightUpdate]):
    async def get_by_text(
        self, db: AsyncSession, *, reading_text_id: int
    ) -> List[VocabularyHighlight]:
        """Get vocabulary highlights for a reading text"""
        result = await db.execute(
            select(self.model)
            .where(self.model.reading_text_id == reading_text_id)
            .order_by(self.model.start_position)
        )
        return result.scalars().all()

    async def get_by_level(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel, 
        reading_text_id: Optional[int] = None
    ) -> List[VocabularyHighlight]:
        """Get vocabulary highlights by difficulty level"""
        conditions = [self.model.difficulty_level == level]
        
        if reading_text_id:
            conditions.append(self.model.reading_text_id == reading_text_id)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.word)
        )
        return result.scalars().all()

    async def search_vocabulary(
        self, 
        db: AsyncSession, 
        *, 
        query: str, 
        reading_text_id: Optional[int] = None
    ) -> List[VocabularyHighlight]:
        """Search vocabulary by word or definition"""
        conditions = [
            or_(
                self.model.word.ilike(f"%{query}%"),
                self.model.definition.ilike(f"%{query}%")
            )
        ]
        
        if reading_text_id:
            conditions.append(self.model.reading_text_id == reading_text_id)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.word)
        )
        return result.scalars().all()


class CRUDReadingProgress(CRUDBase[ReadingProgress, ReadingProgressUpdate, ReadingProgressUpdate]):
    async def get_by_user(self, db: AsyncSession, *, user_id: int) -> Optional[ReadingProgress]:
        """Get reading progress for a user"""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        progress_data: Dict[str, Any]
    ) -> ReadingProgress:
        """Create or update reading progress for a user"""
        existing = await self.get_by_user(db, user_id=user_id)
        
        if existing:
            # Update existing progress
            for key, value in progress_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            
            db.add(existing)
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            # Create new progress
            progress_data['user_id'] = user_id
            new_progress = ReadingProgress(**progress_data)
            db.add(new_progress)
            await db.commit()
            await db.refresh(new_progress)
            return new_progress

    async def update_reading_stats(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        reading_attempt: ReadingAttempt
    ) -> ReadingProgress:
        """Update reading progress based on a reading attempt"""
        progress = await self.get_by_user(db, user_id=user_id)
        
        if not progress:
            progress = ReadingProgress(user_id=user_id)
            db.add(progress)
        
        # Update reading metrics
        if reading_attempt.reading_time_seconds:
            progress.total_reading_time_minutes += reading_attempt.reading_time_seconds // 60
        
        # Update comprehension scores
        if reading_attempt.comprehension_score is not None:
            current_total = (
                progress.average_comprehension_score * progress.total_exercises_completed
            )
            progress.total_exercises_completed += 1
            progress.average_comprehension_score = (
                current_total + reading_attempt.comprehension_score
            ) / progress.total_exercises_completed
            
            if reading_attempt.is_correct:
                progress.total_exercises_correct += 1
        
        # Update reading speed
        if reading_attempt.words_per_minute:
            if progress.average_reading_speed_wpm == 0:
                progress.average_reading_speed_wpm = reading_attempt.words_per_minute
            else:
                # Calculate weighted average
                progress.average_reading_speed_wpm = (
                    progress.average_reading_speed_wpm * 0.8 + 
                    reading_attempt.words_per_minute * 0.2
                )
        
        # Update vocabulary learned
        if reading_attempt.vocabulary_learned:
            progress.total_vocabulary_learned += len(reading_attempt.vocabulary_learned)
        
        await db.commit()
        await db.refresh(progress)
        return progress


# Create CRUD instances
reading_text = CRUDReadingText(ReadingText)
reading_exercise = CRUDReadingExercise(ReadingExercise)
reading_attempt = CRUDReadingAttempt(ReadingAttempt)
vocabulary_highlight = CRUDVocabularyHighlight(VocabularyHighlight)
reading_progress = CRUDReadingProgress(ReadingProgress) 