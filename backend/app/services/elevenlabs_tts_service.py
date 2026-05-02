"""
ElevenLabs Text-to-Speech service.

Mirrors the public interface of GeminiTTSService.generate_audio_content
so it can be used as a drop-in replacement.

Configuration (app.core.config.settings):
    TTS_PROVIDER                       - "elevenlabs" or "gemini" (default: gemini)
    ELEVENLABS_API_KEY                 - API key (required when provider is elevenlabs)
    ELEVENLABS_MODEL_ID                - default "eleven_turbo_v2_5"
    ELEVENLABS_VOICE_ID_AMERICAN       - default voice for American English
    ELEVENLABS_VOICE_ID_BRITISH        - default voice for British English
    ELEVENLABS_DEFAULT_ACCENT          - "american" or "british" (default: american)
"""

import asyncio
import io
import wave
import base64
import logging
import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.audio_storage_service import audio_storage_service

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"

# Sensible defaults for high-quality natural voices.
# These can be overridden via env vars.
DEFAULT_VOICE_AMERICAN = "EXAVITQu4vr4xnSDxMaL"  # Sarah – warm American female
DEFAULT_VOICE_BRITISH = "XB0fDUnXU5powFXDhCwa"   # Charlotte – natural British female
DEFAULT_MODEL = "eleven_turbo_v2_5"


class ElevenLabsTTSService:
    """Async ElevenLabs TTS client returning the same response shape as GeminiTTSService."""

    def __init__(self) -> None:
        self.api_key: Optional[str] = getattr(settings, "ELEVENLABS_API_KEY", None)
        self.model_id: str = getattr(settings, "ELEVENLABS_MODEL_ID", DEFAULT_MODEL) or DEFAULT_MODEL
        self.voice_american: str = (
            getattr(settings, "ELEVENLABS_VOICE_ID_AMERICAN", DEFAULT_VOICE_AMERICAN) or DEFAULT_VOICE_AMERICAN
        )
        self.voice_british: str = (
            getattr(settings, "ELEVENLABS_VOICE_ID_BRITISH", DEFAULT_VOICE_BRITISH) or DEFAULT_VOICE_BRITISH
        )
        self.default_accent: str = (
            getattr(settings, "ELEVENLABS_DEFAULT_ACCENT", "american") or "american"
        ).lower()
        if not self.api_key:
            logger.warning(
                "ELEVENLABS_API_KEY not configured. ElevenLabs TTS will return error responses."
            )

    # ------------------------------------------------------------------ helpers

    def _resolve_voice(
        self,
        speaker_config: Optional[List[Dict[str, Any]]],
        voice_settings: Optional[Dict[str, Any]],
    ) -> str:
        """Pick a voice id from explicit override, accent hint, or default."""
        # Explicit voice id wins.
        if speaker_config and isinstance(speaker_config, list) and speaker_config:
            spk = speaker_config[0] or {}
            explicit = spk.get("voice_id") or spk.get("elevenlabs_voice_id")
            if explicit:
                return str(explicit)
            accent = (spk.get("accent") or "").lower()
            if accent in ("british", "uk", "en-gb", "british english"):
                return self.voice_british
            if accent in ("american", "us", "en-us", "american english"):
                return self.voice_american

        if voice_settings:
            explicit = voice_settings.get("voice_id")
            if explicit:
                return str(explicit)
            accent = (voice_settings.get("accent") or "").lower()
            if accent in ("british", "uk", "en-gb"):
                return self.voice_british
            if accent in ("american", "us", "en-us"):
                return self.voice_american

        return self.voice_british if self.default_accent == "british" else self.voice_american

    @staticmethod
    def _wrap_pcm_as_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    # ----------------------------------------------------------------- public

    async def generate_audio_content(
        self,
        text: str,
        audio_type: str = "conversation",
        speaker_config: Optional[List[Dict[str, Any]]] = None,
        voice_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate audio with ElevenLabs and persist via AudioStorageService.

        Returns the same dict shape as GeminiTTSService.generate_audio_content.
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "ElevenLabs API key not configured",
                "fallback_available": True,
            }

        if not text or not text.strip():
            return {"success": False, "error": "Empty text provided to TTS", "fallback_available": False}

        voice_id = self._resolve_voice(speaker_config, voice_settings)

        # Stable, unique filename (matches existing naming scheme used by the player & cache).
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        filename = f"elevenlabs_tts_{timestamp}_{unique_id}_{text_hash}.wav"

        # Voice tuning: allow caller overrides, otherwise pleasant defaults.
        vs = voice_settings or {}
        body = {
            "text": text,
            "model_id": vs.get("model_id") or self.model_id,
            "voice_settings": {
                "stability": float(vs.get("stability", 0.45)),
                "similarity_boost": float(vs.get("similarity_boost", 0.75)),
                "style": float(vs.get("style", 0.0)),
                "use_speaker_boost": bool(vs.get("use_speaker_boost", True)),
            },
        }

        # Request 24 kHz 16-bit PCM so we can wrap in WAV (matches Gemini path)
        url = (
            f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}"
            f"?output_format=pcm_24000"
        )
        headers = {
            "xi-api-key": self.api_key,
            "accept": "audio/wav",
            "content-type": "application/json",
        }

        try:
            # Retry up to 3 times with exponential backoff for transient failures.
            last_error: Optional[str] = None
            pcm_bytes: Optional[bytes] = None
            async with httpx.AsyncClient(timeout=30.0) as client:
                for attempt in range(3):
                    try:
                        resp = await client.post(url, headers=headers, json=body)
                        if resp.status_code == 200:
                            pcm_bytes = resp.content
                            break
                        # Surface the API error message for diagnostics.
                        last_error = (
                            f"ElevenLabs HTTP {resp.status_code}: "
                            f"{resp.text[:200] if resp.text else 'no body'}"
                        )
                        # Don't retry on 4xx (auth, quota, bad voice id).
                        if 400 <= resp.status_code < 500:
                            break
                    except httpx.TimeoutException as e:
                        last_error = f"ElevenLabs timeout: {e}"
                    except httpx.HTTPError as e:
                        last_error = f"ElevenLabs HTTP error: {e}"
                    if attempt < 2:
                        await asyncio.sleep(1 * (attempt + 1))

            if pcm_bytes is None:
                logger.error(f"ElevenLabs TTS failed after retries: {last_error}")
                return {
                    "success": False,
                    "error": last_error or "ElevenLabs TTS failed",
                    "fallback_available": True,
                }

            wav_bytes = self._wrap_pcm_as_wav(pcm_bytes, sample_rate=24000)
            audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

            storage_result = await audio_storage_service.store_audio(
                audio_data=audio_b64,
                filename=filename,
                metadata={
                    "text": text,
                    "audio_type": audio_type,
                    "speaker_config": speaker_config,
                    "voice_settings": vs,
                    "generated_at": datetime.utcnow().isoformat(),
                    "tts_engine": body["model_id"],
                    "voice": voice_id,
                    "api": "elevenlabs",
                },
            )

            voice_label = (
                "Sarah" if voice_id == self.voice_american
                else "Charlotte" if voice_id == self.voice_british
                else voice_id
            )
            accent_label = (
                "american" if voice_id == self.voice_american
                else "british" if voice_id == self.voice_british
                else None
            )
            return {
                "success": True,
                "audio_url": storage_result["audio_url"],
                "filename": storage_result.get("filename", filename),
                "audio_data": audio_b64,
                "duration_seconds": storage_result.get(
                    "duration_seconds", max(1.0, len(text.split()) * 0.4)
                ),
                "file_size": storage_result.get("file_size", len(wav_bytes)),
                "speaker_count": 1,
                "tts_model": body["model_id"],
                "voice": voice_label,
                "voice_id": voice_id,
                "accent": accent_label,
                "provider": "elevenlabs",
                "metadata": {
                    "text_length": len(text),
                    "audio_type": audio_type,
                    "generated_at": datetime.utcnow().isoformat(),
                    "model": body["model_id"],
                    "voice_used": voice_id,
                    "voice_name": voice_label,
                    "accent": accent_label,
                    "api": "elevenlabs",
                },
            }

        except Exception as e:  # noqa: BLE001 — convert to structured failure
            logger.error(f"ElevenLabs TTS generation failed: {e}", exc_info=True)
            return {"success": False, "error": str(e), "fallback_available": True}


# Singleton accessor (same pattern as gemini_tts_service.get_tts_service)
_elevenlabs_tts_instance: Optional[ElevenLabsTTSService] = None
_elevenlabs_tts_lock: Optional[asyncio.Lock] = None


async def get_elevenlabs_tts_service() -> ElevenLabsTTSService:
    """Return a thread-safe singleton ElevenLabsTTSService."""
    global _elevenlabs_tts_instance, _elevenlabs_tts_lock
    if _elevenlabs_tts_lock is None:
        _elevenlabs_tts_lock = asyncio.Lock()
    if _elevenlabs_tts_instance is None:
        async with _elevenlabs_tts_lock:
            if _elevenlabs_tts_instance is None:
                _elevenlabs_tts_instance = ElevenLabsTTSService()
    return _elevenlabs_tts_instance
