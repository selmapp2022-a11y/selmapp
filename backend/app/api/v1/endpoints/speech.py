import struct
import io

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.api.deps import get_db, get_current_user
from app.schemas.speech import SpeechEvaluateResponse
from app.services.asr_service import GoogleSTTService
from app.services.speaking_eval_service import SpeakingEvaluationService

router = APIRouter()


# The dialects the speech path serves. Unlike the writing endpoint — which
# accepts four and *serves* two, because SpeechAce refuses French for written
# expression — the speech endpoint genuinely serves all four.
#
# Validated rather than passed through, for the reason step 06 established on
# the writing side: an unsupported value reaches the vendor, the vendor
# refuses, our 503 is replaced by the platform gateway's own error page, and
# the candidate sees an opaque 504. A 422 with the list in it is readable.
ALLOWED_SPEECH_DIALECTS = {"en-us", "en-gb", "fr-fr", "fr-ca"}


# _generate_ielts_feedback was removed on 2026-08-25.
#
# It was a Gemini IELTS-Speaking examiner with no call site anywhere in
# app/. Nothing a user has ever seen came from it. The `ielts` block the
# speaking endpoint returns is built by SpeechAcePremiumService._normalise.
#
# It is deleted rather than kept "for later" because dead scoring code is
# not free: it carried a wrong criterion mapping (Task Response, a writing
# criterion, in place of Pronunciation) for months, and it was read twice
# during step 03 as though it were live. The body is in git history at
# d55f9e1 if a transcript-based speaking judge is ever wanted.


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


@router.post("/evaluate")
async def evaluate_speech(
    reference_text: str = Form(...),
    language: str = Form("en-US"),
    audio: UploadFile = File(...),
    mode: str = Form("read"),  # "read" (default, pronunciation-focused) or "ielts" (free-form, full IELTS-style feedback)
    prompt: str = Form(""),  # When mode=ielts, the topic the user was asked to talk about
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # `language` is the exam definition's locale, sent by the exam runner. It
    # decides the acoustic model the response is scored against, so it is not
    # a presentation detail: a Quebec speaker scored at en-us is being marked
    # on the wrong instrument, and until 2026-08-26 every one of them was.
    dialect = (language or "").strip().lower()
    if dialect not in ALLOWED_SPEECH_DIALECTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "unsupported_dialect",
                "message": (
                    f"The speech scorer does not serve '{language}'. "
                    "The dialect comes from the exam definition's locale."
                ),
                "requested": language,
                "allowed": sorted(ALLOWED_SPEECH_DIALECTS),
            },
        )

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
            # STT chain — ElevenLabs Scribe first (confirmed working for
            # this account), SpeechAce Premium open-ended second (only
            # available on Premium plans), Google STT last (currently
            # disabled in this GCP project but kept for future).
            from app.services.elevenlabs_asr_service import ElevenLabsASRService
            from app.services.speechace_premium_service import SpeechAcePremiumService
            stt: Any = ElevenLabsASRService()
            stt_result = await stt.transcribe(audio_bytes, language_code=language)
            if not stt_result.get("success") or not (stt_result.get("text") or "").strip():
                stt = SpeechAcePremiumService()
                stt_result = await stt.transcribe(audio_bytes, language_code=language)
            if not stt_result.get("success") or not (stt_result.get("text") or "").strip():
                stt = GoogleSTTService()
                stt_result = await stt.transcribe(audio_bytes, language_code=language)
            if stt_result.get("success"):
                stt_available = True
                transcript_text = stt_result.get("text", "") or ""
                words = stt_result.get("words", []) or []
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
            dialect=dialect,
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

        # IELTS-style enhancement. SpeechAce Premium open-ended returns IELTS
        # bands, CEFR, PTE/TOEFL estimates and per-skill scores in a single
        # call — no need for a separate vendor. We send the user's prompt as
        # `relevance_context` so SpeechAce can grade Task Response too.
        if mode == "ielts":
            try:
                from app.services.speechace_premium_service import SpeechAcePremiumService
                sa_full = await SpeechAcePremiumService().score_open_ended_normalised(
                    audio_bytes,
                    relevance_context=prompt or None,
                )
                if sa_full.get("success"):
                    extra_tips = sa_full.get("tips") or []
                    resp["tips"] = list(resp.get("tips") or []) + extra_tips
                    resp["ielts"] = sa_full.get("ielts")
                    overall_score = sa_full.get("overallScore")
                    if overall_score is not None:
                        resp["overallScore"] = overall_score
                    if sa_full.get("transcript"):
                        resp["transcript"]["text"] = resp["transcript"].get("text") or sa_full["transcript"]
            except Exception as e:
                resp.setdefault("tips", []).append(
                    f"(IELTS expanded feedback unavailable: {type(e).__name__})"
                )

        return resp

    except HTTPException:
        raise
    except Exception as e:
        # Don't 500 the client — return a minimal scaffold response with the
        # error in tips so the UI can render *something* and we still see what
        # broke. Speaking is a critical path; an outage here would silently
        # block all of Speaking and IELTS.
        import logging as _logging
        _logging.getLogger(__name__).exception("speech/evaluate failed")
        return {
            "overallScore": 0,
            "pronunciationScore": 0,
            "fluencyScore": 0,
            "accuracy": {"wer": 1.0, "correct": 0, "insertions": 0, "deletions": 0, "substitutions": 0},
            "pronunciation": {"issues": [], "score": 0},
            "fluency": {"wpm": 0, "avgPauseMs": None, "longPauses": []},
            "timing": {"durationMs": 0},
            "transcript": {"text": "", "words": [], "isReference": True, "referenceText": reference_text},
            "tips": [
                f"We couldn't score this attempt ({type(e).__name__}). Please try again.",
            ],
            "wordScores": {},
            "detailedWordFeedback": [],
            "phonemeScores": {},
            "scoringType": "error",
        }



