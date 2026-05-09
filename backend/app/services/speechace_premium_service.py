"""
SpeechAce Premium service — single client for every premium endpoint.

Why this exists: SpeechAce Premium covers everything we need (Live
Conversation STT + scoring, IELTS bands, written essay scoring, task
achievement). Adding more vendors (ElevenLabs Scribe, Google STT, ELSA)
just multiplies failure modes for no benefit. Route everything through
this one client and they all use the same API key the operator already
configured for the Pronunciation tab.

Endpoints used:

- ``POST /api/scoring/speech/v9/json`` — Score Speech / Open-ended
  Free-form spoken response (≤ 2 min). Returns transcript +
  pronunciation/fluency/coherence/vocabulary/grammar scores +
  IELTS / PTE / TOEFL / CEFR scaled scores. Used by Live Conversation
  (transcript only) and IELTS Speaking (full assessment).

- ``POST /api/scoring/task/v9/json`` — Score Task / Task Achievement
  Same as open-ended but graded against a specific prompt
  (Describe-Image, Retell-Lecture, Answer-Question). Used by IELTS Part 2.

- ``POST /api/scoring/writing/v9/json`` — Score Writing
  Written-text assessment (no audio). Returns grammar + vocabulary +
  coherence + task achievement aligned to IELTS/CEFR. Used by Writing.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.speechace.co/api/scoring"
SCORE_SPEECH_URL = f"{BASE_URL}/speech/v9/json"
SCORE_TASK_URL = f"{BASE_URL}/task/v9/json"
SCORE_WRITING_URL = f"{BASE_URL}/writing/v9/json"
TIMEOUT_SECONDS = 60.0


class SpeechAcePremiumService:
    """Unified client for SpeechAce Premium endpoints."""

    def __init__(self) -> None:
        self.api_key: Optional[str] = getattr(settings, "SPEECHACE_API_KEY", None)
        self.dialect: str = "en-us"

    # ─── public — Live Conversation / IELTS ────────────────────────

    async def score_open_ended(
        self,
        audio_bytes: bytes,
        relevance_context: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Score a free-form spoken response.

        ``relevance_context`` is the question or topic the user is
        responding to; SpeechAce uses it to compute a relevance score.
        Pass ``None`` for pure transcription."""
        if not self.api_key:
            return {"success": False, "error": "SPEECHACE_API_KEY not configured"}
        if not audio_bytes:
            return {"success": False, "error": "Empty audio"}

        params = {"key": self.api_key, "dialect": self.dialect}
        form = aiohttp.FormData()
        form.add_field("user_audio_file", audio_bytes, filename="audio.webm", content_type="audio/webm")
        if relevance_context:
            form.add_field("relevance_context", relevance_context)
        if user_id:
            form.add_field("user_id", user_id)
        return await self._post(SCORE_SPEECH_URL, params, form, tag="open-ended")

    async def transcribe(self, audio_bytes: bytes, language_code: str = "en-US") -> Dict[str, Any]:
        """Drop-in replacement for ``GoogleSTTService.transcribe`` —
        returns ``{success, text, confidence, words}``. Uses the
        open-ended endpoint and only surfaces the transcript field."""
        del language_code  # SpeechAce premium endpoint is locked to en-us today
        result = await self.score_open_ended(audio_bytes)
        if not result.get("success"):
            return {"success": False, "error": result.get("error")}
        data = result.get("data") or {}
        text = self._extract_transcript(data)
        return {
            "success": True,
            "text": text,
            "confidence": 0.95 if text else 0.0,
            "words": [],
            "raw": data,
        }

    async def score_task(
        self,
        audio_bytes: bytes,
        question_prompt: str,
        task_type: str = "answer-question",
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Score audio against a specific prompt for task achievement."""
        if not self.api_key:
            return {"success": False, "error": "SPEECHACE_API_KEY not configured"}
        params = {"key": self.api_key, "dialect": self.dialect}
        form = aiohttp.FormData()
        form.add_field("user_audio_file", audio_bytes, filename="audio.webm", content_type="audio/webm")
        form.add_field("question_prompt", question_prompt)
        form.add_field("task_type", task_type)
        if user_id:
            form.add_field("user_id", user_id)
        return await self._post(SCORE_TASK_URL, params, form, tag="score-task")

    # ─── public — Writing ──────────────────────────────────────────

    async def score_writing(
        self,
        text: str,
        question_prompt: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Score a piece of written English against IELTS/CEFR rubrics."""
        if not self.api_key:
            return {"success": False, "error": "SPEECHACE_API_KEY not configured"}
        if not (text or "").strip():
            return {"success": False, "error": "Empty text"}
        params = {"key": self.api_key, "dialect": self.dialect}
        form = aiohttp.FormData()
        form.add_field("user_audio_text", text)
        if question_prompt:
            form.add_field("question_prompt", question_prompt)
        if user_id:
            form.add_field("user_id", user_id)
        return await self._post(SCORE_WRITING_URL, params, form, tag="score-writing")

    # ─── normalised IELTS-shaped output ────────────────────────────

    async def score_open_ended_normalised(
        self,
        audio_bytes: bytes,
        relevance_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Same as ``score_open_ended`` but flattens the response into the
        IELTS-style shape the rest of the app already understands.
        """
        result = await self.score_open_ended(audio_bytes, relevance_context=relevance_context)
        if not result.get("success"):
            return result
        return self._normalise(result["data"])

    # ─── internals ─────────────────────────────────────────────────

    async def _post(
        self,
        url: str,
        params: Dict[str, Any],
        form: aiohttp.FormData,
        tag: str,
    ) -> Dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, params=params, data=form) as resp:
                    ct = (resp.headers.get("Content-Type") or "").lower()
                    if "application/json" not in ct:
                        body = await resp.text()
                        logger.error("SpeechAce %s non-JSON %s: %s", tag, resp.status, body[:200])
                        return {"success": False, "error": {"status": resp.status, "body": body[:500]}}
                    data = await resp.json()
                    if resp.status != 200:
                        return {"success": False, "error": data}
                    status_field = (data.get("status") or "").lower()
                    if status_field and status_field != "success":
                        return {
                            "success": False,
                            "error": data.get("detail_message") or data.get("short_message") or "SpeechAce returned non-success",
                            "raw": data,
                        }
                    return {"success": True, "data": data}
        except Exception as e:
            logger.error("SpeechAce %s network error: %s", tag, e)
            return {"success": False, "error": str(e)}

    @staticmethod
    def _extract_transcript(data: Dict[str, Any]) -> str:
        """Pull the user transcript out of either an open-ended or task response."""
        # v9 nests transcript inside text_score / speech_score, depending on plan.
        speech = data.get("speech_score") or {}
        text = data.get("text_score") or {}
        for src in (speech, text, data):
            t = (src.get("transcript") or "").strip() if isinstance(src, dict) else ""
            if t:
                return t
        # Some responses also expose `user_response` or `transcript` at top level
        return (data.get("transcript") or data.get("user_response") or "").strip()

    @staticmethod
    def _normalise(data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten the v9 open-ended response into the shape used elsewhere."""
        speech = data.get("speech_score") or data.get("text_score") or {}
        sa = (speech.get("speechace_score") or {}) if isinstance(speech, dict) else {}
        ielts = (speech.get("ielts_score") or {}) if isinstance(speech, dict) else {}
        cefr = (speech.get("cefr_score") or {}) if isinstance(speech, dict) else {}
        pte = (speech.get("pte_score") or {}) if isinstance(speech, dict) else {}
        toefl = (speech.get("toefl_score") or {}) if isinstance(speech, dict) else {}

        def _sub(score_obj: Dict[str, Any], key: str) -> Optional[float]:
            v = score_obj.get(key) if isinstance(score_obj, dict) else None
            try:
                return float(v) if v is not None else None
            except Exception:
                return None

        # IELTS-shaped band breakdown.
        ielts_overall = _sub(ielts, "overall")
        bands = {
            "fluencyCoherence": {"band": _sub(ielts, "fluency_coherence")},
            "lexicalResource": {"band": _sub(ielts, "vocab")},
            "grammarAccuracy": {"band": _sub(ielts, "grammar")},
            "pronunciation": {"band": _sub(ielts, "pronunciation")},
            "taskResponse": {"band": _sub(ielts, "relevance")},
        }

        transcript = SpeechAcePremiumService._extract_transcript(data)

        # Build user-facing tips from any feedback structures we get back.
        tips: List[str] = []
        for fb in (speech.get("feedback") or [])[:5] if isinstance(speech, dict) else []:
            if isinstance(fb, str) and fb.strip():
                tips.append(fb.strip())
            elif isinstance(fb, dict):
                msg = fb.get("message") or fb.get("text")
                if msg:
                    tips.append(str(msg).strip())

        return {
            "success": True,
            "transcript": transcript,
            "overallScore": _sub(sa, "overall"),
            "pronunciationScore": _sub(sa, "pronunciation"),
            "fluencyScore": _sub(sa, "fluency"),
            "vocabularyScore": _sub(sa, "vocab"),
            "grammarScore": _sub(sa, "grammar"),
            "coherenceScore": _sub(sa, "coherence"),
            "ielts": {
                "overall_band": ielts_overall,
                "ielts_score_estimate": ielts_overall,
                "pte_score_estimate": _sub(pte, "overall"),
                "toefl_score_estimate": _sub(toefl, "overall"),
                "cefr_level": cefr.get("overall") if isinstance(cefr, dict) else None,
                "bands": bands,
            },
            "tips": tips,
            "raw": data,
        }
