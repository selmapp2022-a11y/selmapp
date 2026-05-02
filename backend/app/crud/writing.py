from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.crud.base import CRUDBase
from app.models.writing import (
    WritingPrompt, WritingSubmission, WritingFeedback, 
    WritingTemplate, WritingProgress, GrammarRule,
    WritingType, WritingSkillLevel
)
from app.models.content import DifficultyLevel
from app.schemas.writing import (
    WritingPromptCreate, WritingPromptUpdate,
    WritingSubmissionCreate, WritingSubmissionUpdate, WritingSubmissionSubmit,
    WritingFeedbackCreate, WritingFeedbackUpdate,
    WritingTemplateCreate, WritingTemplateUpdate,
    WritingProgressUpdate,
    GrammarRuleCreate, GrammarRuleUpdate
)


class CRUDWritingPrompt(CRUDBase[WritingPrompt, WritingPromptCreate, WritingPromptUpdate]):
    async def get_by_level(
        self, db: AsyncSession, *, level: DifficultyLevel, skip: int = 0, limit: int = 100
    ) -> List[WritingPrompt]:
        """Get writing prompts by difficulty level"""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.difficulty_level == level, self.model.is_active == True))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_type(
        self, db: AsyncSession, *, writing_type: WritingType, skip: int = 0, limit: int = 100
    ) -> List[WritingPrompt]:
        """Get writing prompts by type"""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.writing_type == writing_type, self.model.is_active == True))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_skill_level(
        self, db: AsyncSession, *, skill_level: WritingSkillLevel, skip: int = 0, limit: int = 100
    ) -> List[WritingPrompt]:
        """Get writing prompts by skill level"""
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.skill_level == skill_level, self.model.is_active == True))
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
        writing_type: WritingType,
        skill_level: Optional[WritingSkillLevel] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[WritingPrompt]:
        """Get writing prompts by level, type, and optionally skill level"""
        conditions = [
            self.model.difficulty_level == level,
            self.model.writing_type == writing_type,
            self.model.is_active == True
        ]
        
        if skill_level:
            conditions.append(self.model.skill_level == skill_level)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def search_prompts(
        self, 
        db: AsyncSession, 
        *, 
        query: str, 
        level: Optional[DifficultyLevel] = None,
        writing_type: Optional[WritingType] = None,
        skip: int = 0, 
        limit: int = 100
    ) -> List[WritingPrompt]:
        """Search writing prompts by title, prompt text, or topic"""
        conditions = [self.model.is_active == True]
        
        # Add search condition
        search_condition = or_(
            self.model.title.ilike(f"%{query}%"),
            self.model.prompt_text.ilike(f"%{query}%"),
            self.model.topic.ilike(f"%{query}%")
        )
        conditions.append(search_condition)
        
        # Add optional filters
        if level:
            conditions.append(self.model.difficulty_level == level)
        if writing_type:
            conditions.append(self.model.writing_type == writing_type)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def get_random_prompts(
        self, 
        db: AsyncSession, 
        *, 
        level: Optional[DifficultyLevel] = None,
        writing_type: Optional[WritingType] = None,
        limit: int = 5
    ) -> List[WritingPrompt]:
        """Get random writing prompts for practice"""
        conditions = [self.model.is_active == True]
        
        if level:
            conditions.append(self.model.difficulty_level == level)
        if writing_type:
            conditions.append(self.model.writing_type == writing_type)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(func.random())
            .limit(limit)
        )
        return result.scalars().all()


class CRUDWritingSubmission(CRUDBase[WritingSubmission, WritingSubmissionCreate, WritingSubmissionUpdate]):
    async def get_user_submissions(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[WritingSubmission]:
        """Get user's writing submissions"""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(self.model.submitted_at.desc())
        )
        return result.scalars().all()

    async def get_prompt_submissions(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        writing_prompt_id: int
    ) -> List[WritingSubmission]:
        """Get user's submissions for a specific prompt"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.user_id == user_id,
                self.model.writing_prompt_id == writing_prompt_id
            ))
            .order_by(self.model.submitted_at.desc())
        )
        return result.scalars().all()

    async def get_drafts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int
    ) -> List[WritingSubmission]:
        """Get user's draft submissions"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.user_id == user_id,
                self.model.is_draft == True
            ))
            .order_by(self.model.submitted_at.desc())
        )
        return result.scalars().all()

    async def get_with_feedback(
        self, db: AsyncSession, *, id: int
    ) -> Optional[WritingSubmission]:
        """Get submission with feedback"""
        result = await db.execute(
            select(self.model)
            .options(selectinload(self.model.writing_feedback))
            .options(selectinload(self.model.writing_prompt))
            .where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_user_stats(self, db: AsyncSession, *, user_id: int) -> Dict[str, Any]:
        """Get user's writing statistics"""
        # Total submissions
        total_submissions = await db.execute(
            select(func.count(self.model.id))
            .where(and_(self.model.user_id == user_id, self.model.is_draft == False))
        )
        
        # Average scores
        avg_overall = await db.execute(
            select(func.avg(self.model.overall_score))
            .where(and_(
                self.model.user_id == user_id, 
                self.model.is_draft == False,
                self.model.is_evaluated == True
            ))
        )
        
        avg_grammar = await db.execute(
            select(func.avg(self.model.grammar_score))
            .where(and_(
                self.model.user_id == user_id, 
                self.model.is_draft == False,
                self.model.is_evaluated == True
            ))
        )
        
        avg_vocabulary = await db.execute(
            select(func.avg(self.model.vocabulary_score))
            .where(and_(
                self.model.user_id == user_id, 
                self.model.is_draft == False,
                self.model.is_evaluated == True
            ))
        )
        
        # Total words written
        total_words = await db.execute(
            select(func.sum(self.model.word_count))
            .where(and_(self.model.user_id == user_id, self.model.is_draft == False))
        )
        
        # Total time spent
        total_time = await db.execute(
            select(func.sum(self.model.time_spent_minutes))
            .where(and_(self.model.user_id == user_id, self.model.is_draft == False))
        )
        
        # Best score
        best_score = await db.execute(
            select(func.max(self.model.overall_score))
            .where(and_(
                self.model.user_id == user_id, 
                self.model.is_draft == False,
                self.model.is_evaluated == True
            ))
        )
        
        return {
            "total_submissions": total_submissions.scalar() or 0,
            "average_overall_score": float(avg_overall.scalar() or 0),
            "average_grammar_score": float(avg_grammar.scalar() or 0),
            "average_vocabulary_score": float(avg_vocabulary.scalar() or 0),
            "total_words_written": int(total_words.scalar() or 0),
            "total_time_minutes": int(total_time.scalar() or 0),
            "best_score": float(best_score.scalar() or 0)
        }

    async def get_recent_submissions(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        days: int = 30
    ) -> List[WritingSubmission]:
        """Get user's recent submissions"""
        since_date = datetime.utcnow() - timedelta(days=days)
        
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.user_id == user_id,
                self.model.submitted_at >= since_date,
                self.model.is_draft == False
            ))
            .order_by(self.model.submitted_at.desc())
        )
        return result.scalars().all()


class CRUDWritingFeedback(CRUDBase[WritingFeedback, WritingFeedbackCreate, WritingFeedbackUpdate]):
    async def get_by_submission(
        self, db: AsyncSession, *, writing_submission_id: int
    ) -> Optional[WritingFeedback]:
        """Get feedback for a writing submission"""
        result = await db.execute(
            select(self.model)
            .where(self.model.writing_submission_id == writing_submission_id)
        )
        return result.scalar_one_or_none()

    async def get_user_feedback_history(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[WritingFeedback]:
        """Get feedback history for a user"""
        result = await db.execute(
            select(self.model)
            .join(WritingSubmission)
            .where(WritingSubmission.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(self.model.generated_at.desc())
        )
        return result.scalars().all()


class CRUDWritingTemplate(CRUDBase[WritingTemplate, WritingTemplateCreate, WritingTemplateUpdate]):
    async def get_by_type(
        self, db: AsyncSession, *, writing_type: WritingType
    ) -> List[WritingTemplate]:
        """Get templates by writing type"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.writing_type == writing_type,
                self.model.is_active == True
            ))
            .order_by(self.model.difficulty_level, self.model.name)
        )
        return result.scalars().all()

    async def get_by_level(
        self, db: AsyncSession, *, level: DifficultyLevel
    ) -> List[WritingTemplate]:
        """Get templates by difficulty level"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.difficulty_level == level,
                self.model.is_active == True
            ))
            .order_by(self.model.writing_type, self.model.name)
        )
        return result.scalars().all()

    async def get_by_type_and_level(
        self, 
        db: AsyncSession, 
        *, 
        writing_type: WritingType, 
        level: DifficultyLevel
    ) -> List[WritingTemplate]:
        """Get templates by type and level"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.writing_type == writing_type,
                self.model.difficulty_level == level,
                self.model.is_active == True
            ))
            .order_by(self.model.name)
        )
        return result.scalars().all()


class CRUDWritingProgress(CRUDBase[WritingProgress, WritingProgressUpdate, WritingProgressUpdate]):
    async def get_by_user(self, db: AsyncSession, *, user_id: int) -> Optional[WritingProgress]:
        """Get writing progress for a user"""
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
    ) -> WritingProgress:
        """Create or update writing progress for a user"""
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
            new_progress = WritingProgress(**progress_data)
            db.add(new_progress)
            await db.commit()
            await db.refresh(new_progress)
            return new_progress

    async def update_writing_stats(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        writing_submission: WritingSubmission
    ) -> WritingProgress:
        """Update writing progress based on a writing submission"""
        progress = await self.get_by_user(db, user_id=user_id)
        
        if not progress:
            progress = WritingProgress(user_id=user_id)
            db.add(progress)
        
        # Update submission count
        if not writing_submission.is_draft:
            progress.total_submissions += 1
            progress.total_words_written += writing_submission.word_count
            
            if writing_submission.time_spent_minutes:
                progress.total_writing_time_minutes += writing_submission.time_spent_minutes
                
                # Calculate writing speed (words per minute)
                if writing_submission.time_spent_minutes > 0:
                    current_wpm = writing_submission.word_count / writing_submission.time_spent_minutes
                    if progress.writing_speed_wpm == 0:
                        progress.writing_speed_wpm = current_wpm
                    else:
                        # Calculate weighted average
                        progress.writing_speed_wpm = (
                            progress.writing_speed_wpm * 0.8 + current_wpm * 0.2
                        )
        
        # Update scores if evaluated
        if writing_submission.is_evaluated and not writing_submission.is_draft:
            # Update average scores
            if progress.total_submissions == 1:
                progress.average_score = writing_submission.overall_score
                progress.average_grammar_score = writing_submission.grammar_score
                progress.average_vocabulary_score = writing_submission.vocabulary_score
            else:
                # Calculate weighted averages
                weight = 1.0 / progress.total_submissions
                progress.average_score = (
                    progress.average_score * (1 - weight) + 
                    writing_submission.overall_score * weight
                )
                progress.average_grammar_score = (
                    progress.average_grammar_score * (1 - weight) + 
                    writing_submission.grammar_score * weight
                )
                progress.average_vocabulary_score = (
                    progress.average_vocabulary_score * (1 - weight) + 
                    writing_submission.vocabulary_score * weight
                )
            
            # Update best score
            if writing_submission.overall_score > progress.best_score:
                progress.best_score = writing_submission.overall_score
        
        await db.commit()
        await db.refresh(progress)
        return progress


class CRUDGrammarRule(CRUDBase[GrammarRule, GrammarRuleCreate, GrammarRuleUpdate]):
    async def get_by_category(
        self, db: AsyncSession, *, category: str
    ) -> List[GrammarRule]:
        """Get grammar rules by category"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.category == category,
                self.model.is_active == True
            ))
            .order_by(self.model.priority.desc(), self.model.name)
        )
        return result.scalars().all()

    async def get_by_level(
        self, db: AsyncSession, *, level: DifficultyLevel
    ) -> List[GrammarRule]:
        """Get grammar rules by difficulty level"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                self.model.difficulty_level == level,
                self.model.is_active == True
            ))
            .order_by(self.model.priority.desc(), self.model.category, self.model.name)
        )
        return result.scalars().all()

    async def get_active_rules(
        self, 
        db: AsyncSession, 
        *, 
        category: Optional[str] = None,
        level: Optional[DifficultyLevel] = None
    ) -> List[GrammarRule]:
        """Get active grammar rules with optional filters"""
        conditions = [self.model.is_active == True]
        
        if category:
            conditions.append(self.model.category == category)
        if level:
            conditions.append(self.model.difficulty_level == level)
        
        result = await db.execute(
            select(self.model)
            .where(and_(*conditions))
            .order_by(self.model.priority.desc(), self.model.category, self.model.name)
        )
        return result.scalars().all()

    async def search_rules(
        self, 
        db: AsyncSession, 
        *, 
        query: str
    ) -> List[GrammarRule]:
        """Search grammar rules by name or description"""
        result = await db.execute(
            select(self.model)
            .where(and_(
                or_(
                    self.model.name.ilike(f"%{query}%"),
                    self.model.rule_description.ilike(f"%{query}%")
                ),
                self.model.is_active == True
            ))
            .order_by(self.model.priority.desc(), self.model.name)
        )
        return result.scalars().all()


# Create CRUD instances
writing_prompt = CRUDWritingPrompt(WritingPrompt)
writing_submission = CRUDWritingSubmission(WritingSubmission)
writing_feedback = CRUDWritingFeedback(WritingFeedback)
writing_template = CRUDWritingTemplate(WritingTemplate)
writing_progress = CRUDWritingProgress(WritingProgress)
grammar_rule = CRUDGrammarRule(GrammarRule) 