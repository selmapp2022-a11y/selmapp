from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.api.deps import get_current_user, get_sync_db
from app.crud.lessons import crud_ai_lesson, crud_lesson_progress
from app.schemas.lessons import (
    AILesson, AILessonCreate, AILessonUpdate,
    LessonProgress, LessonProgressCreate, LessonProgressUpdate,
    GenerateLessonRequest, LessonResponse, CachedLessonResponse
)
from app.schemas.user import User
from app.services.lesson_cache_service import LessonCacheService
from app.services.content_access_service import content_access_service

router = APIRouter()
lesson_cache_service = LessonCacheService()


def _lesson_type_to_module(lesson_type: str) -> str:
    if hasattr(lesson_type, "value"):
        lesson_type = lesson_type.value
    lesson_type = str(lesson_type or "").lower()
    mapping = {
        "vocabulary": "vocabulary",
        "grammar": "grammar",
        "writing": "writing",
        "conversation": "speaking",
        "pronunciation": "speaking",
        "comprehension": "reading",
        "mixed": "reading",
    }
    return mapping.get(lesson_type, lesson_type)


def _enforce_lesson_access(sync_db: Session, current_user: User, *, lesson_type: str, difficulty_level: str) -> None:
    module = _lesson_type_to_module(lesson_type)
    can_access, reason = content_access_service.can_start_new_lesson(
        sync_db,
        current_user,
        module=module,
        cefr_level=difficulty_level,
    )
    if not can_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

# AI-Generated Lesson Caching Endpoints

@router.post("/generate/", response_model=LessonResponse)
async def generate_cached_lesson(
    *,
    sync_db: Session = Depends(get_sync_db),
    request: GenerateLessonRequest,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks
):
    """Generate or retrieve cached AI lesson with smart caching based on user progress"""
    try:
        _enforce_lesson_access(
            sync_db,
            current_user,
            lesson_type=request.lesson_type.value,
            difficulty_level=request.difficulty_level.value,
        )

        # Use smart caching service to get or generate lesson
        result = await lesson_cache_service.get_or_generate_lesson(
            db=sync_db,
            user_id=current_user.id,
            lesson_type=request.lesson_type,
            difficulty_level=request.difficulty_level,
            topic=request.topic,
            user_preferences=request.user_preferences
        )

        if result.get("from_cache"):
            # Return cached lesson with progress data
            cached_lesson = result["lesson"]
            progress = crud_lesson_progress.get_user_lesson_progress(
                sync_db, user_id=current_user.id, lesson_id=cached_lesson.id
            )

            return LessonResponse(
                lesson=cached_lesson,
                progress=progress,
                is_cached=True,
                generated_at=cached_lesson.created_at,
                cache_age_hours=result.get("cache_age_hours", 0)
            )

        else:
            # Create new lesson from generated content
            new_lesson_data = result["lesson_content"]

            # Extract title from generated content or create default
            title = new_lesson_data.get("title", "Generated Lesson")
            description = new_lesson_data.get("description", "AI-generated lesson")

            lesson_in = AILessonCreate(
                user_id=current_user.id,
                lesson_type=request.lesson_type,
                difficulty_level=request.difficulty_level,
                topic=request.topic,
                title=title,
                description=description,
                content=new_lesson_data,
                expires_at=None  # No expiration for now
            )

            lesson = crud_ai_lesson.create_sync(sync_db, obj_in=lesson_in)

            # Queue background analytics update
            background_tasks.add_task(
                lesson_cache_service.update_generation_analytics,
                sync_db, current_user.id, request.lesson_type
            )

            return LessonResponse(
                lesson=lesson,
                progress=None,
                is_cached=False,
                generated_at=lesson.created_at,
                progress_based_adjustments=result.get("adjustments", {})
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate lesson: {str(e)}"
        )

@router.get("/cached/", response_model=List[CachedLessonResponse])
async def get_cached_lessons(
    *,
    sync_db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    lesson_type: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """Get user's cached lessons with optional filtering"""
    try:
        lessons_raw = crud_ai_lesson.get_user_cached_lessons(
            sync_db,
            user_id=current_user.id,
            lesson_type=lesson_type,
            difficulty_level=difficulty_level,
            skip=skip,
            limit=limit
        )

        lessons = []
        for lesson in lessons_raw:
            can_access, _ = content_access_service.can_start_new_lesson(
                sync_db,
                current_user,
                module=_lesson_type_to_module(lesson.lesson_type),
                cefr_level=lesson.difficulty_level,
            )
            if can_access:
                lessons.append(lesson)

        result = []
        for lesson in lessons:
            progress = crud_lesson_progress.get_user_lesson_progress(
                sync_db, user_id=current_user.id, lesson_id=lesson.id
            )

            result.append(CachedLessonResponse(
                lesson=lesson,
                progress=progress,
                is_expired=lesson.is_expired,
                days_until_expiry=lesson.days_until_expiry
            ))

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cached lessons: {str(e)}"
        )

@router.post("/{lesson_id}/start/", response_model=LessonProgress)
async def start_lesson_session(
    *,
    sync_db: Session = Depends(get_sync_db),
    lesson_id: int,
    current_user: User = Depends(get_current_user)
):
    """Start a lesson session and create progress tracking"""
    try:
        # Verify lesson ownership
        lesson = crud_ai_lesson.get_sync(sync_db, id=lesson_id)
        if not lesson or lesson.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found"
            )

        _enforce_lesson_access(
            sync_db,
            current_user,
            lesson_type=lesson.lesson_type,
            difficulty_level=lesson.difficulty_level,
        )

        # Check for existing progress
        existing_progress = crud_lesson_progress.get_user_lesson_progress(
            sync_db, user_id=current_user.id, lesson_id=lesson_id
        )

        if existing_progress:
            # Resume existing session
            return existing_progress

        # Create new progress entry
        progress_in = LessonProgressCreate(
            user_id=current_user.id,
            lesson_id=lesson_id,
            started_at=None,  # Will be set by database
            time_spent_minutes=0
        )

        progress = crud_lesson_progress.create_sync(sync_db, obj_in=progress_in)
        return progress

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start lesson session: {str(e)}"
        )

@router.put("/{lesson_id}/progress/", response_model=LessonProgress)
async def update_lesson_progress(
    *,
    sync_db: Session = Depends(get_sync_db),
    lesson_id: int,
    progress_update: LessonProgressUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update lesson progress"""
    try:
        # Verify lesson ownership
        lesson = crud_ai_lesson.get_sync(sync_db, id=lesson_id)
        if not lesson or lesson.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found"
            )

        _enforce_lesson_access(
            sync_db,
            current_user,
            lesson_type=lesson.lesson_type,
            difficulty_level=lesson.difficulty_level,
        )

        # Get or create progress entry
        progress = crud_lesson_progress.get_user_lesson_progress(
            sync_db, user_id=current_user.id, lesson_id=lesson_id
        )

        if not progress:
            # Create progress entry if it doesn't exist
            progress_in = LessonProgressCreate(
                user_id=current_user.id,
                lesson_id=lesson_id,
                time_spent_minutes=progress_update.time_spent_minutes or 0
            )
            progress = crud_lesson_progress.create_sync(sync_db, obj_in=progress_in)

        # Update progress
        updated_progress = crud_lesson_progress.update_sync(
            sync_db,
            db_obj=progress,
            obj_in=progress_update
        )

        return updated_progress

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update lesson progress: {str(e)}"
        )

@router.delete("/{lesson_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cached_lesson(
    *,
    sync_db: Session = Depends(get_sync_db),
    lesson_id: int,
    current_user: User = Depends(get_current_user)
):
    """Delete a cached lesson"""
    try:
        lesson = crud_ai_lesson.get_sync(sync_db, id=lesson_id)
        if not lesson or lesson.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found"
            )

        crud_ai_lesson.remove_sync(sync_db, id=lesson_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete lesson: {str(e)}"
        )

@router.post("/cleanup/", status_code=status.HTTP_200_OK)
async def cleanup_expired_lessons(
    *,
    sync_db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks
):
    """Clean up expired cached lessons for the current user"""
    try:
        background_tasks.add_task(
            lesson_cache_service.cleanup_expired_lessons,
            sync_db, current_user.id
        )

        return {"message": "Cleanup initiated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate cleanup: {str(e)}"
        )

@router.get("/recommendations/", response_model=List[CachedLessonResponse])
async def get_lesson_recommendations(
    *,
    sync_db: Session = Depends(get_sync_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(5, ge=1, le=20)
):
    """Get personalized lesson recommendations based on user progress"""
    try:
        recommendations_raw = await lesson_cache_service.get_personalized_recommendations(
            sync_db, current_user.id, limit
        )

        recommendations = []
        for lesson in recommendations_raw:
            can_access, _ = content_access_service.can_start_new_lesson(
                sync_db,
                current_user,
                module=_lesson_type_to_module(lesson.lesson_type),
                cefr_level=lesson.difficulty_level,
            )
            if can_access:
                recommendations.append(lesson)

        result = []
        for lesson in recommendations:
            progress = crud_lesson_progress.get_user_lesson_progress(
                sync_db, user_id=current_user.id, lesson_id=lesson.id
            )

            result.append(CachedLessonResponse(
                lesson=lesson,
                progress=progress,
                is_expired=lesson.is_expired,
                days_until_expiry=lesson.days_until_expiry
            ))

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recommendations: {str(e)}"
        )

@router.post("/generate-sequence/", response_model=List[Dict[str, Any]])
async def generate_progress_based_sequence(
    *,
    sync_db: Session = Depends(get_sync_db),
    base_lesson_type: str = Query(..., description="Base lesson type"),
    current_difficulty: str = Query(..., description="Current difficulty level"),
    target_difficulty: Optional[str] = Query(None, description="Target difficulty level"),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks
):
    """Generate a sequence of lessons based on user progress to address skill gaps"""
    try:
        _enforce_lesson_access(
            sync_db,
            current_user,
            lesson_type=base_lesson_type,
            difficulty_level=current_difficulty,
        )

        sequence = await lesson_cache_service.generate_progress_based_sequence(
            db=sync_db,
            user_id=current_user.id,
            base_lesson_type=base_lesson_type,
            current_difficulty=current_difficulty,
            target_difficulty=target_difficulty
        )

        # Queue background task to save sequence to database
        background_tasks.add_task(
            lesson_cache_service.save_lesson_sequence,
            sync_db, current_user.id, sequence, base_lesson_type
        )

        return sequence

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate progress-based sequence: {str(e)}"
        )

@router.get("/progress-analysis/")
async def get_progress_analysis(
    *,
    sync_db: Session = Depends(get_sync_db),
    lesson_type: Optional[str] = Query(None, description="Filter by lesson type"),
    current_user: User = Depends(get_current_user)
):
    """Get detailed progress analysis for the user"""
    try:
        user_level = getattr(getattr(current_user, "current_level", None), "value", None) or "A1"
        if lesson_type:
            _enforce_lesson_access(
                sync_db,
                current_user,
                lesson_type=lesson_type,
                difficulty_level=user_level,
            )
            # Get analysis for specific lesson type
            analysis = await lesson_cache_service._analyze_user_progress(
                sync_db, current_user.id, lesson_type, user_level
            )
        else:
            # Get overall analysis
            progress_stats = crud_lesson_progress.get_user_completion_stats(sync_db, current_user.id)
            analysis = {
                "overall_stats": progress_stats,
                "lesson_count": len(crud_ai_lesson.get_user_cached_lessons(
                    sync_db, user_id=current_user.id, limit=1000
                )),
                "type_breakdown": {}  # Could be implemented later
            }

        return analysis

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get progress analysis: {str(e)}"
        )
