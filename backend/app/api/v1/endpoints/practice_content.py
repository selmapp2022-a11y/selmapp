"""
Practice Content API - Optimized endpoints for instant content loading.

This module provides pre-cached and on-demand generated practice content
that loads instantly for users based on their assessed level.

SELF-HEALING: When retrieving cached content with audio URLs, this module
validates that audio URLs point to cloud storage. Local file paths (which
get deleted during deployments) are detected and the cache is invalidated,
forcing regeneration of fresh content with valid cloud audio URLs.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_sync_db
from app.models.user import User
from app.models.cache import GeneratedContentCache
from app.services.ai_service import AIService
from app.services.content_cache_service import content_cache_service, build_cache_key, is_audio_url_valid
from app.services.audio_healing_service import audio_healing_service
from app.services.content_access_service import content_access_service

logger = logging.getLogger(__name__)
router = APIRouter()
ai_service = AIService()


def _require_practice_access(
    sync_db: Session,
    current_user: User,
    *,
    skill_type: Optional[str] = None,
    level: Optional[str] = None,
) -> None:
    can_access, reason = content_access_service.can_start_new_lesson(
        sync_db,
        current_user,
        module=skill_type,
        cefr_level=level,
    )
    if not can_access:
        raise HTTPException(status_code=403, detail=reason)


def _validate_and_heal_exercises(exercises: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], bool]:
    """
    Validate exercises for broken audio URLs.
    
    Returns:
        Tuple of (exercises, has_broken_audio)
    """
    if not exercises:
        return (exercises, False)
    
    has_broken = False
    for exercise in exercises:
        if isinstance(exercise, dict):
            audio_url = exercise.get("audio_url")
            if audio_url and not is_audio_url_valid(audio_url):
                logger.warning(f"⚠️ Found broken audio URL in exercise: {audio_url}")
                exercise["audio_url"] = ""  # Clear broken URL
                exercise["needs_audio_regeneration"] = True
                has_broken = True
    
    return (exercises, has_broken)


class PracticeContentRequest(BaseModel):
    """Request for practice content"""
    skill_type: str  # vocabulary, grammar, reading, listening, speaking, writing
    topic: Optional[str] = None
    count: int = 5


class MicroLessonRequest(BaseModel):
    """Request for a single micro-lesson (faster generation)"""
    skill_type: str
    topic: Optional[str] = None


class PracticeContentResponse(BaseModel):
    """Response with practice content"""
    success: bool
    source: str  # 'cache', 'generated', 'background'
    content: Optional[Dict[str, Any]] = None
    exercises: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None
    generation_id: Optional[str] = None


# Default topics by skill type for variety
DEFAULT_TOPICS = {
    "vocabulary": [
        "daily routines", "travel and tourism", "food and cooking",
        "work and careers", "technology", "health and fitness",
        "shopping", "entertainment", "family and relationships"
    ],
    "grammar": [
        "present tenses", "past tenses", "future forms",
        "conditionals", "passive voice", "reported speech",
        "articles and determiners", "prepositions", "modal verbs"
    ],
    "reading": [
        # Use concrete, "real-world" themes so passages feel authentic (not meta like "news articles")
        "A new café opens in the neighborhood",
        "A surprising discovery at a local museum",
        "How to plan a stress-free weekend trip",
        "The story of a community garden",
        "A small change that saves water at home",
        "A student prepares for a big presentation",
        "A day at a traditional street market",
        "Why people love morning routines",
        "A helpful app update that makes life easier",
        "A short profile of a street artist",
        "A community event brings neighbors together",
        "Tips for saving money on groceries",
    ],
    "listening": [
        # Concrete scenarios so transcripts sound natural and specific
        "Ordering coffee at a café",
        "Asking for directions in a new city",
        "Planning a weekend trip with a friend",
        "Calling to schedule a doctor's appointment",
        "Returning an item at a store",
        "Talking about a new job",
        "Discussing a movie you watched",
        "An announcement about a train delay",
        "An interview about healthy habits",
        "A short podcast snippet about productivity",
    ],
    "speaking": [
        "introducing yourself", "describing places",
        "giving opinions", "making requests", "telling stories"
    ],
    "writing": [
        "emails", "essays", "reviews",
        "messages", "descriptions", "stories"
    ]
}


def _get_cache_key_for_practice(user_id: int, skill_type: str, level: str) -> str:
    """Generate a simplified cache key for practice content"""
    return f"practice:{user_id}:{skill_type}:{level}"


@router.get("/ready", response_model=Dict[str, Any])
async def get_ready_content(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db),
):
    """
    Get all ready/cached practice content for the user.
    This endpoint returns instantly with pre-generated content.
    
    SELF-HEALING: Automatically detects and removes cached content with broken
    audio URLs (local files that were deleted during deployment).
    """
    try:
        user_level = current_user.current_level.value if current_user.current_level else "B1"
        _require_practice_access(sync_db, current_user, level=user_level)
        
        # Query all cached practice content for this user
        result = await db.execute(
            select(GeneratedContentCache).where(
                and_(
                    GeneratedContentCache.user_id == current_user.id,
                    GeneratedContentCache.content_type.like("practice_%"),
                    GeneratedContentCache.status == "ready",
                    or_(
                        GeneratedContentCache.expires_at.is_(None),
                        GeneratedContentCache.expires_at > datetime.utcnow()
                    )
                )
            )
        )
        cached_items = result.scalars().all()
        
        # Organize by skill type, with self-healing check
        ready_content = {}
        items_to_delete = []
        healed_count = 0
        
        for item in cached_items:
            skill_type = item.content_type.replace("practice_", "")
            
            # --- SELF-HEALING: Check for broken audio URLs ---
            content = item.content or {}
            audio_url = content.get("audio_url")
            
            # Also check in exercises
            exercises = content.get("exercises", [])
            has_broken_audio = False
            
            if audio_url and not is_audio_url_valid(audio_url):
                has_broken_audio = True
            
            for exercise in exercises if isinstance(exercises, list) else []:
                if isinstance(exercise, dict):
                    ex_audio = exercise.get("audio_url")
                    if ex_audio and not is_audio_url_valid(ex_audio):
                        has_broken_audio = True
                        break
            
            if has_broken_audio:
                logger.warning(f"⚠️ Found broken audio URL in cached content: {item.cache_key}")
                items_to_delete.append(item)
                healed_count += 1
                continue  # Skip this item
            # --- END SELF-HEALING ---

            can_access, _ = content_access_service.can_start_new_lesson(
                sync_db,
                current_user,
                module=skill_type,
                cefr_level=user_level,
            )
            if not can_access:
                continue
            
            if skill_type not in ready_content:
                ready_content[skill_type] = []
            ready_content[skill_type].append({
                "id": item.id,
                "topic": item.topic,
                "content": item.content,
                "created_at": item.created_at.isoformat() if item.created_at else None
            })
        
        # Delete broken cache items
        if items_to_delete:
            for item in items_to_delete:
                await db.delete(item)
            await db.commit()
            logger.info(f"🗑️ Deleted {len(items_to_delete)} cached items with broken audio URLs")
        
        # Check which skill types need content
        all_skills = ["vocabulary", "grammar", "reading", "speaking", "writing"]
        missing_skills = [s for s in all_skills if s not in ready_content or len(ready_content[s]) < 2]
        
        return {
            "success": True,
            "user_level": user_level,
            "ready_content": ready_content,
            "content_count": sum(len(v) for v in ready_content.values()),
            "missing_skills": missing_skills,
            "healed_broken_content": healed_count,
            "recommendation": "All content ready!" if not missing_skills else f"Generating content for: {', '.join(missing_skills)}"
        }
    except Exception as e:
        logger.error(f"Error getting ready content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/heal-audio-cache", response_model=Dict[str, Any])
async def heal_audio_cache(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Scan and heal all broken audio URLs in the user's cache.
    
    This endpoint finds all cached content with audio URLs pointing to local
    files (/media/...) and deletes them to trigger fresh regeneration.
    
    Use this if you're experiencing 404 errors for audio files.
    """
    try:
        stats = await audio_healing_service.heal_user_audio_cache(
            db=db,
            user_id=current_user.id,
            content_types=["listening", "practice_listening", "micro_listening", "reading"]
        )
        
        return {
            "success": True,
            "message": f"Healed {stats['invalidated']} broken audio entries",
            "stats": {
                "total_checked": stats["total_checked"],
                "broken_found": stats["broken_found"],
                "invalidated": stats["invalidated"],
                "content_types_affected": stats["content_types_affected"]
            }
        }
    except Exception as e:
        logger.error(f"Error healing audio cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/micro-lesson/{skill_type}", response_model=PracticeContentResponse)
async def get_micro_lesson(
    skill_type: str,
    topic: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db),
):
    """
    Get a single micro-lesson for immediate practice.
    
    Micro-lessons are:
    - 3-5 vocabulary words or 2-3 grammar questions
    - Fast to generate (under 5 seconds)
    - Perfect for quick practice sessions
    
    If cached content exists, returns immediately.
    If not, generates a small piece quickly.
    
    SELF-HEALING: Before returning cached content, validates any audio URLs.
    If broken (local file), invalidates cache and regenerates fresh content.
    """
    try:
        user_level = current_user.current_level.value if current_user.current_level else "B1"
        _require_practice_access(sync_db, current_user, skill_type=skill_type, level=user_level)
        
        # Select topic if not provided
        if not topic:
            import random
            topics = DEFAULT_TOPICS.get(skill_type, ["general English"])
            topic = random.choice(topics)
        
        # Check cache first.
        # The trailing `gen:` segment is the same content-version suffix
        # used in content_cache_service.build_cache_key so a code-level
        # prompt change invalidates micro-lessons too. Without this,
        # every user kept seeing the pre-deploy templated content
        # forever — by far the biggest reason "the bot still doesn't
        # use the new repositories" on iPhone (2026-05-13 audit).
        from app.services.content_cache_service import CONTENT_GENERATION_VERSION
        cache_key = (
            f"micro:{current_user.id}:{skill_type}:{user_level}:"
            f"{topic.replace(' ', '_')}:gen:{CONTENT_GENERATION_VERSION}"
        )
        
        result = await db.execute(
            select(GeneratedContentCache).where(
                and_(
                    GeneratedContentCache.cache_key == cache_key,
                    GeneratedContentCache.status == "ready",
                    or_(
                        GeneratedContentCache.expires_at.is_(None),
                        GeneratedContentCache.expires_at > datetime.utcnow()
                    )
                )
            )
        )
        cached = result.scalars().first()
        
        if cached and cached.content:
            exercises = cached.content.get("exercises", [])
            
            # --- SELF-HEALING: Check for broken audio URLs ---
            exercises, has_broken_audio = _validate_and_heal_exercises(exercises)
            
            if has_broken_audio:
                logger.warning(
                    f"⚠️ Found broken audio URLs in cached micro-lesson. "
                    f"Invalidating cache: {cache_key}"
                )
                # Delete the broken cache
                await db.delete(cached)
                await db.commit()
                # Fall through to regeneration
            else:
                # Cache is valid
                return PracticeContentResponse(
                    success=True,
                    source="cache",
                    content=cached.content,
                    exercises=exercises
                )
        
        # Generate micro-lesson (small, fast)
        exercises = await _generate_micro_lesson(skill_type, topic, user_level)
        
        if exercises:
            # Validate generated exercises for audio URLs
            exercises, _ = _validate_and_heal_exercises(exercises)
            
            # Cache for future use (1 hour TTL)
            try:
                cache_entry = GeneratedContentCache(
                    user_id=current_user.id,
                    cache_key=cache_key,
                    content_type=f"micro_{skill_type}",
                    topic=topic,
                    level=user_level,
                    content={"exercises": exercises, "topic": topic, "level": user_level},
                    status="ready",
                    expires_at=datetime.utcnow() + timedelta(hours=1)
                )
                db.add(cache_entry)
                await db.commit()
            except Exception as cache_err:
                logger.warning(f"Failed to cache micro-lesson: {cache_err}")
            
            return PracticeContentResponse(
                success=True,
                source="generated",
                content={"exercises": exercises, "topic": topic, "level": user_level},
                exercises=exercises
            )
        
        return PracticeContentResponse(
            success=False,
            source="none",
            message="Could not generate content. Please try again."
        )
        
    except Exception as e:
        logger.error(f"Error getting micro-lesson: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-batch", response_model=Dict[str, Any])
async def trigger_batch_generation(
    background_tasks: BackgroundTasks,
    skill_types: List[str] = Query(default=["vocabulary", "grammar"]),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db),
):
    """
    Trigger background generation of practice content.
    
    Call this after assessment or when user has been inactive.
    Content will be ready when user returns.
    """
    user_level = current_user.current_level.value if current_user.current_level else "B1"
    allowed_skill_types = []
    for skill_type in skill_types:
        can_access, _ = content_access_service.can_start_new_lesson(
            sync_db,
            current_user,
            module=skill_type,
            cefr_level=user_level,
        )
        if can_access:
            allowed_skill_types.append(skill_type)

    if not allowed_skill_types:
        raise HTTPException(status_code=403, detail="No accessible practice modules for current plan")
    
    # Add background task for each skill type
    generation_ids = []
    for skill_type in allowed_skill_types:
        gen_id = f"gen_{current_user.id}_{skill_type}_{datetime.utcnow().timestamp()}"
        generation_ids.append(gen_id)
        
        background_tasks.add_task(
            _background_generate_content,
            db_session_maker=get_db,
            user_id=current_user.id,
            skill_type=skill_type,
            level=user_level,
            generation_id=gen_id
        )
    
    return {
        "success": True,
        "message": f"Started generating content for: {', '.join(allowed_skill_types)}",
        "generation_ids": generation_ids,
        "estimated_time_seconds": len(allowed_skill_types) * 10
    }


@router.post("/ensure-ready")
async def ensure_content_ready(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db),
):
    """
    Ensure practice content is ready for the user.
    
    - Checks what content is missing
    - Triggers background generation for missing content
    - Returns immediately with available content
    """
    user_level = current_user.current_level.value if current_user.current_level else "B1"
    _require_practice_access(sync_db, current_user, level=user_level)
    
    # Check what's cached
    result = await db.execute(
        select(GeneratedContentCache.content_type).where(
            and_(
                GeneratedContentCache.user_id == current_user.id,
                GeneratedContentCache.status == "ready",
                or_(
                    GeneratedContentCache.expires_at.is_(None),
                    GeneratedContentCache.expires_at > datetime.utcnow()
                )
            )
        ).distinct()
    )
    cached_types = {r[0].replace("practice_", "").replace("micro_", "") for r in result.fetchall()}
    
    # Determine what needs generation
    required_types = {"vocabulary", "grammar", "speaking", "writing"}
    required_types = {
        skill for skill in required_types
        if content_access_service.can_start_new_lesson(
            sync_db,
            current_user,
            module=skill,
            cefr_level=user_level,
        )[0]
    }
    missing_types = required_types - cached_types
    
    if missing_types:
        for skill_type in missing_types:
            background_tasks.add_task(
                _background_generate_content,
                db_session_maker=get_db,
                user_id=current_user.id,
                skill_type=skill_type,
                level=user_level,
                generation_id=f"ensure_{current_user.id}_{skill_type}"
            )
    
    return {
        "success": True,
        "ready_types": list(cached_types),
        "generating_types": list(missing_types),
        "user_level": user_level,
        "all_ready": len(missing_types) == 0
    }


async def _generate_micro_lesson(
    skill_type: str,
    topic: str,
    level: str,
    count: int = 3
) -> Optional[List[Dict[str, Any]]]:
    """
    Generate a small micro-lesson quickly.

    2026-05-13 rewrite — Why
    ------------------------
    Previously, this function had its own ad-hoc per-skill prompts that
    bypassed the entire prompt_library (CEFR matrix, HUMAN_VOICE_RULES,
    creative_seed, dialogue_seed). The deeper iPhone-app audit traced
    "the bot doesn't use the new repositories" directly to this code:
    every practice screen on iOS calls this endpoint, and none of the
    new variety, voice, or pedagogy infrastructure ever ran here.

    Now every sub-prompt:
      • pastes the level-specific CEFR spec verbatim,
      • includes HUMAN_VOICE_RULES,
      • pulls a fresh creative_seed (reading/speaking/writing) or
        dialogue_seed (listening) so two requests with the same topic
        + level produce different content.
    """
    from app.services.prompt_library import (
        cefr_block,
        creative_seed,
        dialogue_seed,
        render_creative_brief,
        render_dialogue_brief,
        HUMAN_VOICE_RULES,
    )
    try:
        skill = skill_type.lower()

        # Skill-specific prompts for better content generation
        if skill == 'reading':
            # Word count based on level. 2026-05-13: substantially bumped
            # from the previous (A1=60-80, C2=400-500) to give the
            # creative brief room to unfold a real piece of writing.
            # User flagged that short passages felt thin even at lower
            # levels — Ebrahim's note "افزایش حجم متن‌ها در سشن‌های مختلف".
            word_counts = {
                "A1": "100-140",
                "A2": "170-230",
                "B1": "280-360",
                "B2": "420-540",
                "C1": "580-720",
                "C2": "780-950",
            }
            target_words = word_counts.get(level, "300-400")
            import random
            style = random.choice([
                "short news article",
                "personal blog post",
                "short story",
                "email",
                "how-to guide",
                "interview transcript",
                "diary entry",
                "review of a place",
            ])
            r_seed = creative_seed(style)
            r_brief = render_creative_brief(r_seed)

            prompt = f"""Write an ORIGINAL {style} reading passage that reads
like it came from a real publication — not a textbook exercise.
Theme/topic: "{topic}"

{cefr_block(level)}

{HUMAN_VOICE_RULES}

{r_brief}

Return ONLY valid JSON (no markdown):
{{
  "type": "reading",
  "title": "An engaging title for the passage",
  "text": "A {target_words}-word passage. Use natural paragraphs (separate with \\n\\n). Include concrete details (places, names, times, numbers). Respect the CEFR spec above for vocabulary and grammar.",
  "questions": [
    {{
      "question": "A comprehension question — main idea, detail, inference, or vocabulary-in-context",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "The correct option text",
      "explanation": "Why this is correct, with reference to the passage"
    }}
  ],
  "vocabulary_highlights": ["word1", "word2", "word3"],
  "style": "{style}",
  "points": 20
}}

REQUIREMENTS:
- Use the scene/opening/perspective/structure from the creative brief.
- Two requests with the same topic + level MUST produce different
  passages (different scene, different opening, different shape).
- No meta-commentary about learning, no "In today's world…" filler.
- SUBSTANTIVE: every paragraph adds new information. No restating, no
  filler. Hit the target word count with REAL content (specific facts,
  named people, concrete details), not padding. A short padded passage
  is worse than a long substantive one.
- Include exactly {count} comprehension questions, mixing question types."""

        elif skill == 'listening':
            d_seed = dialogue_seed()
            d_brief = render_dialogue_brief(d_seed)
            speaker_a = d_seed["speaker_a_name"]
            speaker_b = d_seed["speaker_b_name"]
            a_gender = 'female' if 'she' in d_seed['speaker_a_pronouns'] else 'male'
            b_gender = 'female' if 'she' in d_seed['speaker_b_pronouns'] else 'male'

            prompt = f"""Write a short listening-comprehension dialogue
between TWO real-sounding people about "{topic}". A monologue is not
acceptable — at least two speakers must speak multiple lines each.

{cefr_block(level)}

{HUMAN_VOICE_RULES}

{d_brief}

Return ONLY valid JSON (no markdown):
{{
  "type": "listening",
  "transcript": "Multi-speaker dialogue. Length by level: A1 90-130, A2 140-200, B1 220-300, B2 320-450, C1 500-650, C2 650-850 words. Format each line as 'Speaker Name: line of dialogue.' on its own line. Use the two names from the dialogue brief. Develop the conversation enough that both speakers exchange real ideas, not just greetings.",
  "speakers": [
    {{"name": "{speaker_a}", "gender": "{a_gender}"}},
    {{"name": "{speaker_b}", "gender": "{b_gender}"}}
  ],
  "questions": [
    {{
      "question": "Comprehension question about what was said",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "The correct option"
    }}
  ],
  "points": 20
}}

REQUIREMENTS:
- Both named speakers MUST speak multiple times — no monologue.
- Use the scene / tension / relationship from the dialogue brief.
- Include exactly {count} comprehension questions."""

        elif skill == 'vocabulary':
            prompt = f"""Generate {count} vocabulary practice items for a learner
about "{topic}". Each item teaches ONE word with a real example.

{cefr_block(level)}

{HUMAN_VOICE_RULES}

Return ONLY valid JSON array (no markdown):
[
  {{
    "type": "vocabulary",
    "word": "...",
    "definition": "level-appropriate, learner-friendly definition",
    "question": "Choose the correct meaning of '<word>' as used in: \\"<concrete sentence>\\"",
    "options": ["plausible definition 1", "plausible definition 2", "plausible definition 3", "plausible definition 4"],
    "correct_answer": "the correct definition (must match one option exactly)",
    "example_sentence": "A new concrete sentence (not the question) using the word",
    "usage_tip": "ONE-line warning about a real mistake learners make with this word",
    "points": 10
  }}
]

Pick words that genuinely belong in {level}-level usage about {topic}.
Distractors must be defensible misreads, not throwaway nonsense."""

        elif skill == 'writing':
            w_seed = creative_seed("essay")
            prompt = f"""Generate ONE writing prompt that gives the learner
something specific and engaging to write about — not a generic essay
question.

Theme/topic: "{topic}"

{cefr_block(level)}

INSPIRATION (use as flavour, not literally):
  Scene: {w_seed['scene']}
  Tone:  {w_seed['register']}
  Place anchor: {w_seed['place']}

Return ONLY valid JSON (no markdown):
{{
  "type": "writing",
  "question": "A specific, concrete writing task — gives the learner a situation, a reader, and a clear purpose. NOT just 'write about {topic}'.",
  "guidelines": ["3-5 guidelines on what to include — specific, not 'use good grammar'"],
  "keywords": ["4-6 useful keywords for the topic at this level"],
  "min_words": 80,
  "max_words": 200,
  "points": 25
}}"""

        elif skill == 'speaking':
            s_seed = creative_seed("story")
            prompt = f"""Generate a single sentence the learner will read aloud
for pronunciation practice.

Theme/topic: "{topic}"

{cefr_block(level)}

INSPIRATION (use as flavour):
  Scene: {s_seed['scene']}
  Tone:  {s_seed['register']}

Return ONLY valid JSON (no markdown):
{{
  "type": "speaking",
  "question": "ONE natural English sentence (10-18 words) at this level — concrete situation, varied phonemes, correct grammar. Capital letter, ends with punctuation.",
  "keywords": ["4-6 single words from the sentence (no spaces)"],
  "sample_response": "Repeat the exact sentence from 'question' verbatim.",
  "points": 15
}}

RULES:
- 'question' is a SENTENCE TO READ ALOUD, never an instruction
  (avoid: Describe..., Talk about..., Explain..., Answer...).
- Pick a sentence with varied consonants/vowels so SpeechAce can score
  pronunciation usefully. Include at least one tricky cluster
  (th, sh, ch, r, l, w, or a vowel pair) where the level allows."""

        else:  # grammar or default
            prompt = f"""Generate {count} short grammar practice items.
Theme/topic: "{topic}"

{cefr_block(level)}

Return ONLY valid JSON array (no markdown):
[
  {{
    "type": "grammar",
    "question": "Complete the sentence: ...",
    "options": ["plausible option", "plausible option", "plausible option", "plausible option"],
    "correct_answer": "the correct option (must match one option exactly)",
    "explanation": "Short explanation that teaches the rule, not just the answer.",
    "points": 10
  }}
]

Vary which grammar structures the items target across the {count}
questions (tenses, articles, prepositions, modals, etc., picked from
the CEFR spec for this level). Distractors must reflect common
{level}-level learner mistakes, not random words."""

        if ai_service.gemini_model:
            # 2026-05-13: timeout bumped from 15→45s. ai_service.gemini_model
            # now uses gemini-2.5-pro (CONTENT tier) instead of flash-lite,
            # which produces much higher-quality multi-paragraph output but
            # can take 10-20 s for longer reading passages at higher CEFR
            # levels. 15 s was timing out and falling back to nothing.
            response = await asyncio.wait_for(
                asyncio.to_thread(ai_service.gemini_model.generate_content, prompt),
                timeout=45.0,
            )
            
            content = response.text.strip()
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            
            exercises = json.loads(content)
            return exercises if isinstance(exercises, list) else [exercises]
    except asyncio.TimeoutError:
        logger.warning(f"Micro-lesson generation timed out for {skill_type}/{topic}")
    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse micro-lesson JSON: {je}")
    except Exception as e:
        logger.error(f"Error generating micro-lesson: {e}")
    
    return None


async def _background_generate_content(
    db_session_maker,
    user_id: int,
    skill_type: str,
    level: str,
    generation_id: str
):
    """
    Background task to generate and cache practice content.
    """
    try:
        logger.info(f"Starting background generation: {generation_id}")
        
        # Get topic variety
        import random
        topics = DEFAULT_TOPICS.get(skill_type, ["general English"])
        
        # Generate content for 2-3 different topics
        for topic in random.sample(topics, min(3, len(topics))):
            exercises = await _generate_micro_lesson(skill_type, topic, level, count=5)
            
            if exercises:
                # Save to cache (need new session for background task)
                async for db in db_session_maker():
                    cache_key = f"practice_{user_id}:{skill_type}:{level}:{topic.replace(' ', '_')}"
                    
                    # Check if already exists
                    existing = await db.execute(
                        select(GeneratedContentCache).where(
                            GeneratedContentCache.cache_key == cache_key
                        )
                    )
                    if existing.scalars().first():
                        continue
                    
                    cache_entry = GeneratedContentCache(
                        user_id=user_id,
                        cache_key=cache_key,
                        content_type=f"practice_{skill_type}",
                        topic=topic,
                        level=level,
                        content={
                            "exercises": exercises,
                            "topic": topic,
                            "level": level,
                            "skill_type": skill_type,
                            "generated_at": datetime.utcnow().isoformat()
                        },
                        status="ready",
                        # Reading/Speaking should feel fresh day-to-day; keep a shorter TTL there.
                        expires_at=datetime.utcnow()
                        + (timedelta(days=1) if skill_type.lower() in ("reading", "speaking") else timedelta(days=7))
                    )
                    db.add(cache_entry)
                    await db.commit()
                    break
        
        logger.info(f"Completed background generation: {generation_id}")
        
    except Exception as e:
        logger.error(f"Background generation failed: {generation_id} - {e}")


@router.post("/trigger-post-assessment")
async def trigger_post_assessment_generation(
    background_tasks: BackgroundTasks,
    determined_level: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    sync_db: Session = Depends(get_sync_db),
):
    """
    Called after assessment completes to pre-generate content.
    This ensures content is ready when user goes to practice.
    """
    # Generate content for all skill types based on assessed level
    requested_types = ["vocabulary", "grammar", "speaking", "writing", "reading"]
    skill_types = [
        skill for skill in requested_types
        if content_access_service.can_start_new_lesson(
            sync_db,
            current_user,
            module=skill,
            cefr_level=determined_level,
        )[0]
    ]

    if not skill_types:
        raise HTTPException(status_code=403, detail="No accessible post-assessment modules for current plan")
    
    for skill_type in skill_types:
        background_tasks.add_task(
            _background_generate_content,
            db_session_maker=get_db,
            user_id=current_user.id,
            skill_type=skill_type,
            level=determined_level,
            generation_id=f"post_assessment_{current_user.id}_{skill_type}"
        )
    
    return {
        "success": True,
        "message": "Content generation started for all skills",
        "level": determined_level,
        "skills_queued": skill_types
    }











