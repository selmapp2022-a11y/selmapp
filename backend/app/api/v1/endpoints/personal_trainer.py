from typing import Any, Dict, List, Optional
from app.services.language_profile import profile_for
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import logging
import json

from app.core.database import get_db, get_sync_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    TrainerInteractionRequest, TrainerInteractionResponse,
    PersonalizedContentRequest, PersonalizedContentResponse
)
from app.schemas.personalization import (
    LearningJourneyRequest,
    LearningSessionRequest,
    LearningSessionResponse,
    LearningSessionCompleteRequest,
    LearningSessionCompleteResponse,
)
from app.services.ai_service import ai_service
from app.crud.personalization import user_onboarding, user_category_preference, learning_profile, learning_path
from app.crud.progress import user_progress_crud
from app.crud.cache import (
    daily_learning_plan_crud,
    weekly_learning_plan_crud,
    user_weekly_progress_crud,
    day_completion_record_crud,
)
from app.tasks.ai_tasks import pre_generate_next_day_content
from app.tasks.weekly_plan_tasks import (
    generate_week_plan_structure,
    check_and_trigger_next_week,
    retry_failed_generation,
)
from datetime import datetime, timedelta
from app.services.personalization_service import PersonalizationService
from app.services.personal_trainer_ai_service import personal_trainer_ai_service
from app.services.content_generation_workflow import content_workflow_service
from app.services.content_access_service import content_access_service
from app.schemas.personalization import LearningJourneyRequest
from app.models.personalization import OnboardingStep

router = APIRouter()
logger = logging.getLogger(__name__)

personalization_service = PersonalizationService()


def _to_module_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).strip().lower()
    mapping = {
        "conversation": "speaking",
        "pronunciation": "speaking",
        "comprehension": "reading",
    }
    return mapping.get(normalized, normalized)


def _enforce_trainer_access(
    sync_db: Session,
    current_user: User,
    *,
    module: Optional[str] = None,
    cefr_level: Optional[str] = None,
) -> None:
    resolved_level = cefr_level or getattr(getattr(current_user, "current_level", None), "value", None) or "A1"
    can_access, reason = content_access_service.can_start_new_lesson(
        sync_db,
        current_user,
        module=_to_module_name(module),
        cefr_level=resolved_level,
    )
    if not can_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


# New: Resilient daily content endpoint
@router.get("/daily-content")
async def get_daily_content_resilient(
    day_number: int = 1,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
):
    """Return a compact set of daily steps (reading, vocabulary, listening) with audio_url when ready.

    If listening audio is not yet generated, returns the step with audio_status: "pending_audio" and no media_url.
    """
    try:
        _enforce_trainer_access(sync_db, current_user)

        session_context = {"day_number": max(1, int(day_number))}
        result = await content_workflow_service.generate_adaptive_session_content(
            db=db,
            sync_db=sync_db,
            user=current_user,
            session_context=session_context,
        )
        if not result.get("success"):
            return {
                "message": "Partial content returned",
                "steps": [
                    {
                        "step_type": "reading",
                        "title": "Reading Practice",
                        "content": "Read a short paragraph about daily life.",
                        "media_url": None,
                        "questions": None,
                        "estimated_minutes": 5,
                    }
                ],
                "error": result.get("error"),
            }

        steps = result.get("session_content", [])
        # Add resilience metadata for listening
        for s in steps:
            if s.get("type") == "listening":
                if not s.get("media_url"):
                    s["audio_status"] = "pending_audio"
        return {"steps": steps, "estimated_minutes": result.get("estimated_difficulty", "appropriate")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting daily content: {e}")
        return {
            "message": "Temporary issue fetching daily content",
            "steps": [],
            "error": str(e),
        }


@router.post("/chat", response_model=TrainerInteractionResponse)
async def chat_with_trainer(
    request: TrainerInteractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Chat with AI personal trainer"""
    try:
        # Get user profile and preferences
        user_profile = await _get_user_profile_for_trainer(db, current_user)
        
        # Get recent conversation history (implement this if you want to store chat history)
        conversation_history = []  # You can implement chat history storage later
        
        # Generate AI trainer response
        ai_result = await ai_service.generate_personal_trainer_response(
            user_message=request.message,
            user_profile=user_profile,
            conversation_history=conversation_history,
            current_lesson_context=request.lesson_context
        )
        
        if not ai_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ai_result.get("error", "Failed to generate trainer response")
            )
        
        # Parse AI response
        try:
            trainer_data = json.loads(ai_result["content"])
        except json.JSONDecodeError:
            # Fallback response if AI doesn't return valid JSON
            trainer_data = {
                "trainer_response": "I'm here to help you learn English! How can I assist you today?",
                "message_type": "encouragement",
                "corrections": [],
                "suggested_actions": [],
                "follow_up_questions": ["What would you like to practice today?"],
                "vocabulary_highlights": []
            }
        
        # Store interaction (you might want to implement this in database)
        interaction_id = 1  # Placeholder - implement actual storage
        
        return TrainerInteractionResponse(
            trainer_response=trainer_data.get("trainer_response", ""),
            message_type=trainer_data.get("message_type", "encouragement"),
            corrections=trainer_data.get("corrections", []),
            suggested_actions=trainer_data.get("suggested_actions", []),
            follow_up_questions=trainer_data.get("follow_up_questions", []),
            vocabulary_highlights=trainer_data.get("vocabulary_highlights", []),
            interaction_id=interaction_id
        )
        
    except Exception as e:
        logger.error(f"Error in trainer chat: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process trainer interaction"
        )

@router.post("/generate-content", response_model=PersonalizedContentResponse)
async def generate_personalized_content(
    request: PersonalizedContentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Generate personalized learning content based on user profile"""
    try:
        _enforce_trainer_access(sync_db, current_user, module=request.content_type)

        # Get user profile and preferences
        user_profile = await _get_user_profile_for_trainer(db, current_user)
        
        # Determine user's weak areas from progress
        weak_areas = await _get_user_weak_areas(db, current_user.id)
        
        # Get learning goals from onboarding
        onboarding = await user_onboarding.get_by_user_id(db, user_id=current_user.id)
        learning_goals = onboarding.learning_goals if onboarding else []
        
        # Use override level if provided, otherwise use user's current level
        target_level = request.difficulty_override or current_user.current_level.value
        
        if request.content_type == "recommendations":
            # Generate comprehensive recommendations
            result = await ai_service.generate_personalized_content_recommendations(
                user_level=target_level,
                user_preferences=user_profile,
                weak_areas=weak_areas,
                learning_goals=learning_goals
            )
            
            if not result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result.get("error", "Failed to generate recommendations")
                )
            
            try:
                recommendations_data = json.loads(result["content"])
                
                # Convert to our schema format
                all_recommendations = []
                for category, recs in recommendations_data.items():
                    if isinstance(recs, list):
                        for rec in recs:
                            all_recommendations.append({
                                "topic": rec.get("topic", ""),
                                "content_type": category.replace("_recommendations", ""),
                                "reason": rec.get("reason", ""),
                                "learning_outcome": rec.get("learning_outcome", ""),
                                "estimated_time_minutes": rec.get("estimated_time_minutes", 15)
                            })
                
                return PersonalizedContentResponse(
                    generated_content=recommendations_data,
                    recommendations=all_recommendations[:10],  # Limit to top 10
                    learning_path_update=None
                )
                
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to parse AI-generated recommendations"
                )
        
        elif request.content_type == "reading":
            # Generate reading content using existing AI reading service
            from app.services.ai_reading_service import ai_reading_service
            from app.models.reading import ReadingTextType
            from app.models.content import DifficultyLevel
            
            # Use specified topic or default based on user preferences
            topic = request.topic or _get_preferred_topic_for_user(user_profile)
            word_count = request.word_count or (200 if target_level in ["A1", "A2"] else 300)
            
            result = await ai_reading_service.generate_reading_text_with_vocabulary(
                db=db,
                level=DifficultyLevel(target_level),
                text_type=ReadingTextType.ARTICLE,  # Default to article
                topic=topic,
                word_count=word_count,
                vocabulary_count=10,
                include_comprehension_questions=True
            )
            
            recommendations = [{
                "topic": topic,
                "content_type": "reading",
                "reason": f"Generated based on your {target_level} level and interests",
                "learning_outcome": f"Improve reading comprehension and vocabulary for {topic}",
                "estimated_time_minutes": 15
            }]
            
            return PersonalizedContentResponse(
                generated_content=result,
                recommendations=recommendations,
                learning_path_update=None
            )
        
        else:
            # For other content types, use the general exercise generation
            result = await ai_service.generate_exercise_content(
                topic=request.topic or "general",
                difficulty_level=target_level,
                exercise_type=request.content_type,
                count=5
            )
            
            if not result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result.get("error", "Failed to generate content")
                )
            
            recommendations = [{
                "topic": request.topic or "general",
                "content_type": request.content_type,
                "reason": f"Personalized {request.content_type} exercises for your level",
                "learning_outcome": f"Improve {request.content_type} skills",
                "estimated_time_minutes": 20
            }]
            
            return PersonalizedContentResponse(
                generated_content={"exercises": result["content"]},
                recommendations=recommendations,
                learning_path_update=None
            )
        
    except Exception as e:
        logger.error(f"Error generating personalized content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate personalized content"
        )

@router.get("/recommendations")
async def get_daily_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Get daily personalized recommendations from AI trainer"""
    try:
        _enforce_trainer_access(sync_db, current_user)

        # Get user profile
        user_profile = await _get_user_profile_for_trainer(db, current_user)
        
        # Get weak areas and learning goals
        weak_areas = await _get_user_weak_areas(db, current_user.id)
        onboarding = await user_onboarding.get_by_user_id(db, user_id=current_user.id)
        learning_goals = onboarding.learning_goals if onboarding else []
        
        # Generate recommendations
        result = await ai_service.generate_personalized_content_recommendations(
            user_level=current_user.current_level.value,
            user_preferences=user_profile,
            weak_areas=weak_areas,
            learning_goals=learning_goals
        )
        
        if not result.get("success"):
            return {
                "message": "Unable to generate AI recommendations at this time",
                "recommendations": _get_fallback_recommendations(current_user.current_level)
            }
        
        try:
            recommendations_data = json.loads(result["content"])
            return {
                "message": "Here are your personalized daily recommendations!",
                "recommendations": recommendations_data,
                "last_updated": "now"
            }
        except json.JSONDecodeError:
            return {
                "message": "Here are some general recommendations for your level",
                "recommendations": _get_fallback_recommendations(current_user.current_level)
            }
        
    except Exception as e:
        logger.error(f"Error getting daily recommendations: {e}")
        return {
            "message": "Here are some general recommendations",
            "recommendations": _get_fallback_recommendations(current_user.current_level)
        }

# Helper Functions

async def _get_user_profile_for_trainer(db: AsyncSession, user: User, language: str = "en") -> Dict[str, Any]:
    """Build comprehensive user profile for AI trainer"""
    
    # Get onboarding data - use async session
    onboarding = await user_onboarding.get_by_user_id(db, user_id=user.id)
    
    # Get category preferences - use async session
    category_prefs = await user_category_preference.get_by_user_id(db, user_id=user.id)
    preferred_categories = [pref.category for pref in category_prefs] if category_prefs else []
    if (not preferred_categories) and onboarding and getattr(onboarding, "selected_categories", None):
        preferred_categories = onboarding.selected_categories or []
    
    return {
        "current_level": user.current_level.value,
        "native_language": user.native_language,
        # From the goal's exam (deprecated column user.target_language no longer read).
        "target_language": profile_for(language).english_name,
        "language_code": profile_for(language).code,
        "learning_goals": onboarding.learning_goals if onboarding else [],
        "preferred_categories": preferred_categories,
        "learning_style": onboarding.preferred_learning_style if onboarding else "mixed",
        "daily_study_commitment": onboarding.daily_study_commitment if onboarding else 30,
        "target_timeline": onboarding.target_timeline if onboarding else "flexible",
        "motivation_factors": onboarding.motivation_factors if onboarding else []
    }

async def _get_user_weak_areas(db: AsyncSession, user_id: int) -> List[str]:
    """Identify user's weak areas based on progress data"""
    weak_areas = []
    
    # Get user progress
    progress = await user_progress_crud.get_by_user(db, user_id=user_id)
    if not progress:
        return []
    
    # Check accuracy thresholds
    if progress.average_accuracy < 0.6:
        weak_areas.append("accuracy")
    
    # Check skill-specific areas (you can enhance this with more detailed tracking)
    if progress.vocabulary_mastered < 100:
        weak_areas.append("vocabulary")
    
    if progress.grammar_rules_learned < 20:
        weak_areas.append("grammar")
    
    if progress.speaking_sessions < 10:
        weak_areas.append("speaking")
    
    if progress.listening_hours < 5:
        weak_areas.append("listening")
    
    return weak_areas

def _get_preferred_topic_for_user(user_profile: Dict[str, Any]) -> str:
    """Get preferred topic based on user's category preferences"""
    categories = user_profile.get("preferred_categories", [])
    
    topic_mapping = {
        "general_english": "daily life",
        "business_english": "business and work",
        "travel_english": "travel and tourism",
        "academic_english": "education and research",
        "conversation_practice": "conversation and communication",
        "vocabulary_building": "vocabulary and expressions"
    }
    
    if categories:
        primary_category = categories[0]
        return topic_mapping.get(primary_category, "general topics")
    
    return "general topics"

def _get_fallback_recommendations(level) -> Dict[str, Any]:
    """Fallback recommendations when AI service is unavailable"""
    return {
        "reading_recommendations": [
            {
                "topic": "daily life",
                "text_type": "article",
                "reason": f"Appropriate for {level.value} level",
                "learning_outcome": "Improve reading comprehension",
                "estimated_time_minutes": 15
            }
        ],
        "vocabulary_recommendations": [
            {
                "topic": "common words",
                "word_count": 20,
                "reason": f"Essential {level.value} vocabulary",
                "learning_outcome": "Expand vocabulary knowledge",
                "estimated_time_minutes": 10
            }
        ],
        "grammar_recommendations": [
            {
                "topic": "basic grammar",
                "focus_area": f"{level.value} grammar rules",
                "reason": "Foundation grammar skills",
                "learning_outcome": "Improve grammar accuracy",
                "estimated_time_minutes": 20
            }
        ]
    }

@router.post("/daily-plan")
async def generate_daily_learning_plan(
    focus_skills: Optional[List[str]] = None,
    language: str = "en",  # from the goal's exam; the plan is generated in it
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Generate AI-powered daily learning plan"""
    try:
        _enforce_trainer_access(sync_db, current_user)

        # Read-or-create DailyLearningPlan for today
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        existing = await daily_learning_plan_crud.get_by_user_and_date(db, user_id=current_user.id, date_str=today_str)

        if existing and not existing.is_completed:
            return {
                "message": "Your personalized daily learning plan is ready!",
                "plan": existing.plan,
                "personalization_score": None,
                "estimated_time": existing.plan.get("plan_overview", {}).get("total_estimated_minutes", 30)
            }

        result = await personal_trainer_ai_service.generate_daily_learning_plan(
            db=db,
            sync_db=sync_db,
            user=current_user,
            focus_skills=focus_skills,
            language=language,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate daily plan")
            )
        
        # Persist plan with optional TTL (e.g., end of day)
        end_of_day = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)
        await daily_learning_plan_crud.upsert(
            db,
            user_id=current_user.id,
            date_str=today_str,
            plan=result["daily_plan"],
            expires_at=end_of_day
        )

        return {
            "message": "Your personalized daily learning plan is ready!",
            "plan": result["daily_plan"],
            "personalization_score": result["personalization_score"],
            "estimated_time": result["estimated_total_time"]
        }
        
    except Exception as e:
        logger.error(f"Error generating daily plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate daily learning plan"
        )

@router.post("/feedback")
async def provide_adaptive_feedback(
    user_performance: Dict[str, Any],
    exercise_context: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Get adaptive feedback from AI trainer based on performance"""
    try:
        result = await personal_trainer_ai_service.provide_adaptive_feedback(
            db=db,
            sync_db=sync_db,
            user=current_user,
            user_performance=user_performance,
            exercise_context=exercise_context
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate feedback")
            )
        
        return {
            "message": "Feedback generated successfully",
            "feedback": result["feedback"]
        }
        
    except Exception as e:
        logger.error(f"Error providing feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to provide adaptive feedback"
        )

# Removed legacy untyped /learning-session route to avoid ambiguity; keep typed version below

@router.post("/learning-session/complete", response_model=LearningSessionCompleteResponse)
async def complete_learning_session(
    completion: LearningSessionCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Record completion, update module progress, attempt to unlock next module."""
    try:
        # Minimal placeholder logic: compute progress and unlock based on simple thresholds
        results = completion.results or {}
        correct = int(results.get("correct", 0))
        total = int(results.get("total", 0))
        time_spent_minutes = int(getattr(completion, "time_spent_minutes", 0) or 0)

        accuracy = max(0.0, min(1.0, (correct / max(1, total))))

        # Progress bump heuristic: base 30% + 70% * accuracy
        progress_bump = (30.0 + 70.0 * accuracy)  # percent
        updated_progress = max(0.0, min(100.0, progress_bump))

        unlocked_next = updated_progress >= 100.0 or accuracy >= 0.8

        # Persist completed day record for quota enforcement and weekly analytics.
        try:
            absolute_day = max(1, int(completion.day_number or 1))
            week_number = ((absolute_day - 1) // 7) + 1
            day_in_week = ((absolute_day - 1) % 7) + 1
            await day_completion_record_crud.upsert(
                db,
                user_id=current_user.id,
                week_number=week_number,
                day_number=day_in_week,
                exercises_completed=max(0, total),
                correct_answers=max(0, correct),
                total_questions=max(0, total),
                time_spent_minutes=max(0, time_spent_minutes),
                content_types_completed=[completion.module_id] if completion.module_id else [],
            )
        except Exception as _dcr_err:
            logger.warning("Failed to persist day completion record for user %s: %s", current_user.id, _dcr_err)

        # Persist analytics to progress tables so Progress/Home show real data
        try:
            from datetime import date as _date
            from app.crud.progress import daily_progress_crud, user_progress_crud

            today = _date.today()

            # Treat `total` as number of exercises/questions completed in this session
            exercises_completed = max(0, total)
            # Simple points heuristic
            points_earned = max(0, correct) * 10

            daily_progress = await daily_progress_crud.create_or_update_daily(
                db,
                user_id=current_user.id,
                date=today,
                progress_data={
                    "study_time_minutes": max(0, time_spent_minutes),
                    "exercises_completed": exercises_completed,
                    "points_earned": points_earned,
                    "accuracy_rate": accuracy,
                    # daily_goal_met is computed after we update totals below
                    "daily_goal_met": False,
                },
            )

            # Update goal-met flag based on accumulated daily study time
            goal_met = (daily_progress.study_time_minutes or 0) >= int(getattr(current_user, "daily_goal_minutes", 0) or 0)
            if daily_progress.daily_goal_met != goal_met:
                daily_progress.daily_goal_met = goal_met
                db.add(daily_progress)
                await db.commit()
                await db.refresh(daily_progress)

            # Ensure user_progress exists
            progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
            if not progress:
                progress = await user_progress_crud.create_or_update(
                    db,
                    user_id=current_user.id,
                    progress_data={
                        "current_level": current_user.current_level,
                        "level_progress_percentage": 0.0,
                    },
                )

            old_total_ex = int(progress.total_exercises_completed or 0)
            old_avg = float(progress.average_accuracy or 0.0)
            new_total_ex = old_total_ex + exercises_completed

            progress.total_study_time_minutes = int(progress.total_study_time_minutes or 0) + max(0, time_spent_minutes)
            progress.total_exercises_completed = new_total_ex
            progress.total_points_earned = int(progress.total_points_earned or 0) + points_earned
            progress.last_study_date = datetime.utcnow()

            if new_total_ex > 0 and exercises_completed > 0:
                progress.average_accuracy = ((old_avg * old_total_ex) + (accuracy * exercises_completed)) / new_total_ex
            elif new_total_ex == 0:
                progress.average_accuracy = 0.0

            db.add(progress)
            await db.commit()
            await db.refresh(progress)

            # Update streak based on calendar day
            await user_progress_crud.update_streak(db, user_id=current_user.id, study_date=today)

        except Exception as _persist_err:
            logger.warning("Failed to persist progress analytics for user %s: %s", current_user.id, _persist_err)

        # ── Adaptive difficulty: recompute and persist profile adjustments ──
        try:
            from app.services.adaptive_difficulty_service import adaptive_difficulty_service
            current_level = getattr(getattr(current_user, "current_level", None), "value", None) or "A1"
            adaptive_result = await adaptive_difficulty_service.compute_adaptive_difficulty(
                db, user_id=current_user.id, current_level=current_level,
            )
            logger.info(
                "Adaptive difficulty for user %s: %s (score=%.3f, confidence=%.2f)",
                current_user.id,
                adaptive_result.recommended_level,
                adaptive_result.difficulty_score,
                adaptive_result.confidence,
            )
        except Exception as _adaptive_err:
            logger.warning("Adaptive difficulty update failed for user %s: %s", current_user.id, _adaptive_err)

        # Schedule pre-generation of next day content
        try:
            next_day = (completion.day_number or 1) + 1
            # Fire-and-forget Celery task
            pre_generate_next_day_content.delay(user_id=current_user.id, day_number=next_day)
        except Exception:
            pass  # Celery might not be running locally

        # For now, return computed values
        return {
            "module_id": completion.module_id,
            "day_number": completion.day_number,
            "updated_progress_percentage": updated_progress,
            "unlocked_next_module": unlocked_next,
        }
    except Exception as e:
        logger.error(f"Error completing learning session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete learning session"
        )


@router.post("/step-progress")
async def save_step_progress(
    progress_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Save progress for individual lesson steps (per-activity save)"""
    try:
        # Extract progress data
        session_id = progress_data.get("session_id", "")
        module_id = progress_data.get("module_id", "")
        day_number = progress_data.get("day_number", 1)
        step_index = progress_data.get("step_index", 0)
        correct = progress_data.get("correct", 0)
        total = progress_data.get("total", 1)
        time_spent = progress_data.get("time_spent_minutes", 0)
        skill_type = progress_data.get("skill_type", "general")
        
        # Calculate step accuracy
        accuracy = correct / max(1, total)
        
        # Log progress (could be stored in a step_progress table in the future)
        logger.info(
            f"Step progress: user={current_user.id}, module={module_id}, "
            f"day={day_number}, step={step_index}, skill={skill_type}, "
            f"accuracy={accuracy:.2f}, time={time_spent}min"
        )
        
        return {
            "success": True,
            "module_id": module_id,
            "day_number": day_number,
            "step_index": step_index,
            "accuracy": accuracy,
        }
    except Exception as e:
        logger.error(f"Error saving step progress: {e}")
        # Don't fail the request - step progress is supplementary
        return {"success": False, "error": str(e)}


@router.post("/learning-journey")
async def create_learning_journey(
    journey_request: LearningJourneyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Create a complete personalized learning journey"""
    try:
        _enforce_trainer_access(sync_db, current_user)

        # Persist onboarding choices so the AI and the client can reliably resume.
        # We store categories in onboarding JSON (supports fine-grained ids like "daily_life", "food").
        try:
            cats = list(journey_request.preferred_categories or [])
            await user_onboarding.update_step(
                db,
                user_id=current_user.id,
                step=OnboardingStep.CATEGORY_SELECTION.value,
                step_data={
                    "selected_categories": cats,
                    "category_priorities": {c: i + 1 for i, c in enumerate(cats)},
                },
            )
            await user_onboarding.update_step(
                db,
                user_id=current_user.id,
                step=OnboardingStep.GOALS_SETTING.value,
                step_data={
                    "daily_study_commitment": int(journey_request.daily_study_time_minutes or 30),
                    "target_timeline": "flexible",
                },
            )
            # Best-effort: persist assessment results if provided in the request
            if isinstance(journey_request.assessment_results, dict) and journey_request.assessment_results:
                await user_onboarding.update_step(
                    db,
                    user_id=current_user.id,
                    step=OnboardingStep.LEVEL_ASSESSMENT.value,
                    step_data={
                        "assessed_level": journey_request.user_level,
                        "assessment_score": float(
                            journey_request.assessment_results.get("overall_score", 0.0) or 0.0
                        ),
                        "assessment_details": journey_request.assessment_results,
                    },
                )
        except Exception as persist_err:
            logger.warning(
                "Failed to persist onboarding prefs from learning-journey: user_id=%s err=%s",
                current_user.id,
                persist_err,
            )

        # Defensive clamp to avoid validation edge-cases propagating downstream
        try:
            original_days = journey_request.journey_duration_days
            clamped_days = max(7, min(1000, int(original_days)))
            if clamped_days != original_days:
                logger.info(
                    f"Clamping journey_duration_days from {original_days} to {clamped_days}"
                )
                # Pydantic model is immutable by default; rebuild with clamped value
                journey_request = LearningJourneyRequest(
                    user_level=journey_request.user_level,
                    preferred_categories=journey_request.preferred_categories,
                    learning_pace=journey_request.learning_pace,
                    daily_study_time_minutes=journey_request.daily_study_time_minutes,
                    assessment_results=journey_request.assessment_results,
                    journey_duration_days=clamped_days,
                )
        except Exception as clamp_err:
            logger.warning(f"Failed to clamp journey_duration_days: {clamp_err}")

        # If assessment_results is missing or empty, generate them via AI
        if not journey_request.assessment_results or journey_request.assessment_results.get('overall_score', 0) == 0:
            logger.info("Assessment results missing; generating via AI for user %s", current_user.id)
            try:
                from app.services.ai_service import ai_service  # Assuming AI service is available
                assessment_prompt = (
                    f"Generate concise assessment results for a {journey_request.user_level} learner. "
                    "Include numeric overall_score (0-100), skill_scores for grammar,vocabulary,reading,listening,speaking,writing (0-1 floats), "
                    "short feedback, and up to 5 recommendations as strings. Return pure JSON."
                )
                ai_result = await ai_service.generate_structured_content(
                    prompt=assessment_prompt,
                    content_type="assessment_results",
                )
                if ai_result.get("success"):
                    parsed = ai_result["content"]
                    if isinstance(parsed, str):
                        try:
                            parsed = json.loads(parsed)
                        except json.JSONDecodeError:
                            parsed = {}
                    if not isinstance(parsed, dict):
                        parsed = {}
                    journey_request = LearningJourneyRequest(
                        user_level=journey_request.user_level,
                        preferred_categories=journey_request.preferred_categories,
                        learning_pace=journey_request.learning_pace,
                        daily_study_time_minutes=journey_request.daily_study_time_minutes,
                        assessment_results=parsed or {
                            "overall_score": 60.0,
                            "skill_scores": {"grammar": 0.6, "vocabulary": 0.6, "reading": 0.6, "listening": 0.6, "speaking": 0.6, "writing": 0.6},
                            "feedback": "Baseline assessment created.",
                            "recommendations": ["Focus on vocabulary and listening"]
                        },
                        journey_duration_days=journey_request.journey_duration_days,
                    )
                else:
                    logger.warning("AI assessment generation failed; proceeding with defaults")
            except Exception as ai_err:
                logger.warning(f"AI assessment generation error: {ai_err}; proceeding with defaults")

        


        result = await content_workflow_service.create_complete_learning_journey(
            db=db,
            sync_db=sync_db,
            user=current_user,
            journey_request=journey_request
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to create learning journey")
            )
        
        return {
            "message": f"Your {journey_request.journey_duration_days}-day personalized learning journey is ready!",
            "journey": result["journey_overview"],
            "first_week_content": result["first_week_content"],
            "user_analysis": result["user_analysis"],
            "estimated_total_hours": result["total_estimated_hours"]
        }
        
    except Exception as e:
        logger.error(f"Error creating learning journey: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create learning journey"
        )

@router.post("/learning-session", response_model=LearningSessionResponse)
async def create_learning_session(
    session_request: LearningSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Create a concrete learning session (list of lesson steps) for a module/day"""
    try:
        context_data = session_request.context or {}
        module_hint = context_data.get("module_type") or context_data.get("skill_type")
        _enforce_trainer_access(sync_db, current_user, module=module_hint)

        session_context = {
            "module_id": session_request.module_id,
            "day_number": session_request.day_number or 1,
            **context_data
        }

        # Enforce journey locking: prevent jumping ahead (e.g. start day_49 without completing prior days).
        requested_day = 1
        try:
            requested_day = int(session_request.day_number or 1)
        except Exception:
            requested_day = 1
        if requested_day < 1:
            requested_day = 1

        max_allowed_day: Optional[int] = None
        consecutive_completed: Optional[int] = None
        modules_count: Optional[int] = None
        requested_is_completed: Optional[bool] = None
        requested_is_unlocked: Optional[bool] = None
        try:
            profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
            active = await learning_path.get_active_path(db, user_profile_id=profile.id) if profile else None
            pd = getattr(active, "path_data", None) or {}
            mods = pd.get("modules") if isinstance(pd, dict) else None
            if isinstance(mods, list) and mods:
                modules_count = len(mods)
                cc = 0
                for m in mods:
                    if not isinstance(m, dict):
                        continue
                    if m.get("isCompleted") is True or m.get("is_completed") is True:
                        cc += 1
                    else:
                        break
                consecutive_completed = cc
                max_allowed_day = min(len(mods), cc + 1)

                # Allow opening already-completed days (review), even if they are beyond the current sequential unlock.
                try:
                    if 1 <= requested_day <= len(mods):
                        rm = mods[requested_day - 1]
                        if isinstance(rm, dict):
                            requested_is_completed = (
                                rm.get("isCompleted") is True or rm.get("is_completed") is True
                            )
                            requested_is_unlocked = (
                                rm.get("isUnlocked") is True or rm.get("is_unlocked") is True
                            )
                except Exception:
                    pass
        except Exception:
            pass

        allowed = True if max_allowed_day is None else (requested_day <= max_allowed_day)

        if max_allowed_day is not None and not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Day {requested_day} is locked. Complete previous days to unlock it.",
            )

        result = await content_workflow_service.generate_adaptive_session_content(
            db=db,
            sync_db=sync_db,
            user=current_user,
            session_context=session_context
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to create learning session")
            )

        steps_raw = result.get("session_content", [])
        steps: list[dict] = []
        allowed_types = {"reading", "listening", "vocabulary", "grammar", "exercise", "quiz", "speaking"}
        
        # De-duplicate duplicate vocabulary steps (prevents empty/duplicate vocab screens in client)
        try:
            _deduped: list[dict] = []
            _seen_vocab: set = set()
            for _s in steps_raw:
                if _s.get("type") == "vocabulary":
                    _cj = _s.get("content_json")
                    _sig = None
                    if isinstance(_cj, dict):
                        _topic = (_cj.get("topic") or "").strip().lower()
                        _level = (_cj.get("level") or "").strip().upper()
                        _vw = _cj.get("vocabulary_words") or _cj.get("words") or []
                        _words: list[str] = []
                        if isinstance(_vw, list):
                            for _w in _vw:
                                if isinstance(_w, dict):
                                    _words.append(str(_w.get("word") or _w.get("text") or "").strip().lower())
                                else:
                                    _words.append(str(_w).strip().lower())
                        _sig = (_level, _topic, tuple([x for x in _words if x][:25]))
                    else:
                        _sig = ("", "", str(_s.get("title") or ""), str(_s.get("content") or ""))

                    if _sig in _seen_vocab:
                        continue
                    _seen_vocab.add(_sig)

                _deduped.append(_s)
            steps_raw = _deduped
        except Exception:
            # If de-dup fails for any reason, fall back to raw steps
            pass

        for s in steps_raw:
            original_type = s.get("type", "reading")
            step_type = original_type if original_type in allowed_types else "exercise"
            content_val = s.get("content")
            content_json_val = s.get("content_json")
            # If a producer mistakenly put structured content into `content`,
            # move it into `content_json` and keep `content` as a string/None.
            if isinstance(content_val, dict) and not isinstance(content_json_val, dict):
                content_json_val = content_val
                maybe_text = content_val.get("content")
                content_val = maybe_text if isinstance(maybe_text, str) else None
            elif content_val is not None and not isinstance(content_val, str):
                content_val = str(content_val)

            steps.append({
                "step_type": step_type,
                "title": s.get("title", "Lesson Step"),
                "content": content_val,
                "media_url": s.get("media_url"),
                "questions": s.get("questions"),
                "estimated_minutes": s.get("estimated_minutes", 5),
                "original_type": original_type if step_type != original_type else None,
                "content_json": content_json_val if isinstance(content_json_val, dict) else None,
            })

        # Inject a speaking step if none present to ensure journey includes speaking practice
        if not any(step.get("step_type") == "speaking" for step in steps):
            try:
                topic = session_context.get("topic") or "daily life"
                speaking = await personal_trainer_ai_service._generate_personalized_speaking_content(
                    db=db,
                    user=current_user,
                    user_profile=await personal_trainer_ai_service._build_comprehensive_user_profile(db, current_user),
                    topic=topic,
                )
                if speaking.get("success"):
                    speaking_payload = speaking.get("content")
                    speaking_content_json = speaking_payload if isinstance(speaking_payload, dict) else None
                    speaking_text: Optional[str] = None
                    if isinstance(speaking_payload, dict):
                        # Typical shape: {"success": true, "content": "<string>"}
                        _inner = speaking_payload.get("content")
                        if isinstance(_inner, str):
                            speaking_text = _inner
                    elif isinstance(speaking_payload, str):
                        speaking_text = speaking_payload

                    steps.append({
                        "step_type": "speaking",
                        "title": "Speaking Practice",
                        "content": speaking_text,
                        "content_json": speaking_content_json,
                        "estimated_minutes": 4,
                    })
            except Exception:
                pass

        return {
            "session_id": result.get("session_id", f"session_{current_user.id}"),
            "module_id": session_request.module_id,
            "day_number": session_request.day_number or 1,
            "steps": steps,
            "total_estimated_minutes": sum([s.get("estimated_minutes", 5) for s in steps])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating learning session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create learning session"
        )

@router.post("/adaptive-content")
async def generate_adaptive_content(
    session_context: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Generate content that adapts to user's current learning state"""
    try:
        module_hint = (session_context or {}).get("module_type") or (session_context or {}).get("skill_type")
        _enforce_trainer_access(sync_db, current_user, module=module_hint)

        result = await content_workflow_service.generate_adaptive_session_content(
            db=db,
            sync_db=sync_db,
            user=current_user,
            session_context=session_context
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate adaptive content")
            )

        return {
            "message": "Adaptive content generated based on your current learning state",
            "content": result["session_content"],
            "content_mix": result["content_mix"],
            "adaptation_reason": result["adaptation_reason"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating adaptive content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate adaptive content"
        )

@router.post("/learning-journey/extend")
async def extend_learning_journey(
    chunk_weeks: int = 4,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Extend the user's journey by 2–4 weeks based on recent performance and completed modules.

    Returns an object containing a compact modules list for the next chunk and updated analysis.
    """
    try:
        _enforce_trainer_access(sync_db, current_user)

        # Build a lightweight request using current user level and preferences
        # Derive preferred categories from onboarding
        onboarding = await user_onboarding.get_by_user_id(db, user_id=current_user.id)
        preferred_categories = onboarding.selected_categories if onboarding and onboarding.selected_categories else []

        # Use recent daily commitment if available
        daily_minutes = onboarding.daily_study_commitment if onboarding and onboarding.daily_study_commitment else 25

        # Cap chunk weeks to [2, 8]
        chunk_weeks = max(2, min(int(chunk_weeks or 4), 8))
        duration_days = chunk_weeks * 7

        ljr = LearningJourneyRequest(
            user_level=current_user.current_level.value,
            preferred_categories=preferred_categories or ["general_english"],
            learning_pace="steady",
            daily_study_time_minutes=daily_minutes,
            assessment_results={},
            journey_duration_days=duration_days,
        )

        result = await content_workflow_service.create_complete_learning_journey(
            db=db,
            sync_db=sync_db,
            user=current_user,
            journey_request=ljr,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to extend learning journey"),
            )

        # Return only the modules for this chunk and the first week's details
        overview = result.get("journey_overview", {})
        modules = overview.get("modules", [])

        return {
            "message": f"Extended journey by {chunk_weeks} weeks.",
            "modules": modules,
            "first_week_content": result.get("first_week_content", {}),
            "user_analysis": result.get("user_analysis"),
        }

    except Exception as e:
        logger.error(f"Error extending learning journey: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to extend learning journey",
        )

@router.post("/skill-series/{skill}")
async def generate_skill_focused_series(
    skill: str,
    series_length: int = 5,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Generate a progressive series focused on improving a specific skill"""
    
    valid_skills = ["vocabulary", "grammar", "reading", "listening", "speaking", "writing"]
    if skill not in valid_skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid skill. Must be one of: {', '.join(valid_skills)}"
        )
    
    try:
        _enforce_trainer_access(sync_db, current_user, module=skill)

        result = await content_workflow_service.generate_skill_focused_content_series(
            db=db,
            sync_db=sync_db,
            user=current_user,
            target_skill=skill,
            series_length=series_length
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate skill series")
            )
        
        return {
            "message": f"Your {skill} improvement series is ready!",
            "series_plan": result["series_plan"],
            "first_session_content": result["first_session_content"]
        }
        
    except Exception as e:
        logger.error(f"Error generating skill series: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate skill-focused series"
        )

@router.post("/weakness-targeted-content")
async def generate_weakness_targeted_content(
    detected_weaknesses: List[str],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Generate content specifically targeting identified weaknesses"""
    try:
        known_modules = {"vocabulary", "grammar", "reading", "listening", "speaking", "writing"}
        weakness_module = next(
            (
                module_name
                for module_name in (_to_module_name(item) for item in (detected_weaknesses or []))
                if module_name in known_modules
            ),
            None,
        )
        _enforce_trainer_access(sync_db, current_user, module=weakness_module)

        result = await content_workflow_service.generate_weakness_targeted_content(
            db=db,
            sync_db=sync_db,
            user=current_user,
            detected_weaknesses=detected_weaknesses
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to generate targeted content")
            )
        
        return {
            "message": "Targeted content generated to address your specific areas for improvement",
            "targeted_content": result["targeted_content"],
            "weaknesses_addressed": result["weaknesses_addressed"],
            "improvement_recommendations": result["recommendations"]
        }
        
    except Exception as e:
        logger.error(f"Error generating weakness-targeted content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate weakness-targeted content"
        )

@router.post("/interactive-lesson")
async def create_interactive_lesson(
    lesson_topic: str,
    lesson_type: str = "comprehensive",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db)
) -> Any:
    """Create an interactive lesson with real-time adaptation capabilities"""
    try:
        _enforce_trainer_access(sync_db, current_user, module=lesson_type)

        result = await content_workflow_service.create_interactive_lesson(
            db=db,
            sync_db=sync_db,
            user=current_user,
            lesson_topic=lesson_topic,
            lesson_type=lesson_type
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to create interactive lesson")
            )
        
        return {
            "message": f"Your interactive lesson about '{lesson_topic}' is ready!",
            "lesson": result["interactive_lesson"]
        }
        
    except Exception as e:
        logger.error(f"Error creating interactive lesson: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create interactive lesson"
        )


# =====================================================
# WEEKLY PLAN ENDPOINTS - New week-based learning system
# =====================================================

@router.post("/weekly-plan/create")
async def create_weekly_plan(
    journey_request: LearningJourneyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """
    Create initial Week 1 plan after assessment.
    Returns plan structure immediately, content generates in background.
    User sees no wait time for AI content generation.
    """
    try:
        _enforce_trainer_access(sync_db, current_user)

        result = await content_workflow_service.create_initial_week_plan(
            db=db,
            user=current_user,
            journey_request=journey_request
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to create weekly plan")
            )
        
        return {
            "message": "Week 1 plan created! Content is being prepared in the background.",
            "week_number": result["week_number"],
            "plan_id": result.get("plan_id"),
            "plan": result["plan"],
            "modules": result.get("modules", []),
            "status": result["status"],
            "days_ready": result.get("days_ready", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating weekly plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create weekly plan"
        )


@router.get("/weekly-plan/{week_number}")
async def get_weekly_plan(
    week_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get a weekly plan from database.
    Returns immediately from cache - no AI wait time.
    """
    try:
        result = await content_workflow_service.get_weekly_plan(
            db=db,
            user_id=current_user.id,
            week_number=week_number
        )
        
        if not result.get("success"):
            if result.get("status") == "not_found":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Week {week_number} plan not found"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get weekly plan")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weekly plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get weekly plan"
        )


@router.get("/weekly-plan/{week_number}/status")
async def get_weekly_plan_status(
    week_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Check generation status for a weekly plan.
    Use this to poll if content is ready.
    """
    try:
        result = await content_workflow_service.get_weekly_plan_status(
            db=db,
            user_id=current_user.id,
            week_number=week_number
        )
        return result
        
    except Exception as e:
        logger.error(f"Error getting plan status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get plan status"
        )


@router.get("/weekly-plan/{week_number}/day/{day_number}")
async def get_day_content(
    week_number: int,
    day_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db),
) -> Any:
    """
    Get content for a specific day.
    Returns from cache if ready, generates on-demand as fallback.
    """
    if day_number < 1 or day_number > 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Day number must be between 1 and 7"
        )
    
    try:
        _enforce_trainer_access(sync_db, current_user)

        result = await content_workflow_service.get_day_content(
            db=db,
            user=current_user,
            week_number=week_number,
            day_number=day_number
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get day content")
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting day content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get day content"
        )


@router.post("/weekly-plan/day-complete")
async def complete_day(
    week_number: int,
    day_number: int,
    results: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Record day completion with performance results.
    Triggers next week generation when day >= 5.
    """
    if day_number < 1 or day_number > 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Day number must be between 1 and 7"
        )
    
    try:
        result = await content_workflow_service.complete_day(
            db=db,
            user_id=current_user.id,
            week_number=week_number,
            day_number=day_number,
            results=results
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to record day completion")
            )
        
        return {
            "message": result["message"],
            "week_number": result["week_number"],
            "day_number": result["day_number"],
            "next_week_triggered": result["next_week_triggered"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing day: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record day completion"
        )


@router.get("/weekly-progress")
async def get_weekly_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get user's overall weekly progress.
    Shows current week, day, skill scores, and areas to focus.
    """
    try:
        progress = await user_weekly_progress_crud.get_or_create(
            db, user_id=current_user.id
        )
        
        # Get current week plan
        current_plan = await weekly_learning_plan_crud.get_by_user_and_week(
            db, user_id=current_user.id, week_number=progress.current_week_number
        )
        
        return {
            "current_week_number": progress.current_week_number,
            "current_day_in_week": progress.current_day_in_week,
            "total_weeks_completed": progress.total_weeks_completed,
            "total_days_completed": progress.total_days_completed,
            "skill_scores": progress.skill_scores or {},
            "weak_areas": progress.weak_areas or [],
            "strong_areas": progress.strong_areas or [],
            "current_week_status": current_plan.status if current_plan else "not_started",
            "last_activity": progress.last_day_completed_at.isoformat() if progress.last_day_completed_at else None
        }
        
    except Exception as e:
        logger.error(f"Error getting weekly progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get weekly progress"
        )


@router.post("/weekly-plan/{plan_id}/retry")
async def retry_failed_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Retry generation for a failed weekly plan.
    """
    try:
        # Verify plan belongs to user
        plan = await weekly_learning_plan_crud.get(db, id=plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan not found"
            )
        if plan.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to retry this plan"
            )
        if plan.status != "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Plan status is {plan.status}, can only retry failed plans"
            )
        
        # Queue retry task
        retry_failed_generation.delay(plan_id=plan_id)
        
        return {
            "message": "Retry triggered for plan generation",
            "plan_id": plan_id,
            "week_number": plan.week_number
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry plan generation"
        )


@router.get("/weekly-plan/all")
async def get_all_weekly_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get all weekly plans for the user.
    """
    try:
        plans = await weekly_learning_plan_crud.get_all_by_user(
            db, user_id=current_user.id
        )
        
        return {
            "total_weeks": len(plans),
            "weeks": [
                {
                    "week_number": p.week_number,
                    "status": p.status,
                    "days_ready": list(p.days_content_ready or []),
                    "days_completed": p.days_completed,
                    "current_day": p.current_day
                }
                for p in plans
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting all plans: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get weekly plans"
        )
