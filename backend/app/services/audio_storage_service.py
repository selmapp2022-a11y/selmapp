import os
import base64
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta

from app.core.cache import get_redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioStorageService:
    """
    Audio storage service for managing TTS-generated audio files.
    Supports multiple storage backends:
    - filesystem: Local disk storage
    - redis: Redis cache with TTL (temporary storage)
    - spaces: DigitalOcean Spaces (S3-compatible cloud storage)
    """

    def __init__(self):
        self.redis = None
        self._spaces_service = None
        # Config-driven
        self.base_url = getattr(settings, "AUDIO_BASE_URL", "/media/audio")
        self.storage_mode = getattr(settings, "AUDIO_STORAGE_MODE", "filesystem")
        self.storage_dir = getattr(settings, "AUDIO_STORAGE_DIR", "storage/audio")
        self.public_base = getattr(settings, "PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")
        
        # Log the configuration on init
        logger.info(f"AudioStorageService initialized:")
        logger.info(f"  - Storage mode: {self.storage_mode}")
        logger.info(f"  - Storage dir: {self.storage_dir}")
        logger.info(f"  - Base URL: {self.base_url}")
        logger.info(f"  - Public base: {self.public_base}")
    
    def _get_spaces_service(self):
        """Lazy-load the spaces storage service"""
        if self._spaces_service is None:
            from app.services.storage_service import storage_service
            self._spaces_service = storage_service
        return self._spaces_service

    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    async def store_audio(
        self,
        audio_data: str,  # Base64 encoded audio (PCM/WAV bytes base64)
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store audio data and return access information.

        Args:
            audio_data: Base64 encoded audio data
            filename: Desired filename
            metadata: Additional metadata
            user_id: Optional user ID for organizing files in cloud storage

        Returns:
            Dict containing URL and storage information
        """
        try:
            # Decode audio once
            audio_bytes = base64.b64decode(audio_data)
            file_size = len(audio_bytes)
            # Preserve the caller's filename if it already has a known
            # audio extension (mp3/m4a/aac/ogg/wav). Previous behaviour
            # blindly appended ``.wav`` which produced files like
            # ``multi_speaker_…mp3.wav`` whose actual bytes were MP3 —
            # iOS just_audio refused to play them. Map extension →
            # content-type so the upload headers also match the bytes.
            # (2026-05-24 fix.)
            _EXT_TO_MIME = {
                ".mp3": "audio/mpeg",
                ".m4a": "audio/mp4",
                ".aac": "audio/aac",
                ".ogg": "audio/ogg",
                ".wav": "audio/wav",
            }
            _lower = filename.lower()
            matched_ext = next(
                (ext for ext in _EXT_TO_MIME if _lower.endswith(ext)),
                None,
            )
            if matched_ext:
                safe_name = filename
                audio_mime = _EXT_TO_MIME[matched_ext]
            else:
                safe_name = f"{filename}.wav"
                audio_mime = "audio/wav"

            # DigitalOcean Spaces storage mode
            if self.storage_mode == "spaces":
                spaces_service = self._get_spaces_service()
                
                if not spaces_service.is_available:
                    # Log detailed reason for fallback
                    status = spaces_service.get_status()
                    logger.warning(
                        f"Spaces not available (error: {status.get('error')}), "
                        f"falling back to filesystem storage"
                    )
                    # Fall through to filesystem mode
                else:
                    logger.info(f"Using Spaces storage for file: {safe_name}")
                    # Organize files in Spaces: audio/tts/{user_id}/{filename}
                    if user_id:
                        destination_path = f"audio/tts/{user_id}/{safe_name}"
                    else:
                        destination_path = f"audio/tts/{safe_name}"
                    
                    # Upload to Spaces. Use content-type that matches
                    # the actual bytes (mp3/m4a/wav/…) — not a hardcoded
                    # ``audio/wav`` which broke iOS playback.
                    public_url = spaces_service.upload_file(
                        file_content=audio_bytes,
                        destination_path=destination_path,
                        content_type=audio_mime,
                    )
                    
                    if public_url:
                        return {
                            "success": True,
                            "audio_url": public_url,
                            "filename": safe_name,
                            "file_size": file_size,
                            "storage_type": "spaces",
                            "storage_path": destination_path,
                        }
                    else:
                        logger.warning("Spaces upload failed, falling back to filesystem")
                        # Fall through to filesystem mode

            if self.storage_mode == "filesystem" or self.storage_mode == "spaces":
                # Filesystem mode (also fallback for spaces)
                # Ensure target directory exists (group under tts)
                target_dir = os.path.join(self.storage_dir, "tts")
                os.makedirs(target_dir, exist_ok=True)
                full_path = os.path.join(target_dir, safe_name)
                # Write bytes to disk (overwrite if exists)
                with open(full_path, "wb") as f:
                    f.write(audio_bytes)

                # URL resolves via FastAPI static mount; build absolute URL for mobile clients
                if self.base_url.startswith("http://") or self.base_url.startswith("https://"):
                    base = self.base_url.rstrip("/")
                    audio_url = f"{base}/tts/{safe_name}"
                else:
                    # base_url is a path like /media/audio → prefix public base
                    path = self.base_url.rstrip("/")
                    audio_url = f"{self.public_base}{path}/tts/{safe_name}"
                return {
                    "success": True,
                    "audio_url": audio_url,
                    "filename": safe_name,
                    "file_size": file_size,
                    "storage_type": "filesystem",
                }

            # Redis cache mode
            redis = await self._get_redis()
            storage_info = {
                "filename": filename,
                "audio_data": audio_data,
                "file_size": file_size,
                "stored_at": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
                "storage_type": "redis_cache",
            }
            cache_key = f"audio:{filename}"
            await redis.setex(
                cache_key,
                timedelta(hours=24).total_seconds(),
                base64.b64encode(str(storage_info).encode()).decode()
            )
            audio_url = f"/api/v1/ai/audio/{filename}"
            return {
                "success": True,
                "audio_url": audio_url,
                "filename": filename,
                "file_size": file_size,
                "storage_type": "redis_cache",
                "expires_in_hours": 24,
            }

        except Exception as e:
            logger.error(f"Failed to store audio: {e}")
            return {"success": False, "error": str(e)}

    async def get_audio(self, filename: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve audio data by filename.

        Args:
            filename: Audio filename
            user_id: Optional user ID for cloud storage path

        Returns:
            Dict containing audio data and metadata, or None if not found
        """
        try:
            # For Spaces mode, files are accessed directly via public URL
            # This method primarily supports filesystem and redis modes
            if self.storage_mode == "spaces":
                spaces_service = self._get_spaces_service()
                if spaces_service.is_available:
                    # Construct the storage path
                    if user_id:
                        storage_path = f"audio/tts/{user_id}/{filename}"
                    else:
                        storage_path = f"audio/tts/{filename}"
                    
                    if spaces_service.file_exists(storage_path):
                        return {
                            "filename": filename,
                            "audio_url": spaces_service.get_public_url(storage_path),
                            "storage_type": "spaces",
                            # Note: For Spaces, we return the URL directly instead of data
                            # to avoid downloading large files unnecessarily
                        }
                # Fall through to filesystem check

            if self.storage_mode in ("filesystem", "spaces"):
                # Attempt to read from filesystem
                target_dir = os.path.join(self.storage_dir, "tts")
                full_path = os.path.join(target_dir, filename)
                if not os.path.exists(full_path):
                    return None
                with open(full_path, "rb") as f:
                    data = f.read()
                return {
                    "filename": filename,
                    "audio_data": base64.b64encode(data).decode(),
                    "file_size": len(data),
                    "stored_at": None,
                    "metadata": {},
                    "storage_type": "filesystem",
                }

            # Redis mode
            redis = await self._get_redis()
            cache_key = f"audio:{filename}"
            cached_data = await redis.get(cache_key)
            if not cached_data:
                return None
            storage_info = eval(base64.b64decode(cached_data).decode())
            return {
                "filename": filename,
                "audio_data": storage_info["audio_data"],
                "file_size": storage_info["file_size"],
                "stored_at": storage_info["stored_at"],
                "metadata": storage_info["metadata"],
                "storage_type": storage_info["storage_type"],
            }

        except Exception as e:
            logger.error(f"Failed to retrieve audio: {e}")
            return None

    async def delete_audio(self, filename: str, user_id: Optional[str] = None) -> bool:
        """
        Delete audio data by filename.

        Args:
            filename: Audio filename
            user_id: Optional user ID for cloud storage path

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if self.storage_mode == "spaces":
                spaces_service = self._get_spaces_service()
                if spaces_service.is_available:
                    # Construct the storage path
                    if user_id:
                        storage_path = f"audio/tts/{user_id}/{filename}"
                    else:
                        storage_path = f"audio/tts/{filename}"
                    
                    if spaces_service.delete_file(storage_path):
                        return True
                # Fall through to filesystem check

            if self.storage_mode in ("filesystem", "spaces"):
                target_dir = os.path.join(self.storage_dir, "tts")
                full_path = os.path.join(target_dir, filename)
                if os.path.exists(full_path):
                    os.remove(full_path)
                    return True
                return False

            redis = await self._get_redis()
            cache_key = f"audio:{filename}"
            result = await redis.delete(cache_key)
            return result > 0

        except Exception as e:
            logger.error(f"Failed to delete audio: {e}")
            return False

    def generate_audio_url(self, filename: str) -> str:
        """
        Generate access URL for audio file.

        Args:
            filename: Audio filename

        Returns:
            Full URL to access the audio
        """
        return f"{self.base_url}/{filename}"

    async def cleanup_expired_audio(self) -> int:
        """
        Clean up expired audio files.
        Note: With Redis TTL, this is automatic, but this method can be
        extended for other storage backends.

        Returns:
            Number of files cleaned up (always 0 for Redis)
        """
        # Redis handles expiration automatically
        return 0

    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dict containing storage statistics
        """
        try:
            redis = await self._get_redis()

            # Get all audio keys
            audio_keys = await redis.keys("audio:*")
            total_files = len(audio_keys)

            # Calculate total size (approximate)
            total_size = 0
            for key in audio_keys[:10]:  # Sample first 10 for performance
                try:
                    cached_data = await redis.get(key)
                    if cached_data:
                        storage_info = eval(base64.b64decode(cached_data).decode())
                        total_size += storage_info.get("file_size", 0)
                except:
                    pass

            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "storage_type": "redis_cache",
                "estimated_total_size": total_size * (total_files / max(10, len(audio_keys))) if audio_keys else 0
            }

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                "error": str(e),
                "total_files": 0,
                "total_size_bytes": 0
            }

# Global instance
audio_storage_service = AudioStorageService()

