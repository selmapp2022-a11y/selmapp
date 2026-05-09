import json
import ast
import re
import logging
from typing import Any, List, Dict, Optional, Callable
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

# Configure logger
logger = logging.getLogger(__name__)
from app.api.deps import get_current_user
from app.models.user import User, UserLevel
from app.schemas.user import User as UserSchema, UserUpdate
from app.schemas.auth import (
    LevelAssessmentResponse,
    LevelAssessmentResult,
    LevelAssessmentSubmission,
    LevelAssessmentStartRequest,
    LevelAssessmentJobStatus,
)
from app.crud.user import user_crud
from app.crud.progress import user_progress_crud, user_achievement_crud, daily_progress_crud
from datetime import datetime, date, timedelta, timezone
from app.services.content_access_service import content_access_service
from app.services.ai_service import ai_service
from sqlalchemy.orm import Session
from app.crud.content import content_crud
from app.core.database import get_sync_db, AsyncSessionLocal
from app.crud.assessment_job import assessment_job_crud
from app.models.assessment_job import AssessmentJob
from app.crud.personalization import user_onboarding
from app.models.personalization import OnboardingStep
from uuid import UUID
import asyncio
from app.core.config import settings

router = APIRouter()

@router.get("/profile", response_model=UserSchema)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get current user profile"""
    from app.crud.oauth2 import oauth2_account_crud

    # Load OAuth2 accounts to avoid async serialization issues
    oauth_accounts = await oauth2_account_crud.get_user_oauth_accounts(db, user_id=current_user.id)
    user_dict = current_user.__dict__.copy()
    user_dict["oauth_accounts"] = oauth_accounts
    return user_dict

@router.put("/profile", response_model=UserSchema)
async def update_profile(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update user profile"""
    from app.crud.oauth2 import oauth2_account_crud

    user = await user_crud.update(db, db_obj=current_user, obj_in=user_update)
    # Load OAuth2 accounts to avoid async serialization issues
    oauth_accounts = await oauth2_account_crud.get_user_oauth_accounts(db, user_id=user.id)
    user_dict = user.__dict__.copy()
    user_dict["oauth_accounts"] = oauth_accounts
    return user_dict

@router.get("/profile/statistics", response_model=dict)
async def get_user_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get comprehensive user statistics"""
    
    # Get user progress
    user_progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
    
    # Get achievements count
    achievements = await user_achievement_crud.get_user_achievements(db, user_id=current_user.id)
    
    # Get recent activity (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=29)
    recent_activity = await daily_progress_crud.get_user_progress_range(
        db, user_id=current_user.id, start_date=start_date, end_date=end_date
    )
    
    # Calculate statistics
    total_study_days = len([day for day in recent_activity if day.study_time_minutes > 0])
    total_recent_study_time = sum(day.study_time_minutes for day in recent_activity)
    total_recent_exercises = sum(day.exercises_completed for day in recent_activity)
    total_recent_points = sum(day.points_earned for day in recent_activity)
    
    # Calculate average accuracy from recent activity
    accuracy_sum = sum(day.accuracy_rate for day in recent_activity if day.exercises_completed > 0)
    accuracy_count = len([day for day in recent_activity if day.exercises_completed > 0])
    recent_accuracy = (accuracy_sum / accuracy_count) if accuracy_count > 0 else 0
    
    # Days since registration (handle tz-aware vs naive datetimes safely)
    created_at = current_user.created_at
    if created_at and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    days_since_registration = (now_utc - created_at).days if created_at else 0
    
    statistics = {
        "profile": {
            "user_id": current_user.id,
            "username": current_user.username,
            "current_level": current_user.current_level,
            "is_premium": current_user.is_premium,
            "days_since_registration": days_since_registration,
            "last_login": current_user.last_login
        },
        "overall_progress": {
            "total_study_time_minutes": user_progress.total_study_time_minutes if user_progress else 0,
            "total_exercises_completed": user_progress.total_exercises_completed if user_progress else 0,
            "total_points_earned": user_progress.total_points_earned if user_progress else 0,
            "current_streak_days": user_progress.current_streak_days if user_progress else 0,
            "longest_streak_days": user_progress.longest_streak_days if user_progress else 0,
            "average_accuracy": user_progress.average_accuracy if user_progress else 0,
            "vocabulary_mastered": user_progress.vocabulary_mastered if user_progress else 0,
            "grammar_rules_learned": user_progress.grammar_rules_learned if user_progress else 0,
            "level_progress_percentage": user_progress.level_progress_percentage if user_progress else 0
        },
        "recent_activity_30_days": {
            "total_study_time_minutes": total_recent_study_time,
            "total_exercises_completed": total_recent_exercises,
            "total_points_earned": total_recent_points,
            "study_days": total_study_days,
            "average_accuracy": recent_accuracy,
            "average_study_time_per_day": total_recent_study_time / 30,
            "average_exercises_per_day": total_recent_exercises / 30
        },
        "achievements": {
            "total_earned": len(achievements),
            "recent_achievements": [
                {
                    "name": achievement.achievement.name,
                    "description": achievement.achievement.description,
                    "earned_at": achievement.earned_at,
                    "points_reward": achievement.achievement.points_reward
                }
                for achievement in achievements[:5]  # Last 5 achievements
            ]
        },
        "learning_preferences": {
            "daily_goal_minutes": current_user.daily_goal_minutes,
            "preferred_study_time": current_user.preferred_study_time,
            "notification_enabled": current_user.notification_enabled,
            "native_language": current_user.native_language,
            "target_language": current_user.target_language
        }
    }
    
    return statistics

@router.put("/preferences", response_model=UserSchema)
async def update_learning_preferences(
    daily_goal_minutes: int = None,
    preferred_study_time: str = None,
    notification_enabled: bool = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update user's learning preferences"""
    update_data = {}
    
    if daily_goal_minutes is not None:
        if daily_goal_minutes < 5 or daily_goal_minutes > 300:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily goal must be between 5 and 300 minutes"
            )
        update_data["daily_goal_minutes"] = daily_goal_minutes
    
    if preferred_study_time is not None:
        if preferred_study_time not in ["morning", "afternoon", "evening", "night"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid study time preference"
            )
        update_data["preferred_study_time"] = preferred_study_time
    
    if notification_enabled is not None:
        update_data["notification_enabled"] = notification_enabled
    
    if update_data:
        user = await user_crud.update(db, db_obj=current_user, obj_in=update_data)
        return user
    
    return current_user

@router.get("/test-auth")
async def test_authentication(
    current_user: User = Depends(get_current_user)
) -> dict:
    """Test endpoint to verify authentication is working"""
    return {
        "message": "Authentication successful",
        "user_id": current_user.id,
        "user_email": current_user.email,
        "user_active": current_user.is_active
    }

@router.post("/level-assessment", response_model=LevelAssessmentResponse)
async def take_level_assessment(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Generate AI-powered level assessment quiz for the user (synchronous)."""
    try:
        response = await _generate_assessment_quiz_shared(
            user_id=current_user.id,
            question_count=20,
        )
        return response
    except Exception as e:
        logger.debug(f"Error generating level assessment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate level assessment"
        )


# ===================== Async Assessment Job Flow =====================

async def _process_assessment_job(job_id: UUID, user_id: int):
    """Process assessment job in background with TTS audio generation for listening questions."""
    logger.info(f"🚀 Starting assessment job processing: job_id={job_id}, user_id={user_id}")
    
    # Global timeout for the entire job processing (3 minutes)
    JOB_TIMEOUT_SECONDS = 180
    
    async def _do_process():
        async with AsyncSessionLocal() as session:
            job = await assessment_job_crud.get(session, id=job_id)
            if not job or job.user_id != user_id:
                logger.warning(f"Assessment job not found or user mismatch: job_id={job_id}")
                return
            try:
                # Update progress: Starting AI generation
                logger.info(f"📝 Updating job status to processing: {job_id}")
                await assessment_job_crud.update_status(
                    session, db_obj=job, status="processing", 
                    progress=10, message="Connecting to AI service..."
                )
                
                # Update progress: AI is generating questions
                await assessment_job_crud.update_status(
                    session, db_obj=job, status="processing", 
                    progress=25, message="AI is generating personalized questions..."
                )
                
                logger.info(f"🤖 Calling AI service for job {job_id}")
                response = await _generate_assessment_quiz_shared(
                    user_id=user_id, 
                    question_count=job.question_count,
                    progress_callback=lambda p, m: _update_job_progress_sync(session, job, p, m)
                )
                
                quiz_data = response.get("quiz_data") or {}
                
                # Log quiz data summary
                questions = quiz_data.get("questions", [])
                listening_with_audio = [q for q in questions if q.get("skill", "").lower() == "listening" and q.get("audio_url")]
                logger.info(f"✅ Assessment generated: {len(questions)} questions, {len(listening_with_audio)} listening with audio")
                
                if not questions:
                    logger.warning(f"⚠️ No questions generated for job {job_id}")
                
                # Update progress: Finalizing
                await assessment_job_crud.update_status(
                    session, db_obj=job, status="processing", 
                    progress=95, message="Finalizing assessment..."
                )
                
                await assessment_job_crud.set_result(session, db_obj=job, result=quiz_data)
                logger.info(f"✅ Assessment job completed: job_id={job_id}")
            except Exception as e:
                logger.error(f"❌ Assessment job failed: job_id={job_id}, error={e}", exc_info=True)
                await assessment_job_crud.set_error(session, db_obj=job, error=str(e))
    
    try:
        await asyncio.wait_for(_do_process(), timeout=JOB_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.error(f"❌ Assessment job timed out after {JOB_TIMEOUT_SECONDS}s: job_id={job_id}")
        try:
            async with AsyncSessionLocal() as session:
                job = await assessment_job_crud.get(session, id=job_id)
                if job and job.status in ["pending", "processing"]:
                    await assessment_job_crud.set_error(
                        session, db_obj=job, 
                        error=f"Assessment generation timed out after {JOB_TIMEOUT_SECONDS} seconds"
                    )
        except Exception as e:
            logger.error(f"Failed to set timeout error for job {job_id}: {e}")
    except Exception as outer_e:
        logger.error(f"❌ Critical error in assessment job processing: job_id={job_id}, error={outer_e}", exc_info=True)


async def _update_job_progress_sync(session: AsyncSession, job: AssessmentJob, progress: int, message: str):
    """Helper to update job progress during generation."""
    try:
        await assessment_job_crud.update_status(
            session, db_obj=job, status="processing", 
            progress=progress, message=message
        )
    except Exception as e:
        logger.warning(f"Failed to update job progress: {e}")


@router.post("/level-assessment/start", response_model=Dict[str, Any])
async def start_level_assessment(
    request: LevelAssessmentStartRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validate
    qcount = request.question_count or 20
    qcount = max(5, min(qcount, 30))

    # Idempotency: return existing in-flight job if present (stale jobs are auto-cleaned)
    existing = await assessment_job_crud.get_in_flight_for_user(db, user_id=current_user.id)
    if existing:
        logger.info(f"Returning existing assessment job: {existing.id}, status={existing.status}, progress={existing.progress}")
        return {"job_id": str(existing.id), "status": existing.status, "progress": existing.progress, "message": existing.message}

    # Create new job
    job = await assessment_job_crud.create_job(
        db,
        user_id=current_user.id,
        question_count=qcount,
        user_preferences=request.user_preferences or [],
        personalized=bool(request.personalized) if request.personalized is not None else True,
    )
    logger.info(f"Created new assessment job: {job.id} for user {current_user.id}")

    background_tasks.add_task(_process_assessment_job, job.id, current_user.id)
    return {"job_id": str(job.id), "status": job.status, "progress": job.progress, "message": job.message}


@router.get("/level-assessment/job/{job_id}", response_model=LevelAssessmentJobStatus)
async def get_level_assessment_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = await assessment_job_crud.get_by_id_for_user(db, job_id=job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    resp = {
        "job_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
    }
    if job.status == "completed" and job.result:
        resp["quiz_data"] = job.result
    if job.status == "failed" and job.error:
        resp["error"] = job.error
    return resp


@router.delete("/level-assessment/job/{job_id}")
async def cancel_level_assessment_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel an in-flight assessment job."""
    job = await assessment_job_crud.cancel_job(db, job_id=job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    return {"job_id": str(job.id), "status": job.status, "message": "Job cancelled"}


def _clean_json_string(json_str: str) -> str:
    """Clean and fix common JSON formatting issues from AI responses"""
    # Remove trailing commas before closing brackets/braces
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    # Fix malformed arrays in strings (like "lively", "acrimonious", "heated" , "robust")
    json_str = re.sub(r'"([^"]*)",\s*"([^"]*)",\s*"([^"]*)"\s*,\s*"([^"]*)"',
                     r'["\1", "\2", "\3", "\4"]', json_str)

    # Fix boolean values that might be malformed (true/false without quotes)
    json_str = re.sub(r'"correct_answer":\s*(true|false)\s*,',
                     lambda m: f'"correct_answer": "{m.group(1).lower()}",', json_str)

    # Remove inline comments (// comments)
    json_str = re.sub(r'\s*//.*?(?=,|\n|\}|\])', '', json_str)

    # Remove any remaining syntax issues
    json_str = json_str.replace('  //Example, could be other sophisticated pairings', '')
    json_str = json_str.replace('  //This answer needs to be adjusted based on the content of the paragraph inserted here.', '')
    json_str = json_str.replace('  //Replace with correct answer based on inserted passage', '')
    json_str = json_str.replace('  //Replace with correct answer based on audio', '')

    # Fix missing options for fill_in_blank questions
    json_str = re.sub(r'("question_type": "fill_in_blank",)\s*"question": ([^,]+),\s*"correct_answer"',
                     r'\1\n      "options": [],\n      "question": \2,\n      "correct_answer"', json_str)

    return json_str


def _normalize_correct_answer(correct_answer: str) -> str:
    """Normalize the correct_answer field to be a string"""
    if isinstance(correct_answer, bool):
        return "true" if correct_answer else "false"
    elif isinstance(correct_answer, list):
        return str(correct_answer[0]) if correct_answer else ""
    elif isinstance(correct_answer, str):
        # Clean up any remaining formatting issues
        correct_answer = correct_answer.strip()
        # Remove quotes if they exist at start and end
        if correct_answer.startswith('"') and correct_answer.endswith('"'):
            correct_answer = correct_answer[1:-1]
        return correct_answer
    else:
        return str(correct_answer)


def _clean_json_string(json_str: str) -> str:
    """Clean and fix common JSON formatting issues from AI responses"""
    # Remove trailing commas before closing brackets/braces
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    # Fix malformed arrays in strings (like "lively", "acrimonious", "heated" , "robust")
    json_str = re.sub(r'"([^"]*)",\s*"([^"]*)",\s*"([^"]*)"\s*,\s*"([^"]*)"',
                     r'["\1", "\2", "\3", "\4"]', json_str)

    # Fix boolean values that might be malformed (true/false without quotes)
    json_str = re.sub(r'"correct_answer":\s*(true|false)\s*,',
                     lambda m: f'"correct_answer": "{m.group(1).lower()}",', json_str)

    # Remove inline comments (// comments)
    json_str = re.sub(r'\s*//.*?(?=,|\n|\}|\])', '', json_str)

    # Remove any remaining syntax issues
    json_str = json_str.replace('  //Example, could be other sophisticated pairings', '')
    json_str = json_str.replace('  //This answer needs to be adjusted based on the content of the paragraph inserted here.', '')
    json_str = json_str.replace('  //Replace with correct answer based on inserted passage', '')
    json_str = json_str.replace('  //Replace with correct answer based on audio', '')

    # Fix missing options for fill_in_blank questions
    json_str = re.sub(r'("question_type": "fill_in_blank",)\s*"question": ([^,]+),\s*"correct_answer"',
                     r'\1\n      "options": [],\n      "question": \2,\n      "correct_answer"', json_str)

    return json_str


def _normalize_correct_answer(correct_answer) -> str:
    """Normalize the correct_answer field to be a string"""
    if isinstance(correct_answer, bool):
        return "true" if correct_answer else "false"
    elif isinstance(correct_answer, list):
        return str(correct_answer[0]) if correct_answer else ""
    elif isinstance(correct_answer, str):
        # Clean up any remaining formatting issues
        correct_answer = correct_answer.strip()
        # Remove quotes if they exist at start and end
        if correct_answer.startswith('"') and correct_answer.endswith('"'):
            correct_answer = correct_answer[1:-1]
        return correct_answer
    else:
        return str(correct_answer)


# ===================== Shared Assessment Generation =====================
async def _generate_assessment_quiz_shared(
    user_id: int, 
    question_count: int = 20,
    progress_callback: Optional[Callable[[int, str], Any]] = None
) -> Dict[str, Any]:
    """Generate a high-quality assessment quiz using AI with robust parsing and 20+ questions fallback.

    Returns a dict with keys: quiz_data, assessment_id, message
    
    Args:
        user_id: The user ID for the assessment
        question_count: Number of questions to generate
        progress_callback: Optional async callback for progress updates (progress%, message)
    """
    async def update_progress(progress: int, message: str):
        if progress_callback:
            try:
                result = progress_callback(progress, message)
                if hasattr(result, '__await__'):
                    await result
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
    
    try:
        await update_progress(30, "AI is generating personalized questions...")
        
        ai_result = await ai_service.generate_level_assessment_quiz(
            target_level=None,
            question_count=question_count,
        )
        
        await update_progress(50, "Processing AI response...")

        if ai_result.get("success"):
            content = ai_result.get("content", "").strip()
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            json_str = json_match.group(1) if json_match else content

            cleaned_json = _clean_json_string(json_str)
            ai_data = json.loads(cleaned_json)
            
            await update_progress(60, "Formatting questions...")

            questions = ai_data.get("questions", [])
            quiz_metadata = ai_data.get("quiz_metadata", {})

            formatted_questions: list[dict] = []
            for q in questions:
                options = q.get("options", [])
                if isinstance(options, list):
                    if len(options) == 1 and isinstance(options[0], list):
                        options = options[0]
                    elif len(options) == 1 and isinstance(options[0], str) and options[0].strip().startswith('[') and options[0].strip().endswith(']'):
                        array_str = options[0]
                        parsed: list[str] = []
                        try:
                            maybe_list = ast.literal_eval(array_str)
                            if isinstance(maybe_list, list):
                                parsed = [str(o) for o in maybe_list if o is not None]
                        except Exception:
                            try:
                                jsonish = array_str.replace("'", '"')
                                maybe_list = json.loads(jsonish)
                                if isinstance(maybe_list, list):
                                    parsed = [str(o) for o in maybe_list if o is not None]
                            except Exception:
                                inner = array_str.strip()[1:-1]
                                parsed = [seg.strip().strip("'\"") for seg in inner.split(',') if seg.strip()]
                        options = parsed
                    else:
                        options = [str(opt) for opt in options if opt is not None]
                else:
                    options = []

                points = q.get("points", 1)
                if isinstance(points, float):
                    points = int(points)
                elif not isinstance(points, int):
                    points = 1

                formatted_q = {
                    "id": q.get("id", len(formatted_questions) + 1),
                    "skill": q.get("skill", "vocabulary"),
                    "difficulty_level": q.get("difficulty_level", "A1"),
                    "question_type": q.get("question_type", "multiple_choice"),
                    "question": q.get("question", ""),
                    "options": options,
                    "correct_answer": _normalize_correct_answer(q.get("correct_answer", "")),
                    "explanation": q.get("explanation", ""),
                    "points": points,
                }
                if q.get("passage"):
                    formatted_q["passage"] = q.get("passage")
                if q.get("audio_url"):
                    formatted_q["audio_url"] = q.get("audio_url")
                if q.get("audio_text"):
                    formatted_q["audio_text"] = q.get("audio_text")
                formatted_questions.append(formatted_q)

            # Enrich listening questions with Gemini TTS audio
            # Generate audio for listening questions that don't have audio_url
            # This is best-effort - assessment will proceed even if TTS fails
            await update_progress(70, "Generating audio for listening questions...")
            
            async def _enrich_with_tts():
                """Helper function to enrich listening questions with TTS audio (with timeout)"""
                from app.services.gemini_tts_service import get_tts_service
                tts_service = await get_tts_service()
                
                # Count listening questions for logging
                listening_questions = [q for q in formatted_questions if q.get("skill", "").lower() == "listening" and not q.get("audio_url")]
                logger.info(f"Found {len(listening_questions)} listening questions to enrich with TTS")
                
                # Limit TTS generation to avoid timeout (max 2 questions with 12s timeout each)
                MAX_TTS_QUESTIONS = 2
                TTS_TIMEOUT_SECONDS = 12
                tts_generated = 0
                
                for q in formatted_questions:
                    skill = q.get("skill", "").lower()
                    
                    # For listening questions without audio_url, generate TTS (up to limit)
                    if skill == "listening" and not q.get("audio_url") and tts_generated < MAX_TTS_QUESTIONS:
                        # Use audio_text if available, otherwise create from question context
                        audio_text = q.get("audio_text")
                        if not audio_text:
                            # Create a listening script from the question context
                            question_text = q.get("question", "")
                            correct = q.get("correct_answer", "")
                            
                            # Generate a short listening passage based on the question
                            audio_text = f"Listen carefully. {question_text}"
                            if correct:
                                audio_text = f"Listen to the following: The answer is {correct}. Now, {question_text}"
                            
                            q["audio_text"] = audio_text
                            logger.info(f"Created audio_text for listening question {q.get('id')}: {audio_text[:50]}...")
                        
                        logger.info(f"Generating TTS audio for listening question {q.get('id')} ({tts_generated + 1}/{MAX_TTS_QUESTIONS})")
                        try:
                            # Add timeout to prevent hanging
                            tts = await asyncio.wait_for(
                                tts_service.generate_audio_content(
                                    text=str(audio_text),
                                    audio_type="assessment_listening",
                                    speaker_config=[{"name": "Narrator", "voice_name": getattr(settings, "GEMINI_TTS_VOICE", "Kore")}]
                                ),
                                timeout=TTS_TIMEOUT_SECONDS
                            )
                            if tts.get("success") and tts.get("audio_url"):
                                q["audio_url"] = tts["audio_url"]
                                tts_generated += 1
                                logger.info(f"TTS audio generated successfully: {tts['audio_url']}")
                            else:
                                logger.warning(f"TTS generation failed for question {q.get('id')}: {tts.get('error', 'Unknown error')}")
                        except asyncio.TimeoutError:
                            logger.warning(f"TTS generation timed out for question {q.get('id')} after {TTS_TIMEOUT_SECONDS}s")
                        except Exception as tts_err:
                            logger.error(f"TTS generation error for question {q.get('id')}: {tts_err}")
                
                logger.info(f"TTS enrichment complete: {tts_generated} audio files generated")
            
            try:
                # Global timeout for entire TTS enrichment process (30 seconds max)
                await asyncio.wait_for(_enrich_with_tts(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("TTS enrichment timed out after 30s - proceeding without all audio")
            except Exception as e:
                # Best-effort enrichment; log error and continue without blocking
                logger.error(f"TTS enrichment failed: {e}", exc_info=True)

            if not formatted_questions:
                formatted_questions = _build_fallback_questions(max(question_count, 20))

            await update_progress(90, "Finalizing assessment...")
            
            quiz_data = {
                "quiz_metadata": {
                    "title": quiz_metadata.get("title", "English Level Assessment"),
                    "description": quiz_metadata.get("description", "Determine your English proficiency level"),
                    "total_questions": len(formatted_questions),
                    "estimated_duration_minutes": quiz_metadata.get("estimated_duration_minutes", 30.0),
                    "created_at": datetime.now().isoformat(),
                    "user_id": user_id,
                },
                "questions": formatted_questions,
            }

            return {
                "quiz_data": quiz_data,
                "assessment_id": f"assessment_{user_id}_{int(datetime.now().timestamp())}",
                "message": "AI-generated level assessment quiz ready. Complete all questions to determine your CEFR level.",
            }

        # AI call failed → fallback
        return {
            "quiz_data": {
                "quiz_metadata": {
                    "title": "English Level Assessment",
                    "description": "Determine your English proficiency level",
                    "total_questions": max(question_count, 20),
                    "estimated_duration_minutes": max(question_count, 20) * 2,
                    "created_at": datetime.now().isoformat(),
                    "user_id": user_id,
                },
                "questions": _build_fallback_questions(max(question_count, 20)),
            },
            "assessment_id": f"assessment_{user_id}_{int(datetime.now().timestamp())}",
            "message": "Fallback assessment generated.",
        }
    except Exception:
        # Any parsing/runtime error → robust fallback
        return {
            "quiz_data": {
                "quiz_metadata": {
                    "title": "English Level Assessment",
                    "description": "Determine your English proficiency level",
                    "total_questions": max(question_count, 20),
                    "estimated_duration_minutes": max(question_count, 20) * 2,
                    "created_at": datetime.now().isoformat(),
                    "user_id": user_id,
                },
                "questions": _build_fallback_questions(max(question_count, 20)),
            },
            "assessment_id": f"assessment_{user_id}_{int(datetime.now().timestamp())}",
            "message": "Fallback assessment generated.",
        }


def _build_fallback_questions(count: int) -> list[dict]:
    """Build a balanced set of fallback questions across skills and levels."""
    skills_cycle = ["grammar", "vocabulary", "reading", "listening"]
    levels_cycle = ["A1", "A2", "B1", "B2"]
    questions: list[dict] = []
    for i in range(count):
        skill = skills_cycle[i % len(skills_cycle)]
        level = levels_cycle[i % len(levels_cycle)]
        qid = i + 1
        if skill == "grammar":
            qtext = "Choose the correct form: 'He ____ to work yesterday.'"
            opts = ["go", "went", "gone", "going"]
            correct = "1"
        elif skill == "vocabulary":
            qtext = "Select the best synonym for 'happy'."
            opts = ["sad", "joyful", "angry", "tired"]
            correct = "1"
        elif skill == "reading":
            qtext = "According to the passage, what time does the store open?"
            opts = ["8 AM", "9 AM", "10 AM", "11 AM"]
            correct = "1"
        else:  # listening
            qtext = "What is the main topic of the audio?"
            opts = ["travel", "food", "sports", "music"]
            correct = "0"
        questions.append({
            "id": qid,
            "skill": skill,
            "difficulty_level": level,
            "question_type": "multiple_choice",
            "question": qtext,
            "options": opts,
            "correct_answer": correct,
            "explanation": "",
            "points": 1,
        })
    return questions

@router.post("/level-assessment/submit", response_model=LevelAssessmentResult)
async def submit_level_assessment(
    submission: LevelAssessmentSubmission,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Submit level assessment results and update user level using AI analysis."""

    try:
        # Aggregate base metrics
        total_questions = len(submission.answers)
        correct_answers = sum(1 for answer in submission.answers if answer.get("is_correct", False))
        overall_score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0.0
        heuristic_skills = {
            "grammar": round(overall_score * 0.9, 2),
            "vocabulary": round(min(overall_score * 1.1, 100.0), 2),
            "reading": round(overall_score * 0.95, 2),
            "listening": round(overall_score * 0.85, 2)
        }

        # Call AI for refined analysis (best-effort)
        ai_summary = await ai_service.analyze_assessment_results(
            answers=submission.answers,
            heuristic_overall_score=overall_score,
            heuristic_skill_scores=heuristic_skills,
        )

        determined_level = None
        final_overall = overall_score
        final_skills = heuristic_skills
        feedback = None
        recommendations_ai: list[str] = []
        if ai_summary.get("success"):
            determined_level = str(ai_summary.get("determined_level", "B1"))
            final_overall = float(ai_summary.get("overall_score", overall_score))
            final_skills = ai_summary.get("skill_scores", heuristic_skills) or heuristic_skills
            feedback = ai_summary.get("feedback")
            recommendations_ai = ai_summary.get("recommendations") or []

        # Persist level change if any
        old_level_str = current_user.current_level.value if isinstance(current_user.current_level, UserLevel) else str(current_user.current_level)
        try:
            assessed_level_enum = UserLevel(determined_level or old_level_str or "A1")
        except Exception:
            assessed_level_enum = UserLevel.A1

        level_changed = assessed_level_enum != current_user.current_level
        if level_changed:
            await user_crud.update(db, db_obj=current_user, obj_in={"current_level": assessed_level_enum})

        # Tailored recommendations (merge AI + level-based)
        base_recs = await _generate_level_based_recommendations(assessed_level_enum, final_skills)
        merged_recs = (recommendations_ai or []) + [r for r in base_recs if r not in (recommendations_ai or [])]

        message = (
            f"You answered {correct_answers} out of {total_questions}. "
            f"Assessed CEFR level: {assessed_level_enum.value}. "
            f"{'Level updated.' if level_changed else 'Level unchanged.'} "
        )
        if feedback:
            message += f" Feedback: {feedback}"

        # Persist assessment results into onboarding for robust resume + AI personalization.
        # This powers `/users/assessment-results` and ensures the app doesn't force users
        # to repeat the assessment after restart.
        try:
            assessment_details = {
                "determined_level": assessed_level_enum.value,
                "overall_score": round(float(final_overall), 2),
                "skill_scores": final_skills,
                "feedback": feedback,
                "recommendations": merged_recs,
                "total_questions": total_questions,
                "correct_answers": correct_answers,
                "completed_at": datetime.utcnow().isoformat(),
            }
            await user_onboarding.update_step(
                db,
                user_id=current_user.id,
                step=OnboardingStep.LEVEL_ASSESSMENT.value,
                step_data={
                    "assessed_level": assessed_level_enum.value,
                    "assessment_score": round(float(final_overall), 2),
                    "assessment_details": assessment_details,
                },
            )
        except Exception as persist_err:
            logger.warning(
                "Failed to persist assessment results to onboarding: user_id=%s err=%s",
                current_user.id,
                persist_err,
            )

        return {
            "old_level": old_level_str,
            "new_level": assessed_level_enum.value,
            "score": round(final_overall, 2),
            "level_changed": level_changed,
            "skill_breakdown": final_skills,
            "recommendations": merged_recs,
            "message": message,
        }

    except Exception as e:
        logger.debug(f"Error processing level assessment submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process assessment results"
        )

@router.get("/dashboard", response_model=dict)
async def get_user_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user dashboard with personalized content"""
    
    # Get user progress
    user_progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
    
    # Get today's progress
    today = date.today()
    today_progress = await daily_progress_crud.get_by_user_and_date(
        db, user_id=current_user.id, date=today
    )
    
    # Calculate daily goal progress
    daily_goal_progress = 0
    if today_progress:
        daily_goal_progress = min(
            (today_progress.study_time_minutes / current_user.daily_goal_minutes) * 100,
            100
        )
    
    # Get recent achievements
    achievements = await user_achievement_crud.get_user_achievements(db, user_id=current_user.id)
    recent_achievements = achievements[:3]  # Last 3 achievements
    
    # Get week progress
    week_start = today - timedelta(days=today.weekday())
    week_progress = await daily_progress_crud.get_user_progress_range(
        db, user_id=current_user.id, start_date=week_start, end_date=today
    )
    
    week_study_time = sum(day.study_time_minutes for day in week_progress)
    week_exercises = sum(day.exercises_completed for day in week_progress)
    
    dashboard = {
        "user_info": {
            "username": current_user.username,
            "current_level": current_user.current_level,
            "is_premium": current_user.is_premium
        },
        "daily_progress": {
            "goal_minutes": current_user.daily_goal_minutes,
            "completed_minutes": today_progress.study_time_minutes if today_progress else 0,
            "progress_percentage": daily_goal_progress,
            "exercises_completed": today_progress.exercises_completed if today_progress else 0,
            "points_earned": today_progress.points_earned if today_progress else 0,
            "goal_met": daily_goal_progress >= 100
        },
        "overall_stats": {
            "current_streak": user_progress.current_streak_days if user_progress else 0,
            "longest_streak": user_progress.longest_streak_days if user_progress else 0,
            "total_study_time": user_progress.total_study_time_minutes if user_progress else 0,
            "total_exercises": user_progress.total_exercises_completed if user_progress else 0,
            "total_points": user_progress.total_points_earned if user_progress else 0,
            "level_progress": user_progress.level_progress_percentage if user_progress else 0,
            "vocabulary_mastered": user_progress.vocabulary_mastered if user_progress else 0
        },
        "week_summary": {
            "total_study_time": week_study_time,
            "total_exercises": week_exercises,
            "days_studied": len([day for day in week_progress if day.study_time_minutes > 0])
        },
        "recent_achievements": [
            {
                "name": achievement.achievement.name,
                "description": achievement.achievement.description,
                "icon_url": achievement.achievement.icon_url,
                "earned_at": achievement.earned_at
            }
            for achievement in recent_achievements
        ],
        "recommendations": _get_personalized_recommendations(current_user, user_progress)
    }
    
    return dashboard


@router.get("/assessment-results", response_model=dict)
async def get_assessment_results(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Return the latest assessment results for the current user from onboarding data.

    Shape: { "results": { "determined_level": str, "overall_score": float, "skill_scores": dict, "feedback": str|null, "recommendations": list } }
    """
    try:
        onboarding = await user_onboarding.get_by_user_id(db, user_id=current_user.id)
        if not onboarding:
            return {"results": {}}

        details = onboarding.assessment_details or {}
        results = {
            "determined_level": (onboarding.assessed_level or (current_user.current_level.value if hasattr(current_user.current_level, 'value') else str(current_user.current_level))) or "A1",
            "overall_score": float(onboarding.assessment_score or details.get("overall_score") or 0.0),
            "skill_scores": details.get("skill_scores", {}),
            "feedback": details.get("feedback"),
            "recommendations": details.get("recommendations", []),
        }
        return {"results": results}
    except Exception as e:
        logger.debug(f"Error fetching assessment results: {e}")
        return {"results": {}}

@router.delete("/account")
async def delete_account(
    confirm_deletion: bool,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Delete user account with proper soft delete.
    
    This implements production-ready account deletion:
    - Anonymizes user email and username (hashes original for audit)
    - Allows the same email to be used for new registration
    - Preserves anonymized data for analytics
    - Compliant with GDPR right to be forgotten
    
    Args:
        confirm_deletion: Must be True to confirm deletion
        
    Returns:
        Success message with deletion confirmation
    """
    if not confirm_deletion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account deletion must be confirmed by setting confirm_deletion=true"
        )
    
    try:
        # Perform soft delete with email hashing
        success = await user_crud.soft_delete(db, user=current_user)
        
        if success:
            logger.info(f"User account soft-deleted: user_id={current_user.id}")
            return {
                "success": True,
                "message": "Your account has been permanently deleted. You can register again with the same email address.",
                "deleted_at": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete account. Please try again."
            )
    except Exception as e:
        logger.error(f"Error deleting account for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting your account. Please contact support."
        )

@router.get("/me/access-summary")
async def get_user_access_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Get user's content access summary"""
    try:
        access_summary = content_access_service.get_user_access_summary(db, current_user)
        return access_summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get access summary: {str(e)}"
        )

@router.get("/me/can-access-content/{content_id}")
async def check_content_access(
    content_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Check if user can access specific content"""
    try:
        # Get content
        content = content_crud.get(db, id=content_id)
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content not found"
            )
        
        can_access, reason = content_access_service.can_access_content(db, current_user, content)
        
        return {
            "can_access": can_access,
            "reason": reason,
            "content_id": content_id,
            "content_title": content.title,
            "content_type": content.content_type,
            "cefr_level": content.cefr_level
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check content access: {str(e)}"
        )

@router.get("/me/can-access-module/{module}")
async def check_module_access(
    module: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Check if user can access specific learning module"""
    try:
        can_access, reason = content_access_service.can_access_module(db, current_user, module)
        
        return {
            "can_access": can_access,
            "reason": reason,
            "module": module
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check module access: {str(e)}"
        )

@router.get("/me/can-access-cefr/{cefr_level}")
async def check_cefr_access(
    cefr_level: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db)
):
    """Check if user can access specific CEFR level"""
    try:
        can_access, reason = content_access_service.can_access_cefr_level(db, current_user, cefr_level)
        
        return {
            "can_access": can_access,
            "reason": reason,
            "cefr_level": cefr_level
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check CEFR access: {str(e)}"
        )

# Helper Functions
def _get_level_recommendations(level: UserLevel) -> List[str]:
    """Get recommendations based on user level"""
    recommendations = {
        UserLevel.A1: [
            "Focus on basic vocabulary and simple sentence structures",
            "Practice common greetings and everyday expressions",
            "Start with present tense verbs"
        ],
        UserLevel.A2: [
            "Expand vocabulary related to family, work, and hobbies",
            "Practice past and future tenses",
            "Work on basic conversations"
        ],
        UserLevel.B1: [
            "Focus on complex sentence structures",
            "Practice expressing opinions and preferences",
            "Work on listening comprehension"
        ],
        UserLevel.B2: [
            "Practice advanced grammar structures",
            "Focus on formal and informal language",
            "Work on reading longer texts"
        ],
        UserLevel.C1: [
            "Master idiomatic expressions",
            "Practice academic and professional English",
            "Focus on nuanced language use"
        ],
        UserLevel.C2: [
            "Perfect native-like fluency",
            "Master all aspects of the language",
            "Focus on specialized vocabulary"
        ]
    }
    
    return recommendations.get(level, [])

def _get_personalized_recommendations(user: User, progress) -> List[str]:
    """Get personalized recommendations based on user progress"""
    recommendations = []
    
    # Check streak
    current_streak = progress.current_streak_days if progress else 0
    if current_streak == 0:
        recommendations.append("Start your learning streak today! Even 10 minutes makes a difference.")
    elif current_streak < 7:
        recommendations.append(f"Great start! Try to reach a 7-day streak. You're at {current_streak} days.")
    elif current_streak < 30:
        recommendations.append(f"Excellent consistency! Aim for a 30-day streak. Current: {current_streak} days.")
    
    # Check daily goal achievement
    if progress and progress.exercises_per_day_average < 5:
        recommendations.append("Try to complete at least 5 exercises per day to maintain steady progress.")
    
    # Check accuracy
    if progress and progress.average_accuracy < 0.7:
        recommendations.append("Focus on understanding before speed. Review incorrect answers to improve accuracy.")
    
    # Level-specific recommendations
    level_recs = _get_level_recommendations(user.current_level)
    recommendations.extend(level_recs[:2])  # Add first 2 level recommendations
    
    return recommendations[:5]  # Return max 5 recommendations

def _calculate_cefr_level_from_scores(
    overall_score: float, 
    level_scores: Dict[str, List[int]], 
    skill_breakdown: Dict[str, float]
) -> UserLevel:
    """Calculate CEFR level based on detailed assessment scores"""
    
    # Weight the scores by level difficulty and performance
    level_weights = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
    weighted_score = 0
    total_weight = 0
    
    for level, scores in level_scores.items():
        if scores:
            level_performance = sum(scores) / len(scores)
            weight = level_weights[level]
            weighted_score += level_performance * weight
            total_weight += weight
    
    if total_weight > 0:
        weighted_average = weighted_score / total_weight
    else:
        weighted_average = overall_score / 100
    
    # Determine level based on weighted performance
    if weighted_average >= 0.9 and overall_score >= 85:
        return UserLevel.C2
    elif weighted_average >= 0.8 and overall_score >= 75:
        return UserLevel.C1
    elif weighted_average >= 0.7 and overall_score >= 65:
        return UserLevel.B2
    elif weighted_average >= 0.6 and overall_score >= 55:
        return UserLevel.B1
    elif weighted_average >= 0.4 and overall_score >= 35:
        return UserLevel.A2
    else:
        return UserLevel.A1

async def _generate_level_based_recommendations(
    level: UserLevel, 
    skill_breakdown: Dict[str, float]
) -> List[str]:
    """Generate recommendations based on assessed level and skill breakdown"""
    recommendations = []
    
    # Level-specific recommendations
    level_recs = {
        UserLevel.A1: [
            "Start with basic vocabulary (family, numbers, colors)",
            "Practice simple present tense sentences",
            "Focus on pronunciation of common words",
            "Learn basic greetings and introductions"
        ],
        UserLevel.A2: [
            "Expand vocabulary to everyday topics (food, shopping, transport)",
            "Practice past and future tenses",
            "Work on basic conversations and questions",
            "Read simple texts and stories"
        ],
        UserLevel.B1: [
            "Learn intermediate grammar (conditionals, passive voice)",
            "Practice expressing opinions and preferences",
            "Read longer articles and stories",
            "Work on listening to native speakers"
        ],
        UserLevel.B2: [
            "Master complex grammar structures",
            "Practice formal and informal registers",
            "Read academic and professional texts",
            "Engage in discussions and debates"
        ],
        UserLevel.C1: [
            "Focus on nuanced vocabulary and idioms",
            "Practice advanced writing skills",
            "Read complex literature and academic papers",
            "Master subtle grammar and style"
        ],
        UserLevel.C2: [
            "Refine near-native fluency",
            "Study specialized vocabulary fields",
            "Practice advanced speaking and presentation skills",
            "Focus on cultural nuances and context"
        ]
    }
    
    recommendations.extend(level_recs.get(level, [])[:2])
    
    # Skill-specific recommendations based on weak areas
    weak_skills = [skill for skill, score in skill_breakdown.items() if score < 60]
    
    for skill in weak_skills[:2]:  # Focus on top 2 weak skills
        if skill == "grammar":
            recommendations.append(f"Focus on {level.value} grammar rules - this is a key area for improvement")
        elif skill == "vocabulary":
            recommendations.append(f"Build your {level.value} vocabulary through daily word practice")
        elif skill == "reading":
            recommendations.append(f"Practice reading {level.value} texts to improve comprehension")
        elif skill == "listening":
            recommendations.append(f"Listen to {level.value} audio content to improve understanding")
    
    return recommendations[:5]

def _get_level_encouragement(level: UserLevel) -> str:
    """Get encouraging message based on assessed level"""
    encouragements = {
        UserLevel.A1: "You're starting your English journey - every expert was once a beginner!",
        UserLevel.A2: "Great progress! You're building a solid foundation in English.",
        UserLevel.B1: "Well done! You can handle everyday English conversations.",
        UserLevel.B2: "Excellent! You have strong intermediate English skills.",
        UserLevel.C1: "Outstanding! You have advanced English proficiency.",
        UserLevel.C2: "Exceptional! You have near-native English mastery."
    }
    return encouragements.get(level, "Keep practicing - you're making great progress!")


# ─────────────────────────────────────────────────────────────────────────────
# Client-side state sync (XP, streak, achievements, recent events)
# ─────────────────────────────────────────────────────────────────────────────
# The web client used to keep progress only in localStorage, so clearing
# the browser cache wiped streaks and XP, and the user got different progress
# on each device. These endpoints persist a small JSON blob per user in
# Redis so the same state appears on phone, desktop, and after a cache clear.

_CLIENT_STATE_KEY = "client_state:user:{user_id}"
_CLIENT_STATE_TTL_SECONDS = 60 * 60 * 24 * 365 * 2  # 2 years (effectively persistent on managed Redis)


@router.get("/me/client-state")
async def get_client_state(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the cross-device client state for the signed-in user."""
    from app.core.cache import get_redis
    redis = await get_redis()
    raw = await redis.get(_CLIENT_STATE_KEY.format(user_id=current_user.id))
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


@router.put("/me/client-state")
async def put_client_state(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Replace the user's cross-device client state with the supplied JSON."""
    from app.core.cache import get_redis
    redis = await get_redis()
    # Cap the payload size so a misbehaving client can't fill Redis.
    encoded = json.dumps(payload)
    if len(encoded) > 256 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="client-state payload exceeds 256KB",
        )
    await redis.set(
        _CLIENT_STATE_KEY.format(user_id=current_user.id),
        encoded,
        ex=_CLIENT_STATE_TTL_SECONDS,
    )
    return {"success": True}
