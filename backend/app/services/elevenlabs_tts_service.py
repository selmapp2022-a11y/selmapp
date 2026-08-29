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
import time
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

# --- The account's own voice catalogue ---------------------------------------
#
# NAME_TO_VOICE_ID above is a hand-written list of seven premade voices. It was
# enough while every recording was a generic English narration and wrong the
# moment the exams needed accents: a TCF listening recording asking for a
# Quebecois speaker silently got Rachel, a North American female, and nothing
# in the response said so. A wrong accent is not a cosmetic defect in a
# listening exam — it is a different test.
#
# So the catalogue is read from the account instead of written down here. Any
# voice the account holds can be addressed by its display name, or by what it
# IS: language + accent + gender. Adding a voice in the ElevenLabs library is
# then the whole of "give the exam a Quebecois speaker" — no deploy, no edit.
#
# Failure is always silent and downward: an unreadable catalogue returns [] and
# selection falls back to the hard-coded pools. A catalogue that raises into a
# render would turn a cosmetic problem into a missing recording.
ACCOUNT_VOICES_URL = "https://api.elevenlabs.io/v2/voices"
CATALOGUE_TTL_SECONDS = 3600.0
CATALOGUE_PAGE_SIZE = 100


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
        # (voices, fetched_at) — see ACCOUNT_VOICES_URL above.
        self._voice_catalogue: Optional[List[Dict[str, Any]]] = None
        self._voice_catalogue_at: float = 0.0

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

        # Voice selection, in order of how specific the caller was:
        #   an explicit voice_id, a name on the account, what the voice must BE
        #   (language/accent/gender), and only then the hard-coded fallback.
        voice_id = await self._resolve_voice_id_async(speaker_config)
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
        # 2026-05-23: AudioStorageService.store_audio expects
        # ``audio_data`` as a base64-encoded string, not raw
        # ``audio_bytes`` — the original code crashed with
        # "got an unexpected keyword argument 'audio_bytes'" on
        # every ElevenLabs TTS call. Same pattern applied to
        # ``generate_listening_content`` below.
        try:
            stored = await audio_storage_service.store_audio(
                audio_data=base64.b64encode(audio_bytes).decode("ascii"),
                filename=filename,
                metadata={
                    "source": "elevenlabs",
                    "format": "mp3",
                    "voice_id": voice_id,
                    "model_id": model_id,
                },
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
        language: str = "en",
    ) -> Dict[str, Any]:
        # Lazy import: re-use Gemini for script generation but produce audio here.
        from app.services.gemini_tts_service import GeminiTTSService
        gemini = GeminiTTSService()
        script_result = await gemini._generate_script(
            language=language,
            topic=topic,
            difficulty_level=difficulty_level,
            content_type=content_type,
            speaker_names=speaker_names,
        )
        if not script_result.get("success"):
            return script_result

        script: str = script_result["script"] or ""
        speakers_meta: List[Dict[str, Any]] = script_result.get("speakers", []) or []

        # Map each unique speaker name to a stable, gender-appropriate voice
        # IN THE LANGUAGE THAT WAS ASKED FOR. `language` reached the script
        # generator and stopped there, so a French script was read aloud by
        # English voices — audible in the first syllable.
        voice_map = await self._build_speaker_voice_map_async(
            speakers_meta, script, language=language
        )

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
            # Same store_audio signature fix as above — pass base64
            # audio_data, not raw audio_bytes (2026-05-23).
            stored = await audio_storage_service.store_audio(
                audio_data=base64.b64encode(audio_bytes).decode("ascii"),
                filename=filename,
                metadata={
                    "source": "elevenlabs_multi_voice",
                    "format": "mp3",
                    "speakers": len(speakers_meta),
                },
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

    async def generate_multi_speaker_audio(
        self,
        turns: List[Dict[str, str]],
        audio_type: str = "conversation",
        accent: Optional[str] = None,
        voice_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Render a multi-speaker dialogue as a single multi-voice MP3.

        2026-05-23: this method existed only as a CALL in
        ``gemini_tts_service.generate_listening_content`` — the
        attribute itself was never implemented, so every call hit
        ``AttributeError`` and the listening pipeline silently fell
        back to single-voice. iPhone testers reported "one voice
        reading both speakers" for months as a result.

        Takes ``turns`` as a list of ``{"speaker": <name>, "text":
        <line>}`` dicts. Builds a per-speaker voice map via the
        existing :meth:`_build_speaker_voice_map` (gender-matched
        when possible, round-robin otherwise), renders each turn
        through the existing :meth:`_render_dialogue_via_legacy`,
        persists the concatenated MP3 via the audio storage
        service, and returns the same response shape as
        :meth:`generate_audio_content` so the caller in
        ``gemini_tts_service`` can swap providers transparently.
        """
        del audio_type, voice_settings  # accepted for API parity
        # `accent` is no longer discarded — see _build_speaker_voice_map_async.
        if not self.api_key:
            return {"success": False, "error": "ELEVENLABS_API_KEY not configured"}
        if not turns:
            return {"success": False, "error": "no turns to synthesise"}

        # Build a speakers_meta list so _build_speaker_voice_map can
        # use its full logic (gender hints + name heuristics + round
        # robin). The caller in gemini_tts_service passes turns with
        # an optional "gender" hint on each turn — we deduplicate by
        # speaker name and keep the first gender we see.
        seen: Dict[str, Dict[str, Any]] = {}
        for t in turns:
            name = (t.get("speaker") or "").strip()
            if not name:
                continue
            if name not in seen:
                seen[name] = {"name": name, "gender": t.get("gender") or ""}
        speakers_meta = list(seen.values())
        voice_map = await self._build_speaker_voice_map_async(
            speakers_meta, "", accent=accent
        )

        audio_bytes = await self._render_dialogue_via_legacy(turns, voice_map)
        if not audio_bytes:
            return {
                "success": False,
                "error": "per-turn ElevenLabs synthesis returned no audio",
            }

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = (
            f"multi_speaker_{timestamp}_{uuid.uuid4().hex[:8]}.mp3"
        )
        try:
            stored = await audio_storage_service.store_audio(
                audio_data=base64.b64encode(audio_bytes).decode("ascii"),
                filename=filename,
                metadata={
                    "source": "elevenlabs_multi_speaker",
                    "format": "mp3",
                    "speaker_count": len(seen),
                    "turn_count": len(turns),
                },
            )
        except Exception as e:
            logger.exception("Failed to persist multi-speaker audio")
            return {"success": False, "error": f"Storage error: {e}"}

        # The gemini_tts_service caller reads ``audio_data`` directly
        # from this dict (KeyError 'audio_data' was the bug observed in
        # production after the first deploy). Keep both names so any
        # downstream callers still find what they expect.
        # Keep shape compatible with generate_audio_content's return so
        # the gemini_tts_service caller can treat both interchangeably.
        # KeyError 'duration_seconds' was the bug observed in production
        # after the audio_data fix — the caller reads this field directly.
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        return {
            "success": True,
            "audio_url": stored.get("url") if isinstance(stored, dict) else stored,
            "filename": filename,
            "audio_format": "mp3",
            "tts_engine": "elevenlabs",
            "tts_model": DEFAULT_MODEL_ID,
            "voice_id": next(iter(voice_map.values()), DEFAULT_VOICE_ID),
            "speakers": [
                {"name": n, "voice_id": v} for n, v in voice_map.items()
            ],
            "turn_count": len(turns),
            "duration_seconds": None,
            "audio_data": audio_b64,
            "audio_data_base64": audio_b64,
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

    async def _build_speaker_voice_map_async(
        self,
        speakers_meta: List[Dict[str, Any]],
        script: str,
        *,
        language: Optional[str] = None,
        accent: Optional[str] = None,
    ) -> Dict[str, str]:
        """The speaker map, drawn from the account when an accent is asked for.

        `accent` used to be accepted and thrown away — `generate_multi_speaker_audio`
        literally read `del accent`. A caller could ask for a Quebecois
        conversation and receive two North American voices, and nothing in the
        result said otherwise.

        Each gender is filled independently: an account with a Quebecois male
        and no Quebecois female gets the right male voice and falls back for
        the female, rather than discarding both. When a pool comes up empty
        that is logged, because it is the moment the recording stops being in
        the accent it claims.
        """
        if not (language or accent):
            return self._build_speaker_voice_map(speakers_meta, script)

        lang = str(language)[:2] if language else None
        female = [
            v["voice_id"]
            for v in await self.find_voices(language=lang, accent=accent, gender="female")
            if v.get("voice_id")
        ]
        male = [
            v["voice_id"]
            for v in await self.find_voices(language=lang, accent=accent, gender="male")
            if v.get("voice_id")
        ]
        for label, pool in (("female", female), ("male", male)):
            if not pool:
                logger.warning(
                    "no %s voice on the account for language=%s accent=%s; "
                    "those speakers will be rendered in a DIFFERENT accent",
                    label,
                    language,
                    accent,
                )
        return self._build_speaker_voice_map(speakers_meta, script, female, male)

    def _build_speaker_voice_map(
        self,
        speakers_meta: List[Dict[str, Any]],
        script: str,
        female_pool: Optional[List[str]] = None,
        male_pool: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Assign a distinct ElevenLabs voice_id to each speaker name.

        Tries to match gender from speaker metadata first; falls back to a
        round-robin over female/male voice pools so two speakers always sound
        different even when gender is unknown.
        """
        # The pools are arguments now. Passing none keeps the old behaviour —
        # seven premade North American English voices — which is right for a
        # generic English exercise and wrong for any exam that names an accent.
        # `_build_speaker_voice_map_async` fills them from the account.
        female_voices = list(female_pool or []) or [
            "21m00Tcm4TlvDq8ikWAM",  # Rachel
            "EXAVITQu4vr4xnSDxMaL",  # Bella
            "MF3mGyEYCl7XYWbV9V6O",  # Elli
        ]
        male_voices = list(male_pool or []) or [
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

    # ---- The account's voice catalogue ----

    async def load_voice_catalogue(self, force: bool = False) -> List[Dict[str, Any]]:
        """Every voice on the account, as ElevenLabs reports it.

        Cached in the process for an hour. Returns [] rather than raising when
        the key is missing, the call fails, or the permission is absent: a
        catalogue that cannot be read must degrade to the hard-coded pools.
        """
        now = time.monotonic()
        if (
            not force
            and self._voice_catalogue is not None
            and (now - self._voice_catalogue_at) < CATALOGUE_TTL_SECONDS
        ):
            return self._voice_catalogue

        if not self.api_key:
            return []

        voices: List[Dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                page_token: Optional[str] = None
                for _ in range(10):  # bounded: 1000 voices is far past any real account
                    params: Dict[str, Any] = {"page_size": CATALOGUE_PAGE_SIZE}
                    if page_token:
                        params["next_page_token"] = page_token
                    resp = await client.get(
                        ACCOUNT_VOICES_URL,
                        headers={"xi-api-key": self.api_key},
                        params=params,
                    )
                    if resp.status_code != 200:
                        logger.warning(
                            "voice catalogue unavailable (%s): %s",
                            resp.status_code,
                            resp.text[:200],
                        )
                        break
                    body = resp.json()
                    voices.extend(body.get("voices") or [])
                    if not body.get("has_more"):
                        break
                    page_token = body.get("next_page_token")
                    if not page_token:
                        break
        except Exception as exc:  # noqa: BLE001 - never raise into a render
            logger.warning("voice catalogue fetch failed: %s", exc)
            return self._voice_catalogue or []

        if voices:
            self._voice_catalogue = voices
            self._voice_catalogue_at = now
        return voices

    @staticmethod
    def _voice_traits(voice: Dict[str, Any]) -> List[Dict[str, str]]:
        """Every (language, accent, gender) a voice claims.

        A voice carries its own labels, and — when it came from the shared
        library — a `verified_languages` list that is the only place the accent
        per language is recorded. Both are read, because a French voice
        verified as Quebecois often carries `labels.accent` from its English
        entry and would otherwise be matched as the wrong thing.
        """
        labels = voice.get("labels") or {}
        gender = str(labels.get("gender") or "").lower()
        traits: List[Dict[str, str]] = []
        for ver in voice.get("verified_languages") or []:
            traits.append(
                {
                    "language": str(ver.get("language") or "").lower(),
                    "accent": str(ver.get("accent") or "").lower(),
                    "gender": str(ver.get("gender") or gender or "").lower(),
                }
            )
        traits.append(
            {
                "language": str(labels.get("language") or "").lower(),
                "accent": str(labels.get("accent") or "").lower(),
                "gender": gender,
            }
        )
        return traits

    async def find_voices(
        self,
        *,
        language: Optional[str] = None,
        accent: Optional[str] = None,
        gender: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Account voices matching what is asked for. Unset criteria are ignored."""
        want_lang = (language or "").lower() or None
        want_accent = (accent or "").lower() or None
        want_gender = (gender or "").lower() or None

        out: List[Dict[str, Any]] = []
        for voice in await self.load_voice_catalogue():
            for t in self._voice_traits(voice):
                if want_lang and not t["language"].startswith(want_lang):
                    continue
                if want_accent and want_accent not in t["accent"]:
                    continue
                if want_gender and not t["gender"].startswith(want_gender[0]):
                    continue
                out.append(voice)
                break

        # A voice whose OWN language is the one asked for comes first.
        #
        # The vendor verifies accents per language, and the results are better
        # than they look: "Silias North", a Canadian ENGLISH narrator, carries
        # `verified_languages: [{language: fr, accent: fr-quebec}]` — it really
        # does sound Quebecois in French. So cross-language voices belong in
        # the result. They do not belong at the front of it: a native French
        # voice chosen for the cast should outrank an English voice that also
        # speaks French, and without this the order is just catalogue order,
        # which is to say accidental.
        if want_lang:
            out.sort(
                key=lambda v: not str((v.get("labels") or {}).get("language") or "")
                .lower()
                .startswith(want_lang)
            )
        return out

    async def pick_voice(
        self,
        *,
        language: Optional[str] = None,
        accent: Optional[str] = None,
        gender: Optional[str] = None,
        exclude: Optional[Any] = None,
    ) -> Optional[str]:
        """One voice_id for what is asked for, or None.

        None is the honest answer when the account holds nothing of that
        accent, and the caller decides what to do with it. Returning a voice
        of the wrong accent here is how a listening bank ends up in the wrong
        variety without anyone noticing.
        """
        taken = set(exclude or ())
        matches = await self.find_voices(language=language, accent=accent, gender=gender)
        for voice in matches:
            vid = voice.get("voice_id")
            if vid and vid not in taken:
                return vid
        return matches[0].get("voice_id") if matches else None

    async def voice_id_for_name(self, name: str) -> Optional[str]:
        """A voice_id by display name, case-insensitively, prefix-tolerant.

        Display names in the library carry a description after the name
        ("Alexandre - Authentic French Canadian"), so an exact match would fail
        for every voice a person would actually name.
        """
        want = (name or "").strip().lower()
        if not want:
            return None
        catalogue = await self.load_voice_catalogue()
        for voice in catalogue:
            if str(voice.get("name") or "").strip().lower() == want:
                return voice.get("voice_id")
        for voice in catalogue:
            if str(voice.get("name") or "").strip().lower().startswith(want):
                return voice.get("voice_id")
        return None

    # ---- Helpers ----

    async def _resolve_voice_id_async(
        self, speaker_config: Optional[List[Dict[str, Any]]]
    ) -> str:
        """_resolve_voice_id, plus the two things only the account can answer.

        A caller may now say `{"voice_name": "Alexandre - Authentic French
        Canadian"}` or `{"language": "fr", "accent": "quebec", "gender":
        "male"}` and get that voice. If the account holds nothing matching, the
        request falls through to the old behaviour rather than failing — but
        the miss is logged, because a silently substituted accent is exactly
        the defect this exists to prevent.
        """
        if speaker_config:
            first = speaker_config[0]
            if first.get("voice_id"):
                return str(first["voice_id"])

            name = first.get("voice_name") or first.get("name")
            if name:
                found = await self.voice_id_for_name(str(name))
                if found:
                    return found

            language = first.get("language") or first.get("locale")
            accent = first.get("accent") or first.get("variety")
            gender = first.get("gender")
            if language or accent:
                found = await self.pick_voice(
                    language=str(language)[:2] if language else None,
                    accent=str(accent) if accent else None,
                    gender=str(gender) if gender else None,
                )
                if found:
                    return found
                logger.warning(
                    "no account voice for language=%s accent=%s gender=%s; "
                    "falling back to a default voice of a DIFFERENT accent",
                    language,
                    accent,
                    gender,
                )

        return self._resolve_voice_id(speaker_config)

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
