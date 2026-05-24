import struct
import io

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Optional

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


# ── IELTS Speaking Part 3 — abstract multi-turn discussion ───────────────
# Part 3 is the 4-5 minute exchange that follows the Part 2 cue-card
# answer. The examiner asks 4-5 open-ended discussion questions about
# the underlying topic, expecting the candidate to extend, justify, and
# discuss abstract ideas. We expose this as two endpoints that the iPhone
# can drive turn-by-turn while staying stateless on the server (the client
# holds the conversation history and sends it back for final scoring).
#   POST /speech/ielts/part3/generate-questions
#     -> {questions: [q1..q5]}
#   POST /speech/ielts/part3/score-discussion
#     -> {bands, overall_band, tips, turn_feedback}
# Each individual turn is still transcribed via the existing
# /speech/evaluate endpoint with mode="ielts"; this just adds the
# question-generation + final-scoring pieces specific to Part 3.
# (2026-05-25 — finding #5 from the 2026-05-24 audit.)

from pydantic import BaseModel as _BaseModel, Field as _Field


class _Part3QuestionsRequest(_BaseModel):
    part2_topic: str = _Field(
        ...,
        min_length=4,
        description=(
            "The Part 2 cue-card topic the candidate just discussed, "
            "e.g. 'describe a memorable journey you have taken'."
        ),
    )
    count: int = _Field(
        default=5,
        ge=3,
        le=6,
        description="How many Part 3 follow-up questions to generate.",
    )


class _Part3Turn(_BaseModel):
    question: str
    transcript: str


class _Part3ScoreRequest(_BaseModel):
    part2_topic: str = _Field(..., min_length=4)
    turns: list = _Field(
        ...,
        description=(
            "Ordered list of {question, transcript} pairs covering "
            "every Part 3 turn the candidate completed."
        ),
    )


@router.post("/ielts/part3/generate-questions")
async def ielts_part3_generate_questions(
    request: _Part3QuestionsRequest,
    current_user = Depends(get_current_user),
):
    """Generate IELTS Speaking Part 3 follow-up questions tied to the
    Part 2 cue-card topic. Static fallback questions are returned if
    Gemini is unreachable, so the iPhone never sees an empty list."""
    import json as _json
    import asyncio as _asyncio
    import google.generativeai as genai
    from app.core.config import settings as _settings

    questions: list = []
    if getattr(_settings, "GOOGLE_GEMINI_API_KEY", None):
        try:
            genai.configure(api_key=_settings.GOOGLE_GEMINI_API_KEY)
            model = genai.GenerativeModel(
                getattr(_settings, "GEMINI_TEXT_MODEL_REASON", _settings.GEMINI_MODEL)
            )
            prompt = (
                "You are an IELTS Speaking examiner running Part 3.\n"
                f"The candidate just completed Part 2 on the topic:\n"
                f"  \"{request.part2_topic}\"\n\n"
                "Generate exactly "
                f"{request.count} Part 3 follow-up questions that:\n"
                "  - move from the personal experience of Part 2 to ABSTRACT, "
                "general, or speculative discussion of the same theme;\n"
                "  - probe opinions, cause-and-effect, comparisons across "
                "cultures or time, and predictions about the future;\n"
                "  - escalate in difficulty (easier first, harder last);\n"
                "  - are answerable in 30-60 seconds each.\n\n"
                "Reply ONLY with valid JSON of this exact shape:\n"
                '{\n  "questions": ["...", "...", "..."]\n}'
            )
            loop = _asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, model.generate_content, prompt
            )
            raw = (getattr(response, "text", "") or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                raw = raw.rsplit("```", 1)[0]
            try:
                data = _json.loads(raw)
            except Exception:
                import re as _re
                m = _re.search(r"\{[\s\S]*\}", raw)
                data = _json.loads(m.group(0)) if m else {}
            questions = [
                str(q).strip()
                for q in (data.get("questions") or [])
                if str(q).strip()
            ]
        except Exception:
            questions = []

    if not questions:
        # Generic Part 3-style fallback covering the four classic angles.
        questions = [
            f"In general, why do you think people are interested in {request.part2_topic.lower()}?",
            "How has this changed compared to your parents' generation?",
            "Do you think technology has made this easier or harder, and why?",
            "What might it look like 20 years from now?",
            "Are there any disadvantages or risks people often overlook?",
        ][: request.count]

    return {
        "success": True,
        "part2_topic": request.part2_topic,
        "questions": questions,
        "total_questions": len(questions),
        "guidance": (
            "Speak for 30-60 seconds per question. Extend, justify and "
            "give examples — Part 3 rewards depth over brevity."
        ),
    }


@router.post("/ielts/part3/score-discussion")
async def ielts_part3_score_discussion(
    request: _Part3ScoreRequest,
    current_user = Depends(get_current_user),
):
    """Score an entire IELTS Speaking Part 3 discussion using the
    official IELTS band descriptors, weighted for Part 3's emphasis on
    extending, justifying and discussing abstract ideas across turns.
    """
    import json as _json
    import asyncio as _asyncio
    import google.generativeai as genai
    from app.core.config import settings as _settings

    # Normalise turns input (list of dicts or list of pydantic-validated).
    norm_turns = []
    for t in request.turns or []:
        if isinstance(t, dict):
            q = str(t.get("question") or "").strip()
            tr = str(t.get("transcript") or "").strip()
        else:
            q = str(getattr(t, "question", "")).strip()
            tr = str(getattr(t, "transcript", "")).strip()
        if q and tr:
            norm_turns.append({"question": q, "transcript": tr})

    if not norm_turns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one turn with question + transcript is required.",
        )

    if not getattr(_settings, "GOOGLE_GEMINI_API_KEY", None):
        # Without Gemini we can't score holistically; return a stub so the
        # client still gets a parseable response.
        return {
            "success": False,
            "error": "Scoring unavailable: GOOGLE_GEMINI_API_KEY not configured",
            "bands": {
                "fluencyCoherence": None,
                "lexicalResource": None,
                "grammarAccuracy": None,
                "taskResponse": None,
            },
            "overall_band": None,
            "tips": [],
            "turn_feedback": [],
        }

    transcript_block = "\n\n".join(
        f"Q{i + 1}: {t['question']}\nA{i + 1}: {t['transcript']}"
        for i, t in enumerate(norm_turns)
    )
    prompt = (
        "You are an IELTS Speaking examiner scoring Part 3. The candidate "
        f"just completed {len(norm_turns)} turns of abstract discussion "
        f"about the Part 2 topic:\n  \"{request.part2_topic}\"\n\n"
        "Part 3 specifically rewards:\n"
        "  - extending answers beyond yes/no;\n"
        "  - justifying opinions with reasons and examples;\n"
        "  - discussing abstract / general / speculative ideas;\n"
        "  - using a range of cohesive devices.\n\n"
        "Full discussion transcript (auto-transcribed):\n\n"
        f"{transcript_block}\n\n"
        "Score using the four official IELTS Speaking criteria on the "
        "0-9 band scale. For each turn, give one short concrete tip "
        "quoting an exact phrase the candidate used (or didn't).\n\n"
        "Reply ONLY with valid JSON of this exact shape:\n"
        "{\n"
        '  "fluency_coherence": {"band": 6.0, "comment": "..."},\n'
        '  "lexical_resource":  {"band": 6.0, "comment": "..."},\n'
        '  "grammar_accuracy":  {"band": 6.0, "comment": "..."},\n'
        '  "task_response":     {"band": 6.0, "comment": "..."},\n'
        '  "overall_band": 6.0,\n'
        '  "tips": ["actionable tip 1", "actionable tip 2"],\n'
        '  "turn_feedback": [\n'
        '    {"turn": 1, "comment": "what this answer did well or missed"}\n'
        "  ]\n"
        "}"
    )

    try:
        genai.configure(api_key=_settings.GOOGLE_GEMINI_API_KEY)
        model = genai.GenerativeModel(
            getattr(_settings, "GEMINI_TEXT_MODEL_REASON", _settings.GEMINI_MODEL)
        )
        loop = _asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, model.generate_content, prompt
        )
        raw = (getattr(response, "text", "") or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0]
        try:
            data = _json.loads(raw)
        except Exception:
            import re as _re
            m = _re.search(r"\{[\s\S]*\}", raw)
            data = _json.loads(m.group(0)) if m else {}
    except Exception as e:
        return {
            "success": False,
            "error": f"Scoring failed: {e}",
            "bands": {
                "fluencyCoherence": None,
                "lexicalResource": None,
                "grammarAccuracy": None,
                "taskResponse": None,
            },
            "overall_band": None,
            "tips": [],
            "turn_feedback": [],
        }

    overall_band = data.get("overall_band")
    try:
        overall_band_f = float(overall_band) if overall_band is not None else None
    except Exception:
        overall_band_f = None
    overall_score_100 = (
        round(overall_band_f * 100.0 / 9.0)
        if overall_band_f is not None
        else None
    )

    return {
        "success": True,
        "part2_topic": request.part2_topic,
        "turn_count": len(norm_turns),
        "bands": {
            "fluencyCoherence": data.get("fluency_coherence"),
            "lexicalResource": data.get("lexical_resource"),
            "grammarAccuracy": data.get("grammar_accuracy"),
            "taskResponse": data.get("task_response"),
        },
        "overall_band": overall_band_f,
        "overall_score": overall_score_100,
        "tips": data.get("tips") or [],
        "turn_feedback": data.get("turn_feedback") or [],
    }



