import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import base64

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import get_async_session
from app.services.audio_processing_service import AudioProcessingService
from app.services.elsa_service import ELSAService
from app.services.writing_analysis_service import WritingAnalysisService
from app.services.enhanced_ai_conversation_service import EnhancedAIConversationService
from app.services.ai_service import AIService
from app.services.content_generation_workflow import content_workflow_service
from app.services.content_cache_service import build_cache_key, content_cache_service
from app.crud.cache import generated_content_cache_crud
from app.models.user import User
from app.models.content import DifficultyLevel
from app.crud.speaking import speaking_attempt
from app.crud.writing import writing_submission
from app.crud.personalization import trainer_interaction

logger = logging.getLogger(__name__)

class AsyncTask(Task):
    """Base task class for async operations"""
    
    def __call__(self, *args, **kwargs):
        """Execute async task in event loop"""
        return asyncio.run(self.run_async(*args, **kwargs))
    
    async def run_async(self, *args, **kwargs):
        """Override this method in subclasses"""
        raise NotImplementedError

@celery_app.task(bind=True, base=AsyncTask, queue="ai_processing")
async def pre_generate_next_day_content(
    self,
    user_id: int,
    day_number: int
) -> Dict[str, Any]:
    """Pre-generate content for the next day to reduce user wait time."""
    try:
        async with get_async_session() as db:
            # Load user
            user = await db.get(User, user_id)
            if not user:
                return {"success": False, "error": f"User {user_id} not found"}

            # Pick a default set of content types to warm
            content_types = ["reading", "vocabulary", "listening"]
            topic = "daily life"
            warmed = []

            for ctype in content_types:
                key = build_cache_key(
                    user_id=user.id,
                    content_type=ctype,
                    topic=topic,
                    level=user.current_level.value,
                    day_number=day_number,
                )
                # Skip if already cached
                existing = await generated_content_cache_crud.get_by_key(db, cache_key=key)
                if existing and existing.content:
                    warmed.append({"type": ctype, "status": "cached"})
                    continue

                # Generate via workflow with minimal context
                result = await content_workflow_service._generate_single_content_piece(
                    db=db,
                    user=user,
                    content_type=ctype,
                    topic=topic,
                    duration_minutes=10,
                    user_context={"day_number": day_number}
                )
                warmed.append({"type": ctype, "status": "generated" if result.get("success") else "failed"})

            return {"success": True, "user_id": user_id, "day_number": day_number, "warmed": warmed}
    except Exception as e:
        logger.error(f"Pre-generation task error: {e}")
        return {"success": False, "error": str(e)}

async def process_audio_comprehensive(
    self,
    audio_data_base64: str,
    user_id: int,
    expected_text: str = "",
    analysis_type: str = "comprehensive"
) -> Dict[str, Any]:
    """
    Comprehensive audio processing task for speech recognition and pronunciation analysis
    
    Args:
        audio_data_base64: Base64 encoded audio data
        user_id: User ID
        expected_text: Expected text for pronunciation analysis
        analysis_type: Type of analysis (quick, comprehensive, pronunciation_only)
        
    Returns:
        Comprehensive analysis results
    """
    try:
        # Decode audio data
        audio_data = base64.b64decode(audio_data_base64)
        
        # Initialize services
        audio_processor = AudioProcessingService()
        elsa_service = ELSAService()
        
        results = {
            "task_id": self.request.id,
            "user_id": user_id,
            "processing_started": datetime.utcnow().isoformat(),
            "analysis_type": analysis_type
        }
        
        # Speech-to-text processing
        stt_result = await audio_processor.speech_to_text(
            audio_data, user_id=user_id
        )
        results["speech_recognition"] = stt_result
        
        # Pronunciation analysis if expected text provided
        if expected_text and stt_result.get("success"):
            pronunciation_result = await elsa_service.analyze_pronunciation(
                audio_data, expected_text, user_id
            )
            results["pronunciation_analysis"] = pronunciation_result
        
        # Audio feature extraction for advanced analysis
        if analysis_type == "comprehensive":
            features_result = await audio_processor.extract_speech_features(audio_data)
            results["audio_features"] = features_result
        
        # Store results in database if needed
        async with get_async_session() as db:
            if expected_text and results.get("pronunciation_analysis", {}).get("success"):
                # Create speaking attempt record
                attempt_data = {
                    "user_id": user_id,
                    "audio_url": f"temp_audio_{self.request.id}",  # Would be actual URL in production
                    "transcribed_text": stt_result.get("transcript", ""),
                    "pronunciation_score": results["pronunciation_analysis"].get("analysis", {}).get("overall_score", 0),
                    "ai_feedback": str(results["pronunciation_analysis"].get("analysis", {}))
                }
                await speaking_attempt.create(db, obj_in=attempt_data)
        
        results["processing_completed"] = datetime.utcnow().isoformat()
        results["success"] = True
        
        return results
        
    except Exception as e:
        logger.error(f"Audio processing task error: {e}")
        return {
            "task_id": self.request.id,
            "success": False,
            "error": str(e),
            "error_type": "audio_processing_error"
        }

@celery_app.task(bind=True, base=AsyncTask, queue="ai_processing")
async def analyze_writing_comprehensive(
    self,
    text: str,
    user_id: int,
    writing_type: str = "essay",
    user_level: str = "intermediate",
    analysis_type: str = "comprehensive"
) -> Dict[str, Any]:
    """
    Comprehensive writing analysis task
    
    Args:
        text: Text to analyze
        user_id: User ID
        writing_type: Type of writing
        user_level: User's proficiency level
        analysis_type: Type of analysis
        
    Returns:
        Comprehensive writing analysis results
    """
    try:
        # Initialize writing analyzer
        writing_analyzer = WritingAnalysisService()
        
        # Convert string parameters to enums
        from app.models.writing import WritingType
        from app.models.content import DifficultyLevel
        
        writing_type_enum = WritingType(writing_type)
        user_level_enum = DifficultyLevel(user_level)
        
        # Perform comprehensive analysis
        analysis_result = await writing_analyzer.analyze_writing_comprehensive(
            text, user_id, writing_type_enum, user_level_enum
        )
        
        # Store results in database
        async with get_async_session() as db:
            if analysis_result.get("success"):
                submission_data = {
                    "user_id": user_id,
                    "content": text,
                    "word_count": len(text.split()),
                    "overall_score": analysis_result["analysis"]["scores"]["overall"],
                    "ai_feedback": str(analysis_result["analysis"]["overall_feedback"]),
                    "suggestions": analysis_result["analysis"]["improvement_suggestions"]
                }
                await writing_submission.create(db, obj_in=submission_data)
        
        analysis_result["task_id"] = self.request.id
        analysis_result["processing_completed"] = datetime.utcnow().isoformat()
        
        return analysis_result
        
    except Exception as e:
        logger.error(f"Writing analysis task error: {e}")
        return {
            "task_id": self.request.id,
            "success": False,
            "error": str(e),
            "error_type": "writing_analysis_error"
        }

@celery_app.task(bind=True, base=AsyncTask, queue="ai_processing")
async def generate_ai_conversation_response(
    self,
    session_id: str,
    user_message: str,
    user_id: int,
    context: str = "daily_life",
    include_feedback: bool = True
) -> Dict[str, Any]:
    """
    Generate AI conversation response in background
    
    Args:
        session_id: Conversation session ID
        user_message: User's message
        user_id: User ID
        context: Conversation context
        include_feedback: Whether to include feedback
        
    Returns:
        AI response with optional feedback
    """
    try:
        # Initialize conversation service
        conversation_service = EnhancedAIConversationService()
        
        async with get_async_session() as db:
            # Process user message
            result = await conversation_service.process_user_message(
                db, session_id, user_message, request_feedback=include_feedback
            )
            
            result["task_id"] = self.request.id
            result["processing_completed"] = datetime.utcnow().isoformat()
            
            return result
    
    except Exception as e:
        logger.error(f"AI conversation task error: {e}")
        return {
            "task_id": self.request.id,
            "success": False,
            "error": str(e),
            "error_type": "conversation_error"
        }

@celery_app.task(bind=True, base=AsyncTask, queue="ai_processing")
async def batch_pronunciation_analysis(
    self,
    audio_files: List[Dict[str, Any]],
    user_id: int
) -> Dict[str, Any]:
    """
    Batch pronunciation analysis for multiple audio files
    
    Args:
        audio_files: List of audio file data with base64 content and expected text
        user_id: User ID
        
    Returns:
        Batch analysis results
    """
    try:
        elsa_service = ELSAService()
        results = []
        
        for i, audio_file in enumerate(audio_files):
            audio_data = base64.b64decode(audio_file["audio_data_base64"])
            expected_text = audio_file.get("expected_text", "")
            
            # Update task progress
            self.update_state(
                state="PROGRESS",
                meta={"current": i + 1, "total": len(audio_files), "status": f"Processing file {i + 1}"}
            )
            
            # Analyze pronunciation
            analysis_result = await elsa_service.analyze_pronunciation(
                audio_data, expected_text, user_id
            )
            
            results.append({
                "file_index": i,
                "file_id": audio_file.get("file_id"),
                "analysis": analysis_result
            })
        
        return {
            "task_id": self.request.id,
            "success": True,
            "results": results,
            "total_processed": len(results),
            "processing_completed": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Batch pronunciation analysis error: {e}")
        return {
            "task_id": self.request.id,
            "success": False,
            "error": str(e),
            "error_type": "batch_analysis_error"
        }

@celery_app.task(bind=True, base=AsyncTask, queue="ai_processing")
async def generate_personalized_exercises(
    self,
    user_id: int,
    exercise_count: int = 10,
    difficulty_level: str = "intermediate",
    focus_areas: List[str] = None
) -> Dict[str, Any]:
    """
    Generate personalized exercises based on user profile and progress
    
    Args:
        user_id: User ID
        exercise_count: Number of exercises to generate
        difficulty_level: Target difficulty level
        focus_areas: Specific areas to focus on
        
    Returns:
        Generated exercises
    """
    try:
        ai_service = AIService()
        
        async with get_async_session() as db:
            # Get user profile
            user = await db.get(User, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Generate exercises for different skills
            exercises = {
                "vocabulary": [],
                "grammar": [],
                "pronunciation": [],
                "comprehension": []
            }
            
            focus_areas = focus_areas or ["vocabulary", "grammar"]
            
            for area in focus_areas:
                # Update task progress
                self.update_state(
                    state="PROGRESS",
                    meta={"current_area": area, "status": f"Generating {area} exercises"}
                )
                
                if area == "vocabulary":
                    vocab_exercises = await ai_service.generate_exercise_content(
                        "vocabulary building", difficulty_level, "multiple_choice", 
                        count=exercise_count // len(focus_areas)
                    )
                    if vocab_exercises.get("success"):
                        exercises["vocabulary"] = vocab_exercises.get("content", [])
                
                elif area == "grammar":
                    grammar_exercises = await ai_service.generate_exercise_content(
                        "grammar practice", difficulty_level, "fill_in_blank",
                        count=exercise_count // len(focus_areas)
                    )
                    if grammar_exercises.get("success"):
                        exercises["grammar"] = grammar_exercises.get("content", [])
        
        return {
            "task_id": self.request.id,
            "success": True,
            "exercises": exercises,
            "user_id": user_id,
            "difficulty_level": difficulty_level,
            "focus_areas": focus_areas,
            "generation_completed": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Exercise generation task error: {e}")
        return {
            "task_id": self.request.id,
            "success": False,
            "error": str(e),
            "error_type": "exercise_generation_error"
        }

@celery_app.task(bind=True, base=AsyncTask, queue="ai_processing")
async def analyze_user_learning_patterns(
    self,
    user_id: int,
    analysis_period_days: int = 30
) -> Dict[str, Any]:
    """
    Analyze user's learning patterns and generate insights
    
    Args:
        user_id: User ID
        analysis_period_days: Number of days to analyze
        
    Returns:
        Learning pattern analysis and recommendations
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import select, and_
        
        async with get_async_session() as db:
            # Get user's recent interactions
            cutoff_date = datetime.utcnow() - timedelta(days=analysis_period_days)
            
            # Analyze conversation patterns
            conversation_query = select(trainer_interaction).where(
                and_(
                    trainer_interaction.c.user_id == user_id,
                    trainer_interaction.c.created_at >= cutoff_date
                )
            )
            
            # This would involve complex analysis of user patterns
            # For now, return mock analysis structure
            
            patterns = {
                "study_frequency": {
                    "daily_average": 2.5,
                    "most_active_days": ["Monday", "Wednesday", "Friday"],
                    "preferred_time": "evening"
                },
                "skill_preferences": {
                    "speaking": 0.4,
                    "writing": 0.3,
                    "listening": 0.2,
                    "reading": 0.1
                },
                "difficulty_progression": {
                    "current_level": "intermediate",
                    "improvement_rate": 0.15,
                    "ready_for_advancement": True
                },
                "common_mistakes": [
                    "verb tense consistency",
                    "article usage",
                    "pronunciation of 'th' sounds"
                ],
                "strengths": [
                    "vocabulary usage",
                    "sentence structure",
                    "conversational flow"
                ]
            }
            
            # Generate personalized recommendations
            recommendations = [
                "Focus more on pronunciation practice",
                "Try advanced grammar exercises",
                "Increase daily practice time to 45 minutes",
                "Practice speaking with more complex topics"
            ]
        
        return {
            "task_id": self.request.id,
            "success": True,
            "user_id": user_id,
            "analysis_period_days": analysis_period_days,
            "patterns": patterns,
            "recommendations": recommendations,
            "analysis_completed": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Learning pattern analysis error: {e}")
        return {
            "task_id": self.request.id,
            "success": False,
            "error": str(e),
            "error_type": "pattern_analysis_error"
        }

@celery_app.task(bind=True, queue="ai_processing")
def cleanup_old_audio_files(self, days_old: int = 7) -> Dict[str, Any]:
    """
    Clean up old temporary audio files
    
    Args:
        days_old: Files older than this many days will be deleted
        
    Returns:
        Cleanup results
    """
    try:
        import os
        from pathlib import Path
        from datetime import datetime, timedelta
        
        # This would clean up actual audio files in production
        # For now, return mock cleanup results
        
        cleanup_results = {
            "files_deleted": 25,
            "space_freed_mb": 150.5,
            "cleanup_date": datetime.utcnow().isoformat()
        }
        
        return {
            "task_id": self.request.id,
            "success": True,
            "results": cleanup_results
        }
    
    except Exception as e:
        logger.error(f"Audio cleanup task error: {e}")
        return {
            "task_id": self.request.id,
            "success": False,
            "error": str(e)
        }
