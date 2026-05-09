"""
ELSA Unscripted Speech API service.

A single call to ``POST https://api.elsanow.io/api/v2/score_audio`` returns
everything we need for free-form speaking practice:

- ``transcript`` (so this can replace Google STT / ElevenLabs Scribe)
- ``other_scores.ielts_score`` (IELTS Speaking band, no Gemini detour)
- per-skill scores: pronunciation, intonation, fluency, grammar, vocabulary
- CEFR estimates for each
- top phoneme errors with examples
- grammar items with `original` / `suggestion`
- vocabulary upgrade suggestions

Two convenience wrappers are exposed:

- ``transcribe(audio_bytes)`` — drop-in for ``GoogleSTTService.transcribe``
  (returns ``{success, text, confidence, words}``).
- ``score(audio_bytes)`` — full structured assessment for IELTS / Live
  Conversation feedback panels.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)

ELSA_SCORE_URL = "https://api.elsanow.io/api/v2/score_audio"
ELSA_TIMEOUT_SECONDS = 60.0  # ELSA can take a moment for premium analysis


class ELSAUnscriptedService:
    """ELSA Unscripted Speech API client (free-form speech assessment)."""

    def __init__(self) -> None:
        self.api_key: Optional[str] = getattr(settings, "ELSA_API_KEY", None)

    # ─── public API ───────────────────────────────────────────────────

    async def transcribe(self, audio_bytes: bytes, language_code: str = "en-US") -> Dict[str, Any]:
        """STT-only wrapper — same shape as ``GoogleSTTService.transcribe``."""
        del language_code  # ELSA only does English; keep arg for signature parity
        result = await self._call(audio_bytes, api_plan="premium")
        if not result.get("success"):
            return {"success": False, "error": result.get("error")}
        data = result["data"]
        text = (data.get("transcript") or "").strip()
        # ELSA doesn't return per-word confidence in the unscripted top level,
        # so we synthesize one from the success of transcription.
        return {
            "success": True,
            "text": text,
            "confidence": 0.95 if text else 0.0,
            "words": [],
        }

    async def score(self, audio_bytes: bytes, api_plan: str = "premium") -> Dict[str, Any]:
        """Full assessment — transcript + scores + IELTS band + feedback."""
        result = await self._call(audio_bytes, api_plan=api_plan)
        if not result.get("success"):
            return {"success": False, "error": result.get("error")}
        return self._normalize(result["data"])

    # ─── internals ────────────────────────────────────────────────────

    async def _call(self, audio_bytes: bytes, api_plan: str) -> Dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "ELSA_API_KEY not configured"}
        if not audio_bytes:
            return {"success": False, "error": "Empty audio"}

        form = aiohttp.FormData()
        form.add_field("api_plan", api_plan)
        # Tell ELSA to return grammar/vocab even on shorter samples — the
        # threshold-policed scores are noisier but at least they exist.
        form.add_field("force_grammar_vocab", "True")
        # Browser MediaRecorder yields webm; ELSA accepts that natively.
        form.add_field(
            "audio_file",
            audio_bytes,
            filename="recording.webm",
            content_type="audio/webm",
        )
        headers = {"Authorization": f"ELSA {self.api_key}"}

        timeout = aiohttp.ClientTimeout(total=ELSA_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(ELSA_SCORE_URL, headers=headers, data=form) as resp:
                    ct = (resp.headers.get("Content-Type") or "").lower()
                    if "application/json" not in ct:
                        body = await resp.text()
                        return {"success": False, "error": {"status": resp.status, "body": body[:500]}}
                    data = await resp.json()
                    if resp.status != 200:
                        return {"success": False, "error": data}
                    if not data.get("success", True):
                        return {"success": False, "error": data.get("message") or data}
                    return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"ELSA API network error: {e}")
            return {"success": False, "error": str(e)}

    def _normalize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten the nested ELSA response into the shape the rest of the
        app already understands (overall score 0-100, per-skill scores, tips,
        IELTS bands, transcript). Keeps callers stable."""
        speakers: List[Dict[str, Any]] = data.get("speakers") or []
        sp = speakers[0] if speakers else {}
        metrics = sp.get("metrics") or {}
        general = metrics.get("general_scores") or {}
        elsa = general.get("elsa") or {}
        cefr = general.get("cefr") or {}
        other_scores = general.get("other_scores") or {}
        feedbacks = sp.get("feedbacks") or {}
        fluency_metrics = (metrics.get("other_metrics") or {}).get("fluency") or {}

        # IELTS bands per sub-skill (0-9). Map ELSA's percentage scores into
        # rough IELTS bands so the IELTS UI can show the four-band breakdown.
        def to_band(percent: Optional[float]) -> Optional[float]:
            if percent is None:
                return None
            try:
                p = float(percent)
            except Exception:
                return None
            return round(min(9.0, max(0.0, p / 100.0 * 9.0)), 1)

        bands = {
            "fluencyCoherence": {"band": to_band(elsa.get("fluency_score")), "comment": elsa.get("fluency_decision")},
            "lexicalResource": {"band": to_band(elsa.get("vocabulary_score")), "comment": elsa.get("vocabulary_decision")},
            "grammarAccuracy": {"band": to_band(elsa.get("grammar_score")), "comment": elsa.get("grammar_decision")},
            "taskResponse": {"band": to_band(elsa.get("eps_score")), "comment": elsa.get("eps_decision")},
            "pronunciation": {"band": to_band(elsa.get("pronunciation_score")), "comment": elsa.get("pronunciation_decision")},
        }

        tips: List[str] = []
        # Build human tips from grammar items + vocabulary suggestions
        for g in (feedbacks.get("grammar") or {}).get("items", [])[:5]:
            orig = g.get("original")
            sugg = g.get("suggestion")
            if orig and sugg:
                tips.append(f"Try '{sugg}' instead of '{orig}'.")
        for v in (feedbacks.get("vocabulary") or {}).get("low_level_words", [])[:3]:
            word = v.get("word")
            sugs = v.get("suggestions") or []
            if word and sugs:
                pick = sugs[0].get("word") if isinstance(sugs[0], dict) else sugs[0]
                if pick:
                    tips.append(f"'{word}' is basic — '{pick}' would sound more advanced.")
        for p in (feedbacks.get("pronunciation") or {}).get("top_errors", [])[:2]:
            phoneme = p.get("phoneme")
            if phoneme:
                examples = []
                for err in p.get("errors", []):
                    for ex in err.get("examples", []):
                        if ex.get("text"):
                            examples.append(ex["text"])
                if examples:
                    tips.append(f"Practise the /{phoneme}/ sound in: {', '.join(examples[:3])}.")

        return {
            "success": True,
            "transcript": data.get("transcript", ""),
            "overallScore": elsa.get("eps_score"),
            "pronunciationScore": elsa.get("pronunciation_score"),
            "fluencyScore": elsa.get("fluency_score"),
            "intonationScore": elsa.get("intonation_score"),
            "grammarScore": elsa.get("grammar_score"),
            "vocabularyScore": elsa.get("vocabulary_score"),
            "cefr": cefr,
            "ielts": {
                "overall_band": to_band(elsa.get("eps_score")),
                "ielts_score_estimate": other_scores.get("ielts_score"),
                "toefl_score_estimate": other_scores.get("toefl_score"),
                "pte_score_estimate": other_scores.get("pte_score"),
                "bands": bands,
            },
            "fluency": {
                "wpm": fluency_metrics.get("words_per_minute"),
                "wpm_min": fluency_metrics.get("words_per_minute_min"),
                "wpm_max": fluency_metrics.get("words_per_minute_max"),
                "pausing_score": fluency_metrics.get("pausing_score"),
            },
            "grammar_items": (feedbacks.get("grammar") or {}).get("items", []),
            "vocabulary_suggestions": (feedbacks.get("vocabulary") or {}).get("low_level_words", []),
            "pronunciation_top_errors": (feedbacks.get("pronunciation") or {}).get("top_errors", []),
            "tips": tips,
            "raw": data,
        }
