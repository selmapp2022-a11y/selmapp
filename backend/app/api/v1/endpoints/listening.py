from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.api import deps
from app.crud.listening import (
    crud_audio_content, crud_listening_exercise,
    crud_listening_attempt, crud_listening_exercise_attempt, crud_listening_progress
)
from app.models.listening import AudioType, DifficultyLevel, ExerciseType
from app.schemas.listening import (
    # Audio Content
    AudioContentResponse, AudioContentCreate, AudioContentUpdate,
    # Exercises
    ListeningExerciseResponse, ListeningExerciseCreate, ListeningExerciseUpdate,
    QuestionResponse, QuestionCreate, QuestionUpdate,
    # Attempts and Answers
    ListeningAttemptResponse, ListeningAttemptCreate, ListeningAttemptUpdate,
    AnswerResponse, AnswerCreate,
    # Progress and Sessions
    ListeningProgressResponse, ListeningProgressCreate, ListeningProgressUpdate,
    ListeningSessionResponse, ListeningSessionCreate, ListeningSessionUpdate,
    # Specialized responses
    ExerciseSubmission, ExerciseSubmissionResponse,
    ListeningAnalytics, ListeningDashboard, ListeningStatistics,
    AudioPlaybackEvent, AudioPlaybackResponse
)
from app.models.user import User
from app.services.gemini_tts_service import get_tts_service
from app.services.audio_healing_service import audio_healing_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_audio_url_valid(audio_url: Optional[str]) -> bool:
    """Check if audio URL is valid (not a local file path)"""
    return audio_healing_service.is_audio_url_valid(audio_url)


# ==================== AI-GENERATED LISTENING CONTENT ====================

@router.post("/generate")
async def generate_listening_exercise(
    topic: str = Body(..., min_length=2),
    difficulty_level: str = Body(default=None),
    content_type: str = Body(default="conversation"),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Dict[str, Any]:
    """
    Generate a listening exercise with AI-generated audio and comprehension questions.
    
    This endpoint creates a complete listening exercise including:
    - AI-generated script/conversation appropriate for the user's level
    - Text-to-speech audio using Gemini native audio
    - Comprehension questions with answers
    - Vocabulary highlights
    
    SELF-HEALING: Before returning cached content, validates the audio URL.
    If it points to a local file (deleted after deployment), regenerates fresh audio.
    """
    try:
        # Use user's level if not provided
        level = difficulty_level or (current_user.current_level.value if current_user.current_level else "B1")
        
        # --- CHECK CACHE WITH SELF-HEALING ---
        from app.models.cache import GeneratedContentCache
        from sqlalchemy import select, and_, or_
        from datetime import datetime
        
        # Cache key carries a generation version. Bump when the audio
        # generation strategy changes so old single-voice clips don't
        # serve forever. v2 = ElevenLabs v3 multi-speaker dialogue.
        cache_key = f"listening:v2:{current_user.id}:{topic.lower().replace(' ', '_')}:{level}"
        
        result_query = await db.execute(
            select(GeneratedContentCache).where(
                and_(
                    GeneratedContentCache.user_id == current_user.id,
                    GeneratedContentCache.cache_key == cache_key,
                    GeneratedContentCache.status == "ready",
                    or_(
                        GeneratedContentCache.expires_at.is_(None),
                        GeneratedContentCache.expires_at > datetime.utcnow()
                    )
                )
            )
        )
        cached = result_query.scalars().first()
        
        if cached and cached.content:
            cached_audio_url = cached.content.get("audio_url") or cached.content.get("exercise", {}).get("audio_url")
            
            # --- SELF-HEALING CHECK ---
            if cached_audio_url and not _is_audio_url_valid(cached_audio_url):
                logger.warning(
                    f"⚠️ Found broken audio URL in cache: {cached_audio_url}. "
                    f"Invalidating and regenerating..."
                )
                # Delete the broken cache
                await db.delete(cached)
                await db.commit()
                cached = None  # Force regeneration below
            elif cached_audio_url:
                # Valid cache - return it
                logger.info(f"Returning cached listening content for {topic}/{level}")
                return cached.content
        # --- END CACHE CHECK ---
        
        # Get TTS service
        tts_service = await get_tts_service()
        
        # Generate listening content with audio
        result = await tts_service.generate_listening_content(
            topic=topic,
            difficulty_level=level,
            content_type=content_type,
            speaker_names=["Dr. Anya", "Liam"] if content_type == "conversation" else ["Narrator"]
        )
        
        if result.get("success"):
            audio_url = result.get("audio_url")
            
            # Verify the generated audio URL is valid (cloud storage)
            if audio_url and not _is_audio_url_valid(audio_url):
                logger.warning(f"Generated audio URL is local file: {audio_url}. This may not persist.")
            
            response_data = {
                "success": True,
                "exercise": {
                    "id": f"listening_{topic.replace(' ', '_').lower()}_{level}",
                    "title": f"{topic} - Listening Practice",
                    "description": f"Listen to the {content_type} about {topic} and answer the questions.",
                    "level": level,
                    "audio_url": audio_url,
                    "transcript": result.get("script", ""),
                    "duration_seconds": result.get("duration_seconds", 60),
                    "questions": [
                        {
                            "id": f"q_{i}",
                            "question": q.get("question", ""),
                            "options": q.get("options", []),
                            "correct_answer": q.get("correct_answer", ""),
                            "explanation": q.get("explanation", "")
                        }
                        for i, q in enumerate(result.get("comprehension_questions", []))
                    ],
                    "vocabulary": result.get("vocabulary_focus", []),
                    "speakers": result.get("speakers", []),
                    "content_type": content_type,
                    "points": 30
                },
                "metadata": {
                    "topic": topic,
                    "level": level,
                    "content_type": content_type,
                    "tts_model": result.get("metadata", {}).get("tts_model", "gemini-native-audio")
                }
            }
            
            # Cache the new content (only if audio URL is valid cloud URL)
            if audio_url and _is_audio_url_valid(audio_url):
                try:
                    from datetime import timedelta
                    cache_entry = GeneratedContentCache(
                        user_id=current_user.id,
                        cache_key=cache_key,
                        content_type="listening",
                        topic=topic,
                        level=level,
                        content=response_data,
                        status="ready",
                        expires_at=datetime.utcnow() + timedelta(days=7)
                    )
                    db.add(cache_entry)
                    await db.commit()
                    logger.info(f"Cached listening content with cloud audio URL")
                except Exception as cache_err:
                    logger.warning(f"Failed to cache listening content: {cache_err}")
            
            return response_data
        else:
            # Fallback response — call Gemini for a real transcript
            # instead of returning the hardcoded "Hello today we talk
            # about ..." template that every user used to see when the
            # multi-voice path failed. (2026-05-13 minimal fix.)
            return await _generate_fallback_listening(topic, level, content_type)

    except Exception as e:
        logger.error(f"Failed to generate listening exercise: {e}")
        return await _generate_fallback_listening(topic, difficulty_level or "B1", content_type)


@router.get("/audio-status/{exercise_id}")
async def check_audio_status(
    exercise_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Dict[str, Any]:
    """
    Check if audio is available for a listening exercise.
    
    This endpoint allows the frontend to poll for audio availability
    when audio generation takes longer than expected.
    
    SELF-HEALING: If a cached audio URL points to a local file (which may be
    deleted after deployment), the cache is invalidated and audio is regenerated.
    
    Returns:
        - ready: bool - whether audio is available
        - audio_url: str - URL to the audio file (if ready)
        - status: str - current status (generating, ready, failed)
        - estimated_wait: int - estimated seconds until ready (if generating)
    """
    try:
        # Check if the exercise exists in cache or database
        from app.models.cache import GeneratedContentCache
        from sqlalchemy import select, and_
        
        # Look for cached content with this exercise ID
        result = await db.execute(
            select(GeneratedContentCache).where(
                and_(
                    GeneratedContentCache.user_id == current_user.id,
                    GeneratedContentCache.cache_key.contains(exercise_id.replace('listening_', ''))
                )
            ).order_by(GeneratedContentCache.created_at.desc()).limit(1)
        )
        cached = result.scalars().first()
        
        if cached and cached.content:
            audio_url = cached.content.get('audio_url', '')
            
            if audio_url and len(audio_url) > 10:
                # --- SELF-HEALING LOGIC START ---
                # Check if audio URL is valid (cloud URL, not local file)
                if not _is_audio_url_valid(audio_url):
                    logger.warning(
                        f"⚠️ Found broken local audio URL in cache: {audio_url}. "
                        f"Regenerating audio for exercise: {exercise_id}"
                    )
                    
                    # Invalidate the broken cache
                    await db.delete(cached)
                    await db.commit()
                    
                    # Trigger regeneration
                    try:
                        # Extract topic from exercise_id
                        parts = exercise_id.replace('listening_', '').rsplit('_', 1)
                        topic = parts[0].replace('_', ' ') if parts else 'Daily Conversation'
                        level = parts[1] if len(parts) > 1 else 'B1'
                        
                        tts_service = await get_tts_service()
                        regen_result = await tts_service.generate_listening_content(
                            topic=topic,
                            difficulty_level=level,
                            content_type="conversation",
                            speaker_names=["Dr. Anya", "Liam"]
                        )
                        
                        if regen_result.get("success") and regen_result.get("audio_url"):
                            new_audio_url = regen_result.get("audio_url")
                            logger.info(f"✅ Audio regenerated successfully: {new_audio_url}")
                            return {
                                "ready": True,
                                "audio_url": new_audio_url,
                                "status": "ready",
                                "exercise_id": exercise_id,
                                "regenerated": True
                            }
                    except Exception as regen_error:
                        logger.error(f"Failed to regenerate audio: {regen_error}")
                    
                    # If regeneration failed, return generating status
                    return {
                        "ready": False,
                        "audio_url": None,
                        "status": "regenerating",
                        "estimated_wait": 15,
                        "message": "Previous audio was invalid. Regenerating... Please try again shortly."
                    }
                # --- SELF-HEALING LOGIC END ---
                
                return {
                    "ready": True,
                    "audio_url": audio_url,
                    "status": "ready",
                    "exercise_id": exercise_id
                }
        
        # Check if there's a pending audio generation task
        # For now, return a status indicating audio may still be generating
        return {
            "ready": False,
            "audio_url": None,
            "status": "generating",
            "estimated_wait": 10,
            "message": "Audio is still being generated. Please try again shortly."
        }
        
    except Exception as e:
        logger.error(f"Error checking audio status: {e}")
        return {
            "ready": False,
            "audio_url": None,
            "status": "unknown",
            "error": str(e)
        }


@router.post("/regenerate-audio/{exercise_id}")
async def regenerate_audio(
    exercise_id: str,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Dict[str, Any]:
    """
    Regenerate audio for an existing listening exercise.
    
    Use this when the initial audio generation failed or was incomplete,
    or when the cached audio URL points to a deleted local file.
    
    This endpoint will:
    1. Generate new audio using cloud storage (DigitalOcean Spaces)
    2. Invalidate any cached content with broken audio URLs
    3. Return the new valid audio URL
    """
    try:
        # Extract topic from exercise_id (format: listening_topic_level)
        parts = exercise_id.replace('listening_', '').rsplit('_', 1)
        topic = parts[0].replace('_', ' ') if parts else 'Daily Conversation'
        level = parts[1] if len(parts) > 1 else 'B1'
        
        # First, invalidate any broken cache entries for this exercise
        from app.models.cache import GeneratedContentCache
        from sqlalchemy import select, and_
        
        result = await db.execute(
            select(GeneratedContentCache).where(
                and_(
                    GeneratedContentCache.user_id == current_user.id,
                    GeneratedContentCache.cache_key.contains(exercise_id.replace('listening_', ''))
                )
            )
        )
        cached_items = result.scalars().all()
        
        for item in cached_items:
            audio_url = item.content.get("audio_url") if item.content else None
            if audio_url and not _is_audio_url_valid(audio_url):
                logger.info(f"🗑️ Deleting broken cache entry: {item.cache_key}")
                await db.delete(item)
        
        await db.commit()
        
        # Get TTS service and regenerate
        tts_service = await get_tts_service()
        
        result = await tts_service.generate_listening_content(
            topic=topic,
            difficulty_level=level,
            content_type="conversation",
            speaker_names=["Dr. Anya", "Liam"]
        )
        
        if result.get("success") and result.get("audio_url"):
            new_audio_url = result.get("audio_url")
            
            # Verify the new URL is valid (cloud storage)
            if _is_audio_url_valid(new_audio_url):
                logger.info(f"✅ Audio regenerated with valid cloud URL: {new_audio_url}")
                return {
                    "success": True,
                    "audio_url": new_audio_url,
                    "status": "ready",
                    "storage_type": "cloud"
                }
            else:
                logger.warning(f"⚠️ Regenerated audio URL is local file: {new_audio_url}")
                return {
                    "success": True,
                    "audio_url": new_audio_url,
                    "status": "ready",
                    "storage_type": "local",
                    "warning": "Audio stored locally. May not persist after deployment."
                }
        else:
            return {
                "success": False,
                "status": "failed",
                "message": "Failed to regenerate audio. Please try again."
            }
            
    except Exception as e:
        logger.error(f"Error regenerating audio: {e}")
        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }


@router.post("/heal-audio-cache")
async def heal_listening_audio_cache(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Dict[str, Any]:
    """
    Scan and heal all broken audio URLs in the user's listening content cache.
    
    This endpoint finds cached listening content with audio URLs pointing to local
    files (/media/...) and deletes them to trigger fresh regeneration.
    
    Use this endpoint if:
    - Audio files are returning 404 errors
    - Audio playback fails after a deployment
    - You see local file paths instead of cloud URLs
    
    Returns statistics about how many broken entries were found and invalidated.
    """
    try:
        stats = await audio_healing_service.heal_user_audio_cache(
            db=db,
            user_id=current_user.id,
            content_types=["listening", "practice_listening", "micro_listening"]
        )
        
        return {
            "success": True,
            "message": f"Scanned {stats['total_checked']} items, healed {stats['invalidated']} broken entries",
            "stats": {
                "total_checked": stats["total_checked"],
                "broken_found": stats["broken_found"],
                "invalidated": stats["invalidated"],
                "content_types_affected": stats["content_types_affected"]
            },
            "next_steps": "Broken cache entries have been deleted. Fresh content will be generated on next request."
        }
    except Exception as e:
        logger.error(f"Error healing audio cache: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def _generate_fallback_listening(topic: str, level: str, content_type: str) -> Dict[str, Any]:
    """Generate fallback listening content when multi-voice TTS is unavailable.

    2026-05-13 minimal fix — was returning a hardcoded one-line
    template ("Hello! Today we talk about X. It is very interesting.
    Let's learn together!") AND hardcoded comprehension questions
    ("What is the main topic of this conversation?" with options
    [topic, Weather, Sports, Food]) for every level, which meant every
    user whose listening generation fell back saw identical tests.
    Now we ask Gemini for the dialogue AND the comprehension questions
    in one JSON response. Hardcoded transcript + questions remain ONLY
    as last-resort safety net for when Gemini itself is unreachable.
    """
    transcript = ""
    gemini_questions: List[Dict[str, Any]] = []
    try:
        from app.services.ai_service import ai_service
        if ai_service.gemini_model:
            import asyncio as _asyncio
            import json as _json
            length_by_level = {
                "A1": "60-90 words",
                "A2": "90-130 words",
                "B1": "130-180 words",
                "B2": "180-240 words",
                "C1": "240-320 words",
                "C2": "320-400 words",
            }.get(level, "130-180 words")
            prompt = (
                f"Generate listening-practice content for an English "
                f"learner. Topic: \"{topic}\". CEFR level: {level}. "
                f"Content type: {content_type}. Length: {length_by_level}.\n\n"
                "Produce: (a) a multi-speaker dialogue with TWO speakers "
                "with distinct names — each must speak at least twice, "
                "no monologue — and (b) 3-4 comprehension questions "
                "(mix main-idea, detail, and inference). Each question "
                "needs four plausible options where the wrong ones are "
                "defensible misreads, NOT 'Weather/Sports/Food/History/"
                "Science/Art' placeholders.\n\n"
                "Reply ONLY with valid JSON of this exact shape:\n"
                "{\n"
                '  "transcript": "Name: line.\\nName: line.\\n...",\n'
                '  "questions": [\n'
                '    {\n'
                '      "question": "...",\n'
                '      "options": ["A", "B", "C", "D"],\n'
                '      "correct_answer": "the correct option (verbatim)",\n'
                '      "explanation": "Why it is correct, with reference to the dialogue."\n'
                '    }\n'
                "  ]\n"
                "}"
            )
            resp = await _asyncio.wait_for(
                _asyncio.to_thread(ai_service.gemini_model.generate_content, prompt),
                timeout=30.0,
            )
            raw = (getattr(resp, "text", "") or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                raw = raw.rsplit("```", 1)[0].strip()
            try:
                data = _json.loads(raw)
            except Exception:
                import re as _re
                m = _re.search(r"\{[\s\S]*\}", raw)
                data = _json.loads(m.group(0)) if m else {}
            transcript = (data.get("transcript") or "").strip()
            for i, q in enumerate((data.get("questions") or [])[:4]):
                if not isinstance(q, dict):
                    continue
                question_text = (q.get("question") or "").strip()
                options = q.get("options") or []
                correct = q.get("correct_answer") or ""
                if not question_text or not options or not correct:
                    continue
                gemini_questions.append({
                    "id": f"q_{i}",
                    "question": question_text,
                    "options": [str(o) for o in options][:4],
                    "correct_answer": str(correct),
                    "explanation": str(q.get("explanation") or ""),
                })
    except Exception as e:
        logger.warning(
            "Gemini fallback listening generation failed for topic=%s level=%s: %s",
            topic, level, e,
        )

    # Last-resort safety net so we never crash. Only reached when
    # Gemini itself is down. Phrasing is intentionally honest rather
    # than pretending to be real lesson content.
    if not transcript:
        transcript = (
            f"Listening content for {topic} is temporarily unavailable. "
            "Please try again in a moment."
        )

    # Fall back to the old templated questions ONLY if Gemini didn't
    # supply any. In normal operation `gemini_questions` is non-empty
    # and these are unused.
    questions = gemini_questions if gemini_questions else [
        {
            "id": "q_0",
            "question": f"What is the main topic of this {content_type}?",
            "options": [topic, "Weather", "Sports", "Food"],
            "correct_answer": topic,
            "explanation": f"The {content_type} is about {topic}.",
        },
        {
            "id": "q_1",
            "question": "What can you learn from this?",
            "options": ["New vocabulary", "History", "Science", "Art"],
            "correct_answer": "New vocabulary",
            "explanation": "This listening exercise helps you learn new vocabulary.",
        },
    ]

    return {
        "success": True,
        "exercise": {
            "id": f"listening_{topic.replace(' ', '_').lower()}_{level}",
            "title": f"{topic} - Listening Practice",
            "description": f"Listen to the {content_type} about {topic} and answer the questions.",
            "level": level,
            "audio_url": "",  # No audio available
            "transcript": transcript,
            "duration_seconds": 60,
            "questions": questions,
            "vocabulary": [
                {"word": "interesting", "definition": "something that captures attention"},
                {"word": "learn", "definition": "to gain knowledge"}
            ],
            "speakers": [{"name": "Narrator", "voice_name": "Kore"}],
            "content_type": content_type,
            "points": 30,
            "is_fallback": True
        },
        "metadata": {
            "topic": topic,
            "level": level,
            "content_type": content_type,
            "fallback": True
        }
    }


# ==================== AUDIO CONTENT ENDPOINTS ====================

@router.get("/audio-content/", response_model=List[AudioContentResponse])
async def get_audio_content(
    skip: int = 0,
    limit: int = 100,
    content_type: Optional[AudioType] = None,
    difficulty_level: Optional[DifficultyLevel] = None,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get audio content with optional filters"""
    if content_type:
        return await crud_audio_content.get_by_content_type(
            db, content_type=content_type, skip=skip, limit=limit
        )
    elif difficulty_level:
        return await crud_audio_content.get_by_difficulty_level(
            db, difficulty_level=difficulty_level, skip=skip, limit=limit
        )
    else:
        return await crud_audio_content.get_multi(db, skip=skip, limit=limit)

@router.get("/audio-content/search", response_model=List[AudioContentResponse])
async def search_audio_content(
    q: str = Query(..., description="Search query"),
    content_type: Optional[AudioType] = None,
    difficulty_level: Optional[DifficultyLevel] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db)
):
    """Search audio content"""
    return await crud_audio_content.search_content(
        db, query=q, content_type=content_type, 
        difficulty_level=difficulty_level, skip=skip, limit=limit
    )

@router.get("/audio-content/popular", response_model=List[AudioContentResponse])
async def get_popular_audio_content(
    limit: int = 10,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get popular audio content"""
    return await crud_audio_content.get_popular_content(db, limit=limit)

@router.get("/audio-content/{content_id}", response_model=AudioContentResponse)
async def get_audio_content_by_id(
    content_id: int,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get specific audio content"""
    content = await crud_audio_content.get(db, content_id)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio content not found"
        )
    return content

@router.post("/audio-content/", response_model=AudioContentResponse)
async def create_audio_content(
    content_data: AudioContentCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create new audio content (admin only)"""
    # Add admin check here if needed
    return await crud_audio_content.create(db, obj_in=content_data)

@router.put("/audio-content/{content_id}", response_model=AudioContentResponse)
async def update_audio_content(
    content_id: int,
    content_data: AudioContentUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update audio content (admin only)"""
    content = await crud_audio_content.get(db, content_id)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio content not found"
        )
    return await crud_audio_content.update(db, db_obj=content, obj_in=content_data)

@router.post("/audio-content/{content_id}/play", response_model=AudioPlaybackResponse)
async def track_audio_play(
    content_id: int,
    playback_event: AudioPlaybackEvent,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Track audio playback events"""
    if playback_event.action == "play":
        await crud_audio_content.increment_play_count(db, content_id)
    
    return AudioPlaybackResponse(
        success=True,
        message=f"Playback event '{playback_event.action}' recorded",
        current_position=playback_event.position_seconds
    )

# ==================== LISTENING EXERCISES ENDPOINTS ====================

@router.get("/exercises/", response_model=List[ListeningExerciseResponse])
async def get_listening_exercises(
    skip: int = 0,
    limit: int = 100,
    audio_content_id: Optional[int] = None,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get listening exercises"""
    if audio_content_id:
        return await crud_listening_exercise.get_by_audio_content(db, audio_content_id)
    return await crud_listening_exercise.get_multi(db, skip=skip, limit=limit)

@router.get("/exercises/recommended", response_model=List[ListeningExerciseResponse])
async def get_recommended_exercises(
    difficulty_level: Optional[DifficultyLevel] = None,
    limit: int = 5,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get recommended exercises for user"""
    return await crud_listening_exercise.get_recommended_exercises(
        db, user_id=current_user.id, difficulty_level=difficulty_level, limit=limit
    )

@router.get("/exercises/{exercise_id}", response_model=ListeningExerciseResponse)
async def get_listening_exercise(
    exercise_id: int,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get specific listening exercise with questions"""
    exercise = await crud_listening_exercise.get_with_questions(db, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found"
        )
    return exercise

@router.post("/exercises/", response_model=ListeningExerciseResponse)
async def create_listening_exercise(
    exercise_data: ListeningExerciseCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create new listening exercise (admin only)"""
    return await crud_listening_exercise.create(db, obj_in=exercise_data)

@router.put("/exercises/{exercise_id}", response_model=ListeningExerciseResponse)
async def update_listening_exercise(
    exercise_id: int,
    exercise_data: ListeningExerciseUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update listening exercise (admin only)"""
    exercise = await crud_listening_exercise.get(db, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found"
        )
    return await crud_listening_exercise.update(db, db_obj=exercise, obj_in=exercise_data)

# ==================== QUESTIONS ENDPOINTS ====================

@router.get("/exercises/{exercise_id}/questions", response_model=List[QuestionResponse])
async def get_exercise_questions(
    exercise_id: int,
    question_type: Optional[ExerciseType] = None,
    db: AsyncSession = Depends(deps.get_db)
):
    """Get questions for an exercise"""
    if question_type:
        return await crud_question.get_by_type(db, exercise_id, question_type)
    return await crud_question.get_by_exercise(db, exercise_id)

@router.post("/exercises/{exercise_id}/questions", response_model=QuestionResponse)
async def create_question(
    exercise_id: int,
    question_data: QuestionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Create new question for exercise (admin only)"""
    question_data.exercise_id = exercise_id
    return await crud_question.create(db, obj_in=question_data)

@router.put("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: int,
    question_data: QuestionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update question (admin only)"""
    question = await crud_question.get(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    return await crud_question.update(db, db_obj=question, obj_in=question_data)

# ==================== ATTEMPTS AND SUBMISSIONS ENDPOINTS ====================

@router.post("/exercises/{exercise_id}/start", response_model=ListeningAttemptResponse)
async def start_listening_attempt(
    exercise_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Start a new listening attempt"""
    attempt_data = ListeningAttemptCreate(exercise_id=exercise_id)
    attempt = await crud_listening_attempt.create_with_user(
        db, obj_in=attempt_data, user_id=current_user.id
    )
    return attempt

@router.post("/exercises/{exercise_id}/submit", response_model=ExerciseSubmissionResponse)
async def submit_listening_exercise(
    exercise_id: int,
    submission: ExerciseSubmission,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Submit listening exercise answers"""
    # Get or create attempt
    attempts = await crud_listening_attempt.get_exercise_attempts(
        db, user_id=current_user.id, exercise_id=exercise_id
    )
    
    # Get the latest incomplete attempt or create new one
    attempt = None
    for att in attempts:
        if not att.is_completed:
            attempt = att
            break
    
    if not attempt:
        attempt_data = ListeningAttemptCreate(exercise_id=exercise_id)
        attempt = await crud_listening_attempt.create_with_user(
            db, obj_in=attempt_data, user_id=current_user.id
        )
    
    # Complete the attempt with answers
    completed_attempt = await crud_listening_attempt.complete_attempt(
        db, attempt_id=attempt.id, answers=submission.answers
    )
    
    # Update user progress
    await crud_listening_progress.update_progress(
        db, user_id=current_user.id, attempt=completed_attempt
    )
    
    # Get detailed results
    answers = await crud_answer.get_by_attempt(db, attempt.id)
    
    return ExerciseSubmissionResponse(
        attempt_id=completed_attempt.id,
        total_score=completed_attempt.total_score,
        max_possible_score=completed_attempt.max_possible_score,
        completion_percentage=completed_attempt.completion_percentage,
        correct_answers=sum(1 for answer in answers if answer.is_correct),
        total_questions=len(answers),
        detailed_results=[
            {
                "question_id": answer.question_id,
                "user_answer": answer.user_answer,
                "correct_answer": answer.question.correct_answer,
                "is_correct": answer.is_correct,
                "points_earned": answer.points_earned,
                "explanation": answer.question.explanation
            }
            for answer in answers
        ],
        feedback="Great job!" if completed_attempt.total_score >= 70 else "Keep practicing!",
        next_recommendations=[]  # Could implement recommendation logic
    )

@router.get("/attempts/", response_model=List[ListeningAttemptResponse])
async def get_user_attempts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's listening attempts"""
    return await crud_listening_attempt.get_user_attempts(
        db, user_id=current_user.id, skip=skip, limit=limit
    )

@router.get("/attempts/{attempt_id}", response_model=ListeningAttemptResponse)
async def get_listening_attempt(
    attempt_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get specific listening attempt"""
    attempt = await crud_listening_attempt.get(db, attempt_id)
    if not attempt or attempt.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attempt not found"
        )
    return attempt

# ==================== PROGRESS ENDPOINTS ====================

@router.get("/progress/", response_model=ListeningProgressResponse)
async def get_listening_progress(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's listening progress"""
    progress = await crud_listening_progress.get_by_user(db, current_user.id)
    if not progress:
        # Create initial progress
        progress_data = ListeningProgressCreate(current_level=DifficultyLevel.A1)
        progress = await crud_listening_progress.create_with_user(
            db, obj_in=progress_data, user_id=current_user.id
        )
    return progress

@router.put("/progress/", response_model=ListeningProgressResponse)
async def update_listening_progress(
    progress_data: ListeningProgressUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Update user's listening progress settings"""
    progress = await crud_listening_progress.get_by_user(db, current_user.id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progress not found"
        )
    return await crud_listening_progress.update(db, db_obj=progress, obj_in=progress_data)

@router.get("/statistics/", response_model=ListeningStatistics)
async def get_listening_statistics(
    days: int = 30,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get user's listening statistics"""
    stats = await crud_listening_attempt.get_user_statistics(
        db, user_id=current_user.id, days=days
    )
    
    progress = await crud_listening_progress.get_by_user(db, current_user.id)
    
    return ListeningStatistics(
        user_id=current_user.id,
        total_time_minutes=stats["total_time_minutes"],
        exercises_completed=stats["completed_attempts"],
        average_score=stats["average_score"],
        best_score=100.0,  # Could implement this
        current_streak=progress.current_streak_days if progress else 0,
        level_distribution={},  # Could implement this
        monthly_progress={},  # Could implement this
        weak_areas=progress.weak_areas if progress else [],
        strong_areas=progress.strong_areas if progress else []
    )

# ==================== SESSIONS ENDPOINTS ====================

@router.post("/sessions/start", response_model=ListeningSessionResponse)
async def start_listening_session(
    session_data: ListeningSessionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Start a new listening session"""
    return await crud_listening_session.create_with_user(
        db, obj_in=session_data, user_id=current_user.id
    )

@router.get("/sessions/active", response_model=Optional[ListeningSessionResponse])
async def get_active_session(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get active listening session"""
    return await crud_listening_session.get_active_session(db, current_user.id)

@router.post("/sessions/{session_id}/end", response_model=ListeningSessionResponse)
async def end_listening_session(
    session_id: int,
    session_update: ListeningSessionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """End a listening session"""
    session = await crud_listening_session.get(db, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Update session with final data
    session = await crud_listening_session.update(db, db_obj=session, obj_in=session_update)
    
    # End the session
    return await crud_listening_session.end_session(db, session_id)

# ==================== ANALYTICS AND DASHBOARD ENDPOINTS ====================

@router.get("/analytics/", response_model=ListeningAnalytics)
async def get_listening_analytics(
    days: int = 30,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get listening analytics"""
    stats = await crud_listening_attempt.get_user_statistics(
        db, user_id=current_user.id, days=days
    )
    
    progress = await crud_listening_progress.get_by_user(db, current_user.id)
    
    return ListeningAnalytics(
        total_listening_time=stats["total_time_minutes"],
        exercises_completed=stats["completed_attempts"],
        average_score=stats["average_score"],
        improvement_rate=0.0,  # Could calculate this
        streak_days=progress.current_streak_days if progress else 0,
        favorite_content_types=[],  # Could implement this
        performance_by_level={},  # Could implement this
        recent_activity=[]  # Could implement this
    )

@router.get("/dashboard/", response_model=ListeningDashboard)
async def get_listening_dashboard(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get listening dashboard data"""
    # Get user progress
    progress = await crud_listening_progress.get_by_user(db, current_user.id)
    if not progress:
        progress_data = ListeningProgressCreate(current_level=DifficultyLevel.A1)
        progress = await crud_listening_progress.create_with_user(
            db, obj_in=progress_data, user_id=current_user.id
        )
    
    # Get recent attempts
    recent_attempts = await crud_listening_attempt.get_user_attempts(
        db, user_id=current_user.id, skip=0, limit=5
    )
    
    # Get recommended exercises
    recommended_exercises = await crud_listening_exercise.get_recommended_exercises(
        db, user_id=current_user.id, difficulty_level=progress.current_level, limit=5
    )
    
    # Get analytics
    analytics = await get_listening_analytics(db=db, current_user=current_user)
    
    return ListeningDashboard(
        user_progress=progress,
        recent_attempts=recent_attempts,
        recommended_exercises=recommended_exercises,
        analytics=analytics,
        daily_goal_progress={
            "minutes_completed": 0,  # Could implement this
            "goal_minutes": progress.daily_goal_minutes,
            "percentage": 0.0
        },
        achievements=[]  # Could implement this
    ) 