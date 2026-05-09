"""
ElevenLabs Text-to-Speech service.

Drop-in replacement for ``GeminiTTSService`` — exposes the same
``generate_audio_content`` interface so existing endpoints work
without any callsite changes. Selected via ``TTS_PROVIDER=elevenlabs``.

Uses HTTP directly (httpx) to avoid pulling in the elevenlabs SDK.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.cache import get_redis
from app.core.config import settings
from app.services.audio_storage_service import audio_storage_service

logger = logging.getLogger(__name__)

# ElevenLabs default voices. Voice IDs come from https://api.elevenlabs.io/v1/voices
# These are stable, name-stable Eleven Labs voice IDs.
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — clear neutral female narration
NAME_TO_VOICE_ID: Dict[str, str] = {
    "Rachel": "21m00Tcm4TlvDq8ikWAM",
    "Adam": "pNInz6obpgDQGcFmaJgB",
    "Bella": "EXAVITQu4vr4xnSDxMaL",
    "Antoni": "ErXwobaYiN019PkySvjV",
    "Josh": "TxGEqnHWrfWFTfGW9XjX",
    "Sam": "yoZ06aMxZJJ28mfd3POQ",
    "Elli": "MF3mGyEYCl7XYWbV9V6O",
    # Friendly aliases also accepted via case-insensitive lookup.
}

DEFAULT_MODEL_ID = "eleven_turbo_v2_5"   # fast multi-lingual model
TTS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TIMEOUT_SECONDS = 30.0


class ElevenLabsTTSService:
    """Text-to-Speech via ElevenLabs HTTP API."""

    def __init__(self) -> None:
        self.api_key: Optional[str] = getattr(settings, "ELEVENLABS_API_KEY", None)
        if not self.api_key:
            logger.warning(
                "ELEVENLABS_API_KEY not set; ElevenLabsTTSService will fail "
                "until the key is configured."
            )
        self.redis = None

    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    # ---- Public API matching GeminiTTSService ----

    async def generate_audio_content(
        self,
        text: str,
        audio_type: str = "conversation",
        speaker_config: Optional[List[Dict[str, Any]]] = None,
        voice_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate audio for ``text`` and persist via audio_storage_service.

        Returns the same shape as GeminiTTSService.generate_audio_content so
        callers (users.py / ai.py / listening.py) need no changes.
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "ELEVENLABS_API_KEY not configured",
                "fallback_available": True,
            }

        # Voice selection — accept either a voice_id directly or a friendly name.
        voice_id = self._resolve_voice_id(speaker_config)
        model_id = (voice_settings or {}).get("model_id") or DEFAULT_MODEL_ID

        # Sensible defaults; overridable per request.
        merged_voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True,
        }
        if voice_settings:
            for k in ("stability", "similarity_boost", "style", "use_speaker_boost"):
                if k in voice_settings:
                    merged_voice_settings[k] = voice_settings[k]

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        filename = f"elevenlabs_tts_{timestamp}_{unique_id}_{text_hash}.mp3"

        url = TTS_API_URL.format(voice_id=voice_id)
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "text": text,
            "model_id": model_id,
            "voice_settings": merged_voice_settings,
        }

        try:
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        audio_bytes = resp.content
                        break
                    # Retry on 429 (rate limit) and 5xx
                    if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        wait = 2 ** attempt
                        logger.warning(
                            "ElevenLabs TTS attempt %s returned %s; retrying in %ss",
                            attempt + 1, resp.status_code, wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    # Hard failure
                    logger.error(
                        "ElevenLabs TTS failed: status=%s body=%s",
                        resp.status_code, resp.text[:200],
                    )
                    return {
                        "success": False,
                        "error": f"ElevenLabs API error {resp.status_code}",
                        "fallback_available": True,
                    }
                except (httpx.TimeoutException, httpx.NetworkError) as e:
                    if attempt == 2:
                        raise
                    logger.warning(
                        "ElevenLabs TTS network error (attempt %s/3): %s",
                        attempt + 1, e,
                    )
                    await asyncio.sleep(1 * (attempt + 1))
            else:  # pragma: no cover — loop exhausted without break
                return {
                    "success": False,
                    "error": "ElevenLabs TTS exhausted retries",
                    "fallback_available": True,
                }
        except Exception as e:  # pragma: no cover
            logger.exception("ElevenLabs TTS unexpected error")
            return {
                "success": False,
                "error": str(e),
                "fallback_available": True,
            }

        # Persist + return matching GeminiTTSService shape.
        try:
            stored = await audio_storage_service.store_audio(
                filename=filename,
                audio_bytes=audio_bytes,
                content_type="audio/mpeg",
            )
        except Exception as e:
            logger.exception("Failed to persist ElevenLabs audio")
            return {"success": False, "error": f"Storage error: {e}"}

        return {
            "success": True,
            "audio_url": stored.get("url") if isinstance(stored, dict) else stored,
            "filename": filename,
            "audio_format": "mp3",
            "tts_engine": "elevenlabs",
            "tts_model": model_id,
            "voice_id": voice_id,
            "duration_seconds": None,  # ElevenLabs doesn't return duration; clients infer
            "audio_data_base64": base64.b64encode(audio_bytes).decode("ascii"),
        }

    async def get_cached_audio(self, filename: str) -> Optional[Dict[str, Any]]:
        """Retrieve previously generated audio by filename."""
        return await audio_storage_service.get_audio(filename)

    # ── Listening content (multi-speaker, Eleven v3 dialogue) ─────────
    #
    # Uses ElevenLabs ``POST /v1/text-to-dialogue`` (Eleven v3). One request,
    # one MP3, native multi-speaker dialogue with proper prosody, turn-taking
    # and emotional delivery. Replaces the older "TTS-per-turn-and-concat"
    # approach, which produced choppy seams and a robotic feel.
    # (Switched 2026-05-08.)
    async def generate_listening_content(
        self,
        topic: str,
        difficulty_level: str,
        content_type: str = "conversation",
        speaker_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        # Lazy import: re-use Gemini for script generation but produce audio here.
        from app.services.gemini_tts_service import GeminiTTSService
        gemini = GeminiTTSService()
        script_result = await gemini._generate_script(
            topic=topic,
            difficulty_level=difficulty_level,
            content_type=content_type,
            speaker_names=speaker_names,
        )
        if not script_result.get("success"):
            return script_result

        script: str = script_result["script"] or ""
        speakers_meta: List[Dict[str, Any]] = script_result.get("speakers", []) or []

        # Map each unique speaker name to a stable, gender-appropriate voice.
        voice_map = self._build_speaker_voice_map(speakers_meta, script)

        # Parse the script into (speaker, text) turns. Lines like
        # "Speaker Name: text" mark a turn; lines without a colon are
        # appended to the previous turn so paragraph wrapping doesn't
        # split a sentence into a separate single-word call.
        turns: List[Dict[str, str]] = []
        current_speaker: Optional[str] = None
        for raw in script.splitlines():
            line = raw.strip()
            if not line:
                continue
            # Heuristic: "<Name>: text" with the name being short and capitalised.
            if ":" in line:
                head, _, tail = line.partition(":")
                if 1 <= len(head) <= 40 and not head.endswith("."):
                    current_speaker = head.strip()
                    text = tail.strip()
                    if text:
                        turns.append({"speaker": current_speaker, "text": text})
                    continue
            # Continuation line — attach to last turn if present.
            if turns:
                turns[-1]["text"] = (turns[-1]["text"] + " " + line).strip()
            else:
                # No structured speaker yet — treat as narrator with default voice.
                turns.append({"speaker": current_speaker or "Narrator", "text": line})

        if not turns:
            return {"success": False, "error": "Generated script had no speakable turns"}

        if not self.api_key:
            return {"success": False, "error": "ELEVENLABS_API_KEY not configured"}

        # One request to Eleven v3 Text-to-Dialogue → one MP3 with native
        # multi-speaker delivery, proper turn-taking, and matched prosody.
        # The total `inputs[].text` size has to stay under 2000 characters,
        # which fits a typical 5–8-turn 60s listening dialogue easily.
        dialogue_inputs: List[Dict[str, str]] = []
        for turn in turns:
            voice_id = voice_map.get(turn["speaker"], DEFAULT_VOICE_ID)
            dialogue_inputs.append({"text": turn["text"], "voice_id": voice_id})

        payload = {
            "inputs": dialogue_inputs,
            "model_id": "eleven_v3",
            "settings": {"stability": 0.5},
        }
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    "https://api.elevenlabs.io/v1/text-to-dialogue",
                    headers=headers,
                    json=payload,
                )
            if resp.status_code != 200:
                logger.error(
                    "ElevenLabs dialogue v3 failed: status=%s body=%s",
                    resp.status_code, resp.text[:300],
                )
                # Graceful fallback to legacy per-turn synthesis so a v3
                # outage doesn't break Listening for the day.
                audio_bytes = await self._render_dialogue_via_legacy(turns, voice_map)
                if not audio_bytes:
                    return {"success": False, "error": f"ElevenLabs dialogue error {resp.status_code}"}
            else:
                audio_bytes = resp.content
        except Exception as e:
            logger.exception("ElevenLabs dialogue v3 unexpected error")
            audio_bytes = await self._render_dialogue_via_legacy(turns, voice_map)
            if not audio_bytes:
                return {"success": False, "error": str(e)}
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"listening_{timestamp}_{unique_id}.mp3"
        try:
            stored = await audio_storage_service.store_audio(
                filename=filename,
                audio_bytes=audio_bytes,
                content_type="audio/mpeg",
            )
        except Exception as e:
            logger.exception("Failed to persist multi-voice listening audio")
            return {"success": False, "error": f"Storage error: {e}"}

        # Update the speakers list so the UI can show which voice each speaker uses.
        speakers_with_voice: List[Dict[str, Any]] = []
        for s in speakers_meta:
            name = s.get("name") or s.get("speaker") or ""
            speakers_with_voice.append({
                **s,
                "name": name,
                "voice_id": voice_map.get(name, DEFAULT_VOICE_ID),
            })

        return {
            "success": True,
            "topic": topic,
            "difficulty_level": difficulty_level,
            "content_type": content_type,
            "script": script,
            "speakers": speakers_with_voice,
            "audio_url": stored.get("url") if isinstance(stored, dict) else stored,
            "audio_data": base64.b64encode(audio_bytes).decode("ascii"),
            "duration_seconds": script_result.get("duration_seconds", 60),
            "comprehension_questions": script_result.get("comprehension_questions", []),
            "vocabulary_focus": script_result.get("vocabulary_focus", []),
            "metadata": {
                "tts_model": DEFAULT_MODEL_ID,
                "generated_at": datetime.utcnow().isoformat(),
                "speaker_count": len(speakers_with_voice),
                "api": "elevenlabs",
                "multi_voice": True,
            },
        }

    async def _render_dialogue_via_legacy(
        self,
        turns: List[Dict[str, str]],
        voice_map: Dict[str, str],
    ) -> bytes:
        """Fallback path — call /v1/text-to-speech once per turn and
        concatenate. Used when Eleven v3 dialogue is unavailable so we still
        ship Listening with multiple voices, just without the natural
        cross-turn prosody."""
        if not self.api_key:
            return b""
        chunks: List[bytes] = []
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            for turn in turns:
                voice_id = voice_map.get(turn["speaker"], DEFAULT_VOICE_ID)
                payload = {
                    "text": turn["text"],
                    "model_id": DEFAULT_MODEL_ID,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True,
                    },
                }
                headers = {
                    "xi-api-key": self.api_key,
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                }
                try:
                    resp = await client.post(TTS_API_URL.format(voice_id=voice_id), headers=headers, json=payload)
                except Exception:
                    return b""
                if resp.status_code != 200:
                    return b""
                chunks.append(resp.content)
        return b"".join(chunks)

    def _build_speaker_voice_map(
        self,
        speakers_meta: List[Dict[str, Any]],
        script: str,
    ) -> Dict[str, str]:
        """Assign a distinct ElevenLabs voice_id to each speaker name.

        Tries to match gender from speaker metadata first; falls back to a
        round-robin over female/male voice pools so two speakers always sound
        different even when gender is unknown.
        """
        female_voices = [
            "21m00Tcm4TlvDq8ikWAM",  # Rachel
            "EXAVITQu4vr4xnSDxMaL",  # Bella
            "MF3mGyEYCl7XYWbV9V6O",  # Elli
        ]
        male_voices = [
            "pNInz6obpgDQGcFmaJgB",  # Adam
            "ErXwobaYiN019PkySvjV",  # Antoni
            "TxGEqnHWrfWFTfGW9XjX",  # Josh
            "yoZ06aMxZJJ28mfd3POQ",  # Sam
        ]

        # Collect speaker names from metadata + parse script for "<Name>:" lines.
        names: List[str] = []
        for s in speakers_meta:
            n = s.get("name") or s.get("speaker")
            if n and n not in names:
                names.append(n)
        for line in (script or "").splitlines():
            head = line.split(":", 1)[0].strip() if ":" in line else ""
            if head and 1 <= len(head) <= 40 and head not in names:
                names.append(head)

        out: Dict[str, str] = {}
        f_i = m_i = 0
        for s in speakers_meta:
            name = s.get("name") or s.get("speaker") or ""
            if not name:
                continue
            gender = (s.get("gender") or "").lower()
            if gender.startswith("f"):
                out[name] = female_voices[f_i % len(female_voices)]
                f_i += 1
            elif gender.startswith("m"):
                out[name] = male_voices[m_i % len(male_voices)]
                m_i += 1
        # Fill in any names that didn't come from metadata.
        for name in names:
            if name in out:
                continue
            # Heuristic by stereotypical English first names.
            if name.lower() in {"sarah", "anya", "emily", "maria", "grace", "rachel", "anna", "lisa", "kate", "emma"}:
                out[name] = female_voices[f_i % len(female_voices)]
                f_i += 1
            elif name.lower() in {"tom", "liam", "john", "ben", "alex", "lucas", "mark", "david", "james", "mike"}:
                out[name] = male_voices[m_i % len(male_voices)]
                m_i += 1
            else:
                # Round-robin between pools so 2 unknown speakers still sound different.
                if (f_i + m_i) % 2 == 0:
                    out[name] = female_voices[f_i % len(female_voices)]
                    f_i += 1
                else:
                    out[name] = male_voices[m_i % len(male_voices)]
                    m_i += 1
        return out

    # ---- Helpers ----

    def _resolve_voice_id(
        self, speaker_config: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Pick a voice_id from speaker_config; fall back to env or Rachel."""
        if speaker_config:
            first = speaker_config[0]
            # Prefer explicit voice_id if caller supplied one.
            vid = first.get("voice_id")
            if vid:
                return vid
            name = first.get("voice_name") or first.get("name")
            if name:
                # Case-insensitive name lookup.
                for k, v in NAME_TO_VOICE_ID.items():
                    if k.lower() == str(name).lower():
                        return v
        # Per-deployment override: ELEVENLABS_VOICE_ID env var (optional).
        env_voice = getattr(settings, "ELEVENLABS_VOICE_ID", None)
        if env_voice:
            return env_voice
        return DEFAULT_VOICE_ID


# Singleton ----------------------------------------------------------------

_elevenlabs_instance: Optional[ElevenLabsTTSService] = None
_elevenlabs_lock: Optional[asyncio.Lock] = None


async def get_elevenlabs_tts_service() -> ElevenLabsTTSService:
    """Get or create a singleton ElevenLabs TTS service."""
    global _elevenlabs_instance, _elevenlabs_lock
    if _elevenlabs_lock is None:
        _elevenlabs_lock = asyncio.Lock()
    if _elevenlabs_instance is None:
        async with _elevenlabs_lock:
            if _elevenlabs_instance is None:
                _elevenlabs_instance = ElevenLabsTTSService()
                logger.info("ElevenLabs TTS service singleton instance created")
    return _elevenlabs_instance
