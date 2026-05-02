import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.speaking import (
    speaking_prompt, speaking_attempt, pronunciation_exercise,
    pronunciation_attempt, speaking_progress, speaking_session,
    voice_profile
)
from app.models.speaking import SpeakingExerciseType, PronunciationFocus, DifficultyLevel
from app.schemas.speaking import (
    SpeakingPromptResponse, SpeakingPromptCreate, SpeakingPromptUpdate,
    SpeakingAttemptResponse, SpeakingAttemptCreate, SpeakingAttemptUpdate,
    PronunciationExerciseResponse, PronunciationExerciseCreate, PronunciationExerciseUpdate,
    PronunciationAttemptResponse, PronunciationAttemptCreate, PronunciationAttemptUpdate,
    SpeakingProgressResponse, SpeakingProgressCreate, SpeakingProgressUpdate,
    SpeakingSessionResponse, SpeakingSessionCreate, SpeakingSessionUpdate,
    VoiceProfileResponse, VoiceProfileCreate, VoiceProfileUpdate,
    AudioRecordingStart, AudioRecordingStop, AudioRecordingResponse,
    SpeechAssessmentRequest, SpeechAssessmentResponse,
    SpeakingAnalytics, SpeakingDashboard, SpeakingStatistics,
    RealTimeFeedback, LiveAssessmentUpdate,
    AudioConversationRequest, AudioConversationResponse
)
from app.models.user import User
from app.services.gemini_flash_conversation_service import GeminiFlashConversationService
from app.services.speechace_service import SpeechaceService
from app.services.asr_service import GoogleSTTService
from app.services.speaking_eval_service import SpeakingEvaluationService

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
gemini_conversation_service = GeminiFlashConversationService()

# ==================== SPEAKING PROMPTS ENDPOINTS ====================

@router.get("/prompts/", response_model=List[SpeakingPromptResponse])
async def get_speaking_prompts(
    skip: int = 0,
    limit: int = 100,
    exercise_type: Optional[SpeakingExerciseType] = None,
    difficulty_level: Optional[DifficultyLevel] = None,
    pronunciation_focus: Optional[PronunciationFocus] = None,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get speaking prompts with optional filters"""
    if exercise_type:
        return await speaking_prompt.get_by_exercise_type(
            db, exercise_type=exercise_type, skip=skip, limit=limit
        )
    elif difficulty_level:
        return await speaking_prompt.get_by_difficulty_level(
            db, difficulty_level=difficulty_level, skip=skip, limit=limit
        )
    elif pronunciation_focus:
        return await speaking_prompt.get_by_pronunciation_focus(
            db, pronunciation_focus=pronunciation_focus, skip=skip, limit=limit
        )
    else:
        return await speaking_prompt.get_multi(db, skip=skip, limit=limit)

@router.get("/prompts/search", response_model=List[SpeakingPromptResponse])
async def search_speaking_prompts(
    q: str = Query(..., description="Search query"),
    exercise_type: Optional[SpeakingExerciseType] = None,
    difficulty_level: Optional[DifficultyLevel] = None,
    pronunciation_focus: Optional[PronunciationFocus] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db)
):
    """Search speaking prompts"""
    return await speaking_prompt.search_prompts(
        db, query=q, exercise_type=exercise_type, 
        difficulty_level=difficulty_level, pronunciation_focus=pronunciation_focus,
        skip=skip, limit=limit
    )

@router.get("/prompts/recommended", response_model=List[SpeakingPromptResponse])
async def get_recommended_prompts(
    difficulty_level: Optional[DifficultyLevel] = None,
    pronunciation_focus: Optional[PronunciationFocus] = None,
    limit: int = 5,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get recommended prompts for user"""
    return await speaking_prompt.get_recommended_prompts(
        db, user_id=current_user.id, difficulty_level=difficulty_level,
        pronunciation_focus=pronunciation_focus, limit=limit
    )

@router.get("/prompts/random", response_model=SpeakingPromptResponse)
async def get_random_prompt(
    difficulty_level: Optional[DifficultyLevel] = None,
    exercise_type: Optional[SpeakingExerciseType] = None,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get a random speaking prompt"""
    prompt = await speaking_prompt.get_random_prompt(
        db, difficulty_level=difficulty_level, exercise_type=exercise_type
    )
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prompts found matching criteria"
        )
    return prompt

@router.get("/prompts/{prompt_id}", response_model=SpeakingPromptResponse)
async def get_speaking_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get specific speaking prompt"""
    prompt = await speaking_prompt.get(db, prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    return prompt

@router.post("/prompts/", response_model=SpeakingPromptResponse)
async def create_speaking_prompt(
    prompt_data: SpeakingPromptCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create new speaking prompt (admin only)"""
    return await speaking_prompt.create(db, obj_in=prompt_data)

@router.put("/prompts/{prompt_id}", response_model=SpeakingPromptResponse)
async def update_speaking_prompt(
    prompt_id: int,
    prompt_data: SpeakingPromptUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update speaking prompt (admin only)"""
    prompt = await speaking_prompt.get(db, prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )
    return await speaking_prompt.update(db, db_obj=prompt, obj_in=prompt_data)

# ==================== SPEAKING ATTEMPTS ENDPOINTS ====================

@router.post("/prompts/{prompt_id}/attempt", response_model=SpeakingAttemptResponse)
async def create_speaking_attempt(
    prompt_id: int,
    attempt_data: SpeakingAttemptCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create a new speaking attempt"""
    attempt_data.prompt_id = prompt_id
    attempt = await speaking_attempt.create_with_user(
        db, obj_in=attempt_data, user_id=current_user.id
    )
    
    # Update user progress
    await speaking_progress.update_progress(
        db, user_id=current_user.id, attempt=attempt
    )
    
    return attempt

@router.get("/attempts/", response_model=List[SpeakingAttemptResponse])
async def get_user_speaking_attempts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's speaking attempts"""
    return await speaking_attempt.get_user_attempts(
        db, user_id=current_user.id, skip=skip, limit=limit
    )

@router.get("/attempts/{attempt_id}", response_model=SpeakingAttemptResponse)
async def get_speaking_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get specific speaking attempt"""
    attempt = await speaking_attempt.get(db, attempt_id)
    if not attempt or attempt.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )
    return attempt

@router.get("/prompts/{prompt_id}/attempts", response_model=List[SpeakingAttemptResponse])
async def get_prompt_attempts(
    prompt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get all attempts for a specific prompt by user"""
    return await speaking_attempt.get_prompt_attempts(
        db, user_id=current_user.id, prompt_id=prompt_id
    )

@router.put("/attempts/{attempt_id}/assess", response_model=SpeakingAttemptResponse)
async def assess_speaking_attempt(
    attempt_id: int,
    assessment_data: SpeakingAttemptUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update speaking attempt with assessment results"""
    attempt = await speaking_attempt.get(db, attempt_id)
    if not attempt or attempt.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )
    
    return await speaking_attempt.update(db, db_obj=attempt, obj_in=assessment_data)

# ==================== PRONUNCIATION EXERCISES ENDPOINTS ====================

@router.get("/pronunciation-exercises/", response_model=List[PronunciationExerciseResponse])
async def get_pronunciation_exercises(
    skip: int = 0,
    limit: int = 100,
    pronunciation_focus: Optional[PronunciationFocus] = None,
    difficulty_level: Optional[DifficultyLevel] = None,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get pronunciation exercises"""
    if pronunciation_focus:
        return await pronunciation_exercise.get_by_focus(
            db, pronunciation_focus=pronunciation_focus, 
            difficulty_level=difficulty_level, skip=skip, limit=limit
        )
    return await pronunciation_exercise.get_multi(db, skip=skip, limit=limit)

@router.get("/pronunciation-exercises/phonemes", response_model=List[PronunciationExerciseResponse])
async def get_exercises_by_phonemes(
    phonemes: List[str] = Query(..., description="Target phonemes"),
    difficulty_level: Optional[DifficultyLevel] = None,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get exercises targeting specific phonemes"""
    return await pronunciation_exercise.get_by_phonemes(
        db, target_phonemes=phonemes, difficulty_level=difficulty_level
    )

@router.get("/pronunciation-exercises/{exercise_id}", response_model=PronunciationExerciseResponse)
async def get_pronunciation_exercise(
    exercise_id: int,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get specific pronunciation exercise"""
    exercise = await pronunciation_exercise.get(db, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found"
        )
    return exercise

@router.post("/pronunciation-exercises/", response_model=PronunciationExerciseResponse)
async def create_pronunciation_exercise(
    exercise_data: PronunciationExerciseCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create new pronunciation exercise (admin only)"""
    return await pronunciation_exercise.create(db, obj_in=exercise_data)

@router.post("/pronunciation-exercises/{exercise_id}/attempt", response_model=PronunciationAttemptResponse)
async def create_pronunciation_attempt(
    exercise_id: int,
    attempt_data: PronunciationAttemptCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create a new pronunciation attempt"""
    attempt_data.exercise_id = exercise_id
    return await pronunciation_attempt.create_with_user(
        db, obj_in=attempt_data, user_id=current_user.id
    )

@router.get("/pronunciation-attempts/", response_model=List[PronunciationAttemptResponse])
async def get_pronunciation_attempts(
    skip: int = 0,
    limit: int = 100,
    exercise_id: Optional[int] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's pronunciation attempts"""
    return await pronunciation_attempt.get_user_attempts(
        db, user_id=current_user.id, exercise_id=exercise_id, skip=skip, limit=limit
    )

# ==================== SPEECH ASSESSMENT ENDPOINTS ====================

@router.post("/assess-speech", response_model=SpeechAssessmentResponse)
async def assess_speech(
    assessment_request: SpeechAssessmentRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Assess speech recording using Speechace and STT services"""
    try:
        import aiohttp

        # Download audio from URL
        async with aiohttp.ClientSession() as session:
            async with session.get(assessment_request.audio_url) as response:
                if response.status != 200:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Failed to download audio from URL: {response.status}"
                    )
                audio_bytes = await response.read()

        # Transcribe audio using STT. STT is optional: when it is not
        # available (no Google STT key or 404), we still want SpeechAce to
        # score the audio against the provided reference text. Only error
        # out if STT fails AND the caller did not provide a reference text.
        transcript_text = ""
        words: list = []
        try:
            stt_service = GoogleSTTService()
            stt_result = await stt_service.transcribe(audio_bytes, language_code="en-US")
            if stt_result.get("success"):
                transcript_text = stt_result.get("text", "") or ""
                words = stt_result.get("words", []) or []
            else:
                logger.warning(
                    f"STT unavailable, continuing with reference-only scoring: "
                    f"{stt_result.get('error')}"
                )
                if not (assessment_request.prompt_text or "").strip():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Transcription service unavailable and no reference text provided",
                    )
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning(f"STT call raised, continuing without transcript: {e}")
            if not (assessment_request.prompt_text or "").strip():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Transcription service unavailable and no reference text provided",
                )

        # Estimate duration from words
        duration_ms = 0
        if words:
            starts = [w.get("startMs") for w in words if w.get("startMs") is not None]
            ends = [w.get("endMs") for w in words if w.get("endMs") is not None]
            if starts and ends:
                duration_ms = max(ends) - min(starts)

        # Try SpeechAce directly first when configured — it returns a clean
        # snake_case payload that maps 1:1 to SpeechAssessmentResponse. Fall
        # back to the integrated evaluation service (Gemini path) only if
        # SpeechAce is missing or fails.
        speechace = SpeechaceService()
        result: Dict[str, Any] = {}
        if speechace.api_key:
            sa = await speechace.assess_pronunciation(
                audio_bytes=audio_bytes,
                reference_text=assessment_request.prompt_text or "",
                user_id=str(current_user.id),
            )
            if sa.get("success") and sa.get("assessment"):
                result = sa["assessment"]
                logger.info(
                    f"SpeechAce ok: overall={result.get('overall_score')}"
                    f" pron={result.get('pronunciation_score')}"
                )
            else:
                logger.warning(f"SpeechAce failed: {sa.get('error')}")

        if not result:
            # Last-resort fallback (Gemini path returns camelCase keys)
            evaluator = SpeakingEvaluationService()
            raw = await evaluator.evaluate(
                reference_text=assessment_request.prompt_text or "",
                transcript_text=transcript_text,
                transcript_words=words,
                duration_ms=duration_ms,
                audio_bytes=audio_bytes,
                user_id=str(current_user.id),
            )
            # Normalize camelCase → snake_case so the response is consistent
            result = {
                "overall_score": raw.get("overall_score") or raw.get("overallScore") or 0.0,
                "pronunciation_score": raw.get("pronunciation_score"),
                "fluency_score": raw.get("fluency_score"),
                "accuracy_score": raw.get("accuracy_score"),
                "transcribed_text": (raw.get("transcript") or {}).get("text", transcript_text),
                "feedback": "Evaluated via Gemini fallback",
                "suggestions": raw.get("tips") or [],
                "confidence": 0.0,
            }

        return SpeechAssessmentResponse(
            overall_score=float(result.get("overall_score") or 0.0),
            pronunciation_score=result.get("pronunciation_score"),
            fluency_score=result.get("fluency_score"),
            accuracy_score=result.get("accuracy_score"),
            transcribed_text=result.get("transcribed_text") or transcript_text,
            phoneme_scores=result.get("phoneme_scores") or {},
            word_scores=result.get("word_scores") or {},
            feedback=result.get("feedback") or "Assessment completed",
            suggestions=result.get("suggestions") or [],
            confidence=float(result.get("confidence") or 0.0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech assessment error: {e}")
        # Fallback response
        return SpeechAssessmentResponse(
            overall_score=0.0,
            pronunciation_score=None,
            fluency_score=None,
            accuracy_score=None,
            transcribed_text="Assessment failed",
            phoneme_scores={},
            word_scores={},
            feedback="Assessment failed due to technical error",
            suggestions=["Please try again"],
            confidence=0.0
        )

@router.post("/real-time-assessment", response_model=LiveAssessmentUpdate)
async def real_time_assessment(
    session_id: str,
    audio_data: bytes = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Real-time speech assessment (placeholder for AI integration)"""
    # This would process real-time audio data
    # For now, return a mock response

    return LiveAssessmentUpdate(
        session_id=session_id,
        current_score=75.0,
        real_time_feedback=[
            RealTimeFeedback(
                timestamp=0.0,
                feedback_type="pronunciation",
                message="Good pronunciation of 'th' sound",
                severity="info",
                suggestions=[]
            )
        ],
        transcription_progress="Hello, how are you..."
    )

# ==================== AUDIO CONVERSATION ENDPOINTS (Gemini Flash-Lite) ====================

@router.post("/audio-conversation", response_model=AudioConversationResponse)
async def process_audio_conversation(
    conversation_context: str = Query(..., description="Context for the conversation (e.g., 'daily life', 'business meeting')"),
    audio_file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Process user audio and generate conversational AI response using Gemini Flash-Lite"""

    # Get user level for personalization
    progress = await speaking_progress.get_by_user(db, current_user.id)
    user_level = progress.current_level.value if progress else "B1"

    # Read audio data
    audio_data = await audio_file.read()

    # Process conversation
    result = await gemini_conversation_service.process_audio_conversation(
        audio_data=audio_data,
        conversation_context=conversation_context,
        user_level=user_level,
        user_id=current_user.id
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Audio conversation processing failed")
        )

    return AudioConversationResponse(**result)

@router.post("/exercise/{prompt_id}/audio-response", response_model=AudioConversationResponse)
async def process_exercise_audio_response(
    prompt_id: int,
    audio_file: UploadFile = File(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Process audio response for a specific speaking exercise"""

    # Get the prompt
    prompt = await speaking_prompt.get(db, prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Speaking prompt not found"
        )

    # Get user level
    progress = await speaking_progress.get_by_user(db, current_user.id)
    user_level = progress.current_level.value if progress else "B1"

    # Read audio data
    audio_data = await audio_file.read()

    # Process exercise response
    result = await gemini_conversation_service.generate_speaking_exercise_response(
        audio_data=audio_data,
        exercise_type=prompt.exercise_type.value,
        prompt_text=prompt.prompt_text,
        user_level=user_level,
        user_id=current_user.id
    )

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Exercise audio processing failed")
        )

    # Create attempt record
    attempt_data = SpeakingAttemptCreate(
        prompt_id=prompt_id,
        audio_url="",  # Will be set after upload
        duration_seconds=result["pronunciation_analysis"]["word_count"] * 0.5,  # Rough estimate
        transcribed_text=result["transcription"],
        recognition_confidence=result["confidence"],
        pronunciation_score=result["pronunciation_analysis"]["overall_score"],
        fluency_score=result["pronunciation_analysis"]["fluency_score"],
        ai_overall_score=result["pronunciation_analysis"]["overall_score"],
        ai_feedback=result["pronunciation_analysis"]["feedback"],
        ai_suggestions=result["exercise_analysis"]["improvement_suggestions"] if result.get("exercise_analysis") else []
    )

    # Save attempt
    attempt = await speaking_attempt.create_with_user(
        db, obj_in=attempt_data, user_id=current_user.id
    )

    # Update progress
    await speaking_progress.update_progress(db, user_id=current_user.id, attempt=attempt)

    return AudioConversationResponse(**result)

@router.get("/conversation-context", response_model=List[Dict[str, Any]])
async def get_conversation_context(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get cached conversation context for continuity"""
    context = await gemini_conversation_service.get_conversation_context(current_user.id)
    return context

@router.delete("/conversation-context")
async def clear_conversation_context(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Clear cached conversation context"""
    cleared = await gemini_conversation_service.clear_conversation_context(current_user.id)
    return {"success": cleared, "message": "Conversation context cleared"}

@router.post("/conversation/start-session", response_model=SpeakingSessionResponse)
async def start_conversation_session(
    conversation_context: str = Query(..., description="Context for the conversation session"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Start a new conversation session with context"""

    session_data = SpeakingSessionCreate(
        session_type="conversation",
        session_goals=[f"Practice {conversation_context} conversations"],
        goals_achieved=[]
    )

    session = await speaking_session.create_with_user(
        db, obj_in=session_data, user_id=current_user.id
    )

    # Cache conversation context
    await gemini_conversation_service._cache_conversation_context(
        user_id=current_user.id,
        conversation_data={
            "session_id": session.id,
            "context": conversation_context,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "type": "session_start"
        }
    )

    return session

# ==================== AUDIO RECORDING ENDPOINTS ====================

@router.post("/recording/start", response_model=AudioRecordingResponse)
async def start_recording(
    recording_data: AudioRecordingStart,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Start audio recording session"""
    # Generate recording ID
    import uuid
    recording_id = str(uuid.uuid4())
    
    return AudioRecordingResponse(
        recording_id=recording_id,
        status="started",
        message="Recording session started"
    )

@router.post("/recording/stop", response_model=AudioRecordingResponse)
async def stop_recording(
    recording_data: AudioRecordingStop,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Stop audio recording session"""
    return AudioRecordingResponse(
        recording_id=recording_data.recording_id,
        status="completed",
        message="Recording completed successfully",
        audio_url=recording_data.audio_url
    )

# ==================== PROGRESS ENDPOINTS ====================

@router.get("/progress/", response_model=SpeakingProgressResponse)
async def get_speaking_progress(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's speaking progress"""
    progress = await speaking_progress.get_by_user(db, current_user.id)
    if not progress:
        # Create initial progress
        progress_data = SpeakingProgressCreate(current_level=DifficultyLevel.A1)
        progress = await speaking_progress.create_with_user(
            db, obj_in=progress_data, user_id=current_user.id
        )
    return progress

@router.put("/progress/", response_model=SpeakingProgressResponse)
async def update_speaking_progress(
    progress_data: SpeakingProgressUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update user's speaking progress settings"""
    progress = await speaking_progress.get_by_user(db, current_user.id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress not found"
        )
    return await speaking_progress.update(db, db_obj=progress, obj_in=progress_data)

@router.post("/progress/streak", response_model=SpeakingProgressResponse)
async def update_speaking_streak(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update user's speaking streak"""
    progress = await speaking_progress.update_streak(db, current_user.id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress not found"
        )
    return progress

@router.get("/progress/phonemes", response_model=Dict[str, float])
async def get_phoneme_progress(
    days: int = 30,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's phoneme pronunciation progress"""
    return await pronunciation_attempt.get_phoneme_progress(
        db, user_id=current_user.id, days=days
    )

# ==================== SESSIONS ENDPOINTS ====================

@router.post("/sessions/start", response_model=SpeakingSessionResponse)
async def start_speaking_session(
    session_data: SpeakingSessionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Start a new speaking session"""
    return await speaking_session.create_with_user(
        db, obj_in=session_data, user_id=current_user.id
    )

@router.get("/sessions/active", response_model=Optional[SpeakingSessionResponse])
async def get_active_speaking_session(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get active speaking session"""
    return await speaking_session.get_active_session(db, current_user.id)

@router.post("/sessions/{session_id}/end", response_model=SpeakingSessionResponse)
async def end_speaking_session(
    session_id: int,
    session_update: SpeakingSessionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """End a speaking session"""
    session = await speaking_session.get(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Update session with final data
    session = await speaking_session.update(db, db_obj=session, obj_in=session_update)
    
    # End the session
    return await speaking_session.end_session(db, session_id)

@router.get("/sessions/", response_model=List[SpeakingSessionResponse])
async def get_speaking_sessions(
    days: int = 30,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's speaking sessions"""
    return await speaking_session.get_user_sessions(
        db, user_id=current_user.id, days=days, skip=skip, limit=limit
    )

# ==================== VOICE PROFILE ENDPOINTS ====================

@router.get("/voice-profile/", response_model=VoiceProfileResponse)
async def get_voice_profile(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's voice profile"""
    profile = await voice_profile.get_by_user(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice profile not found"
        )
    return profile

@router.post("/voice-profile/", response_model=VoiceProfileResponse)
async def create_or_update_voice_profile(
    profile_data: VoiceProfileCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create or update voice profile"""
    return await voice_profile.create_or_update(
        db, user_id=current_user.id, profile_data=profile_data
    )

@router.post("/voice-profile/calibrate", response_model=VoiceProfileResponse)
async def complete_voice_calibration(
    calibration_data: Dict[str, Any],
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Complete voice calibration"""
    profile = await voice_profile.complete_calibration(
        db, user_id=current_user.id, calibration_data=calibration_data
    )
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice profile not found"
        )
    return profile

# ==================== STATISTICS AND ANALYTICS ENDPOINTS ====================

@router.get("/statistics/", response_model=SpeakingStatistics)
async def get_speaking_statistics(
    days: int = 30,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's speaking statistics"""
    stats = await speaking_attempt.get_user_statistics(
        db, user_id=current_user.id, days=days
    )
    
    progress = await speaking_progress.get_by_user(db, current_user.id)
    phoneme_progress = await pronunciation_attempt.get_phoneme_progress(
        db, user_id=current_user.id, days=days
    )
    
    return SpeakingStatistics(
        user_id=current_user.id,
        total_time_minutes=int(stats["total_speaking_time_minutes"]),
        prompts_completed=stats["total_attempts"],
        average_pronunciation_score=stats["average_pronunciation_score"],
        average_fluency_score=stats["average_fluency_score"],
        best_pronunciation_score=stats["best_pronunciation_score"],
        current_streak=progress.current_streak_days if progress else 0,
        level_distribution={},  # Could implement this
        exercise_type_performance={},  # Could implement this
        monthly_progress={},  # Could implement this
        phoneme_strengths=[],  # Could derive from phoneme_progress
        phoneme_weaknesses=[]  # Could derive from phoneme_progress
    )

@router.get("/analytics/", response_model=SpeakingAnalytics)
async def get_speaking_analytics(
    days: int = 30,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get speaking analytics"""
    stats = await speaking_attempt.get_user_statistics(
        db, user_id=current_user.id, days=days
    )
    
    progress = await speaking_progress.get_by_user(db, current_user.id)
    phoneme_progress = await pronunciation_attempt.get_phoneme_progress(
        db, user_id=current_user.id, days=days
    )
    
    return SpeakingAnalytics(
        total_speaking_time=int(stats["total_speaking_time_minutes"]),
        prompts_completed=stats["total_attempts"],
        average_pronunciation_score=stats["average_pronunciation_score"],
        average_fluency_score=stats["average_fluency_score"],
        improvement_rate=0.0,  # Could calculate this
        streak_days=progress.current_streak_days if progress else 0,
        favorite_exercise_types=[],  # Could implement this
        performance_by_level={},  # Could implement this
        phoneme_accuracy=phoneme_progress,
        recent_activity=[]  # Could implement this
    )

@router.get("/dashboard/", response_model=SpeakingDashboard)
async def get_speaking_dashboard(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get speaking dashboard data"""
    # Get user progress
    progress = await speaking_progress.get_by_user(db, current_user.id)
    if not progress:
        progress_data = SpeakingProgressCreate(current_level=DifficultyLevel.A1)
        progress = await speaking_progress.create_with_user(
            db, obj_in=progress_data, user_id=current_user.id
        )
    
    # Get recent attempts
    recent_attempts = await speaking_attempt.get_user_attempts(
        db, user_id=current_user.id, skip=0, limit=5
    )
    
    # Get recommended prompts
    recommended_prompts = await speaking_prompt.get_recommended_prompts(
        db, user_id=current_user.id, difficulty_level=progress.current_level, limit=5
    )
    
    # Get voice profile
    user_voice_profile = await voice_profile.get_by_user(db, current_user.id)
    
    # Get analytics
    analytics = await get_speaking_analytics(db=db, current_user=current_user)
    
    return SpeakingDashboard(
        user_progress=progress,
        recent_attempts=recent_attempts,
        recommended_prompts=recommended_prompts,
        analytics=analytics,
        daily_goal_progress={
            "minutes_completed": 0,  # Could implement this
            "goal_minutes": progress.daily_goal_minutes,
            "percentage": 0.0
        },
        voice_profile=user_voice_profile,
        achievements=[]  # Could implement this
    ) 