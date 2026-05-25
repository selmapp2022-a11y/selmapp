import json
import logging
from typing import Any, Dict, List, Optional

import google.generativeai as genai

from app.core.config import settings
from app.services.speaking_metrics import compute_alignment, compute_fluency
from app.services.speechace_service import SpeechaceService

logger = logging.getLogger(__name__)


class SpeakingEvaluationService:
    def __init__(self):
        # Initialize Gemini
        api_key = getattr(settings, 'GOOGLE_GEMINI_API_KEY', None)
        if not api_key:
            logger.warning("GOOGLE_GEMINI_API_KEY is not configured; Gemini eval disabled")
            self.model = None
        else:
            genai.configure(api_key=api_key)
            model_name = getattr(settings, 'GEMINI_TEXT_MODEL_REASON', getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-pro'))
            self.model = genai.GenerativeModel(model_name)

        # Initialize Speechace
        self.speechace_service = SpeechaceService()
        self.use_speechace = bool(getattr(settings, 'SPEECHACE_API_KEY', None))

    async def evaluate(
        self,
        reference_text: str,
        transcript_text: str,
        transcript_words: List[Dict[str, Any]],
        duration_ms: int,
        audio_bytes: Optional[bytes] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Basic metrics
        acc = compute_alignment(reference_text, transcript_text)
        flu = compute_fluency(transcript_words)

        # Try Speechace first if audio is available and service is configured
        if audio_bytes and self.use_speechace:
            speechace_result = await self.speechace_service.assess_pronunciation(
                audio_bytes=audio_bytes,
                reference_text=reference_text,
                user_id=user_id
            )

            if speechace_result["success"]:
                assessment = speechace_result["assessment"]
                # Enhance with additional metrics from STT
                assessment["accuracy"] = acc
                assessment["fluency"] = flu
                assessment["timing"] = {"durationMs": duration_ms}
                assessment["transcript"] = {
                    "text": transcript_text,
                    "words": transcript_words
                }
                return assessment

            logger.warning(f"Speechace assessment failed: {speechace_result.get('error')}, falling back to Gemini")

        # Fallback to Gemini evaluation
        prompt = self._build_prompt(reference_text, transcript_text, acc, flu)

        if not self.model:
            # Fallback simple scoring
            overall = max(0.0, 100.0 - acc["wer"] * 100)

            return {
                "overallScore": overall,
                "accuracy": acc,
                "pronunciation": {"issues": []},
                "fluency": flu,
                "timing": {"durationMs": duration_ms},
                "transcript": {"text": transcript_text, "words": transcript_words},
                "tips": [
                    "Focus on matching the reference text closely.",
                    "Maintain a steady pace and reduce long pauses.",
                ],
            }

        # Ask Gemini to produce structured JSON
        schema = {
            "type": "object",
            "properties": {
                "overallScore": {"type": "number"},
                "accuracy": {
                    "type": "object",
                    "properties": {
                        "wer": {"type": "number"},
                        "correct": {"type": "integer"},
                        "insertions": {"type": "integer"},
                        "deletions": {"type": "integer"},
                        "substitutions": {"type": "integer"},
                    },
                    "required": ["wer", "correct", "insertions", "deletions", "substitutions"],
                },
                "pronunciation": {
                    "type": "object",
                    "properties": {
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "word": {"type": "string"},
                                    "issue": {"type": "string"},
                                    "suggestion": {"type": "string"},
                                },
                                "required": ["word", "issue"],
                            },
                        }
                    },
                    "required": ["issues"],
                },
                "fluency": {
                    "type": "object",
                    "properties": {
                        "wpm": {"type": "number"},
                        "avgPauseMs": {"type": "number"},
                        "longPauses": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"start": {"type": "integer"}, "end": {"type": "integer"}},
                                "required": ["start", "end"],
                            },
                        },
                    },
                    "required": ["wpm", "longPauses"],
                },
                "timing": {
                    "type": "object",
                    "properties": {"durationMs": {"type": "integer"}},
                    "required": ["durationMs"],
                },
                "transcript": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "words": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "word": {"type": "string"},
                                    "startMs": {"type": "integer"},
                                    "endMs": {"type": "integer"},
                                    "confidence": {"type": "number"},
                                },
                                "required": ["word"],
                            },
                        },
                    },
                    "required": ["text"],
                },
                "tips": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["overallScore", "accuracy", "pronunciation", "fluency", "timing", "transcript", "tips"],
        }

        try:
            response = self.model.generate_content(
            [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "application/json", "data": json.dumps({
                            "reference": reference_text,
                            "transcript": transcript_text,
                            "alignment": acc,
                            "fluency": flu,
                            "words": transcript_words,
                            "durationMs": duration_ms,
                        }).encode("utf-8")}},
                    ],
                }
            ],
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=schema,
                max_output_tokens=512,
            ),
        )

            # SDK returns .text for JSON when response_mime_type is application/json
            obj = json.loads(response.text)
        except Exception:
            # Fallback: basic
            overall = max(0.0, 100.0 - acc["wer"] * 100)
            obj = {
                "overallScore": overall,
                "accuracy": acc,
                "pronunciation": {"issues": []},
                "fluency": flu,
                "timing": {"durationMs": duration_ms},
                "transcript": {"text": transcript_text, "words": transcript_words},
                "tips": [
                    "Focus on matching the reference text closely.",
                    "Maintain a steady pace and reduce long pauses.",
                ],
            }

        return obj

    def _build_prompt(self, reference: str, transcript: str, acc: Dict[str, Any], flu: Dict[str, Any]) -> str:
        return (
            "You are an English speaking coach. Given the reference text and the user's transcript, "
            "analyze correctness, pronunciation issues, and fluency. Use the provided alignment and fluency metrics. "
            "Return a compact JSON that matches the provided response schema. Keep tips short and actionable."
        )



