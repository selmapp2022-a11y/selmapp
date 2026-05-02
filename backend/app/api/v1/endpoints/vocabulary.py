from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.crud.content import (
    vocabulary_crud, user_vocabulary_crud, vocabulary_set_crud, vocabulary_exercise_crud
)
from app.models.user import User
from app.models.content import DifficultyLevel, VocabularyStatus
from app.schemas.content import (
    VocabularyResponse, VocabularyCreate, VocabularyUpdate, VocabularyBulkImport, VocabularyImportResult,
    UserVocabularyResponse, UserVocabularyCreate, UserVocabularyUpdate,
    VocabularySetResponse, VocabularySetCreate, VocabularySetUpdate,
    VocabularyExerciseResponse, VocabularyExerciseCreate,
    VocabularySearchRequest, VocabularySearchResponse,
    VocabularyLearningStats, VocabularyReviewSession
)

router = APIRouter()

# Vocabulary Management Endpoints

@router.get("/", response_model=VocabularySearchResponse)
async def search_vocabulary(
    query: Optional[str] = Query(None, description="Search query for word or definition"),
    difficulty_levels: Optional[List[DifficultyLevel]] = Query(None, description="Filter by CEFR levels"),
    topics: Optional[List[str]] = Query(None, description="Filter by topic categories"),
    part_of_speech: Optional[List[str]] = Query(None, description="Filter by part of speech"),
    sort_by: str = Query("word", description="Sort by: word, frequency, difficulty, date_added"),
    sort_order: str = Query("asc", description="Sort order: asc, desc"),
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Search and filter vocabulary with advanced options"""
    search_request = VocabularySearchRequest(
        query=query,
        difficulty_levels=difficulty_levels,
        topics=topics,
        part_of_speech=part_of_speech,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit
    )
    
    try:
        items, total_count = await vocabulary_crud.search_vocabulary(db, search_request=search_request)
    except Exception as _vocab_err:
        raise
    
    return VocabularySearchResponse(
        items=items,
        total_count=total_count,
        has_more=skip + len(items) < total_count
    )

@router.get("/level/{level}", response_model=List[VocabularyResponse])
async def get_vocabulary_by_level(
    level: DifficultyLevel,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    core_only: bool = Query(False, description="Return only core vocabulary"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get vocabulary words by CEFR level"""
    if core_only:
        vocabulary = await vocabulary_crud.get_core_vocabulary_by_level(
            db, level=level, limit=limit
        )
    else:
        vocabulary = await vocabulary_crud.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    return vocabulary

@router.get("/topic/{topic}", response_model=List[VocabularyResponse])
async def get_vocabulary_by_topic(
    topic: str,
    level: Optional[DifficultyLevel] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get vocabulary words by topic category"""
    vocabulary = await vocabulary_crud.get_by_topic(
        db, topic=topic, level=level, skip=skip, limit=limit
    )
    return vocabulary

@router.get("/{vocabulary_id}", response_model=VocabularyResponse)
async def get_vocabulary(
    vocabulary_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get a specific vocabulary word"""
    vocabulary = await vocabulary_crud.get(db, id=vocabulary_id)
    if not vocabulary:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    return vocabulary

@router.post("/", response_model=VocabularyResponse)
async def create_vocabulary(
    *,
    db: AsyncSession = Depends(get_db),
    vocabulary_in: VocabularyCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new vocabulary word"""
    # Check if word already exists
    existing = await vocabulary_crud.get_by_word(db, word=vocabulary_in.word)
    if existing:
        raise HTTPException(status_code=400, detail="Word already exists")
    
    vocabulary = await vocabulary_crud.create(db, obj_in=vocabulary_in)
    return vocabulary

@router.put("/{vocabulary_id}", response_model=VocabularyResponse)
async def update_vocabulary(
    *,
    db: AsyncSession = Depends(get_db),
    vocabulary_id: int,
    vocabulary_in: VocabularyUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update a vocabulary word"""
    vocabulary = await vocabulary_crud.get(db, id=vocabulary_id)
    if not vocabulary:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    
    vocabulary = await vocabulary_crud.update(db, db_obj=vocabulary, obj_in=vocabulary_in)
    return vocabulary

@router.post("/bulk-import", response_model=VocabularyImportResult)
async def bulk_import_vocabulary(
    *,
    db: AsyncSession = Depends(get_db),
    import_data: VocabularyBulkImport,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Bulk import vocabulary words"""
    result = await vocabulary_crud.bulk_create(
        db,
        vocabulary_items=import_data.vocabulary_items,
        overwrite_existing=import_data.overwrite_existing
    )
    return result

# User Vocabulary Learning Endpoints

@router.get("/my/progress", response_model=VocabularyLearningStats)
async def get_my_vocabulary_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get user's vocabulary learning statistics"""
    stats = await user_vocabulary_crud.get_learning_stats(db, user_id=current_user.id)
    return VocabularyLearningStats(**stats)

@router.get("/my/words", response_model=List[UserVocabularyResponse])
async def get_my_vocabulary(
    status: Optional[VocabularyStatus] = Query(None, description="Filter by learning status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get user's vocabulary words with learning progress"""
    user_vocabulary = await user_vocabulary_crud.get_user_vocabulary(
        db, user_id=current_user.id, status=status, skip=skip, limit=limit
    )
    return user_vocabulary

@router.get("/my/review", response_model=VocabularyReviewSession)
async def get_words_for_review(
    limit: int = Query(20, ge=1, le=50, description="Number of words to review"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get words that are due for review"""
    words_to_review = await user_vocabulary_crud.get_words_for_review(
        db, user_id=current_user.id, limit=limit
    )
    
    return VocabularyReviewSession(
        words_to_review=words_to_review,
        session_type="daily_review",
        estimated_duration_minutes=len(words_to_review) * 2  # 2 minutes per word
    )

@router.get("/my/new-words", response_model=List[VocabularyResponse])
async def get_new_words_to_learn(
    limit: int = Query(10, ge=1, le=50, description="Number of new words to learn"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get new words for the user to learn based on their level"""
    new_words = await user_vocabulary_crud.get_new_words_for_learning(
        db, user_id=current_user.id, user_level=current_user.current_level, limit=limit
    )
    return new_words

@router.post("/my/words/{vocabulary_id}/progress")
async def update_word_progress(
    vocabulary_id: int,
    is_correct: bool,
    response_time_seconds: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update learning progress for a vocabulary word"""
    # Verify vocabulary exists
    vocabulary = await vocabulary_crud.get(db, id=vocabulary_id)
    if not vocabulary:
        raise HTTPException(status_code=404, detail="Vocabulary not found")
    
    user_vocab = await user_vocabulary_crud.update_learning_progress(
        db,
        user_id=current_user.id,
        vocabulary_id=vocabulary_id,
        is_correct=is_correct,
        response_time_seconds=response_time_seconds
    )
    
    return {"message": "Progress updated", "new_status": user_vocab.status.value}

@router.post("/my/words/{vocabulary_id}/notes")
async def update_word_notes(
    vocabulary_id: int,
    notes: str,
    personal_examples: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update personal notes for a vocabulary word"""
    # Get or create user vocabulary record
    user_vocab_result = await user_vocabulary_crud.get_user_vocabulary(
        db, user_id=current_user.id, skip=0, limit=1
    )
    
    # Find the specific word or create new record
    user_vocab = None
    for uv in user_vocab_result:
        if uv.vocabulary_id == vocabulary_id:
            user_vocab = uv
            break
    
    if not user_vocab:
        # Create new user vocabulary record
        user_vocab_create = UserVocabularyCreate(
            vocabulary_id=vocabulary_id,
            user_notes=notes,
            personal_examples=personal_examples or []
        )
        user_vocab = await user_vocabulary_crud.create(db, obj_in=user_vocab_create)
    else:
        # Update existing record
        update_data = UserVocabularyUpdate(
            user_notes=notes,
            personal_examples=personal_examples
        )
        user_vocab = await user_vocabulary_crud.update(db, db_obj=user_vocab, obj_in=update_data)
    
    return {"message": "Notes updated successfully"}

# Vocabulary Sets Endpoints

@router.get("/sets/", response_model=List[VocabularySetResponse])
async def get_vocabulary_sets(
    level: Optional[DifficultyLevel] = Query(None),
    topic: Optional[str] = Query(None),
    is_public: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get vocabulary sets with optional filters"""
    vocabulary_sets = await vocabulary_set_crud.get_by_level_and_topic(
        db, level=level, topic=topic, is_public=is_public, skip=skip, limit=limit
    )
    return vocabulary_sets

@router.get("/sets/{set_id}", response_model=VocabularySetResponse)
async def get_vocabulary_set(
    set_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get a specific vocabulary set with all its words"""
    vocabulary_set = await vocabulary_set_crud.get_with_items(db, set_id=set_id)
    if not vocabulary_set:
        raise HTTPException(status_code=404, detail="Vocabulary set not found")
    return vocabulary_set

@router.post("/sets/", response_model=VocabularySetResponse)
async def create_vocabulary_set(
    *,
    db: AsyncSession = Depends(get_db),
    set_in: VocabularySetCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new vocabulary set"""
    vocabulary_set = await vocabulary_set_crud.create_with_vocabulary(
        db, obj_in=set_in, creator_id=current_user.id
    )
    return vocabulary_set

@router.put("/sets/{set_id}", response_model=VocabularySetResponse)
async def update_vocabulary_set(
    *,
    db: AsyncSession = Depends(get_db),
    set_id: int,
    set_in: VocabularySetUpdate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update a vocabulary set"""
    vocabulary_set = await vocabulary_set_crud.get(db, id=set_id)
    if not vocabulary_set:
        raise HTTPException(status_code=404, detail="Vocabulary set not found")
    
    # Check if user owns the set or is admin
    if vocabulary_set.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    vocabulary_set = await vocabulary_set_crud.update(db, db_obj=vocabulary_set, obj_in=set_in)
    return vocabulary_set

# Vocabulary Exercises Endpoints

@router.post("/exercises/", response_model=VocabularyExerciseResponse)
async def create_vocabulary_exercise(
    *,
    db: AsyncSession = Depends(get_db),
    exercise_in: VocabularyExerciseCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Record a vocabulary exercise attempt"""
    # Add user_id to the exercise
    exercise_data = exercise_in.dict()
    exercise_data["user_id"] = current_user.id
    
    # Get vocabulary for difficulty level
    vocabulary = await vocabulary_crud.get(db, id=exercise_in.vocabulary_id)
    if vocabulary:
        exercise_data["difficulty_at_time"] = vocabulary.difficulty_level
    
    exercise = await vocabulary_exercise_crud.create(db, obj_in=exercise_data)
    
    # Update user's learning progress if this is a learning exercise
    if exercise.is_correct is not None:
        await user_vocabulary_crud.update_learning_progress(
            db,
            user_id=current_user.id,
            vocabulary_id=exercise.vocabulary_id,
            is_correct=exercise.is_correct,
            response_time_seconds=exercise.time_taken_seconds
        )
    
    return exercise

@router.get("/exercises/my", response_model=List[VocabularyExerciseResponse])
async def get_my_vocabulary_exercises(
    vocabulary_id: Optional[int] = Query(None),
    exercise_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get user's vocabulary exercise history"""
    exercises = await vocabulary_exercise_crud.get_user_exercises(
        db, 
        user_id=current_user.id,
        vocabulary_id=vocabulary_id,
        exercise_type=exercise_type,
        skip=skip,
        limit=limit
    )
    return exercises

@router.get("/exercises/my/stats")
async def get_my_exercise_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get user's vocabulary exercise statistics"""
    stats = await vocabulary_exercise_crud.get_exercise_stats(
        db, user_id=current_user.id, days=days
    )
    return stats

# Utility Endpoints

@router.get("/topics/", response_model=List[str])
async def get_available_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get list of available topic categories"""
    # This could be enhanced to query the database for actual topics
    # For now, return the predefined topics
    topics = [
        "family", "work", "food", "travel", "health", "home", "shopping", 
        "time", "weather", "colors", "numbers", "emotions", "nature", 
        "technology", "sports", "general"
    ]
    return topics

@router.get("/parts-of-speech/", response_model=List[str])
async def get_parts_of_speech(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get list of available parts of speech"""
    return ["noun", "verb", "adjective", "adverb", "preposition", "conjunction", "interjection"] 