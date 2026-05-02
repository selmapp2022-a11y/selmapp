from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from app.crud.base import CRUDBase
from app.models.speaking import (
    SpeakingPrompt, SpeakingAttempt, PronunciationExercise, 
    PronunciationAttempt, SpeakingProgress, SpeakingSession, VoiceProfile,
    SpeakingExerciseType, PronunciationFocus, DifficultyLevel
)
from app.schemas.speaking import (
    SpeakingPromptCreate, SpeakingPromptUpdate,
    SpeakingAttemptCreate, SpeakingAttemptUpdate,
    PronunciationExerciseCreate, PronunciationExerciseUpdate,
    PronunciationAttemptCreate, PronunciationAttemptUpdate,
    SpeakingProgressCreate, SpeakingProgressUpdate,
    SpeakingSessionCreate, SpeakingSessionUpdate,
    VoiceProfileCreate, VoiceProfileUpdate
)


class CRUDSpeakingPrompt(CRUDBase[SpeakingPrompt, SpeakingPromptCreate, SpeakingPromptUpdate]):
    def get_by_difficulty(
        self, db: Session, *, difficulty: DifficultyLevel, skip: int = 0, limit: int = 100
    ) -> List[SpeakingPrompt]:
        return (
            db.query(self.model)
            .filter(self.model.difficulty_level == difficulty)
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_exercise_type(
        self, db: Session, *, exercise_type: SpeakingExerciseType, skip: int = 0, limit: int = 100
    ) -> List[SpeakingPrompt]:
        return (
            db.query(self.model)
            .filter(self.model.exercise_type == exercise_type)
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search(
        self, db: Session, *, query: str, skip: int = 0, limit: int = 100
    ) -> List[SpeakingPrompt]:
        return (
            db.query(self.model)
            .filter(
                or_(
                    self.model.title.ilike(f"%{query}%"),
                    self.model.description.ilike(f"%{query}%"),
                    self.model.topic.ilike(f"%{query}%")
                )
            )
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_random(
        self, db: Session, *, difficulty: Optional[DifficultyLevel] = None, 
        exercise_type: Optional[SpeakingExerciseType] = None, limit: int = 1
    ) -> List[SpeakingPrompt]:
        query = db.query(self.model).filter(self.model.is_active == True)
        
        if difficulty:
            query = query.filter(self.model.difficulty_level == difficulty)
        if exercise_type:
            query = query.filter(self.model.exercise_type == exercise_type)
            
        return query.order_by(func.random()).limit(limit).all()


class CRUDSpeakingAttempt(CRUDBase[SpeakingAttempt, SpeakingAttemptCreate, SpeakingAttemptUpdate]):
    def get_by_user(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[SpeakingAttempt]:
        return (
            db.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_prompt(
        self, db: Session, *, prompt_id: int, user_id: Optional[int] = None, 
        skip: int = 0, limit: int = 100
    ) -> List[SpeakingAttempt]:
        query = db.query(self.model).filter(self.model.prompt_id == prompt_id)
        if user_id:
            query = query.filter(self.model.user_id == user_id)
        return query.order_by(desc(self.model.created_at)).offset(skip).limit(limit).all()

    def get_user_statistics(self, db: Session, *, user_id: int) -> Dict[str, Any]:
        attempts = db.query(self.model).filter(self.model.user_id == user_id).all()
        
        if not attempts:
            return {
                "total_attempts": 0,
                "average_pronunciation_score": 0.0,
                "average_fluency_score": 0.0,
                "total_speaking_time": 0,
                "best_score": 0.0
            }

        total_speaking_time = sum(attempt.duration_seconds or 0 for attempt in attempts)
        pronunciation_scores = [a.pronunciation_score for a in attempts if a.pronunciation_score]
        fluency_scores = [a.fluency_score for a in attempts if a.fluency_score]
        overall_scores = [a.ai_overall_score for a in attempts if a.ai_overall_score]

        return {
            "total_attempts": len(attempts),
            "average_pronunciation_score": sum(pronunciation_scores) / len(pronunciation_scores) if pronunciation_scores else 0.0,
            "average_fluency_score": sum(fluency_scores) / len(fluency_scores) if fluency_scores else 0.0,
            "total_speaking_time": int(total_speaking_time),
            "best_score": max(overall_scores) if overall_scores else 0.0
        }


class CRUDPronunciationExercise(CRUDBase[PronunciationExercise, PronunciationExerciseCreate, PronunciationExerciseUpdate]):
    def get_by_focus(
        self, db: Session, *, focus: PronunciationFocus, skip: int = 0, limit: int = 100
    ) -> List[PronunciationExercise]:
        return (
            db.query(self.model)
            .filter(self.model.pronunciation_focus == focus)
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_difficulty(
        self, db: Session, *, difficulty: DifficultyLevel, skip: int = 0, limit: int = 100
    ) -> List[PronunciationExercise]:
        return (
            db.query(self.model)
            .filter(self.model.difficulty_level == difficulty)
            .filter(self.model.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )


class CRUDPronunciationAttempt(CRUDBase[PronunciationAttempt, PronunciationAttemptCreate, PronunciationAttemptUpdate]):
    def get_by_user(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[PronunciationAttempt]:
        return (
            db.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_exercise(
        self, db: Session, *, exercise_id: int, user_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[PronunciationAttempt]:
        query = db.query(self.model).filter(self.model.exercise_id == exercise_id)
        if user_id:
            query = query.filter(self.model.user_id == user_id)
        return query.order_by(desc(self.model.created_at)).offset(skip).limit(limit).all()


class CRUDSpeakingProgress(CRUDBase[SpeakingProgress, SpeakingProgressCreate, SpeakingProgressUpdate]):
    def get_by_user(self, db: Session, *, user_id: int) -> Optional[SpeakingProgress]:
        return db.query(self.model).filter(self.model.user_id == user_id).first()

    def update_progress(
        self, db: Session, *, user_id: int, attempt: SpeakingAttempt
    ) -> SpeakingProgress:
        progress = self.get_by_user(db, user_id=user_id)
        
        if not progress:
            progress = SpeakingProgress(
                user_id=user_id,
                current_level=DifficultyLevel.A1,
                total_speaking_time=0,
                total_attempts=0,
                total_prompts_completed=0
            )
            db.add(progress)
            db.flush()

        # Update statistics
        progress.total_attempts += 1
        progress.total_speaking_time += int(attempt.duration_seconds or 0)
        
        if attempt.ai_overall_score and attempt.ai_overall_score >= 70:  # Threshold for completion
            progress.total_prompts_completed += 1

        # Update average scores
        if attempt.pronunciation_score:
            current_avg = progress.average_pronunciation_score or 0.0
            progress.average_pronunciation_score = (
                (current_avg * (progress.total_attempts - 1) + attempt.pronunciation_score) / 
                progress.total_attempts
            )

        if attempt.fluency_score:
            current_avg = progress.average_fluency_score or 0.0
            progress.average_fluency_score = (
                (current_avg * (progress.total_attempts - 1) + attempt.fluency_score) / 
                progress.total_attempts
            )

        progress.last_activity_date = datetime.utcnow()
        db.commit()
        return progress


class CRUDSpeakingSession(CRUDBase[SpeakingSession, SpeakingSessionCreate, SpeakingSessionUpdate]):
    def get_by_user(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[SpeakingSession]:
        return (
            db.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_session(self, db: Session, *, user_id: int) -> Optional[SpeakingSession]:
        return (
            db.query(self.model)
            .filter(
                and_(
                    self.model.user_id == user_id,
                    self.model.ended_at.is_(None)
                )
            )
            .first()
        )


class CRUDVoiceProfile(CRUDBase[VoiceProfile, VoiceProfileCreate, VoiceProfileUpdate]):
    def get_by_user(self, db: Session, *, user_id: int) -> Optional[VoiceProfile]:
        return db.query(self.model).filter(self.model.user_id == user_id).first()

    def is_calibrated(self, db: Session, *, user_id: int) -> bool:
        profile = self.get_by_user(db, user_id=user_id)
        return profile and profile.calibration_completed


# CRUD instances
speaking_prompt = CRUDSpeakingPrompt(SpeakingPrompt)
speaking_attempt = CRUDSpeakingAttempt(SpeakingAttempt)
pronunciation_exercise = CRUDPronunciationExercise(PronunciationExercise)
pronunciation_attempt = CRUDPronunciationAttempt(PronunciationAttempt)
speaking_progress = CRUDSpeakingProgress(SpeakingProgress)
speaking_session = CRUDSpeakingSession(SpeakingSession)
voice_profile = CRUDVoiceProfile(VoiceProfile)