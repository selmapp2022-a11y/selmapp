"""
Content API endpoints for SelmApp
Provides endpoints for accessing CEFR leveled content
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.content_service import ContentService
from app.models.content import ContentType, DifficultyLevel
from app.schemas.content import (
    ContentResponse, 
    VocabularyResponse, 
    GrammarResponse,
    ContentCreate,
    ContentUpdate,
    DailyContentResponse,
    LearningPathResponse
)
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/content", tags=["content"])

@router.get("/levels", response_model=List[str])
async def get_cefr_levels():
    """Get all available CEFR levels."""
    return [level.value for level in DifficultyLevel]

@router.get("/types", response_model=List[str])
async def get_content_types():
    """Get all available content types."""
    return [content_type.value for content_type in ContentType]

@router.get("/by-level/{level}", response_model=List[ContentResponse])
async def get_content_by_level(
    level: DifficultyLevel,
    content_type: Optional[ContentType] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get content filtered by CEFR level and optionally by content type."""
    content_service = ContentService(db)
    content = content_service.get_content_by_level(level, content_type, limit, offset)
    return content

@router.get("/sentences/{level}", response_model=List[ContentResponse])
async def get_sentences_for_level(
    level: DifficultyLevel,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get sentences for a specific CEFR level."""
    content_service = ContentService(db)
    sentences = content_service.get_sentences_for_level(level, limit)
    return sentences

@router.get("/random-sentence/{level}", response_model=ContentResponse)
async def get_random_sentence(
    level: DifficultyLevel,
    db: Session = Depends(get_db)
):
    """Get a random sentence for a specific CEFR level."""
    content_service = ContentService(db)
    sentence = content_service.get_random_sentence(level)
    
    if not sentence:
        raise HTTPException(status_code=404, detail=f"No sentences found for level {level.value}")
    
    return sentence

@router.get("/vocabulary/{level}", response_model=List[VocabularyResponse])
async def get_vocabulary_for_level(
    level: DifficultyLevel,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get vocabulary words for a specific CEFR level."""
    content_service = ContentService(db)
    vocabulary = content_service.get_vocabulary_for_level(level, limit)
    return vocabulary

@router.get("/grammar/{level}", response_model=List[GrammarResponse])
async def get_grammar_for_level(
    level: DifficultyLevel,
    db: Session = Depends(get_db)
):
    """Get grammar rules for a specific CEFR level."""
    content_service = ContentService(db)
    grammar = content_service.get_grammar_for_level(level)
    return grammar

@router.get("/personalized", response_model=List[ContentResponse])
async def get_personalized_content(
    level: DifficultyLevel,
    content_type: Optional[ContentType] = None,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get personalized content based on user's progress and level."""
    content_service = ContentService(db)
    content = content_service.get_personalized_content(
        current_user.id, level, content_type, limit
    )
    return content

@router.get("/daily/{level}", response_model=DailyContentResponse)
async def get_daily_content(
    level: DifficultyLevel,
    db: Session = Depends(get_db)
):
    """Get daily content mix for a user's level."""
    content_service = ContentService(db)
    daily_content = content_service.get_daily_content(level)
    return daily_content

@router.get("/search")
async def search_content(
    q: str = Query(..., min_length=2),
    level: Optional[DifficultyLevel] = None,
    content_type: Optional[ContentType] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search content by text query."""
    content_service = ContentService(db)
    results = content_service.search_content(q, level, content_type, limit)
    return results

@router.get("/statistics")
async def get_content_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get content statistics for admin dashboard."""
    # Only allow admin users to access statistics
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    content_service = ContentService(db)
    stats = content_service.get_content_statistics()
    return stats

@router.get("/by-tags")
async def get_content_by_tags(
    tags: List[str] = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get content filtered by tags."""
    content_service = ContentService(db)
    content = content_service.get_content_by_tags(tags, limit)
    return content

@router.get("/next-level-preview/{current_level}", response_model=List[ContentResponse])
async def get_next_level_preview(
    current_level: DifficultyLevel,
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Get preview content from the next CEFR level."""
    content_service = ContentService(db)
    preview_content = content_service.get_next_level_preview(current_level, limit)
    return preview_content

@router.get("/review", response_model=List[ContentResponse])
async def get_review_content(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get content for review based on user's past performance."""
    content_service = ContentService(db)
    review_content = content_service.get_review_content(current_user.id, limit)
    return review_content

@router.get("/learning-path/{level}", response_model=LearningPathResponse)
async def get_learning_path(
    level: DifficultyLevel,
    db: Session = Depends(get_db)
):
    """Get structured learning path for a user's level."""
    content_service = ContentService(db)
    learning_path = content_service.get_learning_path(level)
    return learning_path

@router.post("/", response_model=ContentResponse)
async def create_content(
    content_data: ContentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new content entry (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    content_service = ContentService(db)
    content = content_service.create_content(content_data.dict())
    return content

@router.put("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: int,
    update_data: ContentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update existing content (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    content_service = ContentService(db)
    content = content_service.update_content(content_id, update_data.dict(exclude_unset=True))
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    return content

@router.delete("/{content_id}")
async def delete_content(
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete content (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    content_service = ContentService(db)
    success = content_service.delete_content(content_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    
    return {"message": "Content deleted successfully"}

@router.get("/{content_id}", response_model=ContentResponse)
async def get_content_by_id(
    content_id: int,
    db: Session = Depends(get_db)
):
    """Get specific content by ID."""
    content = db.query(Content).filter(Content.id == content_id).first()
    
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    return content 