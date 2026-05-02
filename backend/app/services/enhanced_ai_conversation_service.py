import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import uuid

import google.generativeai as genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.core.config import settings
from app.core.cache import get_redis
from app.models.user import User
from app.models.personalization import (
    PersonalTrainerInteraction, UserLearningProfile,
    TrainerInteractionType, LearningGoalType
)
from app.models.content import DifficultyLevel
from app.crud.personalization import (
    trainer_interaction, learning_profile
)
from app.services.audio_processing_service import AudioProcessingService
from app.services.elsa_service import ELSAService
from app.services.gemini_flash_conversation_service import GeminiFlashConversationService

logger = logging.getLogger(__name__)

class ConversationContext(str, Enum):
    DAILY_LIFE = "daily_life"
    BUSINESS = "business"
    TRAVEL = "travel"
    EDUCATION = "education"
    HEALTH = "health"
    TECHNOLOGY = "technology"
    CULTURE = "culture"
    CURRENT_EVENTS = "current_events"

class ConversationMode(str, Enum):
    PRACTICE = "practice"
    ASSESSMENT = "assessment"
    TUTORING = "tutoring"
    FREE_CHAT = "free_chat"

class MessageType(str, Enum):
    USER_TEXT = "user_text"
    USER_AUDIO = "user_audio"
    AI_RESPONSE = "ai_response"
    SYSTEM_MESSAGE = "system_message"
    FEEDBACK = "feedback"

class EnhancedAIConversationService:
    """
    Advanced AI conversation engine with context persistence,
    personalization, and multi-modal interaction support
    """
    
    def __init__(self):
        # Initialize AI services
        if settings.GOOGLE_GEMINI_API_KEY:
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.gemini_model = None
            logger.warning("Google Gemini API key not configured")
        
        self.audio_processor = AudioProcessingService()
        self.elsa_service = ELSAService()
        self.gemini_flash_lite = GeminiFlashConversationService()
        self.redis = None
        
        # Conversation configuration
        self.max_context_messages = 20
        self.context_retention_hours = 24
        self.response_cache_hours = 1
        
    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    async def start_conversation(
        self,
        db: AsyncSession,
        user_id: int,
        context: ConversationContext,
        mode: ConversationMode = ConversationMode.PRACTICE,
        difficulty_level: Optional[DifficultyLevel] = None,
        specific_topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Start a new AI conversation session with personalized context
        
        Args:
            db: Database session
            user_id: User ID
            context: Conversation context (daily_life, business, etc.)
            mode: Conversation mode (practice, assessment, etc.)
            difficulty_level: Override user's level if specified
            specific_topic: Specific topic within the context
            
        Returns:
            Conversation session data with initial AI message
        """
        try:
            # Get user profile for personalization
            user_profile = await learning_profile.get_by_user_id(db, user_id=user_id)
            if not user_profile:
                # Create basic profile if doesn't exist
                user = await db.get(User, user_id)
                user_profile = await self._create_basic_profile(db, user)

            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Get user's conversation history for context
            conversation_history = await self._get_user_conversation_history(
                db, user_id, context, limit=5
            )
            
            # Determine effective difficulty level
            effective_level = difficulty_level or user_profile.current_level
            
            # Generate initial AI message
            initial_message = await self._generate_initial_message(
                user_profile, context, mode, effective_level, 
                specific_topic, conversation_history
            )
            
            # Create conversation session
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "context": context.value,
                "mode": mode.value,
                "difficulty_level": effective_level.value,
                "specific_topic": specific_topic,
                "started_at": datetime.utcnow().isoformat(),
                "messages": [
                    {
                        "id": str(uuid.uuid4()),
                        "type": MessageType.AI_RESPONSE.value,
                        "content": initial_message["content"],
                        "metadata": initial_message["metadata"],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                ],
                "user_profile_snapshot": {
                    "level": user_profile.current_level.value,
                    "learning_goals": user_profile.learning_goals,
                    "strengths": user_profile.strengths or [],
                    "weaknesses": user_profile.areas_for_improvement or []
                }
            }
            
            # Store session in cache
            await self._store_conversation_session(session_id, session_data)
            
            # Log interaction in database
            await self._log_trainer_interaction(
                db, user_id, TrainerInteractionType.CONVERSATION_START,
                {"session_id": session_id, "context": context.value, "mode": mode.value}
            )
            
            return {
                "success": True,
                "session": session_data,
                "initial_message": initial_message
            }
            
        except Exception as e:
            logger.error(f"Start conversation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "conversation_start_error"
            }

    async def process_user_message(
        self,
        db: AsyncSession,
        session_id: str,
        message_content: str,
        message_type: MessageType = MessageType.USER_TEXT,
        audio_data: Optional[bytes] = None,
        request_feedback: bool = True
    ) -> Dict[str, Any]:
        """
        Process user message and generate AI response with optional feedback
        
        Args:
            db: Database session
            session_id: Conversation session ID
            message_content: User's message text
            message_type: Type of message (text or audio)
            audio_data: Audio data if message_type is USER_AUDIO
            request_feedback: Whether to provide pronunciation/grammar feedback
            
        Returns:
            AI response with optional feedback and analysis
        """
        try:
            # Get conversation session
            session = await self._get_conversation_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Conversation session not found",
                    "error_type": "session_not_found"
                }
            
            # Process audio if provided
            audio_analysis = None
            if message_type == MessageType.USER_AUDIO and audio_data:
                audio_analysis = await self._process_user_audio(
                    audio_data, message_content, session["user_id"]
                )
                if audio_analysis["success"] and audio_analysis.get("transcript"):
                    message_content = audio_analysis["transcript"]
            
            # Add user message to session
            user_message = {
                "id": str(uuid.uuid4()),
                "type": message_type.value,
                "content": message_content,
                "audio_analysis": audio_analysis,
                "timestamp": datetime.utcnow().isoformat()
            }
            session["messages"].append(user_message)
            
            # Generate AI response
            ai_response = await self._generate_contextual_response(
                session, message_content, request_feedback
            )
            
            # Add AI response to session
            ai_message = {
                "id": str(uuid.uuid4()),
                "type": MessageType.AI_RESPONSE.value,
                "content": ai_response["content"],
                "metadata": ai_response["metadata"],
                "timestamp": datetime.utcnow().isoformat()
            }
            session["messages"].append(ai_message)
            
            # Generate feedback if requested
            feedback = None
            if request_feedback:
                feedback = await self._generate_comprehensive_feedback(
                    session, message_content, audio_analysis
                )
                
                if feedback:
                    feedback_message = {
                        "id": str(uuid.uuid4()),
                        "type": MessageType.FEEDBACK.value,
                        "content": feedback["summary"],
                        "details": feedback,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    session["messages"].append(feedback_message)
            
            # Update session
            await self._store_conversation_session(session_id, session)
            
            # Log interaction
            await self._log_trainer_interaction(
                db, session["user_id"], TrainerInteractionType.CONVERSATION_MESSAGE,
                {
                    "session_id": session_id,
                    "user_message": message_content,
                    "ai_response": ai_response["content"],
                    "feedback_provided": feedback is not None
                }
            )
            
            return {
                "success": True,
                "ai_response": ai_response,
                "feedback": feedback,
                "audio_analysis": audio_analysis,
                "session_updated": True
            }
            
        except Exception as e:
            logger.error(f"Process user message error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "message_processing_error"
            }

    async def get_conversation_suggestions(
        self,
        session_id: str,
        suggestion_type: str = "response"
    ) -> Dict[str, Any]:
        """
        Get AI-generated conversation suggestions for the user
        
        Args:
            session_id: Conversation session ID
            suggestion_type: Type of suggestions (response, questions, topics)
            
        Returns:
            List of contextual suggestions
        """
        try:
            session = await self._get_conversation_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found"
                }
            
            # Generate suggestions based on conversation context
            suggestions = await self._generate_contextual_suggestions(
                session, suggestion_type
            )
            
            return {
                "success": True,
                "suggestions": suggestions,
                "suggestion_type": suggestion_type
            }
            
        except Exception as e:
            logger.error(f"Get suggestions error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def end_conversation(
        self,
        db: AsyncSession,
        session_id: str,
        user_rating: Optional[int] = None,
        user_feedback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        End conversation session and generate summary
        
        Args:
            db: Database session
            session_id: Conversation session ID
            user_rating: User's rating of the conversation (1-5)
            user_feedback: User's feedback about the conversation
            
        Returns:
            Conversation summary and learning insights
        """
        try:
            session = await self._get_conversation_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found"
                }
            
            # Generate conversation summary
            summary = await self._generate_conversation_summary(session)
            
            # Calculate session statistics
            stats = await self._calculate_session_statistics(session)
            
            # Generate learning insights
            insights = await self._generate_learning_insights(session, summary, stats)
            
            # Update session with end data
            session.update({
                "ended_at": datetime.utcnow().isoformat(),
                "user_rating": user_rating,
                "user_feedback": user_feedback,
                "summary": summary,
                "statistics": stats,
                "insights": insights
            })
            
            # Store final session data
            await self._store_conversation_session(session_id, session, extended_ttl=True)
            
            # Log conversation end
            await self._log_trainer_interaction(
                db, session["user_id"], TrainerInteractionType.CONVERSATION_END,
                {
                    "session_id": session_id,
                    "duration_minutes": stats.get("duration_minutes", 0),
                    "message_count": stats.get("message_count", 0),
                    "user_rating": user_rating,
                    "summary": summary
                }
            )
            
            # Update user learning analytics
            await self._update_user_learning_analytics(db, session)
            
            return {
                "success": True,
                "summary": summary,
                "statistics": stats,
                "insights": insights,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"End conversation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_conversation_history(
        self,
        db: AsyncSession,
        user_id: int,
        context: Optional[ConversationContext] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get user's conversation history with optional filtering
        
        Args:
            db: Database session
            user_id: User ID
            context: Optional context filter
            limit: Number of conversations to return
            offset: Offset for pagination
            
        Returns:
            List of conversation summaries
        """
        try:
            # Query conversation history from database
            query = select(PersonalTrainerInteraction).where(
                and_(
                    PersonalTrainerInteraction.user_profile_id.in_(
                        select(UserLearningProfile.id).where(
                            UserLearningProfile.user_id == user_id
                        )
                    ),
                    PersonalTrainerInteraction.interaction_type == TrainerInteractionType.CONVERSATION_END
                )
            ).order_by(desc(PersonalTrainerInteraction.created_at))
            
            if context:
                # Filter by context if specified
                query = query.where(
                    PersonalTrainerInteraction.context_data.op('->>')('context') == context.value
                )
            
            result = await db.execute(query.offset(offset).limit(limit))
            interactions = result.scalars().all()
            
            # Format conversation history
            history = []
            for interaction in interactions:
                context_data = interaction.context_data or {}
                history.append({
                    "session_id": context_data.get("session_id"),
                    "context": context_data.get("context"),
                    "duration_minutes": context_data.get("duration_minutes", 0),
                    "message_count": context_data.get("message_count", 0),
                    "user_rating": context_data.get("user_rating"),
                    "summary": context_data.get("summary", ""),
                    "created_at": interaction.created_at.isoformat()
                })
            
            return {
                "success": True,
                "history": history,
                "total_count": len(history),
                "has_more": len(history) == limit
            }
            
        except Exception as e:
            logger.error(f"Get conversation history error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # Private helper methods
    async def _create_basic_profile(self, db: AsyncSession, user: User) -> UserLearningProfile:
        """Create basic learning profile for user"""
        profile_data = {
            "user_id": user.id,
            "current_level": user.current_level or DifficultyLevel.B1,
            "learning_goals": [LearningGoalType.SPEAKING_FLUENCY],
            "preferred_topics": ["daily_life", "general"],
            "study_time_preference": 30,
            "learning_style": "conversational"
        }
        
        return await learning_profile.create(db, obj_in=profile_data)

    async def _get_user_conversation_history(
        self,
        db: AsyncSession,
        user_id: int,
        context: ConversationContext,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history for context"""
        history_result = await self.get_conversation_history(
            db, user_id, context, limit=limit
        )
        return history_result.get("history", [])

    async def _generate_initial_message(
        self,
        user_profile: UserLearningProfile,
        context: ConversationContext,
        mode: ConversationMode,
        difficulty_level: DifficultyLevel,
        specific_topic: Optional[str],
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate personalized initial AI message"""
        if not self.gemini_model:
            return self._fallback_initial_message(context, difficulty_level)
        
        try:
            # Build context-aware prompt
            prompt = f"""
            You are an AI English learning tutor having a conversation with a student.
            
            Student Profile:
            - Level: {difficulty_level.value}
            - Learning Goals: {user_profile.learning_goals}
            - Strengths: {user_profile.strengths or ['general communication']}
            - Areas to improve: {user_profile.areas_for_improvement or ['fluency']}
            
            Conversation Context: {context.value}
            Mode: {mode.value}
            Specific Topic: {specific_topic or 'general'}
            
            Recent conversation topics: {[h.get('summary', '')[:100] for h in conversation_history[:3]]}
            
            Generate a warm, encouraging opening message that:
            1. Greets the student appropriately for their level
            2. Introduces the conversation topic naturally
            3. Asks an engaging question to start the conversation
            4. Uses vocabulary appropriate for {difficulty_level.value} level
            5. Is encouraging and supportive
            
            Keep it conversational and not too formal. Length: 2-3 sentences.
            """
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            
            return {
                "content": response.text.strip(),
                "metadata": {
                    "generated_by": "gemini",
                    "context": context.value,
                    "difficulty_level": difficulty_level.value,
                    "personalized": True
                }
            }
            
        except Exception as e:
            logger.error(f"Initial message generation error: {e}")
            return self._fallback_initial_message(context, difficulty_level)

    def _fallback_initial_message(
        self, 
        context: ConversationContext, 
        difficulty_level: DifficultyLevel
    ) -> Dict[str, Any]:
        """Fallback initial message when AI generation fails"""
        messages = {
            ConversationContext.DAILY_LIFE: {
                DifficultyLevel.A1: "Hello! I'm excited to chat with you today. How are you feeling?",
                DifficultyLevel.A2: "Hi there! I hope you're having a good day. What did you do this morning?",
                DifficultyLevel.B1: "Hello! I'm looking forward to our conversation. Tell me about something interesting that happened to you recently.",
                DifficultyLevel.B2: "Hi! It's great to connect with you today. I'd love to hear about your current interests or hobbies.",
                DifficultyLevel.C1: "Hello! I'm delighted to have this opportunity to chat with you. What's been occupying your thoughts lately?",
                DifficultyLevel.C2: "Greetings! I'm genuinely excited about our conversation today. What fascinating topics have been capturing your attention recently?"
            },
            ConversationContext.BUSINESS: {
                DifficultyLevel.A1: "Hello! Let's talk about work. What is your job?",
                DifficultyLevel.A2: "Hi! I'd like to learn about your work. Can you describe what you do?",
                DifficultyLevel.B1: "Hello! I'm interested in hearing about your professional life. What does a typical day at work look like for you?",
                DifficultyLevel.B2: "Hi there! I'd love to discuss your career and work experiences. What aspects of your job do you find most rewarding?",
                DifficultyLevel.C1: "Hello! I'm keen to explore your professional journey with you. How has your career evolved over the years?",
                DifficultyLevel.C2: "Greetings! I'm fascinated by professional development and career trajectories. What strategic decisions have shaped your career path?"
            }
        }
        
        default_message = "Hello! I'm your AI English tutor. I'm here to help you practice and improve your English. What would you like to talk about today?"
        
        content = messages.get(context, {}).get(difficulty_level, default_message)
        
        return {
            "content": content,
            "metadata": {
                "generated_by": "fallback",
                "context": context.value,
                "difficulty_level": difficulty_level.value,
                "personalized": False
            }
        }

    async def _store_conversation_session(
        self, 
        session_id: str, 
        session_data: Dict[str, Any],
        extended_ttl: bool = False
    ):
        """Store conversation session in cache"""
        try:
            redis = await self._get_redis()
            ttl = timedelta(hours=48 if extended_ttl else self.context_retention_hours)
            await redis.setex(
                f"conversation:{session_id}",
                int(ttl.total_seconds()),
                json.dumps(session_data, default=str)
            )
        except Exception as e:
            logger.error(f"Store session error: {e}")

    async def _get_conversation_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation session from cache"""
        try:
            redis = await self._get_redis()
            session_data = await redis.get(f"conversation:{session_id}")
            if session_data:
                return json.loads(session_data)
        except Exception as e:
            logger.error(f"Get session error: {e}")
        return None

    async def _process_user_audio(
        self, 
        audio_data: bytes, 
        expected_text: str, 
        user_id: int
    ) -> Dict[str, Any]:
        """Process user audio for speech recognition and analysis"""
        try:
            # Speech-to-text
            stt_result = await self.audio_processor.speech_to_text(
                audio_data, user_id=user_id
            )
            
            if not stt_result["success"]:
                return {
                    "success": False,
                    "error": "Speech recognition failed"
                }
            
            # Pronunciation analysis if expected text provided
            pronunciation_analysis = None
            if expected_text and expected_text.strip():
                pronunciation_analysis = await self.elsa_service.analyze_pronunciation(
                    audio_data, expected_text, user_id
                )
            
            return {
                "success": True,
                "transcript": stt_result["transcript"],
                "confidence": stt_result["confidence"],
                "pronunciation_analysis": pronunciation_analysis,
                "processing_metadata": {
                    "engine_used": stt_result.get("engine_used"),
                    "processing_time": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Audio processing error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _generate_contextual_response(
        self,
        session: Dict[str, Any],
        user_message: str,
        request_feedback: bool
    ) -> Dict[str, Any]:
        """Generate contextual AI response based on conversation history"""
        if not self.gemini_model:
            return self._fallback_ai_response(user_message)
        
        try:
            # Build conversation context
            recent_messages = session["messages"][-10:]  # Last 10 messages
            conversation_context = "\n".join([
                f"{'User' if msg['type'] in ['user_text', 'user_audio'] else 'AI'}: {msg['content']}"
                for msg in recent_messages
            ])
            
            user_profile = session["user_profile_snapshot"]
            
            prompt = f"""
            You are an AI English tutor having a natural conversation with a student.
            
            Student Profile:
            - Level: {user_profile['level']}
            - Strengths: {user_profile['strengths']}
            - Areas to improve: {user_profile['weaknesses']}
            
            Conversation Context: {session['context']}
            Mode: {session['mode']}
            
            Recent conversation:
            {conversation_context}
            
            User just said: "{user_message}"
            
            Respond naturally as a supportive tutor:
            1. Acknowledge what the user said
            2. Continue the conversation naturally
            3. Ask a follow-up question or make an encouraging comment
            4. Use vocabulary appropriate for {user_profile['level']} level
            5. Be supportive and encouraging
            6. Keep response conversational (2-4 sentences)
            
            {'Also, gently correct any errors and provide learning tips.' if request_feedback else ''}
            """
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            
            return {
                "content": response.text.strip(),
                "metadata": {
                    "generated_by": "gemini",
                    "contextual": True,
                    "feedback_included": request_feedback,
                    "response_type": "conversational"
                }
            }
            
        except Exception as e:
            logger.error(f"Contextual response error: {e}")
            return self._fallback_ai_response(user_message)

    def _fallback_ai_response(self, user_message: str) -> Dict[str, Any]:
        """Fallback AI response when generation fails"""
        responses = [
            "That's interesting! Can you tell me more about that?",
            "I see! What do you think about that?",
            "Thank you for sharing that with me. How did that make you feel?",
            "That sounds great! What happened next?",
            "I understand. Can you give me an example?"
        ]
        
        # Simple response selection based on message content
        import random
        response = random.choice(responses)
        
        return {
            "content": response,
            "metadata": {
                "generated_by": "fallback",
                "contextual": False,
                "response_type": "generic"
            }
        }

    async def _generate_comprehensive_feedback(
        self,
        session: Dict[str, Any],
        user_message: str,
        audio_analysis: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Generate comprehensive feedback on user's message"""
        try:
            feedback_components = {}
            
            # Grammar and language feedback
            if self.gemini_model:
                grammar_feedback = await self._generate_grammar_feedback(
                    user_message, session["user_profile_snapshot"]["level"]
                )
                feedback_components["grammar"] = grammar_feedback
            
            # Pronunciation feedback from audio analysis
            if audio_analysis and audio_analysis.get("pronunciation_analysis"):
                feedback_components["pronunciation"] = audio_analysis["pronunciation_analysis"]
            
            # Vocabulary suggestions
            vocab_feedback = await self._generate_vocabulary_feedback(
                user_message, session["user_profile_snapshot"]["level"]
            )
            feedback_components["vocabulary"] = vocab_feedback
            
            # Combine feedback into summary
            summary = await self._create_feedback_summary(feedback_components)
            
            return {
                "summary": summary,
                "components": feedback_components,
                "overall_score": self._calculate_overall_score(feedback_components),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Feedback generation error: {e}")
            return None

    async def _log_trainer_interaction(
        self,
        db: AsyncSession,
        user_id: int,
        interaction_type: TrainerInteractionType,
        context_data: Dict[str, Any]
    ):
        """Log trainer interaction to database"""
        try:
            # Get user learning profile
            user_profile = await learning_profile.get_by_user_id(db, user_id=user_id)
            if not user_profile:
                return
            
            # Create interaction record
            interaction_data = {
                "user_profile_id": user_profile.id,
                "interaction_type": interaction_type,
                "context_data": context_data,
                "created_at": datetime.utcnow()
            }
            
            await trainer_interaction.create(db, obj_in=interaction_data)
            
        except Exception as e:
            logger.error(f"Log interaction error: {e}")

    # Additional helper methods (simplified for brevity)
    async def _generate_contextual_suggestions(
        self, session: Dict[str, Any], suggestion_type: str
    ) -> List[str]:
        """Generate contextual conversation suggestions"""
        return [
            "Can you tell me more about that?",
            "What do you think about this topic?",
            "How does this relate to your experience?"
        ]

    async def _generate_conversation_summary(self, session: Dict[str, Any]) -> str:
        """Generate conversation summary"""
        return f"Conversation about {session['context']} lasting {len(session['messages'])} messages"

    async def _calculate_session_statistics(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate session statistics"""
        start_time = datetime.fromisoformat(session["started_at"])
        end_time = datetime.utcnow()
        duration = end_time - start_time
        
        return {
            "duration_minutes": duration.total_seconds() / 60,
            "message_count": len(session["messages"]),
            "user_message_count": len([m for m in session["messages"] if m["type"] in ["user_text", "user_audio"]]),
            "ai_message_count": len([m for m in session["messages"] if m["type"] == "ai_response"])
        }

    async def _generate_learning_insights(
        self, session: Dict[str, Any], summary: str, stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate learning insights from conversation"""
        return {
            "key_topics_discussed": [session["context"]],
            "language_skills_practiced": ["speaking", "listening"],
            "areas_of_strength": ["engagement", "vocabulary"],
            "areas_for_improvement": ["grammar accuracy"],
            "recommended_next_steps": ["Practice similar conversations", "Focus on grammar exercises"]
        }

    async def _update_user_learning_analytics(self, db: AsyncSession, session: Dict[str, Any]):
        """Update user learning analytics based on conversation"""
        # This would update user progress, analytics, etc.
        # Implementation depends on your analytics models
        pass

    async def _generate_grammar_feedback(self, text: str, level: str) -> Dict[str, Any]:
        """Generate grammar feedback for user text"""
        # Simplified implementation
        return {
            "score": 85,
            "corrections": [],
            "suggestions": ["Great grammar usage!"]
        }

    async def _generate_vocabulary_feedback(self, text: str, level: str) -> Dict[str, Any]:
        """Generate vocabulary feedback"""
        return {
            "score": 80,
            "advanced_words_used": [],
            "suggestions": ["Try using more varied vocabulary"]
        }

    def _create_feedback_summary(self, components: Dict[str, Any]) -> str:
        """Create summary from feedback components"""
        return "Good job! Keep practicing to improve your English skills."

    def _calculate_overall_score(self, components: Dict[str, Any]) -> int:
        """Calculate overall score from feedback components"""
        scores = []
        for component in components.values():
            if isinstance(component, dict) and "score" in component:
                scores.append(component["score"])
        return int(sum(scores) / len(scores)) if scores else 75

    # ==================== AUDIO CONVERSATION METHODS ====================

    async def process_audio_message(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: str,
        audio_data: bytes,
        context: Optional[ConversationContext] = None
    ) -> Dict[str, Any]:
        """
        Process audio message in conversation using Gemini Flash-Lite.

        Args:
            db: Database session
            user_id: User ID
            session_id: Conversation session ID
            audio_data: Raw audio bytes
            context: Conversation context

        Returns:
            Dict containing transcription, AI response, and analysis
        """
        try:
            # Get user profile for level
            user_profile = await learning_profile.get_by_user(db, user_id)
            user_level = user_profile.current_level.value if user_profile else "B1"

            # Get conversation context
            conversation_history = await self._get_conversation_context(session_id)
            context_str = context.value if context else "general conversation"

            # Process audio through Gemini Flash-Lite
            result = await self.gemini_flash_lite.process_audio_conversation(
                audio_data=audio_data,
                conversation_context=context_str,
                user_level=user_level,
                conversation_history=conversation_history,
                user_id=user_id
            )

            if not result["success"]:
                return {
                    "success": False,
                    "error": result.get("error", "Audio processing failed"),
                    "fallback": True
                }

            # Add message to conversation
            user_message = {
                "type": "user_audio",
                "timestamp": datetime.utcnow().isoformat(),
                "transcription": result["transcription"],
                "confidence": result["confidence"],
                "pronunciation_score": result["pronunciation_analysis"]["overall_score"]
            }

            ai_message = {
                "type": "ai_response",
                "timestamp": datetime.utcnow().isoformat(),
                "response": result["ai_response"],
                "response_type": result["response_type"],
                "follow_up_questions": result["follow_up_questions"]
            }

            # Update conversation session
            await self._add_messages_to_session(session_id, [user_message, ai_message])

            # Create trainer interaction for learning analytics
            interaction_data = {
                "interaction_type": TrainerInteractionType.CONVERSATION,
                "content": f"Audio conversation: {result['transcription']}",
                "user_response": result["transcription"],
                "ai_response": result["ai_response"],
                "score": result["pronunciation_analysis"]["overall_score"],
                "difficulty_level": user_level,
                "topics": [context_str],
                "metadata": {
                    "audio_confidence": result["confidence"],
                    "fluency_score": result["pronunciation_analysis"]["fluency_score"],
                    "response_type": result["response_type"],
                    "conversation_context": context_str
                }
            }

            await trainer_interaction.create_with_user(
                db, obj_in=interaction_data, user_id=user_id
            )

            return {
                "success": True,
                "session_id": session_id,
                "transcription": result["transcription"],
                "ai_response": result["ai_response"],
                "pronunciation_analysis": result["pronunciation_analysis"],
                "response_type": result["response_type"],
                "follow_up_questions": result["follow_up_questions"],
                "conversation_context": context_str,
                "metadata": result["metadata"]
            }

        except Exception as e:
            logger.error(f"Audio message processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback": True
            }

    async def get_audio_conversation_summary(
        self,
        session_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Get summary of audio conversation session.

        Args:
            session_id: Conversation session ID
            user_id: User ID

        Returns:
            Dict containing conversation summary and analytics
        """
        try:
            session = await self._get_conversation_session(session_id)
            if not session:
                return {"success": False, "error": "Session not found"}

            messages = session.get("messages", [])
            audio_messages = [m for m in messages if m["type"] == "user_audio"]
            ai_messages = [m for m in messages if m["type"] == "ai_response"]

            # Calculate audio-specific metrics
            total_pronunciation_score = 0
            total_confidence = 0
            total_words = 0

            for msg in audio_messages:
                if "pronunciation_score" in msg:
                    total_pronunciation_score += msg["pronunciation_score"]
                if "confidence" in msg:
                    total_confidence += msg["confidence"]
                if "transcription" in msg:
                    total_words += len(msg["transcription"].split())

            avg_pronunciation = total_pronunciation_score / len(audio_messages) if audio_messages else 0
            avg_confidence = total_confidence / len(audio_messages) if audio_messages else 0

            return {
                "success": True,
                "session_id": session_id,
                "total_messages": len(messages),
                "audio_messages": len(audio_messages),
                "ai_responses": len(ai_messages),
                "average_pronunciation_score": avg_pronunciation,
                "average_recognition_confidence": avg_confidence,
                "total_words_spoken": total_words,
                "conversation_duration": session.get("duration_minutes", 0),
                "topics_discussed": session.get("topics", []),
                "learning_objectives": session.get("learning_objectives", [])
            }

        except Exception as e:
            logger.error(f"Audio conversation summary failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
