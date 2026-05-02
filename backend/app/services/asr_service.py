import asyncio
import base64
import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class GoogleSTTService:
    """
    Thin wrapper around Google Speech-to-Text (v2) to obtain transcript with
    word-level timestamps and confidences.

    Note: Uses REST call via googleapis if client not installed. Expects audio bytes (WAV 16k mono).
    """

    def __init__(self):
        self.project_id = getattr(settings, "GCP_PROJECT_ID", None)
        self.location = getattr(settings, "GCP_LOCATION", "global")
        # Prefer a dedicated Google Cloud API key if provided
        self.api_key = getattr(settings, "GOOGLE_CLOUD_API_KEY", None) or getattr(settings, "GOOGLE_GEMINI_API_KEY", None)

    async def transcribe(self, audio_bytes: bytes, language_code: str = "en-US") -> Dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "Missing GOOGLE_GEMINI_API_KEY for STT REST call"}

        try:
            import aiohttp

            url = (
                f"https://speech.googleapis.com/v2/projects/-/locations/{self.location}:recognize"
            )

            req = {
                "config": {
                    "autoDecodingConfig": {},
                    "languageCodes": [language_code],
                    "features": {
                        "enableWordTimeOffsets": True,
                        "enableAutomaticPunctuation": True,
                    },
                },
                "content": base64.b64encode(audio_bytes).decode("utf-8"),
            }

            headers = {"Content-Type": "application/json", "X-Goog-Api-Key": self.api_key}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=json.dumps(req)) as resp:
                    ct = (resp.headers.get("Content-Type") or "").lower()
                    if "application/json" in ct:
                        data = await resp.json()
                    else:
                        # Non-JSON error (e.g., HTML) → capture text and return gracefully
                        text = await resp.text()
                        return {"success": False, "error": {"status": resp.status, "body": text[:500]}}
                    if resp.status != 200:
                        return {"success": False, "error": data}

            # Parse v2 response
            transcript_text = ""
            words: List[Dict[str, Any]] = []
            confidence = 0.0

            results = data.get("results", [])
            if results:
                alt = results[0].get("alternatives", [{}])[0]
                transcript_text = alt.get("transcript", "")
                confidence = alt.get("confidence", 0.0)
                for w in alt.get("words", []):
                    start = self._to_ms(w.get("startOffset"))
                    end = self._to_ms(w.get("endOffset"))
                    words.append(
                        {
                            "word": w.get("word", ""),
                            "startMs": start,
                            "endMs": end,
                            "confidence": w.get("confidence", None),
                        }
                    )

            return {
                "success": True,
                "text": transcript_text,
                "confidence": confidence,
                "words": words,
                "raw": data,
            }

        except Exception as e:
            logger.error(f"STT v2 transcription error: {e}")
            return {"success": False, "error": str(e)}

    def _to_ms(self, offset: Optional[str]) -> Optional[int]:
        if not offset:
            return None
        # v2 returns duration like "1.234s"
        try:
            if offset.endswith("s"):
                seconds = float(offset[:-1])
                return int(seconds * 1000)
        except Exception:
            return None
        return None


