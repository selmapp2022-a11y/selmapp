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


def build_cache_key(*, user_id: int, content_type: str, topic: str, level: str, day_number: int) -> str:
    # Deterministic cache key, all lowercase topic/level for stability
    safe_topic = (topic or "").strip().lower()
    safe_level = (level or "").strip().upper()
    return f"user:{user_id}|type:{content_type}|topic:{safe_topic}|level:{safe_level}|day:{day_number}"


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





















