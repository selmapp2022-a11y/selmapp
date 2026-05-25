import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.cache import GeneratedContentCache
from app.core.cache import get_redis
from app.core.config import settings

logger = logging.getLogger(__name__)


# Generation version. Bump this whenever the content-generation logic
# changes in a way that should invalidate every existing cached lesson.
# The suffix becomes part of the cache key, so old rows mismatch and
# every user gets a fresh generation against the new prompts on their
# next request — without us having to TRUNCATE the cache table.
#
# History:
#   v1 (implicit, pre-2026-05-13) — original prompts, gTTS audio, no
#       creative-variation repository, Persian-default learner context.
#   v2 (2026-05-13) — CEFR matrix + human-voice rules + creative seed
#       (scenes / hooks / perspectives / structures / international
#       names) + voice-pool TTS + multi-speaker listening. Bump here
#       made every user see fresh content on next request.
#   v3 (2026-05-13 later same day) — substantially increased word
#       targets across all CEFR levels (A1=120, B1=320, C2=850),
#       added substantive-depth guardrails to every prompt, bumped
#       listening dialogue lengths, dropped hardcoded "Kore" voice in
#       call sites + downgraded ELEVENLABS_VOICE_ID env to opt-in so
#       solo TTS finally randomises across the voice pool.
#   v4 (2026-05-13 evening) — upgraded content-generation model from
#       gemini-2.5-flash-lite → gemini-2.5-pro for reading passages,
#       listening dialogues, exercises, vocab, conversation practice.
#       Significant prose-quality jump at multi-paragraph scale.
#   v5 (2026-05-13 late evening) — discovered the real "everything is
#       the same one line" bug: both listening.py and
#       content_generation_workflow were silently dropping to hardcoded
#       template paths whenever ElevenLabs multi-voice dialogue failed
#       (which was every request). The speaking flow was even worse —
#       it ALWAYS used seven hardcoded paragraphs and never called
#       Gemini at all. Replaced every fallback with a real Gemini-
#       backed degradation path. Cache invalidated so the bogus
#       template content from v3/v4 is finally cleared.
#   v6 (2026-05-13 night) — switched ElevenLabs DEFAULT_MODEL_ID from
#       eleven_turbo_v2_5 → eleven_multilingual_v2 for noticeably more
#       natural prosody and reliable American accent. Voice pools
#       restricted to American-only voices. v3 dialogue endpoint now
#       falls back to the new parallel synthesize_multi_voice_dialogue
#       instead of the slow sequential legacy helper. Plan upgraded to
#       unlimited so cost is no longer a constraint.
#   v7 (2026-05-13 late night) — TWO regressions in v6: latency went
#       from 10 s → 60 s, voices still not natural. Reverted model to
#       eleven_turbo_v2_5 (English-optimised, ~75 ms latency, more
#       natural for American English than multilingual). Disabled the
#       v3 dialogue endpoint attempt by default (was burning 30 s per
#       request on the timeout — plan doesn't have v3 access). Tuned
#       voice_settings (similarity_boost 0.85, style 0.25-0.35) for
#       richer, less robotic delivery.
#   v8 (2026-05-13 latest) — script-gen for listening switched from
#       gemini-2.5-pro to gemini-2.5-flash (DIALOGUE tier) — pro was
#       the real source of the 60 s wait (15-30 s per script). Added
#       anti-single-voice safety in synthesize_multi_voice_dialogue
#       (when Gemini omits speaker labels, alternate two voices) and
#       a 60 %-failure threshold so we don't play garbled partial
#       audio when many turns time out.
#   v9 (2026-05-13 final) — switched primary TTS provider from
#       ElevenLabs to OpenAI gpt-4o-mini-tts. Per-voice instructions
#       give materially more natural English prosody and the factory
#       cascades automatically (openai → elevenlabs → gemini) so a
#       fresh env always produces audio. Voice pool: 10 American
#       voices (alloy, ash, ballad, coral, echo, nova, onyx, sage,
#       shimmer, verse).
CONTENT_GENERATION_VERSION: str = "v9-2026-05-13"


def build_cache_key(*, user_id: int, content_type: str, topic: str, level: str, day_number: int) -> str:
    # Deterministic cache key, all lowercase topic/level for stability.
    # The trailing version segment is what makes a "bump" invalidate
    # everything generated before — see CONTENT_GENERATION_VERSION above.
    safe_topic = (topic or "").strip().lower()
    safe_level = (level or "").strip().upper()
    return (
        f"user:{user_id}|type:{content_type}|topic:{safe_topic}"
        f"|level:{safe_level}|day:{day_number}|gen:{CONTENT_GENERATION_VERSION}"
    )


def is_audio_url_valid(audio_url: Optional[str]) -> bool:
    """
    Check if an audio URL is valid (points to cloud storage, not local files).
    
    Local file paths (/media/...) are considered invalid because:
    - They get deleted during deployments
    - They don't persist across container restarts
    - They're not accessible from CDN
    """
    if not audio_url:
        return False
        
    audio_url = audio_url.strip()
    
    # Empty URL is invalid
    if not audio_url:
        return False
        
    # Local file paths are invalid (they get deleted on deployment)
    if audio_url.startswith("/media/") or audio_url.startswith("media/"):
        return False
        
    # Relative paths without protocol are invalid
    if not audio_url.startswith(("http://", "https://")):
        return False
        
    return True


class ContentCacheService:
    async def get_cached(
        self, 
        db: AsyncSession, 
        *, 
        cache_key: str,
        validate_audio: bool = True
    ) -> Optional[GeneratedContentCache]:
        """
        Get cached content with optional audio URL validation.
        
        If validate_audio is True and the cached content has a broken audio URL
        (local file path), the cache entry will be invalidated and None returned,
        forcing regeneration on the next request.
        """
        result = await db.execute(
            select(GeneratedContentCache).where(GeneratedContentCache.cache_key == cache_key)
        )
        obj = result.scalars().first()
        if not obj:
            return None
        # Expiration check
        if obj.expires_at and obj.expires_at < datetime.utcnow():
            return None
        
        # --- SELF-HEALING LOGIC START ---
        if validate_audio and obj.content:
            audio_url = self._extract_audio_url(obj.content)
            
            if audio_url and not is_audio_url_valid(audio_url):
                logger.warning(
                    f"⚠️ Found broken local audio URL in cache: {audio_url}. "
                    f"Cache key: {cache_key}. Invalidating for regeneration..."
                )
                # Delete the broken cache entry
                await db.delete(obj)
                await db.commit()
                # Return None to trigger regeneration
                return None
        # --- SELF-HEALING LOGIC END ---
        
        return obj
    
    async def get_cached_with_healing(
        self, 
        db: AsyncSession, 
        *, 
        cache_key: str,
        regenerate_audio_callback=None
    ) -> Tuple[Optional[GeneratedContentCache], bool]:
        """
        Get cached content and attempt to heal broken audio URLs.
        
        Args:
            db: Database session
            cache_key: Cache key to look up
            regenerate_audio_callback: Optional async function to regenerate audio.
                                       Should return a new audio URL.
        
        Returns:
            Tuple of (cached_content, was_healed)
            - If audio was broken and regenerated, was_healed is True
            - If cache was invalidated, returns (None, False)
        """
        result = await db.execute(
            select(GeneratedContentCache).where(GeneratedContentCache.cache_key == cache_key)
        )
        obj = result.scalars().first()
        
        if not obj:
            return (None, False)
            
        # Expiration check
        if obj.expires_at and obj.expires_at < datetime.utcnow():
            return (None, False)
        
        # Check for broken audio URLs
        if obj.content:
            audio_url = self._extract_audio_url(obj.content)
            
            if audio_url and not is_audio_url_valid(audio_url):
                logger.warning(
                    f"⚠️ Found broken local audio URL: {audio_url}. Attempting to heal..."
                )
                
                if regenerate_audio_callback:
                    try:
                        # Try to regenerate audio
                        new_audio_url = await regenerate_audio_callback()
                        
                        if new_audio_url and is_audio_url_valid(new_audio_url):
                            # Update the cache with new URL
                            content = dict(obj.content)
                            self._update_audio_url(content, new_audio_url)
                            obj.content = content
                            obj.updated_at = datetime.utcnow()
                            await db.commit()
                            await db.refresh(obj)
                            logger.info(f"✅ Successfully healed audio URL: {new_audio_url}")
                            return (obj, True)
                    except Exception as e:
                        logger.error(f"Failed to regenerate audio: {e}")
                
                # Could not heal - invalidate cache
                logger.info(f"🗑️ Invalidating broken cache: {cache_key}")
                await db.delete(obj)
                await db.commit()
                return (None, False)
        
        return (obj, False)
    
    def _extract_audio_url(self, content: Dict[str, Any]) -> Optional[str]:
        """Extract audio URL from content dictionary"""
        if not isinstance(content, dict):
            return None
            
        # Check common locations for audio_url
        audio_url = content.get("audio_url")
        
        if not audio_url:
            # Check in exercise object
            exercise = content.get("exercise", {})
            if isinstance(exercise, dict):
                audio_url = exercise.get("audio_url")
        
        if not audio_url:
            # Check in listening data
            listening = content.get("listening", {})
            if isinstance(listening, dict):
                audio_url = listening.get("audio_url")
        
        return audio_url
    
    def _update_audio_url(self, content: Dict[str, Any], new_url: str):
        """Update audio URL in content dictionary"""
        if "audio_url" in content:
            content["audio_url"] = new_url
        
        if "exercise" in content and isinstance(content["exercise"], dict):
            if "audio_url" in content["exercise"]:
                content["exercise"]["audio_url"] = new_url
        
        if "listening" in content and isinstance(content["listening"], dict):
            if "audio_url" in content["listening"]:
                content["listening"]["audio_url"] = new_url

    async def save_cached(
        self,
        db: AsyncSession,
        *,
        cache_key: str,
        user_id: int,
        content_type: str,
        topic: Optional[str],
        level: Optional[str],
        day_number: Optional[int],
        payload: Dict[str, Any],
        refs: Optional[Dict[str, Any]] = None,
        model_used: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        status: str = "ready",
        error: Optional[str] = None,
    ) -> GeneratedContentCache:
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        obj = GeneratedContentCache(
            user_id=user_id,
            cache_key=cache_key,
            content_type=content_type,
            topic=topic,
            level=level,
            day_number=day_number,
            params=None,
            content=payload,
            content_refs=refs,
            model_used=model_used,
            status=status,
            error=error,
            expires_at=expires_at,
        )

        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    async def with_distributed_lock(self, key: str, *, ttl_seconds: int = 60):
        redis = await get_redis()
        lock_key = f"lock:{key}"
        locked = await redis.set(lock_key, "1", nx=True, ex=ttl_seconds)
        return locked is True

    async def release_lock(self, key: str):
        redis = await get_redis()
        await redis.delete(f"lock:{key}")


content_cache_service = ContentCacheService()





















