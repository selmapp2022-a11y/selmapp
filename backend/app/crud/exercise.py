from typing import Any, Dict, List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, Integer, case
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.exercise import (
    Exercise, ExerciseAttempt, Quiz, QuizExercise, QuizAttempt,
    ExerciseType, DifficultyLevel
)
from app.schemas.exercise import (
    ExerciseCreate, ExerciseUpdate, ExerciseAttemptCreate,
    QuizCreate, QuizUpdate, QuizAttemptCreate
)

class CRUDExercise(CRUDBase[Exercise, ExerciseCreate, ExerciseUpdate]):
    async def get_by_level(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[Exercise]:
        """Get exercises by difficulty level"""
        result = await db.execute(
            select(Exercise)
            .where(
                and_(
                    Exercise.difficulty_level == level,
                    Exercise.is_active == True
                )
            )
            .order_by(Exercise.order_index)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_type_and_level(
        self, 
        db: AsyncSession, 
        *, 
        exercise_type: ExerciseType,
        level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[Exercise]:
        """Get exercises by type and difficulty level"""
        result = await db.execute(
            select(Exercise)
            .where(
                and_(
                    Exercise.exercise_type == exercise_type,
                    Exercise.difficulty_level == level,
                    Exercise.is_active == True
                )
            )
            .order_by(Exercise.order_index)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_content(
        self, 
        db: AsyncSession, 
        *, 
        content_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[Exercise]:
        """Get exercises by content ID"""
        result = await db.execute(
            select(Exercise)
            .where(
                and_(
                    Exercise.content_id == content_id,
                    Exercise.is_active == True
                )
            )
            .order_by(Exercise.order_index)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_random_exercises(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel,
        exercise_type: Optional[ExerciseType] = None,
        count: int = 10
    ) -> List[Exercise]:
        """Get random exercises for practice"""
        filters = [
            Exercise.difficulty_level == level,
            Exercise.is_active == True
        ]
        
        if exercise_type:
            filters.append(Exercise.exercise_type == exercise_type)
        
        result = await db.execute(
            select(Exercise)
            .where(and_(*filters))
            .order_by(func.random())
            .limit(count)
        )
        return result.scalars().all()

class CRUDExerciseAttempt(CRUDBase[ExerciseAttempt, ExerciseAttemptCreate, ExerciseAttemptCreate]):
    async def get_user_attempts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[ExerciseAttempt]:
        """Get user's exercise attempts"""
        result = await db.execute(
            select(ExerciseAttempt)
            .options(selectinload(ExerciseAttempt.exercise))
            .where(ExerciseAttempt.user_id == user_id)
            .order_by(desc(ExerciseAttempt.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_exercise_attempts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int,
        exercise_id: int
    ) -> List[ExerciseAttempt]:
        """Get user's attempts for a specific exercise"""
        result = await db.execute(
            select(ExerciseAttempt)
            .where(
                and_(
                    ExerciseAttempt.user_id == user_id,
                    ExerciseAttempt.exercise_id == exercise_id
                )
            )
            .order_by(desc(ExerciseAttempt.created_at))
        )
        return result.scalars().all()

    async def get_user_statistics(
        self, db: AsyncSession, *, user_id: int
    ) -> Dict[str, Any]:
        """Get user's exercise statistics"""
        result = await db.execute(
            select(
                func.count(ExerciseAttempt.id).label('total_attempts'),
                func.sum(case((ExerciseAttempt.is_correct == True, 1), else_=0)).label('correct_attempts'),
                func.avg(ExerciseAttempt.score).label('average_score'),
                func.avg(ExerciseAttempt.time_taken_seconds).label('average_time')
            )
            .where(ExerciseAttempt.user_id == user_id)
        )
        stats = result.first()
        
        total_attempts = stats.total_attempts or 0 if stats else 0
        correct_attempts = stats.correct_attempts or 0 if stats else 0
        
        return {
            'total_attempts': total_attempts,
            'correct_attempts': correct_attempts,
            'accuracy_rate': (correct_attempts / total_attempts * 100) if total_attempts else 0,
            'average_score': float(stats.average_score) if stats and stats.average_score else 0,
            'average_time': float(stats.average_time) if stats and stats.average_time else 0
        }

    async def get_recent_performance(
        self, db: AsyncSession, *, user_id: int, days: int = 7
    ) -> List[Dict[str, Any]]:
        """Get user's recent performance"""
        from datetime import datetime, timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = await db.execute(
            select([
                func.date(ExerciseAttempt.created_at).label('date'),
                func.count(ExerciseAttempt.id).label('attempts'),
                func.sum(func.cast(ExerciseAttempt.is_correct, 'integer')).label('correct'),
                func.avg(ExerciseAttempt.score).label('avg_score')
            ])
            .where(
                and_(
                    ExerciseAttempt.user_id == user_id,
                    ExerciseAttempt.created_at >= start_date
                )
            )
            .group_by(func.date(ExerciseAttempt.created_at))
            .order_by(func.date(ExerciseAttempt.created_at))
        )
        
        return [
            {
                'date': row.date,
                'attempts': row.attempts,
                'correct': row.correct,
                'accuracy': (row.correct / row.attempts * 100) if row.attempts else 0,
                'average_score': float(row.avg_score) if row.avg_score else 0
            }
            for row in result
        ]

class CRUDQuiz(CRUDBase[Quiz, QuizCreate, QuizUpdate]):
    async def get_by_level(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[Quiz]:
        """Get quizzes by difficulty level"""
        result = await db.execute(
            select(Quiz)
            .where(
                and_(
                    Quiz.difficulty_level == level,
                    Quiz.is_active == True
                )
            )
            .order_by(Quiz.title)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_with_exercises(
        self, db: AsyncSession, *, quiz_id: int
    ) -> Optional[Quiz]:
        """Get quiz with its exercises"""
        result = await db.execute(
            select(Quiz)
            .options(
                selectinload(Quiz.quiz_exercises)
                .selectinload(QuizExercise.exercise)
            )
            .where(Quiz.id == quiz_id)
        )
        return result.scalar_one_or_none()

    async def add_exercise_to_quiz(
        self, db: AsyncSession, *, quiz_id: int, exercise_id: int, order_index: int = 0
    ) -> QuizExercise:
        """Add exercise to quiz"""
        quiz_exercise = QuizExercise(
            quiz_id=quiz_id,
            exercise_id=exercise_id,
            order_index=order_index
        )
        db.add(quiz_exercise)
        await db.commit()
        await db.refresh(quiz_exercise)
        return quiz_exercise

class CRUDQuizAttempt(CRUDBase[QuizAttempt, QuizAttemptCreate, QuizAttemptCreate]):
    async def get_user_attempts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[QuizAttempt]:
        """Get user's quiz attempts"""
        result = await db.execute(
            select(QuizAttempt)
            .options(selectinload(QuizAttempt.quiz))
            .where(QuizAttempt.user_id == user_id)
            .order_by(desc(QuizAttempt.started_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_quiz_attempts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int,
        quiz_id: int
    ) -> List[QuizAttempt]:
        """Get user's attempts for a specific quiz"""
        result = await db.execute(
            select(QuizAttempt)
            .where(
                and_(
                    QuizAttempt.user_id == user_id,
                    QuizAttempt.quiz_id == quiz_id
                )
            )
            .order_by(desc(QuizAttempt.started_at))
        )
        return result.scalars().all()

    async def get_best_attempt(
        self, db: AsyncSession, *, user_id: int, quiz_id: int
    ) -> Optional[QuizAttempt]:
        """Get user's best attempt for a quiz"""
        result = await db.execute(
            select(QuizAttempt)
            .where(
                and_(
                    QuizAttempt.user_id == user_id,
                    QuizAttempt.quiz_id == quiz_id
                )
            )
            .order_by(desc(QuizAttempt.score))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def can_attempt_quiz(
        self, db: AsyncSession, *, user_id: int, quiz_id: int
    ) -> bool:
        """Check if user can attempt quiz (based on max attempts)"""
        quiz = await db.execute(select(Quiz).where(Quiz.id == quiz_id))
        quiz = quiz.scalar_one_or_none()
        
        if not quiz or quiz.max_attempts == 0:
            return True
        
        attempt_count = await db.execute(
            select(func.count(QuizAttempt.id))
            .where(
                and_(
                    QuizAttempt.user_id == user_id,
                    QuizAttempt.quiz_id == quiz_id
                )
            )
        )
        count = attempt_count.scalar()
        
        return count < quiz.max_attempts

# Create instances
exercise_crud = CRUDExercise(Exercise)
exercise_attempt_crud = CRUDExerciseAttempt(ExerciseAttempt)
quiz_crud = CRUDQuiz(Quiz)
quiz_attempt_crud = CRUDQuizAttempt(QuizAttempt) 