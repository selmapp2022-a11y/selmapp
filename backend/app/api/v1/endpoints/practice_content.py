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
    level: Optional[str] = None,
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
        valid_levels = {"A1","A2","B1","B2","C1","C2"}
        if level and level.upper() in valid_levels:
            user_level = level.upper()
        else:
            user_level = current_user.current_level.value if current_user.current_level else "B1"
        _require_practice_access(sync_db, current_user, skill_type=skill_type, level=user_level)
        
        # Select topic if not provided
        if not topic:
            import random
            topics = DEFAULT_TOPICS.get(skill_type, ["general English"])
            topic = random.choice(topics)
        
        # Check cache first
        cache_key = f"micro:{current_user.id}:{skill_type}:{user_level}:{topic.replace(' ', '_')}"
        
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
    Uses skill-specific prompts for proper content.
    """
    try:
        # Skill-specific prompts for better content generation
        if skill_type.lower() == 'reading':
            # Word count based on level
            word_counts = {"A1": "60-80", "A2": "80-120", "B1": "150-200", "B2": "200-280", "C1": "280-400", "C2": "400-500"}
            target_words = word_counts.get(level, "100-150")
            import random
            style = random.choice([
                "short news article",
                "personal blog post",
                "short story",
                "email",
                "how-to guide",
            ])
            
            prompt = f"""You are creating an ORIGINAL, authentic {style} reading passage for {level} level English learners.
Theme/topic: "{topic}"

CRITICAL: Create a REAL, MEANINGFUL passage that reads like something from a real publication.
It must NOT sound like a textbook or an AI template.

Return ONLY valid JSON (no markdown):
{{
  "type": "reading",
  "title": "An engaging title for the passage",
  "text": "A {target_words} word passage. Write in natural paragraphs (use \\n\\n). Include concrete details (places, names, times, numbers) and a clear main idea. Keep grammar correct and vocabulary appropriate for {level}.",
  "questions": [
    {{
      "question": "A comprehension question testing understanding of the main idea or key details",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "The correct option text",
      "explanation": "Brief explanation of why this is correct"
    }}
  ],
  "vocabulary_highlights": ["word1", "word2", "word3"],
  "style": "{style}",
  "points": 20
}}

REQUIREMENTS:
- The passage MUST feel authentic: include interesting facts, real information, or engaging narrative
- Avoid generic filler like "In today's world..." / "has become increasingly important..." unless it truly fits the passage
- Write as if for a real publication, NOT as a language exercise
- Do NOT reference "learners" or "students" in the text
- Do NOT include meta-commentary about learning
- Include {count} varied comprehension questions (main idea, detail, inference, vocabulary)
- Make questions progressively challenging"""
        
        elif skill_type.lower() == 'listening':
            prompt = f"""Generate a listening comprehension exercise for {level} level English learners about "{topic}".

Return ONLY valid JSON (no markdown):
{{
  "type": "listening",
  "transcript": "A 80-120 word dialogue or monologue about {topic} appropriate for {level} level learners.",
  "questions": [
    {{
      "question": "Comprehension question about what was said",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": "The correct option"
    }}
  ],
  "points": 20
}}

Make the transcript natural and conversational. Include {count} comprehension questions."""

        elif skill_type.lower() == 'vocabulary':
            prompt = f"""Generate {count} vocabulary practice items for {level} level English learners about "{topic}".

Return ONLY valid JSON array (no markdown):
[
  {{
    "type": "vocabulary",
    "word": "example word",
    "definition": "the meaning",
    "question": "Choose the correct meaning of 'word'",
    "options": ["definition 1", "definition 2", "definition 3", "definition 4"],
    "correct_answer": "the correct definition",
    "example_sentence": "A sentence using the word",
    "points": 10
  }}
]

Choose useful vocabulary words related to {topic}."""

        elif skill_type.lower() == 'writing':
            prompt = f"""Generate a writing prompt for {level} level English learners about "{topic}".

Return ONLY valid JSON (no markdown):
{{
  "type": "writing",
  "question": "Write a paragraph/essay prompt about {topic}",
  "guidelines": ["Guideline 1", "Guideline 2", "Guideline 3"],
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],
  "min_words": 50,
  "max_words": 200,
  "points": 25
}}

Make the prompt engaging and appropriate for {level} level."""

        elif skill_type.lower() == 'speaking':
            prompt = f"""Generate a PRONUNCIATION (read-aloud) speaking exercise for {level} level English learners.
Theme/topic: "{topic}"

Return ONLY valid JSON (no markdown):
{{
  "type": "speaking",
  "question": "ONE complete, natural sentence (8-16 words) the learner will read aloud. Correct grammar. Starts with a capital letter and ends with punctuation.",
  "keywords": ["4-6 SINGLE WORDS from the sentence (no spaces)"],
  "sample_response": "Repeat the exact same sentence from 'question' (verbatim).",
  "points": 15
}}

RULES:
- 'question' must be a sentence to read aloud, NOT an instruction (avoid: Describe..., Talk about..., Explain..., Answer...)
- No blanks, no brackets, no quotes, no emojis
- Keep it practical and conversational, with topic-relevant vocabulary
- Keep grammar correct and level-appropriate"""

        else:  # grammar or default
            prompt = f"""Generate {count} quick grammar practice items for {level} level English learners.
Topic: {topic}

Return ONLY valid JSON array (no markdown):
[
  {{
    "type": "grammar",
    "question": "Complete this sentence: I ___ to the store yesterday.",
    "options": ["go", "went", "going", "goes"],
    "correct_answer": "went",
    "explanation": "Use past simple for completed actions.",
    "points": 10
  }}
]

Make questions appropriate for {level} level. Be concise."""

        if ai_service.gemini_model:
            response = await asyncio.wait_for(
                asyncio.to_thread(ai_service.gemini_model.generate_content, prompt),
                timeout=15.0  # 15 second timeout for fast response
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











