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
from app.services.language_profile import profile_for

logger = logging.getLogger(__name__)

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
                # Fallback to google-generativeai for text generation.
                # 2026-05-13 (late): use DIALOGUE tier (flash) for
                # listening scripts — pro was making the iPhone wait
                # 30 s, flash returns in 3-6 s with quality that's
                # well above flash-lite. The right trade-off for
                # dialogue where structure matters more than nuance.
                genai.configure(api_key=api_key)
                dialogue_name = (
                    getattr(settings, "GEMINI_TEXT_MODEL_DIALOGUE", None)
                    or getattr(settings, "GEMINI_TEXT_MODEL_FAST", "gemini-2.5-flash-lite")
                )
                try:
                    self._text_model = genai.GenerativeModel(dialogue_name)
                except Exception:
                    self._text_model = None
                logger.info(
                    "google-generativeai configured (script-gen fallback) model=%s",
                    dialogue_name,
                )
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
        Generate audio content using Gemini native audio model.

        Args:
            text: The text to convert to speech
            audio_type: Type of audio content (conversation, monologue, etc.)
            speaker_config: Configuration for multiple speakers (currently supports single speaker)
            voice_settings: Additional voice configuration

        Returns:
            Dict containing audio data and metadata
        """
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
        speaker_names: Optional[List[str]] = None
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

            # Generate audio using Gemini TTS
            audio_result = await self.generate_audio_content(
                text=script,
                audio_type=content_type,
                speaker_config=speakers
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
                "comprehension_questions": _normalize_questions(script_result.get("comprehension_questions", [])),
                "vocabulary_focus": script_result.get("vocabulary_focus", []),
                "metadata": {
                    "tts_model": settings.GEMINI_SPEECH_MODEL,
                    "generated_at": datetime.utcnow().isoformat(),
                    "speaker_count": len(speakers),
                    "api": "google-genai"
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
        speaker_names: Optional[List[str]] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Generate an appropriate script for the listening content.

        2026-05-13: listening is now ALWAYS multi-speaker (2 or 3
        people) regardless of content_type unless the caller explicitly
        provides a single speaker_name. Ebrahim asked for genuine
        conversations, not narrated monologues. Speaker identities,
        relationship, tension, scene and place come from
        ``dialogue_seed()`` so two listening exercises about the same
        topic never feel like the same recording.
        """
        from app.services.prompt_library import (
            cefr_block,
            dialogue_seed,
            render_dialogue_brief,
            HUMAN_VOICE_RULES,
            NAMES_F,
            NAMES_M,
        )
        import random as _random

        # Adjust script complexity based on difficulty level.
        # 2026-05-13: bumped meaningfully so listening dialogues have
        # room for a real exchange (turn → reaction → development →
        # resolution). Previous targets produced exchanges that ended
        # before either speaker had built any momentum.
        length_guide = {
            "A1": "90-130 words",
            "A2": "140-200 words",
            "B1": "220-310 words",
            "B2": "320-450 words",
            "C1": "470-620 words",
            "C2": "650-850 words",
        }

        # Pick a fresh dialogue brief (international speakers, varied
        # relationship + tension + scene) so listening exercises never
        # feel like the same recording with different vocabulary.
        d_seed = dialogue_seed()
        d_brief = render_dialogue_brief(d_seed)

        # Decide speaker count + names. If the caller passed names, honour them.
        # Otherwise default to 2 speakers from the seed, or 3 if content_type
        # hints at it (e.g. group conversation). Single-narrator only when
        # caller forces it via speaker_names=["Narrator"].
        if speaker_names:
            speakers_for_prompt = speaker_names
        else:
            base = [d_seed["speaker_a_name"], d_seed["speaker_b_name"]]
            # 25% chance of a third speaker for richer group dynamics —
            # picked separately so we don't repeat A or B.
            if _random.random() < 0.25:
                pool = NAMES_F + NAMES_M
                third = next((n for n in _random.sample(pool, len(pool)) if n not in base), None)
                if third:
                    base.append(third)
            speakers_for_prompt = base

        # Generate script prompt
        speakers_block = ", ".join(speakers_for_prompt)

        # 2026-08-28, Amendment 2 §2.3. Without this line the prompt is
        # written in English and therefore produces English, whatever voices
        # render it. It is placed FIRST because a language instruction buried
        # under four blocks of style rules is one the model drops.
        _lang = profile_for(language)

        prompt = f"""{_lang.write_in}

Write a {length_guide.get(difficulty_level, "140-200 words")} listening-practice script — a multi-speaker conversation about "{topic}".

{cefr_block(difficulty_level)}

{HUMAN_VOICE_RULES}

{d_brief}

SPEAKER ROSTER
  Use these exact names, in this order, for all dialogue lines:
  {speakers_block}

MULTI-SPEAKER REQUIREMENTS — MANDATORY
  • The script MUST be a genuine back-and-forth conversation with at
    least 2 speakers. Do NOT write a monologue with one speaker doing
    all the talking.
  • Every speaker named above must speak multiple times. No speaker
    should have a single line.
  • Turns should feel natural — short reactions, interruptions, follow-up
    questions, brief agreement or disagreement, the occasional
    "yeah" / "right" / "huh" / "I see" at the level allowed.
  • Each speaker should sound distinct (different sentence length,
    different vocabulary habits, different reactive patterns).

SUBSTANTIVE DEPTH — non-negotiable
  • Use the FULL word count from the level guide above. A short
    dialogue that wraps up in 4 turns is failure even if it's "natural".
  • The conversation should develop: opening situation → small
    complication → exchange of perspectives → some resolution or
    deepening. Don't end before both speakers have built momentum.
  • Anchor exchanges in concrete specifics (a name, a place, a thing
    one of them owns or does) — vague chit-chat at any length is filler.

Output Format — follow exactly so the parser can read it:
[SCRIPT START]
{speakers_for_prompt[0]}: First line of dialogue.
{speakers_for_prompt[1] if len(speakers_for_prompt) > 1 else speakers_for_prompt[0]}: Response line.
... (continue alternating; every speaker speaks multiple times) ...
[SCRIPT END]

[QUESTIONS START]
[
  {{
    "question": "Question text testing understanding of the conversation?",
    "options": ["A", "B", "C", "D"],
    "correct_answer": "A",
    "explanation": "Why this is correct, with reference to what was said."
  }}
]
[QUESTIONS END]

[VOCABULARY START]
- word1: short level-appropriate definition
- word2: short level-appropriate definition
[VOCABULARY END]
"""

        try:
            # Generate the script using preferred client
            script_text = ""
            if self._genai_client is not None:
                # 2026-05-13 (late): use DIALOGUE tier (flash) instead
                # of CONTENT (pro). On iPhone, pro was taking 15-30s
                # for a typical 12-turn dialogue script, which pushed
                # total listening load time past 60s when combined with
                # TTS. Flash returns in 3-6s with quality that's still
                # well above flash-lite, which is the right trade-off
                # for dialogue scripts (structure matters more than
                # prose nuance here).
                script_model_name = (
                    getattr(settings, "GEMINI_TEXT_MODEL_DIALOGUE", None)
                    or getattr(settings, "GEMINI_TEXT_MODEL_FAST", "gemini-2.5-flash-lite")
                )
                resp = self._genai_client.models.generate_content(
                    model=script_model_name,
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

            # Parse the script using the ACTUAL roster (speakers_for_prompt),
            # not the original `speaker_names` parameter — that's often None
            # when the caller relies on our auto-rostering.
            parsed_result = self._parse_generated_script(script_text, speakers_for_prompt)

            # Attach gender hints from the dialogue seed so the TTS layer
            # (ElevenLabs' _build_speaker_voice_map) can pick a gender-
            # matched voice. Without this hint, all speakers would be
            # round-robin'd across the full voice pool regardless of name.
            speakers_with_gender: List[Dict[str, Any]] = []
            name_to_gender: Dict[str, str] = {}
            if d_seed:
                name_to_gender[d_seed["speaker_a_name"]] = (
                    "female" if "she" in d_seed["speaker_a_pronouns"] else "male"
                )
                name_to_gender[d_seed["speaker_b_name"]] = (
                    "female" if "she" in d_seed["speaker_b_pronouns"] else "male"
                )
            from app.services.prompt_library import NAMES_F as _NF
            for sp in parsed_result["speakers"]:
                name = sp.get("name") or ""
                # Use the seed mapping if we have it; else infer from name pool.
                if name in name_to_gender:
                    sp["gender"] = name_to_gender[name]
                elif name in _NF:
                    sp["gender"] = "female"
                else:
                    sp["gender"] = "male"
                speakers_with_gender.append(sp)

            return {
                "success": True,
                "script": parsed_result["script"],
                "speakers": speakers_with_gender,
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


async def get_tts_service():
    """
    Get or create a singleton TTS service instance.

    Provider is selected by the ``TTS_PROVIDER`` env var:
      - ``elevenlabs`` → ElevenLabsTTSService (paid, higher voice quality)
      - anything else (default) → GeminiTTSService

    The returned object exposes ``generate_audio_content(...)`` and
    ``get_cached_audio(...)`` regardless of provider, so existing endpoints
    don't need to change.

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
                provider = (
                    getattr(settings, "TTS_PROVIDER", "")
                    or getattr(settings, "TTS_SERVICE", "")
                    or "openai"
                ).strip().lower()

                # Resolution order with automatic fallback (2026-05-13):
                # If the chosen provider's API key is missing, we cascade
                # down: openai → elevenlabs → gemini. This way a fresh
                # dev environment without OpenAI still produces audio,
                # and a production with OPENAI_API_KEY set always
                # prefers the natural-voice provider.
                openai_key = getattr(settings, "OPENAI_API_KEY", None)
                eleven_key = getattr(settings, "ELEVENLABS_API_KEY", None)

                if provider == "openai" and openai_key:
                    from app.services.openai_tts_service import OpenAITTSService
                    _tts_service_instance = OpenAITTSService()
                    logger.info(
                        "TTS service singleton created (provider=openai)"
                    )
                elif provider == "elevenlabs" and eleven_key:
                    from app.services.elevenlabs_tts_service import (
                        ElevenLabsTTSService,
                    )
                    _tts_service_instance = ElevenLabsTTSService()
                    logger.info(
                        "TTS service singleton created (provider=elevenlabs)"
                    )
                elif provider in ("openai", "elevenlabs"):
                    # Chosen provider's key missing — try the other
                    # provider before falling back to Gemini.
                    if openai_key:
                        from app.services.openai_tts_service import (
                            OpenAITTSService,
                        )
                        _tts_service_instance = OpenAITTSService()
                        logger.warning(
                            "TTS_PROVIDER=%s but its key is missing; using "
                            "OpenAI TTS instead.", provider,
                        )
                    elif eleven_key:
                        from app.services.elevenlabs_tts_service import (
                            ElevenLabsTTSService,
                        )
                        _tts_service_instance = ElevenLabsTTSService()
                        logger.warning(
                            "TTS_PROVIDER=%s but its key is missing; using "
                            "ElevenLabs TTS instead.", provider,
                        )
                    else:
                        _tts_service_instance = GeminiTTSService()
                        logger.warning(
                            "Neither OpenAI nor ElevenLabs key configured "
                            "— falling back to Gemini TTS."
                        )
                else:
                    _tts_service_instance = GeminiTTSService()
                    logger.info(
                        "TTS service singleton created (provider=gemini)"
                    )
    return _tts_service_instance
