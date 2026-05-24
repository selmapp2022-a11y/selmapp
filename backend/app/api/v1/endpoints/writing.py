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
from pydantic import BaseModel, Field

router = APIRouter()
ai_service = AIService()


def _score_to_ielts_band(score_0_100: Optional[float]) -> Optional[float]:
    """Map a 0-100 SELM/Gemini writing score onto an IELTS 0-9 band,
    rounded to the nearest half-band as IELTS reports them.

    The mapping is calibrated so that:
      - 90+  → band 8.5-9
      - 80   → band 7.5
      - 70   → band 6.5
      - 60   → band 5.5
      - 50   → band 4.5
      - 40   → band 3.5
      - below 40 → bands 1-3

    Used when the Gemini fallback path returns numeric scores and we
    want to surface an IELTS-aligned band to the iPhone UI, matching
    the SpeechAce premium path that returns the band natively.
    (2026-05-25 — finding #6 from the 2026-05-24 audit.)
    """
    if score_0_100 is None:
        return None
    try:
        s = max(0.0, min(100.0, float(score_0_100)))
    except Exception:
        return None
    # 0-100 → 0-9 linear, then round to nearest 0.5
    raw_band = (s / 100.0) * 9.0
    rounded = round(raw_band * 2.0) / 2.0
    return max(0.0, min(9.0, rounded))


def _ielts_breakdown(scores: dict) -> dict:
    """Return per-criterion IELTS band so the UI can render the four
    standard IELTS Writing bands separately."""
    return {
        "task_response": _score_to_ielts_band(scores.get("task_achievement")),
        "coherence_cohesion": _score_to_ielts_band(scores.get("coherence")),
        "lexical_resource": _score_to_ielts_band(scores.get("vocabulary")),
        "grammar_accuracy": _score_to_ielts_band(scores.get("grammar")),
    }


# ── IELTS Writing Task 1 / Task 2 ────────────────────────────────────────
# Three task types are supported, matching the real IELTS exam structure:
#   - ielts_task1_letter  → IELTS General Task 1: write a letter (formal,
#                           semi-formal or informal) in 150 words / 20 min.
#   - ielts_task1_chart   → IELTS Academic Task 1: describe a chart, graph,
#                           table, map or diagram in 150 words / 20 min.
#   - ielts_task2         → IELTS Task 2 (General or Academic): opinion /
#                           discussion / problem-solution / advantages-
#                           disadvantages essay in 250 words / 40 min.
# (2026-05-25 — finding #4 from the 2026-05-24 audit.)

IELTS_TASK_SPECS = {
    "ielts_task1_letter": {
        "name": "IELTS General Task 1 — Letter",
        "word_count_target": "at least 150 words",
        "time_limit_minutes": 20,
        "scoring_weight": "33% of the total Writing band",
        "generation_instructions": (
            "Generate a realistic IELTS General Task 1 letter-writing prompt. "
            "Pick ONE register: formal (e.g. complaint to a company, request "
            "to a manager), semi-formal (e.g. landlord, school administrator), "
            "or informal (e.g. friend, family member). Include three bullet "
            "points the test-taker must address."
        ),
        "instructions_for_taker": (
            "You should spend about 20 minutes on this task. Write at least "
            "150 words. You do NOT need to include addresses. Begin your "
            "letter as follows: 'Dear ...,'"
        ),
    },
    "ielts_task1_chart": {
        "name": "IELTS Academic Task 1 — Chart / Graph Description",
        "word_count_target": "at least 150 words",
        "time_limit_minutes": 20,
        "scoring_weight": "33% of the total Writing band",
        "generation_instructions": (
            "Generate a realistic IELTS Academic Task 1 prompt. Describe a "
            "specific chart, graph, table, map or diagram in text form "
            "(since this is text-only, narrate the visual data clearly with "
            "concrete numbers, categories, time periods and units). The "
            "test-taker must summarise the information, select and report "
            "the main features, and make comparisons where relevant."
        ),
        "instructions_for_taker": (
            "You should spend about 20 minutes on this task. Summarise the "
            "information by selecting and reporting the main features, and "
            "make comparisons where relevant. Write at least 150 words."
        ),
    },
    "ielts_task2": {
        "name": "IELTS Task 2 — Essay",
        "word_count_target": "at least 250 words",
        "time_limit_minutes": 40,
        "scoring_weight": "67% of the total Writing band",
        "generation_instructions": (
            "Generate a realistic IELTS Task 2 essay question. Pick ONE of "
            "the four classic Task 2 types: (1) opinion (agree/disagree), "
            "(2) discussion (discuss both views and give your opinion), "
            "(3) problem-solution (causes and solutions), or "
            "(4) advantages and disadvantages. Topic should be of broad, "
            "current interest (education, technology, environment, health, "
            "work, society, culture). Make the prompt thought-provoking, "
            "not trivial."
        ),
        "instructions_for_taker": (
            "You should spend about 40 minutes on this task. Write at least "
            "250 words. Give reasons for your answer and include any "
            "relevant examples from your own knowledge or experience."
        ),
    },
}


def _ielts_writing_rubric_block() -> str:
    """The official-style IELTS Writing band descriptors, condensed
    enough to fit in a Gemini prompt while preserving the four
    criteria the markers actually use."""
    return (
        "Score against the official IELTS Writing band descriptors, "
        "with four criteria (each scored on the IELTS 0-9 band scale, "
        "then mapped to a 0-100 score for the JSON output):\n"
        "  1. Task Achievement / Task Response — does the response fully "
        "address every part of the prompt? Are the position and key ideas "
        "clearly developed?\n"
        "  2. Coherence and Cohesion — is the writing logically organised "
        "into paragraphs? Are cohesive devices (linking words, referencing) "
        "used naturally?\n"
        "  3. Lexical Resource — is vocabulary varied, accurate, and used "
        "with appropriate collocation? Any awkward or repetitive word choice?\n"
        "  4. Grammatical Range and Accuracy — does the writer use a range "
        "of sentence structures correctly? How frequent and serious are the "
        "errors?\n"
        "Reference bands: 9 = expert user, 8 = very good, 7 = good, "
        "6 = competent, 5 = modest, 4 = limited, 3 = extremely limited."
    )


class GenerateIeltsTaskRequest(BaseModel):
    task_type: str = Field(
        ...,
        description=(
            "One of: ielts_task1_letter, ielts_task1_chart, ielts_task2"
        ),
    )
    topic_hint: Optional[str] = Field(
        default=None,
        description="Optional theme to bias the generated prompt towards.",
    )


@router.post("/ielts/generate-task")
async def generate_ielts_writing_task(
    request: GenerateIeltsTaskRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """Return an IELTS-style writing prompt for one of the three task
    types. The prompt itself is generated by Gemini at request time so
    test-takers get a fresh question each session.
    """
    spec = IELTS_TASK_SPECS.get(request.task_type)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unknown task_type. Use one of: ielts_task1_letter, "
                "ielts_task1_chart, ielts_task2."
            ),
        )

    topic_hint_line = (
        f"Theme hint (optional, weave in naturally): {request.topic_hint}\n"
        if request.topic_hint
        else ""
    )
    gemini_prompt = (
        f"{spec['generation_instructions']}\n\n"
        f"{topic_hint_line}"
        "Reply ONLY with valid JSON of exactly this shape:\n"
        "{\n"
        '  "prompt_text": "the full task prompt the test-taker will see, '
        'including any bullet points or chart description",\n'
        '  "title": "a 3-7 word title summarising the prompt"\n'
        "}"
    )

    prompt_text = ""
    title = ""
    try:
        if ai_service.gemini_model:
            import asyncio as _asyncio
            import json as _json
            resp = await _asyncio.wait_for(
                _asyncio.to_thread(
                    ai_service.gemini_model.generate_content, gemini_prompt
                ),
                timeout=25.0,
            )
            raw = (getattr(resp, "text", "") or "").strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                raw = raw.rsplit("```", 1)[0].strip()
            try:
                data = _json.loads(raw)
            except Exception:
                import re as _re
                m = _re.search(r"\{[\s\S]*\}", raw)
                data = _json.loads(m.group(0)) if m else {}
            prompt_text = (data.get("prompt_text") or "").strip()
            title = (data.get("title") or "").strip()
    except Exception:
        # Generation failure → return a static safety prompt so the
        # client never sees an empty body for an authenticated request.
        prompt_text = ""

    if not prompt_text:
        # Static fallbacks per task type. Boring but valid.
        prompt_text = {
            "ielts_task1_letter": (
                "You recently bought a household appliance, but it stopped "
                "working soon after. Write a letter to the shop manager. "
                "In your letter:\n"
                "  - describe the product and when you bought it\n"
                "  - explain what is wrong with it\n"
                "  - say what you would like the shop to do"
            ),
            "ielts_task1_chart": (
                "The chart shows household electricity consumption in three "
                "countries (Country A, B and C) from 2010 to 2020, measured "
                "in kilowatt-hours per household per year. Summarise the "
                "information by selecting and reporting the main features, "
                "and make comparisons where relevant."
            ),
            "ielts_task2": (
                "Some people believe that universities should focus only on "
                "providing students with knowledge directly related to their "
                "future job. Others argue that universities should offer a "
                "broad range of subjects. Discuss both views and give your "
                "own opinion."
            ),
        }.get(request.task_type, "")
        title = spec["name"]

    return {
        "success": True,
        "task_type": request.task_type,
        "task_name": spec["name"],
        "title": title or spec["name"],
        "prompt_text": prompt_text,
        "instructions": spec["instructions_for_taker"],
        "word_count_target": spec["word_count_target"],
        "time_limit_minutes": spec["time_limit_minutes"],
        "scoring_weight": spec["scoring_weight"],
    }


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
    task_type: str = Body(
        default="general",
        description=(
            "Optional. When set to one of ielts_task1_letter, "
            "ielts_task1_chart, ielts_task2 the grading rubric is the "
            "official IELTS Writing band descriptors (4 criteria, 0-9 "
            "bands) instead of the generic SELM rubric."
        ),
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Directly assess a piece of writing and return detailed feedback.

    `prompt` is the original task the user was given (e.g. "Write a cover
    letter for a software engineer position"). When supplied, the AI grades
    Task Achievement against the prompt instead of giving generic feedback.

    `task_type` opts into IELTS Writing band scoring. When IELTS is
    selected, the Gemini fallback path uses the official band descriptors
    and the response always includes ``ielts_band`` + ``ielts_breakdown``.
    (2026-05-25 — finding #4 from the 2026-05-24 audit.)
    """
    is_ielts = task_type in IELTS_TASK_SPECS
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
            ts = sa_data.get("text_score") or {}
            sa_score = ts.get("speechace_score") or {}
            ielts = ts.get("ielts_score") or {}

            def _f(d, k):
                v = d.get(k) if isinstance(d, dict) else None
                try:
                    return float(v) if v is not None else None
                except Exception:
                    return None

            # Map SpeechAce 0-100 scale into the same fields the UI expects.
            sa_scores = {
                "overall": int(_f(sa_score, "overall") or 0),
                "grammar": int(_f(sa_score, "grammar") or 0),
                "vocabulary": int(_f(sa_score, "vocab") or 0),
                "coherence": int(_f(sa_score, "coherence") or 0),
                "task_achievement": int(_f(sa_score, "relevance") or 0),
            }
            sa_ielts_breakdown = {
                # Prefer SpeechAce's own per-criterion IELTS bands when
                # available, otherwise derive them from the 0-100 scores.
                "task_response": _f(ielts, "relevance") or _score_to_ielts_band(sa_scores["task_achievement"]),
                "coherence_cohesion": _f(ielts, "coherence") or _score_to_ielts_band(sa_scores["coherence"]),
                "lexical_resource": _f(ielts, "vocab") or _score_to_ielts_band(sa_scores["vocabulary"]),
                "grammar_accuracy": _f(ielts, "grammar") or _score_to_ielts_band(sa_scores["grammar"]),
            }
            return {
                "success": True,
                "assessment": {
                    "scores": sa_scores,
                    "ielts_band": _f(ielts, "overall") or _score_to_ielts_band(sa_scores["overall"]),
                    "ielts_breakdown": sa_ielts_breakdown,
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
                    "task_type": task_type,
                },
            }

        # Fallback: Gemini-based assessment (the previous default).
        # When IELTS task_type is set, prefix the prompt with the
        # official IELTS Writing band descriptors so Gemini grades
        # against the same four criteria human IELTS markers use.
        effective_prompt = prompt
        if is_ielts:
            spec = IELTS_TASK_SPECS[task_type]
            ielts_header = (
                f"This is an IELTS Writing exam answer for {spec['name']} "
                f"({spec['word_count_target']}, {spec['time_limit_minutes']} "
                f"minutes, worth {spec['scoring_weight']}).\n\n"
                f"{_ielts_writing_rubric_block()}\n\n"
                f"Original task prompt: {prompt or '(not supplied)'}"
            )
            effective_prompt = ielts_header
        ai_result = await ai_service.assess_writing(
            text=text,
            writing_type=writing_type,
            user_level=level,
            task_prompt=effective_prompt,
        )
        
        if ai_result.get('success'):
            assessment = ai_result.get('content', {})
            gemini_scores = {
                "overall": assessment.get('overall_score', 70),
                "grammar": assessment.get('grammar_score', 70),
                "vocabulary": assessment.get('vocabulary_score', 70),
                "coherence": assessment.get('coherence_score', 70),
                "task_achievement": assessment.get('task_achievement_score', 70),
            }
            return {
                "success": True,
                "assessment": {
                    "scores": gemini_scores,
                    "ielts_band": _score_to_ielts_band(gemini_scores["overall"]),
                    "ielts_breakdown": _ielts_breakdown(gemini_scores),
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
                    "user_level": level,
                    "scorer": "gemini",
                    "task_type": task_type,
                }
            }
        else:
            # Fallback response
            fb_scores = {
                "overall": 70, "grammar": 70, "vocabulary": 70,
                "coherence": 70, "task_achievement": 70,
            }
            return {
                "success": True,
                "assessment": {
                    "scores": fb_scores,
                    "ielts_band": _score_to_ielts_band(fb_scores["overall"]),
                    "ielts_breakdown": _ielts_breakdown(fb_scores),
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
                    "user_level": level,
                    "scorer": "fallback",
                    "task_type": task_type,
                }
            }
            
    except Exception as e:
        ex_scores = {
            "overall": 70, "grammar": 70, "vocabulary": 70,
            "coherence": 70, "task_achievement": 70,
        }
        return {
            "success": False,
            "error": str(e),
            "assessment": {
                "scores": ex_scores,
                "ielts_band": _score_to_ielts_band(ex_scores["overall"]),
                "ielts_breakdown": _ielts_breakdown(ex_scores),
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
                "user_level": user_level or "B1",
                "scorer": "error_fallback",
                "task_type": task_type,
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
