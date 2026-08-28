import asyncio
import functools
import aiohttp
from typing import Dict, List, Optional, Any
import google.generativeai as genai
import io
import base64
import logging

from app.core.config import settings
from app.services.prompt_library import (
    cefr_block,
    build_learner_context,
    creative_seed,
    dialogue_seed,
    render_creative_brief,
    render_dialogue_brief,
    HUMAN_VOICE_RULES,
    PEDAGOGY_RULES,
)

logger = logging.getLogger(__name__)

from app.services.language_profile import profile_for


class AIService:
    def __init__(self):
        # Configure Google Gemini.
        #
        # 2026-05-13: ``self.gemini_model`` is now the CONTENT-tier
        # model (gemini-2.5-pro by default). Previously this was
        # flash-lite, which produced noticeably weaker multi-paragraph
        # prose. The cost increase is intentional — Ebrahim approved
        # it explicitly to lift content quality across the app.
        #
        # ``self.fast_model`` keeps a flash-lite handle for the few
        # paths that genuinely need sub-second latency over quality
        # (e.g. real-time grammar-answer feedback). New code should
        # default to ``self.gemini_model``.
        #
        # If the CONTENT model fails to initialise (wrong name, quota,
        # etc.) we fall back to flash-lite so the app degrades to "old
        # quality" instead of failing outright.
        if settings.GOOGLE_GEMINI_API_KEY:
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)

            content_name = getattr(
                settings, "GEMINI_TEXT_MODEL_CONTENT", None
            ) or getattr(settings, "GEMINI_TEXT_MODEL_FAST", "gemini-2.5-flash-lite")
            fast_name = getattr(
                settings, "GEMINI_TEXT_MODEL_FAST", "gemini-2.5-flash-lite"
            )

            try:
                self.gemini_model = genai.GenerativeModel(content_name)
                logger.info("Gemini CONTENT model initialised: %s", content_name)
            except Exception as e:
                logger.warning(
                    "Failed to init CONTENT model %s; using FAST as primary: %s",
                    content_name, e,
                )
                try:
                    self.gemini_model = genai.GenerativeModel(fast_name)
                    logger.info("Gemini FAST model initialised (fallback): %s", fast_name)
                except Exception as e2:
                    logger.error("Failed to init any Gemini model: %s", e2)
                    self.gemini_model = None

            try:
                self.fast_model = genai.GenerativeModel(fast_name)
            except Exception:
                # If FAST init fails but CONTENT works, just reuse it.
                self.fast_model = self.gemini_model

            # Alias kept for callers that already use this name.
            self.content_model = self.gemini_model
        else:
            self.gemini_model = None
            self.fast_model = None
            self.content_model = None
            logger.warning("Google Gemini API key not configured")

    async def generate_exercise_content(
        self, 
        topic: str, 
        difficulty_level: str, 
        exercise_type: str,
        count: int = 5
    ) -> Dict[str, Any]:
        """Generate exercise content using AI"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        prompt = f"""You are designing a single lesson + practice set for an
adult English learner. The output goes directly into a mobile app — there
is no teacher in the loop to fix weak material — so the writing has to do
the work of a real teacher: specific, level-appropriate, and engaging.

LESSON BRIEF
  Topic:           {topic}
  Exercise type:   {exercise_type}
  Practice items:  {count}

{cefr_block(difficulty_level)}

{HUMAN_VOICE_RULES}

{PEDAGOGY_RULES}

CONTENT REQUIREMENTS
  1. Vocabulary: 8–12 items that genuinely belong in a {difficulty_level}
     conversation about "{topic}" — not just words tangentially related.
     Each item needs: the word, part of speech, learner-friendly
     definition, a one-line plain-English explanation, a concrete example
     sentence using the word (a real situation, not "This is an example
     of X"), and a usage_tip that warns about a real mistake learners
     make with this word.
  2. Grammar (only when exercise_type is "grammar"): one focused rule
     directly useful for the topic. Provide three example sentences in
     contrasting situations, and two common-mistake examples each with
     a fix.
  3. Practice exercises: produce exactly {count}. Mix question types
     (multiple_choice, fill_in_blank, sentence_transformation) where
     reasonable. Every question must:
       • test something the lesson actually taught,
       • have a single defensible correct answer,
       • include an "explanation" that teaches the rule, not just states
         the answer,
       • for multiple_choice, give plausible distractors based on common
         {difficulty_level} learner errors — never throwaway nonsense.
  4. Match the "vocabulary_words" top-level array EXACTLY to
     lesson.vocabulary_words (the UI reads from the top level).

Return ONLY valid JSON, no markdown fences, in this exact shape:
{{
  "topic": "{topic}",
  "level": "{difficulty_level}",
  "lesson": {{
    "objective": "By the end of this lesson, learners will be able to ___ (one observable skill).",
    "vocabulary_words": [
      {{
        "word": "...",
        "part_of_speech": "noun|verb|adjective|adverb|phrasal_verb|idiom",
        "definition": "...",
        "simple_explanation": "...",
        "example_sentence": "concrete situation using the word",
        "usage_tip": "real-world tip OR common-mistake warning"
      }}
    ],
    "grammar_point": {{
      "title": "...",
      "explanation": "...",
      "examples": ["...", "...", "..."],
      "common_mistakes": [
        {{"mistake": "...", "fix": "..."}},
        {{"mistake": "...", "fix": "..."}}
      ]
    }}
  }},
  "vocabulary_words": [COPY OF lesson.vocabulary_words],
  "grammar_summary": {{
    "title": "...",
    "explanation": "...",
    "examples": ["...", "..."],
    "common_mistakes": ["...", "..."]
  }},
  "exercises": [
    {{
      "question": "...",
      "type": "multiple_choice|fill_in_blank|sentence_transformation",
      "options": ["...", "...", "...", "..."],
      "correct_answer": "...",
      "explanation": "Explain WHY it is correct — teach the rule.",
      "target": "vocabulary|grammar"
    }}
  ]
}}"""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            content = response.text.strip()
            # Clean up markdown code blocks if present
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            return {"content": content, "success": True}
        except Exception as e:
            logger.error(f"Error generating exercise content: {e}")
            return {"error": str(e), "success": False}

    async def check_grammar(self, text: str, language: str = "en") -> Dict[str, Any]:
        """Check grammar and provide corrections.

        `language` comes from the goal's exam, not a per-user setting, and is
        routed through profile_for so an unknown code falls back to English
        loudly rather than silently checking French prose against English
        rules. Until 2026-08-28 this prompt said "English text" unconditionally
        - the fifth "value written into code that should have been config".
        """
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        lang = profile_for(language)
        prompt = f"""
        Check the following {lang.english_name} text for grammar errors and provide corrections. {lang.write_in}
        
        Text: "{text}"
        
        Please provide:
        1. Corrected version of the text
        2. List of errors found with explanations
        3. Grammar rules that apply
        
        Format as JSON:
        {{
            "original": "{text}",
            "corrected": "...",
            "errors": [
                {{
                    "error": "...",
                    "correction": "...",
                    "explanation": "...",
                    "rule": "..."
                }}
            ],
            "score": 0-100
        }}
        """

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            return {"content": response.text, "success": True}
        except Exception as e:
            logger.error(f"Error checking grammar: {e}")
            return {"error": str(e), "success": False}

    async def assess_grammar_answer(
        self,
        question: str,
        selected_answer: str,
        correct_answer: str,
        options: List[str],
        grammar_rule: str = "",
        user_level: str = "B1"
    ) -> Dict[str, Any]:
        """Provide detailed AI feedback for a grammar practice answer"""
        if not self.gemini_model:
            # Fallback when AI is not available
            is_correct = selected_answer == correct_answer
            return {
                "success": True,
                "is_correct": is_correct,
                "explanation": f"The correct answer is '{correct_answer}'.",
                "rule_explanation": grammar_rule if grammar_rule else "Practice this grammar pattern more.",
                "examples": [],
                "common_mistakes": [],
                "tip": "Keep practicing to improve your grammar skills!"
            }

        is_correct = selected_answer == correct_answer
        options_str = ", ".join(f'"{opt}"' for opt in options)

        prompt = f"""You are a careful English-grammar tutor giving feedback
on a single practice answer. Be specific, accurate, and encouraging —
never patronising.

CONTEXT
  Question:           {question}
  Options:            [{options_str}]
  Student's answer:   {selected_answer}
  Correct answer:     {correct_answer}
  Grammar topic:      {grammar_rule if grammar_rule else "General grammar"}
  Outcome:            {"CORRECT" if is_correct else "INCORRECT"}

{cefr_block(user_level)}

{HUMAN_VOICE_RULES}

WHAT TO PRODUCE
  • explanation: 2–3 sentences. Don't restate the answer; explain WHY
    the rule selects it.
  • rule_explanation: name the rule (e.g. "second conditional"), give
    the structure in plain symbols (If + past simple, would + base
    verb), and one short prose paragraph.
  • examples: three different example sentences using the rule in
    different real-life situations.
  • common_mistakes: two specific learner errors with this rule at
    {user_level} level, each with a one-line fix.
  • tip: one memorable, short tip — a pattern, an analogy, or a
    mnemonic. Not "practice more".
  • why_wrong: only when the answer was incorrect, explain what the
    student's choice WOULD have meant or where it breaks the rule. If
    correct, return an empty string.

Return ONLY valid JSON (no markdown):
{{
    "is_correct": {str(is_correct).lower()},
    "explanation": "...",
    "rule_explanation": "...",
    "examples": ["...", "...", "..."],
    "common_mistakes": [
        {{"mistake": "...", "fix": "..."}},
        {{"mistake": "...", "fix": "..."}}
    ],
    "tip": "...",
    "why_wrong": "{'' if is_correct else '...'}"
}}"""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            
            import json
            import re
            
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)
            
            result = json.loads(response_text)
            result["success"] = True
            return result
            
        except Exception as e:
            logger.error(f"Error assessing grammar answer: {e}")
            # Return basic feedback on error
            return {
                "success": True,
                "is_correct": is_correct,
                "explanation": f"The correct answer is '{correct_answer}'." + (
                    f" You chose '{selected_answer}', which is incorrect." if not is_correct else " Great job!"
                ),
                "rule_explanation": grammar_rule if grammar_rule else "This tests your understanding of English grammar patterns.",
                "examples": [f"Example: {correct_answer} is used correctly in this context."],
                "common_mistakes": [],
                "tip": "Keep practicing to master this grammar point!",
                "why_wrong": "" if is_correct else f"'{selected_answer}' doesn't fit the grammatical context here."
            }

    async def generate_vocabulary_explanation(
        self, word: str, level: str, language: str = "en"
    ) -> Dict[str, Any]:
        """Generate vocabulary explanation with examples.

        `language` comes from the goal's exam. Was hard-coded to English, so a
        TCF candidate adding a French word got an English-framed explanation.
        """
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        lang = profile_for(language)
        prompt = f"""Teach the {lang.english_name} word "{word}" to an adult
international learner. {lang.write_in} Make this feel like a tutor explaining
the word in person — specific, accurate, and useful — not a dictionary dump.

{cefr_block(level)}

REQUIREMENTS
  • Definition: clear and learner-friendly, calibrated to the level
    above. Avoid circular definitions.
  • Pronunciation: IPA in slashes (e.g. /ˈekzæmpl/), plus a short
    plain-English approximation when the IPA is tricky.
  • Three example sentences in contrasting contexts (e.g. work, daily
    life, opinion) — concrete and human. No "This is a {word}."
  • Collocations: the 3–6 word partners learners actually need first
    (verb+noun, adjective+noun, etc.).
  • Synonyms and antonyms with a one-line note on when each fits or
    doesn't — synonyms are rarely fully interchangeable.
  • Usage notes: the one mistake learners commonly make with this word
    at this level, and how to avoid it.

Return ONLY valid JSON:
{{
    "word": "{word}",
    "definition": "...",
    "part_of_speech": "...",
    "pronunciation_ipa": "...",
    "pronunciation_plain": "...",
    "examples": ["...", "...", "..."],
    "collocations": [
        {{"phrase": "...", "note": "common partner — when to use"}}
    ],
    "synonyms": [
        {{"word": "...", "note": "how it differs from the headword"}}
    ],
    "antonyms": [
        {{"word": "...", "note": "..."}}
    ],
    "common_mistake": {{"mistake": "...", "fix": "..."}},
    "usage_notes": "..."
}}"""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            return {"content": response.text, "success": True}
        except Exception as e:
            logger.error(f"Error generating vocabulary explanation: {e}")
            return {"error": str(e), "success": False}

    async def generate_text_to_speech(
        self, text: str, language: str = "en", slow: bool = False
    ) -> Optional[bytes]:
        """Generate audio bytes for ``text`` via the unified TTS factory.

        Routes through ``get_tts_service()`` so the call honours the
        ``TTS_PROVIDER`` env var — by default ElevenLabs (natural human
        voice), with automatic Gemini fallback if the ElevenLabs key is
        missing. The old gTTS path produced robotic, low-quality audio
        and bypassed both providers, so it was retired (2026-05-13).

        ``language`` and ``slow`` are kept for call-site compatibility but
        only English is currently supported by the rest of the pipeline.
        """
        try:
            from app.services.gemini_tts_service import get_tts_service
            tts = await get_tts_service()
            result = await tts.generate_audio_content(
                text=text,
                audio_type="narration",
            )
            if not result.get("success"):
                logger.error(
                    "TTS failed via %s: %s",
                    type(tts).__name__,
                    result.get("error"),
                )
                return None
            # Prefer the base64 payload — same shape both providers return.
            b64 = result.get("audio_data_base64") or result.get("audio_data")
            if b64:
                return base64.b64decode(b64)
            # Fallback: caller may resolve the audio_url separately.
            return None
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None

    async def analyze_pronunciation(
        self, audio_data: bytes, expected_text: str
    ) -> Dict[str, Any]:
        """Analyze pronunciation, stress, fluency and intonation.

        Routes through SpeechAce (premium endpoints) so we get
        phoneme-level scoring, syllable stress, fluency, and an IELTS/CEFR
        band — not a hardcoded mock. Was a placeholder until 2026-05-13.

        Returns a normalised dict the frontend already knows how to render:

            {
              "score": float (0–100, overall),
              "pronunciation_score": float,
              "fluency_score": float,
              "accuracy_score": float,
              "transcript": str,
              "word_scores": {word: score},
              "phoneme_scores": {phoneme: score},
              "pronunciation_issues": [{word, issue, suggestion, score}],
              "feedback": str,
              "suggestions": [str],
              "ielts": { "overall_band": float, "cefr_level": str, ... } | None
            }
        """
        # Defensive: empty audio or text → nothing to score.
        if not audio_data:
            return {
                "score": 0.0,
                "feedback": "No audio received. Please record again.",
                "suggestions": ["Make sure your microphone is enabled."],
                "word_scores": {},
                "phoneme_scores": {},
                "pronunciation_issues": [],
            }

        # Lazy import to avoid circulars at module-load time.
        from app.services.speechace_service import SpeechaceService

        if not getattr(settings, "SPEECHACE_API_KEY", None):
            logger.warning(
                "analyze_pronunciation called but SPEECHACE_API_KEY is not "
                "set — returning a minimal heuristic result. Configure "
                "SPEECHACE_API_KEY in .env for real phoneme-level scoring."
            )
            return {
                "score": 0.0,
                "feedback": (
                    "Pronunciation scoring is not configured on this "
                    "deployment. Ask the operator to set SPEECHACE_API_KEY."
                ),
                "suggestions": [],
                "word_scores": {},
                "phoneme_scores": {},
                "pronunciation_issues": [],
            }

        service = SpeechaceService()
        result = await service.assess_pronunciation(
            audio_bytes=audio_data,
            reference_text=expected_text or "",
        )
        if not result.get("success"):
            logger.error(
                "SpeechAce assess_pronunciation failed: %s",
                result.get("error"),
            )
            return {
                "score": 0.0,
                "feedback": "Pronunciation analysis failed. Please try again.",
                "suggestions": [],
                "word_scores": {},
                "phoneme_scores": {},
                "pronunciation_issues": [],
                "error": result.get("error"),
            }

        a = result.get("assessment") or {}
        # Adapt SpeechAce's keys to the historical shape this endpoint
        # exposed so frontend rendering doesn't have to change.
        return {
            "score": float(a.get("overall_score", 0.0) or 0.0),
            "pronunciation_score": float(
                a.get("pronunciation_score", 0.0) or 0.0
            ),
            "fluency_score": float(a.get("fluency_score", 0.0) or 0.0),
            "accuracy_score": float(a.get("accuracy_score", 0.0) or 0.0),
            "transcript": a.get("transcribed_text", "") or "",
            "word_scores": a.get("word_scores", {}) or {},
            "phoneme_scores": a.get("phoneme_scores", {}) or {},
            "pronunciation_issues": a.get("pronunciation_issues", []) or [],
            "detailed_word_feedback": a.get("detailed_word_feedback", []) or [],
            "feedback": a.get("feedback", "") or "",
            "suggestions": a.get("suggestions", []) or [],
        }

    async def generate_conversation_practice(
        self, topic: str, level: str, turns: int = 6
    ) -> Dict[str, Any]:
        """Generate conversation practice scenarios"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        d_seed = dialogue_seed()
        d_brief = render_dialogue_brief(d_seed)

        prompt = f"""Write a short conversation practice that sounds like
two real people speaking — not a textbook example.

BRIEF
  Topic:     {topic}
  Turns:     exactly {turns}
  Audience:  international English learner, any background

{cefr_block(level)}

{HUMAN_VOICE_RULES}

{d_brief}

DIALOGUE RULES
  • Use the speakers' names from the brief above for every line. Do
    NOT use generic labels like "Speaker A" / "Speaker B".
  • Open with a specific concrete moment in the scene above — someone
    is doing something, somewhere, for a reason. Don't write "X meets Y".
  • The conversation should have the small arc described in the
    brief's "Tension" line — not just polite greetings.
  • Each speaker should sound different: different sentence length,
    different reactive habits, different filler words ("right",
    "honestly", "I mean", "huh"), where the level allows.
  • Keep total length appropriate for the level's sentence rules.
  • Pull 5–8 useful target vocabulary items that genuinely appear in
    the dialogue, plus 3–5 ready-made phrases learners can reuse
    elsewhere (e.g. "do you mind if I…", "I see what you mean").

Return ONLY valid JSON in this shape:
{{
  "scenario": "One sentence setting the scene: who, where, why.",
  "speakers": [
    {{"name": "...", "gender": "female|male|unspecified", "role": "short role label"}},
    {{"name": "...", "gender": "female|male|unspecified", "role": "..."}}
  ],
  "dialogue": [
    {{"speaker": "<name>", "text": "..."}}
  ],
  "vocabulary": [
    {{"word": "...", "definition": "...", "example": "the line from the dialogue where it appears"}}
  ],
  "phrases": [
    {{"phrase": "...", "use_when": "natural situation where a learner could deploy this"}}
  ],
  "comprehension_check": [
    {{"question": "...", "answer": "..."}}
  ]
}}"""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            return {"content": response.text, "success": True}
        except Exception as e:
            logger.error(f"Error generating conversation practice: {e}")
            return {"error": str(e), "success": False}

    async def generate_level_assessment_quiz(
        self,
        target_level: Optional[str] = None,
        question_count: int = 20,
        user_preferences: Optional[List[str]] = None,
        personalized: bool = True
    ) -> Dict[str, Any]:
        """Generate a comprehensive level assessment quiz to determine user's CEFR level"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        level_focus = f"Focus on {target_level} level assessment" if target_level else "Cover all CEFR levels (A1-C2)"

        preferences_text = f"Preferred topics: {', '.join(user_preferences)}" if user_preferences else ""
        personalization_text = (
            "Personalize contexts and topics to the provided preferences." if personalized else ""
        )

        prompt = f"""
        Create a comprehensive English level assessment quiz with {question_count} questions to determine a student's CEFR level.

        {level_focus}

        {personalization_text}
        {preferences_text}

        CRITICAL REQUIREMENTS:
        1. Output ONLY valid JSON - no comments, no explanations, no markdown formatting
        2. Include questions for all 4 skills: Grammar (30%), Vocabulary (30%), Reading (25%), Listening Comprehension (15%)
        3. Progress from easy (A1) to difficult (C2) questions
        4. Each question should clearly test specific CEFR level competencies
        5. Include a mix of question types: multiple_choice, true_false, fill_in_blank
        5a. For reading questions, you MUST include a complete, self-contained passage in a field named "passage". The passage must be substantial and level-appropriate: A1≈40-60 words, A2≈80-120 words, B1≈150-220 words, B2≈250-350 words, C1/C2≈400-600+ words. Do NOT reference or assume any external content; embed the full text.
        5b. For listening questions, include either an "audio_url" (HTTPS link to MP3) OR, if you cannot host audio, include "audio_text" (the exact transcript to be fed to TTS). One of these fields is REQUIRED for listening questions.
        6. Provide detailed explanations for correct answers
        7. Include difficulty level for each question (A1-C2)
        8. Points must be integers (1, 2, 3, 4, 5) - NOT floats

        REQUIRED JSON FORMAT (copy this structure exactly):
        {{
            "quiz_metadata": {{
                "title": "CEFR Level Assessment Quiz",
                "description": "Comprehensive assessment to determine your English proficiency level",
                "total_questions": {question_count},
                "estimated_duration_minutes": {int(question_count * 1.5)},
                "skills_tested": ["grammar", "vocabulary", "reading", "listening"]
            }},
            "questions": [
                {{
                    "id": 1,
                    "skill": "grammar",
                    "difficulty_level": "A1",
                    "question_type": "multiple_choice",
                    "question": "I _____ a student.",
                    "options": ["am", "is", "are", "be"],
                    "correct_answer": "am",
                    "explanation": "This uses the present simple tense, 'am' is the correct form for the first person singular (I).",
                    "points": 1
                }},
                {{
                    "id": 2,
                    "skill": "vocabulary",
                    "difficulty_level": "A1",
                    "question_type": "multiple_choice",
                    "question": "What do you use to write?",
                    "options": ["a book", "a pen", "a tree", "a car"],
                    "correct_answer": "a pen",
                    "explanation": "A pen is used for writing.",
                    "points": 1
                }},
                {{
                    "id": 2,
                    "skill": "listening",
                    "difficulty_level": "A1",
                    "question_type": "multiple_choice",
                    "audio_text": "Hello, my name is Anna. I live in London.",
                    "question": "Where does the speaker live?",
                    "options": ["Paris", "London", "Rome", "Berlin"],
                    "correct_answer": "London",
                    "explanation": "The speaker says: I live in London.",
                    "points": 1
                }},
                {{
                    "id": 3,
                    "skill": "reading",
                    "difficulty_level": "A1",
                    "question_type": "true_false",
                    "passage": "My name is Sara. I have a small cat. Every morning, my cat sits on a blue mat near the door. It watches the birds and the trees outside. I give it milk and it purrs happily. Then I go to school.",
                    "question": "According to the passage, the cat sat on the mat.",
                    "options": ["True", "False"],
                    "correct_answer": "True",
                    "explanation": "The sentence is a simple declarative statement that is factually correct.",
                    "points": 1
                }},
                {{
                    "id": 4,
                    "skill": "grammar",
                    "difficulty_level": "A2",
                    "question_type": "fill_in_blank",
                    "question": "Yesterday, I _____ to the park.",
                    "options": [],
                    "correct_answer": "went",
                    "explanation": "This requires the past simple tense of the verb 'go'.",
                    "points": 2
                }}
            ]
        }}

        COMPETENCY REQUIREMENTS:
        - A1: Basic vocabulary, present tense, simple sentences
        - A2: Past tense, future tense, everyday vocabulary
        - B1: Conditionals, complex sentences, intermediate vocabulary
        - B2: Passive voice, advanced grammar, formal/informal register
        - C1: Advanced grammar structures, nuanced vocabulary, complex texts
        - C2: Mastery level grammar, sophisticated vocabulary, abstract concepts

        IMPORTANT: Return ONLY the JSON object, nothing else. No comments, no explanations, no markdown.
        """

        try:
            logger.info(f"Starting AI quiz generation with {question_count} questions...")
            # Add timeout to prevent hanging - AI generation can take up to 2 minutes
            response = await asyncio.wait_for(
                asyncio.to_thread(self.gemini_model.generate_content, prompt),
                timeout=120.0  # 2 minute timeout
            )
            logger.info("AI quiz generation completed successfully")
            return {"content": response.text, "success": True}
        except asyncio.TimeoutError:
            logger.error("AI quiz generation timed out after 120 seconds")
            return {"error": "AI generation timed out. Please try again.", "success": False}
        except Exception as e:
            logger.error(f"Error generating level assessment quiz: {e}", exc_info=True)
            return {"error": str(e), "success": False}

    async def generate_personalized_content_recommendations(
        self, 
        user_level: str,
        user_preferences: Dict[str, Any],
        weak_areas: List[str] = None,
        learning_goals: List[str] = None
    ) -> Dict[str, Any]:
        """Generate personalized content recommendations based on user profile"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        weak_areas_text = f"Focus on improving: {', '.join(weak_areas)}" if weak_areas else ""
        goals_text = f"Learning goals: {', '.join(learning_goals)}" if learning_goals else ""
        
        prompt = f"""
        Create personalized learning content recommendations for an English learner with the following profile:
        
        Current Level: {user_level}
        Preferences: {user_preferences}
        {weak_areas_text}
        {goals_text}
        
        Generate recommendations for:
        1. Reading texts (3 recommendations)
        2. Vocabulary topics (3 recommendations) 
        3. Grammar focus areas (3 recommendations)
        4. Speaking/conversation topics (3 recommendations)
        5. Writing exercises (3 recommendations)
        
        Each recommendation should include:
        - Specific topic/content
        - Why it's suitable for this user
        - Expected learning outcome
        - Estimated study time
        
        Format as JSON:
        {{
            "reading_recommendations": [
                {{
                    "topic": "...",
                    "text_type": "article|story|news|dialogue",
                    "reason": "...",
                    "learning_outcome": "...",
                    "estimated_time_minutes": 15
                }}
            ],
            "vocabulary_recommendations": [
                {{
                    "topic": "...",
                    "word_count": 20,
                    "reason": "...",
                    "learning_outcome": "...",
                    "estimated_time_minutes": 10
                }}
            ],
            "grammar_recommendations": [
                {{
                    "topic": "...",
                    "focus_area": "...",
                    "reason": "...",
                    "learning_outcome": "...",
                    "estimated_time_minutes": 20
                }}
            ],
            "speaking_recommendations": [
                {{
                    "topic": "...",
                    "activity_type": "conversation|pronunciation|monologue",
                    "reason": "...",
                    "learning_outcome": "...",
                    "estimated_time_minutes": 15
                }}
            ],
            "writing_recommendations": [
                {{
                    "topic": "...",
                    "writing_type": "email|essay|story|letter",
                    "reason": "...",
                    "learning_outcome": "...",
                    "estimated_time_minutes": 25
                }}
            ]
        }}
        """

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            return {"content": response.text, "success": True}
        except Exception as e:
            logger.error(f"Error generating personalized recommendations: {e}")
            return {"error": str(e), "success": False}

    async def generate_personal_trainer_response(
        self,
        user_message: str,
        user_profile: Dict[str, Any],
        conversation_history: List[Dict[str, Any]] = None,
        current_lesson_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate personalized AI trainer response based on user context"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        history_context = ""
        if conversation_history:
            recent_history = conversation_history[-5:]  # Last 5 interactions
            history_context = "\n".join([
                f"User: {h.get('user_message', '')}\nTrainer: {h.get('trainer_response', '')}"
                for h in recent_history
            ])

        lesson_context = ""
        if current_lesson_context:
            lesson_context = f"""
            Current lesson context:
            - Topic: {current_lesson_context.get('topic', 'General')}
            - Skill focus: {current_lesson_context.get('skill', 'Mixed')}
            - Difficulty: {current_lesson_context.get('level', user_profile.get('current_level', 'A1'))}
            """

        # Build a neutral, optional native-language line. We deliberately
        # do NOT default to any specific language — SELM ships globally.
        native_lang = user_profile.get("native_language")
        native_line = (
            f"  - native language: {native_lang} (use only if it helps "
            f"avoid known L1 interference patterns)\n"
            if native_lang
            else ""
        )

        learner_block = build_learner_context(
            user_profile, include_history_hint=bool(history_context)
        )

        level = user_profile.get("current_level", "A1")

        prompt = f"""You are an AI English-language coach. The learner just
sent you a message — respond like a real tutor: address the actual question
or moment, calibrate to the learner's level, and keep the tone warm without
being saccharine.

{learner_block}
{native_line}
{cefr_block(level)}

{HUMAN_VOICE_RULES}

{lesson_context}

Recent conversation:
{history_context if history_context else "(This is the start of the conversation.)"}

Learner's message:
\"\"\"
{user_message}
\"\"\"

RESPONSE RULES
  • Address the actual question first. Don't pad with "Great question!".
  • Write the trainer_response in English at or slightly above the
    learner's CEFR level — never below, to nudge growth — but always
    decodable. If you use a word that's clearly beyond level, gloss it
    in parentheses on first use.
  • If the learner made a small mistake, correct ONE meaningful issue
    explicitly (not every minor slip — pick the most useful). Add it to
    the "corrections" array with the rule. If they made no mistakes,
    return an empty corrections array.
  • Suggest 1–3 concrete next actions, each tied to something they can
    do in the app (a specific lesson type, a 5-minute drill, etc.).
  • End with one open follow-up question that nudges them to produce
    English back, not just consume it.

Return ONLY valid JSON:
{{
    "trainer_response": "...",
    "message_type": "encouragement|correction|explanation|instruction|assessment",
    "corrections": [
        {{"original": "...", "corrected": "...", "explanation": "..."}}
    ],
    "suggested_actions": [
        {{"action": "...", "description": "...", "estimated_time_minutes": 10}}
    ],
    "follow_up_questions": ["..."],
    "vocabulary_highlights": [
        {{"word": "...", "definition": "...", "example": "..."}}
    ]
}}"""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            return {"content": response.text, "success": True}
        except Exception as e:
            logger.error(f"Error generating trainer response: {e}")
            return {"error": str(e), "success": False}

    async def generate_structured_content(
        self,
        prompt: str,
        content_type: str,
        user_context: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """Generate structured content using AI"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        context_str = ""
        if user_context:
            context_str = f"""
User Context:
- Current Level: {user_context.get('current_level', 'Unknown')}
- Learning Goals: {', '.join(user_context.get('learning_goals', []))}
- Areas for Improvement: {', '.join(user_context.get('weak_areas', []))}
- Preferred Categories: {', '.join(user_context.get('preferred_categories', []))}
"""

        full_prompt = f"""{context_str}

{content_type.upper()} GENERATION REQUEST:
{prompt}

Please provide a well-structured response in JSON format."""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content,
                full_prompt
            )

            return {
                "success": True,
                "content": response.text.strip()
            }
        except Exception as e:
            logger.error(f"Error generating structured content: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def analyze_assessment_results(
        self,
        *,
        answers: List[Dict[str, Any]],
        heuristic_overall_score: float,
        heuristic_skill_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """Use Gemini to analyze assessment answers and produce level, scores, and feedback."""
        if not self.gemini_model:
            return {"success": False, "error": "Gemini API not configured"}

        try:
            preview = []
            for a in answers[:10]:
                preview.append({
                    "question_id": a.get("question_id"),
                    "selected_answer": a.get("selected_answer"),
                    "is_correct": a.get("is_correct"),
                    "time_spent": a.get("time_spent"),
                })

            prompt = (
                "You are an English assessment engine. Based on the following summary of a user's answers, "
                "determine the user's CEFR level (A1,A2,B1,B2,C1,C2) and provide numeric scores.\n\n"
                f"Heuristic overall score (0-100): {round(heuristic_overall_score,2)}\n"
                f"Heuristic skill scores (0-100): {heuristic_skill_scores}\n"
                f"Sample of answers (up to 10): {preview}\n\n"
                "Respond ONLY in strict JSON with this schema: {\n"
                "  \"determined_level\": \"B1\",\n"
                "  \"overall_score\": 72.5,\n"
                "  \"skill_scores\": {\n"
                "    \"grammar\": 68, \"vocabulary\": 74, \"reading\": 70, \"listening\": 65\n"
                "  },\n"
                "  \"feedback\": \"One paragraph summarizing strengths and weaknesses.\",\n"
                "  \"recommendations\": [\"short actionable tip 1\", \"tip 2\"]\n"
                "}"
            )

            response = await asyncio.to_thread(self.gemini_model.generate_content, prompt)
            content = getattr(response, "text", None) or ""

            import re, json as _json
            json_match = re.search(r"\{[\s\S]*\}", content)
            json_str = json_match.group(0) if json_match else content.strip()
            data = _json.loads(json_str)

            level = str(data.get("determined_level", "B1")).upper()
            if level not in {"A1","A2","B1","B2","C1","C2"}:
                level = "B1"
            overall = float(data.get("overall_score", heuristic_overall_score))
            skills = data.get("skill_scores", {}) or {}
            for k in ["grammar","vocabulary","reading","listening"]:
                if k not in skills:
                    skills[k] = float(heuristic_skill_scores.get(k, overall))
            feedback = data.get("feedback") or "Great effort. Keep practicing consistently to improve across skills."
            recs = data.get("recommendations") or [
                "Study 20 minutes daily with mixed skills.",
                "Review grammar basics and expand vocabulary via reading.",
            ]

            return {
                "success": True,
                "determined_level": level,
                "overall_score": float(round(overall, 2)),
                "skill_scores": {k: float(round(float(v), 2)) for k, v in skills.items()},
                "feedback": str(feedback),
                "recommendations": [str(r) for r in recs],
            }
        except Exception as e:
            logger.error(f"Error analyzing assessment with Gemini: {e}")
            return {"success": False, "error": str(e)}

    async def assess_writing(
        self,
        text: str,
        writing_type: str = "general",
        user_level: str = "B1",
        task_prompt: str = ""
    ) -> Dict[str, Any]:
        """
        Assess a writing submission and provide detailed feedback with specific errors.

        Args:
            text: The written text to assess
            writing_type: Type of writing (essay, email, letter, story, description, opinion)
            user_level: User's CEFR level (A1-C2)
            task_prompt: The original task the user was asked to complete. When
                supplied, Task Achievement is graded against this prompt; otherwise
                only general writing quality is graded.

        Returns:
            Comprehensive assessment with scores, errors, and suggestions
        """
        if not self.gemini_model:
            return {"success": False, "error": "Gemini API not configured"}

        # Inject the original task into the AI prompt so the assessor can judge
        # whether the user actually addressed it. Without this, scores like
        # `task_achievement_score` and `feedback` end up generic.
        task_block = (
            f'\n        TASK THE STUDENT WAS GIVEN:\n        "{task_prompt.strip()}"\n'
            if task_prompt and task_prompt.strip()
            else ""
        )

        prompt = f"""You are an experienced English writing examiner.
Assess this {writing_type} written by a {user_level}-level learner.
Judge it against the level criteria below — not against native-speaker
prose — and explain every error so the writer learns the rule, not just
the fix.{task_block}
{cefr_block(user_level)}

TEXT TO ANALYZE:
\"\"\"
{text}
\"\"\"

Be specific about errors and give clear corrections. If a TASK was
given above, judge how well the response addresses it
(Task Achievement). For each error: show the exact wrong phrase, the
fixed version, and one-line teaching of the underlying rule.
        
SCORING SCALE — 0 to 100. Use these anchors. They are the definition of
the scale, not examples:
  90-100  No error that would be noticed. Range and control beyond the level.
  75-89   Occasional slips that do not impede meaning. Solidly at the level.
  60-74   Errors are noticeable and recurring but meaning is clear throughout.
  45-59   Errors impede meaning in places. The reader has to reread.
  30-44   Frequent breakdown. Meaning recoverable only with effort.
  0-29    Meaning is largely not recoverable, or the response is off-task.

Score each criterion independently against these anchors. Do not converge
the four criteria toward one another and do not anchor on the numbers used
in the JSON shape below — they are placeholders showing the format, not
scores to reproduce.

        Return ONLY valid JSON (no markdown):
        {{
            "overall_score": 0,
            "grammar_score": 0,
            "vocabulary_score": 0,
            "coherence_score": 0,
            "task_achievement_score": 0,
            
            "feedback": "Overall assessment of the writing in 2-3 sentences",
            
            "strengths": [
                "Specific thing the student did well",
                "Another strength with example from text"
            ],
            
            "weaknesses": [
                "Area that needs improvement with specific example",
                "Another weakness to work on"
            ],
            
            "errors": [
                {{
                    "type": "grammar|spelling|vocabulary|punctuation|structure",
                    "original": "The exact wrong text from the writing",
                    "corrected": "The corrected version",
                    "explanation": "Clear explanation of why this is wrong and the rule",
                    "severity": "minor|moderate|major"
                }}
            ],
            
            "vocabulary_suggestions": [
                {{
                    "original_word": "word used in text",
                    "better_alternatives": ["synonym1", "synonym2"],
                    "context": "When to use each alternative"
                }}
            ],
            
            "suggestions": [
                "Specific, actionable tip to improve",
                "Another concrete suggestion with example",
                "Practice recommendation"
            ],
            
            "next_steps": [
                "Review [specific grammar rule]",
                "Practice writing [specific type of sentences]",
                "Learn vocabulary about [topic]"
            ],
            
            "corrected_version": "The full text rewritten with all corrections applied (optional, only if there are significant errors)",
            
            "recommended_exercises": [
                {{
                    "type": "grammar|vocabulary|writing",
                    "topic": "Specific topic to practice",
                    "reason": "Why this will help"
                }}
            ]
        }}
        
        IMPORTANT:
        - Be encouraging but honest
        - Every error must include the EXACT original text and correction
        - Explanations should teach the rule, not just fix the mistake
        - Suggestions should be specific and actionable
        - If the writing is very short, note that more content would help assessment
        """

        try:
            # Deterministic decoding for the writing assessor.
            #
            # Measured on production 2026-08-25, before this change: the same
            # weak response scored 75 on ten of ten identical calls — exactly
            # the placeholder value that used to sit in the JSON shape below —
            # while a strong response moved 40 points on one criterion between
            # two calls seconds apart. The sampler was at the model default and
            # the scale had no definition anywhere in the prompt, so the only
            # numeric information the model had was the example.
            #
            # Pin the sampler, ask for JSON directly instead of parsing it out
            # of free text, and define the scale in the prompt.
            response = await asyncio.to_thread(
                functools.partial(
                    self.gemini_model.generate_content,
                    prompt,
                    generation_config={
                        "temperature": 0.0,
                        "top_p": 1.0,
                        "top_k": 1,
                        "candidate_count": 1,
                        "response_mime_type": "application/json",
                    },
                )
            )
            
            # Parse the response
            import json
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            assessment = json.loads(response_text.strip())
            
            return {
                "success": True,
                "content": assessment
            }
            
        except json.JSONDecodeError as e:
            # A parse failure is a failure.
            #
            # This used to return success: True with 70 in every field —
            # the same fabricated assessment the endpoint error paths
            # returned, indistinguishable downstream from a real one, and
            # uncountable in any measurement of how often the judge
            # actually works.
            #
            # The call now requests application/json directly, so this
            # branch should be unreachable. If it is ever reached, that is
            # information worth having, not information worth hiding.
            logger.error("writing assessment returned unparseable JSON: %s", e)
            return {"success": False, "error": "judge returned unparseable output"}
        except Exception as e:
            logger.error(f"Error assessing writing: {e}")
            return {"success": False, "error": str(e)}

# Global AI service instance
ai_service = AIService() 