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

logger = logging.getLogger(__name__)

class AIReadingService:
    def __init__(self):
        # Configure Google Gemini
        if settings.GOOGLE_GEMINI_API_KEY:
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel(settings.GEMINI_TEXT_MODEL_FAST)
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
        include_comprehension_questions: bool = True
    ) -> Dict[str, Any]:
        """
        Generate reading text using leveled vocabulary from database
        
        Args:
            db: Database session
            level: CEFR level (A1, A2, B1, B2, C1, C2)
            text_type: Type of reading text (article, story, news, etc.)
            topic: Topic for the text (travel, business, daily life, etc.)
            word_count: Target word count for the text
            vocabulary_count: Number of vocabulary words to include
            include_comprehension_questions: Whether to generate questions
        
        Returns:
            Dictionary containing generated text, vocabulary, and questions
        """
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

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

        # Generate the reading text
        text_content = await self._generate_text_content(
            level, text_type, topic, word_count, vocab_list
        )

        result = {
            "text_content": text_content,
            "vocabulary_used": vocab_list,
            "level": level.value,
            "text_type": text_type.value,
            "topic": topic,
            "word_count": len(text_content.split()) if text_content else 0
        }

        # Generate comprehension questions if requested
        if include_comprehension_questions and text_content:
            questions = await self._generate_comprehension_questions(
                text_content, level, vocab_list
            )
            result["comprehension_questions"] = questions

        return result

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
        vocabulary_list: List[Dict[str, Any]]
    ) -> str:
        """Generate the actual reading text content - produces meaningful, comprehensive passages"""
        
        # Create vocabulary context for the prompt
        vocab_context = "\n".join([
            f"- {item['word']} ({item['part_of_speech']}): {item['definition']}"
            for item in vocabulary_list
        ])

        # Level-specific writing guidelines with detailed instructions
        level_guidelines = {
            DifficultyLevel.A1: {
                "style": "Use very simple sentences (5-8 words), present tense only, basic vocabulary, short paragraphs (2-3 sentences each)",
                "word_target": max(word_count, 60),
                "sentence_length": "short",
                "topics_hint": "everyday life, family, food, weather, simple descriptions"
            },
            DifficultyLevel.A2: {
                "style": "Use simple sentences, present and past tense, familiar everyday topics, clear structure with transitions",
                "word_target": max(word_count, 100),
                "sentence_length": "simple",
                "topics_hint": "daily routines, hobbies, travel basics, shopping"
            },
            DifficultyLevel.B1: {
                "style": "Use varied sentence structures with some complex sentences, multiple tenses including present perfect, clear logical flow",
                "word_target": max(word_count, 180),
                "sentence_length": "medium",
                "topics_hint": "work, education, health, environment, social issues"
            },
            DifficultyLevel.B2: {
                "style": "Use complex sentence structures, various tenses and conditionals, abstract concepts, detailed descriptions with nuance",
                "word_target": max(word_count, 280),
                "sentence_length": "varied",
                "topics_hint": "current events, cultural topics, professional subjects, opinions"
            },
            DifficultyLevel.C1: {
                "style": "Use sophisticated language with idioms, complex ideas and argumentation, nuanced expressions, advanced cohesion",
                "word_target": max(word_count, 400),
                "sentence_length": "complex",
                "topics_hint": "academic topics, specialized fields, nuanced debates, literary themes"
            },
            DifficultyLevel.C2: {
                "style": "Use highly sophisticated native-like language, complex abstract concepts, subtle meanings, academic register when appropriate",
                "word_target": max(word_count, 500),
                "sentence_length": "native-like",
                "topics_hint": "any topic with native-level complexity"
            }
        }

        # Text type specific instructions with examples
        text_type_instructions = {
            ReadingTextType.ARTICLE: {
                "format": "Write an informative article with a compelling title, engaging introduction, informative body paragraphs with facts and examples, and a conclusion",
                "structure": "Title → Introduction (hook + thesis) → Body (2-3 paragraphs with facts) → Conclusion"
            },
            ReadingTextType.STORY: {
                "format": "Write an engaging narrative story with interesting characters, a clear setting, a problem/conflict, and a resolution",
                "structure": "Setting/Characters → Problem/Conflict → Rising action → Resolution"
            },
            ReadingTextType.NEWS: {
                "format": "Write a news article following journalistic standards: who, what, when, where, why, how",
                "structure": "Headline → Lead paragraph (main facts) → Supporting details → Background → Quotes if relevant"
            },
            ReadingTextType.LETTER: {
                "format": "Write a letter with appropriate greeting, clear purpose, supporting details, and proper closing",
                "structure": "Greeting → Purpose → Details → Request/Action → Closing"
            },
            ReadingTextType.ESSAY: {
                "format": "Write a structured essay with clear thesis, supporting arguments, and conclusion",
                "structure": "Introduction (thesis) → Body paragraphs (arguments + evidence) → Conclusion"
            },
            ReadingTextType.DIALOGUE: {
                "format": "Write a natural conversation between 2-3 people with realistic exchanges",
                "structure": "Context setting → Natural dialogue exchange → Resolution/Ending"
            },
            ReadingTextType.INSTRUCTION: {
                "format": "Write clear step-by-step instructions that are easy to follow",
                "structure": "Introduction/Purpose → Materials/Prerequisites → Step-by-step instructions → Tips/Conclusion"
            }
        }

        level_info = level_guidelines.get(level, level_guidelines[DifficultyLevel.B1])
        type_info = text_type_instructions.get(text_type, text_type_instructions[ReadingTextType.ARTICLE])

        prompt = f"""You are an expert English language content creator specializing in creating authentic, engaging reading materials for language learners.

Create a {text_type.value} in English about "{topic}" for CEFR {level.value} level learners.

=== CONTENT REQUIREMENTS ===
• Word count: approximately {level_info['word_target']} words
• CEFR Level: {level.value}
• Text type: {text_type.value}

=== WRITING STYLE ===
{level_info['style']}

=== TEXT STRUCTURE ===
{type_info['format']}
Structure: {type_info['structure']}

=== VOCABULARY TO INCORPORATE ===
Naturally weave these vocabulary words into your text:
{vocab_context}

=== CRITICAL QUALITY GUIDELINES ===
1. CREATE AUTHENTIC CONTENT: Write as if this were a real {text_type.value} from a magazine, newspaper, or book - NOT a textbook exercise
2. MEANINGFUL CONTENT: Include interesting facts, real-world information, or engaging narrative elements
3. NATURAL FLOW: The text should read naturally; vocabulary words should fit seamlessly, not feel forced
4. CULTURAL RELEVANCE: Include references that make the content feel contemporary and relevant
5. EDUCATIONAL VALUE: Readers should learn something new or be engaged by the content
6. PROPER FORMATTING: Use appropriate paragraphs, and include a title if applicable

=== WHAT TO AVOID ===
- Do NOT write meta-commentary about the exercise or lesson
- Do NOT reference "learning vocabulary" or "practice reading" within the text
- Do NOT create artificial or stilted sentences just to include vocabulary words
- Do NOT write generic placeholder content
- Do NOT reference previous lessons or what the student has learned

=== OUTPUT ===
Write ONLY the {text_type.value} content. Start directly with the title (if applicable) or the first sentence.
Make this a piece of writing that would be interesting to read in any context, not just as a language exercise."""

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
        vocabulary_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate comprehension questions for the text"""
        
        prompt = f"""
        Based on the following text, create 5 comprehension questions appropriate for {level.value} level students.
        
        Text:
        {text_content}
        
        Create questions that:
        1. Test understanding of main ideas
        2. Check comprehension of details
        3. Test vocabulary understanding (use some of these words: {', '.join([v['word'] for v in vocabulary_list])})
        4. Are appropriate for {level.value} level
        
        Format each question as JSON with this structure:
        {{
            "question": "What is the main idea of the text?",
            "type": "multiple_choice",
            "options": ["A", "B", "C", "D"],
            "correct_answer": "A",
            "explanation": "The answer is A because..."
        }}
        
        Include different question types: multiple_choice, true_false, short_answer.
        Return as a JSON array of questions.
        """

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