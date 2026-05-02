from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.lessons import crud_ai_lesson, crud_lesson_progress
from app.schemas.lessons import LessonType, AILessonCreate
from app.services.ai_service import ai_service
from app.services.adaptive_difficulty_service import adaptive_difficulty_service
from app.core.logging import debug_log
from app.models.personalization import (
    UserOnboarding,
    UserLearningProfile,
    UserCategoryPreference,
)
from app.models.progress import UserWeeklyProgress, UserProgress

class LessonCacheService:
    """Service for intelligent lesson caching and generation"""

    def __init__(self):
        self.cache_ttl_days = 30  # Default cache TTL

    async def get_cached_lesson(
        self,
        db: Session,
        user_id: int,
        lesson_type: str,
        difficulty_level: str,
        topic: Optional[str] = None
    ) -> Optional[Any]:
        """Get cached lesson if available and not expired, with smart cache update"""
        lesson = crud_ai_lesson.get_cached_lesson(
            db,
            user_id=user_id,
            lesson_type=lesson_type,
            difficulty_level=difficulty_level,
            topic=topic
        )

        # Update access time if lesson found
        if lesson:
            crud_ai_lesson.update_access_time(db, lesson_id=lesson.id)

        return lesson

    async def get_or_generate_lesson(
        self,
        db: Session,
        user_id: int,
        lesson_type: str,
        difficulty_level: str,
        topic: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Smart caching: get from cache or generate new with progress consideration"""

        # Try to get cached lesson first
        cached_lesson = await self.get_cached_lesson(
            db, user_id, lesson_type, difficulty_level, topic
        )

        if cached_lesson:
            return {
                "lesson": cached_lesson,
                "from_cache": True,
                "cache_age_hours": (datetime.utcnow() - cached_lesson.created_at).total_seconds() / 3600
            }

        # No cached lesson, generate new one based on user progress
        progress_data = await self._analyze_user_progress(db, user_id, lesson_type, difficulty_level)

        # Adjust generation parameters based on progress
        adjusted_preferences = await self._adjust_generation_params(
            user_preferences or {}, progress_data, lesson_type, difficulty_level
        )

        # Generate new lesson content
        lesson_content = await self.generate_lesson_content(
            user_id=user_id,
            lesson_type=lesson_type,
            difficulty_level=difficulty_level,
            topic=topic,
            user_preferences=adjusted_preferences,
            db=db,
        )

        return {
            "lesson_content": lesson_content,
            "from_cache": False,
            "progress_based": True,
            "adjustments": adjusted_preferences
        }

    async def _analyze_user_progress(
        self,
        db: Session,
        user_id: int,
        lesson_type: str,
        difficulty_level: str
    ) -> Dict[str, Any]:
        """Analyze user's progress in this lesson type and difficulty"""
        # Get user's recent lessons of this type
        recent_lessons = crud_ai_lesson.get_user_cached_lessons(
            db, user_id=user_id, lesson_type=lesson_type, limit=10
        )

        # Get progress data
        progress_stats = crud_lesson_progress.get_user_completion_stats(db, user_id)

        # Analyze performance patterns
        type_performance = {
            "recent_completion_rate": 0.0,
            "average_accuracy": 0.0,
            "common_mistakes": [],
            "preferred_topics": [],
            "time_spent_average": 0
        }

        if recent_lessons:
            completed_lessons = [l for l in recent_lessons if l.total_completions > 0]
            type_performance["recent_completion_rate"] = len(completed_lessons) / len(recent_lessons)

        return {
            "overall_stats": progress_stats,
            "type_performance": type_performance,
            "lesson_count": len(recent_lessons),
            "has_prior_experience": len(recent_lessons) > 0
        }

    async def _adjust_generation_params(
        self,
        base_preferences: Dict[str, Any],
        progress_data: Dict[str, Any],
        lesson_type: str,
        difficulty_level: str
    ) -> Dict[str, Any]:
        """Adjust lesson generation parameters based on user progress"""

        adjustments = base_preferences.copy()

        # Adjust difficulty based on performance
        overall_stats = progress_data["overall_stats"]
        type_performance = progress_data["type_performance"]

        # If user is struggling, make content more supportive
        if overall_stats["avg_accuracy"] < 0.6:
            adjustments["difficulty_modifier"] = "supportive"
            adjustments["include_hints"] = True
            adjustments["extra_examples"] = True

        # If user is excelling, add challenges
        elif overall_stats["avg_accuracy"] > 0.85:
            adjustments["difficulty_modifier"] = "challenging"
            adjustments["include_advanced_concepts"] = True

        # Adjust content based on completion patterns
        if type_performance["recent_completion_rate"] < 0.5:
            adjustments["shorter_segments"] = True
            adjustments["more_frequent_breaks"] = True

        # Add progress-based personalization
        if progress_data["has_prior_experience"]:
            adjustments["build_on_previous"] = True
            adjustments["avoid_repetition"] = True

        return adjustments

    async def generate_progress_based_sequence(
        self,
        db: Session,
        user_id: int,
        base_lesson_type: str,
        current_difficulty: str,
        target_difficulty: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate a sequence of lessons based on user progress to bridge skill gaps"""

        # Analyze user's current performance
        progress_analysis = await self._analyze_user_progress(
            db, user_id, base_lesson_type, current_difficulty
        )

        # Determine skill gaps and needed interventions
        skill_gaps = await self._identify_skill_gaps(progress_analysis, base_lesson_type)

        # Create learning sequence
        sequence = []
        current_level = current_difficulty

        for gap in skill_gaps:
            # Generate bridging lesson for this gap
            lesson_content = await self._generate_bridging_lesson(
                user_id, base_lesson_type, current_level, gap
            )

            sequence.append({
                "lesson_content": lesson_content,
                "gap_addressed": gap,
                "estimated_difficulty": current_level,
                "sequence_position": len(sequence) + 1
            })

            # Gradually increase difficulty if target is higher
            if target_difficulty and current_level != target_difficulty:
                current_level = await self._increment_difficulty_level(current_level, target_difficulty)

        return sequence

    async def _identify_skill_gaps(
        self,
        progress_analysis: Dict[str, Any],
        lesson_type: str
    ) -> List[str]:
        """Identify specific skill gaps based on progress analysis"""

        gaps = []
        overall_stats = progress_analysis["overall_stats"]
        type_performance = progress_analysis["type_performance"]

        # Accuracy-based gaps
        if overall_stats["avg_accuracy"] < 0.6:
            if lesson_type == "vocabulary":
                gaps.extend(["word_recognition", "spelling_accuracy", "context_usage"])
            elif lesson_type == "grammar":
                gaps.extend(["tense_usage", "sentence_structure", "agreement_rules"])
            elif lesson_type == "conversation":
                gaps.extend(["fluency", "vocabulary_retrieval", "pronunciation"])

        # Completion-based gaps
        if type_performance["recent_completion_rate"] < 0.5:
            gaps.append("persistence")
            gaps.append("time_management")

        # Add gaps based on weak areas from progress data
        weak_areas = overall_stats.get("weak_areas", [])
        gaps.extend(weak_areas)

        # Ensure some gaps are identified even if analysis is limited
        if not gaps:
            gaps = await self._get_default_gaps_for_type(lesson_type)

        return list(set(gaps))  # Remove duplicates

    async def _get_default_gaps_for_type(self, lesson_type: str) -> List[str]:
        """Get default skill gaps for a lesson type"""
        gap_mapping = {
            "vocabulary": ["word_meanings", "usage_context", "pronunciation"],
            "grammar": ["sentence_structure", "verb_forms", "word_order"],
            "conversation": ["opening_conversations", "asking_questions", "responding_appropriately"],
            "writing": ["organization", "vocabulary_choice", "grammar_accuracy"],
            "pronunciation": ["individual_sounds", "word_stress", "sentence_intonation"],
            "comprehension": ["main_ideas", "details", "inferences"]
        }
        return gap_mapping.get(lesson_type, ["general_practice"])

    async def _generate_bridging_lesson(
        self,
        user_id: int,
        lesson_type: str,
        difficulty_level: str,
        skill_gap: str
    ) -> Dict[str, Any]:
        """Generate a focused lesson to address a specific skill gap"""

        prompt = f"""
        Create a targeted lesson to address the skill gap: "{skill_gap}"
        Lesson type: {lesson_type}
        Difficulty level: {difficulty_level}
        User ID: {user_id}

        This lesson should specifically focus on improving the identified skill gap.
        Make it engaging, practical, and directly address the weakness.

        Generate a lesson with:
        1. Clear objective addressing the skill gap
        2. Focused practice activities
        3. Immediate feedback mechanisms
        4. Progress tracking elements
        5. Encouragement and motivation

        Format as structured JSON with targeted content.
        """

        try:
            result = await ai_service.generate_structured_content(
                prompt=prompt,
                content_type="bridging_lesson"
            )

            if result.get("success"):
                content = result["content"]
                content["skill_gap_targeted"] = skill_gap
                content["bridging_lesson"] = True
                return content
            else:
                return await self._get_fallback_bridging_lesson(lesson_type, difficulty_level, skill_gap)

        except Exception as e:
            debug_log(f"AI generation failed for bridging lesson: {e}")
            return await self._get_fallback_bridging_lesson(lesson_type, difficulty_level, skill_gap)

    async def _get_fallback_bridging_lesson(
        self,
        lesson_type: str,
        difficulty_level: str,
        skill_gap: str
    ) -> Dict[str, Any]:
        """Provide fallback bridging lesson content"""
        return {
            "title": f"Improving {skill_gap.replace('_', ' ').title()}",
            "description": f"Focused practice to improve {skill_gap} skills",
            "objective": f"Develop better {skill_gap} through targeted practice",
            "skill_gap_targeted": skill_gap,
            "bridging_lesson": True,
            "activities": [
                f"Practice exercise for {skill_gap}",
                "Immediate feedback practice",
                "Reflection and improvement"
            ],
            "tips": [f"Focus on {skill_gap} in your daily practice"]
        }

    async def _increment_difficulty_level(self, current: str, target: str) -> str:
        """Increment difficulty level towards target"""
        levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        try:
            current_idx = levels.index(current.upper())
            target_idx = levels.index(target.upper())

            if current_idx < target_idx:
                return levels[current_idx + 1]
            else:
                return current
        except ValueError:
            return current

    async def save_lesson_sequence(
        self,
        db: Session,
        user_id: int,
        sequence: List[Dict[str, Any]],
        base_lesson_type: str
    ):
        """Save a generated lesson sequence to database"""
        try:
            for lesson_data in sequence:
                content = lesson_data["lesson_content"]

                # Create lesson in database using sync helper
                lesson_in = AILessonCreate(
                    user_id=user_id,
                    lesson_type=base_lesson_type,
                    difficulty_level=lesson_data["estimated_difficulty"],
                    topic=content.get("skill_gap_targeted", base_lesson_type),
                    title=content.get("title", f"Sequence Lesson {lesson_data['sequence_position']}"),
                    description=content.get("description", "Progress-based lesson"),
                    content=content,
                    expires_at=None
                )

                crud_ai_lesson.create_sync(db, obj_in=lesson_in)

            debug_log(f"Saved {len(sequence)} lessons in sequence for user {user_id}")

        except Exception as e:
            debug_log(f"Failed to save lesson sequence: {e}")

    async def generate_lesson_content(
        self,
        user_id: int,
        lesson_type: str,
        difficulty_level: str,
        topic: Optional[str] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Generate new lesson content based on user profile and progress"""

        # Get user profile for personalization (uses real DB data when db is provided)
        user_profile = await self._get_user_context(user_id, difficulty_level, db=db)

        # Generate lesson content based on type
        if lesson_type == LessonType.CONVERSATION.value:
            content = await self._generate_conversation_lesson(
                difficulty_level, topic, user_profile, user_preferences
            )
        elif lesson_type == LessonType.WRITING.value:
            content = await self._generate_writing_lesson(
                difficulty_level, topic, user_profile, user_preferences
            )
        elif lesson_type == LessonType.GRAMMAR.value:
            content = await self._generate_grammar_lesson(
                difficulty_level, topic, user_profile, user_preferences
            )
        elif lesson_type == LessonType.VOCABULARY.value:
            content = await self._generate_vocabulary_lesson(
                difficulty_level, topic, user_profile, user_preferences
            )
        else:
            content = await self._generate_general_lesson(
                lesson_type, difficulty_level, topic, user_profile, user_preferences
            )

        return content

    async def _get_user_context(
        self,
        user_id: int,
        difficulty_level: str,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Get user context for personalization from real DB data.

        When *db* is a sync ``Session`` (the common case in this service) we use
        synchronous ORM queries.  The method also gracefully falls back to
        sensible defaults if no data exists yet for the user.
        """
        context: Dict[str, Any] = {
            "current_level": difficulty_level,
            "learning_goals": [],
            "preferred_topics": [],
            "weaknesses": [],
            "strengths": [],
            "preferred_content_types": [],
            "challenge_preference": 0.5,
            "learning_style": "mixed",
        }

        if db is None:
            return context

        try:
            # ── UserOnboarding ────────────────────────────────────
            onboarding = (
                db.query(UserOnboarding)
                .filter(UserOnboarding.user_id == user_id)
                .first()
            )
            if onboarding:
                context["preferred_topics"] = onboarding.selected_categories or []
                if onboarding.primary_category:
                    primary = (
                        onboarding.primary_category.value
                        if hasattr(onboarding.primary_category, "value")
                        else str(onboarding.primary_category)
                    )
                    if primary not in context["preferred_topics"]:
                        context["preferred_topics"].insert(0, primary)
                context["learning_goals"] = onboarding.learning_goals or []
                context["preferred_content_types"] = onboarding.preferred_content_types or []
                if onboarding.assessed_level:
                    context["current_level"] = onboarding.assessed_level
                if onboarding.preferred_learning_style:
                    context["learning_style"] = (
                        onboarding.preferred_learning_style.value
                        if hasattr(onboarding.preferred_learning_style, "value")
                        else str(onboarding.preferred_learning_style)
                    )

            # ── UserLearningProfile ───────────────────────────────
            profile = (
                db.query(UserLearningProfile)
                .filter(UserLearningProfile.user_id == user_id)
                .first()
            )
            if profile:
                context["challenge_preference"] = float(
                    profile.challenge_preference or 0.5
                )
                context["learning_rate"] = float(profile.learning_rate or 1.0)
                context["retention_rate"] = float(profile.retention_rate or 0.8)
                if profile.primary_goal:
                    goal_val = (
                        profile.primary_goal.value
                        if hasattr(profile.primary_goal, "value")
                        else str(profile.primary_goal)
                    )
                    if goal_val not in context["learning_goals"]:
                        context["learning_goals"].insert(0, goal_val)
                if profile.secondary_goals:
                    for g in profile.secondary_goals:
                        if g not in context["learning_goals"]:
                            context["learning_goals"].append(g)

            # ── UserCategoryPreference ────────────────────────────
            cat_prefs = (
                db.query(UserCategoryPreference)
                .filter(
                    UserCategoryPreference.user_id == user_id,
                    UserCategoryPreference.is_active == True,
                )
                .order_by(UserCategoryPreference.priority_level.asc())
                .limit(5)
                .all()
            )
            if cat_prefs:
                for cp in cat_prefs:
                    cat_val = (
                        cp.category.value
                        if hasattr(cp.category, "value")
                        else str(cp.category)
                    )
                    if cat_val not in context["preferred_topics"]:
                        context["preferred_topics"].append(cat_val)

            # ── UserWeeklyProgress (weak / strong areas) ──────────
            weekly = (
                db.query(UserWeeklyProgress)
                .filter(UserWeeklyProgress.user_id == user_id)
                .first()
            )
            if weekly:
                context["weaknesses"] = weekly.weak_areas or []
                context["strengths"] = weekly.strong_areas or []
                context["skill_scores"] = weekly.skill_scores or {}

            # ── UserProgress (overall stats) ──────────────────────
            progress = (
                db.query(UserProgress)
                .filter(UserProgress.user_id == user_id)
                .first()
            )
            if progress:
                if progress.current_level:
                    level_val = (
                        progress.current_level.value
                        if hasattr(progress.current_level, "value")
                        else str(progress.current_level)
                    )
                    context["current_level"] = level_val
                context["average_accuracy"] = float(
                    progress.average_accuracy or 0.0
                )

        except Exception as e:
            debug_log(f"Error fetching user context for user {user_id}: {e}")

        # Ensure we always have some defaults
        if not context["preferred_topics"]:
            context["preferred_topics"] = ["general_english"]
        if not context["learning_goals"]:
            context["learning_goals"] = ["improve_conversation", "build_vocabulary"]
        if not context["weaknesses"]:
            context["weaknesses"] = ["grammar"]
        if not context["strengths"]:
            context["strengths"] = ["vocabulary"]

        return context

    async def _generate_conversation_lesson(
        self,
        difficulty_level: str,
        topic: Optional[str],
        user_profile: Dict[str, Any],
        preferences: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate conversation-focused lesson"""

        prompt = f"""
        Create a conversation lesson for {difficulty_level} level English learners.
        Topic: {topic or 'General conversation'}
        User profile: {user_profile}

        Generate a lesson with:
        1. Conversation scenario and dialogue
        2. Key vocabulary (10-15 words)
        3. Grammar focus points
        4. Pronunciation practice
        5. Comprehension questions
        6. Role-play activities

        Format as structured JSON with all lesson components.
        """

        try:
            result = await ai_service.generate_structured_content(
                prompt=prompt,
                content_type="conversation_lesson"
            )

            if result.get("success"):
                return result["content"]
            else:
                return self._get_fallback_conversation_lesson(difficulty_level, topic)

        except Exception as e:
            debug_log(f"AI generation failed: {e}")
            return self._get_fallback_conversation_lesson(difficulty_level, topic)

    async def _generate_writing_lesson(
        self,
        difficulty_level: str,
        topic: Optional[str],
        user_profile: Dict[str, Any],
        preferences: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate writing-focused lesson"""

        prompt = f"""
        Create a writing lesson for {difficulty_level} level English learners.
        Topic: {topic or 'General writing'}
        User profile: {user_profile}

        Generate a lesson with:
        1. Writing task/prompt
        2. Model text/example
        3. Key vocabulary and phrases
        4. Grammar structures to practice
        5. Writing tips and guidelines
        6. Peer review checklist

        Format as structured JSON with all lesson components.
        """

        try:
            result = await ai_service.generate_structured_content(
                prompt=prompt,
                content_type="writing_lesson"
            )

            if result.get("success"):
                return result["content"]
            else:
                return self._get_fallback_writing_lesson(difficulty_level, topic)

        except Exception as e:
            debug_log(f"AI generation failed: {e}")
            return self._get_fallback_writing_lesson(difficulty_level, topic)

    async def _generate_grammar_lesson(
        self,
        difficulty_level: str,
        topic: Optional[str],
        user_profile: Dict[str, Any],
        preferences: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate grammar-focused lesson"""

        prompt = f"""
        Create a grammar lesson for {difficulty_level} level English learners.
        Topic: {topic or 'General grammar'}
        User profile: {user_profile}

        Generate a lesson with:
        1. Grammar rule explanation
        2. Example sentences
        3. Practice exercises
        4. Common mistakes to avoid
        5. Application activities
        6. Progress check

        Format as structured JSON with all lesson components.
        """

        try:
            result = await ai_service.generate_structured_content(
                prompt=prompt,
                content_type="grammar_lesson"
            )

            if result.get("success"):
                return result["content"]
            else:
                return self._get_fallback_grammar_lesson(difficulty_level, topic)

        except Exception as e:
            debug_log(f"AI generation failed: {e}")
            return self._get_fallback_grammar_lesson(difficulty_level, topic)

    async def _generate_vocabulary_lesson(
        self,
        difficulty_level: str,
        topic: Optional[str],
        user_profile: Dict[str, Any],
        preferences: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate vocabulary-focused lesson"""

        prompt = f"""
        Create a vocabulary lesson for {difficulty_level} level English learners.
        Topic: {topic or 'General vocabulary'}
        User profile: {user_profile}

        Generate a lesson with:
        1. Target vocabulary words (15-20 words)
        2. Definitions and example sentences
        3. Word families and collocations
        4. Practice activities (matching, fill-in-blank)
        5. Memory techniques
        6. Review games

        Format as structured JSON with all lesson components.
        """

        try:
            result = await ai_service.generate_structured_content(
                prompt=prompt,
                content_type="vocabulary_lesson"
            )

            if result.get("success"):
                return result["content"]
            else:
                return self._get_fallback_vocabulary_lesson(difficulty_level, topic)

        except Exception as e:
            debug_log(f"AI generation failed: {e}")
            return self._get_fallback_vocabulary_lesson(difficulty_level, topic)

    async def _generate_general_lesson(
        self,
        lesson_type: str,
        difficulty_level: str,
        topic: Optional[str],
        user_profile: Dict[str, Any],
        preferences: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate general lesson for other types"""

        prompt = f"""
        Create a {lesson_type} lesson for {difficulty_level} level English learners.
        Topic: {topic or 'General practice'}
        User profile: {user_profile}

        Generate a comprehensive lesson with appropriate activities and content.
        Format as structured JSON with all lesson components.
        """

        try:
            result = await ai_service.generate_structured_content(
                prompt=prompt,
                content_type=f"{lesson_type}_lesson"
            )

            if result.get("success"):
                return result["content"]
            else:
                return self._get_fallback_general_lesson(lesson_type, difficulty_level, topic)

        except Exception as e:
            debug_log(f"AI generation failed: {e}")
            return self._get_fallback_general_lesson(lesson_type, difficulty_level, topic)

    # Fallback methods for when AI generation fails
    def _get_fallback_conversation_lesson(self, difficulty_level: str, topic: Optional[str]) -> Dict[str, Any]:
        return {
            "title": f"Conversation: {topic or 'Daily Life'}",
            "description": f"Practice everyday conversations in {difficulty_level} English",
            "scenario": f"A conversation about {topic or 'daily life'}",
            "dialogue": [
                {"speaker": "A", "text": "Hello! How are you today?"},
                {"speaker": "B", "text": "I'm fine, thank you. And you?"}
            ],
            "vocabulary": ["hello", "thank you", "fine", "today"],
            "exercises": ["Repeat the dialogue", "Create your own conversation"]
        }

    def _get_fallback_writing_lesson(self, difficulty_level: str, topic: Optional[str]) -> Dict[str, Any]:
        return {
            "title": f"Writing: {topic or 'Personal Message'}",
            "description": f"Learn to write {topic or 'personal messages'} in {difficulty_level} English",
            "task": f"Write a short message about {topic or 'your day'}",
            "example": "Dear friend, I hope you are well. Today I...",
            "vocabulary": ["hope", "well", "today", "friend"],
            "tips": ["Start with a greeting", "Use simple sentences", "End with a closing"]
        }

    def _get_fallback_grammar_lesson(self, difficulty_level: str, topic: Optional[str]) -> Dict[str, Any]:
        return {
            "title": f"Grammar: {topic or 'Basic Structures'}",
            "description": f"Practice {topic or 'basic grammar'} in {difficulty_level} English",
            "rule": f"Basic {topic or 'sentence'} structure",
            "examples": ["I eat breakfast.", "She reads books.", "They play soccer."],
            "exercises": ["Complete the sentences", "Make your own examples"],
            "common_mistakes": ["Word order", "Verb forms", "Articles"]
        }

    def _get_fallback_vocabulary_lesson(self, difficulty_level: str, topic: Optional[str]) -> Dict[str, Any]:
        return {
            "title": f"Vocabulary: {topic or 'Common Words'}",
            "description": f"Learn {topic or 'common'} vocabulary in {difficulty_level} English",
            "words": [
                {"word": "hello", "definition": "a greeting", "example": "Hello, nice to meet you."},
                {"word": "thank", "definition": "express gratitude", "example": "Thank you for your help."}
            ],
            "activities": ["Match words to definitions", "Use words in sentences"],
            "memory_tips": ["Practice daily", "Use flashcards", "Connect with images"]
        }

    def _get_fallback_general_lesson(self, lesson_type: str, difficulty_level: str, topic: Optional[str]) -> Dict[str, Any]:
        return {
            "title": f"{lesson_type.title()}: {topic or 'Practice'}",
            "description": f"General {lesson_type} practice in {difficulty_level} English",
            "content": f"This is a {lesson_type} lesson about {topic or 'general topics'}",
            "activities": [f"Practice {lesson_type} skills", "Complete exercises", "Review materials"],
            "objectives": [f"Improve {lesson_type} skills", "Build confidence", "Learn new concepts"]
        }

    async def get_personalized_recommendations(
        self,
        db: Session,
        user_id: int,
        limit: int = 5
    ) -> List[Any]:
        """Get personalized lesson recommendations based on user progress"""
        # Get user progress stats
        progress_stats = crud_lesson_progress.get_user_completion_stats(db, user_id=user_id)

        # Get user's existing lessons
        completed_lessons = crud_lesson_progress.get_user_recent_progress(db, user_id=user_id, limit=20)

        # Determine what type of lessons to recommend
        recommendations = []

        # Recommend based on weak areas
        if progress_stats['avg_accuracy'] < 0.7:
            # Recommend practice lessons
            practice_lessons = crud_ai_lesson.get_user_cached_lessons(
                db, user_id=user_id, lesson_type="vocabulary", limit=2
            )
            recommendations.extend(practice_lessons)

        # Recommend based on completion patterns
        if progress_stats['completion_rate'] < 0.8:
            # Recommend shorter, easier lessons
            easy_lessons = crud_ai_lesson.get_user_cached_lessons(
                db, user_id=user_id, difficulty_level="A1", limit=2
            )
            recommendations.extend(easy_lessons)

        # If no recommendations, get recent popular lessons
        if len(recommendations) < limit:
            recent_lessons = crud_ai_lesson.get_user_cached_lessons(
                db, user_id=user_id, skip=0, limit=limit - len(recommendations)
            )
            recommendations.extend(recent_lessons)

        return recommendations[:limit]

    async def update_generation_analytics(
        self,
        db: Session,
        user_id: int,
        lesson_type: str
    ):
        """Update analytics for lesson generation"""
        # This would track generation metrics for optimization
        # For now, just log the activity
        debug_log(f"Generated {lesson_type} lesson for user {user_id}")

    async def cleanup_expired_lessons(self, db: Session, user_id: Optional[int] = None):
        """Clean up expired cached lessons"""
        expired_count = crud_ai_lesson.cleanup_expired_lessons(db, user_id=user_id)
        debug_log(f"Cleaned up {expired_count} expired lessons")

# Global instance
lesson_cache_service = LessonCacheService()
