from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
import base64
import logging

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.ai_service import ai_service
from app.services.audio_storage_service import audio_storage_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

class TextToSpeechRequest(BaseModel):
    text: str
    language: str = "en"
    slow: bool = False

class GeminiTTSRequest(BaseModel):
    """Request model for native-audio TTS (dispatched to ElevenLabs or Gemini)."""
    text: str
    voice: Optional[str] = None  # e.g., "Kore", "Sarah", "Charlotte"
    audio_type: str = "general"  # general, assessment, conversation
    accent: Optional[str] = None  # "american" | "british" — overrides default voice

class GrammarCheckRequest(BaseModel):
    text: str

class GrammarAnswerAssessRequest(BaseModel):
    """Request for assessing a grammar practice answer"""
    question: str
    selected_answer: str
    correct_answer: str
    options: list[str]
    grammar_rule: str = ""
    user_level: str = "B1"

class VocabularyRequest(BaseModel):
    word: str
    level: str

class ExerciseGenerationRequest(BaseModel):
    topic: str
    difficulty_level: str
    exercise_type: str
    count: int = 5

class ConversationRequest(BaseModel):
    topic: str
    level: str
    turns: int = 6

@router.post("/text-to-speech")
async def text_to_speech(
    request: TextToSpeechRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Convert text to speech"""
    try:
        audio_data = await ai_service.generate_text_to_speech(
            text=request.text,
            language=request.language,
            slow=request.slow
        )
        
        if not audio_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate audio"
            )
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=speech.mp3"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/audio/{filename}", response_class=Response)
async def get_audio_file(filename: str) -> Response:
    """Serve cached audio bytes stored by the audio storage service as WAV."""
    audio_entry = await audio_storage_service.get_audio(filename)
    if not audio_entry:
        raise HTTPException(status_code=404, detail="Audio not found")
    audio_bytes = base64.b64decode(audio_entry["audio_data"])  # stored as base64 string
    return Response(content=audio_bytes, media_type="audio/wav")


@router.post("/gemini-tts")
async def gemini_text_to_speech(
    request: GeminiTTSRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Generate high-quality TTS audio using Gemini native audio model.
    
    Returns a JSON response with audio_url that can be played directly.
    This is the preferred TTS endpoint for assessment and learning content.
    
    Thread-safe and supports concurrent requests from multiple users.
    """
    try:
        from app.services.gemini_tts_service import get_tts_service
        from app.core.config import settings
        
        # Use singleton TTS service for thread-safe concurrent access
        tts_service = await get_tts_service()
        
        # Use provided voice or default from settings
        voice_name = request.voice or getattr(settings, 'GEMINI_TTS_VOICE', 'Kore')
        accent = (request.accent or "").strip().lower() or None

        logger.info(
            f"Generating TTS for text: {request.text[:50]}... "
            f"(voice={voice_name}, accent={accent or 'default'})"
        )

        speaker = {"name": "Speaker", "voice_name": voice_name}
        if accent:
            speaker["accent"] = accent  # ElevenLabs path uses this to pick Sarah/Charlotte

        result = await tts_service.generate_audio_content(
            text=request.text,
            audio_type=request.audio_type,
            speaker_config=[speaker],
            voice_settings={"accent": accent} if accent else None,
        )
        
        if result.get("success"):
            logger.info(f"Gemini TTS generated successfully: {result.get('audio_url')}")
            return {
                "success": True,
                "audio_url": result["audio_url"],
                "duration_seconds": result.get("duration_seconds", 0),
                "voice": voice_name,
                "model": result.get("tts_model", "gemini-native-audio")
            }
        else:
            error_msg = result.get("error", "Unknown TTS error")
            logger.error(f"Gemini TTS failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"TTS generation failed: {error_msg}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gemini TTS endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"TTS service error: {str(e)}"
        )

@router.post("/grammar-check")
async def grammar_check(
    request: GrammarCheckRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Check grammar and provide corrections"""
    try:
        result = await ai_service.check_grammar(request.text)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to check grammar")
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/assess-grammar-answer")
async def assess_grammar_answer(
    request: GrammarAnswerAssessRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Provide detailed AI feedback for a grammar practice answer"""
    try:
        result = await ai_service.assess_grammar_answer(
            question=request.question,
            selected_answer=request.selected_answer,
            correct_answer=request.correct_answer,
            options=request.options,
            grammar_rule=request.grammar_rule,
            user_level=request.user_level
        )
        return result
    except Exception as e:
        logger.error(f"Error assessing grammar answer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/vocabulary-explanation")
async def vocabulary_explanation(
    request: VocabularyRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get vocabulary explanation with examples"""
    try:
        result = await ai_service.generate_vocabulary_explanation(
            word=request.word,
            level=request.level
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate explanation")
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/generate-exercises")
async def generate_exercises(
    request: ExerciseGenerationRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Generate exercises using AI"""
    try:
        result = await ai_service.generate_exercise_content(
            topic=request.topic,
            difficulty_level=request.difficulty_level,
            exercise_type=request.exercise_type,
            count=request.count
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate exercises")
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/conversation-practice")
async def conversation_practice(
    request: ConversationRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Generate conversation practice scenarios"""
    try:
        result = await ai_service.generate_conversation_practice(
            topic=request.topic,
            level=request.level,
            turns=request.turns
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate conversation")
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/pronunciation-analysis")
async def pronunciation_analysis(
    audio_file: UploadFile = File(...),
    expected_text: str = "",
    current_user: User = Depends(get_current_user)
) -> Any:
    """Analyze pronunciation from audio file"""
    try:
        # Read audio file
        audio_data = await audio_file.read()
        
        # Analyze pronunciation
        result = await ai_service.analyze_pronunciation(
            audio_data=audio_data,
            expected_text=expected_text
        )
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class SpeakingImageRequest(BaseModel):
    """Request model for speaking exercise image generation"""
    prompt: str
    speaking_type: str = "conversation"  # pronunciation, conversation, description, storytelling
    user_level: str = "B1"


@router.post("/generate-speaking-image")
async def generate_speaking_image(
    request: SpeakingImageRequest,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Generate an image for a speaking exercise using Gemini.
    Returns a small image suitable for language learning exercises.
    """
    try:
        from app.services.gemini_image_service import get_image_service
        
        image_service = await get_image_service()
        
        if not image_service.is_available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image generation service is not available"
            )
        
        result = await image_service.generate_speaking_image(
            prompt=request.prompt,
            speaking_type=request.speaking_type,
            user_level=request.user_level,
        )
        
        if result.get("success"):
            return {
                "success": True,
                "image_url": result.get("image_url"),
                "image_data": result.get("image_data"),  # Base64 encoded
                "fallback": result.get("fallback", False),
                "image_description": result.get("image_description"),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate image")
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image generation endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image generation error: {str(e)}"
        ) 