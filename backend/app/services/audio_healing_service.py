"""
Audio Self-Healing Service

This service provides "self-healing" capabilities for audio files.
When cached audio URLs point to invalid locations (e.g., local files that no longer exist
after deployment), this service detects and regenerates the audio automatically.

Key Features:
- Validates audio URLs to detect broken/invalid links
- Automatically regenerates audio when needed
- Updates cache with new valid URLs
- Supports both local files and cloud storage (DigitalOcean Spaces)
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.cache import GeneratedContentCache
from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioHealingService:
    """
    Service for detecting and healing broken audio URLs in cached content.
    
    A URL is considered "broken" if:
    1. It starts with /media/ (local file path that may be deleted after deployment)
    2. It starts with media/ (relative local path)
    3. It's empty or None
    
    A URL is considered "valid" if:
    1. It starts with http:// or https:// (cloud storage URL)
    2. It points to a DigitalOcean Spaces CDN endpoint
    """
    
    def __init__(self):
        # Get the expected cloud storage base URL
        self.spaces_cdn_endpoint = getattr(settings, 'SPACES_CDN_ENDPOINT', None)
        self.spaces_bucket = getattr(settings, 'SPACES_BUCKET', None)
        self.spaces_region = getattr(settings, 'SPACES_REGION', 'nyc3')
        
    def is_audio_url_valid(self, audio_url: Optional[str]) -> bool:
        """
        Check if an audio URL is valid (points to cloud storage).
        
        Args:
            audio_url: The audio URL to validate
            
        Returns:
            True if the URL is valid (cloud storage), False if broken (local)
        """
        if not audio_url:
            return False
            
        audio_url = audio_url.strip()
        
        # Empty URL is invalid
        if not audio_url or audio_url == "":
            return False
            
        # Local file paths are invalid (they get deleted on deployment)
        if audio_url.startswith("/media/") or audio_url.startswith("media/"):
            logger.debug(f"Invalid local audio URL detected: {audio_url}")
            return False
            
        # Relative paths without protocol are invalid
        if not audio_url.startswith(("http://", "https://")):
            logger.debug(f"Invalid relative audio URL detected: {audio_url}")
            return False
            
        # Valid cloud URL
        return True
    
    def get_audio_url_status(self, audio_url: Optional[str]) -> Dict[str, Any]:
        """
        Get detailed status of an audio URL.
        
        Args:
            audio_url: The audio URL to check
            
        Returns:
            Dict containing:
                - is_valid: bool
                - url_type: 'cloud', 'local', 'empty', 'relative'
                - needs_regeneration: bool
                - reason: str (if invalid)
        """
        if not audio_url or not audio_url.strip():
            return {
                "is_valid": False,
                "url_type": "empty",
                "needs_regeneration": True,
                "reason": "Audio URL is empty or None"
            }
        
        audio_url = audio_url.strip()
        
        if audio_url.startswith("/media/") or audio_url.startswith("media/"):
            return {
                "is_valid": False,
                "url_type": "local",
                "needs_regeneration": True,
                "reason": "Local file path - may be deleted after deployment",
                "original_url": audio_url
            }
        
        if not audio_url.startswith(("http://", "https://")):
            return {
                "is_valid": False,
                "url_type": "relative",
                "needs_regeneration": True,
                "reason": "Relative URL without protocol",
                "original_url": audio_url
            }
        
        return {
            "is_valid": True,
            "url_type": "cloud",
            "needs_regeneration": False,
            "url": audio_url
        }
    
    async def check_and_heal_content(
        self,
        db: AsyncSession,
        cached_content: GeneratedContentCache,
        regenerate_callback=None
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Check cached content for broken audio URLs and heal if necessary.
        
        Args:
            db: Database session
            cached_content: The cached content to check
            regenerate_callback: Async function to call for regenerating audio
                                 Should accept (topic, level, content_type) and return audio_url
        
        Returns:
            Tuple of (content_dict, was_healed)
        """
        if not cached_content or not cached_content.content:
            return ({}, False)
        
        content = dict(cached_content.content)  # Make a copy
        was_healed = False
        
        # Check for audio_url in various locations
        audio_url_locations = [
            "audio_url",
            "listening_audio_url",
            "exercise.audio_url",
        ]
        
        for location in audio_url_locations:
            audio_url = self._get_nested_value(content, location)
            
            if audio_url:
                status = self.get_audio_url_status(audio_url)
                
                if status["needs_regeneration"]:
                    logger.warning(
                        f"⚠️ Found broken audio URL in cache (key: {cached_content.cache_key}): "
                        f"{audio_url} - Reason: {status['reason']}"
                    )
                    
                    if regenerate_callback:
                        try:
                            # Regenerate audio
                            new_audio_url = await regenerate_callback(
                                topic=cached_content.topic or "general",
                                level=cached_content.level or "B1",
                                content_type=cached_content.content_type
                            )
                            
                            if new_audio_url and self.is_audio_url_valid(new_audio_url):
                                # Update the content with new URL
                                self._set_nested_value(content, location, new_audio_url)
                                was_healed = True
                                logger.info(
                                    f"✅ Successfully healed audio URL: {audio_url} -> {new_audio_url}"
                                )
                            else:
                                logger.error(
                                    f"❌ Failed to regenerate valid audio URL for {cached_content.cache_key}"
                                )
                        except Exception as e:
                            logger.error(f"❌ Error regenerating audio: {e}")
                    else:
                        # No callback provided, just invalidate the cache
                        logger.info(f"No regenerate callback provided, marking content for regeneration")
        
        # Also check exercises list for audio_url
        exercises = content.get("exercises", [])
        if isinstance(exercises, list):
            for i, exercise in enumerate(exercises):
                if isinstance(exercise, dict):
                    exercise_audio = exercise.get("audio_url")
                    if exercise_audio:
                        status = self.get_audio_url_status(exercise_audio)
                        if status["needs_regeneration"]:
                            logger.warning(
                                f"⚠️ Found broken audio URL in exercise {i}: {exercise_audio}"
                            )
                            # Mark as empty - will need regeneration
                            exercises[i]["audio_url"] = ""
                            exercises[i]["needs_audio_regeneration"] = True
                            was_healed = True
        
        if was_healed:
            # Update the cache with healed content
            try:
                cached_content.content = content
                cached_content.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(cached_content)
                logger.info(f"Cache updated with healed content: {cached_content.cache_key}")
            except Exception as e:
                logger.error(f"Failed to update cache with healed content: {e}")
                await db.rollback()
        
        return (content, was_healed)
    
    async def invalidate_broken_cache(
        self,
        db: AsyncSession,
        cache_key: str
    ) -> bool:
        """
        Delete a cache entry with broken audio URL.
        This forces regeneration on next request.
        
        Args:
            db: Database session
            cache_key: The cache key to invalidate
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            result = await db.execute(
                select(GeneratedContentCache).where(
                    GeneratedContentCache.cache_key == cache_key
                )
            )
            cached = result.scalars().first()
            
            if cached:
                await db.delete(cached)
                await db.commit()
                logger.info(f"🗑️ Invalidated broken cache: {cache_key}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache {cache_key}: {e}")
            await db.rollback()
            return False
    
    async def heal_user_audio_cache(
        self,
        db: AsyncSession,
        user_id: int,
        content_types: list = None
    ) -> Dict[str, Any]:
        """
        Scan and heal all broken audio URLs in a user's cache.
        
        Args:
            db: Database session
            user_id: User ID to heal cache for
            content_types: Optional list of content types to check
                          (e.g., ["listening", "practice_listening"])
            
        Returns:
            Dict with healing statistics
        """
        stats = {
            "total_checked": 0,
            "broken_found": 0,
            "invalidated": 0,
            "content_types_affected": set()
        }
        
        try:
            # Query all cached content for user
            query = select(GeneratedContentCache).where(
                GeneratedContentCache.user_id == user_id
            )
            
            if content_types:
                from sqlalchemy import or_
                type_conditions = [
                    GeneratedContentCache.content_type.ilike(f"%{ct}%")
                    for ct in content_types
                ]
                query = query.where(or_(*type_conditions))
            
            result = await db.execute(query)
            cached_items = result.scalars().all()
            
            for item in cached_items:
                stats["total_checked"] += 1
                
                if not item.content:
                    continue
                
                content = item.content
                audio_url = None
                
                # Check various locations for audio_url
                if isinstance(content, dict):
                    audio_url = content.get("audio_url")
                    if not audio_url and "exercise" in content:
                        audio_url = content.get("exercise", {}).get("audio_url")
                
                if audio_url and not self.is_audio_url_valid(audio_url):
                    stats["broken_found"] += 1
                    stats["content_types_affected"].add(item.content_type)
                    
                    # Invalidate the broken cache entry
                    if await self.invalidate_broken_cache(db, item.cache_key):
                        stats["invalidated"] += 1
            
            stats["content_types_affected"] = list(stats["content_types_affected"])
            return stats
            
        except Exception as e:
            logger.error(f"Error healing user cache: {e}")
            return stats
    
    def _get_nested_value(self, d: dict, path: str) -> Any:
        """Get a value from a nested dict using dot notation"""
        keys = path.split(".")
        value = d
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    def _set_nested_value(self, d: dict, path: str, value: Any):
        """Set a value in a nested dict using dot notation"""
        keys = path.split(".")
        current = d
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value


# Global singleton instance
audio_healing_service = AudioHealingService()


async def validate_and_heal_audio_content(
    db: AsyncSession,
    content: Dict[str, Any],
    cache_key: Optional[str] = None,
    regenerate_audio_func=None
) -> Tuple[Dict[str, Any], bool]:
    """
    Convenience function to validate and heal audio content.
    
    Args:
        db: Database session
        content: Content dict that may contain audio_url
        cache_key: Optional cache key to invalidate if healing fails
        regenerate_audio_func: Optional async function to regenerate audio
        
    Returns:
        Tuple of (healed_content, was_modified)
    """
    if not content:
        return (content, False)
    
    audio_url = content.get("audio_url")
    if not audio_url:
        # Also check nested locations
        if "exercise" in content:
            audio_url = content.get("exercise", {}).get("audio_url")
    
    if not audio_url:
        return (content, False)
    
    if audio_healing_service.is_audio_url_valid(audio_url):
        return (content, False)
    
    # Audio URL is broken
    logger.warning(f"⚠️ Broken audio URL detected: {audio_url}")
    
    if regenerate_audio_func:
        try:
            new_audio_url = await regenerate_audio_func()
            if new_audio_url and audio_healing_service.is_audio_url_valid(new_audio_url):
                if "exercise" in content and "audio_url" in content.get("exercise", {}):
                    content["exercise"]["audio_url"] = new_audio_url
                else:
                    content["audio_url"] = new_audio_url
                logger.info(f"✅ Audio URL healed: {new_audio_url}")
                return (content, True)
        except Exception as e:
            logger.error(f"Failed to regenerate audio: {e}")
    
    # If we can't regenerate, invalidate the cache so next request generates fresh
    if cache_key:
        await audio_healing_service.invalidate_broken_cache(db, cache_key)
    
    return (content, False)





