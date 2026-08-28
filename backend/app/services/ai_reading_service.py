import asyncio
import json
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import logging

from app.core.config import settings
from app.crud.content import vocabulary_crud
from app.models.content import DifficultyLevel, Vocabulary
from app.models.reading import ReadingTextType
from app.services.language_profile import profile_for

logger = logging.getLogger(__name__)

class AIReadingService:
    def __init__(self):
        # 2026-05-13: upgraded from FAST (flash-lite) to CONTENT (pro)
        # because reading passages are the highest-stakes prose the app
        # produces — quality at multi-paragraph scale matters far more
        # than per-call latency here. Falls back to FAST on init error.
        if settings.GOOGLE_GEMINI_API_KEY:
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
            content_name = getattr(
                settings, "GEMINI_TEXT_MODEL_CONTENT", None
            ) or getattr(settings, "GEMINI_TEXT_MODEL_FAST", "gemini-2.5-flash-lite")
            try:
                self.gemini_model = genai.GenerativeModel(content_name)
                logger.info(
                    "AIReadingService using Gemini model: %s", content_name
                )
            except Exception as e:
                fallback = getattr(
                    settings, "GEMINI_TEXT_MODEL_FAST", "gemini-2.5-flash-lite"
                )
                logger.warning(
                    "Failed to init %s for reading, falling back to %s: %s",
                    content_name, fallback, e,
                )
                self.gemini_model = genai.GenerativeModel(fallback)
        else:
            self.gemini_model = None
            logger.warning("Google Gemini API key not configured")

    async def generate_reading_text_with_vocabulary(
        self,
        db: AsyncSession,
        level: DifficultyLevel,
        text_type: ReadingTextType,
        topic: str,
        word_count: int = 200,
        vocabulary_count: int = 10,
        include_comprehension_questions: bool = True,
        original_text: Optional[str] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Generate reading text using leveled vocabulary from database.

        If ``original_text`` is provided, that text is used verbatim (the AI
        does not invent a new passage), and vocabulary + questions are derived
        from it. This powers the Reading → "Paste any English text" flow,
        where the user expects feedback on THEIR text — not a random article.
        """
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        # Branch 1: user supplied their own passage. Use it as-is and just
        # build vocabulary + questions around it.
        if original_text and original_text.strip():
            text_content = original_text.strip()
            vocab_list = await self._extract_vocabulary_from_text(
                text_content, level, vocabulary_count, language=language
            )
            result = {
                "text_content": text_content,
                "vocabulary_used": vocab_list,
                "level": level.value,
                "text_type": text_type.value,
                "topic": topic,
                "word_count": len(text_content.split()),
                # Echoed back so the caller can never be in doubt about what
                # language it just received. The old code returned an English
                # passage whatever was asked for, silently.
                "language": profile_for(language).code,
            }
            if include_comprehension_questions:
                questions = await self._generate_comprehension_questions(
                    text_content, level, vocab_list, language=language
                )
                result["comprehension_questions"] = questions
            return result

        # Branch 2: generate fresh content (the original behaviour).

        # Get vocabulary words for the specified level
        vocabulary_words = await self._get_leveled_vocabulary(
            db, level, topic, vocabulary_count
        )

        if not vocabulary_words:
            # Fallback: use general high-frequency words for the level
            vocabulary_words = await vocabulary_crud.get_by_level(
                db, level=level, limit=vocabulary_count
            )
            logger.warning(f"No topic-specific vocabulary for {level.value}/{topic}; using general words fallback")

        # Create vocabulary list for AI prompt
        vocab_list = []
        for vocab in vocabulary_words:
            vocab_list.append({
                "word": vocab.word,
                "definition": vocab.definition,
                "part_of_speech": vocab.part_of_speech,
                "example": vocab.example_sentence
            })

        # Build the creative seed once at this level so we can
        # (a) hand it down to the generator for prompt diversity, and
        # (b) surface the chosen voice_category to the audio step.
        from app.services.prompt_library import creative_seed
        seed = creative_seed(text_type.value)

        # Generate the reading text
        text_content = await self._generate_text_content(
            level, text_type, topic, word_count, vocab_list, seed=seed, language=language
        )

        result = {
            "text_content": text_content,
            "vocabulary_used": vocab_list,
            "level": level.value,
            "text_type": text_type.value,
            "topic": topic,
            "word_count": len(text_content.split()) if text_content else 0,
            # Voice hint for the TTS layer — pass into
            # `tts.generate_audio_content(speaker_config=[{"voice_category": ...}])`
            "voice_category": seed.get("voice_category"),
            "language": profile_for(language).code,
        }

        # Generate comprehension questions if requested
        if include_comprehension_questions and text_content:
            questions = await self._generate_comprehension_questions(
                text_content, level, vocab_list, language=language
            )
            result["comprehension_questions"] = questions

        return result

    async def _extract_vocabulary_from_text(
        self,
        text: str,
        level: DifficultyLevel,
        count: int,
        language: str = "en",
    ) -> List[Dict[str, Any]]:
        """Pick `count` interesting / level-appropriate words *from the user's text*
        and return definitions + examples for them. Used when the user pasted
        their own passage, so vocab matches the actual reading.
        """
        if not self.gemini_model:
            return []
        from app.services.prompt_library import cefr_block

        lang = profile_for(language)
        prompt = f"""You are {lang.tutor}. {lang.write_in} From the passage
below, pick exactly {count} vocabulary items that genuinely repay
study at this learner's level. Prefer words that:
  • actually appear in the text,
  • help unlock the meaning of the passage,
  • are useful beyond this single passage (high-utility, not one-off
    names/places),
  • match the level spec below — skip items that are obviously below
    level (likely already known) or far above level (unhelpful here).

{cefr_block(level.value)}

PASSAGE
\"\"\"
{text}
\"\"\"

For each item return:
  • "word"            — surface form as it appears (lemmatised if a
                         common inflection).
  • "definition"      — short, learner-friendly, calibrated to level.
  • "part_of_speech"  — noun|verb|adj|adv|phrasal_verb|idiom.
  • "example"         — a NEW sentence (not the passage line) using
                         the word in a clear, concrete situation.
  • "in_text_line"    — the exact line from the passage where the
                         learner can see it in context.

Return ONLY a valid JSON array (no markdown fences):
[
  {{
    "word": "...",
    "definition": "...",
    "part_of_speech": "...",
    "example": "...",
    "in_text_line": "..."
  }}
]"""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, self.gemini_model.generate_content, prompt)
            raw = (response.text or "").strip()
            # strip ```json fences
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                raw = raw.rsplit("```", 1)[0]
            data = json.loads(raw)
            if isinstance(data, list):
                return [
                    {
                        "word": str(d.get("word", "")).strip(),
                        "definition": str(d.get("definition", "")).strip(),
                        "part_of_speech": str(d.get("part_of_speech", "")).strip(),
                        "example": str(d.get("example", "")).strip(),
                        # New: where the word lives in the passage. Frontend
                        # can use this to highlight the in-context line.
                        "in_text_line": str(d.get("in_text_line", "")).strip(),
                    }
                    for d in data if isinstance(d, dict) and d.get("word")
                ]
        except Exception as e:
            logger.warning(f"_extract_vocabulary_from_text failed: {e}")
        return []

    async def _get_leveled_vocabulary(
        self,
        db: AsyncSession,
        level: DifficultyLevel,
        topic: str,
        count: int
    ) -> List[Vocabulary]:
        """Get vocabulary words for specific level and topic"""
        try:
            # First try to get topic-specific vocabulary
            vocabulary = await vocabulary_crud.get_by_level_and_topic(
                db, level=level, topic=topic, limit=count
            )
            
            # If not enough topic-specific words, get general vocabulary for the level
            if len(vocabulary) < count:
                additional_vocab = await vocabulary_crud.get_by_level(
                    db, level=level, limit=count - len(vocabulary)
                )
                vocabulary.extend(additional_vocab)
            
            return vocabulary[:count]
        except Exception as e:
            logger.error(f"Error getting vocabulary: {e}")
            try:
                await db.rollback()
            except Exception:
                pass
            return []

    async def _generate_text_content(
        self,
        level: DifficultyLevel,
        text_type: ReadingTextType,
        topic: str,
        word_count: int,
        vocabulary_list: List[Dict[str, Any]],
        seed: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> str:
        """Generate the actual reading text content - produces meaningful, comprehensive passages.

        2026-05-13: every call now pulls a fresh creative_seed() so two
        requests for the same topic + level produce genuinely different
        texts (different scene, opening hook, perspective, tone, shape),
        not just different vocabulary stuffed into the same skeleton.

        ``seed`` may be provided by the caller (so the caller can also
        access voice_category, protagonist, etc.); if None we build one
        here for backwards compatibility with older call sites.
        """
        from app.services.prompt_library import (
            cefr_block,
            creative_seed,
            render_creative_brief,
            HUMAN_VOICE_RULES,
        )

        # Fresh randomized creative angle for THIS generation. The seed
        # is read by Gemini as part of the brief; we don't store it.
        if seed is None:
            seed = creative_seed(text_type.value if hasattr(text_type, "value") else str(text_type))
        creative_brief = render_creative_brief(seed)

        # Create vocabulary context for the prompt
        vocab_context = "\n".join([
            f"- {item['word']} ({item['part_of_speech']}): {item['definition']}"
            for item in vocabulary_list
        ])

        # Level-specific writing guidelines with detailed instructions.
        #
        # 2026-05-13: word targets bumped substantially across the board.
        # The previous targets (A1=60, B1=180, C2=500) produced skimpy
        # passages that the user flagged as too short. New targets give
        # enough room for the creative_brief (scene → development →
        # turn → resolution) to actually unfold. We also stopped capping
        # the caller-provided ``word_count`` with ``max(word_count, X)``
        # — the level floor now wins so practice sessions are
        # substantive even when the caller's hint is small.
        level_guidelines = {
            DifficultyLevel.A1: {
                "style": "Short sentences (6-10 words), present simple + a little past simple, very common vocabulary, paragraphs of 2-3 sentences each",
                "word_target": max(word_count, 120),
                "sentence_length": "short",
                "topics_hint": "everyday life, family, food, weather, simple descriptions",
            },
            DifficultyLevel.A2: {
                "style": "Simple sentences, present and past tense, some future with 'will'/'going to', familiar everyday topics, clear connectives",
                "word_target": max(word_count, 200),
                "sentence_length": "simple",
                "topics_hint": "daily routines, hobbies, travel basics, shopping, simple feelings",
            },
            DifficultyLevel.B1: {
                "style": "Varied sentence structures with subordinate clauses, all common tenses including present perfect and second conditional, clear logical flow with discourse markers",
                "word_target": max(word_count, 320),
                "sentence_length": "medium",
                "topics_hint": "work, education, health, environment, social issues, personal opinions",
            },
            DifficultyLevel.B2: {
                "style": "Complex sentences with multiple clauses, full range of tenses and conditionals, abstract concepts, detailed descriptions with nuance, hedging language",
                "word_target": max(word_count, 480),
                "sentence_length": "varied",
                "topics_hint": "current events, cultural topics, professional subjects, nuanced arguments",
            },
            DifficultyLevel.C1: {
                "style": "Sophisticated language with idioms, complex argumentation, nuanced expressions, subjunctive where appropriate, advanced cohesion across paragraphs",
                "word_target": max(word_count, 650),
                "sentence_length": "complex",
                "topics_hint": "academic topics, specialised fields, nuanced debates, literary themes",
            },
            DifficultyLevel.C2: {
                "style": "Highly sophisticated near-native language, complex abstract concepts, subtle meanings, register switching for stylistic effect, full grammatical range",
                "word_target": max(word_count, 850),
                "sentence_length": "native-like",
                "topics_hint": "any topic with native-level complexity, including specialised, literary, or technical",
            },
        }

        level_info = level_guidelines.get(level, level_guidelines[DifficultyLevel.B1])

        lang = profile_for(language)
        prompt = f"""You are {lang.writer}. {lang.write_in} You are producing
authentic reading material for adult learners. Write the {text_type.value}
below — a real piece of writing, not a textbook exercise.

TOPIC:  {topic}

{cefr_block(level.value)}

{HUMAN_VOICE_RULES}

{creative_brief}

LENGTH
  • Aim for approximately {level_info['word_target']} words. Going
    10-15% over is fine if the piece earns it; going under is not —
    we want a substantive passage, not a snippet.

WRITING STYLE NOTES
{level_info['style']}

VOCABULARY TO WEAVE IN (naturally — never forced)
{vocab_context}

SUBSTANTIVE DEPTH — non-negotiable
  • Every paragraph must add new information, not restate the last one.
  • Anchor each section in something concrete: a specific moment, a
    named person doing something, a real-world detail (a time, a place,
    a number, a sensory observation). Generic abstraction at any length
    is failure.
  • If a paragraph could be cut without losing meaning, it shouldn't be
    there. Replace filler with substance.
  • Develop ONE idea fully across the passage; don't sprinkle three
    half-formed ideas.

CRITICAL: Two requests for the same topic at the same level MUST produce
genuinely different pieces. Different opening, different scene, different
shape — that's the whole point of the creative brief above. Do not
collapse back into a generic Title → Intro → Body → Conclusion structure
unless the brief explicitly asked for that shape.

=== WHAT TO AVOID ===
- Meta-commentary about the exercise, lesson, or vocabulary list.
- Generic openers ("In today's fast-paced world…", "It is important to…").
- Recycling the same character archetype or scene every time.
- Sentences engineered solely to use a vocabulary word.

=== OUTPUT ===
Write ONLY the {text_type.value} content. Start directly with the title
(only if the structural shape calls for one) or the first sentence."""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            generated_text = response.text.strip()
            
            # Clean up any markdown formatting that might have been added
            if generated_text.startswith("```"):
                lines = generated_text.split("\n")
                generated_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            return generated_text
        except Exception as e:
            logger.error(f"Error generating text content: {e}")
            return ""

    async def _generate_comprehension_questions(
        self,
        text_content: str,
        level: DifficultyLevel,
        vocabulary_list: List[Dict[str, Any]],
        language: str = "en",
    ) -> List[Dict[str, Any]]:
        """Generate comprehension questions for the text"""
        
        from app.services.prompt_library import cefr_block, HUMAN_VOICE_RULES

        target_vocab = ", ".join([v.get("word", "") for v in vocabulary_list if v.get("word")][:8])

        lang = profile_for(language)
        prompt = f"""{lang.write_in} Create 5 comprehension questions based on the passage
below. The questions must test real understanding, not surface recall —
a strong reader at this level should still need to think.

{cefr_block(level.value)}

{HUMAN_VOICE_RULES}

PASSAGE
\"\"\"
{text_content}
\"\"\"

TARGET VOCABULARY (try to test at least 2 of these in context, not
definition-style): {target_vocab}

QUESTION-MIX RULES (exactly 5 total)
  1. One MAIN-IDEA question: "What is the writer's main point?" / "Why
     was X mentioned?" — never answerable by quoting a single line.
  2. One DETAIL question: a specific fact in the text the reader has to
     locate.
  3. One INFERENCE question: requires reading between the lines (tone,
     implication, cause-effect not stated outright).
  4. One VOCABULARY-IN-CONTEXT question: pick a word from the target
     list, give the line it appears in, ask what it means HERE (not the
     dictionary definition — the contextual one).
  5. One PRODUCTION question: short_answer, learner writes 1–2 sentences
     applying the text to their own life or opinion.

PER QUESTION
  • multiple_choice items need 4 plausible options. The wrong ones must
    be defensible misreads, not nonsense.
  • true_false items need a one-line justification in "explanation".
  • short_answer items get a model answer plus 1–2 lines of marking
    guidance (what makes an acceptable answer).
  • Every "explanation" should teach — point at the line(s) of evidence
    in the passage and explain the reasoning.

Return ONLY a valid JSON array (no markdown fences):
[
  {{
    "question_type": "main_idea|detail|inference|vocabulary_in_context|production",
    "type": "multiple_choice|true_false|short_answer",
    "question": "...",
    "options": ["..."],          // [] for short_answer
    "correct_answer": "...",     // model answer for short_answer
    "explanation": "...",
    "evidence": "the line or paragraph the answer comes from (paste it)"
  }}
]"""

        try:
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            
            # Parse the JSON response
            questions_text = response.text.strip()
            if questions_text.startswith('```json'):
                questions_text = questions_text[7:-3]
            elif questions_text.startswith('```'):
                questions_text = questions_text[3:-3]
            
            questions = json.loads(questions_text)
            return questions
        except Exception as e:
            logger.error(f"Error generating comprehension questions: {e}")
            return []

    async def generate_reading_text_batch(
        self,
        db: AsyncSession,
        level: DifficultyLevel,
        topics: List[str],
        text_types: List[ReadingTextType],
        count_per_combination: int = 1
    ) -> List[Dict[str, Any]]:
        """Generate multiple reading texts in batch"""
        results = []
        
        for topic in topics:
            for text_type in text_types:
                for _ in range(count_per_combination):
                    try:
                        result = await self.generate_reading_text_with_vocabulary(
                            db=db,
                            level=level,
                            text_type=text_type,
                            topic=topic,
                            word_count=200 if level in [DifficultyLevel.A1, DifficultyLevel.A2] else 300,
                            vocabulary_count=8 if level in [DifficultyLevel.A1, DifficultyLevel.A2] else 12
                        )
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Error generating text for {topic}/{text_type}: {e}")
                        continue
        
        return results

    async def enhance_existing_text_with_vocabulary(
        self,
        db: AsyncSession,
        text_content: str,
        level: DifficultyLevel,
        vocabulary_count: int = 10
    ) -> Dict[str, Any]:
        """Enhance existing text by adding vocabulary highlights and exercises"""
        
        # Get relevant vocabulary for the level
        vocabulary_words = await vocabulary_crud.get_by_level(
            db, level=level, limit=vocabulary_count * 2  # Get more to have options
        )
        
        # Find vocabulary words that appear in the text
        text_lower = text_content.lower()
        found_vocabulary = []
        
        for vocab in vocabulary_words:
            if vocab.word.lower() in text_lower:
                found_vocabulary.append({
                    "word": vocab.word,
                    "definition": vocab.definition,
                    "part_of_speech": vocab.part_of_speech,
                    "position": text_lower.find(vocab.word.lower())
                })
        
        # Sort by position in text
        found_vocabulary.sort(key=lambda x: x["position"])
        
        return {
            "original_text": text_content,
            "vocabulary_highlights": found_vocabulary[:vocabulary_count],
            "level": level.value,
            "vocabulary_count": len(found_vocabulary)
        }

# Global AI reading service instance
ai_reading_service = AIReadingService() 