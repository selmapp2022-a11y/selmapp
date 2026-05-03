"""
Content Generation Workflow Service
Orchestrates the generation of all types of learning content for personalized AI trainer experience
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
import math
import os
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.services.personal_trainer_ai_service import personal_trainer_ai_service
from app.services.ai_service import ai_service
from app.services.ai_reading_service import ai_reading_service
from app.services.gemini_tts_service import GeminiTTSService
from app.models.user import User
from app.models.content import DifficultyLevel
from app.models.reading import ReadingTextType
from app.schemas.personalization import LearningJourneyRequest
from app.crud.content import vocabulary_crud
from app.services.content_cache_service import content_cache_service, build_cache_key
from app.crud.cache import (
    generated_content_cache_crud,
    weekly_learning_plan_crud,
    user_weekly_progress_crud,
    day_completion_record_crud,
)
from app.crud.personalization import user_onboarding, user_category_preference
from app.crud.progress import user_progress_crud

logger = logging.getLogger(__name__)

class ContentGenerationWorkflow:
    """
    Orchestrates the complete content generation workflow for personalized learning
    """
    
    def __init__(self):
        self.trainer_service = personal_trainer_ai_service
        self.ai_service = ai_service
        self.reading_service = ai_reading_service
        self.tts_service = GeminiTTSService()

    async def create_complete_learning_journey(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        journey_request: LearningJourneyRequest
    ) -> Dict[str, Any]:
        """Create a complete personalized learning journey for the user"""
        
        try:
            logger.info(f"Creating {journey_request.journey_duration_days}-day learning journey for user {user.id} with level {journey_request.user_level} and {journey_request.daily_study_time_minutes} min/day commitment")

            # Step 1: Analyze user using provided assessment data
            user_analysis = await self._analyze_user_for_journey_with_assessment(
                sync_db, db, user, journey_request
            )

            # Step 2: Generate learning path structure based on time commitment
            # Soft-cap generation to avoid huge plans; preserve original days in metadata
            requested_days = int(journey_request.journey_duration_days)
            effective_days = max(7, min(56, requested_days))
            journey_structure = await self._generate_journey_structure_with_time_constraint(
                user_analysis, effective_days, journey_request.daily_study_time_minutes
            )
            journey_structure["requested_duration_days"] = requested_days
            
            # Ensure journey_structure has weeks; if missing, use fallback
            if not isinstance(journey_structure, dict) or not journey_structure.get("weeks"):
                journey_structure = self._create_fallback_journey_structure(
                    user_analysis,
                    journey_request.journey_duration_days,
                    journey_request.daily_study_time_minutes,
                )

            # Step 3: Generate content for first week (guard for empty weeks)
            first_week_content = {}
            weeks_list = journey_structure.get("weeks", [])
            if weeks_list:
                first_week_content = await self._generate_week_content(
                    db, sync_db, user, weeks_list[0], user_analysis
                )
            else:
                first_week_content = {"days": []}

            # Derive a modules array to simplify frontend consumption
            modules: list[dict] = []
            for w in journey_structure.get("weeks", []):
                # Support both daily_schedule and days shapes
                days = w.get("daily_schedule") or w.get("days") or []
                for d in days:
                    title = d.get("session_title") or d.get("title") or f"Day {d.get('day') or d.get('day_number', 1)}"
                    est = d.get("estimated_minutes")
                    # If daily_schedule stores content_types, approximate duration
                    if est is None:
                        est = 20
                        ct = d.get("content_types") or []
                        if isinstance(ct, list) and ct:
                            est = max(15, min(45, 10 * len(ct)))
                    modules.append({
                        "id": f"day_{d.get('day') or d.get('day_number', len(modules)+1)}",
                        "title": title,
                        "skills": ["mixed"],
                        "estimated_minutes": int(est) if isinstance(est, (int, float)) else 20,
                        "is_unlocked": len(modules) == 0,
                        "description": "Auto-generated module"
                    })
            # Limit modules returned to first 12 to keep UI snappy; client can request more later
            if len(modules) > 12:
                modules = modules[:12]

            return {
                "success": True,
                "journey_overview": {**journey_structure, "modules": modules},
                "first_week_content": first_week_content,
                "user_analysis": user_analysis,
                # Compute hours using requested duration to reflect long-term plan even if generation was capped
                "total_estimated_hours": (requested_days * journey_request.daily_study_time_minutes) / 60
            }
            
        except Exception as e:
            logger.error(f"Error creating learning journey: {e}")
            return {"success": False, "error": str(e)}

    async def generate_adaptive_session_content(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        session_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate content for a learning session that adapts to user's current state"""

        try:
            # Get real-time user state
            current_state = await self._get_current_user_state(db, sync_db, user)
            
            # Determine optimal content mix for this session
            content_mix = await self._calculate_optimal_content_mix(
                current_state, session_context
            )
            
            # Generate content for each component and normalize to a list of steps
            steps: list[dict] = []

            for component in content_mix["components"]:
                content_type = component["type"]
                topic = component["topic"]
                duration = int(round(component.get("duration_minutes", 5)))

                # Pass minimal user_context with day_number for caching scope
                day_ctx = {"day_number": session_context.get("day_number", 0)}
                content_result = await self._generate_single_content_piece(
                    db, user, content_type, topic, duration, day_ctx
                )

                if not content_result.get("success"):
                    logger.warning(
                        f"Failed to generate {content_type} content: {content_result.get('error')}"
                    )
                    # Still add a placeholder step to keep UX flow consistent
                    steps.append({
                        "type": content_type,
                        "title": f"{content_type.title()} Practice",
                        "content": f"Practice {content_type} on the topic '{topic}'.",
                        "media_url": None,
                        "questions": None,
                        "estimated_minutes": duration or 5,
                    })
                    continue

                generated = content_result.get("content", {})

                # Try to extract sensible fields across content types
                media_url = None
                questions = None
                text_content = None

                if isinstance(generated, dict):
                    # Clean up content if it's a raw JSON string from AI
                    if isinstance(generated.get("content"), str):
                        raw_content = generated.get("content", "").strip()
                        # Strip markdown code blocks
                        if raw_content.startswith("```"):
                            raw_content = raw_content.replace("```json", "").replace("```", "").strip()
                        
                        try:
                            parsed_content = json.loads(raw_content)
                            # Update generated dict with parsed content
                            if isinstance(parsed_content, dict):
                                generated.update(parsed_content)
                                # If we parsed 'exercises', make sure they are available for questions extraction
                                if "exercises" in parsed_content:
                                    generated["exercises"] = parsed_content["exercises"]
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse raw content JSON for {content_type}")

                    # If we have exercises but no vocabulary words, create a lightweight vocab list for UI
                    if generated.get("exercises") and not generated.get("vocabulary_words") and not generated.get("words"):
                        vocab_words = []
                        for ex in generated.get("exercises", []):
                            if not isinstance(ex, dict):
                                continue
                            word = ex.get("correct_answer") or (ex.get("question") or "").split(" ")[0]
                            definition = ex.get("explanation") or ex.get("question") or "Practice this term."
                            vocab_words.append({"word": str(word), "definition": str(definition)})
                            if len(vocab_words) >= 12:
                                break
                        if vocab_words:
                            generated["vocabulary_words"] = vocab_words

                    # Common fields used by services
                    media_url = generated.get("audio_url") or generated.get("media_url")
                    questions = (
                        generated.get("questions")
                        or generated.get("comprehension_questions")
                        or generated.get("targeted_exercises")
                        or generated.get("exercises")
                    )
                    text_content = (
                        generated.get("text")
                        or generated.get("text_content")
                        or generated.get("reading_text")
                        or generated.get("audio_script")
                        or generated.get("passage")
                        or generated.get("article")
                        or generated.get("story")
                        or generated.get("prompt_text")  # For speaking
                        or generated.get("conversation_prompt")  # For speaking
                        or generated.get("description")
                    )
                    
                    # Fallback for vocabulary: if no text but we have exercises/words
                    if not text_content:
                        if generated.get("words"):
                            words = [w.get("word") for w in generated.get("words", []) if isinstance(w, dict)]
                            if words:
                                text_content = "Vocabulary focus: " + ", ".join(words[:12])
                        elif questions:
                             text_content = f"Complete the following {len(questions)} exercises to practice."
                        elif generated.get("content") and isinstance(generated.get("content"), str):
                             # Use the raw cleaned string as a last resort if it's readable
                             clean_text = generated.get("content").replace("```json", "").replace("```", "").strip()
                             if not clean_text.startswith("{"): # Don't show raw JSON object
                                 text_content = clean_text

                else:
                    # If service returned a plain string
                    text_content = str(generated)

                # Strong fallbacks to keep UI populated
                if not text_content:
                    if content_type == "listening":
                        text_content = generated.get("audio_script") or "Listen and answer the questions."
                    elif content_type == "reading":
                        text_content = generated.get("passage") or generated.get("text") or generated.get("reading_text") or "Read the passage and answer the questions."
                    elif content_type == "vocabulary":
                        words = [w.get("word") for w in generated.get("words", []) if isinstance(w, dict)] if isinstance(generated, dict) else []
                        text_content = "Vocabulary practice: " + ", ".join(words[:8]) if words else "Vocabulary practice."
                    elif content_type == "speaking":
                        text_content = generated.get("prompt_text") or generated.get("conversation_prompt") or f"Practice speaking about {topic}. Share your thoughts and experiences."
                    elif content_type == "grammar":
                        text_content = generated.get("grammar_point") or generated.get("explanation") or f"Grammar practice on {topic}"
                    else:
                        text_content = f"{content_type.title()} practice on {topic}"

                # Ensure media_url is populated if audio_url exists under another key
                if not media_url and isinstance(generated, dict):
                    media_url = generated.get("audioUrl") or generated.get("audio_url") or generated.get("mediaUrl")

                steps.append({
                    "type": content_type,
                    "title": f"{content_type.title()} • {topic.title()}",
                    "content": text_content,
                    "media_url": media_url,
                    "questions": questions,
                    "estimated_minutes": duration or 5,
                    "content_json": generated if isinstance(generated, dict) else None,
                })

            return {
                "success": True,
                "session_content": steps,  # normalized list for API consumer
                "content_mix": content_mix,
                "adaptation_reason": content_mix.get("adaptation_reason", ""),
                "estimated_difficulty": content_mix.get("estimated_difficulty", "appropriate")
            }
            
        except Exception as e:
            logger.error(f"Error generating adaptive session content: {e}")
            return {"success": False, "error": str(e)}

    async def generate_skill_focused_content_series(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        target_skill: str,  # vocabulary, grammar, reading, listening, speaking, writing
        series_length: int = 5
    ) -> Dict[str, Any]:
        """Generate a series of progressive content focused on a specific skill"""
        
        try:
            user_profile = await personal_trainer_ai_service._build_comprehensive_user_profile(db, user)
            progress_analytics = await personal_trainer_ai_service._get_user_progress_analytics(db, user.id)
            
            # Generate progression plan for the skill
            progression_prompt = f"""
            Create a {series_length}-part progression plan for improving {target_skill} skills.
            
            User Context:
            - Current Level: {user_profile.get('current_level')}
            - Learning Goals: {', '.join(user_profile.get('learning_goals', []))}
            - Current {target_skill} Performance: {self._get_skill_performance(progress_analytics, target_skill)}
            - Preferred Topics: {', '.join(user_profile.get('preferred_categories', []))}
            - Personal Interests: {', '.join(user_profile.get('interests', [])) or 'not specified'}
            
            Create a progression where:
            1. Each session builds on the previous one
            2. Difficulty gradually increases
            3. Topics are relevant and engaging
            4. Each session takes 15-20 minutes
            
            Format as JSON:
            {{
                "series_overview": {{
                    "title": "...",
                    "description": "...",
                    "target_skill": "{target_skill}",
                    "total_sessions": {series_length},
                    "progression_strategy": "..."
                }},
                "sessions": [
                    {{
                        "session_number": 1,
                        "title": "...",
                        "topic": "...",
                        "learning_objectives": ["...", "..."],
                        "difficulty_progression": "review|current|challenge",
                        "estimated_minutes": 20,
                        "key_concepts": ["...", "..."]
                    }}
                ]
            }}
            """
            
            response = await asyncio.to_thread(
                self.ai_service.gemini_model.generate_content, progression_prompt
            )
            
            try:
                progression_data = json.loads(response.text)
                
                # Generate actual content for the first session
                first_session = progression_data["sessions"][0]
                first_content = await self._generate_single_content_piece(
                    db, user, target_skill, first_session["topic"], 
                    first_session["estimated_minutes"], user_profile
                )
                
                return {
                    "success": True,
                    "series_plan": progression_data,
                    "first_session_content": first_content.get("content") if first_content.get("success") else None
                }
                
            except json.JSONDecodeError:
                return {"success": False, "error": "Failed to parse progression plan"}
                
        except Exception as e:
            logger.error(f"Error generating skill-focused series: {e}")
            return {"success": False, "error": str(e)}

    async def generate_weakness_targeted_content(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        detected_weaknesses: List[str]
    ) -> Dict[str, Any]:
        """Generate content specifically targeting user's identified weaknesses"""
        
        try:
            user_profile = await personal_trainer_ai_service._build_comprehensive_user_profile(db, user)
            
            targeted_content = {}
            
            for weakness in detected_weaknesses:
                # Generate AI prompt for this specific weakness
                weakness_prompt = f"""
                Create targeted learning content to help a {user_profile.get('current_level')} level learner improve their {weakness} skills.
                
                User Context:
                - Current Weakness: {weakness}
                - Learning Style: {user_profile.get('learning_style')}
                - Available Study Time: {user_profile.get('daily_study_commitment')} minutes
                - Motivation: {', '.join(user_profile.get('motivation_factors', []))}
                
                Create content that:
                1. Directly addresses the weakness
                2. Provides clear, actionable exercises
                3. Includes immediate feedback mechanisms
                4. Builds confidence while challenging the learner
                5. Connects to their interests and goals
                
                Format as JSON:
                {{
                    "weakness_analysis": {{
                        "identified_weakness": "{weakness}",
                        "root_causes": ["...", "..."],
                        "improvement_strategy": "..."
                    }},
                    "targeted_exercises": [
                        {{
                            "exercise_type": "...",
                            "title": "...",
                            "instructions": "...",
                            "content": "...",
                            "success_criteria": "...",
                            "estimated_minutes": 10
                        }}
                    ],
                    "progress_tracking": {{
                        "metrics_to_track": ["...", "..."],
                        "improvement_indicators": ["...", "..."]
                    }},
                    "motivation_elements": [
                        "...",
                        "..."
                    ]
                }}
                """
                
                response = await asyncio.to_thread(
                    self.ai_service.gemini_model.generate_content, weakness_prompt
                )
                
                try:
                    weakness_content = json.loads(response.text)
                    targeted_content[weakness] = weakness_content
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse content for weakness: {weakness}")
                    continue
            
            return {
                "success": True,
                "targeted_content": targeted_content,
                "weaknesses_addressed": len(targeted_content),
                "recommendations": self._generate_weakness_improvement_plan(detected_weaknesses)
            }
            
        except Exception as e:
            logger.error(f"Error generating weakness-targeted content: {e}")
            return {"success": False, "error": str(e)}

    async def create_interactive_lesson(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        lesson_topic: str,
        lesson_type: str = "comprehensive"  # comprehensive, vocabulary_focus, grammar_focus, etc.
    ) -> Dict[str, Any]:
        """Create an interactive lesson with multiple content types and real-time adaptation"""
        
        try:
            user_profile = await personal_trainer_ai_service._build_comprehensive_user_profile(db, user)
            
            # Generate lesson structure
            lesson_prompt = f"""
            Create an interactive English lesson about "{lesson_topic}" for a {user_profile.get('current_level')} level learner.
            
            Lesson Type: {lesson_type}
            User Profile:
            - Learning Goals: {', '.join(user_profile.get('learning_goals', []))}
            - Preferred Style: {user_profile.get('learning_style')}
            - Study Time: {user_profile.get('daily_study_commitment')} minutes
            
            Create a lesson with:
            1. Introduction (2 minutes)
            2. Pre-lesson assessment (3 minutes) 
            3. Main content delivery (60% of time)
            4. Practice activities (25% of time)
            5. Assessment and reflection (10% of time)
            
            Include checkpoints for adaptation and real-time feedback.
            
            Format as JSON:
            {{
                "lesson_overview": {{
                    "title": "...",
                    "topic": "{lesson_topic}",
                    "level": "{user_profile.get('current_level')}",
                    "type": "{lesson_type}",
                    "total_duration_minutes": {user_profile.get('daily_study_commitment', 30)},
                    "learning_objectives": ["...", "..."],
                    "key_vocabulary": ["...", "..."],
                    "grammar_focus": ["...", "..."]
                }},
                "lesson_phases": [
                    {{
                        "phase_name": "introduction|pre_assessment|main_content|practice|assessment",
                        "duration_minutes": 5,
                        "activities": [
                            {{
                                "activity_type": "...",
                                "content": "...",
                                "interaction_required": true,
                                "adaptation_points": ["...", "..."]
                            }}
                        ]
                    }}
                ],
                "adaptation_checkpoints": [
                    {{
                        "checkpoint_name": "...",
                        "assessment_criteria": "...",
                        "adaptation_options": {{
                            "if_struggling": "...",
                            "if_excelling": "...",
                            "if_disengaged": "..."
                        }}
                    }}
                ]
            }}
            """
            
            response = await asyncio.to_thread(
                self.ai_service.gemini_model.generate_content, lesson_prompt
            )
            
            try:
                lesson_data = json.loads(response.text)
                
                # Generate actual content for each activity
                enhanced_lesson = await self._generate_lesson_content(
                    db, lesson_data, user, user_profile
                )
                
                return {"success": True, "interactive_lesson": enhanced_lesson}
                
            except json.JSONDecodeError:
                return {"success": False, "error": "Failed to parse lesson structure"}
                
        except Exception as e:
            logger.error(f"Error creating interactive lesson: {e}")
            return {"success": False, "error": str(e)}

    # Private helper methods

    async def _analyze_user_for_journey(
        self,
        sync_db: Session,
        db: AsyncSession,
        user: User
    ) -> Dict[str, Any]:
        """Comprehensive user analysis for journey planning (legacy method)"""

        user_profile = await personal_trainer_ai_service._build_comprehensive_user_profile(db, user)
        progress_analytics = await personal_trainer_ai_service._get_user_progress_analytics(db, user.id)

        # Get onboarding data for deeper insights - use async session
        onboarding = await user_onboarding.get_by_user_id(db, user_id=user.id)

        return {
            "profile": user_profile,
            "progress": progress_analytics,
            "onboarding_data": {
                "assessed_level": onboarding.assessed_level if onboarding else None,
                "assessment_score": onboarding.assessment_score if onboarding else None,
                "selected_categories": onboarding.selected_categories if onboarding else [],
                "completion_status": onboarding.is_completed if onboarding else False
            },
            "learning_readiness_score": self._calculate_learning_readiness(user_profile, progress_analytics)
        }

    async def _analyze_user_for_journey_with_assessment(
        self,
        sync_db: Session,
        db: AsyncSession,
        user: User,
        journey_request: LearningJourneyRequest
    ) -> Dict[str, Any]:
        """Comprehensive user analysis using fresh assessment data from frontend"""

        # Use database data as fallback/base
        user_profile = await personal_trainer_ai_service._build_comprehensive_user_profile(db, user)
        progress_analytics = await personal_trainer_ai_service._get_user_progress_analytics(db, user.id)

        # Override with fresh assessment data from frontend
        assessment_data = journey_request.assessment_results or {}

        # Enhanced user profile using assessment results
        enhanced_profile = {
            **user_profile,  # Keep existing database data
            "current_level": journey_request.user_level,
            "preferred_categories": journey_request.preferred_categories,
            "learning_pace": journey_request.learning_pace,
            "assessment_results": assessment_data,
            "skill_scores": assessment_data.get("skill_scores", {}),
            "overall_assessment_score": assessment_data.get("overall_score", 0.0),
            "assessment_determined_level": assessment_data.get("determined_level", journey_request.user_level),
            "assessment_feedback": assessment_data.get("feedback", ""),
            "assessment_recommendations": assessment_data.get("recommendations", [])
        }

        # Update progress analytics with assessment data
        enhanced_progress = {
            **progress_analytics,
            "assessment_based_insights": {
                "current_level_confirmed": journey_request.user_level,
                "skill_breakdown": assessment_data.get("skill_scores", {}),
                "areas_for_improvement": self._identify_weak_areas_from_assessment(assessment_data),
                "learning_recommendations": assessment_data.get("recommendations", [])
            }
        }

        # Get onboarding data for additional context - use async session
        onboarding = await user_onboarding.get_by_user_id(db, user_id=user.id)

        return {
            "profile": enhanced_profile,
            "progress": enhanced_progress,
            "onboarding_data": {
                "assessed_level": journey_request.user_level,  # Use fresh assessment level
                "assessment_score": assessment_data.get("overall_score"),
                "selected_categories": journey_request.preferred_categories,
                "learning_pace": journey_request.learning_pace,
                "completion_status": onboarding.is_completed if onboarding else False
            },
            "learning_readiness_score": self._calculate_learning_readiness(enhanced_profile, enhanced_progress),
            "fresh_assessment_data": True  # Flag to indicate we used fresh data
        }

    def _identify_weak_areas_from_assessment(self, assessment_data: Dict[str, Any]) -> List[str]:
        """Identify areas for improvement based on assessment skill scores"""
        skill_scores = assessment_data.get("skill_scores", {})
        weak_areas = []

        # Define thresholds for identifying weak areas
        for skill, score in skill_scores.items():
            if isinstance(score, (int, float)) and score < 0.6:  # Below 60%
                weak_areas.append(skill)

        return weak_areas

    async def _generate_journey_structure_with_time_constraint(
        self,
        user_analysis: Dict[str, Any],
        duration_days: int,
        daily_study_minutes: int
    ) -> Dict[str, Any]:
        """Generate learning journey structure considering user's daily time commitment"""

        profile = user_analysis["profile"]
        progress = user_analysis["progress"]

        # Calculate total available study time
        total_available_minutes = duration_days * daily_study_minutes
        logger.info(f"User has {total_available_minutes} total minutes available over {duration_days} days")

        prompt = f"""
        Create a {duration_days}-day personalized English learning journey structure.

        User Time Commitment:
        - Daily study time: {daily_study_minutes} minutes
        - Total available time: {total_available_minutes} minutes
        - Journey duration: {duration_days} days

        Learner Analysis:
        - Level: {profile.get('current_level')}
        - Goals: {', '.join(profile.get('learning_goals', []))}
        - Weak Areas: {', '.join(progress.get('weak_areas', []))}
        - Strong Areas: {', '.join(progress.get('strong_areas', []))}
        - Preferred Categories: {', '.join(profile.get('preferred_categories', []))}
        - Personal Interests: {', '.join(profile.get('interests', [])) or 'not specified'}
        - Learning Pace: {profile.get('learning_pace')}

        Create a structured journey that fits within their {daily_study_minutes} minutes/day limit:
        1. Weekly themes and focuses (respecting daily time limits)
        2. Progressive difficulty scaling
        3. Realistic module durations that fit daily time commitment
        4. Skill development balance (listening, speaking, reading, writing)
        5. Category-specific content based on preferences

        Each daily session should be ≤ {daily_study_minutes} minutes.
        Total content should fit within {total_available_minutes} minutes.
        """

        try:
            journey_plan = await self.ai_service.generate_structured_content(
                prompt=prompt,
                content_type="learning_journey_structure",
                user_context=user_analysis
            )

            # Parse and validate the generated structure
            return self._parse_and_validate_journey_structure(
                journey_plan, duration_days, daily_study_minutes
            )

        except Exception as e:
            logger.error(f"Error generating journey structure: {e}")
            return self._create_fallback_journey_structure(
                user_analysis, duration_days, daily_study_minutes
            )

    def _parse_and_validate_journey_structure(
        self,
        journey_plan: str,
        duration_days: int,
        daily_study_minutes: int
    ) -> Dict[str, Any]:
        """Parse AI-generated journey structure and validate time constraints"""

        try:
            # Parse the JSON response from AI
            structure_data = json.loads(journey_plan) if isinstance(journey_plan, str) else journey_plan

            # Validate time constraints
            total_minutes = 0
            for week in structure_data.get("weeks", []):
                for day in week.get("days", []):
                    session_minutes = day.get("estimated_minutes", 0)
                    if session_minutes > daily_study_minutes:
                        logger.warning(f"Session duration {session_minutes} exceeds daily limit {daily_study_minutes}")
                        day["estimated_minutes"] = daily_study_minutes  # Cap at daily limit
                    total_minutes += day["estimated_minutes"]

            structure_data["total_estimated_minutes"] = total_minutes
            structure_data["daily_time_limit"] = daily_study_minutes
            structure_data["journey_duration_days"] = duration_days

            return structure_data

        except Exception as e:
            logger.error(f"Error parsing journey structure: {e}")
            return self._create_fallback_journey_structure(
                {"profile": {}, "progress": {}}, duration_days, daily_study_minutes
            )

    def _create_fallback_journey_structure(
        self,
        user_analysis: Dict[str, Any],
        duration_days: int,
        daily_study_minutes: int
    ) -> Dict[str, Any]:
        # """Create a basic journey structure when AI generation fails"""

        # profile = user_analysis.get("profile", {})
        # categories = profile.get("preferred_categories", ["general"])

        # # Create weekly structure respecting time limits
        # weeks = []
        # current_day = 1

        # for week_num in range(1, (duration_days // 7) + 2):
        #     week = {
        #         "week_number": week_num,
        #         "theme": f"Week {week_num}: Building Foundations",
        #         "focus_areas": ["vocabulary", "grammar", "listening"],
        #         "days": []
        #     }

        #     # Add up to 7 days or remaining days
        #     for day_offset in range(7):
        #         if current_day > duration_days:
        #             break

        #         day = {
        #             "day_number": current_day,
        #             "session_title": f"Day {current_day} Practice",
        #             "estimated_minutes": min(daily_study_minutes, 30),  # Cap at daily limit
        #             "skill_focus": ["vocabulary", "listening"][current_day % 2],
        #             "category": categories[current_day % len(categories)],
        #             "difficulty_level": profile.get("current_level", "A1")
        #         }

        #         week["days"].append(day)
        #         current_day += 1

        #     if week["days"]:  # Only add weeks with days
        #         weeks.append(week)

        # return {
        #     "journey_overview": f"{duration_days}-day personalized learning journey",
        #     "total_estimated_minutes": duration_days * min(daily_study_minutes, 30),
        #     "daily_time_limit": daily_study_minutes,
        #     "journey_duration_days": duration_days,
        #     "weeks": weeks,
        #     "categories_covered": categories,
        #     "skill_development_focus": ["listening", "speaking", "reading", "writing"]
        # }
        profile = user_analysis.get("profile", {})
        categories = profile.get("preferred_categories", ["general"])
        
        # Calculate weeks from duration_days
        total_weeks = max(1, math.ceil(duration_days / 7))
        total_hours = (duration_days * daily_study_minutes) / 60
        
        weeks = []
        for week_num in range(1, total_weeks + 1):
            week = {
                "week_number": week_num,
                "theme": f"Week {week_num}: Building Foundations",
                "focus_areas": ["vocabulary", "grammar", "listening"],
                "days": []
            }

            # Add up to 7 days or remaining days
            for day_offset in range(7):
                day_num = (week_num - 1) * 7 + day_offset + 1
                if day_num > duration_days:
                    break

                day = {
                    "day_number": day_num,
                    "session_title": f"Day {day_num} Practice",
                    "estimated_minutes": min(daily_study_minutes, 30),
                    "skill_focus": ["vocabulary", "listening"][day_num % 2],
                    "category": categories[day_num % len(categories)],
                    "difficulty_level": profile.get("current_level", "A1")
                }

                week["days"].append(day)

            if week["days"]:  # Only add weeks with days
                weeks.append(week)

        return {
            "journey_overview": f"{duration_days}-day personalized learning journey",
            "total_estimated_hours": total_hours,
            "daily_time_limit": daily_study_minutes,
            "journey_duration_days": duration_days,
            "weeks": weeks,
            "categories_covered": categories,
            "skill_development_focus": ["listening", "speaking", "reading", "writing"]
        }

    async def _generate_journey_structure(
        self,
        user_analysis: Dict[str, Any],
        duration_days: int
    ) -> Dict[str, Any]:
        """Generate overall learning journey structure using AI"""
        
        profile = user_analysis["profile"]
        progress = user_analysis["progress"]
        
        prompt = f"""
        Create a {duration_days}-day personalized English learning journey structure.
        
        Learner Analysis:
        - Level: {profile.get('current_level')}
        - Goals: {', '.join(profile.get('learning_goals', []))}
        - Weak Areas: {', '.join(progress.get('weak_areas', []))}
        - Strong Areas: {', '.join(progress.get('strong_areas', []))}
        - Daily Study Time: {profile.get('daily_study_commitment')} minutes
        - Learning Velocity: {progress.get('learning_velocity')}
        
        Create a structured journey with:
        1. Weekly themes and focuses
        2. Progressive difficulty scaling
        3. Skill integration across weeks
        4. Milestone checkpoints
        5. Adaptive branching points
        
        Format as JSON:
        {{
            "journey_overview": {{
                "title": "...",
                "duration_days": {duration_days},
                "target_improvement": "...",
                "success_metrics": ["...", "..."]
            }},
            "weeks": [
                {{
                    "week_number": 1,
                    "theme": "...",
                    "focus_skills": ["...", "..."],
                    "learning_objectives": ["...", "..."],
                    "daily_schedule": [
                        {{
                            "day": 1,
                            "focus": "...",
                            "content_types": ["...", "..."],
                            "estimated_minutes": {profile.get('daily_study_commitment')}
                        }}
                    ]
                }}
            ],
            "milestones": [
                {{
                    "milestone_day": 7,
                    "title": "...",
                    "assessment_criteria": "...",
                    "reward_message": "..."
                }}
            ]
        }}
        """
        
        response = await asyncio.to_thread(
            self.ai_service.gemini_model.generate_content, prompt
        )
        
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback structure
            return self._create_fallback_journey_structure({"profile": profile, "progress": {}}, duration_days, 25)

    async def _generate_week_content(
        self,
        db: AsyncSession,
        sync_db: Session,
        user: User,
        week_data: Dict[str, Any],
        user_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate actual content for a week of learning"""
        
        week_content = {"days": []}

        # Normalize days from either daily_schedule or days
        raw_days = list(week_data.get("daily_schedule", []))
        if not raw_days and week_data.get("days"):
            for d in week_data.get("days", []):
                raw_days.append({
                    "day": d.get("day_number") or d.get("day") or 1,
                    "content_types": d.get("content_types") or (
                        [d.get("skill_focus")] if d.get("skill_focus") else None
                    ),
                    "estimated_minutes": d.get("estimated_minutes", 20)
                })

        # Synthesize content types if missing
        default_mix = ["vocabulary", "reading", "listening"]

        for day_plan in raw_days:
            day_num = day_plan.get("day", 1)
            content_types = day_plan.get("content_types") or default_mix
            if isinstance(content_types, str):
                content_types = [content_types]

            per_type_minutes = max(5, int(day_plan.get("estimated_minutes", 30) / max(1, len(content_types))))

            day_content = {"day": day_num, "activities": []}

            for content_type in content_types:
                topic = self._get_day_topic(week_data.get("theme", "daily life"), day_num)

                content_result = await self._generate_single_content_piece(
                    db,
                    user,
                    content_type,
                    topic,
                    per_type_minutes,
                    {
                        **(user_analysis.get("profile", {}) or {}),
                        "day_number": day_num,
                    },
                )

                if content_result.get("success"):
                    day_content["activities"].append({
                        "type": content_type,
                        "topic": topic,
                        "content": content_result["content"]
                    })

            week_content["days"].append(day_content)
        
        return week_content

    async def _generate_single_content_piece(
        self,
        db: AsyncSession,
        user: User,
        content_type: str,
        topic: str,
        duration_minutes: int,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a single piece of content with full context"""
        
        try:
            if content_type == "reading":
                return await self._generate_contextual_reading(db, user, topic, user_context)
            elif content_type == "vocabulary":
                return await self._generate_contextual_vocabulary(db, user, topic, user_context)
            elif content_type == "grammar":
                return await self._generate_contextual_grammar(db, user, topic, user_context)
            elif content_type == "listening":
                return await self._generate_contextual_listening(db, user, topic, user_context)
            elif content_type == "speaking":
                return await self._generate_contextual_speaking(user, topic, user_context)
            elif content_type == "writing":
                return await self._generate_contextual_writing(user, topic, user_context)
            else:
                return {"success": False, "error": f"Unknown content type: {content_type}"}
                
        except Exception as e:
            logger.error(f"Error generating {content_type} content: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_contextual_reading(
        self, 
        db: AsyncSession, 
        user: User, 
        topic: str, 
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate reading content with full user context"""
        
        try:
            # Cache lookup
            day_number = int(user_context.get("day_number", 0))
            cache_key = build_cache_key(
                user_id=user.id,
                content_type="reading",
                topic=topic,
                level=user.current_level.value,
                day_number=day_number,
            )
            cached = await generated_content_cache_crud.get_by_key(db, cache_key=cache_key)
            if cached and cached.content:
                logger.info(f"Cache hit reading key={cache_key}")
                return {"success": True, "content": cached.content}
            # If not found for the specific day, attempt day 0 fallback (pre-generated week content)
            if day_number > 0:
                fallback_key = build_cache_key(
                    user_id=user.id,
                    content_type="reading",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=0,
                )
                cached0 = await generated_content_cache_crud.get_by_key(db, cache_key=fallback_key)
                if cached0 and cached0.content:
                    logger.info(f"Cache hit reading fallback key={fallback_key}")
                    return {"success": True, "content": cached0.content}

            result = await self.reading_service.generate_reading_text_with_vocabulary(
                db=db,
                level=DifficultyLevel(user.current_level.value),
                text_type=ReadingTextType.ARTICLE,
                topic=topic,
                word_count=200 if user.current_level.value in ["A1", "A2"] else 300,
                vocabulary_count=8 if user.current_level.value in ["A1", "A2"] else 12,
                include_comprehension_questions=True
            )
            
            await content_cache_service.save_cached(
                db,
                cache_key=cache_key,
                user_id=user.id,
                content_type="reading",
                topic=topic,
                level=user.current_level.value,
                day_number=day_number,
                payload=result,
            )
            logger.info(f"Cached reading key={cache_key}")

            return {"success": True, "content": result}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _generate_contextual_vocabulary(
        self, 
        db: AsyncSession, 
        user: User, 
        topic: str, 
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate vocabulary content with user context"""
        
        try:
            day_number = int(user_context.get("day_number", 0))
            cache_key = build_cache_key(
                user_id=user.id,
                content_type="vocabulary",
                topic=topic,
                level=user.current_level.value,
                day_number=day_number,
            )

            cached = await generated_content_cache_crud.get_by_key(db, cache_key=cache_key)
            if cached and cached.content:
                logger.info(f"Cache hit vocabulary key={cache_key}")
                return {"success": True, "content": cached.content}
            # Fallback to day 0 cache if day-specific miss
            if day_number > 0:
                fallback_key = build_cache_key(
                    user_id=user.id,
                    content_type="vocabulary",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=0,
                )
                cached0 = await generated_content_cache_crud.get_by_key(db, cache_key=fallback_key)
                if cached0 and cached0.content:
                    logger.info(f"Cache hit vocabulary fallback key={fallback_key}")
                    return {"success": True, "content": cached0.content}

            # Get existing vocabulary for this level/topic
            vocab_words = await vocabulary_crud.get_by_level_and_topic(
                db,
                level=DifficultyLevel(user.current_level.value),
                topic=topic,
                limit=15
            )
            
            if vocab_words:
                # Create personalized vocabulary exercises
                # Note: Use vocabulary_words as main key (Flutter expects this), but also include words for compatibility
                words_list = [
                    {
                        "word": word.word,
                        "definition": word.definition,
                        "example": word.example_sentence,
                        "pronunciation": word.pronunciation,
                        "difficulty": word.difficulty_level.value
                    } for word in vocab_words
                ]
                vocab_content = {
                    "topic": topic,
                    "level": user.current_level.value,
                    "vocabulary_words": words_list,  # Primary key for Flutter
                    "words": words_list,  # Fallback key for compatibility
                    "learning_activities": [
                        "Definition matching",
                        "Example sentence completion", 
                        "Pronunciation practice",
                        "Usage in context"
                    ]
                }
                await content_cache_service.save_cached(
                    db,
                    cache_key=cache_key,
                    user_id=user.id,
                    content_type="vocabulary",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=day_number,
                    payload=vocab_content,
                )
                logger.info(f"Cached vocabulary key={cache_key}")

                return {"success": True, "content": vocab_content}
            else:
                # Generate using AI if no existing vocabulary
                try:
                    result = await self.ai_service.generate_exercise_content(
                        topic=topic,
                        difficulty_level=user.current_level.value,
                        exercise_type="vocabulary",
                        count=10
                    )
                except Exception as ai_err:
                    logger.error(f"AI vocabulary generation error: {ai_err}")
                    result = {"success": False, "error": str(ai_err)}

                if not result.get("success"):
                    fallback = self._build_fallback_vocabulary(topic, user.current_level.value)
                    await content_cache_service.save_cached(
                        db,
                        cache_key=cache_key,
                        user_id=user.id,
                        content_type="vocabulary",
                        topic=topic,
                        level=user.current_level.value,
                        day_number=day_number,
                        payload=fallback,
                        status="fallback",
                        error=result.get("error"),
                    )
                    logger.warning(f"Using fallback vocabulary for topic '{topic}' due to AI error: {result.get('error')}")
                    return {"success": True, "content": fallback}

            normalized = self._normalize_ai_exercise_payload(result, content_type="vocabulary")

            await content_cache_service.save_cached(
                db,
                cache_key=cache_key,
                user_id=user.id,
                content_type="vocabulary",
                topic=topic,
                level=user.current_level.value,
                day_number=day_number,
                payload=normalized,
            )
            logger.info(f"Cached vocabulary key={cache_key} (AI-generated)")

            return {"success": True, "content": normalized}
                
        except Exception as e:
            logger.error(f"Vocabulary generation failed; using fallback. Err={e}")
            fallback = self._build_fallback_vocabulary(topic, user.current_level.value)
            try:
                await content_cache_service.save_cached(
                    db,
                    cache_key=build_cache_key(
                        user_id=user.id,
                        content_type="vocabulary",
                        topic=topic,
                        level=user.current_level.value,
                        day_number=int(user_context.get("day_number", 0)),
                    ),
                    user_id=user.id,
                    content_type="vocabulary",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=int(user_context.get("day_number", 0)),
                    payload=fallback,
                    status="fallback",
                    error=str(e),
                )
            except Exception:
                # If caching fallback fails, still return the content
                pass
            return {"success": True, "content": fallback}

    async def _generate_contextual_grammar(
        self, 
        db: AsyncSession,
        user: User, 
        topic: str, 
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate grammar content with user context and resilient fallback"""
        
        day_number = int(user_context.get("day_number", 0))
        cache_key = build_cache_key(
            user_id=user.id,
            content_type="grammar",
            topic=topic,
            level=user.current_level.value,
            day_number=day_number,
        )

        try:
            cached = await generated_content_cache_crud.get_by_key(db, cache_key=cache_key)
            if cached and cached.content:
                logger.info(f"Cache hit grammar key={cache_key}")
                return {"success": True, "content": cached.content}
            if day_number > 0:
                fallback_key = build_cache_key(
                    user_id=user.id,
                    content_type="grammar",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=0,
                )
                cached0 = await generated_content_cache_crud.get_by_key(db, cache_key=fallback_key)
                if cached0 and cached0.content:
                    logger.info(f"Cache hit grammar fallback key={fallback_key}")
                    return {"success": True, "content": cached0.content}

            try:
                result = await self.ai_service.generate_exercise_content(
                    topic=topic,
                    difficulty_level=user.current_level.value,
                    exercise_type="grammar",
                    count=5
                )
            except Exception as ai_err:
                logger.error(f"AI grammar generation error: {ai_err}")
                result = {"success": False, "error": str(ai_err)}

            if not result.get("success"):
                fallback = self._build_fallback_grammar(topic, user.current_level.value)
                await content_cache_service.save_cached(
                    db,
                    cache_key=cache_key,
                    user_id=user.id,
                    content_type="grammar",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=day_number,
                    payload=fallback,
                    status="fallback",
                    error=result.get("error"),
                )
                logger.warning(f"Using fallback grammar for topic '{topic}' due to AI error: {result.get('error')}")
                return {"success": True, "content": fallback}

            normalized = self._normalize_ai_exercise_payload(result, content_type="grammar")

            await content_cache_service.save_cached(
                db,
                cache_key=cache_key,
                user_id=user.id,
                content_type="grammar",
                topic=topic,
                level=user.current_level.value,
                day_number=day_number,
                payload=normalized,
            )
            logger.info(f"Cached grammar key={cache_key}")

            return {"success": True, "content": normalized}
            
        except Exception as e:
            logger.error(f"Grammar generation failed; using fallback. Err={e}")
            fallback = self._build_fallback_grammar(topic, user.current_level.value)
            try:
                await content_cache_service.save_cached(
                    db,
                    cache_key=cache_key,
                    user_id=user.id,
                    content_type="grammar",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=day_number,
                    payload=fallback,
                    status="fallback",
                    error=str(e),
                )
            except Exception:
                pass
            return {"success": True, "content": fallback}

    async def _generate_contextual_listening(
        self,
        db: AsyncSession,
        user: User,
        topic: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate listening content with user context using Gemini TTS"""

        try:
            # Cache lookup
            day_number = int(user_context.get("day_number", 0))
            cache_key = build_cache_key(
                user_id=user.id,
                content_type="listening",
                topic=topic,
                level=user.current_level.value,
                day_number=day_number,
            )
            cached = await generated_content_cache_crud.get_by_key(db, cache_key=cache_key)
            if cached and cached.content:
                logger.info(f"Cache hit listening key={cache_key}")
                return {"success": True, "content": cached.content}
            if day_number > 0:
                fallback_key = build_cache_key(
                    user_id=user.id,
                    content_type="listening",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=0,
                )
                cached0 = await generated_content_cache_crud.get_by_key(db, cache_key=fallback_key)
                if cached0 and cached0.content:
                    logger.info(f"Cache hit listening fallback key={fallback_key}")
                    return {"success": True, "content": cached0.content}

            # Generate listening content with audio using Gemini TTS
            listening_result = await self.tts_service.generate_listening_content(
                topic=topic,
                difficulty_level=user.current_level.value,
                content_type="conversation",  # Default to conversation
                speaker_names=["Dr. Anya", "Liam"]  # Default speakers from user's example
            )

            if not listening_result["success"]:
                # Fallback to basic content if TTS fails
                logger.warning(f"TTS generation failed for topic '{topic}': {listening_result.get('error', 'Unknown error')}")
                return self._generate_fallback_listening_content(topic, user.current_level.value)

            # Transform the result to match expected format
            listening_content = {
                "topic": topic,
                "level": user.current_level.value,
                "audio_script": listening_result["script"],
                "comprehension_questions": [
                    q if isinstance(q, dict) else {
                        "question": str(q),
                        "correct_answer": topic,
                        "type": "short_answer"
                    }
                    for q in listening_result.get("comprehension_questions", [])
                ],
                "audio_url": listening_result["audio_url"],
                "duration_seconds": listening_result["duration_seconds"],
                "speakers": listening_result["speakers"],
                "vocabulary_focus": listening_result.get("vocabulary_focus", []),
                "tts_model": listening_result.get("tts_model", "gemini-2.5-flash-preview-tts"),
                "voice": listening_result.get("voice", "Zephyr")
            }

            # Persist cache with refs for audio
            try:
                audio_filename = listening_result.get("filename")
                audio_path = None
                if audio_filename:
                    audio_path = os.path.join(getattr(settings, "AUDIO_STORAGE_DIR", "storage/audio"), "tts", audio_filename)
                await content_cache_service.save_cached(
                    db,
                    cache_key=cache_key,
                    user_id=user.id,
                    content_type="listening",
                    topic=topic,
                    level=user.current_level.value,
                    day_number=day_number,
                    payload=listening_content,
                    refs={"audio_url": listening_result.get("audio_url"), "audio_path": audio_path},
                    model_used=listening_result.get("tts_model"),
                )
                logger.info(f"Cached listening key={cache_key}")
            except Exception as cache_err:
                logger.warning(f"Failed to cache listening content: {cache_err}")

            return {"success": True, "content": listening_content}

        except Exception as e:
            logger.error(f"Failed to generate listening content: {e}")
            return self._generate_fallback_listening_content(topic, user.current_level.value)

    def _generate_fallback_listening_content(self, topic: str, level: str) -> Dict[str, Any]:
        """Generate basic listening content when TTS fails"""
        listening_content = {
            "topic": topic,
            "level": level,
            "audio_script": f"Listening content about {topic} for {level} level",
            "comprehension_questions": [
                {
                    "question": f"What is the main topic of this audio?",
                    "correct_answer": topic,
                    "type": "short_answer"
                }
            ],
            "audio_url": None,
            "duration_seconds": 120,
            "fallback": True
        }

        return {"success": True, "content": listening_content}

    def _normalize_ai_exercise_payload(self, result: Dict[str, Any], content_type: str) -> Dict[str, Any]:
        """
        Normalize AI exercise payloads so cached content is structured (exercises + vocab_words).
        The DB will then store parsed JSON instead of a raw markdown string.
        """
        payload: Dict[str, Any] = result or {}

        # If AI returned a string inside "content", try to parse it as JSON
        if isinstance(payload, dict) and isinstance(payload.get("content"), str):
            raw_content = payload["content"].strip()
            if raw_content.startswith("```"):
                raw_content = raw_content.replace("```json", "").replace("```", "").strip()
            try:
                parsed = json.loads(raw_content)
                if isinstance(parsed, dict):
                    payload.update(parsed)
            except json.JSONDecodeError:
                pass

        # Flatten lesson/practice sections from richer prompts
        if isinstance(payload, dict):
            lesson = payload.get("lesson")
            if isinstance(lesson, dict):
                lesson_vocab = lesson.get("vocabulary_words") or lesson.get("vocabulary")
                if lesson_vocab and not payload.get("vocabulary_words"):
                    payload["vocabulary_words"] = lesson_vocab
                if lesson.get("grammar_point") and not payload.get("grammar_summary"):
                    payload["grammar_summary"] = lesson.get("grammar_point")

            practice = payload.get("practice")
            if isinstance(practice, dict) and not payload.get("exercises"):
                maybe_ex = practice.get("questions") or practice.get("exercises")
                if isinstance(maybe_ex, list):
                    payload["exercises"] = maybe_ex

        # Build vocabulary_words from exercises when missing (helps UI show a list)
        if isinstance(payload, dict):
            exercises = payload.get("exercises") or []
            if (
                exercises
                and content_type in {"vocabulary", "grammar"}
                and not payload.get("vocabulary_words")
                and not payload.get("words")
            ):
                vocab_words = []
                for ex in exercises:
                    if not isinstance(ex, dict):
                        continue
                    word = ex.get("correct_answer") or ex.get("question") or ex.get("target_word") or ""
                    definition = ex.get("explanation") or ex.get("question") or "Practice this term."
                    vocab_words.append({"word": str(word), "definition": str(definition)})
                    if len(vocab_words) >= 12:
                        break
                if vocab_words:
                    payload["vocabulary_words"] = vocab_words
            if payload.get("vocabulary_words") and not payload.get("words"):
                payload["words"] = payload.get("vocabulary_words")

        return payload

    def _build_fallback_vocabulary(self, topic: str, level: str) -> Dict[str, Any]:
        """Offline fallback vocabulary set when AI/quota is unavailable"""
        words = [
            {"word": "foundation", "definition": "the basic support or base of something"},
            {"word": "concept", "definition": "an idea or principle"},
            {"word": "practice", "definition": "to do something many times to improve"},
            {"word": "review", "definition": "to look at something again to remember it"},
            {"word": "goal", "definition": "something you want to achieve"},
            {"word": "plan", "definition": "a set of steps to reach a goal"},
            {"word": "focus", "definition": "to give attention to something"},
            {"word": "progress", "definition": "improvement over time"},
        ]

        exercises = [
            {
                "question": "The _______ is the strong base of a building or idea.",
                "options": ["roof", "window", "foundation", "light"],
                "correct_answer": "foundation",
                "explanation": "A foundation is the base that supports everything above it.",
            },
            {
                "question": "When you study again to remember, you _______.",
                "options": ["review", "sleep", "forget", "hide"],
                "correct_answer": "review",
                "explanation": "Reviewing means looking again at what you learned.",
            },
            {
                "question": "A clear _______ helps you know what you want to achieve.",
                "options": ["goal", "noise", "rain", "bus"],
                "correct_answer": "goal",
                "explanation": "A goal is a target you want to reach.",
            },
            {
                "question": "To _______ means to give all your attention to one thing.",
                "options": ["focus", "jump", "visit", "wash"],
                "correct_answer": "focus",
                "explanation": "Focus is concentrating on one task or idea.",
            },
            {
                "question": "Doing something many times to improve is called _______.",
                "options": ["practice", "rest", "ignore", "forget"],
                "correct_answer": "practice",
                "explanation": "Practice is repeating an activity so you get better.",
            },
        ]

        return {
            "topic": topic,
            "level": level,
            "vocabulary_words": words,
            "words": words,
            "exercises": exercises,
            "source": "offline_fallback",
        }

    def _build_fallback_grammar(self, topic: str, level: str) -> Dict[str, Any]:
        """Offline fallback grammar exercises to avoid blank screens"""
        exercises = [
            {
                "question": "I ____ to class every Monday.",
                "options": ["go", "goes", "going", "to go"],
                "correct_answer": "go",
                "explanation": "Use the base form with I/you/we/they in the present simple.",
            },
            {
                "question": "She ____ coffee in the morning.",
                "options": ["drink", "drinks", "drinking", "to drink"],
                "correct_answer": "drinks",
                "explanation": "Add -s for he/she/it in the present simple.",
            },
            {
                "question": "They ____ not at home right now.",
                "options": ["is", "are", "be", "am"],
                "correct_answer": "are",
                "explanation": "Use 'are' with plural subjects like 'they'.",
            },
            {
                "question": "We ____ English every day to improve.",
                "options": ["study", "studies", "studying", "studied"],
                "correct_answer": "study",
                "explanation": "With 'we', use the base form 'study' in present simple.",
            },
            {
                "question": "He ____ from Iran.",
                "options": ["come", "comes", "coming", "to come"],
                "correct_answer": "comes",
                "explanation": "For he/she/it, the verb takes an -s ending.",
            },
        ]

        return {
            "topic": topic,
            "level": level,
            "grammar_point": "Present simple basics",
            "grammar_summary": {
                "title": "Present simple basics",
                "explanation": "Use the base form with I/you/we/they and add -s for he/she/it in statements about habits and facts.",
                "examples": [
                    "I go to class every Monday.",
                    "She drinks coffee in the morning.",
                    "They are not at home right now.",
                ],
                "common_mistakes": [
                    "Forgetting the -s with he/she/it.",
                    "Using 'is' instead of 'are' with plural subjects.",
                ],
            },
            "lesson": {
                "objective": "Review present simple verbs for daily routines and accuracy.",
                "vocabulary_words": [
                    {"word": "go", "definition": "move or travel to a place", "example": "I go to class every Monday."},
                    {"word": "drink", "definition": "take liquid into the mouth and swallow", "example": "She drinks coffee in the morning."},
                    {"word": "be", "definition": "exist or live", "example": "They are not at home right now."},
                    {"word": "study", "definition": "learn about a subject", "example": "We study English every day to improve."},
                    {"word": "come", "definition": "move toward the speaker", "example": "He comes from Iran."},
                ],
                "grammar_point": {
                    "title": "Present simple basics",
                    "explanation": "Use base form for I/you/we/they; add -s for he/she/it.",
                    "examples": [
                        "I go to work on Mondays.",
                        "She drinks tea every morning.",
                        "They are happy with the plan."
                    ],
                    "common_mistakes": [
                        "Using 'goes' with I/you/we/they.",
                        "Forgetting the -s with he/she/it."
                    ]
                }
            },
            "exercises": exercises,
            "vocabulary_words": [
                {"word": "go", "definition": "move or travel to a place", "example": "I go to class every Monday."},
                {"word": "drink", "definition": "take liquid into the mouth and swallow", "example": "She drinks coffee in the morning."},
                {"word": "be", "definition": "exist or live", "example": "They are not at home right now."},
                {"word": "study", "definition": "learn about a subject", "example": "We study English every day to improve."},
                {"word": "come", "definition": "move toward the speaker", "example": "He comes from Iran."},
            ],
            "words": [
                {"word": "go", "definition": "move or travel to a place", "example": "I go to class every Monday."},
                {"word": "drink", "definition": "take liquid into the mouth and swallow", "example": "She drinks coffee in the morning."},
                {"word": "be", "definition": "exist or live", "example": "They are not at home right now."},
                {"word": "study", "definition": "learn about a subject", "example": "We study English every day to improve."},
                {"word": "come", "definition": "move toward the speaker", "example": "He comes from Iran."},
            ],
            "source": "offline_fallback",
        }

    async def _generate_contextual_speaking(
        self,
        user: User,
        topic: str,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate speaking content with read-aloud text for pronunciation practice"""

        try:
            level = user.current_level.value
            
            # Generate a proper read-aloud text based on topic and level
            read_aloud_text = self._generate_read_aloud_text(topic, level)
            
            # Build standardized speaking content structure with read-aloud mode
            speaking_content = {
                "topic": topic,
                "level": level,
                "content_type": "speaking",
                "mode": "read_aloud",
                # Main text for the user to read aloud
                "prompt_text": read_aloud_text["primary"],
                # Individual sentences for step-by-step practice
                "sentences": read_aloud_text["sentences"],
                # Vocabulary words highlighted in the text
                "vocabulary_focus": read_aloud_text["vocabulary_focus"],
                # Tips for speaking
                "speaking_tips": [
                    "Read each sentence clearly and naturally",
                    "Focus on pronunciation of highlighted words",
                    "Maintain a steady, conversational pace",
                    "Try to express the meaning as you speak"
                ],
            }

            return {"success": True, "content": speaking_content}

        except Exception as e:
            logger.error(f"Speaking generation error: {e}")
            # Return a fallback read-aloud text
            fallback_content = self._generate_read_aloud_text(topic, user.current_level.value)
            return {"success": True, "content": {
                "topic": topic,
                "level": user.current_level.value,
                "content_type": "speaking",
                "mode": "read_aloud",
                "prompt_text": fallback_content["primary"],
                "sentences": fallback_content["sentences"],
                "vocabulary_focus": fallback_content["vocabulary_focus"],
                "speaking_tips": [
                    "Read each sentence clearly",
                    "Focus on pronunciation",
                    "Speak at a natural pace"
                ],
            }}

    def _generate_read_aloud_text(self, topic: str, level: str) -> Dict[str, Any]:
        """Generate read-aloud text appropriate for the topic and level"""
        
        # Define read-aloud texts by topic
        texts_by_topic = {
            "daily life": {
                "primary": "Every morning I wake up early and start my day with a healthy breakfast. I usually have coffee with toast and some fresh fruit. After breakfast, I check my schedule and plan the important tasks for the day. In the evening, I like to relax and spend time with my family.",
                "sentences": [
                    "Every morning I wake up early and start my day with a healthy breakfast.",
                    "I usually have coffee with toast and some fresh fruit.",
                    "After breakfast, I check my schedule and plan the important tasks for the day.",
                    "In the evening, I like to relax and spend time with my family."
                ],
                "vocabulary_focus": ["morning", "breakfast", "schedule", "tasks", "relax"]
            },
            "travel": {
                "primary": "I love to travel and explore new places. Last summer, I visited a beautiful city in Europe. The architecture was amazing and the local food was delicious. I took many photographs to remember the wonderful experience.",
                "sentences": [
                    "I love to travel and explore new places.",
                    "Last summer, I visited a beautiful city in Europe.",
                    "The architecture was amazing and the local food was delicious.",
                    "I took many photographs to remember the wonderful experience."
                ],
                "vocabulary_focus": ["travel", "explore", "architecture", "delicious", "experience"]
            },
            "food": {
                "primary": "Cooking is one of my favorite hobbies. I enjoy preparing meals for my family and friends. Fresh ingredients are important for making tasty dishes. My specialty is pasta with homemade tomato sauce.",
                "sentences": [
                    "Cooking is one of my favorite hobbies.",
                    "I enjoy preparing meals for my family and friends.",
                    "Fresh ingredients are important for making tasty dishes.",
                    "My specialty is pasta with homemade tomato sauce."
                ],
                "vocabulary_focus": ["cooking", "preparing", "ingredients", "tasty", "specialty"]
            },
            "work": {
                "primary": "I work in a modern office in the city center. My job involves meeting with clients and managing important projects. Communication skills are essential in my profession. I always try to meet deadlines and deliver quality work.",
                "sentences": [
                    "I work in a modern office in the city center.",
                    "My job involves meeting with clients and managing important projects.",
                    "Communication skills are essential in my profession.",
                    "I always try to meet deadlines and deliver quality work."
                ],
                "vocabulary_focus": ["office", "clients", "projects", "communication", "deadlines"]
            },
            "health": {
                "primary": "Taking care of your health is very important. I try to exercise regularly and eat balanced meals. Getting enough sleep helps me feel energetic during the day. Mental health is just as important as physical health.",
                "sentences": [
                    "Taking care of your health is very important.",
                    "I try to exercise regularly and eat balanced meals.",
                    "Getting enough sleep helps me feel energetic during the day.",
                    "Mental health is just as important as physical health."
                ],
                "vocabulary_focus": ["health", "exercise", "balanced", "energetic", "mental"]
            },
            "entertainment": {
                "primary": "I enjoy watching movies and listening to music in my free time. My favorite genre is comedy because it makes me laugh. I also like to read books, especially mystery novels. Entertainment helps me relax after a busy week.",
                "sentences": [
                    "I enjoy watching movies and listening to music in my free time.",
                    "My favorite genre is comedy because it makes me laugh.",
                    "I also like to read books, especially mystery novels.",
                    "Entertainment helps me relax after a busy week."
                ],
                "vocabulary_focus": ["entertainment", "genre", "comedy", "mystery", "relax"]
            },
            "education": {
                "primary": "Learning new things is an exciting journey. I believe education opens many doors to opportunity. Practicing every day helps improve your skills. Setting clear goals makes learning more effective and enjoyable.",
                "sentences": [
                    "Learning new things is an exciting journey.",
                    "I believe education opens many doors to opportunity.",
                    "Practicing every day helps improve your skills.",
                    "Setting clear goals makes learning more effective and enjoyable."
                ],
                "vocabulary_focus": ["learning", "education", "opportunity", "practicing", "goals"]
            },
        }
        
        # Find matching topic or use default
        topic_lower = topic.lower()
        for key in texts_by_topic:
            if key in topic_lower or topic_lower in key:
                return texts_by_topic[key]
        
        # Default fallback text
        return texts_by_topic["daily life"]

    async def _generate_contextual_writing(
        self, 
        user: User, 
        topic: str, 
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate writing content with user context"""
        
        try:
            result = await self.ai_service.generate_exercise_content(
                topic=topic,
                difficulty_level=user.current_level.value,
                exercise_type="writing",
                count=3
            )
            
            return {"success": result.get("success", False), "content": result}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Utility methods

    def _get_skill_performance(self, progress_analytics: Dict[str, Any], skill: str) -> str:
        """Get performance level for a specific skill"""
        
        weak_areas = progress_analytics.get("weak_areas", [])
        strong_areas = progress_analytics.get("strong_areas", [])
        
        if skill in weak_areas:
            return "needs_improvement"
        elif skill in strong_areas:
            return "strong"
        else:
            return "average"

    def _calculate_learning_readiness(
        self, 
        user_profile: Dict[str, Any], 
        progress_analytics: Dict[str, Any]
    ) -> float:
        """Calculate how ready the user is for personalized learning (0.0-1.0)"""
        
        score = 0.0
        
        # Profile completeness
        if user_profile.get("learning_goals"):
            score += 0.2
        if user_profile.get("preferred_categories"):
            score += 0.2
        if user_profile.get("target_timeline") != "flexible":
            score += 0.1
        
        # Engagement indicators
        if progress_analytics.get("current_streak", 0) > 3:
            score += 0.2
        if progress_analytics.get("total_study_time", 0) > 300:  # 5+ hours
            score += 0.3
        
        return min(score, 1.0)

    async def _get_current_user_state(
        self, 
        db: AsyncSession, 
        sync_db: Session, 
        user: User
    ) -> Dict[str, Any]:
        """Get real-time user state for adaptive content generation"""
        
        profile = await personal_trainer_ai_service._build_comprehensive_user_profile(db, user)
        progress = await personal_trainer_ai_service._get_user_progress_analytics(db, user.id)
        
        # Add real-time factors
        return {
            **profile,
            **progress,
            "session_context": {
                "time_of_day": "flexible",  # Could be enhanced with actual time
                "energy_level": "normal",  # Could be tracked
                "last_session_performance": progress.get("average_accuracy", 0)
            }
        }

    async def _calculate_optimal_content_mix(
        self, 
        current_state: Dict[str, Any], 
        session_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate optimal mix of content types for current session"""
        
        available_time = int(session_context.get("duration_minutes", current_state.get("daily_study_commitment", 30)))
        weak_areas = current_state.get("weak_areas", [])

        # Get user's preferred categories for topic selection
        preferred_categories = current_state.get("preferred_categories", [])
        
        # Use day_number to vary topics, but incorporate user preferences
        day_number = int(session_context.get("day_number", 0))
        
        # If user has preferred categories, rotate through them based on day number
        topic_override = None
        if preferred_categories and day_number > 0:
            # Cycle through user's preferred categories
            category_index = (day_number - 1) % len(preferred_categories)
            preferred_cat = preferred_categories[category_index]
            cat_id = preferred_cat.value if hasattr(preferred_cat, 'value') else str(preferred_cat)
            topic_override = self._suggest_topic_for_skill("vocabulary", {"preferred_categories": [cat_id]})
        elif day_number > 0:
            # No preferences - use generic week-based topic
            week_num = math.ceil(day_number / 7)
            topic_override = f"Week {week_num}: Building Foundations day {day_number}"
        
        # Base allocation
        components = []
        
        # Always include some vocabulary (foundation)
        components.append({
            "type": "vocabulary",
            "topic": topic_override or self._suggest_topic_for_skill("vocabulary", current_state),
            "duration_minutes": max(5, int(available_time * 0.2)),
            "priority": "high" if "vocabulary" in weak_areas else "medium"
        })
        
        # Add skill based on weak areas or preferences
        if weak_areas:
            primary_focus = weak_areas[0]
            components.append({
                "type": primary_focus,
                "topic": topic_override or self._suggest_topic_for_skill(primary_focus, current_state),
                "duration_minutes": int(available_time * 0.3),
                "priority": "high"
            })
        
        # Ensure broad skill coverage: grammar, listening, reading, speaking, writing
        coverage_order = ["grammar", "listening", "reading", "speaking", "writing"]
        existing_types = {c["type"] for c in components}
        for skill in coverage_order:
            if len(components) >= 5:
                break
            if skill not in existing_types:
                components.append({
                    "type": skill,
                    "topic": topic_override or self._suggest_topic_for_skill(skill, current_state),
                    "duration_minutes": 0,  # placeholder; will distribute below
                    "priority": "medium"
                })
                existing_types.add(skill)

        # Distribute remaining time evenly among components not yet assigned duration
        time_used = sum(int(c.get("duration_minutes", 0)) for c in components)
        remaining_time = max(5, available_time - time_used)
        zero_duration_components = [c for c in components if int(c.get("duration_minutes", 0)) <= 0]
        if zero_duration_components:
            share = max(5, int(remaining_time / len(zero_duration_components)))
            for c in zero_duration_components:
                c["duration_minutes"] = share
        else:
            # If all have durations but time remains, add it to primary focus (first item)
            if remaining_time > 0 and components:
                components[0]["duration_minutes"] = int(components[0]["duration_minutes"]) + remaining_time
        
        return {
            "components": components,
            "total_duration": available_time,
            "adaptation_reason": f"Focused on {', '.join(weak_areas) if weak_areas else 'balanced skills'}",
            "estimated_difficulty": "appropriate"
        }

    def _suggest_topic_for_skill(self, skill: str, user_state: Dict[str, Any]) -> str:
        """Suggest appropriate topic for a specific skill based on user preferences"""
        
        preferred_categories = user_state.get("preferred_categories", [])
        
        # Map frontend category IDs to engaging topics
        category_topics = {
            # Frontend categories
            "daily_life": "daily life and routines",
            "food": "food, dining, and cooking",
            "travel": "travel and tourism",
            "business": "workplace and professional communication",
            "entertainment": "movies, music, and hobbies",
            "shopping": "shopping and market conversations",
            "health": "health, fitness, and medical topics",
            "education": "education and academic topics",
            "technology": "technology and digital life",
            "culture": "culture, arts, and traditions",
            # Legacy/backend categories for backwards compatibility
            "general_english": "daily life and conversations",
            "business_english": "workplace communication",
            "travel_english": "travel and tourism", 
            "conversation_practice": "social interactions",
            "vocabulary_building": "common expressions",
            "grammar_focus": "sentence structure"
        }
        
        # Try to find a matching category from user preferences
        if preferred_categories:
            for category in preferred_categories:
                # Handle both string and enum formats
                cat_id = category.value if hasattr(category, 'value') else str(category)
                if cat_id in category_topics:
                    return category_topics[cat_id]
            # If no exact match, try the first category anyway
            first_cat = preferred_categories[0]
            cat_id = first_cat.value if hasattr(first_cat, 'value') else str(first_cat)
            return category_topics.get(cat_id, "general topics")
        
        # Default topics by skill when no categories specified
        skill_topics = {
            "vocabulary": "daily routines and common words",
            "grammar": "practical grammar structures",
            "reading": "short stories and articles",
            "listening": "everyday conversations",
            "speaking": "introductions and daily communication",
            "writing": "personal messages and emails"
        }
        
        return skill_topics.get(skill, "general topics")

    def _get_day_topic(self, week_theme: str, day_number: int) -> str:
        """Get specific topic for a day within a week theme"""
        
        # This could be enhanced with more sophisticated topic progression
        topic_progressions = {
            "daily life": ["morning routine", "family time", "meals", "evening activities", "weekend plans"],
            "work": ["job interview", "office communication", "meetings", "presentations", "teamwork"],
            "travel": ["planning trip", "at airport", "hotel check-in", "sightseeing", "local food"]
        }
        
        if week_theme in topic_progressions:
            topics = topic_progressions[week_theme]
            return topics[(day_number - 1) % len(topics)]
        
        return f"{week_theme} day {day_number}"

    async def _generate_lesson_content(
        self,
        db: AsyncSession,
        lesson_data: Dict[str, Any],
        user: User,
        user_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate actual content for lesson activities"""
        
        enhanced_phases = []
        
        for phase in lesson_data.get("lesson_phases", []):
            enhanced_activities = []
            
            for activity in phase.get("activities", []):
                if activity.get("activity_type") in ["vocabulary", "grammar", "reading", "speaking", "writing"]:
                    # Generate content for this activity
                    content_result = await self._generate_single_content_piece(
                        db, user, activity["activity_type"], 
                        lesson_data["lesson_overview"]["topic"],
                        phase["duration_minutes"], user_profile
                    )
                    activity["generated_content"] = content_result.get("content") if content_result.get("success") else None
                    activity["content_ready"] = content_result.get("success", False)
                
                enhanced_activities.append(activity)
            
            phase["activities"] = enhanced_activities
            enhanced_phases.append(phase)
        
        lesson_data["lesson_phases"] = enhanced_phases
        return lesson_data

    # NOTE: Removed duplicate fallback method with inconsistent signature to avoid runtime errors

    def _generate_weakness_improvement_plan(self, weaknesses: List[str]) -> List[str]:
        """Generate actionable improvement recommendations for weaknesses"""
        
        improvement_strategies = {
            "vocabulary": [
                "Practice 10 new words daily with spaced repetition",
                "Read texts slightly above your level to encounter new words",
                "Keep a vocabulary journal with personal examples"
            ],
            "grammar": [
                "Complete one grammar exercise daily",
                "Focus on one grammar rule per week",
                "Practice writing sentences using new grammar patterns"
            ],
            "speaking": [
                "Practice speaking for 5 minutes daily",
                "Record yourself and listen back for improvement",
                "Practice pronunciation with audio resources"
            ],
            "listening": [
                "Listen to English content 15 minutes daily",
                "Start with slower speech and gradually increase speed",
                "Practice with different accents and voices"
            ],
            "reading": [
                "Read for 10 minutes daily at your level",
                "Gradually increase text complexity",
                "Practice different text types (news, stories, articles)"
            ],
            "writing": [
                "Write short texts daily (50-100 words)",
                "Focus on clear structure and correct grammar",
                "Get feedback and revise your writing"
            ]
        }
        
        recommendations = []
        for weakness in weaknesses:
            if weakness in improvement_strategies:
                recommendations.extend(improvement_strategies[weakness][:2])  # Take first 2 for each
        
        return recommendations

    # =====================================================
    # WEEKLY PLAN SYSTEM - New methods for week-based generation
    # =====================================================

    async def create_initial_week_plan(
        self,
        db: AsyncSession,
        user: User,
        journey_request: LearningJourneyRequest
    ) -> Dict[str, Any]:
        """
        Create ONLY the first week (7 days) plan after assessment.
        Content is generated in background, user gets immediate response.
        
        Returns plan structure immediately, queues content generation.
        """
        try:
            logger.info(f"Creating Week 1 plan for user {user.id}")
            
            # Check if week 1 already exists
            existing_week = await weekly_learning_plan_crud.get_by_user_and_week(
                db, user_id=user.id, week_number=1
            )
            
            if existing_week and existing_week.status == "ready":
                return {
                    "success": True,
                    "week_number": 1,
                    "plan": existing_week.plan_data,
                    "status": "ready",
                    "message": "Week 1 plan already exists"
                }
            
            # Get or create user weekly progress
            progress = await user_weekly_progress_crud.get_or_create(db, user_id=user.id)
            
            # Generate week 1 structure quickly (no actual content)
            week_structure = self._create_week_structure(
                week_number=1,
                user_level=journey_request.user_level,
                preferred_categories=journey_request.preferred_categories,
                daily_study_minutes=journey_request.daily_study_time_minutes,
                assessment_results=journey_request.assessment_results
            )
            
            # Create or update the weekly plan record
            if existing_week:
                plan_record = await weekly_learning_plan_crud.update_plan_data(
                    db, plan_id=existing_week.id, plan_data=week_structure
                )
                await weekly_learning_plan_crud.update_status(
                    db, plan_id=existing_week.id, status="generating"
                )
            else:
                plan_record = await weekly_learning_plan_crud.create(
                    db,
                    user_id=user.id,
                    week_number=1,
                    plan_data=week_structure,
                    status="generating"
                )
            
            # Queue background content generation for days 1-3
            from app.tasks.weekly_plan_tasks import generate_days_content
            generate_days_content.delay(
                user_id=user.id,
                week_number=1,
                plan_id=plan_record.id,
                days=[1, 2, 3],
                user_level=journey_request.user_level
            )
            
            # Build modules list for UI
            modules = self._build_week_modules(week_structure)
            
            return {
                "success": True,
                "week_number": 1,
                "plan_id": plan_record.id,
                "plan": week_structure,
                "modules": modules,
                "status": "generating",
                "days_ready": [],
                "message": "Week 1 structure created, content generating in background"
            }
            
        except Exception as e:
            logger.error(f"Error creating initial week plan: {e}")
            return {"success": False, "error": str(e)}

    async def get_weekly_plan(
        self,
        db: AsyncSession,
        user_id: int,
        week_number: int
    ) -> Dict[str, Any]:
        """
        Get a weekly plan from database.
        Returns immediately from cache/DB - no AI generation wait.
        """
        try:
            plan = await weekly_learning_plan_crud.get_by_user_and_week(
                db, user_id=user_id, week_number=week_number
            )
            
            if not plan:
                return {
                    "success": False,
                    "error": f"Week {week_number} plan not found",
                    "status": "not_found"
                }
            
            modules = self._build_week_modules(plan.plan_data) if plan.plan_data else []
            
            return {
                "success": True,
                "week_number": week_number,
                "plan_id": plan.id,
                "plan": plan.plan_data,
                "modules": modules,
                "status": plan.status,
                "days_ready": list(plan.days_content_ready or []),
                "current_day": plan.current_day,
                "days_completed": plan.days_completed
            }
            
        except Exception as e:
            logger.error(f"Error getting weekly plan: {e}")
            return {"success": False, "error": str(e)}

    async def get_day_content(
        self,
        db: AsyncSession,
        user: User,
        week_number: int,
        day_number: int
    ) -> Dict[str, Any]:
        """
        Get content for a specific day.
        Returns from cache if ready, or generates on-demand if needed.
        """
        try:
            # Get the weekly plan
            plan = await weekly_learning_plan_crud.get_by_user_and_week(
                db, user_id=user.id, week_number=week_number
            )
            
            if not plan:
                return {"success": False, "error": f"Week {week_number} not found"}
            
            # Check if day content is ready
            days_ready = list(plan.days_content_ready or [])
            
            if day_number not in days_ready:
                # Content not ready - generate on-demand (fallback)
                logger.info(f"Day {day_number} content not ready, generating on-demand")
                
                day_plan = self._get_day_from_plan(plan.plan_data, day_number)
                steps = []
                
                for content_type in day_plan.get("content_types", ["vocabulary", "reading"]):
                    result = await self._generate_single_content_piece(
                        db=db,
                        user=user,
                        content_type=content_type,
                        topic=day_plan.get("topic", "daily life"),
                        duration_minutes=day_plan.get("duration_per_type", 10),
                        user_context={"day_number": day_number, "week_number": week_number}
                    )
                    
                    if result.get("success"):
                        steps.append({
                            "type": content_type,
                            "title": f"{content_type.title()} Practice",
                            "content": result.get("content"),
                            "estimated_minutes": day_plan.get("duration_per_type", 10)
                        })
                
                return {
                    "success": True,
                    "week_number": week_number,
                    "day_number": day_number,
                    "day_plan": day_plan,
                    "steps": steps,
                    "from_cache": False
                }
            
            # Day is ready - fetch from cache
            day_plan = self._get_day_from_plan(plan.plan_data, day_number)
            steps = []
            
            for content_type in day_plan.get("content_types", ["vocabulary", "reading"]):
                cache_key = build_cache_key(
                    user_id=user.id,
                    content_type=content_type,
                    topic=day_plan.get("topic", "daily life"),
                    level=user.current_level.value,
                    day_number=day_number
                )
                
                cached = await generated_content_cache_crud.get_by_key(db, cache_key=cache_key)
                
                if cached and cached.content:
                    steps.append({
                        "type": content_type,
                        "title": f"{content_type.title()} Practice",
                        "content": cached.content,
                        "estimated_minutes": day_plan.get("duration_per_type", 10)
                    })
            
            return {
                "success": True,
                "week_number": week_number,
                "day_number": day_number,
                "day_plan": day_plan,
                "steps": steps,
                "from_cache": True
            }
            
        except Exception as e:
            logger.error(f"Error getting day content: {e}")
            return {"success": False, "error": str(e)}

    async def complete_day(
        self,
        db: AsyncSession,
        user_id: int,
        week_number: int,
        day_number: int,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Record day completion and trigger next week generation if day >= 5.
        """
        try:
            # Record completion
            record = await day_completion_record_crud.upsert(
                db,
                user_id=user_id,
                week_number=week_number,
                day_number=day_number,
                exercises_completed=results.get("exercises_completed", 0),
                correct_answers=results.get("correct_answers", 0),
                total_questions=results.get("total_questions", 0),
                time_spent_minutes=results.get("time_spent_minutes", 0),
                skill_results=results.get("skill_results", {}),
                content_types_completed=results.get("content_types_completed", [])
            )
            
            # Update weekly plan progress
            plan = await weekly_learning_plan_crud.get_by_user_and_week(
                db, user_id=user_id, week_number=week_number
            )
            if plan:
                await weekly_learning_plan_crud.update_day_progress(
                    db,
                    plan_id=plan.id,
                    current_day=day_number + 1 if day_number < 7 else 7,
                    days_completed=day_number
                )
            
            # Update user weekly progress
            await user_weekly_progress_crud.update_day_completed(
                db, user_id=user_id, day_in_week=day_number
            )
            
            # Analyze and update skill scores
            await self._update_skill_analysis(db, user_id, week_number)
            
            # Trigger next week generation if day >= 5
            next_week_triggered = False
            if day_number >= 5:
                from app.tasks.weekly_plan_tasks import check_and_trigger_next_week
                check_and_trigger_next_week.delay(
                    user_id=user_id,
                    current_week=week_number,
                    completed_day=day_number
                )
                next_week_triggered = True
            
            return {
                "success": True,
                "week_number": week_number,
                "day_number": day_number,
                "record_id": record.id,
                "next_week_triggered": next_week_triggered,
                "message": f"Day {day_number} completed" + (
                    f", Week {week_number + 1} generation triggered" if next_week_triggered else ""
                )
            }
            
        except Exception as e:
            logger.error(f"Error completing day: {e}")
            return {"success": False, "error": str(e)}

    async def get_weekly_plan_status(
        self,
        db: AsyncSession,
        user_id: int,
        week_number: int
    ) -> Dict[str, Any]:
        """
        Get generation status for a weekly plan.
        Used by frontend to check if content is ready.
        """
        try:
            plan = await weekly_learning_plan_crud.get_by_user_and_week(
                db, user_id=user_id, week_number=week_number
            )
            
            if not plan:
                return {
                    "exists": False,
                    "status": "not_found",
                    "week_number": week_number
                }
            
            return {
                "exists": True,
                "status": plan.status,
                "week_number": week_number,
                "days_ready": list(plan.days_content_ready or []),
                "generation_attempts": plan.generation_attempts,
                "last_error": plan.last_error if plan.status == "failed" else None
            }
            
        except Exception as e:
            logger.error(f"Error getting plan status: {e}")
            return {"exists": False, "status": "error", "error": str(e)}

    # Helper methods for weekly system

    def _create_week_structure(
        self,
        week_number: int,
        user_level: str,
        preferred_categories: List[str],
        daily_study_minutes: int,
        assessment_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a 7-day week structure quickly without AI"""
        
        topics = self._get_topics_for_categories(preferred_categories)
        skill_rotations = [
            ["vocabulary", "reading", "listening"],
            ["grammar", "vocabulary", "speaking"],
            ["reading", "listening", "writing"],
            ["vocabulary", "grammar", "listening"],
            ["speaking", "reading", "vocabulary"],
            ["listening", "writing", "grammar"],
            ["vocabulary", "reading", "speaking"]
        ]
        
        # Adjust based on assessment weak areas
        weak_areas = []
        if assessment_results:
            skill_scores = assessment_results.get("skill_scores", {})
            weak_areas = [skill for skill, score in skill_scores.items() if score < 0.6]
        
        days = []
        for day in range(1, 8):
            day_topic = topics[(day - 1 + (week_number - 1) * 7) % len(topics)]
            day_skills = list(skill_rotations[(day - 1) % len(skill_rotations)])
            
            # Prioritize weak areas
            if weak_areas and day % 2 == 0:
                for weak in weak_areas[:1]:
                    if weak not in day_skills:
                        day_skills[0] = weak
            
            duration_per_type = max(5, daily_study_minutes // len(day_skills))
            
            days.append({
                "day": day,
                "title": f"Day {day}: {day_topic.title()}",
                "topic": day_topic,
                "content_types": day_skills,
                "skills_focus": day_skills[:2],
                "estimated_minutes": daily_study_minutes,
                "duration_per_type": duration_per_type,
                "learning_objectives": [
                    f"Practice {day_skills[0]} related to {day_topic}",
                    f"Improve {day_skills[1]} skills"
                ]
            })
        
        return {
            "week_number": week_number,
            "theme": f"Week {week_number}: Building Your English Skills",
            "level": user_level,
            "categories": preferred_categories,
            "daily_study_minutes": daily_study_minutes,
            "days": days
        }

    def _get_topics_for_categories(self, categories: List[str]) -> List[str]:
        """Get topics based on user's preferred categories"""
        category_topics = {
            "general_english": ["daily routines", "family life", "hobbies", "food", "shopping"],
            "business_english": ["workplace", "meetings", "emails", "presentations", "networking"],
            "travel_english": ["airports", "hotels", "directions", "restaurants", "sightseeing"],
            "academic_english": ["study skills", "research", "presentations", "writing", "discussions"],
            "conversation_practice": ["small talk", "opinions", "storytelling", "debates", "social events"],
            "vocabulary_building": ["word families", "expressions", "idioms", "collocations", "synonyms"],
        }
        
        topics = []
        for cat in categories:
            topics.extend(category_topics.get(cat, ["general topics"]))
        
        if not topics:
            topics = ["daily life", "work", "travel", "hobbies", "food", "culture", "health"]
        
        return topics

    def _build_week_modules(self, plan_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build modules list for UI from plan data"""
        if not plan_data:
            return []
        
        modules = []
        for day in plan_data.get("days", []):
            modules.append({
                "id": f"day_{day.get('day', len(modules) + 1)}",
                "day_number": day.get("day"),
                "title": day.get("title", f"Day {day.get('day')}"),
                "topic": day.get("topic"),
                "skills": day.get("content_types", []),
                "estimated_minutes": day.get("estimated_minutes", 30),
                "is_unlocked": day.get("day", 1) == 1,
                "learning_objectives": day.get("learning_objectives", [])
            })
        
        return modules

    def _get_day_from_plan(
        self,
        plan_data: Optional[Dict[str, Any]],
        day_number: int
    ) -> Dict[str, Any]:
        """Get specific day's plan from week plan data"""
        if not plan_data:
            return {
                "day": day_number,
                "topic": "daily life",
                "content_types": ["vocabulary", "reading", "listening"],
                "duration_per_type": 10
            }
        
        for day in plan_data.get("days", []):
            if day.get("day") == day_number:
                return day
        
        return {
            "day": day_number,
            "topic": "general topics",
            "content_types": ["vocabulary", "reading", "listening"],
            "duration_per_type": 10
        }

    async def _update_skill_analysis(
        self,
        db: AsyncSession,
        user_id: int,
        week_number: int
    ) -> None:
        """Update skill scores based on recent completion records"""
        try:
            records = await day_completion_record_crud.get_week_records(
                db, user_id=user_id, week_number=week_number
            )
            
            if not records:
                return
            
            # Aggregate skill results
            skill_totals = {}
            for record in records:
                for skill, results in (record.skill_results or {}).items():
                    if skill not in skill_totals:
                        skill_totals[skill] = {"correct": 0, "total": 0}
                    skill_totals[skill]["correct"] += results.get("correct", 0)
                    skill_totals[skill]["total"] += results.get("total", 0)
            
            # Calculate scores
            skill_scores = {}
            weak_areas = []
            strong_areas = []
            
            for skill, totals in skill_totals.items():
                if totals["total"] > 0:
                    score = totals["correct"] / totals["total"]
                    skill_scores[skill] = round(score, 2)
                    
                    if score < 0.6:
                        weak_areas.append(skill)
                    elif score >= 0.8:
                        strong_areas.append(skill)
            
            # Update user progress
            await user_weekly_progress_crud.update_skill_scores(
                db,
                user_id=user_id,
                skill_scores=skill_scores,
                weak_areas=weak_areas,
                strong_areas=strong_areas
            )
            
        except Exception as e:
            logger.error(f"Error updating skill analysis: {e}")


# Global instance
content_workflow_service = ContentGenerationWorkflow()
