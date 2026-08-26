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
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
ai_service = AIService()

# The values the bound writing assessor accepts. Mirrored from the vendor's
# v9 writing endpoint; sending anything else returns error_invalid_parameters.
ALLOWED_TASK_TYPES = {"chat-writing", "essay-writing", "short-writing"}

# The dialects this product examines in. `dialect` is exam data in exactly
# the same way `task_type` is: the exam definition already declares
# `language` and `locale`, and until 2026-08-27 the service ignored both and
# sent en-us for every call in every language. That is why the fr-fr against
# fr-ca question had never been measurable — nothing could ask it.
#
# The list is the four the product needs, not the vendor's full catalogue,
# because a value nobody has tested is not a value worth accepting.
ALLOWED_DIALECTS = {"en-us", "en-gb", "fr-fr", "fr-ca"}

# ...but the WRITING scorer serves only the English two.
#
# Measured against the vendor on 2026-08-27: fr-fr and fr-ca both come back
#
#   {"status": "error", "short_message": "error_feature_unavailable",
#    "detail_message": "The requested feature is not available in fr-ca dialect."}
#
# Without this list a French exam definition sends fr-ca, the vendor refuses,
# the endpoint correctly declines to substitute a judge, and the platform
# gateway replaces the 503 body with its own page — so the caller gets an
# opaque 504 and no reason. Rejecting it here turns that into a 422 that says
# what is actually wrong, and puts the finding where the next person to bind
# a French judge will see it.
#
# The SPEECH endpoint does accept fr-fr and fr-ca. This limit is the writing
# scorer's, not the vendor's.
WRITING_DIALECTS = {"en-us", "en-gb"}

# The vendor's own limit, quoted from its rejection:
#   "answer length 58799 should be between 1 and 4096"
MAX_ANSWER_CHARS = 4096

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
    task_type: str = Body(default="short-writing"),
    dialect: str = Body(default="en-us"),
    report_band: Optional[bool] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Directly assess a piece of writing and return detailed feedback.

    `prompt` is the original task the user was given (e.g. "Write a cover
    letter for a software engineer position"). When supplied, the AI grades
    Task Achievement against the prompt instead of giving generic feedback.

    `task_type` says what kind of writing this is, and the assessor marks
    against a different expectation for each. It is exam data: a 150-word
    IELTS General Training Task 1 letter is short-writing, a 250-word Task 2
    is essay-writing. Until 2026-08-25 it was fixed at short-writing inside
    the service, so every task in every exam was marked as the same kind of
    writing regardless of what the exam definition said it was. The default
    is kept for the learning app, whose free-practice screens have no exam
    definition to read it from.
    """
    # Two requirements of the bound judge, checked here rather than paid for
    # with a round trip. Both were discovered on 2026-08-25 by reading its
    # rejections in the production log once failures stopped being swallowed:
    #
    #   prompt parameter has invalid value ''
    #   answer length 58799 should be between 1 and 4096
    #
    # The first one matters more than it looks. This assessor scores a
    # response AGAINST A TASK — task achievement is one of its four criteria
    # — so it refuses a submission with no task. Every call this app has ever
    # made without a prompt was rejected by the vendor, and the rejection was
    # then covered up: first by a fall-through to a differently-scaled judge,
    # then by a fixed 70. Free-practice screens that let a user write with no
    # prompt have therefore never produced a real score. They now get a clear
    # 422 saying what is missing, instead of a number that was never earned.
    #
    # 422 rather than 503 on purpose: this is the caller's request being
    # incomplete, not the judge being down. It is also the only status whose
    # body survives — the platform gateway replaces 5xx bodies with its own
    # error page, so a 503's detail never reaches the client.
    if not (prompt or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "A task is required. This assessor scores the response against the task it was set, and one of its four criteria is task achievement.",
                "field": "prompt",
            },
        )

    if len(text) > MAX_ANSWER_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "The response is longer than the judge accepts.",
                "field": "text",
                "characters": len(text),
                "maximum": MAX_ANSWER_CHARS,
            },
        )

    if dialect not in ALLOWED_DIALECTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Unknown dialect.",
                "given": dialect,
                "allowed": sorted(ALLOWED_DIALECTS),
            },
        )

    if dialect not in WRITING_DIALECTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "This judge does not assess writing in that dialect.",
                "given": dialect,
                "served": sorted(WRITING_DIALECTS),
                "vendor_says": "error_feature_unavailable — the requested feature "
                               "is not available in that dialect",
                "note": "The speech endpoint does accept fr-fr and fr-ca. "
                        "No written-French scorer is bound yet.",
            },
        )

    # There is no IELTS band for French.
    #
    # The band scale belongs to one English examination. Emitting it for a
    # French script is not an approximation, it is a category error — and on
    # a French page it would be read as a real number by exactly the
    # candidate least able to know it is meaningless. TCF reports 0-20 and
    # converts to NCLC; TEF reports /450.
    #
    # The caller may state it outright; when it does not, the language of
    # the dialect decides, because the band scale exists only for English.
    band_wanted = report_band if report_band is not None else dialect.startswith("en")

    if task_type not in ALLOWED_TASK_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Unknown task_type.",
                "given": task_type,
                "allowed": sorted(ALLOWED_TASK_TYPES),
            },
        )

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
                task_type=task_type,
                dialect=dialect,
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

            raw = {
                "overall": _f(sa_score, "overall"),
                "grammar": _f(sa_score, "grammar"),
                "vocabulary": _f(sa_score, "vocab"),
                "coherence": _f(sa_score, "coherence"),
                # The writing endpoint calls this `task_response`;
                # `relevance` is the speech endpoint's name for it.
                "task_achievement": _f(sa_score, "task_response") or _f(sa_score, "relevance"),
            }

            # A response with correct grammar that answers the wrong
            # question does not have zero grammar.
            #
            # The judge returns 0 on every criterion, and CEFR A0, when it
            # decides the response does not address the task. Passing that
            # through as `grammar: 0` made a genuine off-topic answer
            # indistinguishable from a bug that sent the wrong prompt, and
            # zero grammar is not something an examiner awards for an
            # off-topic script.
            #
            # So it is reported as a VERDICT, not as scores, and the criteria
            # are null rather than zero: the judge did not measure them.
            # Whether a response addressed the task is the deterministic
            # gate's decision — `GateRule.off_topic` in the exam definitions
            # is where it is made. This endpoint only stops lying about it.
            markable = any((v or 0) > 0 for v in raw.values())

            assessment = {
                "markable": markable,
                "scores": raw if markable else {k: None for k in raw},
                "cefr": cefr or None,
                "feedback": ts.get("feedback_text") or (
                    "Detailed scores from SpeechAce. Review the highlights below."
                    if markable else
                    "This response was not marked: it does not address the task it was "
                    "set. That is a verdict about the task, not a measurement of the "
                    "language."
                ),
                "strengths": ts.get("strengths") or [],
                "weaknesses": ts.get("weaknesses") or [],
                "errors": ts.get("errors") or [],
                "vocabulary_suggestions": ts.get("vocabulary_suggestions") or [],
                "suggestions": ts.get("suggestions") or [],
                "next_steps": [],
                "corrected_version": ts.get("corrected_text"),
                "recommended_exercises": [],
            }

            # The band block is emitted only for an exam that reports bands,
            # and only for a response the judge actually marked. A band of
            # 0.0 on an unmarked script is the same lie as a grammar of 0.
            if band_wanted and markable:
                assessment["ielts_band"] = _f(ielts, "overall")
                assessment["ielts_bands"] = {
                    "task_response": _f(ielts, "task_response"),
                    "vocab": _f(ielts, "vocab"),
                    "coherence": _f(ielts, "coherence"),
                    "grammar": _f(ielts, "grammar"),
                }

            return {
                "success": True,
                "assessment": assessment,
                "metadata": {
                    "word_count": len(text.split()),
                    "character_count": len(text),
                    "writing_type": writing_type,
                    "user_level": level,
                    "task_type": task_type,
                    "dialect": dialect,
                    "reports_band": bool(band_wanted),
                    "markable": markable,
                    "scorer": "speechace_premium",
                },
            }

        # No fallback judge. Deliberately.
        #
        # Until 2026-08-25 this endpoint fell through to a Gemini assessor
        # when SpeechAce failed, and then to a fixed 70/70/70/70
        # "assessment" when Gemini failed too. Both were returned as
        # success: true, on a different scale from the primary judge, with
        # nothing in the response to say which judge had answered.
        #
        # That substitution is how the inverted ranking measured in step 03
        # survived for months: the numbers on screen never stopped
        # arriving, they only stopped meaning anything.
        #
        # A scoring product may return a score or an error. It may not
        # return a different judge's number, or an invented one, under the
        # first judge's name. If a second judge is ever added it will be
        # named in the response and combined explicitly, not swapped in
        # when the first one is quiet.
        reason = sa_resp.get("error") or "writing judge returned no usable score"
        logger.error("writing judge failed; no substitution made: %s", reason)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "The writing judge is unavailable. No score was produced.",
                "judge": "speechace_premium",
                "reason": reason if isinstance(reason, str) else str(reason)[:300],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("writing assessment failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "The writing judge is unavailable. No score was produced.",
                "reason": str(e)[:300],
            },
        )

# Helper functions
async def _assess_writing_submission(db: AsyncSession, submission) -> dict:
    """Assess a writing submission using AI and grammar rules"""
    try:
        # Get AI assessment
        ai_result = await ai_service.assess_writing(submission.content)
        
        if ai_result.get('success'):
            assessment = ai_result.get('content', {})
            
            # No defaults. A missing criterion used to become 70, which is
            # a mark nobody awarded, written to the submission record and
            # indistinguishable afterwards from one the judge did award.
            required = (
                'overall_score', 'grammar_score', 'vocabulary_score',
                'coherence_score', 'task_achievement_score',
            )
            missing = [k for k in required if assessment.get(k) is None]
            if missing:
                logger.error(
                    "submission %s: judge omitted %s",
                    getattr(submission, "id", "?"), ", ".join(missing),
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The writing judge returned an incomplete assessment. The submission was not scored.",
                )
            overall_score = float(assessment['overall_score'])
            grammar_score = float(assessment['grammar_score'])
            vocabulary_score = float(assessment['vocabulary_score'])
            coherence_score = float(assessment['coherence_score'])
            task_achievement_score = float(assessment['task_achievement_score'])
            
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
        logger.error("submission %s: judge returned no assessment", getattr(submission, "id", "?"))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The writing judge is unavailable. The submission was not scored.",
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("submission %s: judge failed", getattr(submission, "id", "?"))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The writing judge is unavailable. The submission was not scored.",
        )

# _fallback_assessment was removed on 2026-08-25.
#
# It produced a score from word count alone — 70, plus 10 at 100 words,
# plus 10 more at 200 — and that number was written to the submission
# record as the user's assessment whenever the judge errored. A grader
# that reads only length is exactly the failure this project is trying
# to rule out, and it was sitting in the error path of the real one.
#
# There is no replacement. A submission that cannot be judged is not
# scored, and the caller is told so.


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
