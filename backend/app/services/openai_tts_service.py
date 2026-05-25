"""
OpenAI Text-to-Speech service for SELM.

Drop-in alternative to ``ElevenLabsTTSService`` — exposes the same
``generate_audio_content`` and ``synthesize_multi_voice_dialogue``
interface so the rest of the app (listening endpoint, content workflow,
practice content) needs no changes. Selected via ``TTS_PROVIDER=openai``.

Why this exists
---------------
After several rounds tuning ElevenLabs (model selection, voice pools,
voice_settings, parallel synthesis, accent restriction), Ebrahim's
testers still reported the iPhone voice felt synthetic. The release of
OpenAI's ``gpt-4o-mini-tts`` (2025) was a step change in naturalness:
it accepts a free-form *instructions* parameter (e.g. "speak warmly in
an American accent, conversational pace") that the model actually
follows, giving prosody that ElevenLabs Turbo can't match. Cost is
also lower ($0.015/1K chars vs ElevenLabs $0.05/1K).

Interface
---------
* ``generate_audio_content(text, audio_type, speaker_config, voice_settings)``
  — single-voice synthesis. Mirrors the ElevenLabs signature so call
  sites (users.py / ai.py / listening.py degraded path) need no changes.
* ``synthesize_multi_voice_dialogue(turns, speakers)`` — multi-voice
  per-turn parallel synthesis with bounded concurrency. Same shape as
  the ElevenLabs equivalent so the factory can swap providers
  transparently.
* ``get_cached_audio(filename)`` — pass-through to audio storage.

Voices
------
OpenAI's tts voices are all natural-sounding native English speakers.
We restrict the pool to clearly American-accent voices to match the
brand. The full available set (May 2026):
  - alloy   (neutral, slightly androgynous)
  - ash     (male, calm)
  - ballad  (male, expressive)
  - coral   (female, warm)
  - echo    (male, low and calm)
  - fable   (British male — excluded from American pools)
  - nova    (female, energetic)
  - onyx    (male, deep)
  - sage    (female, mature)
  - shimmer (female, soft)
  - verse   (male, expressive)

Future
------
* Add `gpt-4o-tts` (full-quality variant) when it becomes broadly
  available — currently gpt-4o-mini-tts is the production tier.
* Per-character voice instructions can be tuned by content type
  (e.g., news anchor for News, calm narrator for Story).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import random
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.audio_storage_service import audio_storage_service

logger = logging.getLogger(__name__)


# ── Voice catalogue ───────────────────────────────────────────────────
# OpenAI voices are referenced by short name string. We keep both a
# name → name map (for interface parity with ElevenLabs) and pools by
# category. All entries are American-accent unless explicitly noted.

OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
TIMEOUT_SECONDS = 30.0

DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "nova"

VOICE_NAMES = {
    # English / American
    "alloy", "ash", "ballad", "coral", "echo", "nova",
    "onyx", "sage", "shimmer", "verse",
    # British — used only when caller explicitly asks for a British accent.
    "fable",
}

VOICE_POOLS: Dict[str, List[str]] = {
    "narrator_warm":  ["shimmer", "coral", "sage"],
    "narrator_dry":   ["echo", "onyx", "ash"],
    "adult_female":   ["shimmer", "coral", "sage", "nova"],
    "adult_male":     ["echo", "onyx", "ash", "verse"],
    # OpenAI doesn't have explicit "young" voices the way ElevenLabs
    # does, so the young pools reuse the brighter / lighter members.
    "young_female":   ["nova", "coral"],
    "young_male":     ["verse", "ballad"],
}

# Per-voice "instructions" string sent on each call. This is the new
# `instructions` parameter on gpt-4o-mini-tts (2025+) that the model
# actually follows — the biggest naturalness win we get over ElevenLabs.
# Keep instructions short and pragmatic; the model overweights specifics.
VOICE_INSTRUCTIONS: Dict[str, str] = {
    "alloy":   "Speak in a clear, neutral American accent at a natural conversational pace.",
    "ash":     "Speak in a calm, friendly American male voice. Natural conversational pace.",
    "ballad":  "Speak in an expressive American male voice with a touch of warmth and natural variation.",
    "coral":   "Speak in a warm, friendly American female voice. Sound engaged, like a real person, not a narrator.",
    "echo":    "Speak in a calm, mature American male voice. Easy and steady, slightly low.",
    "nova":    "Speak in a bright, friendly American female voice. Energetic but not rushed.",
    "onyx":    "Speak in a deep, grounded American male voice. Warm and unhurried.",
    "sage":    "Speak in a thoughtful, mature American female voice at a measured pace.",
    "shimmer": "Speak in a soft, warm American female voice. Gentle and natural.",
    "verse":   "Speak in an expressive American male voice — sounds engaged and lively.",
    "fable":   "Speak in a clear, British male accent at a measured, articulate pace.",
}


class OpenAITTSService:
    """OpenAI TTS via /v1/audio/speech (gpt-4o-mini-tts by default)."""

    def __init__(self) -> None:
        self.api_key: Optional[str] = getattr(settings, "OPENAI_API_KEY", None)
        if not self.api_key:
            logger.warning(
                "OPENAI_API_KEY not set; OpenAITTSService will fail until "
                "the key is configured."
            )

    # ── solo TTS (matches ElevenLabsTTSService.generate_audio_content) ──

    async def generate_audio_content(
        self,
        text: str,
        audio_type: str = "conversation",
        speaker_config: Optional[List[Dict[str, Any]]] = None,
        voice_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Single-voice synthesis. Returns same shape as ElevenLabs equivalent."""
        if not self.api_key:
            return {
                "success": False,
                "error": "OPENAI_API_KEY not configured",
                "fallback_available": True,
            }
        if not (text or "").strip():
            return {"success": False, "error": "empty text"}

        voice = self._resolve_voice(speaker_config)
        model = (voice_settings or {}).get("model") or DEFAULT_MODEL
        # Optional speed/instructions overrides from caller.
        speed = float((voice_settings or {}).get("speed", 1.0))
        instructions = (
            (voice_settings or {}).get("instructions")
            or VOICE_INSTRUCTIONS.get(voice, VOICE_INSTRUCTIONS["nova"])
        )

        payload: Dict[str, Any] = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": "mp3",
            "speed": speed,
        }
        # Only gpt-4o-mini-tts (and newer) support `instructions`. tts-1
        # silently ignores it but we send it anyway — no harm.
        if instructions:
            payload["instructions"] = instructions

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            audio_bytes = await self._post_audio(payload, headers)
        except Exception as e:
            logger.exception("OpenAI TTS failed")
            return {"success": False, "error": str(e)}

        if not audio_bytes:
            return {"success": False, "error": "OpenAI returned empty audio"}

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
        filename = f"openai_tts_{timestamp}_{unique_id}_{text_hash}.mp3"

        try:
            stored = await audio_storage_service.store_audio(
                filename=filename,
                audio_bytes=audio_bytes,
                content_type="audio/mpeg",
            )
        except Exception as e:
            logger.exception("Failed to persist OpenAI TTS audio")
            return {"success": False, "error": f"Storage error: {e}"}

        return {
            "success": True,
            "audio_url": stored.get("url") if isinstance(stored, dict) else stored,
            "filename": filename,
            "audio_format": "mp3",
            "tts_engine": "openai",
            "tts_model": model,
            "voice_id": voice,
            "duration_seconds": None,
            "audio_data_base64": base64.b64encode(audio_bytes).decode("ascii"),
        }

    async def get_cached_audio(self, filename: str) -> Optional[Dict[str, Any]]:
        return await audio_storage_service.get_audio(filename)

    # ── multi-voice dialogue (parallel per-turn synthesis) ──

    async def synthesize_multi_voice_dialogue(
        self,
        turns: List[Dict[str, str]],
        speakers: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Per-turn parallel TTS with distinct voices per speaker.

        Matches the signature of ``ElevenLabsTTSService`` so the
        listening endpoint and degraded fallback work without provider-
        specific branching. Bounded concurrency keeps us under OpenAI's
        rate limits while staying fast.
        """
        if not self.api_key:
            return {"success": False, "error": "OPENAI_API_KEY not configured"}
        if not turns:
            return {"success": False, "error": "no turns to synthesise"}

        # Assign voices per speaker name. Pull from female/male pools so
        # two unknown speakers always sound distinct.
        voice_map = self._build_dialogue_voice_map(speakers or [], turns)

        # Anti-single-voice safety (Gemini sometimes omits speaker names
        # → all turns collapse to one voice). If we end up with one or
        # zero distinct speakers, alternate two voices across turns.
        distinct = {(t.get("speaker") or "").strip() for t in turns}
        distinct.discard("")
        if len(distinct) <= 1:
            logger.warning(
                "OpenAI multi-voice: turns have no distinct speaker labels; "
                "alternating two voices as safety net."
            )
            fallback_voices = [
                VOICE_POOLS["adult_female"][0],
                VOICE_POOLS["adult_male"][0],
            ]
            for i, t in enumerate(turns):
                t["speaker"] = f"Speaker {1 + (i % 2)}"
                voice_map[t["speaker"]] = fallback_voices[i % 2]

        sem = asyncio.Semaphore(4)

        async def render_turn(idx: int, turn: Dict[str, str]):
            name = (turn.get("speaker") or "").strip() or "Speaker 1"
            text = (turn.get("text") or "").strip()
            voice = voice_map.get(name, DEFAULT_VOICE)
            if not text:
                return idx, b"", voice, name
            payload = {
                "model": DEFAULT_MODEL,
                "voice": voice,
                "input": text,
                "response_format": "mp3",
                "instructions": VOICE_INSTRUCTIONS.get(voice, VOICE_INSTRUCTIONS["nova"]),
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            async with sem:
                for attempt in range(2):
                    try:
                        audio = await self._post_audio(payload, headers)
                        if audio:
                            return idx, audio, voice, name
                    except Exception as e:
                        if attempt == 0:
                            await asyncio.sleep(0.5)
                            continue
                        logger.warning("OpenAI per-turn TTS turn=%s failed: %s", idx, e)
                return idx, b"", voice, name

        tasks = [render_turn(i, t) for i, t in enumerate(turns)]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        results.sort(key=lambda r: r[0])

        chunks = [r[1] for r in results if r[1]]
        success_ratio = (len(chunks) / len(turns)) if turns else 0
        if success_ratio < 0.6:
            failed = [str(r[0]) for r in results if not r[1]]
            return {
                "success": False,
                "error": (
                    f"too many per-turn TTS calls failed "
                    f"({len(chunks)}/{len(turns)}) — failed turns: "
                    f"{','.join(failed[:5])}"
                ),
            }

        audio_bytes = b"".join(chunks)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"dialogue_openai_{timestamp}_{uuid.uuid4().hex[:8]}.mp3"
        try:
            stored = await audio_storage_service.store_audio(
                filename=filename,
                audio_bytes=audio_bytes,
                content_type="audio/mpeg",
            )
        except Exception as e:
            logger.exception("Failed to persist OpenAI multi-voice audio")
            return {"success": False, "error": f"Storage error: {e}"}

        return {
            "success": True,
            "audio_url": stored.get("url") if isinstance(stored, dict) else stored,
            "filename": filename,
            "audio_format": "mp3",
            "tts_engine": "openai",
            "tts_model": DEFAULT_MODEL,
            "speakers": [{"name": n, "voice_id": v} for n, v in voice_map.items()],
            "turn_count": len(turns),
            "successful_turns": len(chunks),
        }

    # ── internals ──

    async def _post_audio(
        self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> bytes:
        """One HTTP call. Returns audio bytes or raises."""
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(OPENAI_TTS_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            # Surface the body so DO Runtime Logs show *why*.
            logger.error(
                "OpenAI TTS HTTP %s: %s",
                resp.status_code, resp.text[:200],
            )
            return b""
        return resp.content

    def _resolve_voice(
        self, speaker_config: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Pick a voice name from speaker_config.

        Resolution order:
          1. Explicit ``voice_name`` (must be in VOICE_NAMES; ElevenLabs
             names won't match — fall through).
          2. ``voice_category`` → random pick from VOICE_POOLS.
          3. Random pick from a wide American narrator pool.
        """
        if speaker_config:
            first = speaker_config[0]
            name = first.get("voice_name") or first.get("voice_id")
            if name and str(name).lower() in VOICE_NAMES:
                return str(name).lower()
            category = first.get("voice_category")
            if category:
                pool = VOICE_POOLS.get(str(category).lower())
                if pool:
                    return random.choice(pool)
        # Default: rotate across the narrator + adult pools so solo TTS
        # doesn't always sound like the same voice.
        default_pool = (
            VOICE_POOLS["narrator_warm"]
            + VOICE_POOLS["narrator_dry"]
            + VOICE_POOLS["adult_female"]
            + VOICE_POOLS["adult_male"]
        )
        return random.choice(default_pool)

    def _build_dialogue_voice_map(
        self,
        speakers: List[Dict[str, Any]],
        turns: List[Dict[str, str]],
    ) -> Dict[str, str]:
        """Assign one OpenAI voice name per distinct speaker name.

        Gender-matched when speakers metadata carries gender; otherwise
        round-robins across the female and male pools so two unknown
        speakers always sound different.
        """
        female_pool = VOICE_POOLS["adult_female"]
        male_pool = VOICE_POOLS["adult_male"]
        out: Dict[str, str] = {}
        f_i = m_i = 0
        # First pass: use explicit gender hints from speakers metadata.
        for s in speakers or []:
            name = (s.get("name") or s.get("speaker") or "").strip()
            if not name:
                continue
            gender = (s.get("gender") or "").lower()
            if gender.startswith("f"):
                out[name] = female_pool[f_i % len(female_pool)]
                f_i += 1
            elif gender.startswith("m"):
                out[name] = male_pool[m_i % len(male_pool)]
                m_i += 1
        # Second pass: whatever speaker names appear in turns that we
        # haven't already mapped — round-robin so unknowns differ.
        for t in turns:
            name = (t.get("speaker") or "").strip()
            if not name or name in out:
                continue
            if (f_i + m_i) % 2 == 0:
                out[name] = female_pool[f_i % len(female_pool)]
                f_i += 1
            else:
                out[name] = male_pool[m_i % len(male_pool)]
                m_i += 1
        return out


# ── Singleton ─────────────────────────────────────────────────────────

_openai_tts_instance: Optional[OpenAITTSService] = None
_openai_tts_lock: Optional[asyncio.Lock] = None


async def get_openai_tts_service() -> OpenAITTSService:
    global _openai_tts_instance, _openai_tts_lock
    if _openai_tts_lock is None:
        _openai_tts_lock = asyncio.Lock()
    if _openai_tts_instance is None:
        async with _openai_tts_lock:
            if _openai_tts_instance is None:
                _openai_tts_instance = OpenAITTSService()
                logger.info("OpenAI TTS service singleton instance created")
    return _openai_tts_instance
