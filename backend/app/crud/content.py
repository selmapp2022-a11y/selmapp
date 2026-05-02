from typing import Any, Dict, List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
import logging

from app.crud.base import CRUDBase
from app.models.content import (
    Content, Vocabulary, Grammar, ContentType, DifficultyLevel, VocabularyStatus,
    UserVocabulary, VocabularySet, VocabularySetItem, VocabularyExercise
)
from app.models.user import User
from app.schemas.content import (
    ContentCreate, ContentUpdate, VocabularyCreate, VocabularyUpdate,
    GrammarCreate, GrammarUpdate,
    VocabularyCreate, VocabularyUpdate, UserVocabularyCreate, UserVocabularyUpdate,
    VocabularySetCreate, VocabularySetUpdate, VocabularyExerciseCreate,
    VocabularySearchRequest
)

logger = logging.getLogger(__name__)

class CRUDContent(CRUDBase[Content, ContentCreate, ContentUpdate]):
    async def get_by_level_and_type(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel, 
        content_type: ContentType,
        skip: int = 0,
        limit: int = 100
    ) -> List[Content]:
        """Get content by difficulty level and type"""
        result = await db.execute(
            select(Content)
            .where(
                and_(
                    Content.difficulty_level == level,
                    Content.content_type == content_type,
                    Content.is_active == True
                )
            )
            .order_by(Content.order_index)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_level(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[Content]:
        """Get all content by difficulty level"""
        result = await db.execute(
            select(Content)
            .where(
                and_(
                    Content.difficulty_level == level,
                    Content.is_active == True
                )
            )
            .order_by(Content.content_type, Content.order_index)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def search_content(
        self, 
        db: AsyncSession, 
        *, 
        query: str,
        level: Optional[DifficultyLevel] = None,
        content_type: Optional[ContentType] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Content]:
        """Search content by title or description"""
        filters = [Content.is_active == True]
        
        if level:
            filters.append(Content.difficulty_level == level)
        if content_type:
            filters.append(Content.content_type == content_type)
        
        # Simple text search - in production, consider using full-text search
        filters.append(
            Content.title.ilike(f"%{query}%") | 
            Content.description.ilike(f"%{query}%")
        )
        
        result = await db.execute(
            select(Content)
            .where(and_(*filters))
            .order_by(Content.order_index)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_type_and_level(
        self,
        db: AsyncSession,
        *,
        content_type: str,
        difficulty_level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[Content]:
        """Get content by type and difficulty level"""
        result = await db.execute(
            select(Content)
            .where(
                and_(
                    Content.content_type == content_type,
                    Content.difficulty_level == difficulty_level,
                    Content.is_active == True
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

class CRUDGrammar(CRUDBase[Grammar, GrammarCreate, GrammarUpdate]):
    async def get_by_level(
        self,
        db: AsyncSession,
        *,
        level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[Grammar]:
        """Get grammar by difficulty level"""
        result = await db.execute(
            select(Grammar)
            .where(
                and_(
                    Grammar.difficulty_level == level,
                    Grammar.is_active == True
                )
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

class CRUDVocabulary(CRUDBase[Vocabulary, VocabularyCreate, VocabularyUpdate]):
    async def get_by_level(
        self, 
        db: AsyncSession, 
        *, 
        level: DifficultyLevel,
        skip: int = 0,
        limit: int = 100
    ) -> List[Vocabulary]:
        """Get vocabulary by difficulty level"""
        result = await db.execute(
            select(Vocabulary)
            .where(
                and_(
                    Vocabulary.difficulty_level == level,
                    Vocabulary.is_active == True
                )
            )
            .order_by(Vocabulary.frequency_rank.nulls_last(), Vocabulary.word)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_word(self, db: AsyncSession, *, word: str) -> Optional[Vocabulary]:
        """Get vocabulary by word"""
        result = await db.execute(
            select(Vocabulary).where(
                and_(
                    Vocabulary.word.ilike(word),
                    Vocabulary.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def search_vocabulary(
        self, 
        db: AsyncSession, 
        *, 
        search_request: VocabularySearchRequest
    ) -> tuple[List[Vocabulary], int]:
        """Advanced vocabulary search with filters"""
        query = select(Vocabulary).where(Vocabulary.is_active == True)
        count_query = select(func.count(Vocabulary.id)).where(Vocabulary.is_active == True)
        
        # Apply filters
        filters = []
        
        if search_request.query:
            filters.append(
                or_(
                    Vocabulary.word.ilike(f"%{search_request.query}%"),
                    Vocabulary.definition.ilike(f"%{search_request.query}%"),
                    Vocabulary.translation.ilike(f"%{search_request.query}%")
                )
            )
        
        if search_request.difficulty_levels:
            filters.append(Vocabulary.difficulty_level.in_(search_request.difficulty_levels))
        
        if search_request.part_of_speech:
            filters.append(Vocabulary.part_of_speech.in_(search_request.part_of_speech))
        
        if search_request.topics:
            # JSON array contains any of the topics (cast column to JSONB for safety)
            topic_filters = []
            for topic in search_request.topics:
                topic_filters.append(
                    Vocabulary.topic_categories.cast(postgresql.JSONB).contains([topic])
                )
            filters.append(or_(*topic_filters))
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Apply sorting
        if search_request.sort_by == "frequency":
            order_col = Vocabulary.frequency_rank.nulls_last()
        elif search_request.sort_by == "difficulty":
            order_col = Vocabulary.difficulty_level
        elif search_request.sort_by == "date_added":
            order_col = Vocabulary.created_at
        else:
            order_col = Vocabulary.word
        
        if search_request.sort_order == "desc":
            order_col = desc(order_col)
        else:
            order_col = asc(order_col)
        
        query = query.order_by(order_col)
        
        # Get total count
        total_result = await db.execute(count_query)
        total_count = total_result.scalar()
        
        # Apply pagination
        query = query.offset(search_request.skip).limit(search_request.limit)
        
        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()
        
        return items, total_count

    async def get_core_vocabulary_by_level(
        self,
        db: AsyncSession,
        *,
        level: DifficultyLevel,
        limit: int = 50
    ) -> List[Vocabulary]:
        """Get core vocabulary words for a specific level"""
        result = await db.execute(
            select(Vocabulary)
            .where(
                and_(
                    Vocabulary.difficulty_level == level,
                    Vocabulary.is_core_vocabulary == True,
                    Vocabulary.is_active == True
                )
            )
            .order_by(Vocabulary.frequency_rank.nulls_last())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_topic(
        self,
        db: AsyncSession,
        *,
        topic: str,
        level: Optional[DifficultyLevel] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Vocabulary]:
        """Get vocabulary by topic category"""
        filters = [
            Vocabulary.topic_categories.cast(postgresql.JSONB).contains([topic]),
            Vocabulary.is_active == True
        ]
        
        if level:
            filters.append(Vocabulary.difficulty_level == level)
        
        result = await db.execute(
            select(Vocabulary)
            .where(and_(*filters))
            .order_by(Vocabulary.frequency_rank.nulls_last())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_level_and_topic(
        self,
        db: AsyncSession,
        *,
        level: DifficultyLevel,
        topic: str,
        limit: int = 100
    ) -> List[Vocabulary]:
        """Get vocabulary by both level and topic"""
        return await self.get_by_topic(
            db, topic=topic, level=level, limit=limit
        )

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        vocabulary_items: List[VocabularyCreate],
        overwrite_existing: bool = False
    ) -> Dict[str, Any]:
        """Bulk import vocabulary items"""
        result = {
            "total_processed": len(vocabulary_items),
            "successful_imports": 0,
            "skipped_duplicates": 0,
            "errors": [],
            "imported_ids": []
        }
        
        for vocab_data in vocabulary_items:
            try:
                # Check if word already exists
                existing = await self.get_by_word(db, word=vocab_data.word)
                
                if existing and not overwrite_existing:
                    result["skipped_duplicates"] += 1
                    continue
                
                if existing and overwrite_existing:
                    # Update existing
                    updated_vocab = await self.update(
                        db, db_obj=existing, obj_in=vocab_data
                    )
                    result["imported_ids"].append(updated_vocab.id)
                else:
                    # Create new
                    new_vocab = await self.create(db, obj_in=vocab_data)
                    result["imported_ids"].append(new_vocab.id)
                
                result["successful_imports"] += 1
                
            except Exception as e:
                result["errors"].append(f"Error importing '{vocab_data.word}': {str(e)}")
                logger.error(f"Error importing vocabulary '{vocab_data.word}': {e}")
        
        return result

class CRUDUserVocabulary(CRUDBase[UserVocabulary, UserVocabularyCreate, UserVocabularyUpdate]):
    async def get_user_vocabulary(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        status: Optional[VocabularyStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[UserVocabulary]:
        """Get user's vocabulary with optional status filter"""
        query = (
            select(UserVocabulary)
            .options(selectinload(UserVocabulary.vocabulary))
            .where(UserVocabulary.user_id == user_id)
        )
        
        if status:
            query = query.where(UserVocabulary.status == status)
        
        query = query.order_by(UserVocabulary.last_reviewed_date.nulls_first())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    async def get_words_for_review(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        limit: int = 20
    ) -> List[UserVocabulary]:
        """Get words that are due for review"""
        now = datetime.utcnow()
        
        result = await db.execute(
            select(UserVocabulary)
            .options(selectinload(UserVocabulary.vocabulary))
            .where(
                and_(
                    UserVocabulary.user_id == user_id,
                    UserVocabulary.next_review_date <= now,
                    UserVocabulary.status.in_([VocabularyStatus.LEARNING, VocabularyStatus.REVIEW])
                )
            )
            .order_by(UserVocabulary.next_review_date)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_new_words_for_learning(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        user_level: DifficultyLevel,
        limit: int = 10
    ) -> List[Vocabulary]:
        """Get new words for the user to learn based on their level"""
        # Get words user hasn't encountered yet
        subquery = select(UserVocabulary.vocabulary_id).where(
            UserVocabulary.user_id == user_id
        )
        
        result = await db.execute(
            select(Vocabulary)
            .where(
                and_(
                    Vocabulary.difficulty_level == user_level,
                    Vocabulary.is_active == True,
                    ~Vocabulary.id.in_(subquery)
                )
            )
            .order_by(Vocabulary.frequency_rank.nulls_last())
            .limit(limit)
        )
        return result.scalars().all()

    async def update_learning_progress(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        vocabulary_id: int,
        is_correct: bool,
        response_time_seconds: Optional[int] = None
    ) -> UserVocabulary:
        """Update user's learning progress for a vocabulary word using spaced repetition"""
        # Get or create user vocabulary record
        user_vocab = await db.execute(
            select(UserVocabulary).where(
                and_(
                    UserVocabulary.user_id == user_id,
                    UserVocabulary.vocabulary_id == vocabulary_id
                )
            )
        )
        user_vocab = user_vocab.scalar_one_or_none()
        
        if not user_vocab:
            # Create new record
            user_vocab = UserVocabulary(
                user_id=user_id,
                vocabulary_id=vocabulary_id,
                status=VocabularyStatus.LEARNING
            )
            db.add(user_vocab)
        
        # Update statistics
        user_vocab.times_seen += 1
        user_vocab.last_reviewed_date = datetime.utcnow()
        
        if is_correct:
            user_vocab.times_correct += 1
            user_vocab.streak_count += 1
            
            # Update spaced repetition parameters (simplified Anki algorithm)
            if user_vocab.streak_count >= 2:
                user_vocab.ease_factor = max(1.3, user_vocab.ease_factor + 0.1)
                user_vocab.interval_days = int(user_vocab.interval_days * user_vocab.ease_factor)
            else:
                user_vocab.interval_days = min(user_vocab.interval_days + 1, 7)
            
            # Update mastery level
            user_vocab.mastery_level = min(1.0, user_vocab.mastery_level + 0.1)
            
            # Update status based on mastery
            if user_vocab.mastery_level >= 0.8 and user_vocab.streak_count >= 5:
                user_vocab.status = VocabularyStatus.MASTERED
            elif user_vocab.mastery_level >= 0.5:
                user_vocab.status = VocabularyStatus.REVIEW
        else:
            user_vocab.times_incorrect += 1
            user_vocab.streak_count = 0
            
            # Reset interval and reduce ease factor
            user_vocab.ease_factor = max(1.3, user_vocab.ease_factor - 0.2)
            user_vocab.interval_days = 1
            
            # Reduce mastery level
            user_vocab.mastery_level = max(0.0, user_vocab.mastery_level - 0.2)
            
            # Set status back to learning
            user_vocab.status = VocabularyStatus.LEARNING
        
        # Set next review date
        user_vocab.next_review_date = datetime.utcnow() + timedelta(days=user_vocab.interval_days)
        
        await db.commit()
        await db.refresh(user_vocab)
        return user_vocab

    async def get_learning_stats(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> Dict[str, Any]:
        """Get user's vocabulary learning statistics"""
        # Total words
        total_result = await db.execute(
            select(func.count(UserVocabulary.id)).where(UserVocabulary.user_id == user_id)
        )
        total_words = total_result.scalar() or 0
        
        # Words by status
        status_result = await db.execute(
            select(UserVocabulary.status, func.count(UserVocabulary.id))
            .where(UserVocabulary.user_id == user_id)
            .group_by(UserVocabulary.status)
        )
        words_by_status = {status: count for status, count in status_result.all()}
        
        # Average mastery
        mastery_result = await db.execute(
            select(func.avg(UserVocabulary.mastery_level))
            .where(UserVocabulary.user_id == user_id)
        )
        mastery_average = mastery_result.scalar() or 0.0
        
        # Words due for review today
        today = datetime.utcnow()
        review_result = await db.execute(
            select(func.count(UserVocabulary.id))
            .where(
                and_(
                    UserVocabulary.user_id == user_id,
                    UserVocabulary.next_review_date <= today
                )
            )
        )
        daily_review_count = review_result.scalar() or 0
        
        # Words by level (joining with vocabulary)
        level_result = await db.execute(
            select(Vocabulary.difficulty_level, func.count(UserVocabulary.id))
            .join(UserVocabulary.vocabulary)
            .where(UserVocabulary.user_id == user_id)
            .group_by(Vocabulary.difficulty_level)
        )
        words_by_level = {level.value: count for level, count in level_result.all()}
        
        return {
            "total_words": total_words,
            "words_by_level": words_by_level,
            "words_by_status": {status.value: count for status, count in words_by_status.items()},
            "mastery_average": float(mastery_average),
            "daily_review_count": daily_review_count,
            "streak_days": 0,  # TODO: Calculate streak
            "next_review_words": daily_review_count
        }

class CRUDVocabularySet(CRUDBase[VocabularySet, VocabularySetCreate, VocabularySetUpdate]):
    async def create_with_vocabulary(
        self,
        db: AsyncSession,
        *,
        obj_in: VocabularySetCreate,
        creator_id: int
    ) -> VocabularySet:
        """Create vocabulary set with associated vocabulary items"""
        # Create the set
        vocab_set_data = obj_in.dict(exclude={"vocabulary_ids"})
        vocab_set_data["created_by_user_id"] = creator_id
        
        vocab_set = VocabularySet(**vocab_set_data)
        db.add(vocab_set)
        await db.flush()  # Get the ID
        
        # Add vocabulary items if provided
        if obj_in.vocabulary_ids:
            for i, vocab_id in enumerate(obj_in.vocabulary_ids):
                set_item = VocabularySetItem(
                    vocabulary_set_id=vocab_set.id,
                    vocabulary_id=vocab_id,
                    order_index=i
                )
                db.add(set_item)
            
            vocab_set.word_count = len(obj_in.vocabulary_ids)
        
        await db.commit()
        await db.refresh(vocab_set)
        return vocab_set

    async def get_by_level_and_topic(
        self,
        db: AsyncSession,
        *,
        level: Optional[DifficultyLevel] = None,
        topic: Optional[str] = None,
        is_public: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[VocabularySet]:
        """Get vocabulary sets by level and topic"""
        filters = [VocabularySet.is_active == True]
        
        if is_public:
            filters.append(VocabularySet.is_public == True)
        
        if level:
            filters.append(VocabularySet.difficulty_level == level)
        
        if topic:
            filters.append(VocabularySet.topic.ilike(f"%{topic}%"))
        
        result = await db.execute(
            select(VocabularySet)
            .where(and_(*filters))
            .order_by(VocabularySet.is_featured.desc(), VocabularySet.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_with_items(
        self,
        db: AsyncSession,
        *,
        set_id: int
    ) -> Optional[VocabularySet]:
        """Get vocabulary set with all its items"""
        result = await db.execute(
            select(VocabularySet)
            .options(
                selectinload(VocabularySet.vocabulary_items)
                .selectinload(VocabularySetItem.vocabulary)
            )
            .where(VocabularySet.id == set_id)
        )
        return result.scalar_one_or_none()

class CRUDVocabularyExercise(CRUDBase[VocabularyExercise, VocabularyExerciseCreate, VocabularyExerciseCreate]):
    async def get_user_exercises(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        vocabulary_id: Optional[int] = None,
        exercise_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[VocabularyExercise]:
        """Get user's vocabulary exercises with optional filters"""
        filters = [VocabularyExercise.user_id == user_id]
        
        if vocabulary_id:
            filters.append(VocabularyExercise.vocabulary_id == vocabulary_id)
        
        if exercise_type:
            filters.append(VocabularyExercise.exercise_type == exercise_type)
        
        result = await db.execute(
            select(VocabularyExercise)
            .options(selectinload(VocabularyExercise.vocabulary))
            .where(and_(*filters))
            .order_by(VocabularyExercise.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_exercise_stats(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user's exercise statistics"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Total exercises
        total_result = await db.execute(
            select(func.count(VocabularyExercise.id))
            .where(
                and_(
                    VocabularyExercise.user_id == user_id,
                    VocabularyExercise.created_at >= since_date
                )
            )
        )
        total_exercises = total_result.scalar() or 0
        
        # Correct exercises
        correct_result = await db.execute(
            select(func.count(VocabularyExercise.id))
            .where(
                and_(
                    VocabularyExercise.user_id == user_id,
                    VocabularyExercise.created_at >= since_date,
                    VocabularyExercise.is_correct == True
                )
            )
        )
        correct_exercises = correct_result.scalar() or 0
        
        # Exercises by type
        type_result = await db.execute(
            select(VocabularyExercise.exercise_type, func.count(VocabularyExercise.id))
            .where(
                and_(
                    VocabularyExercise.user_id == user_id,
                    VocabularyExercise.created_at >= since_date
                )
            )
            .group_by(VocabularyExercise.exercise_type)
        )
        exercises_by_type = {ex_type: count for ex_type, count in type_result.all()}
        
        accuracy = (correct_exercises / total_exercises * 100) if total_exercises > 0 else 0
        
        return {
            "total_exercises": total_exercises,
            "correct_exercises": correct_exercises,
            "accuracy_percentage": round(accuracy, 2),
            "exercises_by_type": exercises_by_type
        }

# Create CRUD instances
content_crud = CRUDContent(Content)
grammar_crud = CRUDGrammar(Grammar)
vocabulary_crud = CRUDVocabulary(Vocabulary)
user_vocabulary_crud = CRUDUserVocabulary(UserVocabulary)
vocabulary_set_crud = CRUDVocabularySet(VocabularySet)
vocabulary_exercise_crud = CRUDVocabularyExercise(VocabularyExercise) 