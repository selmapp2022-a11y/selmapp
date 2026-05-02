from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.content import DifficultyLevel
from app.models.reading import ReadingTextType
from app.crud.reading import (
    reading_text, reading_exercise, reading_attempt, 
    vocabulary_highlight, reading_progress
)
from app.schemas.reading import (
    ReadingTextResponse, ReadingTextWithExercises, ReadingTextCreate, ReadingTextUpdate,
    ReadingExerciseResponse, ReadingExerciseCreate, ReadingExerciseUpdate,
    ReadingAttemptResponse, ReadingAttemptCreate, ReadingAttemptSubmit,
    VocabularyHighlightResponse, VocabularyHighlightCreate, VocabularyHighlightUpdate,
    ReadingProgressResponse, ReadingProgressUpdate,
    ReadingTextPractice, ReadingExercisePractice,
    ReadingSessionStart, ReadingSessionSave, ReadingSessionResponse,
    ReadingStatistics, ReadingAnalytics, ReadingDashboard
)
from app.services.ai_service import AIService
from datetime import datetime, timedelta

router = APIRouter()
ai_service = AIService()

# Reading Text Endpoints
@router.get("/texts/", response_model=List[ReadingTextResponse])
async def get_reading_texts(
    level: Optional[DifficultyLevel] = None,
    text_type: Optional[ReadingTextType] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get reading texts with optional filtering"""
    if level and text_type:
        texts = await reading_text.get_by_level_and_type(
            db, level=level, text_type=text_type, skip=skip, limit=limit
        )
    elif level:
        texts = await reading_text.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    elif text_type:
        texts = await reading_text.get_by_type(
            db, text_type=text_type, skip=skip, limit=limit
        )
    else:
        texts = await reading_text.get_multi(db, skip=skip, limit=limit)
    
    return texts

@router.get("/texts/search", response_model=List[ReadingTextResponse])
async def search_reading_texts(
    query: str = Query(..., min_length=2),
    level: Optional[DifficultyLevel] = None,
    text_type: Optional[ReadingTextType] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Search reading texts by title, content, or keywords"""
    texts = await reading_text.search_texts(
        db, query=query, level=level, text_type=text_type, skip=skip, limit=limit
    )
    return texts

@router.get("/texts/{text_id}", response_model=ReadingTextWithExercises)
async def get_reading_text(
    text_id: int,
    include_exercises: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get specific reading text with optional exercises"""
    if include_exercises:
        text = await reading_text.get_with_exercises(db, id=text_id)
    else:
        text = await reading_text.get(db, id=text_id)
    
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading text not found"
        )
    
    if not text.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading text not available"
        )
    
    return text

@router.get("/texts/{text_id}/vocabulary", response_model=List[VocabularyHighlightResponse])
async def get_text_vocabulary(
    text_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get vocabulary highlights for a reading text"""
    # Verify text exists
    text = await reading_text.get(db, id=text_id)
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading text not found"
        )
    
    vocabulary = await vocabulary_highlight.get_by_text(db, reading_text_id=text_id)
    return vocabulary

@router.post("/texts/{text_id}/start", response_model=ReadingSessionResponse)
async def start_reading_session(
    text_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Start a reading session"""
    text = await reading_text.get_with_exercises(db, id=text_id)
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading text not found"
        )
    
    # Get vocabulary highlights
    vocabulary = await vocabulary_highlight.get_by_text(db, reading_text_id=text_id)
    
    return ReadingSessionResponse(
        reading_text=text,
        vocabulary_highlights=vocabulary,
        session_started_at=datetime.utcnow()
    )

# Reading Exercise Endpoints
@router.get("/exercises/", response_model=List[ReadingExerciseResponse])
async def get_reading_exercises(
    text_id: Optional[int] = None,
    exercise_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get reading exercises with optional filtering"""
    if text_id:
        exercises = await reading_exercise.get_by_text(db, reading_text_id=text_id)
    elif exercise_type:
        exercises = await reading_exercise.get_by_type(db, exercise_type=exercise_type)
    else:
        exercises = await reading_exercise.get_multi(db, skip=skip, limit=limit)
    
    return exercises

@router.get("/exercises/{exercise_id}", response_model=ReadingExercisePractice)
async def get_reading_exercise(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get specific reading exercise for practice"""
    exercise = await reading_exercise.get(db, id=exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading exercise not found"
        )
    
    if not exercise.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading exercise not available"
        )
    
    return exercise

@router.post("/exercises/submit", response_model=ReadingAttemptResponse)
async def submit_reading_exercise(
    submission: ReadingAttemptSubmit,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Submit reading exercise answer and get feedback"""
    # Get the exercise
    exercise = await reading_exercise.get(db, id=submission.reading_exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading exercise not found"
        )
    
    # Check answer correctness
    is_correct = await _check_reading_answer_correctness(exercise, submission.user_answer)
    
    # Calculate comprehension score
    comprehension_score = 100.0 if is_correct else 0.0
    
    # Calculate reading speed if time provided
    words_per_minute = None
    if submission.reading_time_seconds and submission.reading_time_seconds > 0:
        # Get text word count
        text = await reading_text.get(db, id=submission.reading_text_id)
        if text and text.word_count:
            minutes = submission.reading_time_seconds / 60
            words_per_minute = text.word_count / minutes if minutes > 0 else 0
    
    # Create attempt record
    attempt_data = ReadingAttemptCreate(
        user_id=current_user.id,
        reading_text_id=submission.reading_text_id,
        reading_exercise_id=submission.reading_exercise_id,
        reading_time_seconds=submission.reading_time_seconds,
        user_answer=submission.user_answer,
        is_correct=is_correct,
        comprehension_score=comprehension_score,
        words_per_minute=words_per_minute
    )
    
    attempt = await reading_attempt.create(db, obj_in=attempt_data)
    
    # Update reading progress
    await reading_progress.update_reading_stats(
        db, user_id=current_user.id, reading_attempt=attempt
    )
    
    return ReadingAttemptResponse(
        id=attempt.id,
        reading_text_id=attempt.reading_text_id,
        reading_exercise_id=attempt.reading_exercise_id,
        is_correct=is_correct,
        score=comprehension_score,
        correct_answer=exercise.correct_answer,
        explanation=exercise.explanation,
        comprehension_score=comprehension_score,
        words_per_minute=words_per_minute,
        reading_time_seconds=submission.reading_time_seconds,
        created_at=attempt.created_at
    )

# Reading Attempt Endpoints
@router.get("/attempts/", response_model=List[ReadingAttemptResponse])
async def get_reading_attempts(
    text_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's reading attempts"""
    if text_id:
        attempts = await reading_attempt.get_text_attempts(
            db, user_id=current_user.id, reading_text_id=text_id
        )
    else:
        attempts = await reading_attempt.get_user_attempts(
            db, user_id=current_user.id, skip=skip, limit=limit
        )
    return attempts

@router.get("/statistics/", response_model=ReadingStatistics)
async def get_reading_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's reading statistics"""
    stats = await reading_attempt.get_user_stats(db, user_id=current_user.id)
    
    # Get progress data
    progress = await reading_progress.get_by_user(db, user_id=current_user.id)
    
    return ReadingStatistics(
        total_texts_read=progress.total_texts_read if progress else 0,
        total_reading_time_hours=stats['total_reading_time_seconds'] / 3600,
        average_reading_speed_wpm=stats['average_reading_speed_wpm'],
        average_comprehension_score=stats['average_comprehension_score'],
        total_exercises_completed=stats['total_attempts'],
        accuracy_rate=stats['accuracy_rate'],
        vocabulary_learned=progress.total_vocabulary_learned if progress else 0,
        reading_streak=progress.current_reading_streak if progress else 0,
        favorite_text_types=[],  # Could be calculated from attempts
        current_level=progress.current_level if progress else DifficultyLevel.A1
    )

@router.get("/progress/", response_model=ReadingProgressResponse)
async def get_reading_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's reading progress"""
    progress = await reading_progress.get_by_user(db, user_id=current_user.id)
    
    if not progress:
        # Create initial progress if doesn't exist
        progress = await reading_progress.create_or_update(
            db, user_id=current_user.id, progress_data={}
        )
    
    return progress

@router.get("/analytics/", response_model=ReadingAnalytics)
async def get_reading_analytics(
    days: int = Query(default=30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get detailed reading analytics"""
    # Get recent attempts for analytics
    recent_attempts = await reading_attempt.get_user_attempts(
        db, user_id=current_user.id, skip=0, limit=1000
    )
    
    # Filter by date range
    since_date = datetime.utcnow() - timedelta(days=days)
    filtered_attempts = [
        attempt for attempt in recent_attempts 
        if attempt.created_at >= since_date
    ]
    
    # Process analytics data
    daily_activity = _process_daily_reading_activity(filtered_attempts)
    comprehension_trends = _process_comprehension_trends(filtered_attempts)
    speed_trends = _process_speed_trends(filtered_attempts)
    text_type_performance = _process_text_type_performance(filtered_attempts)
    
    return ReadingAnalytics(
        daily_reading_activity=daily_activity,
        comprehension_trends=comprehension_trends,
        reading_speed_trends=speed_trends,
        text_type_performance=text_type_performance,
        vocabulary_growth=[]  # Could be implemented based on vocabulary highlights
    )

@router.get("/dashboard/", response_model=ReadingDashboard)
async def get_reading_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get reading dashboard data"""
    # Get current statistics
    stats = await get_reading_statistics(current_user=current_user, db=db)
    
    # Get recent attempts
    recent_attempts = await reading_attempt.get_user_attempts(
        db, user_id=current_user.id, skip=0, limit=5
    )
    
    # Get recommended texts based on user level and progress
    progress = await reading_progress.get_by_user(db, user_id=current_user.id)
    user_level = progress.current_level if progress else DifficultyLevel.A1
    
    recommended_texts = await reading_text.get_by_level(
        db, level=user_level, skip=0, limit=5
    )
    
    return ReadingDashboard(
        current_stats=stats,
        recent_attempts=recent_attempts,
        recommended_texts=recommended_texts,
        reading_goals=[]  # Could be implemented as a separate feature
    )

# Vocabulary Endpoints
@router.get("/vocabulary/", response_model=List[VocabularyHighlightResponse])
async def get_vocabulary_highlights(
    level: Optional[DifficultyLevel] = None,
    text_id: Optional[int] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get vocabulary highlights with optional filtering"""
    if search:
        vocabulary = await vocabulary_highlight.search_vocabulary(
            db, query=search, reading_text_id=text_id
        )
    elif level and text_id:
        vocabulary = await vocabulary_highlight.get_by_level(
            db, level=level, reading_text_id=text_id
        )
    elif level:
        vocabulary = await vocabulary_highlight.get_by_level(db, level=level)
    elif text_id:
        vocabulary = await vocabulary_highlight.get_by_text(db, reading_text_id=text_id)
    else:
        vocabulary = await vocabulary_highlight.get_multi(db, skip=skip, limit=limit)
    
    return vocabulary

# Admin endpoints (for content management)
@router.post("/texts/", response_model=ReadingTextResponse)
async def create_reading_text(
    text_data: ReadingTextCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new reading text (admin only)"""
    # Note: In a real application, you'd want to check if user is admin
    text = await reading_text.create(db, obj_in=text_data)
    return text

@router.post("/exercises/", response_model=ReadingExerciseResponse)
async def create_reading_exercise(
    exercise_data: ReadingExerciseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new reading exercise (admin only)"""
    # Verify the reading text exists
    text = await reading_text.get(db, id=exercise_data.reading_text_id)
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading text not found"
        )
    
    exercise = await reading_exercise.create(db, obj_in=exercise_data)
    return exercise

@router.post("/vocabulary/", response_model=VocabularyHighlightResponse)
async def create_vocabulary_highlight(
    vocabulary_data: VocabularyHighlightCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new vocabulary highlight (admin only)"""
    # Verify the reading text exists
    text = await reading_text.get(db, id=vocabulary_data.reading_text_id)
    if not text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reading text not found"
        )
    
    vocabulary = await vocabulary_highlight.create(db, obj_in=vocabulary_data)
    return vocabulary

# Helper functions
async def _check_reading_answer_correctness(exercise, user_answer) -> bool:
    """Check if the user's answer is correct"""
    if exercise.exercise_type == "multiple_choice":
        return str(user_answer).strip().lower() == str(exercise.correct_answer).strip().lower()
    elif exercise.exercise_type == "true_false":
        return str(user_answer).strip().lower() == str(exercise.correct_answer).strip().lower()
    elif exercise.exercise_type == "short_answer":
        # Simple string matching - could be enhanced with fuzzy matching
        user_text = str(user_answer).strip().lower()
        correct_text = str(exercise.correct_answer).strip().lower()
        return user_text == correct_text
    elif exercise.exercise_type == "essay":
        # For essay questions, we might want to use AI for evaluation
        # For now, return True and let human evaluation handle it
        return True
    else:
        return False

def _process_daily_reading_activity(attempts):
    """Process daily reading activity data"""
    daily_data = {}
    for attempt in attempts:
        date_key = attempt.created_at.date().isoformat()
        if date_key not in daily_data:
            daily_data[date_key] = {
                "date": date_key,
                "attempts": 0,
                "reading_time": 0,
                "texts_read": set()
            }
        daily_data[date_key]["attempts"] += 1
        if attempt.reading_time_seconds:
            daily_data[date_key]["reading_time"] += attempt.reading_time_seconds
        daily_data[date_key]["texts_read"].add(attempt.reading_text_id)
    
    # Convert sets to counts
    for data in daily_data.values():
        data["texts_read"] = len(data["texts_read"])
    
    return list(daily_data.values())

def _process_comprehension_trends(attempts):
    """Process comprehension score trends"""
    return [
        {
            "date": attempt.created_at.date().isoformat(),
            "score": attempt.comprehension_score or 0
        }
        for attempt in attempts
        if attempt.comprehension_score is not None
    ]

def _process_speed_trends(attempts):
    """Process reading speed trends"""
    return [
        {
            "date": attempt.created_at.date().isoformat(),
            "speed": attempt.words_per_minute or 0
        }
        for attempt in attempts
        if attempt.words_per_minute is not None
    ]

def _process_text_type_performance(attempts):
    """Process performance by text type"""
    # This would require joining with reading_text table
    # For now, return empty dict
    return {} 