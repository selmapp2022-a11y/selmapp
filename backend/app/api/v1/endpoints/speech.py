import struct
import io

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_db, get_current_user
from app.schemas.speech import SpeechEvaluateResponse
from app.services.asr_service import GoogleSTTService
from app.services.speaking_eval_service import SpeakingEvaluationService

router = APIRouter()


async def _generate_ielts_feedback(transcript: str, task_prompt: str, pronunciation_score: float) -> Optional[dict]:
    """Run a Gemini IELTS-style assessment over the user's transcript.

    Returns a dict with `tips` (list[str]), `bands` (dict of the four IELTS
    sub-skills with band 0-9), and `overall_score` (0-100), or ``None`` if
    Gemini is unavailable. Errors propagate to the caller.
    """
    import json as _json
    import google.generativeai as genai
    from app.core.config import settings as _settings
    if not getattr(_settings, "GOOGLE_GEMINI_API_KEY", None):
        return None
    genai.configure(api_key=_settings.GOOGLE_GEMINI_API_KEY)
    model = genai.GenerativeModel(
        getattr(_settings, "GEMINI_TEXT_MODEL_REASON", _settings.GEMINI_MODEL)
    )
    task_block = f'\n        TASK GIVEN:\n        "{task_prompt.strip()}"' if task_prompt and task_prompt.strip() else ""
    prompt_text = f"""You are an IELTS Speaking examiner. The candidate just gave the following spoken response (auto-transcribed){task_block}

CANDIDATE TRANSCRIPT:
\"\"\"
{transcript}
\"\"\"

Score the response on the four official IELTS Speaking criteria using the 0-9 band scale.
Be specific — quote the candidate's exact words when pointing out errors or strengths.

Return ONLY valid JSON (no markdown, no commentary):
{{
  "fluency_coherence": {{"band": 6.0, "comment": "..."}},
  "lexical_resource": {{"band": 5.5, "comment": "..."}},
  "grammar_accuracy": {{"band": 6.0, "comment": "..."}},
  "task_response": {{"band": 6.5, "comment": "How well they addressed the task"}},
  "overall_band": 6.0,
  "tips": [
    "Specific actionable tip quoting an exact phrase the candidate used",
    "Another concrete tip"
  ]
}}
"""
    import asyncio as _asyncio
    loop = _asyncio.get_event_loop()
    response = await loop.run_in_executor(None, model.generate_content, prompt_text)
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0]
    try:
        data = _json.loads(raw)
    except Exception:
        return None
    bands = {
        "fluencyCoherence": data.get("fluency_coherence"),
        "lexicalResource": data.get("lexical_resource"),
        "grammarAccuracy": data.get("grammar_accuracy"),
        "taskResponse": data.get("task_response"),
    }
    overall_band = data.get("overall_band")
    overall_score = round(float(overall_band) * 10) if overall_band else None
    return {
        "tips": data.get("tips") or [],
        "bands": bands,
        "overall_score": overall_score,
    }


def estimate_audio_duration_ms(audio_bytes: bytes) -> int:
    """Estimate audio duration from WAV file headers or file size."""
    try:
        # Try to parse WAV header
        if audio_bytes[:4] == b'RIFF':
            # WAV file - parse header for duration
            # Bytes 24-28: sample rate
            # Bytes 28-32: byte rate
            # Bytes 40-44: data size (for PCM)
            sample_rate = struct.unpack('<I', audio_bytes[24:28])[0]
            byte_rate = struct.unpack('<I', audio_bytes[28:32])[0]
            # Find data chunk size
            data_pos = audio_bytes.find(b'data')
            if data_pos > 0 and len(audio_bytes) > data_pos + 8:
                data_size = struct.unpack('<I', audio_bytes[data_pos + 4:data_pos + 8])[0]
                if byte_rate > 0:
                    duration_seconds = data_size / byte_rate
                    return int(duration_seconds * 1000)
        
        # Fallback: estimate based on common audio parameters (16kHz, 16-bit, mono)
        # Rough estimate: ~32 bytes per ms for 16kHz 16-bit mono
        estimated_ms = len(audio_bytes) // 32
        return max(1000, min(estimated_ms, 60000))  # Clamp between 1-60 seconds
        
    except Exception:
        # Default to file size estimation
        return max(1000, len(audio_bytes) // 32)


@router.post("/evaluate", response_model=SpeechEvaluateResponse)
async def evaluate_speech(
    reference_text: str = Form(...),
    language: str = Form("en-US"),
    audio: UploadFile = File(...),
    mode: str = Form("read"),  # "read" (default, pronunciation-focused) or "ielts" (free-form, full IELTS-style feedback)
    prompt: str = Form(""),  # When mode=ielts, the topic the user was asked to talk about
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file")

        # Estimate duration from audio file (fallback if STT doesn't provide it)
        estimated_duration_ms = estimate_audio_duration_ms(audio_bytes)

        # 1) Transcribe (best-effort). If STT fails, proceed with Speechace only.
        transcript_text = ""
        words = []
        duration_ms = 0
        stt_available = False
        try:
            stt = GoogleSTTService()
            stt_result = await stt.transcribe(audio_bytes, language_code=language)
            if stt_result.get("success"):
                stt_available = True
                transcript_text = stt_result.get("text", "") or ""
                words = stt_result.get("words", []) or []
                # estimate duration from words if possible
                if words:
                    starts = [w.get("startMs") for w in words if w.get("startMs") is not None]
                    ends = [w.get("endMs") for w in words if w.get("endMs") is not None]
                    if starts and ends:
                        duration_ms = max(ends) - min(starts)
        except Exception:
            # Do not fail the request on STT errors; Speechace can assess directly from audio
            pass
        
        # Use estimated duration if STT didn't provide it
        if duration_ms == 0:
            duration_ms = estimated_duration_ms

        # 2) Evaluate with Speechace (prioritized) or Gemini (fallback)
        evaluator = SpeakingEvaluationService()
        result = await evaluator.evaluate(
            reference_text=reference_text,
            transcript_text=transcript_text,
            transcript_words=words,
            duration_ms=duration_ms,
            audio_bytes=audio_bytes,  # Pass audio for Speechace assessment
            user_id=str(current_user.id) if current_user else None,
        )

        # 3) Shape to response model (camelCase, required fields)
        
        # Get pronunciation issues from Speechace detailed feedback
        pronunciation_issues = result.get("pronunciation_issues") or []
        detailed_word_feedback = result.get("detailed_word_feedback") or []
        
        # Calculate estimated word count for WPM (pronunciation-only plans don't provide fluency)
        word_count = len(detailed_word_feedback) if detailed_word_feedback else 0
        estimated_wpm = (word_count / (duration_ms / 60000)) if duration_ms > 0 else 0.0
        
        # Build accuracy from word scores (pronunciation-only plans use word quality)
        word_scores_dict = result.get("word_scores") or {}
        correct_words = sum(1 for score in word_scores_dict.values() if score >= 70)
        total_words = len(word_scores_dict)
        wer = 1.0 - (correct_words / total_words) if total_words > 0 else 0.0
        
        resp = {
            "overallScore": result.get("overallScore")
                or result.get("overall_score")
                or result.get("quality_score", {}).get("overall", 0.0) * 100,
            "pronunciationScore": result.get("pronunciation_score") or 0.0,
            "fluencyScore": result.get("fluency_score") or estimated_wpm,  # Use WPM as proxy for fluency display
            "accuracy": result.get("accuracy") or {
                "wer": wer,
                "correct": correct_words,
                "insertions": 0,
                "deletions": 0,
                "substitutions": total_words - correct_words,
            },
            "pronunciation": {
                "issues": pronunciation_issues,
                "score": result.get("pronunciation_score", 0.0),
            },
            "fluency": result.get("fluency") or {
                "wpm": estimated_wpm,
                "avgPauseMs": None,
                "longPauses": [],
            },
            "timing": result.get("timing") or {"durationMs": duration_ms},
            "transcript": result.get("transcript") or {
                # Only show actual transcript if STT was successful, otherwise indicate it's the reference
                "text": transcript_text if stt_available and transcript_text else "",
                "words": words if stt_available else [],
                "isReference": not stt_available,  # Flag to indicate transcript unavailable
                "referenceText": reference_text,  # Always include reference for comparison
            },
            "tips": result.get("tips")
                or result.get("suggestions")
                or ([result.get("feedback")] if result.get("feedback") else []),
            "wordScores": word_scores_dict,
            "detailedWordFeedback": detailed_word_feedback,  # Words from reference with pronunciation scores
            "phonemeScores": result.get("phoneme_scores") or {},
            "scoringType": "text",  # Indicate this is text scoring (comparing against reference)
        }

        # IELTS-style enhancement. When the client requests mode="ielts",
        # SpeechAce alone only returns pronunciation/fluency. IELTS scoring
        # additionally needs Lexical Resource, Grammatical Range & Accuracy,
        # and Task Response. Run the transcript through Gemini for those
        # bands and merge richer tips/scores into the response.
        if mode == "ielts" and transcript_text:
            try:
                ielts_extras = await _generate_ielts_feedback(
                    transcript=transcript_text,
                    task_prompt=prompt,
                    pronunciation_score=resp["pronunciationScore"],
                )
                if ielts_extras:
                    extra_tips = ielts_extras.get("tips") or []
                    resp["tips"] = list(resp.get("tips") or []) + extra_tips
                    resp["ielts"] = ielts_extras.get("bands")
                    if ielts_extras.get("overall_score"):
                        resp["overallScore"] = ielts_extras["overall_score"]
            except Exception as e:
                resp.setdefault("tips", []).append(
                    f"(IELTS expanded feedback unavailable: {type(e).__name__})"
                )

        return resp

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



