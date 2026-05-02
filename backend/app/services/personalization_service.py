from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import json
import random
from enum import Enum

from app.crud.personalization import (
    learning_profile, learning_path, learning_milestone,
    content_recommendation, trainer_interaction, learning_analytics, 
    user_onboarding, user_category_preference
)
from app.crud.speaking import speaking_prompt
from app.crud.reading import reading_text
from app.crud.listening import crud_audio_content
from app.crud.writing import writing_prompt
from app.schemas.personalization import (
    UserLearningProfileCreate, PersonalizedLearningPathCreate,
    LearningPathMilestoneCreate, ContentRecommendationCreate,
    PersonalTrainerInteractionCreate, PersonalTrainerResponse,
    LearningInsights, PersonalizationDashboard, ChatWithTrainerResponse
)
from app.models.personalization import (
    LearningGoalType, TrainerInteractionType, RecommendationType,
    OnboardingStep, LearningCategory
)
from app.services.ai_service import AIService

class PersonalizationService:
    def __init__(self):
        self.ai_service = AIService()
    
    # Learning Profile Management
    async def create_user_profile(self, db: AsyncSession, user_id: int, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a comprehensive learning profile for a user"""
        # Validate skill weights sum to 1.0
        weights = [
            profile_data.get('listening_weight', 0.25),
            profile_data.get('speaking_weight', 0.25),
            profile_data.get('reading_weight', 0.25),
            profile_data.get('writing_weight', 0.25)
        ]
        if abs(sum(weights) - 1.0) > 0.01:
            # Normalize weights
            total = sum(weights)
            profile_data['listening_weight'] = weights[0] / total
            profile_data['speaking_weight'] = weights[1] / total
            profile_data['reading_weight'] = weights[2] / total
            profile_data['writing_weight'] = weights[3] / total
        
        profile_create = UserLearningProfileCreate(
            user_id=user_id,
            **profile_data
        )
        
        profile = await learning_profile.create_or_update_profile(
            db, user_id=user_id, profile_data=profile_create
        )
        
        # Generate initial learning path
        initial_path = await self.generate_learning_path(db, profile.id)
        
        # Create welcome interaction
        await self._create_welcome_interaction(db, profile.id, profile_data.get('primary_goal'))
        
        return {
            "profile": profile,
            "learning_path": initial_path,
            "message": "Learning profile created successfully!"
        }

    async def bootstrap_profile_from_onboarding(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """
        Create a learning profile (and path) using existing onboarding data.
        Raises ValueError if onboarding is missing so callers can surface 404.
        """
        onboarding = await user_onboarding.get_by_user_id(db, user_id=user_id)
        if not onboarding:
            raise ValueError("Onboarding record not found for user")

        profile_data = self._create_profile_from_onboarding(onboarding)
        return await self.create_user_profile(db, user_id=user_id, profile_data=profile_data)
    
    # Learning Path Optimization
    async def generate_learning_path(
        self,
        db: AsyncSession,
        user_profile_id: int,
        path_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate an optimized learning path based on user profile"""
        profile = await learning_profile.get(db, id=user_profile_id)
        if not profile:
            raise ValueError("User profile not found")
        
        # Analyze user's current level and goals
        override_data = path_overrides or {}
        path_structure = override_data.get("path_data") or self._design_learning_path(profile)
        default_milestones = path_structure.get("milestones", [])
        
        # Create personalized learning path
        path_create = PersonalizedLearningPathCreate(
            user_profile_id=user_profile_id,
            name=override_data.get("name", f"Personalized Path to {profile.target_cefr_level}"),
            description=override_data.get("description", f"Customized learning journey for {profile.primary_goal.value}"),
            estimated_duration_weeks=override_data.get("estimated_duration_weeks", path_structure.get("duration_weeks", 12)),
            total_steps=override_data.get("total_steps", len(default_milestones)),
            path_data=path_structure
        )
        
        new_path = await learning_path.create(db, obj_in=path_create)
        
        # Create milestones
        for i, milestone_data in enumerate(default_milestones):
            milestone_create = LearningPathMilestoneCreate(
                learning_path_id=new_path.id,
                step_number=i + 1,
                **milestone_data
            )
            await learning_milestone.create(db, obj_in=milestone_create)
        
        return {
            "learning_path": new_path,
            "milestones": default_milestones,
            "estimated_completion": path_structure.get('duration_weeks', path_create.estimated_duration_weeks)
        }
    
    def _design_learning_path(self, profile) -> Dict[str, Any]:
        """Design a learning path based on user profile"""
        # Calculate duration based on goals and available time
        base_weeks = self._calculate_base_duration(profile.target_cefr_level, profile.primary_goal)
        duration_weeks = int(base_weeks * (2.0 - profile.learning_rate))
        
        # Create skill-focused milestones
        milestones = []
        skills = ['listening', 'speaking', 'reading', 'writing']
        weights = [profile.listening_weight, profile.speaking_weight, 
                  profile.reading_weight, profile.writing_weight]
        
        # Generate milestones based on skill weights
        total_milestones = max(8, duration_weeks // 2)  # At least 8 milestones
        
        for i in range(total_milestones):
            # Determine primary skill for this milestone
            skill_index = i % len(skills)
            primary_skill = skills[skill_index]
            weight = weights[skill_index]
            
            milestone = {
                "title": f"{primary_skill.title()} Mastery - Level {i + 1}",
                "description": self._generate_milestone_description(primary_skill, i + 1, profile.target_cefr_level),
                "skill_focus": primary_skill,
                "required_activities": self._generate_required_activities(primary_skill, profile.target_cefr_level),
                "mastery_threshold": 0.75 + (weight * 0.2)  # Higher threshold for preferred skills
            }
            milestones.append(milestone)
        
        return {
            "duration_weeks": duration_weeks,
            "milestones": milestones,
            "focus_distribution": dict(zip(skills, weights)),
            "difficulty_progression": profile.preferred_difficulty_progression
        }
    
    def _calculate_base_duration(self, target_level: str, goal: LearningGoalType) -> int:
        """Calculate base duration in weeks"""
        level_weeks = {
            "A1": 12, "A2": 16, "B1": 20, "B2": 24, "C1": 28, "C2": 32
        }
        
        goal_multipliers = {
            LearningGoalType.FLUENCY: 1.2,
            LearningGoalType.EXAM_PREP: 0.8,
            LearningGoalType.BUSINESS: 1.0,
            LearningGoalType.TRAVEL: 0.6,
            LearningGoalType.ACADEMIC: 1.1
        }
        
        base = level_weeks.get(target_level, 20)
        multiplier = goal_multipliers.get(goal, 1.0)
        
        return int(base * multiplier)
    
    def _generate_milestone_description(self, skill: str, level: int, target_cefr: str) -> str:
        """Generate description for milestone"""
        descriptions = {
            "listening": f"Develop {target_cefr} level listening comprehension through varied audio content",
            "speaking": f"Build {target_cefr} level speaking fluency and pronunciation accuracy",
            "reading": f"Master {target_cefr} level reading comprehension and vocabulary",
            "writing": f"Achieve {target_cefr} level writing proficiency and grammar accuracy"
        }
        return descriptions.get(skill, f"Improve {skill} skills to {target_cefr} level")
    
    def _generate_required_activities(self, skill: str, target_level: str) -> List[Dict[str, Any]]:
        """Generate required activities for a milestone"""
        activities = {
            "listening": [
                {"type": "audio_comprehension", "count": 5, "difficulty": target_level},
                {"type": "listening_exercises", "count": 10, "difficulty": target_level}
            ],
            "speaking": [
                {"type": "pronunciation_practice", "count": 8, "difficulty": target_level},
                {"type": "conversation_practice", "count": 5, "difficulty": target_level}
            ],
            "reading": [
                {"type": "text_comprehension", "count": 7, "difficulty": target_level},
                {"type": "vocabulary_exercises", "count": 15, "difficulty": target_level}
            ],
            "writing": [
                {"type": "writing_exercises", "count": 5, "difficulty": target_level},
                {"type": "grammar_practice", "count": 10, "difficulty": target_level}
            ]
        }
        return activities.get(skill, [])
    
    # Content Recommendation System
    async def generate_recommendations(self, db: AsyncSession, user_profile_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Generate personalized content recommendations"""
        profile = await learning_profile.get(db, id=user_profile_id)
        if not profile:
            return []
        
        # Get recent analytics to identify weak areas
        analytics = await learning_analytics.get_recent_analytics(db, user_profile_id=user_profile_id, days=30)
        weak_areas = self._identify_weak_areas(analytics, profile)
        
        # Generate recommendations for each skill area
        recommendations = []
        skills = ['reading', 'listening', 'speaking', 'writing']
        skill_weights = [profile.reading_weight, profile.listening_weight, 
                        profile.speaking_weight, profile.writing_weight]
        
        # Distribute limit across skills based on weights and weak areas
        for skill, weight in zip(skills, skill_weights):
            skill_limit = max(1, int(limit * weight))
            if skill in weak_areas:
                skill_limit += 2  # Boost weak areas
                
            skill_recommendations = await self._generate_skill_recommendations(
                db, profile, skill, weak_areas, skill_limit
            )
            recommendations.extend(skill_recommendations)
        
        # Sort by priority and return top recommendations
        recommendations.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        return recommendations[:limit]

    def _identify_weak_areas(self, analytics: List, profile) -> List[str]:
        """Identify areas where user is struggling"""
        weak_areas = []
        
        if not analytics:
            return weak_areas
            
        # Analyze performance across different skills
        skill_performance = {}
        for analytic in analytics:
            skill = analytic.skill_area
            performance = analytic.performance_score
            
            if skill not in skill_performance:
                skill_performance[skill] = []
            skill_performance[skill].append(performance)
        
        # Identify skills with below-average performance
        for skill, scores in skill_performance.items():
            avg_score = sum(scores) / len(scores)
            if avg_score < 0.7:  # Below 70% threshold
                weak_areas.append(skill)
        
        return weak_areas

    async def _generate_skill_recommendations(self, db: AsyncSession, profile, skill: str, weak_areas: List[str], count: int) -> List[Dict[str, Any]]:
        """Generate recommendations for a specific skill"""
        recommendations = []
        
        # Higher priority for weak areas
        priority_boost = 0.3 if skill in weak_areas else 0.0
        
        if skill == "reading":
            texts = await reading_text.get_by_level(
                db, level=profile.target_cefr_level, limit=count
            )
            for text in texts:
                recommendations.append({
                    "recommendation_type": RecommendationType.CONTENT,
                    "title": f"Reading Practice: {text.title}",
                    "description": f"Improve reading comprehension with {profile.target_cefr_level} level text",
                    "content_type": "reading",
                    "content_id": text.id,
                    "content_metadata": {"difficulty": text.difficulty_level, "word_count": text.word_count},
                    "relevance_score": 0.8 + priority_boost,
                    "confidence_score": 0.9,
                    "priority_score": 0.7 + priority_boost,
                    "reasoning": f"Matches your {profile.target_cefr_level} target level",
                    "expected_benefit": "Improve reading comprehension and vocabulary",
                    "estimated_time_minutes": max(10, text.word_count // 50)
                })
        
        elif skill == "listening":
            audio_contents = await crud_audio_content.get_by_difficulty_level(
                db, difficulty_level=profile.target_cefr_level, limit=count
            )
            for audio in audio_contents:
                recommendations.append({
                    "recommendation_type": RecommendationType.CONTENT,
                    "title": f"Listening Practice: {audio.title}",
                    "description": f"Enhance listening skills with {profile.target_cefr_level} level audio",
                    "content_type": "listening",
                    "content_id": audio.id,
                    "content_metadata": {"difficulty": audio.difficulty_level, "duration": audio.duration_seconds},
                    "relevance_score": 0.8 + priority_boost,
                    "confidence_score": 0.9,
                    "priority_score": 0.7 + priority_boost,
                    "reasoning": f"Matches your {profile.target_cefr_level} target level",
                    "expected_benefit": "Improve listening comprehension and pronunciation",
                    "estimated_time_minutes": audio.duration_seconds // 60 + 5
                })
        
        elif skill == "speaking":
            prompts = await db.run_sync(
                lambda sync_session: speaking_prompt.get_by_difficulty(
                    sync_session, difficulty=profile.target_cefr_level, limit=count
                )
            )
            for prompt in prompts:
                recommendations.append({
                    "recommendation_type": RecommendationType.EXERCISE,
                    "title": f"Speaking Practice: {prompt.prompt_text[:50]}...",
                    "description": f"Practice speaking with {profile.target_cefr_level} level prompts",
                    "content_type": "speaking",
                    "content_id": prompt.id,
                    "content_metadata": {"difficulty": prompt.difficulty_level, "type": prompt.exercise_type},
                    "relevance_score": 0.8 + priority_boost,
                    "confidence_score": 0.9,
                    "priority_score": 0.7 + priority_boost,
                    "reasoning": f"Matches your {profile.target_cefr_level} target level",
                    "expected_benefit": "Improve speaking fluency and confidence",
                    "estimated_time_minutes": prompt.estimated_duration_minutes
                })
        
        elif skill == "writing":
            prompts = await writing_prompt.get_by_level(
                db, level=profile.target_cefr_level, limit=count
            )
            for prompt in prompts:
                recommendations.append({
                    "recommendation_type": RecommendationType.EXERCISE,
                    "title": f"Writing Practice: {prompt.title}",
                    "description": f"Develop writing skills with {profile.target_cefr_level} level exercises",
                    "content_type": "writing",
                    "content_id": prompt.id,
                    "content_metadata": {"difficulty": prompt.difficulty_level, "type": prompt.writing_type},
                    "relevance_score": 0.8 + priority_boost,
                    "confidence_score": 0.9,
                    "priority_score": 0.7 + priority_boost,
                    "reasoning": f"Matches your {profile.target_cefr_level} target level",
                    "expected_benefit": "Improve writing accuracy and style",
                    "estimated_time_minutes": prompt.estimated_duration_minutes
                })
        
        return recommendations
    
    # Personal Trainer AI
    async def chat_with_trainer(self, db: AsyncSession, user_profile_id: int, user_message: str, context: Dict[str, Any] = None) -> ChatWithTrainerResponse:
        """Handle chat interaction with AI personal trainer"""
        profile = await learning_profile.get(db, id=user_profile_id)
        if not profile:
            raise ValueError("User profile not found")
        
        # Simple AI response for now (can be enhanced with actual AI service)
        ai_response = self._generate_simple_trainer_response(user_message, profile)
        
        # Determine interaction type
        interaction_type = self._classify_interaction_type(user_message, ai_response)
        
        # Create trainer interaction record
        interaction_create = PersonalTrainerInteractionCreate(
            user_profile_id=user_profile_id,
            interaction_type=interaction_type,
            trainer_message=ai_response["message"],
            context_data=context or {},
            tone=ai_response.get("tone", "encouraging"),
            formality_level=self._determine_formality_level(profile.personality_type),
            is_proactive=False
        )
        
        saved_interaction = await trainer_interaction.create(db, obj_in=interaction_create)
        
        # Generate suggestions based on conversation
        suggestions = await self._generate_contextual_suggestions(db, profile, user_message, ai_response)
        
        trainer_response = PersonalTrainerResponse(
            message=ai_response["message"],
            interaction_type=interaction_type,
            context=ai_response.get("context", {}),
            suggested_actions=ai_response.get("suggested_actions", []),
            follow_up_questions=ai_response.get("follow_up_questions", [])
        )
        
        return ChatWithTrainerResponse(
            trainer_response=trainer_response,
            interaction_id=saved_interaction.id,
            suggestions=suggestions
        )
    
    def _generate_simple_trainer_response(self, user_message: str, profile) -> Dict[str, Any]:
        """Generate a simple AI trainer response"""
        user_lower = user_message.lower()
        
        # Greeting responses
        if any(word in user_lower for word in ["hello", "hi", "good morning", "good afternoon"]):
            responses = [
                f"Hello! Ready to continue your journey to {profile.target_cefr_level} level English?",
                f"Hi there! How are you feeling about your {profile.primary_goal.value} goals today?",
                f"Good to see you! Let's make some progress on your English skills."
            ]
            return {
                "message": random.choice(responses),
                "tone": "friendly",
                "suggested_actions": ["Start today's lesson", "Review yesterday's progress", "Set new goals"],
                "follow_up_questions": ["What would you like to focus on today?", "How are you feeling about your progress?"]
            }
        
        # Help requests
        elif any(word in user_lower for word in ["help", "stuck", "difficult", "hard"]):
            responses = [
                "I understand it can be challenging! Let's break this down into smaller steps.",
                "Don't worry, everyone faces difficulties while learning. What specific area is giving you trouble?",
                "That's completely normal! Learning a language has ups and downs. Let me help you through this."
            ]
            return {
                "message": random.choice(responses),
                "tone": "supportive",
                "suggested_actions": ["Try an easier exercise first", "Review fundamentals", "Take a short break"],
                "follow_up_questions": ["Which skill is most challenging for you?", "Would you like me to recommend some easier exercises?"]
            }
        
        # Motivation requests
        elif any(word in user_lower for word in ["tired", "unmotivated", "boring", "discouraged"]):
            responses = [
                f"I believe in you! Remember, you've already made progress toward your {profile.primary_goal.value} goal.",
                "Every expert was once a beginner. Your consistent effort is what matters most!",
                "It's okay to feel this way sometimes. Let's find something fun and engaging to reignite your passion!"
            ]
            return {
                "message": random.choice(responses),
                "tone": "motivational",
                "suggested_actions": ["Try a fun speaking exercise", "Review your achievements", "Set a small daily goal"],
                "follow_up_questions": ["What initially motivated you to learn English?", "Would you like to try something different today?"]
            }
        
        # Progress inquiries
        elif any(word in user_lower for word in ["progress", "improvement", "better", "level"]):
            responses = [
                "Great question! Let me check your recent performance and give you an update.",
                "I'm proud of your dedication! Your consistency is really showing in your results.",
                "Progress isn't always linear, but you're definitely moving in the right direction!"
            ]
            return {
                "message": random.choice(responses),
                "tone": "encouraging",
                "suggested_actions": ["View detailed progress report", "Set new milestones", "Celebrate achievements"],
                "follow_up_questions": ["Which skill do you feel most confident about?", "What would you like to improve next?"]
            }
        
        # Default response
        else:
            responses = [
                "That's interesting! Tell me more about what you're thinking.",
                "I'm here to help you with your English learning journey. What can I assist you with?",
                f"As your personal English trainer, I'm committed to helping you reach {profile.target_cefr_level} level. How can I support you today?"
            ]
            return {
                "message": random.choice(responses),
                "tone": "helpful",
                "suggested_actions": ["Start a lesson", "Get recommendations", "Check progress"],
                "follow_up_questions": ["What aspect of English would you like to work on?", "Do you have any specific questions?"]
            }
    
    def _classify_interaction_type(self, user_message: str, ai_response: Dict[str, Any]) -> TrainerInteractionType:
        """Classify the type of interaction based on content"""
        user_lower = user_message.lower()
        
        if any(word in user_lower for word in ["help", "stuck", "difficult", "hard"]):
            return TrainerInteractionType.FEEDBACK
        elif any(word in user_lower for word in ["hello", "hi", "good morning", "good afternoon"]):
            return TrainerInteractionType.GREETING
        elif any(word in user_lower for word in ["tired", "unmotivated", "boring"]):
            return TrainerInteractionType.MOTIVATION
        elif any(word in user_lower for word in ["what should", "recommend", "suggest"]):
            return TrainerInteractionType.SUGGESTION
        elif any(word in user_lower for word in ["wrong", "mistake", "error", "correct"]):
            return TrainerInteractionType.CORRECTION
        else:
            return TrainerInteractionType.FEEDBACK
    
    def _determine_formality_level(self, personality_type) -> str:
        """Determine appropriate formality level"""
        formal_types = ["guided", "independent"]
        return "formal" if personality_type.value in formal_types else "casual"
    
    async def _generate_contextual_suggestions(self, db: AsyncSession, profile, user_message: str, ai_response: Dict[str, Any]) -> List[str]:
        """Generate contextual suggestions based on conversation"""
        suggestions = []
        user_lower = user_message.lower()
        
        # Skill-based suggestions
        if any(word in user_lower for word in ["speaking", "pronunciation", "talk"]):
            suggestions.extend([
                "Try a speaking exercise for your level",
                "Practice pronunciation with audio feedback",
                "Join a conversation practice session"
            ])
        elif any(word in user_lower for word in ["listening", "hear", "understand"]):
            suggestions.extend([
                "Listen to audio content at your level",
                "Practice with listening comprehension exercises",
                "Try dictation exercises"
            ])
        elif any(word in user_lower for word in ["reading", "text", "comprehension"]):
            suggestions.extend([
                "Read texts matched to your level",
                "Practice reading comprehension exercises",
                "Build vocabulary through reading"
            ])
        elif any(word in user_lower for word in ["writing", "essay", "composition"]):
            suggestions.extend([
                "Complete writing prompts for your level",
                "Practice grammar through writing exercises",
                "Get AI feedback on your writing"
            ])
        
        # Motivational suggestions
        if any(word in user_lower for word in ["difficult", "hard", "struggle"]):
            suggestions.extend([
                "Try easier content to build confidence",
                "Review fundamentals for this skill",
                "Set smaller, achievable daily goals"
            ])
        
        # Progress-based suggestions
        if any(word in user_lower for word in ["progress", "improve", "better"]):
            suggestions.extend([
                "Check your detailed progress analytics",
                "Review your recent achievements",
                "Adjust your learning goals"
            ])
        
        return suggestions
    
    async def _create_welcome_interaction(self, db: AsyncSession, user_profile_id: int, primary_goal):
        """Create welcome interaction for new users"""
        welcome_messages = {
            LearningGoalType.FLUENCY: "Welcome! I'm excited to help you achieve fluency in English. Let's start with understanding your current level and creating a personalized path for you.",
            LearningGoalType.BUSINESS: "Hello! Ready to boost your business English skills? I'll help you master professional communication and workplace vocabulary.",
            LearningGoalType.TRAVEL: "Hi there! Planning to travel? Let's get you confident with essential English for your adventures around the world.",
            LearningGoalType.EXAM_PREP: "Welcome! I'm here to help you ace your English exam. We'll focus on test strategies and skill building.",
            LearningGoalType.ACADEMIC: "Hello! Ready to excel in academic English? I'll guide you through advanced reading, writing, and critical thinking skills."
        }
        
        message = welcome_messages.get(primary_goal, "Welcome to your personalized English learning journey! I'm here to support you every step of the way.")
        
        interaction_create = PersonalTrainerInteractionCreate(
            user_profile_id=user_profile_id,
            interaction_type=TrainerInteractionType.GREETING,
            trainer_message=message,
            context_data={"event": "user_registration"},
            is_proactive=True
        )
        
        await trainer_interaction.create(db, obj_in=interaction_create)
    
    # Analytics and Insights
    async def get_learning_insights(self, db: AsyncSession, user_profile_id: int) -> LearningInsights:
        """Generate comprehensive learning insights for user"""
        profile = await learning_profile.get(db, id=user_profile_id)
        if not profile:
            raise ValueError("User profile not found")
        
        # Get recent analytics
        recent_analytics = await learning_analytics.get_performance_trends(
            db, user_profile_id=user_profile_id, days=30
        )
        
        # Analyze progress
        progress_summary = self._analyze_progress(recent_analytics)
        strengths = self._identify_strengths(recent_analytics)
        improvements = self._identify_weak_areas(recent_analytics, profile)
        
        # Get current recommendations
        recommendations = await content_recommendation.get_by_user_profile(
            db, user_profile_id=user_profile_id, limit=5
        )
        
        # Get next milestones
        current_path = await learning_path.get_active_path(db, user_profile_id=user_profile_id)
        next_milestones = []
        if current_path:
            milestones = await learning_milestone.get_by_learning_path(
                db, learning_path_id=current_path.id
            )
            next_milestones = milestones[current_path.current_step:current_path.current_step+3]
        
        # Generate motivation tips
        motivation_tips = self._generate_motivation_tips(profile, progress_summary)
        
        return LearningInsights(
            user_profile_id=user_profile_id,
            current_level=profile.target_cefr_level,
            progress_summary=progress_summary,
            strengths=strengths,
            areas_for_improvement=improvements,
            recommendations=recommendations,
            motivation_tips=motivation_tips,
            next_milestones=next_milestones
        )
    
    def _analyze_progress(self, analytics: List) -> Dict[str, Any]:
        """Analyze user's learning progress"""
        if not analytics:
            return {"message": "Not enough data yet", "trend": "neutral"}
        
        # Calculate trends
        recent_avg = sum(a.average_accuracy for a in analytics[-7:]) / min(7, len(analytics))
        older_avg = sum(a.average_accuracy for a in analytics[-14:-7]) / max(1, min(7, len(analytics) - 7))
        
        trend = "improving" if recent_avg > older_avg else "declining" if recent_avg < older_avg else "stable"
        
        return {
            "current_accuracy": recent_avg,
            "trend": trend,
            "improvement_rate": recent_avg - older_avg,
            "consistency": sum(a.consistency_score for a in analytics) / len(analytics),
            "total_study_time": sum(a.study_time_minutes for a in analytics),
            "streak_days": analytics[-1].streak_days if analytics else 0
        }
    
    def _identify_strengths(self, analytics: List) -> List[str]:
        """Identify user's learning strengths"""
        if not analytics:
            return []
        
        # Calculate average scores for each skill
        avg_scores = {
            'listening': sum(a.listening_score for a in analytics) / len(analytics),
            'speaking': sum(a.speaking_score for a in analytics) / len(analytics),
            'reading': sum(a.reading_score for a in analytics) / len(analytics),
            'writing': sum(a.writing_score for a in analytics) / len(analytics)
        }
        
        # Identify skills above 80% threshold
        strengths = [skill.title() for skill, score in avg_scores.items() if score > 0.8]
        
        # Add consistency if user is consistent
        if sum(a.consistency_score for a in analytics) / len(analytics) > 0.8:
            strengths.append("Consistent practice")
        
        return strengths
    
    def _generate_motivation_tips(self, profile, progress_summary: Dict[str, Any]) -> List[str]:
        """Generate personalized motivation tips"""
        tips = []
        
        # Personality-based tips
        if profile.personality_type.value == "competitive":
            tips.append("Challenge yourself with harder exercises to push your limits!")
        elif profile.personality_type.value == "collaborative":
            tips.append("Consider joining study groups or language exchange sessions")
        
        # Progress-based tips
        if progress_summary.get("trend") == "improving":
            tips.append("Great progress! Keep up the momentum with consistent practice")
        elif progress_summary.get("trend") == "declining":
            tips.append("Don't worry about temporary setbacks - adjust your study schedule and try different approaches")
        
        # Goal-based tips
        if profile.primary_goal == LearningGoalType.FLUENCY:
            tips.append("Practice speaking daily, even if just for 5 minutes")
        elif profile.primary_goal == LearningGoalType.EXAM_PREP:
            tips.append("Focus on timed practice to build test-taking stamina")
        
        return tips[:5]  # Return max 5 tips
    
    # Dashboard
    async def get_personalization_dashboard(self, db: AsyncSession, user_profile_id: int) -> PersonalizationDashboard:
        """Get comprehensive personalization dashboard"""
        profile = await learning_profile.get(db, id=user_profile_id)
        if not profile:
            raise ValueError("User profile not found")
        
        # Get all dashboard components
        active_path = await learning_path.get_active_path(db, user_profile_id=user_profile_id)
        recent_recommendations = await content_recommendation.get_by_user_profile(
            db, user_profile_id=user_profile_id, limit=5
        )
        recent_interactions = await trainer_interaction.get_recent_interactions(
            db, user_profile_id=user_profile_id, hours=48
        )
        analytics = await learning_analytics.get_by_user_profile(
            db, user_profile_id=user_profile_id, limit=30
        )
        insights = await self.get_learning_insights(db, user_profile_id)
        
        return PersonalizationDashboard(
            user_profile=profile,
            active_learning_path=active_path,
            recent_recommendations=recent_recommendations,
            recent_trainer_interactions=recent_interactions,
            learning_analytics=analytics,
            insights=insights,
            adaptive_adjustments=[]  # Will be populated by adaptive learning engine
        )
    
    # Add onboarding service methods
    async def start_onboarding(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """Start the onboarding process for a new user"""
        # Check if onboarding already exists
        existing_onboarding = await user_onboarding.get_by_user_id(db, user_id=user_id)
        if existing_onboarding and existing_onboarding.is_completed:
            return {
                "message": "Onboarding already completed",
                "onboarding": existing_onboarding,
                "current_step": existing_onboarding.current_step
            }
        
        # Create or update onboarding
        if not existing_onboarding:
            onboarding = await user_onboarding.create_for_user(
                db, user_id=user_id, 
                obj_in={"current_step": OnboardingStep.WELCOME.value}
            )
        else:
            onboarding = existing_onboarding
        
        return {
            "message": "Onboarding started",
            "onboarding": onboarding,
            "current_step": onboarding.current_step,
            "next_steps": self._get_onboarding_next_steps(onboarding.current_step)
        }
    
    def get_available_categories(self) -> List[Dict[str, Any]]:
        """Get all available learning categories with descriptions"""
        category_descriptions = {
            LearningCategory.GENERAL_ENGLISH: {
                "name": "General English",
                "description": "Build overall English proficiency with balanced focus on all skills",
                "focus_areas": ["everyday conversations", "basic grammar", "common vocabulary"],
                "suitable_for": ["beginners", "general learners", "everyday communication"]
            },
            LearningCategory.BUSINESS_ENGLISH: {
                "name": "Business English",
                "description": "Professional English for workplace communication",
                "focus_areas": ["business vocabulary", "formal writing", "presentations", "meetings"],
                "suitable_for": ["professionals", "career advancement", "workplace communication"]
            },
            LearningCategory.TRAVEL_ENGLISH: {
                "name": "Travel English",
                "description": "Essential English for travelers and tourists",
                "focus_areas": ["travel vocabulary", "directions", "booking", "cultural communication"],
                "suitable_for": ["travelers", "tourists", "hospitality workers"]
            },
            LearningCategory.ACADEMIC_ENGLISH: {
                "name": "Academic English",
                "description": "English for academic and educational purposes",
                "focus_areas": ["academic writing", "research skills", "formal presentations", "critical thinking"],
                "suitable_for": ["students", "researchers", "academic professionals"]
            },
            LearningCategory.EXAM_PREPARATION: {
                "name": "Exam Preparation",
                "description": "Prepare for English proficiency exams (IELTS, TOEFL, etc.)",
                "focus_areas": ["test strategies", "exam formats", "time management", "specific skills"],
                "suitable_for": ["exam candidates", "certification seekers"]
            },
            LearningCategory.CONVERSATION_PRACTICE: {
                "name": "Conversation Practice",
                "description": "Improve speaking fluency and confidence",
                "focus_areas": ["speaking fluency", "pronunciation", "natural expressions", "confidence"],
                "suitable_for": ["shy speakers", "fluency improvement", "conversation skills"]
            },
            LearningCategory.GRAMMAR_FOCUS: {
                "name": "Grammar Focus",
                "description": "Master English grammar rules and structures",
                "focus_areas": ["grammar rules", "sentence structure", "verb tenses", "accuracy"],
                "suitable_for": ["grammar improvement", "accuracy focus", "structured learning"]
            },
            LearningCategory.VOCABULARY_BUILDING: {
                "name": "Vocabulary Building",
                "description": "Expand your English vocabulary systematically",
                "focus_areas": ["word learning", "synonyms", "collocations", "word families"],
                "suitable_for": ["vocabulary expansion", "word enthusiasts", "expression improvement"]
            },
            LearningCategory.PRONUNCIATION_IMPROVEMENT: {
                "name": "Pronunciation Improvement",
                "description": "Perfect your English pronunciation and accent",
                "focus_areas": ["phonetics", "accent reduction", "intonation", "clarity"],
                "suitable_for": ["accent improvement", "clarity issues", "pronunciation focus"]
            },
            LearningCategory.WRITING_SKILLS: {
                "name": "Writing Skills",
                "description": "Develop strong English writing abilities",
                "focus_areas": ["essay writing", "grammar in context", "style", "organization"],
                "suitable_for": ["writing improvement", "academic writing", "professional communication"]
            },
            LearningCategory.READING_COMPREHENSION: {
                "name": "Reading Comprehension",
                "description": "Improve reading skills and understanding",
                "focus_areas": ["reading speed", "comprehension", "vocabulary in context", "analysis"],
                "suitable_for": ["reading improvement", "comprehension skills", "academic reading"]
            },
            LearningCategory.LISTENING_SKILLS: {
                "name": "Listening Skills",
                "description": "Enhance listening comprehension and understanding",
                "focus_areas": ["listening comprehension", "accent recognition", "note-taking", "audio materials"],
                "suitable_for": ["listening improvement", "comprehension skills", "audio learning"]
            }
        }
        
        return [
            {
                "category": category.value,
                "display_name": info["name"],
                "description": info["description"],
                "focus_areas": info["focus_areas"],
                "suitable_for": info["suitable_for"]
            }
            for category, info in category_descriptions.items()
        ]
    
    async def process_level_assessment(self, db: AsyncSession, user_id: int, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process level assessment results and update onboarding"""
        # Calculate assessment score and level
        assessment_result = self._calculate_assessment_level(assessment_data)
        
        # Update onboarding with assessment results
        onboarding = await user_onboarding.update_step(
            db, user_id=user_id, 
            step=OnboardingStep.LEVEL_ASSESSMENT.value,
            step_data={
                "assessed_level": assessment_result["level"],
                "assessment_score": assessment_result["score"],
                "assessment_details": assessment_result["details"]
            }
        )
        
        return {
            "onboarding": onboarding,
            "assessment_result": assessment_result,
            "next_step": OnboardingStep.CATEGORY_SELECTION.value,
            "recommendations": self._get_level_based_recommendations(assessment_result["level"])
        }
    
    async def process_category_selection(self, db: AsyncSession, user_id: int, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process category selection and create user preferences"""
        # Update onboarding with category selection
        onboarding = await user_onboarding.update_step(
            db, user_id=user_id,
            step=OnboardingStep.CATEGORY_SELECTION.value,
            step_data=category_data
        )
        
        # Create category preferences
        preferences = await user_category_preference.create_from_onboarding(
            db, user_id=user_id,
            categories=category_data["selected_categories"],
            primary_category=category_data["primary_category"],
            priorities=category_data.get("category_priorities", {})
        )
        
        return {
            "onboarding": onboarding,
            "category_preferences": preferences,
            "next_step": OnboardingStep.GOALS_SETTING.value,
            "recommendations": self._get_category_based_recommendations(category_data["selected_categories"])
        }
    
    async def complete_onboarding_and_generate_path(self, db: AsyncSession, user_id: int, final_data: Dict[str, Any]) -> Dict[str, Any]:
        """Complete onboarding and generate personalized learning path"""
        # Get current onboarding data
        onboarding = await user_onboarding.get_by_user_id(db, user_id=user_id)
        if not onboarding:
            raise ValueError("Onboarding not found")
        
        # Update with final preferences
        onboarding = await user_onboarding.update_step(
            db, user_id=user_id,
            step=OnboardingStep.PREFERENCES_SETUP.value,
            step_data=final_data
        )
        
        # Create learning profile based on onboarding data
        profile_data = self._create_profile_from_onboarding(onboarding)
        profile = await self.create_user_profile(db, user_id=user_id, profile_data=profile_data)
        
        # Generate learning path based on categories and preferences
        learning_path = await self._generate_category_based_learning_path(db, profile["profile"], onboarding)
        
        # Complete onboarding
        completed_onboarding = await user_onboarding.complete_onboarding(
            db, user_id=user_id,
            feedback=final_data.get("feedback"),
            rating=final_data.get("rating")
        )
        
        # Generate initial recommendations
        recommendations = await self.generate_recommendations(db, user_profile_id=profile["profile"].id, limit=10)
        
        return {
            "onboarding": completed_onboarding,
            "learning_profile": profile["profile"],
            "learning_path": learning_path,
            "recommendations": recommendations,
            "welcome_message": self._generate_welcome_message(onboarding, profile["profile"]),
            "next_actions": self._get_next_actions_for_new_user(learning_path)
        }
    
    def _get_onboarding_next_steps(self, current_step: str) -> List[str]:
        """Get next steps in onboarding process"""
        step_flow = {
            OnboardingStep.WELCOME.value: ["Take level assessment", "Learn about the platform"],
            OnboardingStep.LEVEL_ASSESSMENT.value: ["Select learning categories", "Set learning goals"],
            OnboardingStep.CATEGORY_SELECTION.value: ["Set learning goals", "Choose study preferences"],
            OnboardingStep.GOALS_SETTING.value: ["Set up preferences", "Generate learning path"],
            OnboardingStep.PREFERENCES_SETUP.value: ["Generate personalized learning path"],
            OnboardingStep.LEARNING_PATH_GENERATION.value: ["Complete onboarding", "Start learning"],
            OnboardingStep.COMPLETED.value: ["Start your first lesson", "Explore the platform"]
        }
        
        return step_flow.get(current_step, ["Continue onboarding"])
    
    def _calculate_assessment_level(self, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate CEFR level from assessment data"""
        # Simple assessment logic - can be enhanced with more sophisticated algorithms
        answers = assessment_data.get("assessment_answers", {})
        self_reported = assessment_data.get("self_reported_level")
        
        # Calculate score based on correct answers
        total_questions = len(answers)
        correct_answers = sum(1 for answer in answers.values() if answer.get("correct", False))
        score = correct_answers / total_questions if total_questions > 0 else 0.5
        
        # Map score to CEFR level
        if score >= 0.9:
            level = "C2"
        elif score >= 0.8:
            level = "C1"
        elif score >= 0.7:
            level = "B2"
        elif score >= 0.6:
            level = "B1"
        elif score >= 0.4:
            level = "A2"
        else:
            level = "A1"
        
        # Adjust based on self-reported level if provided
        if self_reported and self_reported in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            # Take average of calculated and self-reported
            levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
            calc_index = levels.index(level)
            self_index = levels.index(self_reported)
            avg_index = (calc_index + self_index) // 2
            level = levels[avg_index]
        
        # Generate skill breakdown
        skill_breakdown = {
            "listening": min(score + 0.1, 1.0),
            "speaking": max(score - 0.1, 0.0),
            "reading": score,
            "writing": max(score - 0.05, 0.0)
        }
        
        return {
            "level": level,
            "score": score,
            "details": {
                "total_questions": total_questions,
                "correct_answers": correct_answers,
                "skill_breakdown": skill_breakdown,
                "confidence": 0.8 if self_reported else 0.6
            }
        }
    
    def _get_level_based_recommendations(self, level: str) -> List[str]:
        """Get recommendations based on assessed level"""
        recommendations = {
            "A1": [
                "Start with basic vocabulary and simple sentences",
                "Focus on everyday topics and situations",
                "Practice pronunciation with simple words",
                "Begin with present tense verbs"
            ],
            "A2": [
                "Expand vocabulary for common situations",
                "Practice past and future tenses",
                "Work on basic conversations",
                "Start reading simple texts"
            ],
            "B1": [
                "Focus on expressing opinions and ideas",
                "Practice complex sentence structures",
                "Improve listening comprehension",
                "Start writing short essays"
            ],
            "B2": [
                "Work on fluency and natural expression",
                "Practice advanced grammar structures",
                "Engage with authentic materials",
                "Develop critical thinking in English"
            ],
            "C1": [
                "Perfect advanced grammar and vocabulary",
                "Focus on nuanced expression",
                "Practice academic and professional English",
                "Work on complex text analysis"
            ],
            "C2": [
                "Maintain and refine near-native proficiency",
                "Focus on specialized vocabulary",
                "Practice advanced writing styles",
                "Engage with complex academic materials"
            ]
        }
        
        return recommendations.get(level, recommendations["A1"])
    
    def _get_category_based_recommendations(self, categories: List[str]) -> List[str]:
        """Get recommendations based on selected categories"""
        category_tips = {
            "general_english": "Start with everyday conversations and basic grammar",
            "business_english": "Focus on professional vocabulary and formal communication",
            "travel_english": "Learn essential phrases for travel situations",
            "academic_english": "Develop academic writing and research skills",
            "exam_preparation": "Practice test strategies and exam-specific skills",
            "conversation_practice": "Focus on speaking fluency and confidence",
            "grammar_focus": "Master grammar rules systematically",
            "vocabulary_building": "Use spaced repetition for word learning",
            "pronunciation_improvement": "Practice phonetics and accent training",
            "writing_skills": "Develop structured writing techniques",
            "reading_comprehension": "Practice with varied text types",
            "listening_skills": "Use diverse audio materials"
        }
        
        recommendations = []
        for category in categories[:3]:  # Top 3 categories
            if category in category_tips:
                recommendations.append(category_tips[category])
        
        return recommendations
    
    def _create_profile_from_onboarding(self, onboarding) -> Dict[str, Any]:
        """Create learning profile data from onboarding information"""
        from app.models.personalization import LearningGoalType, LearningStyle, PersonalityType
        
        # Map onboarding data to profile structure
        primary_goal = self._map_category_to_goal(onboarding.primary_category)
        secondary_goals = [self._map_category_to_goal(cat) for cat in onboarding.selected_categories[:3]]
        
        # Determine learning style from preferences
        learning_style = onboarding.preferred_learning_style or LearningStyle.MIXED
        
        # Calculate skill weights based on category preferences
        skill_weights = self._calculate_skill_weights(onboarding.selected_categories)
        
        return {
            "learning_style": learning_style,
            "personality_type": PersonalityType.INDEPENDENT,  # Default, can be enhanced
            "preferred_session_duration": onboarding.daily_study_commitment,
            "primary_goal": primary_goal,
            "secondary_goals": secondary_goals,
            "target_cefr_level": onboarding.assessed_level or "B1",
            "listening_weight": skill_weights["listening"],
            "speaking_weight": skill_weights["speaking"],
            "reading_weight": skill_weights["reading"],
            "writing_weight": skill_weights["writing"],
            "preferred_content_types": onboarding.preferred_content_types or ["interactive", "audio", "text"],
            "challenge_preference": 0.7 if onboarding.preferred_difficulty == "challenging" else 0.3 if onboarding.preferred_difficulty == "gradual" else 0.5
        }
    
    def _map_category_to_goal(self, category: str) -> str:
        """Map learning category to learning goal type"""
        from app.models.personalization import LearningGoalType
        
        mapping = {
            "general_english": LearningGoalType.FLUENCY,
            "business_english": LearningGoalType.BUSINESS,
            "travel_english": LearningGoalType.TRAVEL,
            "academic_english": LearningGoalType.ACADEMIC,
            "exam_preparation": LearningGoalType.EXAM_PREP,
            "conversation_practice": LearningGoalType.SPEAKING,
            "grammar_focus": LearningGoalType.GRAMMAR,
            "vocabulary_building": LearningGoalType.VOCABULARY,
            "pronunciation_improvement": LearningGoalType.PRONUNCIATION,
            "writing_skills": LearningGoalType.WRITING,
            "reading_comprehension": LearningGoalType.READING,
            "listening_skills": LearningGoalType.LISTENING
        }
        
        return mapping.get(category, LearningGoalType.FLUENCY).value
    
    def _calculate_skill_weights(self, categories: List[str]) -> Dict[str, float]:
        """Calculate skill weights based on selected categories"""
        # Default balanced weights
        weights = {"listening": 0.25, "speaking": 0.25, "reading": 0.25, "writing": 0.25}
        
        # Adjust weights based on categories
        category_adjustments = {
            "conversation_practice": {"speaking": 0.15, "listening": 0.1},
            "writing_skills": {"writing": 0.2},
            "reading_comprehension": {"reading": 0.15},
            "listening_skills": {"listening": 0.15},
            "pronunciation_improvement": {"speaking": 0.1},
            "business_english": {"writing": 0.1, "speaking": 0.05},
            "academic_english": {"reading": 0.1, "writing": 0.1}
        }
        
        for category in categories:
            if category in category_adjustments:
                for skill, adjustment in category_adjustments[category].items():
                    weights[skill] += adjustment
        
        # Normalize weights to sum to 1.0
        total = sum(weights.values())
        for skill in weights:
            weights[skill] = weights[skill] / total
        
        return weights
    
    async def _generate_category_based_learning_path(self, db: AsyncSession, profile, onboarding) -> Dict[str, Any]:
        """Generate learning path based on selected categories"""
        from app.crud.personalization import category_learning_template
        
        # Get templates for selected categories
        templates = []
        for category in onboarding.selected_categories:
            category_templates = await category_learning_template.get_by_category(
                db, category=category, level=onboarding.assessed_level
            )
            if category_templates:
                templates.extend(category_templates[:1])  # Take best template per category
        
        # If no specific templates, use general template
        if not templates:
            general_templates = await category_learning_template.get_by_category(
                db, category="general_english", level=onboarding.assessed_level
            )
            if general_templates:
                templates = [general_templates[0]]
        
        # Generate learning path from templates
        if templates:
            # Use the primary category template as base
            primary_template = templates[0]
            learning_path_data = self._merge_templates(templates, onboarding)
            
            # Create learning path
            path_create_data = {
                "user_profile_id": profile.id,
                "name": f"Personalized {onboarding.primary_category.replace('_', ' ').title()} Path",
                "description": f"Customized learning path based on your interests in {', '.join(onboarding.selected_categories)}",
                "estimated_duration_weeks": primary_template.estimated_duration_weeks,
                "total_steps": primary_template.total_milestones,
                "path_data": learning_path_data
            }
            
            return await self.generate_learning_path(db, profile.id, path_create_data)
        
        # Fallback: generate basic learning path
        return await self.generate_learning_path(db, profile.id)
    
    def _merge_templates(self, templates, onboarding) -> Dict[str, Any]:
        """Merge multiple category templates into a single learning path"""
        # This is a simplified version - can be enhanced with more sophisticated merging logic
        primary_template = templates[0]
        merged_data = primary_template.template_data.copy()
        
        # Adjust content based on user preferences
        merged_data["user_preferences"] = {
            "selected_categories": onboarding.selected_categories,
            "primary_category": onboarding.primary_category,
            "learning_goals": onboarding.learning_goals,
            "target_timeline": onboarding.target_timeline,
            "preferred_difficulty": onboarding.preferred_difficulty
        }
        
        return merged_data
    
    def _generate_welcome_message(self, onboarding, profile) -> str:
        """Generate personalized welcome message"""
        return f"""
        Welcome to your personalized English learning journey! 
        
        Based on your assessment, you're at {onboarding.assessed_level} level, and we've created a learning path focused on {onboarding.primary_category.replace('_', ' ').title()}.
        
        Your learning plan includes:
        • {len(onboarding.selected_categories)} focus areas: {', '.join([cat.replace('_', ' ').title() for cat in onboarding.selected_categories])}
        • Daily study commitment: {onboarding.daily_study_commitment} minutes
        • Target timeline: {onboarding.target_timeline.replace('_', ' ') if onboarding.target_timeline else 'flexible'}
        
        Let's start your English learning adventure! 🚀
        """
    
    def _get_next_actions_for_new_user(self, learning_path) -> List[str]:
        """Get recommended next actions for new users"""
        return [
            "Complete your first lesson",
            "Set up daily study reminders",
            "Explore vocabulary practice",
            "Try a speaking exercise",
            "Review your learning path"
        ] 