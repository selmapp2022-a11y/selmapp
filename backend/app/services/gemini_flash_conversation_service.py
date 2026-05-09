import asyncio
import base64
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cache import get_redis
from app.services.audio_processing_service import AudioProcessingService

logger = logging.getLogger(__name__)

class GeminiFlashConversationService:
    """
    Advanced conversational AI service using Google Gemini 2.5 Flash model.
    Processes audio input from users and generates contextual text responses for speaking exercises.
    """

    def __init__(self):
        self.client = None
        self.audio_processor = AudioProcessingService()
        self.redis = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the Gemini client with API key"""
        try:
            api_key = getattr(settings, 'GOOGLE_GEMINI_API_KEY', None)
            if not api_key:
                logger.warning("GOOGLE_GEMINI_API_KEY not found in settings. Gemini Flash-Lite will be unavailable.")
                return

            genai.configure(api_key=api_key)
            self.client = genai.GenerativeModel(getattr(settings, 'GEMINI_TEXT_MODEL_FAST', 'gemini-2.5-flash'))
            logger.info("Gemini Flash-Lite conversation service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Flash-Lite client: {e}")
            self.client = None

    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    async def process_audio_conversation(
        self,
        audio_data: bytes,
        conversation_context: str,
        user_level: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process user audio input and generate conversational response.

        Args:
            audio_data: Raw audio bytes from user
            conversation_context: Context of the conversation (topic, scenario)
            user_level: User's current CEFR level
            conversation_history: Previous messages in the conversation
            user_id: User ID for personalization

        Returns:
            Dict containing transcription, AI response, and metadata
        """
        if not self.client:
            return {
                "success": False,
                "error": "Gemini Flash-Lite service not initialized",
                "fallback": True
            }

        try:
            # Step 1+2: STT with a 3-stage fallback chain so a single failing
            # provider can never silently break Live Conversation:
            #   1. ELSA Unscripted (also gives transcript + IELTS/CEFR scores)
            #   2. ElevenLabs Scribe (existing key, no GCP gymnastics)
            #   3. Google Cloud STT (last resort — needs the GCP project to
            #      have the Speech API enabled, which currently it doesn't)
            from app.services.elsa_unscripted_service import ELSAUnscriptedService
            from app.services.elevenlabs_asr_service import ElevenLabsASRService
            from app.services.asr_service import GoogleSTTService

            stt_result = await ELSAUnscriptedService().transcribe(audio_data)
            if not stt_result.get("success") or not (stt_result.get("text") or "").strip():
                stt_result = await ElevenLabsASRService().transcribe(audio_data)
            if not stt_result.get("success") or not (stt_result.get("text") or "").strip():
                stt_result = await GoogleSTTService().transcribe(audio_data, language_code="en-US")

            if not stt_result.get("success"):
                return {
                    "success": False,
                    "error": f"Speech recognition failed: {stt_result.get('error', 'Unknown error')}",
                    "fallback": True,
                }

            user_transcription = (stt_result.get("text") or "").strip()
            recognition_confidence = stt_result.get("confidence", 0.0)
            audio_processing_result: Dict[str, Any] = {
                "quality_analysis": {},
                "features": {},
            }

            if not user_transcription:
                return {
                    "success": False,
                    "error": "We couldn't make out what you said — please speak a bit louder or longer.",
                    "transcription": "",
                    "confidence": 0.0,
                    "fallback": True,
                }

            # Step 3: Generate conversational AI response
            ai_response_result = await self._generate_conversational_response(
                user_input=user_transcription,
                conversation_context=conversation_context,
                user_level=user_level,
                conversation_history=conversation_history,
                user_id=user_id
            )

            if not ai_response_result["success"]:
                return {
                    "success": False,
                    "error": f"AI response generation failed: {ai_response_result.get('error', 'Unknown error')}",
                    "transcription": user_transcription,
                    "confidence": recognition_confidence
                }

            # Step 4: Analyze pronunciation and speaking quality
            pronunciation_analysis = await self._analyze_speaking_quality(
                transcription=user_transcription,
                audio_features=audio_processing_result.get("features", {}),
                user_level=user_level
            )

            # Step 5: Cache conversation for context
            if user_id:
                await self._cache_conversation_context(
                    user_id=user_id,
                    conversation_data={
                        "user_input": user_transcription,
                        "ai_response": ai_response_result["response"],
                        "context": conversation_context,
                        "timestamp": datetime.utcnow().isoformat(),
                        "pronunciation_score": pronunciation_analysis.get("overall_score", 0)
                    }
                )

            return {
                "success": True,
                "transcription": user_transcription,
                "confidence": recognition_confidence,
                "ai_response": ai_response_result["response"],
                "response_type": ai_response_result["response_type"],
                "follow_up_questions": ai_response_result.get("follow_up_questions", []),
                "pronunciation_analysis": pronunciation_analysis,
                "conversation_context": conversation_context,
                "metadata": {
                    "model": "gemini-2.5-flash",
                    "audio_quality": audio_processing_result.get("quality_analysis", {}),
                    "processing_time": datetime.utcnow().isoformat(),
                    "conversation_length": len(conversation_history) if conversation_history else 0
                }
            }

        except Exception as e:
            logger.error(f"Audio conversation processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": True
            }

    async def _generate_conversational_response(
        self,
        user_input: str,
        conversation_context: str,
        user_level: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate contextual conversational response using Gemini"""

        try:
            # Build conversation prompt
            prompt = self._build_conversation_prompt(
                user_input=user_input,
                conversation_context=conversation_context,
                user_level=user_level,
                conversation_history=conversation_history
            )

            # Generate response
            response = self.client.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=300,
                    top_p=0.9,
                    top_k=40
                )
            )

            ai_response_text = response.text.strip()

            # Parse response for structured data
            parsed_response = self._parse_ai_response(ai_response_text)

            return {
                "success": True,
                "response": parsed_response["response"],
                "response_type": parsed_response["response_type"],
                "follow_up_questions": parsed_response.get("follow_up_questions", []),
                "teaching_points": parsed_response.get("teaching_points", [])
            }

        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _build_conversation_prompt(
        self,
        user_input: str,
        conversation_context: str,
        user_level: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build a comprehensive prompt for conversational AI response"""

        # Level-specific guidance
        level_guidance = {
            "A1": "Use very simple vocabulary and short sentences. Be encouraging and patient.",
            "A2": "Use basic vocabulary and simple sentence structures. Include some new words with explanations.",
            "B1": "Use intermediate vocabulary. Include idioms occasionally. Provide gentle corrections.",
            "B2": "Use more advanced vocabulary and complex structures. Discuss nuanced topics.",
            "C1": "Use sophisticated vocabulary and complex grammar. Engage in deep discussions.",
            "C2": "Use native-like expressions and advanced linguistic features. Challenge with complex topics."
        }

        # Build conversation history context
        history_context = ""
        if conversation_history and len(conversation_history) > 0:
            recent_history = conversation_history[-6:]  # Last 6 messages for context
            history_lines = []
            for msg in recent_history:
                if msg["type"] == "user_audio":
                    history_lines.append(f"User: {msg['transcription']}")
                elif msg["type"] == "ai_response":
                    history_lines.append(f"AI: {msg['response']}")
            history_context = "\nPrevious conversation:\n" + "\n".join(history_lines)

        prompt = f"""You are an expert English conversation tutor helping a {user_level} level learner practice speaking.

CONTEXT: {conversation_context}
USER LEVEL: {user_level}
LEVEL GUIDANCE: {level_guidance.get(user_level, "Adapt to learner's level")}

{history_context}

USER'S CURRENT MESSAGE: "{user_input}"

The user just said the message above. Reference a specific detail from their message in your reply (quote or paraphrase). If you cannot understand their message, politely ask them to clarify.

Your task is to:
1. Acknowledge the specific content the user said
2. Continue the conversation naturally
3. Gently correct any major errors in the user's message
4. Teach 1-2 relevant language points naturally
5. Ask a follow-up question that builds on what they said
6. Keep responses appropriate in length for speaking practice (2-4 sentences)

Format your response as:
RESPONSE: [Your natural conversational response]

RESPONSE_TYPE: [question/statement/clarification/confirmation]

FOLLOW_UP_QUESTION: [A question to continue the conversation]

TEACHING_POINTS: [1-2 language points you taught naturally, separated by semicolons]

Make your response engaging, encouraging, and educational!"""

        return prompt

    def _parse_ai_response(self, ai_response_text: str) -> Dict[str, Any]:
        """Parse the AI response to extract structured data"""

        lines = ai_response_text.strip().split('\n')
        parsed = {
            "response": "",
            "response_type": "statement",
            "follow_up_questions": [],
            "teaching_points": []
        }

        current_section = "response"

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.upper().startswith("RESPONSE:"):
                current_section = "response"
                parsed["response"] = line[9:].strip()
            elif line.upper().startswith("RESPONSE_TYPE:"):
                parsed["response_type"] = line[14:].strip().lower()
            elif line.upper().startswith("FOLLOW_UP_QUESTION:"):
                question = line[19:].strip()
                if question:
                    parsed["follow_up_questions"].append(question)
            elif line.upper().startswith("TEACHING_POINTS:"):
                current_section = "teaching"
                teaching_text = line[16:].strip()
                if teaching_text:
                    parsed["teaching_points"] = [point.strip() for point in teaching_text.split(';') if point.strip()]
            elif current_section == "response" and parsed["response"]:
                # Continue adding to response if it's multi-line
                if line.upper().startswith(("RESPONSE_TYPE:", "FOLLOW_UP_QUESTION:", "TEACHING_POINTS:")):
                    continue
                parsed["response"] += " " + line

        # Ensure we have a response
        if not parsed["response"]:
            parsed["response"] = ai_response_text.strip()

        return parsed

    async def _analyze_speaking_quality(
        self,
        transcription: str,
        audio_features: Dict[str, Any],
        user_level: str
    ) -> Dict[str, Any]:
        """Analyze speaking quality including pronunciation, fluency, etc."""

        try:
            # Simple analysis based on available data
            word_count = len(transcription.split())
            avg_word_length = sum(len(word) for word in transcription.split()) / max(word_count, 1)

            # Basic fluency score based on word count and complexity
            fluency_score = min(100, word_count * 2)  # Rough estimation

            # Pronunciation score (placeholder - would need more sophisticated analysis)
            pronunciation_score = 75.0  # Default good score

            # Adjust based on user level
            level_adjustment = {
                "A1": -10, "A2": -5, "B1": 0, "B2": 5, "C1": 10, "C2": 15
            }
            pronunciation_score += level_adjustment.get(user_level, 0)
            pronunciation_score = max(0, min(100, pronunciation_score))

            return {
                "overall_score": pronunciation_score,
                "fluency_score": fluency_score,
                "pronunciation_score": pronunciation_score,
                "word_count": word_count,
                "avg_word_length": avg_word_length,
                "audio_features": audio_features,
                "feedback": self._generate_speaking_feedback(pronunciation_score, fluency_score, word_count)
            }

        except Exception as e:
            logger.error(f"Speaking quality analysis failed: {e}")
            return {
                "overall_score": 70.0,
                "fluency_score": 70.0,
                "pronunciation_score": 70.0,
                "error": str(e)
            }

    def _generate_speaking_feedback(
        self,
        pronunciation_score: float,
        fluency_score: float,
        word_count: int
    ) -> str:
        """Generate encouraging feedback based on scores"""

        feedback_parts = []

        if pronunciation_score >= 80:
            feedback_parts.append("Great pronunciation!")
        elif pronunciation_score >= 60:
            feedback_parts.append("Good pronunciation with room for improvement.")
        else:
            feedback_parts.append("Keep practicing pronunciation - you're making progress!")

        if fluency_score >= 80:
            feedback_parts.append("Your fluency is excellent!")
        elif fluency_score >= 60:
            feedback_parts.append("Good fluency - try speaking a bit faster.")
        else:
            feedback_parts.append("Work on fluency by speaking more smoothly.")

        if word_count < 5:
            feedback_parts.append("Try to say a bit more in your responses.")
        elif word_count > 50:
            feedback_parts.append("Great detail in your response!")

        return " ".join(feedback_parts)

    async def _cache_conversation_context(
        self,
        user_id: int,
        conversation_data: Dict[str, Any]
    ):
        """Cache conversation context for continuity"""

        try:
            redis = await self._get_redis()
            cache_key = f"conversation_context:{user_id}"

            # Get existing context
            existing_context = await redis.get(cache_key)
            if existing_context:
                context_list = json.loads(existing_context)
            else:
                context_list = []

            # Add new conversation data
            context_list.append(conversation_data)

            # Keep only last 20 messages for context
            if len(context_list) > 20:
                context_list = context_list[-20:]

            # Cache for 2 hours
            await redis.setex(
                cache_key,
                timedelta(hours=2).total_seconds(),
                json.dumps(context_list)
            )

        except Exception as e:
            logger.warning(f"Failed to cache conversation context: {e}")

    async def get_conversation_context(self, user_id: int) -> List[Dict[str, Any]]:
        """Retrieve cached conversation context"""

        try:
            redis = await self._get_redis()
            cache_key = f"conversation_context:{user_id}"

            cached_context = await redis.get(cache_key)
            if cached_context:
                return json.loads(cached_context)
            return []

        except Exception as e:
            logger.warning(f"Failed to retrieve conversation context: {e}")
            return []

    async def clear_conversation_context(self, user_id: int) -> bool:
        """Clear cached conversation context"""

        try:
            redis = await self._get_redis()
            cache_key = f"conversation_context:{user_id}"
            result = await redis.delete(cache_key)
            return result > 0

        except Exception as e:
            logger.warning(f"Failed to clear conversation context: {e}")
            return False

    async def generate_speaking_exercise_response(
        self,
        audio_data: bytes,
        exercise_type: str,
        prompt_text: str,
        user_level: str,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate response for structured speaking exercises.

        Args:
            audio_data: User's audio response
            exercise_type: Type of speaking exercise (conversation, pronunciation, etc.)
            prompt_text: The exercise prompt
            user_level: User's CEFR level
            user_id: User ID for personalization

        Returns:
            Dict containing analysis and feedback
        """

        # Process the audio through the conversation pipeline
        conversation_result = await self.process_audio_conversation(
            audio_data=audio_data,
            conversation_context=f"Speaking exercise: {exercise_type} - {prompt_text}",
            user_level=user_level,
            user_id=user_id
        )

        if not conversation_result["success"]:
            return conversation_result

        # Add exercise-specific analysis
        exercise_analysis = await self._analyze_exercise_response(
            transcription=conversation_result["transcription"],
            exercise_type=exercise_type,
            prompt_text=prompt_text,
            user_level=user_level
        )

        conversation_result["exercise_analysis"] = exercise_analysis
        conversation_result["exercise_type"] = exercise_type
        conversation_result["prompt_text"] = prompt_text

        return conversation_result

    async def _analyze_exercise_response(
        self,
        transcription: str,
        exercise_type: str,
        prompt_text: str,
        user_level: str
    ) -> Dict[str, Any]:
        """Analyze response specific to the exercise type"""

        analysis = {
            "completeness_score": 0,
            "relevance_score": 0,
            "exercise_specific_feedback": "",
            "improvement_suggestions": []
        }

        try:
            # Basic analysis based on transcription length and content
            word_count = len(transcription.split())

            # Completeness based on expected response length
            expected_words = {"A1": 5, "A2": 10, "B1": 15, "B2": 25, "C1": 35, "C2": 50}
            expected_word_count = expected_words.get(user_level, 15)
            analysis["completeness_score"] = min(100, (word_count / expected_word_count) * 100)

            # Relevance score (simplified - would need NLP for better analysis)
            analysis["relevance_score"] = 85.0  # Placeholder

            # Exercise-specific feedback
            if exercise_type == "conversation":
                analysis["exercise_specific_feedback"] = "Good conversational flow. Try to ask more questions to continue the dialogue."
                analysis["improvement_suggestions"] = [
                    "Include follow-up questions",
                    "Use more varied vocabulary",
                    "Practice natural intonation"
                ]
            elif exercise_type == "pronunciation":
                analysis["exercise_specific_feedback"] = "Focus on clear articulation of individual sounds."
                analysis["improvement_suggestions"] = [
                    "Slow down for difficult sounds",
                    "Practice in front of a mirror",
                    "Record and compare with native speakers"
                ]
            else:
                analysis["exercise_specific_feedback"] = "Good effort! Keep practicing regularly."
                analysis["improvement_suggestions"] = [
                    "Practice daily",
                    "Focus on weak areas",
                    "Get feedback from native speakers"
                ]

        except Exception as e:
            logger.error(f"Exercise analysis failed: {e}")

        return analysis
