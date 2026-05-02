import asyncio
import io
import base64
import logging
import uuid
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime

# Keep Generative AI imports for script generation and TTS
import google.generativeai as genai
from google.generativeai import types as generativeai_types
try:
    # Prefer the newer Google GenAI client when available
    from google import genai as genai_client
    from google.genai import types as genai_types
    HAS_GOOGLE_GENAI = True
except Exception:  # pragma: no cover - optional dependency
    genai_client = None
    genai_types = None
    HAS_GOOGLE_GENAI = False

from app.core.config import settings
from app.core.cache import get_redis
from app.services.audio_storage_service import audio_storage_service

logger = logging.getLogger(__name__)


def _parse_script_into_turns(script: str, speaker_names: List[str]) -> List[Dict[str, str]]:
    """Parse a generated dialogue script into ordered (speaker, text) turns.

    Accepts lines in either of these formats (LLM output may vary):
        [Speaker Name]: dialogue text
        Speaker Name: dialogue text

    Lines that don't match a known speaker are appended to the most recent
    turn so we don't drop content.
    """
    import re

    if not script:
        return []
    known = [s for s in (speaker_names or []) if isinstance(s, str) and s.strip()]
    # Match optional leading bracket, then name, then colon.
    name_re = re.compile(r"^\s*\[?\s*([^\[\]:]{1,60}?)\s*\]?\s*:\s*(.+?)\s*$")
    turns: List[Dict[str, str]] = []
    for raw in script.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = name_re.match(line)
        if m:
            speaker_raw = m.group(1).strip()
            text = m.group(2).strip()
            # Resolve to a known speaker name when possible (case-insensitive).
            resolved = next(
                (k for k in known if k.lower() == speaker_raw.lower()),
                speaker_raw,
            )
            turns.append({"speaker": resolved, "text": text})
        elif turns:
            turns[-1]["text"] = (turns[-1]["text"] + " " + line).strip()
        else:
            turns.append({"speaker": (known[0] if known else "Speaker"), "text": line})
    return turns


# Global singleton instance for thread-safe reuse
_tts_service_instance: Optional["GeminiTTSService"] = None
_tts_service_lock: Optional[asyncio.Lock] = None

class GeminiTTSService:
    """
    Text-to-Speech service using Gemini native audio model.
    Uses gemini-2.5-flash-native-audio-preview for high-quality audio generation.
    """

    def __init__(self):
        self._genai_client = None  # google.genai client for TTS and script generation
        self._text_model = None    # google.generativeai text model fallback
        self.redis = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize Gemini API client for TTS and text generation"""
        try:
            api_key = getattr(settings, 'GOOGLE_GEMINI_API_KEY', None)
            if not api_key:
                logger.warning("GOOGLE_GEMINI_API_KEY not found in settings. TTS and script generation will be unavailable.")
                return

            if HAS_GOOGLE_GENAI:
                # New Google GenAI client (preferred for native audio TTS)
                self._genai_client = genai_client.Client(api_key=api_key)
                logger.info("Google GenAI client initialized for Gemini native audio TTS")
            else:
                # Fallback to google-generativeai for text generation
                genai.configure(api_key=api_key)
                try:
                    self._text_model = genai.GenerativeModel(settings.GEMINI_TEXT_MODEL_FAST)
                except Exception:
                    self._text_model = None
                logger.info("google-generativeai configured (fallback mode for scripts)")
        except Exception as e:
            logger.error(f"Failed to initialize GenAI clients: {e}")
            self._genai_client = None
            self._text_model = None

    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    async def generate_audio_content(
        self,
        text: str,
        audio_type: str = "conversation",
        speaker_config: Optional[List[Dict[str, Any]]] = None,
        voice_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate audio content using the configured TTS provider.

        When ``settings.TTS_PROVIDER == "elevenlabs"`` this delegates to
        ElevenLabsTTSService. If ElevenLabs returns a non-fatal error
        and ``fallback_available`` is True, it falls back to Gemini.

        Args:
            text: The text to convert to speech
            audio_type: Type of audio content (conversation, monologue, etc.)
            speaker_config: Configuration for multiple speakers (currently supports single speaker)
            voice_settings: Additional voice configuration

        Returns:
            Dict containing audio data and metadata
        """
        provider = (getattr(settings, "TTS_PROVIDER", "gemini") or "gemini").lower()
        if provider == "elevenlabs":
            try:
                from app.services.elevenlabs_tts_service import get_elevenlabs_tts_service
                el = await get_elevenlabs_tts_service()
                el_result = await el.generate_audio_content(
                    text=text,
                    audio_type=audio_type,
                    speaker_config=speaker_config,
                    voice_settings=voice_settings,
                )
                if el_result.get("success"):
                    return el_result
                if not el_result.get("fallback_available"):
                    return el_result
                logger.warning(
                    f"ElevenLabs TTS failed, falling back to Gemini: {el_result.get('error')}"
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"ElevenLabs dispatch failed, falling back to Gemini: {e}")

        try:
            # Generate unique filename with UUID to prevent collisions in concurrent requests
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            # Also create a hash of the text for caching purposes
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"gemini_tts_{timestamp}_{unique_id}_{text_hash}.wav"

            # Set up default single-speaker voice configuration
            if not speaker_config:
                speaker_config = [{
                    "name": "Narrator",
                    "voice_name": getattr(settings, 'GEMINI_TTS_VOICE', 'Kore')
                }]

            voice_name = speaker_config[0].get("voice_name", getattr(settings, 'GEMINI_TTS_VOICE', 'Kore'))
            speech_model = getattr(settings, "GEMINI_SPEECH_MODEL", "gemini-2.5-flash-native-audio-preview-09-2025")

            # Use Gemini native audio API for TTS
            if self._genai_client is None:
                return {
                    "success": False,
                    "error": "Gemini API client not initialized. Check GOOGLE_GEMINI_API_KEY.",
                    "fallback_available": False,
                }

            # Build request for Gemini native audio TTS
            cfg = genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            )
            
            # Run the synchronous API call in a thread pool with timeout
            try:
                resp = None
                # Add simple retry logic
                for attempt in range(3):
                    try:
                        resp = await asyncio.wait_for(
                            asyncio.to_thread(
                                self._genai_client.models.generate_content,
                                model=speech_model,
                                contents=text,
                                config=cfg,
                            ),
                            timeout=30.0  # Increased to 30 second timeout
                        )
                        break
                    except asyncio.TimeoutError:
                        if attempt == 2:
                            raise
                        logger.warning(f"TTS attempt {attempt + 1} timed out, retrying...")
                        await asyncio.sleep(1 * (attempt + 1))
                    except Exception as e:
                        if attempt == 2:
                            raise
                        logger.warning(f"TTS attempt {attempt + 1} failed: {e}, retrying...")
                        await asyncio.sleep(1 * (attempt + 1))
            except asyncio.TimeoutError:
                logger.error(f"Gemini TTS API call timed out after 30s for text: {text[:50]}...")
                return {
                    "success": False,
                    "error": "TTS generation timed out",
                    "fallback_available": True
                }
            # Extract audio (PCM bytes or base64)
            data_field = None
            try:
                data_field = resp.candidates[0].content.parts[0].inline_data.data  # type: ignore[attr-defined]
            except Exception:
                # Fallback: some SDK versions expose a flat .text or .data
                data_field = getattr(resp, "data", None)

            if data_field is None:
                raise RuntimeError("No audio data returned from Gemini TTS")

            if isinstance(data_field, (bytes, bytearray)):
                pcm_bytes = bytes(data_field)
            elif isinstance(data_field, str):
                pcm_bytes = base64.b64decode(data_field)
            else:
                # Attempt to coerce buffer-like types
                pcm_bytes = bytes(data_field)

            # Wrap PCM in a WAV container
            import wave
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(24000)
                wf.writeframes(pcm_bytes)
            wav_bytes = buf.getvalue()
            audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

            # Store audio file and get URL
            storage_result = await audio_storage_service.store_audio(
                audio_data=audio_b64,
                filename=filename,
                metadata={
                    "text": text,
                    "audio_type": audio_type,
                    "speaker_config": speaker_config,
                    "voice_settings": voice_settings,
                    "generated_at": datetime.utcnow().isoformat(),
                    "tts_engine": speech_model,
                    "voice": voice_name,
                    "api": "google-genai",
                },
            )

            return {
                "success": True,
                "audio_url": storage_result["audio_url"],
                "filename": storage_result.get("filename", filename),
                "audio_data": audio_b64,
                "duration_seconds": storage_result.get("duration_seconds", len(text.split()) * 0.4),
                "file_size": storage_result.get("file_size", 0),
                "speaker_count": len(speaker_config),
                "tts_model": speech_model,
                "voice": voice_name,
                "metadata": {
                    "text_length": len(text),
                    "audio_type": audio_type,
                    "generated_at": datetime.utcnow().isoformat(),
                    "model": speech_model,
                    "voice_used": voice_name,
                    "api": "google-genai",
                },
            }

        except Exception as e:
            logger.error(f"Gemini TTS generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_available": True
            }

    # Audio storage is handled by AudioStorageService

    async def generate_listening_content(
        self,
        topic: str,
        difficulty_level: str,
        content_type: str = "conversation",
        speaker_names: Optional[List[str]] = None,
        accent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate listening content with appropriate script and audio.

        Args:
            topic: The topic for the listening content
            difficulty_level: CEFR level (A1, A2, B1, etc.)
            content_type: Type of content (conversation, monologue, etc.)
            speaker_names: Names for speakers in multi-speaker content

        Returns:
            Dict containing script, audio data, and metadata
        """
        try:
            # Generate appropriate script based on content type and level
            script_result = await self._generate_script(
                topic=topic,
                difficulty_level=difficulty_level,
                content_type=content_type,
                speaker_names=speaker_names
            )

            if not script_result["success"]:
                return script_result

            script = script_result["script"]
            speakers = script_result["speakers"]

            # Tag every speaker with the requested accent so the TTS provider
            # (ElevenLabs) can resolve American/British voices.
            accent_norm = (accent or "").strip().lower() or None
            if accent_norm and speakers:
                speakers = [
                    {**(s if isinstance(s, dict) else {"name": str(s)}), "accent": accent_norm}
                    for s in speakers
                ]

            # For multi-speaker formats (conversation/interview) on ElevenLabs,
            # synthesize each turn with a distinct voice (female + male) and
            # concatenate. This produces a dialogue with two recognizable voices
            # instead of a single voice reading both sides.
            audio_result: Optional[Dict[str, Any]] = None
            provider_pref = (getattr(settings, "TTS_PROVIDER", "gemini") or "gemini").lower()
            if (
                provider_pref == "elevenlabs"
                and content_type in ("conversation", "interview")
            ):
                turns = _parse_script_into_turns(script, speaker_names)
                if turns and len({t["speaker"] for t in turns}) >= 2:
                    try:
                        from app.services.elevenlabs_tts_service import (
                            get_elevenlabs_tts_service,
                        )
                        el = await get_elevenlabs_tts_service()
                        multi_result = await el.generate_multi_speaker_audio(
                            turns=turns,
                            audio_type=content_type,
                            accent=(accent_norm or "american"),
                            voice_settings=None,
                        )
                        if multi_result.get("success"):
                            audio_result = multi_result
                        else:
                            logger.warning(
                                "Multi-speaker ElevenLabs failed, falling back to "
                                f"single-voice: {multi_result.get('error')}"
                            )
                    except Exception as e:  # noqa: BLE001
                        logger.error(
                            f"Multi-speaker dispatch failed, falling back: {e}"
                        )

            # Single-voice path (or fallback): generate as one block.
            if audio_result is None:
                audio_result = await self.generate_audio_content(
                    text=script,
                    audio_type=content_type,
                    speaker_config=speakers,
                    voice_settings={"accent": accent_norm} if accent_norm else None,
                )

            if not audio_result["success"]:
                return audio_result

            # Normalize questions to include options and a clear correct answer
            def _normalize_questions(raw_questions: List[Any]) -> List[Dict[str, Any]]:
                normalized = []
                for idx, q in enumerate(raw_questions or []):
                    if isinstance(q, dict):
                        qdict = dict(q)
                    else:
                        qdict = {"question": str(q)}

                    question_text = qdict.get("question") or qdict.get("prompt") or f"Question {idx+1}?"
                    correct = qdict.get("correct_answer") or qdict.get("answer") or topic
                    options = qdict.get("options") if isinstance(qdict.get("options"), list) else []

                    # Build reasonable distractors if options missing or incomplete
                    if not options:
                        options = [
                            correct,
                            "A different detail from the audio",
                            "Not mentioned in the audio",
                            "An unrelated inference"
                        ]
                    # Ensure correct answer is present
                    if correct not in options:
                        options[0] = correct

                    # Optional explanation
                    explanation = qdict.get("explanation") or "Review the audio to confirm key details."

                    normalized.append({
                        "question": question_text,
                        "options": options,
                        "correct_answer": correct,
                        "explanation": explanation,
                    })
                return normalized

            # Echo provider/accent/voice from the underlying TTS so clients can
            # show the right label (e.g. "British accent — Charlotte").
            _provider = audio_result.get("provider") or (
                "elevenlabs" if str(audio_result.get("tts_model", "")).startswith("eleven") else "gemini"
            )
            _voice = (
                audio_result.get("voice")
                or audio_result.get("voice_name")
                or (speakers[0].get("voice_name") if speakers and isinstance(speakers[0], dict) else None)
            )
            _accent = audio_result.get("accent") or accent_norm

            return {
                "success": True,
                "topic": topic,
                "difficulty_level": difficulty_level,
                "content_type": content_type,
                "script": script,
                "speakers": speakers,
                "audio_url": audio_result["audio_url"],
                "audio_data": audio_result["audio_data"],
                "duration_seconds": audio_result["duration_seconds"],
                "audio_provider": _provider,
                "accent": _accent,
                "voice": _voice,
                "comprehension_questions": _normalize_questions(script_result.get("comprehension_questions", [])),
                "vocabulary_focus": script_result.get("vocabulary_focus", []),
                "metadata": {
                    "tts_model": audio_result.get("tts_model") or settings.GEMINI_SPEECH_MODEL,
                    "generated_at": datetime.utcnow().isoformat(),
                    "speaker_count": len(speakers),
                    "api": audio_result.get("api") or "google-genai",
                    "provider": _provider,
                    "accent": _accent,
                    "voice": _voice,
                }
            }

        except Exception as e:
            logger.error(f"Failed to generate listening content: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _generate_script(
        self,
        topic: str,
        difficulty_level: str,
        content_type: str,
        speaker_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate an appropriate script for the listening content"""

        # Adjust script complexity based on CEFR level
        length_guide = {
            "A1": "60-90 words",
            "A2": "90-140 words",
            "B1": "140-200 words",
            "B2": "200-260 words",
            "C1": "260-320 words",
            "C2": "320-400 words",
        }

        # Per-level CEFR guidance — what learners can do, sentence shape,
        # vocabulary band, tense range, and target question depth.
        cefr_guidance = {
            "A1": (
                "Use only the most basic everyday words (family, food, numbers, "
                "days, common verbs). Short, simple sentences (5-9 words), "
                "present simple, present continuous, simple imperatives. "
                "Speakers should pause between ideas. No idioms, no phrasal verbs. "
                "Questions should be literal recall (who/what/where/when)."
            ),
            "A2": (
                "Use frequent, concrete vocabulary about routines, work, study, "
                "shopping, travel. Short to medium sentences (8-14 words). "
                "Past simple, near future ('going to'), can/can't, basic comparatives. "
                "1-2 simple connectors (and, but, because). Questions test "
                "main ideas plus one obvious detail."
            ),
            "B1": (
                "Topic-relevant intermediate vocabulary; allow 2-3 mid-frequency "
                "words explained in context. Mixed sentence lengths (10-18 words). "
                "Present perfect, past continuous, first conditional, common "
                "modals (should, might, have to). Use natural connectors "
                "(however, although, so, then). Questions test main idea, "
                "supporting detail, and one inference."
            ),
            "B2": (
                "Independent-user vocabulary including some abstract terms and "
                "collocations. Sentence length 14-22 words with subordinate "
                "clauses. Second/third conditional, present/past perfect, "
                "passive voice, reported speech. Include opinion/attitude markers "
                "('it seems', 'apparently'). Questions probe attitude, gist, "
                "specific information, and inference from tone."
            ),
            "C1": (
                "Advanced vocabulary, common idioms, varied collocations, formal "
                "and neutral register. Long, complex sentences with embedded "
                "clauses. Full range of tenses, mixed conditionals, inversion "
                "for emphasis. Speakers signal stance and concession naturally. "
                "Questions cover implication, speaker purpose, register shifts, "
                "and synthesis across the text."
            ),
            "C2": (
                "Proficient vocabulary including low-frequency, idiomatic, and "
                "domain-specific terms; nuance, irony, and connotation expected. "
                "Sophisticated syntax: cleft sentences, fronting, ellipsis, "
                "discourse markers. Cohesive, near-native flow. Questions test "
                "subtle implication, rhetorical strategy, evaluative judgment, "
                "and recognition of bias or stance."
            ),
        }

        level_key = (difficulty_level or "B1").upper()
        level_guidance = cefr_guidance.get(level_key, cefr_guidance["B1"])
        target_length = length_guide.get(level_key, "140-200 words")

        # Set default speaker names based on content type
        if not speaker_names:
            if content_type == "conversation":
                speaker_names = ["Dr. Anya", "Liam"]
            elif content_type == "interview":
                speaker_names = ["Interviewer", "Expert"]
            else:
                speaker_names = ["Narrator"]

        prompt = f"""You are a CEFR-aligned English-listening content writer for SELM, an AI English-learning platform for any English learner worldwide.

Generate a {target_length} {content_type} about "{topic}" calibrated to CEFR level {level_key}.

Speakers: {', '.join(speaker_names)}

CEFR {level_key} requirements:
{level_guidance}

Universal rules:
- Natural spoken English, not written prose. Use contractions where appropriate.
- Avoid culturally narrow references; keep examples globally accessible.
- Do NOT use any non-English text. Output English only.
- Do NOT include translations, transliterations, or glosses inside the script.
- 4 multiple-choice comprehension questions, each with 4 plausible options and exactly one correct answer.
- Vocabulary list of 4-6 useful items from the script, each with a short, level-appropriate English definition.

Output Format (use these exact section markers):
[SCRIPT START]
[Speaker Name]: Dialogue line
...
[SCRIPT END]

[QUESTIONS START]
[
  {{
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "Option A",
    "explanation": "Why this is correct, in one short sentence."
  }}
]
[QUESTIONS END]

[VOCABULARY START]
- word1: short definition
- word2: short definition
[VOCABULARY END]
"""

        try:
            # Generate the script using preferred client
            script_text = ""
            if self._genai_client is not None:
                # Use a supported text model name for v1beta; adjust if needed
                resp = self._genai_client.models.generate_content(
                    model=settings.GEMINI_TEXT_MODEL_FAST,
                    contents=prompt,
                )
                # google.genai returns a response with .text
                script_text = getattr(resp, 'text', None) or ""
            elif self._text_model is not None:
                # Ensure fallback model is a supported one
                try:
                    resp = await asyncio.to_thread(self._text_model.generate_content, prompt)
                except Exception:
                    # Reconfigure with a safer model name and retry once
                    try:
                        genai.configure(api_key=getattr(settings, 'GOOGLE_GEMINI_API_KEY', None))
                        self._text_model = genai.GenerativeModel(settings.GEMINI_TEXT_MODEL_FAST)
                        resp = await asyncio.to_thread(self._text_model.generate_content, prompt)
                    except Exception:
                        raise
                script_text = getattr(resp, 'text', None) or ""
            else:
                raise RuntimeError("No GenAI client available for script generation")

            # Parse the script and extract components
            parsed_result = self._parse_generated_script(script_text, speaker_names)

            return {
                "success": True,
                "script": parsed_result["script"],
                "speakers": parsed_result["speakers"],
                "comprehension_questions": parsed_result["questions"],
                "vocabulary_focus": parsed_result["vocabulary"]
            }

        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_generated_script(self, script_text: str, speaker_names: List[str]) -> Dict[str, Any]:
        """Parse the generated script into components"""
        import json
        import re

        script_lines = []
        questions = []
        vocabulary = []

        # Remove markdown code blocks if present
        text = script_text.replace("```json", "").replace("```", "")
        
        # Extract sections using regex
        script_match = re.search(r"\[SCRIPT START\](.*?)\[SCRIPT END\]", text, re.DOTALL)
        questions_match = re.search(r"\[QUESTIONS START\](.*?)\[QUESTIONS END\]", text, re.DOTALL)
        vocab_match = re.search(r"\[VOCABULARY START\](.*?)\[VOCABULARY END\]", text, re.DOTALL)

        # Parse Script
        if script_match:
            script_lines = [line.strip() for line in script_match.group(1).strip().split('\n') if line.strip()]
        else:
            # Fallback for legacy format or failure
            script_lines = [line.strip() for line in text.split('\n') if line.strip() and not line.startswith('[')]

        # Parse Questions
        if questions_match:
            try:
                questions_json = questions_match.group(1).strip()
                questions = json.loads(questions_json)
            except json.JSONDecodeError:
                logger.warning("Failed to parse questions JSON from script")
        
        # Parse Vocabulary
        if vocab_match:
            vocab_text = vocab_match.group(1).strip()
            for line in vocab_text.split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    vocabulary.append({
                        "word": parts[0].strip("- ").strip(),
                        "definition": parts[1].strip()
                    })

        # Build speaker configurations for TTS
        speakers = []
        voice_options = ["Kore", "Puck", "Charon", "Kore", "Puck"]  # Available voices

        for i, name in enumerate(speaker_names):
            speakers.append({
                "name": name,
                "voice_name": voice_options[i % len(voice_options)]
            })

        return {
            "script": '\n'.join(script_lines),
            "speakers": speakers,
            "questions": questions,
            "vocabulary": vocabulary
        }

    async def get_cached_audio(self, filename: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached audio data using storage service"""
        return await audio_storage_service.get_audio(filename)


async def get_tts_service() -> "GeminiTTSService":
    """
    Get or create a singleton TTS service instance.
    Thread-safe for concurrent access.
    """
    global _tts_service_instance, _tts_service_lock
    
    # Lazy initialize the lock to avoid event loop issues
    if _tts_service_lock is None:
        _tts_service_lock = asyncio.Lock()
    
    if _tts_service_instance is None:
        async with _tts_service_lock:
            # Double-check after acquiring lock
            if _tts_service_instance is None:
                _tts_service_instance = GeminiTTSService()
                logger.info("TTS service singleton instance created")
    return _tts_service_instance
