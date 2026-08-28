"""
Personal Trainer AI Service
Comprehensive AI service for personalized language learning with context-aware content generation
"""

import asyncio
from app.services.language_profile import profile_for
import json
import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.services.ai_service import ai_service
from app.services.ai_reading_service import ai_reading_service
from app.models.user import User
from app.models.content import DifficultyLevel
from app.models.reading import ReadingTextType
from app.models.listening import AudioType
from app.models.speaking import SpeakingExerciseType
from app.models.writing import WritingType
from app.crud.personalization import user_onboarding, user_category_preference
from app.crud.progress import user_progress_crud
from app.crud.content import vocabulary_crud

logger = logging.getLogger(__name__)

class PersonalTrainerAIService:
    """
    Enhanced AI service that acts as a personal English trainer
    Generates contextual, personalized content based on user's learning journey
    """
    
    def __init__(self):
        self.ai_service = ai_service
        self.reading_service = ai_reading_service

    async def generate_daily_learning_plan(
        self,
        db: AsyncSession,
        sync_db: Session, 
        user: User,
        focus_skills: Optional[List[str]] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Generate a comprehensive daily learning plan tailored to the user"""
        
        try:
            # Get user profile and preferences
            user_profile = await self._build_comprehensive_user_profile(db, user, language=language)
            
            # Get learning analytics
            progress_analytics = await self._get_user_progress_analytics(db, user.id)
            
            # Determine focus areas
            if not focus_skills:
                focus_skills = await self._determine_daily_focus_skills(user_profile, progress_analytics)
            
            # Generate personalized learning plan using AI
            prompt = self._create_daily_plan_prompt(user_profile, progress_analytics, focus_skills)
            
            # generate_content is SYNCHRONOUS; awaiting it directly raised
            # "object GenerateContentResponse can't be used in 'await'
            # expression" and made the daily plan fail for every language.
            # Every other call in this file already wraps it in to_thread.
            ai_result = await asyncio.to_thread(
                self.ai_service.gemini_model.generate_content, prompt
            )
            
            try:
                plan_data = json.loads(ai_result.text)
                
                # Enhance the plan with actual generated content
                enhanced_plan = await self._enhance_plan_with_content(
                    db, plan_data, user, user_profile
                )
                
                return {
                    "success": True,
                    "daily_plan": enhanced_plan,
                    "focus_skills": focus_skills,
                    "estimated_total_time": enhanced_plan.get("total_estimated_minutes", 30),
                    "personalization_score": self._calculate_personalization_score(user_profile, progress_analytics)
                }
                
            except json.JSONDecodeError:
                return {"success": False, "error": "Failed to parse AI-generated plan"}
                
        except Exception as e:
            logger.error(f"Error generating daily learning plan: {e}")
            return {"success": False, "error": str(e)}

    async def generate_contextual_content(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        content_type: str,
        topic: Optional[str] = None,
        previous_interaction_context: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Generate content that fits perfectly into the user's learning journey"""
        
        try:
            user_profile = await self._build_comprehensive_user_profile(db, user, language=language)
            
            # Use AI to determine the best topic if not provided
            if not topic:
                topic = await self._ai_suggest_optimal_topic(user_profile, content_type, previous_interaction_context)
            
            if content_type == "reading":
                return await self._generate_personalized_reading_content(db, user, user_profile, topic)
            elif content_type == "vocabulary":
                return await self._generate_personalized_vocabulary_content(db, user, user_profile, topic)
            elif content_type == "listening":
                return await self._generate_personalized_listening_content(db, user, user_profile, topic)
            elif content_type == "speaking":
                return await self._generate_personalized_speaking_content(db, user, user_profile, topic)
            elif content_type == "writing":
                return await self._generate_personalized_writing_content(db, user, user_profile, topic)
            else:
                return {"success": False, "error": f"Unsupported content type: {content_type}"}
                
        except Exception as e:
            logger.error(f"Error generating contextual content: {e}")
            return {"success": False, "error": str(e)}

    async def provide_adaptive_feedback(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        user_performance: Dict[str, Any],
        exercise_context: Dict[str, Any],
        language: str = "en",
    ) -> Dict[str, Any]:
        """Provide intelligent, adaptive feedback based on user's performance"""
        
        try:
            user_profile = await self._build_comprehensive_user_profile(db, user, language=language)
            progress_analytics = await self._get_user_progress_analytics(db, user.id)
            
            # Create context-aware feedback prompt
            prompt = f"""
            You are an encouraging English learning AI trainer. Provide personalized feedback for this learner.
            
            User Profile:
            - Level: {user_profile.get('current_level')}
            - Learning Goals: {', '.join(user_profile.get('learning_goals', []))}
            - Study Time: {user_profile.get('daily_study_commitment')} minutes/day
            - Preferred Categories: {', '.join(user_profile.get('preferred_categories', []))}
            
            Current Performance:
            - Exercise Type: {exercise_context.get('type', 'general')}
            - Topic: {exercise_context.get('topic', 'general')}
            - Score: {user_performance.get('score', 0)}%
            - Time Taken: {user_performance.get('time_taken_seconds', 0)} seconds
            - Accuracy: {user_performance.get('accuracy', 0)}%
            
            Recent Progress:
            - Total Study Time: {progress_analytics.get('total_study_time', 0)} minutes
            - Current Streak: {progress_analytics.get('current_streak', 0)} days
            - Overall Accuracy: {progress_analytics.get('average_accuracy', 0)}%
            - Weak Areas: {', '.join(progress_analytics.get('weak_areas', []))}
            
            Provide:
            1. Encouraging feedback about their performance
            2. Specific areas for improvement
            3. Actionable next steps
            4. Motivation based on their goals
            5. Difficulty adjustment suggestions if needed
            
            Format as JSON:
            {{
                "feedback_message": "...",
                "performance_analysis": {{
                    "strengths": ["...", "..."],
                    "areas_for_improvement": ["...", "..."],
                    "difficulty_assessment": "too_easy|appropriate|too_hard"
                }},
                "next_steps": [
                    {{
                        "action": "...",
                        "reason": "...",
                        "estimated_time_minutes": 10
                    }}
                ],
                "motivation_message": "...",
                "progress_celebration": "..."
            }}
            """
            
            response = await asyncio.to_thread(
                self.ai_service.gemini_model.generate_content, prompt
            )
            
            try:
                feedback_data = json.loads(response.text)
                return {"success": True, "feedback": feedback_data}
            except json.JSONDecodeError:
                return {
                    "success": True, 
                    "feedback": {
                        "feedback_message": "Great work on that exercise! Keep practicing to improve your English skills.",
                        "performance_analysis": {
                            "strengths": ["Good effort"],
                            "areas_for_improvement": ["Continue practicing"],
                            "difficulty_assessment": "appropriate"
                        },
                        "next_steps": [{"action": "Continue practicing", "reason": "Builds skills", "estimated_time_minutes": 10}],
                        "motivation_message": "You're making progress!",
                        "progress_celebration": "Every practice session counts!"
                    }
                }
                
        except Exception as e:
            logger.error(f"Error providing adaptive feedback: {e}")
            return {"success": False, "error": str(e)}

    async def create_learning_session(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        session_type: str = "mixed",  # reading, vocabulary, grammar, listening, speaking, writing, mixed
        duration_minutes: Optional[int] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Create a complete learning session with multiple content types"""
        
        try:
            user_profile = await self._build_comprehensive_user_profile(db, user, language=language)
            progress_analytics = await self._get_user_progress_analytics(db, user.id)
            
            # Determine session duration
            if not duration_minutes:
                duration_minutes = user_profile.get('daily_study_commitment', 30)
            
            # Generate session structure using AI
            prompt = f"""
            Create a structured learning session for an English learner.
            
            User Profile:
            - Level: {user_profile.get('current_level')}
            - Preferred Categories: {', '.join(user_profile.get('preferred_categories', []))}
            - Learning Goals: {', '.join(user_profile.get('learning_goals', []))}
            - Session Duration: {duration_minutes} minutes
            - Session Type: {session_type}
            
            Progress Context:
            - Current Streak: {progress_analytics.get('current_streak', 0)} days
            - Weak Areas: {', '.join(progress_analytics.get('weak_areas', []))}
            - Recent Performance: {progress_analytics.get('average_accuracy', 0)}%
            
            Create a session with:
            1. Warm-up activity (5 minutes)
            2. Main learning activities (70% of time)
            3. Practice/review (20% of time)
            4. Cool-down/reflection (5% of time)
            
            Balance the activities based on weak areas and learning goals.
            Include specific topics, exercise types, and time allocations.
            
            Format as JSON:
            {{
                "session_overview": {{
                    "title": "...",
                    "description": "...",
                    "total_duration_minutes": {duration_minutes},
                    "focus_skills": ["...", "..."],
                    "learning_objectives": ["...", "..."]
                }},
                "activities": [
                    {{
                        "phase": "warm_up|main|practice|cool_down",
                        "activity_type": "vocabulary|grammar|reading|listening|speaking|writing",
                        "topic": "...",
                        "description": "...",
                        "duration_minutes": 5,
                        "difficulty": "easy|medium|hard",
                        "ai_content_needed": true
                    }}
                ]
            }}
            """
            
            response = await asyncio.to_thread(
                self.ai_service.gemini_model.generate_content, prompt
            )
            
            try:
                session_data = json.loads(response.text)
                
                # Generate actual content for each activity that needs it
                enhanced_session = await self._generate_session_content(
                    db, session_data, user, user_profile
                )
                
                return {"success": True, "learning_session": enhanced_session}
                
            except json.JSONDecodeError:
                return {"success": False, "error": "Failed to parse AI-generated session"}
                
        except Exception as e:
            logger.error(f"Error creating learning session: {e}")
            return {"success": False, "error": str(e)}

    # Private helper methods

    async def _build_comprehensive_user_profile(
        self, db: AsyncSession, user: User, language: str = "en"
    ) -> Dict[str, Any]:
        """Build a comprehensive user profile for AI context"""
        # Get onboarding data - use async session
        try:
            onboarding = await user_onboarding.get_by_user_id(db, user_id=user.id)
        except Exception as _e:
            raise
        
        # Get category preferences - use async session
        try:
            category_prefs = await user_category_preference.get_by_user_id(db, user_id=user.id)
        except Exception as _e:
            raise

        # Preferred categories priority:
        # 1) Explicit category preferences table (if populated)
        # 2) Fallback to onboarding.selected_categories (mobile/web onboarding writes here)
        # This is important because some clients send fine-grained interest ids
        # (e.g. "daily_life", "food") which are stored in onboarding JSON but may
        # not map 1:1 to the enum-backed preferences table.
        preferred_categories = (
            [pref.category for pref in category_prefs] if category_prefs else []
        )
        if (not preferred_categories) and onboarding and getattr(onboarding, "selected_categories", None):
            preferred_categories = onboarding.selected_categories or []

        return {
            "current_level": user.current_level.value,
            "native_language": user.native_language,
            # From the GOAL's exam, passed by the caller, not user.target_language
            # (deprecated — see the column comment in models/user.py). The daily
            # plan is generated in this language; reading it off a dead per-user
            # column made a TCF candidate's plan come back in English.
            "target_language": profile_for(language).english_name,
            "language_code": profile_for(language).code,
            "learning_goals": onboarding.learning_goals if onboarding else [],
            "preferred_categories": preferred_categories,
            "learning_style": onboarding.preferred_learning_style if onboarding else "mixed",
            "daily_study_commitment": onboarding.daily_study_commitment if onboarding else 30,
            "target_timeline": onboarding.target_timeline if onboarding else "flexible",
            "motivation_factors": onboarding.motivation_factors if onboarding else [],
            "preferred_difficulty": onboarding.preferred_difficulty if onboarding else "gradual",
            "preferred_content_types": onboarding.preferred_content_types if onboarding else [],
            "interests": (onboarding.assessment_details or {}).get("interests", []) if onboarding else []
        }

    async def _get_user_progress_analytics(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user progress analytics"""
        try:
            progress = await user_progress_crud.get_by_user(db, user_id=user_id)
        except Exception as _e:
            raise
        
        if not progress:
            return {
                "total_study_time": 0,
                "current_streak": 0,
                "average_accuracy": 0,
                "weak_areas": [],
                "strong_areas": [],
                "learning_velocity": "unknown"
            }
        
        # Identify weak and strong areas
        weak_areas = []
        strong_areas = []
        
        if progress.vocabulary_mastered < 50:
            weak_areas.append("vocabulary")
        elif progress.vocabulary_mastered > 100:
            strong_areas.append("vocabulary")
            
        if progress.grammar_rules_learned < 20:
            weak_areas.append("grammar")
        elif progress.grammar_rules_learned > 50:
            strong_areas.append("grammar")
            
        if progress.speaking_sessions < 10:
            weak_areas.append("speaking")
        elif progress.speaking_sessions > 30:
            strong_areas.append("speaking")
            
        if progress.listening_hours < 5:
            weak_areas.append("listening")
        elif progress.listening_hours > 20:
            strong_areas.append("listening")
        
        # Calculate learning velocity
        last_activity = progress.updated_at or progress.created_at or progress.last_study_date
        if not last_activity and not progress.created_at:
             days_since_start = 1
        elif last_activity and progress.created_at:
             days_since_start = (last_activity - progress.created_at).days
             if days_since_start < 1:
                 days_since_start = 1
        else:
             days_since_start = 1
             
        velocity = progress.total_exercises_completed / days_since_start
        
        velocity_category = "slow" if velocity < 2 else "moderate" if velocity < 5 else "fast"
        
        return {
            "total_study_time": progress.total_study_time_minutes,
            "current_streak": progress.current_streak_days,
            "average_accuracy": progress.average_accuracy * 100,
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "learning_velocity": velocity_category,
            "total_exercises_completed": progress.total_exercises_completed,
            "vocabulary_mastered": progress.vocabulary_mastered,
            "grammar_rules_learned": progress.grammar_rules_learned
        }

    async def _determine_daily_focus_skills(
        self, 
        user_profile: Dict[str, Any], 
        progress_analytics: Dict[str, Any]
    ) -> List[str]:
        """AI-powered determination of what skills to focus on today"""
        
        weak_areas = progress_analytics.get("weak_areas", [])
        preferred_categories = user_profile.get("preferred_categories", [])
        
        # Priority system: weak areas first, then preferences
        focus_skills = []
        
        # Add weak areas first (max 2)
        focus_skills.extend(weak_areas[:2])
        
        # Add preferred categories that aren't already weak areas
        for category in preferred_categories:
            skill_mapping = {
                "conversation_practice": "speaking",
                "vocabulary_building": "vocabulary", 
                "grammar_focus": "grammar",
                "reading_comprehension": "reading",
                "listening_skills": "listening",
                "writing_skills": "writing"
            }
            
            skill = skill_mapping.get(category)
            if skill and skill not in focus_skills and len(focus_skills) < 3:
                focus_skills.append(skill)
        
        # Ensure we have at least 2 skills
        if len(focus_skills) < 2:
            all_skills = ["vocabulary", "grammar", "reading", "speaking"]
            for skill in all_skills:
                if skill not in focus_skills:
                    focus_skills.append(skill)
                    if len(focus_skills) >= 2:
                        break
        
        return focus_skills[:3]  # Max 3 focus skills per day

    def _create_daily_plan_prompt(
        self, 
        user_profile: Dict[str, Any], 
        progress_analytics: Dict[str, Any], 
        focus_skills: List[str]
    ) -> str:
        """Create AI prompt for daily learning plan generation"""

        lang = profile_for(user_profile.get("language_code", "en"))
        return f"""
        Create a personalized daily {lang.english_name} learning plan for this learner.
        {lang.write_in} Every title, description, objective and activity name in the
        JSON below must be written in {lang.english_name}.
        
        Learner Profile:
        - CEFR Level: {user_profile.get('current_level')}
        - Study Time Available: {user_profile.get('daily_study_commitment')} minutes
        - Learning Goals: {', '.join(user_profile.get('learning_goals', []))}
        - Preferred Learning Style: {user_profile.get('learning_style')}
        - Motivation Factors: {', '.join(user_profile.get('motivation_factors', []))}
        
        Current Progress:
        - Study Streak: {progress_analytics.get('current_streak')} days
        - Overall Accuracy: {progress_analytics.get('average_accuracy')}%
        - Weak Areas: {', '.join(progress_analytics.get('weak_areas', []))}
        - Strong Areas: {', '.join(progress_analytics.get('strong_areas', []))}
        - Learning Velocity: {progress_analytics.get('learning_velocity')}
        
        Today's Focus Skills: {', '.join(focus_skills)}
        
        Create a structured learning plan that:
        1. Addresses weak areas while building on strengths
        2. Aligns with the user's learning goals
        3. Fits within their available study time
        4. Incorporates their preferred learning style
        5. Provides appropriate challenge level
        6. Includes variety to maintain engagement
        
        Format as JSON:
        {{
            "plan_overview": {{
                "title": "...",
                "description": "...", 
                "total_estimated_minutes": {user_profile.get('daily_study_commitment')},
                "focus_areas": {focus_skills},
                "difficulty_level": "{user_profile.get('current_level')}",
                "learning_objectives": ["...", "..."]
            }},
            "activities": [
                {{
                    "sequence_order": 1,
                    "activity_name": "...",
                    "skill_type": "vocabulary|grammar|reading|listening|speaking|writing",
                    "topic": "...",
                    "description": "...",
                    "estimated_minutes": 10,
                    "difficulty": "review|current_level|challenge",
                    "specific_instructions": "...",
                    "success_criteria": "...",
                    "content_generation_needed": true
                }}
            ],
            "session_tips": [
                "...",
                "..."
            ],
            "progress_tracking": {{
                "skills_to_track": ["...", "..."],
                "success_metrics": ["accuracy", "completion_time", "engagement"]
            }}
        }}
        """

    async def _enhance_plan_with_content(
        self,
        db: AsyncSession,
        plan_data: Dict[str, Any],
        user: User,
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate actual content for activities that need it"""
        
        enhanced_activities = []
        
        for activity in plan_data.get("activities", []):
            enhanced_activity = activity.copy()
            
            if activity.get("content_generation_needed", False):
                skill_type = activity.get("skill_type")
                topic = activity.get("topic", "general")
                
                # Generate content based on skill type
                content_result = await self.generate_contextual_content(
                    db, None, user, skill_type, topic
                )
                
                if content_result.get("success"):
                    enhanced_activity["generated_content"] = content_result.get("content")
                    enhanced_activity["content_available"] = True
                else:
                    enhanced_activity["content_available"] = False
                    enhanced_activity["content_error"] = content_result.get("error")
            
            enhanced_activities.append(enhanced_activity)
        
        plan_data["activities"] = enhanced_activities
        return plan_data

    async def _generate_personalized_reading_content(
        self, 
        db: AsyncSession, 
        user: User, 
        user_profile: Dict[str, Any], 
        topic: str
    ) -> Dict[str, Any]:
        """Generate personalized reading content"""
        
        try:
            result = await self.reading_service.generate_reading_text_with_vocabulary(
                db=db,
                level=DifficultyLevel(user.current_level.value),
                text_type=ReadingTextType.ARTICLE,
                topic=topic,
                word_count=200 if user.current_level.value in ["A1", "A2"] else 300,
                vocabulary_count=8 if user.current_level.value in ["A1", "A2"] else 12,
                include_comprehension_questions=True
            )
            
            return {"success": True, "content": result}
            
        except Exception as e:
            logger.error(f"Error generating reading content: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_personalized_vocabulary_content(
        self, 
        db: AsyncSession, 
        user: User, 
        user_profile: Dict[str, Any], 
        topic: str
    ) -> Dict[str, Any]:
        """Generate personalized vocabulary content"""
        
        try:
            # Get vocabulary words for user's level and topic
            vocab_words = await vocabulary_crud.get_by_level_and_topic(
                db, 
                level=DifficultyLevel(user.current_level.value),
                topic=topic,
                limit=10
            )
            
            if not vocab_words:
                # Generate vocabulary using AI if no existing words
                result = await self.ai_service.generate_exercise_content(
                    topic=topic,
                    difficulty_level=user.current_level.value,
                    exercise_type="vocabulary",
                    count=10
                )
                
                return {"success": result.get("success", False), "content": result}
            
            # Create vocabulary exercises with the found words
            vocab_data = {
                "vocabulary_words": [
                    {
                        "word": word.word,
                        "definition": word.definition,
                        "example": word.example_sentence,
                        "pronunciation": word.pronunciation
                    } for word in vocab_words
                ],
                "topic": topic,
                "level": user.current_level.value
            }
            
            return {"success": True, "content": vocab_data}
            
        except Exception as e:
            logger.error(f"Error generating vocabulary content: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_personalized_listening_content(
        self, 
        db: AsyncSession, 
        user: User, 
        user_profile: Dict[str, Any], 
        topic: str
    ) -> Dict[str, Any]:
        """Generate personalized listening content"""
        
        # For now, return a structured response - you can enhance with actual audio generation
        return {
            "success": True,
            "content": {
                "audio_url": None,  # Would be generated with TTS
                "transcript": f"Sample listening content about {topic} for {user.current_level.value} level",
                "comprehension_questions": [
                    {
                        "question": f"What is the main topic discussed?",
                        "options": [topic, "weather", "sports", "food"],
                        "correct_answer": topic
                    }
                ],
                "vocabulary_focus": [],
                "topic": topic,
                "duration_seconds": 120
            }
        }

    async def _generate_personalized_speaking_content(
        self, 
        db: AsyncSession, 
        user: User, 
        user_profile: Dict[str, Any], 
        topic: str
    ) -> Dict[str, Any]:
        """Generate personalized speaking content"""
        
        try:
            result = await self.ai_service.generate_conversation_practice(
                topic=topic,
                level=user.current_level.value,
                turns=6
            )
            
            return {"success": result.get("success", False), "content": result}
            
        except Exception as e:
            logger.error(f"Error generating speaking content: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_personalized_writing_content(
        self, 
        db: AsyncSession, 
        user: User, 
        user_profile: Dict[str, Any], 
        topic: str
    ) -> Dict[str, Any]:
        """Generate personalized writing content"""
        
        try:
            # Generate writing prompts and exercises
            result = await self.ai_service.generate_exercise_content(
                topic=topic,
                difficulty_level=user.current_level.value,
                exercise_type="writing",
                count=3
            )
            
            return {"success": result.get("success", False), "content": result}
            
        except Exception as e:
            logger.error(f"Error generating writing content: {e}")
            return {"success": False, "error": str(e)}

    async def _ai_suggest_optimal_topic(
        self, 
        user_profile: Dict[str, Any], 
        content_type: str,
        previous_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Use AI to suggest the most optimal topic for current learning session"""
        
        try:
            prompt = f"""
            Suggest the most effective learning topic for this English learner today.
            
            Learner Profile:
            - Level: {user_profile.get('current_level')}
            - Goals: {', '.join(user_profile.get('learning_goals', []))}
            - Preferred Categories: {', '.join(user_profile.get('preferred_categories', []))}
            - Learning Style: {user_profile.get('learning_style')}
            
            Content Type: {content_type}
            Previous Context: {previous_context or 'First session'}
            
            Consider:
            1. User's learning goals and interests
            2. Appropriate complexity for their level
            3. Practical relevance for English learners
            4. Engagement and motivation factors
            
            Suggest ONE specific topic (2-3 words max) that would be most beneficial.
            Examples: "travel planning", "job interviews", "family dinner", "daily routine"
            
            Respond with just the topic name, no additional text.
            """
            
            response = await asyncio.to_thread(
                self.ai_service.gemini_model.generate_content, prompt
            )
            
            suggested_topic = response.text.strip().lower()
            
            # Validate and clean the suggestion
            if len(suggested_topic.split()) <= 3 and suggested_topic.isalpha() or " " in suggested_topic:
                return suggested_topic
            else:
                return "daily life"  # Safe fallback
                
        except Exception as e:
            logger.error(f"Error suggesting optimal topic: {e}")
            return "general topics"

    async def _generate_session_content(
        self,
        db: AsyncSession,
        session_data: Dict[str, Any],
        user: User,
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate actual content for session activities"""
        
        enhanced_activities = []
        
        for activity in session_data.get("activities", []):
            enhanced_activity = activity.copy()
            
            if activity.get("ai_content_needed", False):
                content_result = await self.generate_contextual_content(
                    db, None, user, activity.get("activity_type"), activity.get("topic")
                )
                
                if content_result.get("success"):
                    enhanced_activity["generated_content"] = content_result.get("content")
                    enhanced_activity["content_ready"] = True
                else:
                    enhanced_activity["content_ready"] = False
                    enhanced_activity["content_error"] = content_result.get("error")
            
            enhanced_activities.append(enhanced_activity)
        
        session_data["activities"] = enhanced_activities
        return session_data

    def _calculate_personalization_score(
        self, 
        user_profile: Dict[str, Any], 
        progress_analytics: Dict[str, Any]
    ) -> float:
        """Calculate how personalized the content is (0.0 - 1.0)"""
        
        score = 0.0
        
        # Check if we have key profile data
        if user_profile.get("learning_goals"):
            score += 0.2
        if user_profile.get("preferred_categories"):
            score += 0.2
        if user_profile.get("learning_style") != "mixed":
            score += 0.1
        if user_profile.get("motivation_factors"):
            score += 0.1
        
        # Check if we have progress data to personalize with
        if progress_analytics.get("weak_areas"):
            score += 0.2
        if progress_analytics.get("total_study_time", 0) > 60:  # At least 1 hour of data
            score += 0.2
        
        return min(score, 1.0)

# Global instance
personal_trainer_ai_service = PersonalTrainerAIService()
