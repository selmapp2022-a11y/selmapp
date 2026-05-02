from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from uuid import UUID
from datetime import datetime, timedelta, timezone
import logging

from app.crud.base import CRUDBase
from app.models.assessment_job import AssessmentJob

logger = logging.getLogger(__name__)

# Jobs older than this are considered stale and should be cancelled
# Set to 4 minutes to fail before frontend's 3 minute timeout
STALE_JOB_TIMEOUT_MINUTES = 4


class CRUDAssessmentJob(CRUDBase[AssessmentJob, Dict[str, Any], Dict[str, Any]]):
    async def create_job(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        question_count: int,
        user_preferences: Optional[list] = None,
        personalized: bool = True
    ) -> AssessmentJob:
        data = {
            "user_id": user_id,
            "status": "pending",
            "progress": 0,
            "question_count": question_count,
            "user_preferences": user_preferences or [],
            "personalized": personalized,
        }
        return await self.create(db, obj_in=data)

    async def get_by_id_for_user(
        self, db: AsyncSession, *, job_id: UUID, user_id: int
    ) -> Optional[AssessmentJob]:
        result = await db.execute(
            select(self.model).where(self.model.id == job_id, self.model.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_in_flight_for_user(self, db: AsyncSession, *, user_id: int) -> Optional[AssessmentJob]:
        """Return the latest pending/processing job for a user, if any.
        
        Jobs older than STALE_JOB_TIMEOUT_MINUTES are considered stale and will be
        automatically marked as failed before returning None.
        """
        result = await db.execute(
            select(self.model)
            .where(and_(self.model.user_id == user_id, self.model.status.in_(["pending", "processing"])))
            .order_by(desc(self.model.created_at))
        )
        job = result.scalars().first()
        
        if job:
            # Check if job is stale (older than timeout)
            # Use timezone-aware datetime for comparison
            now = datetime.now(timezone.utc)
            stale_threshold = now - timedelta(minutes=STALE_JOB_TIMEOUT_MINUTES)
            
            # Make job.created_at timezone-aware if it's naive
            job_created_at = job.created_at
            if job_created_at.tzinfo is None:
                job_created_at = job_created_at.replace(tzinfo=timezone.utc)
            
            if job_created_at < stale_threshold:
                # Mark stale job as failed
                logger.warning(
                    f"Marking stale assessment job as failed: job_id={job.id}, "
                    f"created_at={job_created_at}, threshold={stale_threshold}"
                )
                await self.update(
                    db, 
                    db_obj=job, 
                    obj_in={
                        "status": "failed", 
                        "error": "Job timed out - assessment generation took too long",
                        "message": "Job timed out"
                    }
                )
                return None
            logger.debug(f"Found active assessment job: {job.id}, status={job.status}")
        
        return job
    
    async def cancel_job(
        self, db: AsyncSession, *, job_id: UUID, user_id: int
    ) -> Optional[AssessmentJob]:
        """Cancel an in-flight job for a user."""
        job = await self.get_by_id_for_user(db, job_id=job_id, user_id=user_id)
        if job and job.status in ["pending", "processing"]:
            return await self.update(
                db, 
                db_obj=job, 
                obj_in={
                    "status": "cancelled", 
                    "error": "Cancelled by user",
                    "message": "Assessment cancelled"
                }
            )
        return job

    async def update_status(
        self,
        db: AsyncSession,
        *,
        db_obj: AssessmentJob,
        status: str,
        progress: Optional[int] = None,
        message: Optional[str] = None
    ) -> AssessmentJob:
        update_data: Dict[str, Any] = {"status": status}
        if progress is not None:
            update_data["progress"] = progress
        if message is not None:
            update_data["message"] = message
        return await self.update(db, db_obj=db_obj, obj_in=update_data)

    async def set_result(
        self,
        db: AsyncSession,
        *,
        db_obj: AssessmentJob,
        result: Dict[str, Any]
    ) -> AssessmentJob:
        return await self.update(
            db, db_obj=db_obj, obj_in={"result": result, "status": "completed", "progress": 100}
        )

    async def set_error(
        self, db: AsyncSession, *, db_obj: AssessmentJob, error: str
    ) -> AssessmentJob:
        return await self.update(
            db, db_obj=db_obj, obj_in={"status": "failed", "error": error, "message": error}
        )


assessment_job_crud = CRUDAssessmentJob(AssessmentJob)



