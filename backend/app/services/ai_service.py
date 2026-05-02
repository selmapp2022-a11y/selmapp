import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from gtts import gTTS
import io
import base64
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        # Configure Google Gemini
        if settings.GOOGLE_GEMINI_API_KEY:
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
            # Use configurable models
            try:
                self.gemini_model = genai.GenerativeModel(settings.GEMINI_TEXT_MODEL_FAST)
                logger.info(f"Gemini model initialized: {settings.GEMINI_TEXT_MODEL_FAST}")
            except Exception as e:
                logger.error(f"Failed to init Gemini model {settings.GEMINI_TEXT_MODEL_FAST}: {e}")
                self.gemini_model = None
        else:
            self.gemini_model = None
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

        prompt = f"""You are an expert English teacher creating a lesson + practice set.

Topic: {topic}
CEFR Level: {difficulty_level}  
Exercise Type: {exercise_type}
Number of practice questions: {count}

IMPORTANT STRUCTURE:
1. Create a LESSON section first with vocabulary and grammar explanation
2. Then create practice exercises
3. The "vocabulary_words" array at the TOP LEVEL must be IDENTICAL to lesson.vocabulary_words (this is for UI display)

For vocabulary items, include ALL these fields:
- word: the vocabulary word
- part_of_speech: noun/verb/adjective/etc
- definition: clear definition
- simple_explanation: easy explanation for the learner
- example_sentence: sentence using the word in context
- usage_tip: helpful tip on how to use it

For grammar (if exercise_type is "grammar"), include in grammar_summary:
- title: the grammar rule name
- explanation: clear explanation
- examples: 3-5 example sentences
- common_mistakes: 2-3 mistakes to avoid

Return ONLY valid JSON (no markdown, no code blocks):
{{
  "topic": "{topic}",
  "level": "{difficulty_level}",
  "lesson": {{
    "objective": "one sentence learning goal",
    "vocabulary_words": [
      {{
        "word": "example",
        "part_of_speech": "noun",
        "definition": "a thing characteristic of its kind",
        "simple_explanation": "something that shows what other things are like",
        "example_sentence": "This is an example of good writing.",
        "usage_tip": "Use 'for example' to introduce examples"
      }}
    ],
    "grammar_point": {{
      "title": "Grammar Rule Name",
      "explanation": "Clear explanation of the rule",
      "examples": ["Example sentence 1", "Example sentence 2"],
      "common_mistakes": ["Common mistake 1", "Common mistake 2"]
    }}
  }},
  "vocabulary_words": [COPY THE SAME ARRAY FROM lesson.vocabulary_words HERE],
  "grammar_summary": {{
    "title": "Grammar Rule Name",
    "explanation": "Clear explanation",
    "examples": ["Example 1", "Example 2"],
    "common_mistakes": ["Mistake 1", "Mistake 2"]
  }},
  "exercises": [
    {{
      "question": "Question text here",
      "type": "multiple_choice",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "Option A",
      "explanation": "Why this is the correct answer",
      "target": "vocabulary"
    }}
  ]
}}

Generate 8-12 vocabulary words appropriate for {difficulty_level} level about "{topic}".
Generate {count} practice exercises."""

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

    async def check_grammar(self, text: str) -> Dict[str, Any]:
        """Check grammar and provide corrections"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        prompt = f"""
        Check the following English text for grammar errors and provide corrections:
        
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

        prompt = f"""You are an expert English teacher providing detailed feedback on a grammar practice question.

Question: {question}
Options: [{options_str}]
Student's Answer: {selected_answer}
Correct Answer: {correct_answer}
Grammar Topic: {grammar_rule if grammar_rule else "General grammar"}
Student Level: {user_level}

The student answered {"CORRECTLY" if is_correct else "INCORRECTLY"}.

Provide helpful, encouraging feedback that helps the student understand WHY the correct answer is correct.

Return ONLY valid JSON (no markdown):
{{
    "is_correct": {str(is_correct).lower()},
    "explanation": "2-3 sentences explaining why '{correct_answer}' is the correct answer. Be specific about the grammar rule.",
    "rule_explanation": "Clear explanation of the grammar rule being tested, with the rule name if applicable.",
    "examples": ["Example sentence 1 using this grammar correctly", "Example sentence 2", "Example sentence 3"],
    "common_mistakes": ["A common mistake learners make with this grammar point", "Another common error to avoid"],
    "tip": "A helpful tip for remembering or applying this grammar rule correctly.",
    "why_wrong": "{'' if is_correct else 'Explain specifically why the selected answer is incorrect and what it would mean if used.'}"
}}
"""

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
        self, word: str, level: str
    ) -> Dict[str, Any]:
        """Generate vocabulary explanation with examples"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        prompt = f"""
        Provide a comprehensive explanation of the English word "{word}" for {level} level students.
        
        Include:
        1. Definition (simple and clear)
        2. Part of speech
        3. Pronunciation guide
        4. 3 example sentences
        5. Common collocations
        6. Synonyms and antonyms (if applicable)
        7. Usage notes
        
        Format as JSON:
        {{
            "word": "{word}",
            "definition": "...",
            "part_of_speech": "...",
            "pronunciation": "...",
            "examples": ["...", "...", "..."],
            "collocations": ["...", "..."],
            "synonyms": ["...", "..."],
            "antonyms": ["...", "..."],
            "usage_notes": "..."
        }}
        """

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
        """Generate audio from text using Google TTS"""
        try:
            tts = gTTS(text=text, lang=language, slow=slow)
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            return audio_buffer.getvalue()
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None

    async def analyze_pronunciation(
        self, audio_data: bytes, expected_text: str
    ) -> Dict[str, Any]:
        """Analyze pronunciation (placeholder for ELSA API integration)"""
        # This would integrate with ELSA API or similar service
        # For now, return a mock response
        return {
            "score": 85.0,
            "feedback": "Good pronunciation overall. Work on the 'th' sound.",
            "word_scores": [
                {"word": "hello", "score": 90},
                {"word": "world", "score": 80}
            ],
            "suggestions": [
                "Practice the 'th' sound by placing your tongue between your teeth"
            ]
        }

    async def generate_conversation_practice(
        self, topic: str, level: str, turns: int = 6
    ) -> Dict[str, Any]:
        """Generate conversation practice scenarios"""
        if not self.gemini_model:
            raise ValueError("Gemini API not configured")

        prompt = f"""
        Create a conversation practice scenario for {level} level English students.
        Topic: {topic}
        Number of turns: {turns}
        
        Create a realistic dialogue between two people with:
        1. Natural conversation flow
        2. Appropriate vocabulary for {level} level
        3. Common phrases and expressions
        4. Cultural context
        
        Format as JSON:
        {{
            "scenario": "...",
            "dialogue": [
                {{"speaker": "A", "text": "..."}},
                {{"speaker": "B", "text": "..."}}
            ],
            "vocabulary": ["word1", "word2", ...],
            "phrases": ["phrase1", "phrase2", ...],
            "cultural_notes": "..."
        }}
        """

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

        prompt = f"""
        You are an AI English learning trainer. Respond to the user's message with a helpful, encouraging, and educational response.
        
        User Profile:
        - Current Level: {user_profile.get('current_level', 'A1')}
        - Native Language: {user_profile.get('native_language', 'Persian')}
        - Learning Goals: {', '.join(user_profile.get('learning_goals', []))}
        - Preferred Categories: {', '.join(user_profile.get('preferred_categories', []))}
        - Learning Style: {user_profile.get('learning_style', 'mixed')}
        - Daily Study Time: {user_profile.get('daily_study_commitment', 30)} minutes
        
        {lesson_context}
        
        Recent Conversation History:
        {history_context if history_context else "This is the start of the conversation."}
        
        User's Message: "{user_message}"
        
        Respond as a supportive English teacher who:
        1. Addresses the user's specific question or need
        2. Provides clear, level-appropriate explanations
        3. Gives practical examples and usage tips
        4. Suggests next learning steps
        5. Maintains an encouraging and motivating tone
        6. Uses simple language appropriate for their level
        
        If the user made any English errors, gently correct them with explanations.
        If they're asking for help with specific grammar/vocabulary, provide clear explanations with examples.
        If they're sharing progress or concerns, respond with encouragement and actionable advice.
        
        Format as JSON:
        {{
            "trainer_response": "...",
            "message_type": "encouragement|correction|explanation|instruction|assessment",
            "corrections": [
                {{
                    "original": "...",
                    "corrected": "...",
                    "explanation": "..."
                }}
            ],
            "suggested_actions": [
                {{
                    "action": "...",
                    "description": "...",
                    "estimated_time_minutes": 10
                }}
            ],
            "follow_up_questions": ["...", "..."],
            "vocabulary_highlights": [
                {{
                    "word": "...",
                    "definition": "...",
                    "example": "..."
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
        user_level: str = "B1"
    ) -> Dict[str, Any]:
        """
        Assess a writing submission and provide detailed feedback with specific errors.
        
        Args:
            text: The written text to assess
            writing_type: Type of writing (essay, email, letter, story, description, opinion)
            user_level: User's CEFR level (A1-C2)
            
        Returns:
            Comprehensive assessment with scores, errors, and suggestions
        """
        if not self.gemini_model:
            return {"success": False, "error": "Gemini API not configured"}

        prompt = f"""
        You are an expert English writing teacher. Analyze this {writing_type} written by a {user_level} level student.
        
        TEXT TO ANALYZE:
        "{text}"
        
        Provide a comprehensive, educational assessment. Be specific about errors and give clear corrections.
        Focus on being helpful - show EXACTLY what was wrong and HOW to fix it.
        
        Return ONLY valid JSON (no markdown):
        {{
            "overall_score": 75,
            "grammar_score": 70,
            "vocabulary_score": 80,
            "coherence_score": 75,
            "task_achievement_score": 78,
            
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
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
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
            logger.error(f"Failed to parse writing assessment JSON: {e}")
            # Return a basic assessment if parsing fails
            return {
                "success": True,
                "content": {
                    "overall_score": 70,
                    "grammar_score": 70,
                    "vocabulary_score": 70,
                    "coherence_score": 70,
                    "task_achievement_score": 70,
                    "feedback": "Your writing shows good effort. Keep practicing to improve your skills.",
                    "strengths": ["Good attempt at expressing ideas"],
                    "weaknesses": ["Could benefit from more practice"],
                    "errors": [],
                    "vocabulary_suggestions": [],
                    "suggestions": [
                        "Continue practicing writing regularly",
                        "Read more English content to improve vocabulary",
                        "Review basic grammar rules"
                    ],
                    "next_steps": ["Practice writing daily"],
                    "recommended_exercises": []
                }
            }
        except Exception as e:
            logger.error(f"Error assessing writing: {e}")
            return {"success": False, "error": str(e)}

# Global AI service instance
ai_service = AIService() 