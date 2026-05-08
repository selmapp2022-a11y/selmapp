from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.content import DifficultyLevel
from app.models.reading import ReadingTextType
from app.services.ai_reading_service import ai_reading_service
from app.crud.reading import reading_text, reading_exercise, vocabulary_highlight
from app.schemas.reading import ReadingTextCreate, ReadingExerciseCreate, VocabularyHighlightCreate

router = APIRouter()

class GenerateReadingTextRequest(BaseModel):
    level: DifficultyLevel = Field(..., description="CEFR level for the text")
    text_type: ReadingTextType = Field(..., description="Type of reading text")
    topic: str = Field(..., description="Topic for the text")
    word_count: int = Field(default=200, ge=100, le=1000, description="Target word count")
    vocabulary_count: int = Field(default=10, ge=5, le=20, description="Number of vocabulary words to include")
    include_questions: bool = Field(default=True, description="Generate comprehension questions")
    save_to_database: bool = Field(default=False, description="Save generated content to database")
    # When supplied, the AI analyses the user's own text (highlighting vocab,
    # generating comprehension questions) instead of inventing a new passage on
    # `topic`. Powers the "Paste any English text" flow on the Reading page.
    original_text: Optional[str] = Field(default=None, description="User-provided text to analyse instead of generating fresh content")

class GenerateReadingTextResponse(BaseModel):
    text_content: str
    vocabulary_used: List[dict]
    level: str
    text_type: str
    topic: str
    word_count: int
    comprehension_questions: Optional[List[dict]] = None
    reading_text_id: Optional[int] = None
    message: str

class BatchGenerateRequest(BaseModel):
    level: DifficultyLevel
    topics: List[str] = Field(..., min_items=1, max_items=5)
    text_types: List[ReadingTextType] = Field(..., min_items=1, max_items=3)
    count_per_combination: int = Field(default=1, ge=1, le=3)
    save_to_database: bool = Field(default=False)

class BatchGenerateResponse(BaseModel):
    total_generated: int
    successful: int
    failed: int
    results: List[GenerateReadingTextResponse]
    errors: List[str]

@router.post("/generate-text", response_model=GenerateReadingTextResponse)
async def generate_reading_text(
    request: GenerateReadingTextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Generate reading text using AI with leveled vocabulary from database.

    If `original_text` is supplied the AI analyses that text (vocab + questions)
    instead of inventing a new passage. This powers Reading → "Paste any
    English text".
    """
    try:
        # Generate the reading text
        result = await ai_reading_service.generate_reading_text_with_vocabulary(
            db=db,
            level=request.level,
            text_type=request.text_type,
            topic=request.topic,
            word_count=request.word_count,
            vocabulary_count=request.vocabulary_count,
            include_comprehension_questions=request.include_questions,
            original_text=request.original_text,
        )
        
        reading_text_id = None
        message = "Reading text generated successfully"
        
        # Save to database if requested
        if request.save_to_database:
            reading_text_id = await _save_generated_content_to_database(
                db, result, current_user.id
            )
            message += f" and saved to database with ID {reading_text_id}"
        
        return GenerateReadingTextResponse(
            text_content=result["text_content"],
            vocabulary_used=result["vocabulary_used"],
            level=result["level"],
            text_type=result["text_type"],
            topic=result["topic"],
            word_count=result["word_count"],
            comprehension_questions=result.get("comprehension_questions"),
            reading_text_id=reading_text_id,
            message=message
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate reading text: {str(e)}"
        )

@router.post("/generate-batch", response_model=BatchGenerateResponse)
async def generate_reading_texts_batch(
    request: BatchGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Generate multiple reading texts in batch"""
    try:
        results = await ai_reading_service.generate_reading_text_batch(
            db=db,
            level=request.level,
            topics=request.topics,
            text_types=request.text_types,
            count_per_combination=request.count_per_combination
        )
        
        successful = 0
        failed = 0
        errors = []
        processed_results = []
        
        for result in results:
            try:
                reading_text_id = None
                if request.save_to_database:
                    reading_text_id = await _save_generated_content_to_database(
                        db, result, current_user.id
                    )
                
                processed_results.append(GenerateReadingTextResponse(
                    text_content=result["text_content"],
                    vocabulary_used=result["vocabulary_used"],
                    level=result["level"],
                    text_type=result["text_type"],
                    topic=result["topic"],
                    word_count=result["word_count"],
                    comprehension_questions=result.get("comprehension_questions"),
                    reading_text_id=reading_text_id,
                    message="Generated successfully"
                ))
                successful += 1
            except Exception as e:
                failed += 1
                errors.append(f"Failed to process result: {str(e)}")
        
        return BatchGenerateResponse(
            total_generated=len(results),
            successful=successful,
            failed=failed,
            results=processed_results,
            errors=errors
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate batch reading texts: {str(e)}"
        )

@router.post("/enhance-text")
async def enhance_existing_text(
    text_content: str = Body(..., description="Existing text content"),
    level: DifficultyLevel = Body(..., description="CEFR level"),
    vocabulary_count: int = Body(default=10, description="Number of vocabulary words to highlight"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Enhance existing text with vocabulary highlights"""
    try:
        result = await ai_reading_service.enhance_existing_text_with_vocabulary(
            db=db,
            text_content=text_content,
            level=level,
            vocabulary_count=vocabulary_count
        )
        
        return {
            "original_text": result["original_text"],
            "vocabulary_highlights": result["vocabulary_highlights"],
            "level": result["level"],
            "vocabulary_count": result["vocabulary_count"],
            "message": "Text enhanced with vocabulary highlights"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enhance text: {str(e)}"
        )

@router.get("/vocabulary-topics")
async def get_vocabulary_topics(
    level: Optional[DifficultyLevel] = Query(None, description="Filter by CEFR level"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get available vocabulary topics for text generation"""
    try:
        # This would need to be implemented based on your vocabulary database structure
        # For now, return common topics
        common_topics = [
            "travel", "business", "daily_life", "family", "food", "health",
            "education", "technology", "environment", "culture", "sports",
            "entertainment", "shopping", "transportation", "work", "hobbies"
        ]
        
        return {
            "topics": common_topics,
            "level": level.value if level else "all",
            "message": f"Available topics for {level.value if level else 'all levels'}"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vocabulary topics: {str(e)}"
        )

@router.get("/generation-stats")
async def get_generation_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get statistics about AI-generated reading texts"""
    try:
        # This would query your database for statistics
        # For now, return mock statistics
        return {
            "total_texts_generated": 0,
            "texts_by_level": {
                "A1": 0, "A2": 0, "B1": 0, "B2": 0, "C1": 0, "C2": 0
            },
            "texts_by_type": {
                "article": 0, "story": 0, "news": 0, "letter": 0,
                "essay": 0, "dialogue": 0, "instruction": 0
            },
            "vocabulary_usage": {
                "total_words_used": 0,
                "unique_words_used": 0,
                "average_words_per_text": 0
            },
            "message": "Generation statistics retrieved"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get generation statistics: {str(e)}"
        )

# Helper function to save generated content to database
async def _save_generated_content_to_database(
    db: AsyncSession, 
    generated_content: dict, 
    user_id: int
) -> int:
    """Save generated reading text and related content to database"""
    try:
        # Create reading text
        reading_text_data = ReadingTextCreate(
            title=f"{generated_content['topic'].title()} - {generated_content['text_type'].title()}",
            content=generated_content["text_content"],
            text_type=ReadingTextType(generated_content["text_type"]),
            difficulty_level=DifficultyLevel(generated_content["level"]),
            word_count=generated_content["word_count"],
            topic=generated_content["topic"],
            keywords=[vocab["word"] for vocab in generated_content["vocabulary_used"]],
            source="AI Generated",
            estimated_reading_time=max(1, generated_content["word_count"] // 200)
        )
        
        saved_text = await reading_text.create(db, obj_in=reading_text_data)
        
        # Create vocabulary highlights
        for i, vocab in enumerate(generated_content["vocabulary_used"]):
            # Find word position in text (simplified)
            text_lower = generated_content["text_content"].lower()
            word_position = text_lower.find(vocab["word"].lower())
            
            if word_position != -1:
                highlight_data = VocabularyHighlightCreate(
                    reading_text_id=saved_text.id,
                    word=vocab["word"],
                    definition=vocab["definition"],
                    part_of_speech=vocab.get("part_of_speech", ""),
                    difficulty_level=DifficultyLevel(generated_content["level"]),
                    start_position=word_position,
                    end_position=word_position + len(vocab["word"]),
                    example_sentence=vocab.get("example", "")
                )
                await vocabulary_highlight.create(db, obj_in=highlight_data)
        
        # Create comprehension questions as reading exercises
        if generated_content.get("comprehension_questions"):
            for i, question in enumerate(generated_content["comprehension_questions"]):
                exercise_data = ReadingExerciseCreate(
                    reading_text_id=saved_text.id,
                    title=f"Question {i+1}",
                    question=question["question"],
                    exercise_type=question.get("type", "multiple_choice"),
                    options=question.get("options", []),
                    correct_answer=question["correct_answer"],
                    explanation=question.get("explanation", ""),
                    points=1,
                    order_index=i
                )
                await reading_exercise.create(db, obj_in=exercise_data)
        
        return saved_text.id
        
    except Exception as e:
        raise Exception(f"Failed to save generated content to database: {str(e)}") 