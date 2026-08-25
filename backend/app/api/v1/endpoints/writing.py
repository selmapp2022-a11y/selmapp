from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.content import DifficultyLevel
from app.models.writing import WritingType, WritingSkillLevel
from app.crud.writing import (
    writing_prompt, writing_submission, writing_feedback, 
    writing_template, writing_progress, grammar_rule
)
from app.schemas.writing import (
    WritingPromptResponse, WritingPromptCreate, WritingPromptUpdate,
    WritingSubmissionResponse, WritingSubmissionCreate, WritingSubmissionUpdate, 
    WritingSubmissionSubmit, WritingSubmissionWithFeedback,
    WritingFeedbackResponse, WritingFeedbackCreate,
    WritingTemplateResponse, WritingTemplateCreate, WritingTemplateUpdate,
    WritingProgressResponse, WritingProgressUpdate,
    GrammarRuleResponse, GrammarRuleCreate, GrammarRuleUpdate,
    WritingPromptPractice, WritingAssessmentRequest, WritingAssessmentResponse,
    WritingSessionStart, WritingSessionSave, WritingSessionResponse,
    WritingStatistics, WritingAnalytics, WritingDashboard
)
from app.services.ai_service import AIService
from datetime import datetime, timedelta
import json

router = APIRouter()
ai_service = AIService()

# Writing Prompt Endpoints
@router.get("/prompts/", response_model=List[WritingPromptResponse])
async def get_writing_prompts(
    level: Optional[DifficultyLevel] = None,
    writing_type: Optional[WritingType] = None,
    skill_level: Optional[WritingSkillLevel] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get writing prompts with optional filtering"""
    if level and writing_type:
        prompts = await writing_prompt.get_by_level_and_type(
            db, level=level, writing_type=writing_type, skill_level=skill_level,
            skip=skip, limit=limit
        )
    elif level:
        prompts = await writing_prompt.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    elif writing_type:
        prompts = await writing_prompt.get_by_type(
            db, writing_type=writing_type, skip=skip, limit=limit
        )
    elif skill_level:
        prompts = await writing_prompt.get_by_skill_level(
            db, skill_level=skill_level, skip=skip, limit=limit
        )
    else:
        prompts = await writing_prompt.get_multi(db, skip=skip, limit=limit)
    
    return prompts

@router.get("/prompts/search", response_model=List[WritingPromptResponse])
async def search_writing_prompts(
    query: str = Query(..., min_length=2),
    level: Optional[DifficultyLevel] = None,
    writing_type: Optional[WritingType] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Search writing prompts by title, prompt text, or topic"""
    prompts = await writing_prompt.search_prompts(
        db, query=query, level=level, writing_type=writing_type, skip=skip, limit=limit
    )
    return prompts

@router.get("/prompts/random", response_model=List[WritingPromptResponse])
async def get_random_writing_prompts(
    level: Optional[DifficultyLevel] = None,
    writing_type: Optional[WritingType] = None,
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get random writing prompts for practice"""
    prompts = await writing_prompt.get_random_prompts(
        db, level=level, writing_type=writing_type, limit=limit
    )
    return prompts

@router.get("/prompts/{prompt_id}", response_model=WritingPromptResponse)
async def get_writing_prompt(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get specific writing prompt"""
    prompt = await writing_prompt.get(db, id=prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found"
        )
    
    if not prompt.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not available"
        )
    
    return prompt

@router.post("/prompts/{prompt_id}/start", response_model=WritingSessionResponse)
async def start_writing_session(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Start a writing session"""
    prompt = await writing_prompt.get(db, id=prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found"
        )
    
    # Get relevant templates
    templates = await writing_template.get_by_type_and_level(
        db, writing_type=prompt.writing_type, level=prompt.difficulty_level
    )
    
    return WritingSessionResponse(
        writing_prompt=WritingPromptPractice(
            id=prompt.id,
            title=prompt.title,
            prompt_text=prompt.prompt_text,
            instructions=prompt.instructions,
            writing_type=prompt.writing_type,
            min_words=prompt.min_words,
            max_words=prompt.max_words,
            time_limit_minutes=prompt.time_limit_minutes,
            required_vocabulary=prompt.required_vocabulary or [],
            grammar_focus=prompt.grammar_focus or []
        ),
        templates=templates,
        session_started_at=datetime.utcnow()
    )

# Writing Submission Endpoints
@router.get("/submissions/", response_model=List[WritingSubmissionResponse])
async def get_writing_submissions(
    prompt_id: Optional[int] = None,
    include_drafts: bool = Query(default=False),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's writing submissions"""
    if prompt_id:
        submissions = await writing_submission.get_prompt_submissions(
            db, user_id=current_user.id, writing_prompt_id=prompt_id
        )
    else:
        submissions = await writing_submission.get_user_submissions(
            db, user_id=current_user.id, skip=skip, limit=limit
        )
    
    # Filter drafts if not requested
    if not include_drafts:
        submissions = [s for s in submissions if not s.is_draft]
    
    return submissions

@router.get("/submissions/drafts", response_model=List[WritingSubmissionResponse])
async def get_writing_drafts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's draft submissions"""
    drafts = await writing_submission.get_drafts(db, user_id=current_user.id)
    return drafts

@router.get("/submissions/{submission_id}", response_model=WritingSubmissionWithFeedback)
async def get_writing_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get specific writing submission with feedback"""
    submission = await writing_submission.get_with_feedback(db, id=submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing submission not found"
        )
    
    # Verify ownership
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this submission"
        )
    
    return submission

@router.post("/submissions/", response_model=WritingSubmissionResponse)
async def create_writing_submission(
    submission_data: WritingSubmissionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new writing submission (save draft)"""
    # Verify prompt exists
    prompt = await writing_prompt.get(db, id=submission_data.writing_prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing prompt not found"
        )
    
    # Add user_id to submission data
    submission_data.user_id = current_user.id
    submission = await writing_submission.create(db, obj_in=submission_data)
    return submission

@router.put("/submissions/{submission_id}", response_model=WritingSubmissionResponse)
async def update_writing_submission(
    submission_id: int,
    submission_data: WritingSubmissionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Update a writing submission"""
    submission = await writing_submission.get(db, id=submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing submission not found"
        )
    
    # Verify ownership
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this submission"
        )
    
    updated_submission = await writing_submission.update(
        db, db_obj=submission, obj_in=submission_data
    )
    return updated_submission

@router.post("/submissions/{submission_id}/submit", response_model=WritingAssessmentResponse)
async def submit_writing_for_assessment(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Submit writing for final assessment"""
    submission = await writing_submission.get(db, id=submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing submission not found"
        )
    
    # Verify ownership
    if submission.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit this writing"
        )
    
    # Mark as submitted (not draft)
    submission.is_draft = False
    submission.submitted_at = datetime.utcnow()
    
    # Perform AI assessment
    assessment_result = await _assess_writing_submission(db, submission)
    
    # Update submission with assessment results
    submission.overall_score = assessment_result['overall_score']
    submission.grammar_score = assessment_result['grammar_score']
    submission.vocabulary_score = assessment_result['vocabulary_score']
    submission.coherence_score = assessment_result['coherence_score']
    submission.task_achievement_score = assessment_result['task_achievement_score']
    submission.ai_feedback = assessment_result['ai_feedback']
    submission.suggestions = assessment_result['suggestions']
    submission.strengths = assessment_result['strengths']
    submission.weaknesses = assessment_result['weaknesses']
    submission.is_evaluated = True
    
    await db.commit()
    await db.refresh(submission)
    
    # Update writing progress
    await writing_progress.update_writing_stats(
        db, user_id=current_user.id, writing_submission=submission
    )
    
    # Create detailed feedback record
    feedback_data = WritingFeedbackCreate(
        writing_submission_id=submission.id,
        content_organization=assessment_result.get('content_organization', 0.0),
        language_accuracy=assessment_result.get('language_accuracy', 0.0),
        vocabulary_range=assessment_result.get('vocabulary_range', 0.0),
        sentence_structure=assessment_result.get('sentence_structure', 0.0),
        punctuation_mechanics=assessment_result.get('punctuation_mechanics', 0.0),
        positive_aspects=assessment_result.get('positive_aspects', []),
        areas_for_improvement=assessment_result.get('areas_for_improvement', []),
        specific_errors=assessment_result.get('specific_errors', []),
        vocabulary_suggestions=assessment_result.get('vocabulary_suggestions', []),
        next_steps=assessment_result.get('next_steps', []),
        recommended_exercises=assessment_result.get('recommended_exercises', [])
    )
    
    feedback = await writing_feedback.create(db, obj_in=feedback_data)
    
    return WritingAssessmentResponse(
        submission=submission,
        feedback=feedback,
        assessment_complete=True
    )

# Writing Progress and Statistics
@router.get("/statistics/", response_model=WritingStatistics)
async def get_writing_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's writing statistics"""
    stats = await writing_submission.get_user_stats(db, user_id=current_user.id)
    
    # Get progress data
    progress = await writing_progress.get_by_user(db, user_id=current_user.id)
    
    return WritingStatistics(
        total_submissions=stats['total_submissions'],
        total_words_written=stats['total_words_written'],
        total_writing_time_hours=stats['total_time_minutes'] / 60,
        average_score=stats['average_overall_score'],
        best_score=stats['best_score'],
        average_grammar_score=stats['average_grammar_score'],
        average_vocabulary_score=stats['average_vocabulary_score'],
        writing_speed_wpm=progress.writing_speed_wpm if progress else 0.0,
        favorite_writing_types=[],  # Could be calculated from submissions
        writing_streak=progress.current_writing_streak if progress else 0,
        improvement_rate=progress.grammar_improvement_rate if progress else 0.0,
        current_level=progress.current_level if progress else DifficultyLevel.A1
    )

@router.get("/progress/", response_model=WritingProgressResponse)
async def get_writing_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's writing progress"""
    progress = await writing_progress.get_by_user(db, user_id=current_user.id)
    
    if not progress:
        # Create initial progress if doesn't exist
        progress = await writing_progress.create_or_update(
            db, user_id=current_user.id, progress_data={}
        )
    
    return progress

@router.get("/analytics/", response_model=WritingAnalytics)
async def get_writing_analytics(
    days: int = Query(default=30, ge=7, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get detailed writing analytics"""
    # Get recent submissions for analytics
    recent_submissions = await writing_submission.get_recent_submissions(
        db, user_id=current_user.id, days=days
    )
    
    # Process analytics data
    daily_activity = _process_daily_writing_activity(recent_submissions)
    score_trends = _process_score_trends(recent_submissions)
    writing_speed_trends = _process_writing_speed_trends(recent_submissions)
    writing_type_performance = _process_writing_type_performance(recent_submissions)
    error_analysis = _process_error_analysis(recent_submissions)
    
    return WritingAnalytics(
        daily_writing_activity=daily_activity,
        score_trends=score_trends,
        writing_speed_trends=writing_speed_trends,
        writing_type_performance=writing_type_performance,
        error_analysis=error_analysis
    )

@router.get("/dashboard/", response_model=WritingDashboard)
async def get_writing_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get writing dashboard data"""
    # Get current statistics
    stats = await get_writing_statistics(current_user=current_user, db=db)
    
    # Get recent submissions
    recent_submissions = await writing_submission.get_user_submissions(
        db, user_id=current_user.id, skip=0, limit=5
    )
    
    # Get recommended prompts based on user level and progress
    progress = await writing_progress.get_by_user(db, user_id=current_user.id)
    user_level = progress.current_level if progress else DifficultyLevel.A1
    
    recommended_prompts = await writing_prompt.get_by_level(
        db, level=user_level, skip=0, limit=5
    )
    
    return WritingDashboard(
        current_stats=stats,
        recent_submissions=recent_submissions,
        recommended_prompts=recommended_prompts,
        writing_goals=[]  # Could be implemented as a separate feature
    )

# Template Endpoints
@router.get("/templates/", response_model=List[WritingTemplateResponse])
async def get_writing_templates(
    writing_type: Optional[WritingType] = None,
    level: Optional[DifficultyLevel] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get writing templates"""
    if writing_type and level:
        templates = await writing_template.get_by_type_and_level(
            db, writing_type=writing_type, level=level
        )
    elif writing_type:
        templates = await writing_template.get_by_type(db, writing_type=writing_type)
    elif level:
        templates = await writing_template.get_by_level(db, level=level)
    else:
        templates = await writing_template.get_multi(db, skip=0, limit=100)
    
    return templates

@router.get("/templates/{template_id}", response_model=WritingTemplateResponse)
async def get_writing_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get specific writing template"""
    template = await writing_template.get(db, id=template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Writing template not found"
        )
    
    return template

# Grammar Rules
@router.get("/grammar-rules/", response_model=List[GrammarRuleResponse])
async def get_grammar_rules(
    category: Optional[str] = None,
    level: Optional[DifficultyLevel] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get grammar rules"""
    if search:
        rules = await grammar_rule.search_rules(db, query=search)
    else:
        rules = await grammar_rule.get_active_rules(
            db, category=category, level=level
        )
    
    return rules

# Admin endpoints (for content management)
@router.post("/prompts/", response_model=WritingPromptResponse)
async def create_writing_prompt(
    prompt_data: WritingPromptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new writing prompt (admin only)"""
    # Note: In a real application, you'd want to check if user is admin
    prompt = await writing_prompt.create(db, obj_in=prompt_data)
    return prompt

@router.post("/templates/", response_model=WritingTemplateResponse)
async def create_writing_template(
    template_data: WritingTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new writing template (admin only)"""
    template = await writing_template.create(db, obj_in=template_data)
    return template

@router.post("/grammar-rules/", response_model=GrammarRuleResponse)
async def create_grammar_rule(
    rule_data: GrammarRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new grammar rule (admin only)"""
    rule = await grammar_rule.create(db, obj_in=rule_data)
    return rule


# Direct Writing Assessment Endpoint (without creating a submission)
@router.post("/assess")
async def assess_writing_direct(
    text: str = Body(..., embed=True, min_length=10),
    writing_type: str = Body(default="general"),
    user_level: str = Body(default=None),
    prompt: str = Body(default=""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Directly assess a piece of writing and return detailed feedback.

    `prompt` is the original task the user was given (e.g. "Write a cover
    letter for a software engineer position"). When supplied, the AI grades
    Task Achievement against the prompt instead of giving generic feedback.
    """
    try:
        # Use user's level if not provided
        level = user_level or (current_user.current_level.value if current_user.current_level else "B1")

        # Try SpeechAce Score Writing first — it's the same Premium account
        # we use for pronunciation, but the writing endpoint returns
        # IELTS/CEFR-aligned grammar+vocab+coherence+task scores. Fall back
        # to Gemini if SpeechAce is unreachable or returns no usable data.
        try:
            from app.services.speechace_premium_service import SpeechAcePremiumService
            sa_resp = await SpeechAcePremiumService().score_writing(
                text=text,
                question_prompt=prompt or None,
                user_id=str(current_user.id),
            )
        except Exception:
            sa_resp = {"success": False}

        if sa_resp.get("success"):
            sa_data = sa_resp.get("data") or {}
            # The writing endpoint answers under `writing_score`, not
            # `text_score` — verified against the live v9 API 2026-08-25.
            # `text_score` is the speech endpoint's envelope, so this read
            # returned {} even on the rare occasion the call succeeded.
            ws = sa_data.get("writing_score") or {}
            ts = sa_data.get("text_score") or {}
            sa_score = ws.get("speechace") or ts.get("speechace_score") or {}
            ielts = ws.get("ielts") or ts.get("ielts_score") or {}
            cefr = ws.get("cefr") or {}

            def _f(d, k):
                v = d.get(k) if isinstance(d, dict) else None
                try:
                    return float(v) if v is not None else None
                except Exception:
                    return None

            # Map SpeechAce 0-100 scale into the same fields the UI expects.
            return {
                "success": True,
                "assessment": {
                    "scores": {
                        "overall": int(_f(sa_score, "overall") or 0),
                        "grammar": int(_f(sa_score, "grammar") or 0),
                        "vocabulary": int(_f(sa_score, "vocab") or 0),
                        "coherence": int(_f(sa_score, "coherence") or 0),
                        # The writing endpoint calls this `task_response`;
                        # `relevance` is the speech endpoint's name for it.
                        "task_achievement": int(
                            _f(sa_score, "task_response") or _f(sa_score, "relevance") or 0
                        ),
                    },
                    "ielts_band": _f(ielts, "overall"),
                    "ielts_bands": {
                        "task_response": _f(ielts, "task_response"),
                        "vocab": _f(ielts, "vocab"),
                        "coherence": _f(ielts, "coherence"),
                        "grammar": _f(ielts, "grammar"),
                    },
                    "cefr": cefr or None,
                    "feedback": ts.get("feedback_text") or "Detailed scores from SpeechAce. Review the highlights below.",
                    "strengths": ts.get("strengths") or [],
                    "weaknesses": ts.get("weaknesses") or [],
                    "errors": ts.get("errors") or [],
                    "vocabulary_suggestions": ts.get("vocabulary_suggestions") or [],
                    "suggestions": ts.get("suggestions") or [],
                    "next_steps": [],
                    "corrected_version": ts.get("corrected_text"),
                    "recommended_exercises": [],
                },
                "metadata": {
                    "word_count": len(text.split()),
                    "character_count": len(text),
                    "writing_type": writing_type,
                    "user_level": level,
                    "scorer": "speechace_premium",
                },
            }

        # Fallback: Gemini-based assessment (the previous default).
        ai_result = await ai_service.assess_writing(
            text=text,
            writing_type=writing_type,
            user_level=level,
            task_prompt=prompt,
        )
        
        if ai_result.get('success'):
            assessment = ai_result.get('content', {})
            
            return {
                "success": True,
                "assessment": {
                    "scores": {
                        "overall": assessment.get('overall_score', 70),
                        "grammar": assessment.get('grammar_score', 70),
                        "vocabulary": assessment.get('vocabulary_score', 70),
                        "coherence": assessment.get('coherence_score', 70),
                        "task_achievement": assessment.get('task_achievement_score', 70)
                    },
                    "feedback": assessment.get('feedback', 'Good effort! Keep practicing.'),
                    "strengths": assessment.get('strengths', []),
                    "weaknesses": assessment.get('weaknesses', []),
                    "errors": assessment.get('errors', []),
                    "vocabulary_suggestions": assessment.get('vocabulary_suggestions', []),
                    "suggestions": assessment.get('suggestions', []),
                    "next_steps": assessment.get('next_steps', []),
                    "corrected_version": assessment.get('corrected_version'),
                    "recommended_exercises": assessment.get('recommended_exercises', [])
                },
                "metadata": {
                    "word_count": len(text.split()),
                    "character_count": len(text),
                    "writing_type": writing_type,
                    "user_level": level
                }
            }
        else:
            # Fallback response
            return {
                "success": True,
                "assessment": {
                    "scores": {
                        "overall": 70,
                        "grammar": 70,
                        "vocabulary": 70,
                        "coherence": 70,
                        "task_achievement": 70
                    },
                    "feedback": "Your writing shows good effort. Continue practicing to improve your skills.",
                    "strengths": ["Good attempt at expressing ideas"],
                    "weaknesses": [],
                    "errors": [],
                    "vocabulary_suggestions": [],
                    "suggestions": [
                        "Keep practicing writing regularly",
                        "Read more English content to improve vocabulary"
                    ],
                    "next_steps": ["Practice writing daily"],
                    "corrected_version": None,
                    "recommended_exercises": []
                },
                "metadata": {
                    "word_count": len(text.split()),
                    "character_count": len(text),
                    "writing_type": writing_type,
                    "user_level": level
                }
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "assessment": {
                "scores": {
                    "overall": 70,
                    "grammar": 70,
                    "vocabulary": 70,
                    "coherence": 70,
                    "task_achievement": 70
                },
                "feedback": "Your writing has been received. Keep practicing!",
                "strengths": [],
                "weaknesses": [],
                "errors": [],
                "vocabulary_suggestions": [],
                "suggestions": ["Continue practicing writing regularly"],
                "next_steps": [],
                "corrected_version": None,
                "recommended_exercises": []
            },
            "metadata": {
                "word_count": len(text.split()),
                "character_count": len(text),
                "writing_type": writing_type,
                "user_level": user_level or "B1"
            }
        }


# Helper functions
async def _assess_writing_submission(db: AsyncSession, submission) -> dict:
    """Assess a writing submission using AI and grammar rules"""
    try:
        # Get AI assessment
        ai_result = await ai_service.assess_writing(submission.content)
        
        if ai_result.get('success'):
            assessment = ai_result.get('content', {})
            
            # Extract scores (with defaults)
            overall_score = float(assessment.get('overall_score', 70.0))
            grammar_score = float(assessment.get('grammar_score', 70.0))
            vocabulary_score = float(assessment.get('vocabulary_score', 70.0))
            coherence_score = float(assessment.get('coherence_score', 70.0))
            task_achievement_score = float(assessment.get('task_achievement_score', 70.0))
            
            return {
                'overall_score': overall_score,
                'grammar_score': grammar_score,
                'vocabulary_score': vocabulary_score,
                'coherence_score': coherence_score,
                'task_achievement_score': task_achievement_score,
                'content_organization': coherence_score,
                'language_accuracy': grammar_score,
                'vocabulary_range': vocabulary_score,
                'sentence_structure': grammar_score,
                'punctuation_mechanics': grammar_score,
                'ai_feedback': assessment.get('feedback', 'Good work!'),
                'suggestions': assessment.get('suggestions', []),
                'strengths': assessment.get('strengths', []),
                'weaknesses': assessment.get('weaknesses', []),
                'positive_aspects': assessment.get('strengths', []),
                'areas_for_improvement': assessment.get('weaknesses', []),
                'specific_errors': assessment.get('errors', []),
                'vocabulary_suggestions': assessment.get('vocabulary_suggestions', []),
                'next_steps': assessment.get('next_steps', []),
                'recommended_exercises': assessment.get('recommended_exercises', [])
            }
        else:
            # Fallback assessment if AI fails
            return _fallback_assessment(submission)
            
    except Exception as e:
        # Fallback assessment if AI service fails
        return _fallback_assessment(submission)

def _fallback_assessment(submission) -> dict:
    """Provide a basic assessment when AI is not available"""
    word_count = submission.word_count
    base_score = 70.0
    
    # Simple scoring based on word count and basic metrics
    if word_count >= 100:
        base_score += 10.0
    if word_count >= 200:
        base_score += 10.0
    
    return {
        'overall_score': min(base_score, 100.0),
        'grammar_score': base_score,
        'vocabulary_score': base_score,
        'coherence_score': base_score,
        'task_achievement_score': base_score,
        'content_organization': base_score,
        'language_accuracy': base_score,
        'vocabulary_range': base_score,
        'sentence_structure': base_score,
        'punctuation_mechanics': base_score,
        'ai_feedback': 'Your writing has been submitted successfully. Keep practicing to improve!',
        'suggestions': ['Continue practicing regularly', 'Focus on grammar and vocabulary'],
        'strengths': ['Good effort', 'Completed the task'],
        'weaknesses': ['Could improve with more practice'],
        'positive_aspects': ['Good effort', 'Completed the task'],
        'areas_for_improvement': ['Grammar', 'Vocabulary', 'Sentence structure'],
        'specific_errors': [],
        'vocabulary_suggestions': [],
        'next_steps': ['Practice more writing exercises', 'Review grammar rules'],
        'recommended_exercises': []
    }

def _process_daily_writing_activity(submissions):
    """Process daily writing activity data"""
    daily_data = {}
    for submission in submissions:
        if submission.submitted_at:
            date_key = submission.submitted_at.date().isoformat()
            if date_key not in daily_data:
                daily_data[date_key] = {
                    "date": date_key,
                    "submissions": 0,
                    "words_written": 0,
                    "time_spent": 0
                }
            daily_data[date_key]["submissions"] += 1
            daily_data[date_key]["words_written"] += submission.word_count
            if submission.time_spent_minutes:
                daily_data[date_key]["time_spent"] += submission.time_spent_minutes
    
    return list(daily_data.values())

def _process_score_trends(submissions):
    """Process score trends over time"""
    return [
        {
            "date": submission.submitted_at.date().isoformat() if submission.submitted_at else "",
            "overall_score": submission.overall_score or 0,
            "grammar_score": submission.grammar_score or 0,
            "vocabulary_score": submission.vocabulary_score or 0
        }
        for submission in submissions
        if submission.is_evaluated and submission.submitted_at
    ]

def _process_writing_speed_trends(submissions):
    """Process writing speed trends"""
    speed_data = []
    for submission in submissions:
        if submission.time_spent_minutes and submission.time_spent_minutes > 0:
            wpm = submission.word_count / submission.time_spent_minutes
            speed_data.append({
                "date": submission.submitted_at.date().isoformat() if submission.submitted_at else "",
                "speed": wpm
            })
    return speed_data

def _process_writing_type_performance(submissions):
    """Process performance by writing type"""
    type_performance = {}
    for submission in submissions:
        if submission.is_evaluated and submission.writing_prompt:
            writing_type = submission.writing_prompt.writing_type.value
            if writing_type not in type_performance:
                type_performance[writing_type] = {
                    "count": 0,
                    "total_score": 0,
                    "average_score": 0
                }
            type_performance[writing_type]["count"] += 1
            type_performance[writing_type]["total_score"] += submission.overall_score or 0
    
    # Calculate averages
    for type_data in type_performance.values():
        if type_data["count"] > 0:
            type_data["average_score"] = type_data["total_score"] / type_data["count"]
    
    return type_performance

def _process_error_analysis(submissions):
    """Process common errors from submissions"""
    error_categories = {}
    for submission in submissions:
        if submission.grammar_errors:
            for error in submission.grammar_errors:
                category = error.get('category', 'other')
                if category not in error_categories:
                    error_categories[category] = 0
                error_categories[category] += 1
    
    return [
        {"category": category, "count": count}
        for category, count in error_categories.items()
    ]
