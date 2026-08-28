from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
import base64
import hashlib
import logging
import re

import httpx

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.ai_service import ai_service
from app.services.audio_storage_service import audio_storage_service
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── /v1/ai/text-to-speech multi-voice helper ──────────────────────────────
# Older iOS TestFlight builds call this legacy endpoint once per turn while
# playing a Listening dialogue. The pre-2026-05-24 behaviour was to render
# every call through a single gTTS voice, so the user heard one voice for
# the whole conversation. We can give those clients real multi-voice
# playback WITHOUT shipping a new iOS build by routing this endpoint
# through ElevenLabs and picking a voice based on the "Name:" prefix of
# the line (or a stable hash of the line, when no name is present). Same
# response shape (audio/mpeg StreamingResponse) — pure server-side fix.
_TTS_VOICE_FEMALE = "21m00Tcm4TlvDq8ikWAM"   # Rachel — American
_TTS_VOICE_MALE = "pNInz6obpgDQGcFmaJgB"     # Adam — American
_TTS_MODEL_ID = "eleven_turbo_v2_5"
_TTS_ELEVENLABS_URL = (
    "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
)
_TTS_TIMEOUT = 12.0
_SPEAKER_PREFIX_RE = re.compile(r"^([A-Za-z][\w\-'. ]{0,38}):\s*(.+)$", re.DOTALL)

# Coarse name → gender lookup. Misses are fine — we fall back to a
# stable hash on the speaker name, which still gives consistent voice
# per speaker across multiple turns.
_FEMALE_NAME_HINTS = {
    "anya", "sarah", "mary", "lisa", "emma", "sophie", "ava", "mia",
    "olivia", "isabella", "amelia", "charlotte", "harper", "evelyn",
    "abigail", "ella", "emily", "luna", "chloe", "grace", "zoe", "hannah",
    "lily", "aria", "scarlett", "victoria", "natalie", "alice", "jane",
    "kate", "katie", "anna", "anne", "claire", "rachel", "rose", "ruby",
    "stella", "violet", "willow", "nora", "ivy", "leah", "maya", "jasmine",
    "priya", "aisha", "fatima", "yuki", "mei", "linh", "sofia", "elena",
    "carmen", "linda", "susan", "jennifer", "michelle", "amy", "laura",
    "samantha", "stephanie", "rebecca", "elizabeth", "diana", "monica",
    "narrator", "host", "teacher",
}
_MALE_NAME_HINTS = {
    "liam", "noah", "oliver", "elijah", "william", "james", "benjamin",
    "lucas", "henry", "alexander", "mason", "ethan", "daniel", "matthew",
    "jackson", "logan", "aiden", "owen", "samuel", "david", "joseph",
    "john", "michael", "robert", "thomas", "andrew", "richard", "charles",
    "anthony", "mark", "steven", "kevin", "brian", "george", "edward",
    "ryan", "nicholas", "jonathan", "tyler", "patrick", "sean", "peter",
    "paul", "kyle", "jack", "max", "leo", "luke", "ben", "tom", "sam",
    "mike", "bob", "rick", "joe", "tony", "dan", "carlos", "diego", "raj",
    "amir", "hiroshi", "wei", "kenji", "ahmed", "narrator2",
}


def _pick_voice_for_text(text: str) -> tuple:
    """Return (voice_id, cleaned_text). Cleaned text strips the
    "Name:" prefix so ElevenLabs doesn't actually read the speaker's
    name out loud."""
    s = (text or "").strip()
    if not s:
        return _TTS_VOICE_FEMALE, s
    m = _SPEAKER_PREFIX_RE.match(s)
    if m:
        speaker = m.group(1).strip()
        body = m.group(2).strip()
        first_word = speaker.split()[0].lower() if speaker else ""
        if first_word in _FEMALE_NAME_HINTS:
            return _TTS_VOICE_FEMALE, body
        if first_word in _MALE_NAME_HINTS:
            return _TTS_VOICE_MALE, body
        # Unknown name → stable hash decides (same speaker → same voice).
        h = int(hashlib.md5(first_word.encode("utf-8")).hexdigest(), 16)
        return (
            _TTS_VOICE_FEMALE if h % 2 == 0 else _TTS_VOICE_MALE
        ), body
    # No speaker prefix at all. Use the line itself for the hash so
    # repeated identical lines come back with the same voice.
    h = int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16)
    return (
        _TTS_VOICE_FEMALE if h % 2 == 0 else _TTS_VOICE_MALE
    ), s


async def _render_text_via_elevenlabs(text: str) -> Optional[bytes]:
    """Call ElevenLabs with a voice picked from the line's speaker
    prefix. Returns MP3 bytes, or None on any failure so the caller
    can fall back to the legacy gTTS path."""
    api_key = getattr(settings, "ELEVENLABS_API_KEY", None)
    if not api_key:
        return None
    voice_id, clean_text = _pick_voice_for_text(text)
    if not clean_text.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=_TTS_TIMEOUT) as client:
            resp = await client.post(
                _TTS_ELEVENLABS_URL.format(voice_id=voice_id),
                headers={
                    "xi-api-key": api_key,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                },
                json={
                    "text": clean_text,
                    "model_id": _TTS_MODEL_ID,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.85,
                        "style": 0.25,
                        "use_speaker_boost": True,
                    },
                },
            )
        if resp.status_code == 200 and resp.content:
            return resp.content
        logger.warning(
            "text-to-speech ElevenLabs call failed status=%s body=%s",
            resp.status_code, resp.text[:160],
        )
    except Exception as e:
        logger.warning("text-to-speech ElevenLabs error: %s", e)
    return None

router = APIRouter()

class TextToSpeechRequest(BaseModel):
    text: str
    language: str = "en"
    slow: bool = False

class GeminiTTSRequest(BaseModel):
    """Request model for Gemini native audio TTS"""
    text: str
    voice: Optional[str] = None  # e.g., "Kore", "Puck", "Charon"
    audio_type: str = "general"  # general, assessment, conversation

class GrammarCheckRequest(BaseModel):
    text: str
    # From the goal's exam. Absent -> "en" via profile_for (loud fallback).
    language: str = "en"

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
    """Convert text to speech.

    Now multi-voice aware: when the incoming text starts with a
    ``Name:`` prefix (which the Listening dialogue lines do), we
    pick between Rachel (female) and Adam (male) per speaker via
    ElevenLabs. Same response shape — audio/mpeg StreamingResponse —
    so older iOS TestFlight builds that call this once per turn now
    hear varied voices without needing a client rebuild
    (2026-05-24).

    On any ElevenLabs failure we fall back to the original
    ``ai_service.generate_text_to_speech`` path so the endpoint
    never silently breaks for callers that don't care about voices.
    """
    try:
        audio_data: Optional[bytes] = await _render_text_via_elevenlabs(
            request.text
        )

        if not audio_data:
            # Legacy fallback — single-voice gTTS, kept so we never
            # return an empty response if ElevenLabs is unavailable.
            audio_data = await ai_service.generate_text_to_speech(
                text=request.text,
                language=request.language,
                slow=request.slow,
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
    except HTTPException:
        raise
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
        
        # Build speaker_config that works for BOTH providers:
        #   • If caller specified a voice → honour it (Gemini name passes
        #     straight through; ElevenLabs friendly-name lookup handles
        #     it via NAME_TO_VOICE_ID).
        #   • If caller did NOT specify → pass voice_category instead of
        #     a Gemini-only default ("Kore"). The ElevenLabs resolver
        #     picks a random voice from the narrator_warm pool so two
        #     calls don't return the same voice.  The Gemini resolver
        #     ignores voice_category and falls back to GEMINI_TTS_VOICE
        #     internally, so this is safe across providers.
        #
        # The old behaviour ("voice_name='Kore'" for every call) was a
        # major contributor to "the app has only one voice" — Kore
        # doesn't exist in ElevenLabs' name map, so resolution fell to
        # ELEVENLABS_VOICE_ID (if set) and every call returned the same
        # voice. Confirmed in production 2026-05-13.
        explicit_voice = request.voice
        if explicit_voice:
            speaker_config = [{"name": "Speaker", "voice_name": explicit_voice}]
            voice_log = f"explicit:{explicit_voice}"
        else:
            speaker_config = [{"name": "Speaker", "voice_category": "narrator_warm"}]
            voice_log = "category:narrator_warm (randomised)"

        logger.info(
            f"TTS request: text={request.text[:50]}... ({voice_log})"
        )

        result = await tts_service.generate_audio_content(
            text=request.text,
            audio_type=request.audio_type,
            speaker_config=speaker_config,
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
        result = await ai_service.check_grammar(request.text, language=request.language)
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