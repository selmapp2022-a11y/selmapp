"""
Weekly Plan Generation Tasks
Background Celery tasks for generating weekly learning plans and content.
Implements retry mechanism with exponential backoff for AI failures.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from celery import Task

from app.core.celery_app import celery_app
from app.core.database import get_async_session
from app.models.user import User
from app.models.cache import WeeklyLearningPlan
from app.crud.cache import (
    weekly_learning_plan_crud,
    user_weekly_progress_crud,
    day_completion_record_crud,
)

logger = logging.getLogger(__name__)

# Custom exception for AI generation failures
class AIGenerationError(Exception):
    """Raised when AI content generation fails"""
    pass


class AsyncTask(Task):
    """Base task class for async operations"""
    
    def __call__(self, *args, **kwargs):
        """Execute async task in event loop"""
        return asyncio.run(self.run_async(*args, **kwargs))
    
    async def run_async(self, *args, **kwargs):
        """Override this method in subclasses"""
        raise NotImplementedError


@celery_app.task(
    bind=True,
    base=AsyncTask,
    queue="weekly_plan_generation",
    max_retries=3,
    default_retry_delay=30
)
async def generate_week_plan_structure(
    self,
    user_id: int,
    week_number: int,
    user_level: str,
    preferred_categories: List[str],
    daily_study_minutes: int = 30,
    user_progress_snapshot: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate the 7-day plan structure for a week.
    This creates the plan outline quickly without generating actual content.
    
    Args:
        user_id: User ID
        week_number: Week number (1, 2, 3, ...)
        user_level: CEFR level (A1-C2)
        preferred_categories: User's preferred learning categories
        daily_study_minutes: Daily study time commitment
        user_progress_snapshot: Previous week's progress data for adaptation
    
    Returns:
        Dict with plan structure and status
    """
    try:
        async with get_async_session() as db:
            # Check if plan already exists
            existing = await weekly_learning_plan_crud.get_by_user_and_week(
                db, user_id=user_id, week_number=week_number
            )
            
            if existing and existing.status == "ready":
                return {
                    "success": True,
                    "plan_id": existing.id,
                    "status": "already_ready",
                    "message": f"Week {week_number} plan already exists"
                }
            
            # Create or update the plan record
            if not existing:
                plan_record = await weekly_learning_plan_crud.create(
                    db,
                    user_id=user_id,
                    week_number=week_number,
                    user_progress_snapshot=user_progress_snapshot,
                    status="generating"
                )
            else:
                plan_record = await weekly_learning_plan_crud.update_status(
                    db, plan_id=existing.id, status="generating"
                )
            
            # Generate plan structure using AI service
            try:
                from app.services.ai_service import ai_service
                
                # Build prompt for week structure generation
                prompt = _build_week_structure_prompt(
                    week_number=week_number,
                    user_level=user_level,
                    preferred_categories=preferred_categories,
                    daily_study_minutes=daily_study_minutes,
                    progress_data=user_progress_snapshot
                )
                
                result = await ai_service.generate_structured_content(
                    prompt=prompt,
                    content_type="weekly_plan_structure",
                )
                
                if not result.get("success"):
                    raise AIGenerationError(f"AI generation failed: {result.get('error')}")
                
                # Parse and validate plan data
                plan_data = _parse_week_structure(result.get("content"), week_number, daily_study_minutes)
                
                # Update plan record with generated structure
                await weekly_learning_plan_crud.update_plan_data(
                    db, plan_id=plan_record.id, plan_data=plan_data
                )
                
                # Queue content generation for days 1-3 immediately
                generate_days_content.delay(
                    user_id=user_id,
                    week_number=week_number,
                    plan_id=plan_record.id,
                    days=[1, 2, 3],
                    user_level=user_level
                )
                
                return {
                    "success": True,
                    "plan_id": plan_record.id,
                    "week_number": week_number,
                    "status": "structure_ready",
                    "plan_data": plan_data,
                    "message": f"Week {week_number} structure generated, content queued"
                }
                
            except Exception as ai_err:
                logger.error(f"AI generation error for week {week_number}: {ai_err}")
                
                # Use fallback structure
                plan_data = _create_fallback_week_structure(
                    week_number=week_number,
                    user_level=user_level,
                    preferred_categories=preferred_categories,
                    daily_study_minutes=daily_study_minutes
                )
                
                await weekly_learning_plan_crud.update_plan_data(
                    db, plan_id=plan_record.id, plan_data=plan_data
                )
                
                # Still queue content generation
                generate_days_content.delay(
                    user_id=user_id,
                    week_number=week_number,
                    plan_id=plan_record.id,
                    days=[1, 2, 3],
                    user_level=user_level
                )
                
                return {
                    "success": True,
                    "plan_id": plan_record.id,
                    "week_number": week_number,
                    "status": "fallback_structure",
                    "plan_data": plan_data,
                    "message": f"Week {week_number} fallback structure used"
                }
                
    except Exception as e:
        logger.error(f"Week plan generation task error: {e}")
        
        # Retry with exponential backoff
        countdown = 30 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)


@celery_app.task(
    bind=True,
    base=AsyncTask,
    queue="weekly_plan_generation",
    max_retries=3,
    default_retry_delay=60
)
async def generate_days_content(
    self,
    user_id: int,
    week_number: int,
    plan_id: int,
    days: List[int],
    user_level: str
) -> Dict[str, Any]:
    """
    Generate actual content for specific days in a week.
    Called in batches (days 1-3, then 4-7) to distribute AI load.
    
    Args:
        user_id: User ID
        week_number: Week number
        plan_id: WeeklyLearningPlan ID
        days: List of day numbers to generate (e.g., [1, 2, 3])
        user_level: CEFR level
    
    Returns:
        Dict with generation results
    """
    try:
        async with get_async_session() as db:
            # Load user and plan
            user = await db.get(User, user_id)
            if not user:
                return {"success": False, "error": f"User {user_id} not found"}
            
            plan = await weekly_learning_plan_crud.get(db, id=plan_id)
            if not plan:
                return {"success": False, "error": f"Plan {plan_id} not found"}
            
            # Import content workflow service
            from app.services.content_generation_workflow import content_workflow_service
            
            results = {"days_generated": [], "days_failed": []}
            
            for day_num in days:
                try:
                    # Get day's plan from plan_data
                    day_plan = _get_day_plan(plan.plan_data, day_num)
                    
                    # Generate content for each content type in the day
                    for content_type in day_plan.get("content_types", ["vocabulary", "reading", "listening"]):
                        topic = day_plan.get("topic", "daily life")
                        
                        result = await content_workflow_service._generate_single_content_piece(
                            db=db,
                            user=user,
                            content_type=content_type,
                            topic=topic,
                            duration_minutes=day_plan.get("duration_per_type", 10),
                            user_context={
                                "day_number": day_num,
                                "week_number": week_number
                            }
                        )
                        
                        if not result.get("success"):
                            logger.warning(
                                f"Content generation failed for day {day_num}, type {content_type}: "
                                f"{result.get('error')}"
                            )
                    
                    # Mark day content as ready
                    await weekly_learning_plan_crud.mark_day_content_ready(
                        db, plan_id=plan_id, day_number=day_num
                    )
                    results["days_generated"].append(day_num)
                    
                except Exception as day_err:
                    logger.error(f"Error generating day {day_num} content: {day_err}")
                    results["days_failed"].append({"day": day_num, "error": str(day_err)})
            
            # If this was days 1-3, queue days 4-7
            if days == [1, 2, 3]:
                generate_days_content.apply_async(
                    args=[user_id, week_number, plan_id, [4, 5, 6, 7], user_level],
                    countdown=60  # Start 1 minute later to spread load
                )
            
            # Check if all days are now ready
            updated_plan = await weekly_learning_plan_crud.get(db, id=plan_id)
            all_ready = len(updated_plan.days_content_ready or []) >= 7
            
            if all_ready:
                await weekly_learning_plan_crud.update_status(
                    db, plan_id=plan_id, status="ready"
                )
            
            return {
                "success": True,
                "plan_id": plan_id,
                "week_number": week_number,
                "days_generated": results["days_generated"],
                "days_failed": results["days_failed"],
                "all_days_ready": all_ready
            }
            
    except Exception as e:
        logger.error(f"Days content generation task error: {e}")
        
        # Update plan with error
        try:
            async with get_async_session() as db:
                await weekly_learning_plan_crud.increment_attempts(
                    db, plan_id=plan_id, error=str(e)
                )
        except Exception:
            pass
        
        # Retry with exponential backoff
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=e, countdown=countdown)


@celery_app.task(
    bind=True,
    base=AsyncTask,
    queue="weekly_plan_generation"
)
async def check_and_trigger_next_week(
    self,
    user_id: int,
    current_week: int,
    completed_day: int
) -> Dict[str, Any]:
    """
    Check if user has completed day 5 and trigger next week generation.
    Called when a day is completed.
    
    Args:
        user_id: User ID
        current_week: Current week number
        completed_day: Day number just completed (1-7)
    
    Returns:
        Dict with trigger result
    """
    try:
        # Only trigger on day 5 or later
        if completed_day < 5:
            return {
                "success": True,
                "triggered": False,
                "message": f"Day {completed_day} completed, not yet day 5"
            }
        
        async with get_async_session() as db:
            # Check if next week already exists
            next_week = current_week + 1
            existing = await weekly_learning_plan_crud.get_by_user_and_week(
                db, user_id=user_id, week_number=next_week
            )
            
            if existing:
                return {
                    "success": True,
                    "triggered": False,
                    "message": f"Week {next_week} already exists (status: {existing.status})"
                }
            
            # Get user data for next week generation
            user = await db.get(User, user_id)
            if not user:
                return {"success": False, "error": f"User {user_id} not found"}
            
            # Get user's progress data for adaptation
            progress = await user_weekly_progress_crud.get_by_user(db, user_id=user_id)
            recent_records = await day_completion_record_crud.get_week_records(
                db, user_id=user_id, week_number=current_week
            )
            
            # Build progress snapshot
            progress_snapshot = _build_progress_snapshot(progress, recent_records)
            
            # Get user preferences from onboarding
            from app.crud.personalization import user_onboarding
            onboarding = await user_onboarding.get_by_user_id(db, user_id=user_id)
            preferred_categories = onboarding.selected_categories if onboarding else ["general_english"]
            daily_minutes = onboarding.daily_study_commitment if onboarding else 30
            
            # Queue next week generation
            generate_week_plan_structure.delay(
                user_id=user_id,
                week_number=next_week,
                user_level=user.current_level.value,
                preferred_categories=preferred_categories,
                daily_study_minutes=daily_minutes,
                user_progress_snapshot=progress_snapshot
            )
            
            return {
                "success": True,
                "triggered": True,
                "next_week": next_week,
                "message": f"Week {next_week} generation triggered"
            }
            
    except Exception as e:
        logger.error(f"Check and trigger next week error: {e}")
        return {"success": False, "error": str(e)}


@celery_app.task(
    bind=True,
    base=AsyncTask,
    queue="weekly_plan_generation"
)
async def retry_failed_generation(
    self,
    plan_id: int
) -> Dict[str, Any]:
    """
    Retry generation for a failed weekly plan.
    
    Args:
        plan_id: WeeklyLearningPlan ID
    
    Returns:
        Dict with retry result
    """
    try:
        async with get_async_session() as db:
            plan = await weekly_learning_plan_crud.get(db, id=plan_id)
            if not plan:
                return {"success": False, "error": f"Plan {plan_id} not found"}
            
            if plan.status != "failed":
                return {
                    "success": False,
                    "error": f"Plan status is {plan.status}, not failed"
                }
            
            if plan.generation_attempts >= plan.max_attempts:
                return {
                    "success": False,
                    "error": f"Max attempts ({plan.max_attempts}) reached"
                }
            
            # Get user
            user = await db.get(User, plan.user_id)
            if not user:
                return {"success": False, "error": f"User {plan.user_id} not found"}
            
            # Get preferences
            from app.crud.personalization import user_onboarding
            onboarding = await user_onboarding.get_by_user_id(db, user_id=plan.user_id)
            preferred_categories = onboarding.selected_categories if onboarding else ["general_english"]
            daily_minutes = onboarding.daily_study_commitment if onboarding else 30
            
            # Reset status and retry
            await weekly_learning_plan_crud.update_status(
                db, plan_id=plan_id, status="pending"
            )
            
            # Trigger generation
            generate_week_plan_structure.delay(
                user_id=plan.user_id,
                week_number=plan.week_number,
                user_level=user.current_level.value,
                preferred_categories=preferred_categories,
                daily_study_minutes=daily_minutes,
                user_progress_snapshot=plan.user_progress_snapshot
            )
            
            return {
                "success": True,
                "plan_id": plan_id,
                "message": f"Retry triggered for plan {plan_id}"
            }
            
    except Exception as e:
        logger.error(f"Retry failed generation error: {e}")
        return {"success": False, "error": str(e)}


# Helper functions

def _build_week_structure_prompt(
    week_number: int,
    user_level: str,
    preferred_categories: List[str],
    daily_study_minutes: int,
    progress_data: Optional[Dict[str, Any]]
) -> str:
    """Build AI prompt for week structure generation"""
    
    progress_context = ""
    if progress_data:
        weak_areas = progress_data.get("weak_areas", [])
        strong_areas = progress_data.get("strong_areas", [])
        avg_accuracy = progress_data.get("average_accuracy", 0)
        
        progress_context = f"""
        Based on previous week's progress:
        - Areas needing focus: {', '.join(weak_areas) if weak_areas else 'none identified'}
        - Strong areas: {', '.join(strong_areas) if strong_areas else 'none identified'}
        - Average accuracy: {avg_accuracy:.0%}
        """
    
    return f"""
    Create a 7-day English learning plan structure for Week {week_number}.
    
    User Profile:
    - CEFR Level: {user_level}
    - Daily Study Time: {daily_study_minutes} minutes
    - Preferred Categories: {', '.join(preferred_categories)}
    {progress_context}
    
    Generate a structured plan with:
    1. Daily themes that build progressively
    2. Mix of skills (vocabulary, grammar, reading, listening, speaking, writing)
    3. Content aligned with preferred categories
    4. Appropriate difficulty for {user_level} level
    
    Format as JSON:
    {{
        "week_number": {week_number},
        "theme": "Weekly theme description",
        "days": [
            {{
                "day": 1,
                "title": "Day title",
                "topic": "Specific topic",
                "content_types": ["vocabulary", "reading", "listening"],
                "skills_focus": ["skill1", "skill2"],
                "estimated_minutes": {daily_study_minutes},
                "learning_objectives": ["objective1", "objective2"]
            }}
        ]
    }}
    """


def _parse_week_structure(
    ai_content: Any,
    week_number: int,
    daily_minutes: int
) -> Dict[str, Any]:
    """Parse AI-generated week structure"""
    import json
    
    try:
        if isinstance(ai_content, str):
            # Clean markdown code blocks if present
            content = ai_content.strip()
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
        elif isinstance(ai_content, dict):
            data = ai_content
        else:
            raise ValueError(f"Unexpected content type: {type(ai_content)}")
        
        # Validate structure
        if "days" not in data:
            raise ValueError("Missing 'days' in plan structure")
        
        return data
        
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse AI week structure: {e}")
        return _create_fallback_week_structure(
            week_number=week_number,
            user_level="B1",
            preferred_categories=["general_english"],
            daily_study_minutes=daily_minutes
        )


def _create_fallback_week_structure(
    week_number: int,
    user_level: str,
    preferred_categories: List[str],
    daily_study_minutes: int
) -> Dict[str, Any]:
    """Create fallback week structure when AI fails"""
    
    topics = [
        "Daily Routines",
        "Family and Friends",
        "Work and Study",
        "Shopping and Services",
        "Travel and Transport",
        "Health and Wellness",
        "Entertainment and Leisure"
    ]
    
    skills_rotation = [
        ["vocabulary", "reading", "listening"],
        ["grammar", "vocabulary", "speaking"],
        ["reading", "listening", "writing"],
        ["vocabulary", "grammar", "listening"],
        ["speaking", "reading", "vocabulary"],
        ["listening", "writing", "grammar"],
        ["vocabulary", "reading", "speaking"]
    ]
    
    days = []
    for day in range(1, 8):
        day_topic = topics[(day - 1) % len(topics)]
        day_skills = skills_rotation[(day - 1) % len(skills_rotation)]
        
        days.append({
            "day": day,
            "title": f"Day {day}: {day_topic}",
            "topic": day_topic.lower(),
            "content_types": day_skills,
            "skills_focus": day_skills[:2],
            "estimated_minutes": daily_study_minutes,
            "duration_per_type": daily_study_minutes // len(day_skills),
            "learning_objectives": [
                f"Practice {day_skills[0]} related to {day_topic.lower()}",
                f"Improve {day_skills[1]} skills"
            ]
        })
    
    return {
        "week_number": week_number,
        "theme": f"Week {week_number}: Building English Skills",
        "level": user_level,
        "categories": preferred_categories,
        "days": days
    }


def _get_day_plan(plan_data: Dict[str, Any], day_number: int) -> Dict[str, Any]:
    """Extract specific day's plan from week plan data"""
    if not plan_data:
        return {
            "topic": "daily life",
            "content_types": ["vocabulary", "reading", "listening"],
            "duration_per_type": 10
        }
    
    days = plan_data.get("days", [])
    for day in days:
        if day.get("day") == day_number:
            return day
    
    # Fallback
    return {
        "topic": "general topics",
        "content_types": ["vocabulary", "reading", "listening"],
        "duration_per_type": 10
    }


def _build_progress_snapshot(
    progress: Optional[Any],
    recent_records: List[Any]
) -> Dict[str, Any]:
    """Build progress snapshot for next week's plan adaptation"""
    
    snapshot = {
        "weak_areas": [],
        "strong_areas": [],
        "average_accuracy": 0.0,
        "skills_practiced": {},
        "total_time_spent": 0
    }
    
    if progress:
        snapshot["weak_areas"] = list(progress.weak_areas or [])
        snapshot["strong_areas"] = list(progress.strong_areas or [])
        snapshot["skill_scores"] = dict(progress.skill_scores or {})
    
    if recent_records:
        total_correct = sum(r.correct_answers for r in recent_records)
        total_questions = sum(r.total_questions for r in recent_records)
        snapshot["average_accuracy"] = total_correct / total_questions if total_questions > 0 else 0.0
        snapshot["total_time_spent"] = sum(r.time_spent_minutes for r in recent_records)
        
        # Aggregate skill results
        for record in recent_records:
            for skill, results in (record.skill_results or {}).items():
                if skill not in snapshot["skills_practiced"]:
                    snapshot["skills_practiced"][skill] = {"correct": 0, "total": 0}
                snapshot["skills_practiced"][skill]["correct"] += results.get("correct", 0)
                snapshot["skills_practiced"][skill]["total"] += results.get("total", 0)
    
    return snapshot


