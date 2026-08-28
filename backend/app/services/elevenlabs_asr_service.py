"""
ElevenLabs Scribe Speech-to-Text service.

Drop-in replacement for ``GoogleSTTService.transcribe`` — the public method
returns the same ``{success, text, confidence, words}`` shape, so callers
(speaking_eval, conversation service) need no changes.

Why this exists: the deployed Google Cloud project doesn't have
Cloud Speech-to-Text enabled and the operator can't enable it (the project
isn't theirs — it's the one tied to the API key). The user already has an
ElevenLabs subscription wired up for TTS, so we reuse the same key here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)

ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL_ID = "scribe_v1"
TIMEOUT_SECONDS = 30.0


class ElevenLabsASRService:
    """Speech-to-text via ElevenLabs Scribe."""

    def __init__(self) -> None:
        self.api_key: Optional[str] = getattr(settings, "ELEVENLABS_API_KEY", None)

    async def transcribe(self, audio_bytes: bytes, language_code: str = "en-US") -> Dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "ELEVENLABS_API_KEY not configured"}
        if not audio_bytes:
            return {"success": False, "error": "Empty audio"}

        # Scribe wants a 2-letter language code; map common BCP-47 codes.
        lang = (language_code or "en-US").split("-")[0].lower()

        form = aiohttp.FormData()
        form.add_field("model_id", DEFAULT_MODEL_ID)
        form.add_field("language_code", lang)
        # Pin verbatim ON explicitly. Scribe defaults no_verbatim=false, which
        # keeps filler words, false starts and pauses — and the fluency scoring
        # downstream DEPENDS on those: strip the hesitations and a halting
        # answer reads as fluent. The default is currently correct, but the
        # whole pronunciation/fluency path rests on it, so it is set here
        # rather than inherited, where a vendor default change could flip it
        # silently. timestamps_granularity defaults to "word", which is the
        # single timing source the annotated playback uses; set it too so the
        # word list the client aligns against can never quietly change shape.
        form.add_field("no_verbatim", "false")
        form.add_field("timestamps_granularity", "word")
        # Send raw bytes — Scribe sniffs the format. We label as audio/webm
        # since the browser MediaRecorder ships webm/opus by default.
        form.add_field(
            "file",
            audio_bytes,
            filename="recording.webm",
            content_type="audio/webm",
        )

        headers = {"xi-api-key": self.api_key, "Accept": "application/json"}

        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(ELEVENLABS_STT_URL, headers=headers, data=form) as resp:
                    ct = (resp.headers.get("Content-Type") or "").lower()
                    if "application/json" in ct:
                        data = await resp.json()
                    else:
                        body = await resp.text()
                        return {
                            "success": False,
                            "error": {"status": resp.status, "body": body[:500]},
                        }
                    if resp.status != 200:
                        return {"success": False, "error": data}
        except Exception as e:
            logger.error(f"ElevenLabs STT network error: {e}")
            return {"success": False, "error": str(e)}

        text = (data.get("text") or "").strip()
        words: List[Dict[str, Any]] = []
        for w in data.get("words", []) or []:
            # ElevenLabs returns non-word tokens like spacing/punctuation —
            # filter them so the rest of the pipeline only sees real words.
            if (w.get("type") or "word") != "word":
                continue
            start_s = w.get("start")
            end_s = w.get("end")
            words.append({
                "word": w.get("text", ""),
                "startMs": int(start_s * 1000) if isinstance(start_s, (int, float)) else None,
                "endMs": int(end_s * 1000) if isinstance(end_s, (int, float)) else None,
                "confidence": w.get("logprob"),
            })

        return {
            "success": True,
            "text": text,
            "confidence": 0.95 if text else 0.0,
            "words": words,
            "raw": data,
        }
