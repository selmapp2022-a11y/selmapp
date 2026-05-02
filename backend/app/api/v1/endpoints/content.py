from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_premium_user, get_sync_db
from app.models.user import User
from app.models.content import DifficultyLevel, ContentType
from app.crud.content import content_crud, vocabulary_crud, grammar_crud
from app.services.content_access_service import content_access_service
from app.schemas.content import (
    ContentResponse, ContentCreate, ContentUpdate,
    VocabularyResponse, VocabularyCreate, VocabularyUpdate,
    GrammarResponse, GrammarCreate, GrammarUpdate
)

router = APIRouter()


def _raise_if_no_lesson_access(
    sync_db: Session,
    current_user: User,
    *,
    module: Optional[str] = None,
    cefr_level: Optional[str] = None,
) -> None:
    can_access, reason = content_access_service.can_start_new_lesson(
        sync_db,
        current_user,
        module=module,
        cefr_level=cefr_level,
    )
    if not can_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


def _filter_module_items_by_access(
    sync_db: Session,
    current_user: User,
    *,
    module: str,
    items: List[Any],
) -> List[Any]:
    filtered: List[Any] = []
    for item in items:
        level = getattr(item, "difficulty_level", None)
        can_access, _ = content_access_service.can_start_new_lesson(
            sync_db,
            current_user,
            module=module,
            cefr_level=level,
        )
        if can_access:
            filtered.append(item)
    return filtered

# Content Endpoints
@router.get("/", response_model=List[ContentResponse])
async def get_content(
    level: Optional[DifficultyLevel] = None,
    content_type: Optional[ContentType] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Get content with optional filtering by level and type"""
    _raise_if_no_lesson_access(
        sync_db,
        current_user,
        module=content_type.value if content_type else None,
        cefr_level=level.value if level else None,
    )

    if level and content_type:
        content = await content_crud.get_by_level_and_type(
            db, level=level, content_type=content_type, skip=skip, limit=limit
        )
    elif level:
        content = await content_crud.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    else:
        content = await content_crud.get_multi(db, skip=skip, limit=limit)

    return [
        item for item in content
        if content_access_service.can_access_content(sync_db, current_user, item)[0]
    ]

@router.get("/{content_id}", response_model=ContentResponse)
async def get_content_by_id(
    content_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Get specific content by ID"""
    content = await content_crud.get(db, id=content_id)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
    
    can_access, reason = content_access_service.can_access_content(sync_db, current_user, content)
    if not can_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)
    
    return content

@router.get("/search/", response_model=List[ContentResponse])
async def search_content(
    q: str = Query(..., min_length=2, description="Search query"),
    level: Optional[DifficultyLevel] = None,
    content_type: Optional[ContentType] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Search content by title or description"""
    content = await content_crud.search_content(
        db, query=q, level=level, content_type=content_type, skip=skip, limit=limit
    )
    return [
        item for item in content
        if content_access_service.can_access_content(sync_db, current_user, item)[0]
    ]

# Vocabulary Endpoints
@router.get("/vocabulary/", response_model=List[VocabularyResponse])
async def get_vocabulary(
    level: Optional[DifficultyLevel] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Get vocabulary by difficulty level"""
    _raise_if_no_lesson_access(
        sync_db,
        current_user,
        module=ContentType.VOCABULARY.value,
        cefr_level=level.value if level else None,
    )
    if level:
        vocabulary = await vocabulary_crud.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    else:
        vocabulary = await vocabulary_crud.get_multi(db, skip=skip, limit=limit)
    
    return _filter_module_items_by_access(
        sync_db,
        current_user,
        module=ContentType.VOCABULARY.value,
        items=vocabulary,
    )

@router.get("/vocabulary/{word}", response_model=VocabularyResponse)
async def get_vocabulary_by_word(
    word: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Get vocabulary by word"""
    vocabulary = await vocabulary_crud.get_by_word(db, word=word)
    if not vocabulary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vocabulary not found"
        )

    level = getattr(vocabulary, "difficulty_level", None)
    _raise_if_no_lesson_access(
        sync_db,
        current_user,
        module=ContentType.VOCABULARY.value,
        cefr_level=level.value if hasattr(level, "value") else level,
    )
    return vocabulary

@router.get("/vocabulary/search/", response_model=List[VocabularyResponse])
async def search_vocabulary(
    q: str = Query(..., min_length=2, description="Search query"),
    level: Optional[DifficultyLevel] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Search vocabulary by word or definition"""
    _raise_if_no_lesson_access(
        sync_db,
        current_user,
        module=ContentType.VOCABULARY.value,
        cefr_level=level.value if level else None,
    )
    vocabulary = await vocabulary_crud.search_vocabulary(
        db, query=q, level=level, skip=skip, limit=limit
    )
    return _filter_module_items_by_access(
        sync_db,
        current_user,
        module=ContentType.VOCABULARY.value,
        items=vocabulary,
    )

@router.post("/vocabulary/", response_model=VocabularyResponse)
async def create_vocabulary(
    vocabulary_in: VocabularyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_premium_user)  # Only premium users can create content
) -> Any:
    """Create new vocabulary entry"""
    vocabulary = await vocabulary_crud.create(db, obj_in=vocabulary_in)
    return vocabulary

# Grammar Endpoints
@router.get("/grammar/", response_model=List[GrammarResponse])
async def get_grammar(
    level: Optional[DifficultyLevel] = None,
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Get grammar content by level and/or category"""
    _raise_if_no_lesson_access(
        sync_db,
        current_user,
        module=ContentType.GRAMMAR.value,
        cefr_level=level.value if level else None,
    )
    if category:
        grammar = await grammar_crud.get_by_category(
            db, category=category, level=level, skip=skip, limit=limit
        )
    elif level:
        grammar = await grammar_crud.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    else:
        grammar = await grammar_crud.get_multi(db, skip=skip, limit=limit)
    
    return _filter_module_items_by_access(
        sync_db,
        current_user,
        module=ContentType.GRAMMAR.value,
        items=grammar,
    )

@router.get("/grammar/{grammar_id}", response_model=GrammarResponse)
async def get_grammar_by_id(
    grammar_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Get specific grammar content by ID"""
    grammar = await grammar_crud.get(db, id=grammar_id)
    if not grammar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Grammar content not found"
        )

    level = getattr(grammar, "difficulty_level", None)
    _raise_if_no_lesson_access(
        sync_db,
        current_user,
        module=ContentType.GRAMMAR.value,
        cefr_level=level.value if hasattr(level, "value") else level,
    )
    return grammar

@router.post("/grammar/", response_model=GrammarResponse)
async def create_grammar(
    grammar_in: GrammarCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_premium_user)  # Only premium users can create content
) -> Any:
    """Create new grammar content"""
    grammar = await grammar_crud.create(db, obj_in=grammar_in)
    return grammar

# Learning Path Endpoints
@router.get("/learning-path/{level}", response_model=dict)
async def get_learning_path(
    level: DifficultyLevel,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """Get structured learning path for a specific level"""
    _raise_if_no_lesson_access(sync_db, current_user, cefr_level=level.value)
    
    # Get vocabulary for the level
    _raise_if_no_lesson_access(sync_db, current_user, module=ContentType.VOCABULARY.value, cefr_level=level.value)
    vocabulary = await vocabulary_crud.get_by_level(db, level=level, limit=20)
    
    # Get grammar for the level
    _raise_if_no_lesson_access(sync_db, current_user, module=ContentType.GRAMMAR.value, cefr_level=level.value)
    grammar = await grammar_crud.get_by_level(db, level=level, limit=10)
    
    # Get different types of content
    _raise_if_no_lesson_access(sync_db, current_user, module=ContentType.READING.value, cefr_level=level.value)
    reading_content = await content_crud.get_by_level_and_type(
        db, level=level, content_type=ContentType.READING, limit=10
    )
    
    _raise_if_no_lesson_access(sync_db, current_user, module=ContentType.LISTENING.value, cefr_level=level.value)
    listening_content = await content_crud.get_by_level_and_type(
        db, level=level, content_type=ContentType.LISTENING, limit=10
    )
    
    _raise_if_no_lesson_access(sync_db, current_user, module=ContentType.SPEAKING.value, cefr_level=level.value)
    speaking_content = await content_crud.get_by_level_and_type(
        db, level=level, content_type=ContentType.SPEAKING, limit=5
    )
    
    _raise_if_no_lesson_access(sync_db, current_user, module=ContentType.WRITING.value, cefr_level=level.value)
    writing_content = await content_crud.get_by_level_and_type(
        db, level=level, content_type=ContentType.WRITING, limit=5
    )
    
    return {
        "level": level,
        "vocabulary": vocabulary,
        "grammar": grammar,
        "reading": reading_content,
        "listening": listening_content,
        "speaking": speaking_content,
        "writing": writing_content,
        "total_items": len(vocabulary) + len(grammar) + len(reading_content) + 
                      len(listening_content) + len(speaking_content) + len(writing_content)
    }

# Content Statistics
@router.get("/statistics/", response_model=dict)
async def get_content_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get content statistics"""
    from sqlalchemy import select, func
    from app.models.content import Content, Vocabulary, Grammar
    
    # Count content by level
    content_by_level = {}
    for level in DifficultyLevel:
        count = await db.execute(
            select(func.count(Content.id)).where(Content.difficulty_level == level)
        )
        content_by_level[level.value] = count.scalar()
    
    # Count content by type
    content_by_type = {}
    for content_type in ContentType:
        count = await db.execute(
            select(func.count(Content.id)).where(Content.content_type == content_type)
        )
        content_by_type[content_type.value] = count.scalar()
    
    # Count vocabulary and grammar
    vocab_count = await db.execute(select(func.count(Vocabulary.id)))
    grammar_count = await db.execute(select(func.count(Grammar.id)))
    total_content = await db.execute(select(func.count(Content.id)))
    
    return {
        "content_by_level": content_by_level,
        "content_by_type": content_by_type,
        "total_vocabulary": vocab_count.scalar(),
        "total_grammar": grammar_count.scalar(),
        "total_content": total_content.scalar()
    } 