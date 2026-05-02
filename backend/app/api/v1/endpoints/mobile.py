from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import base64
import json
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.content import DifficultyLevel
from app.services.enhanced_ai_conversation_service import (
    EnhancedAIConversationService, ConversationContext, ConversationMode
)
from app.services.audio_processing_service import AudioProcessingService
from app.services.elsa_service import ELSAService
from app.services.writing_analysis_service import WritingAnalysisService
from app.services.advanced_caching_service import caching_service
from app.middleware.security_middleware import audio_validator, input_sanitizer
from app.tasks.ai_tasks import (
    process_audio_comprehensive, analyze_writing_comprehensive,
    generate_personalized_exercises
)
from app.schemas.mobile import (
    MobileSessionStart, MobileSessionResponse,
    MobileAudioUpload, MobileAudioResponse,
    MobileWritingSubmission, MobileWritingResponse,
    MobileProgressSync, MobileProgressResponse,
    MobileOfflineData, MobileOfflineResponse,
    MobilePracticeSession, MobilePracticeResponse,
    MobileQuickFeedback, MobileQuickFeedbackResponse,
    MobileContentRequest, MobileContentResponse,
    MobileNotificationSettings, MobileNotificationResponse
)

router = APIRouter()

# Initialize services
conversation_service = EnhancedAIConversationService()
audio_processor = AudioProcessingService()
elsa_service = ELSAService()
writing_analyzer = WritingAnalysisService()

@router.post("/session/start", response_model=MobileSessionResponse)
async def start_mobile_session(
    session_data: MobileSessionStart,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Start a mobile learning session with optimized data transfer
    
    Features:
    - Lightweight session initialization
    - Offline capability preparation
    - Mobile-optimized content delivery
    """
    try:
        # Start conversation session
        conversation_result = await conversation_service.start_conversation(
            db, current_user.id, 
            ConversationContext(session_data.context),
            ConversationMode(session_data.mode),
            DifficultyLevel(session_data.difficulty_level) if session_data.difficulty_level else None,
            session_data.topic
        )
        
        if not conversation_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start conversation session"
            )
        
        # Prepare mobile-optimized session data
        session = conversation_result["session"]
        
        # Pre-cache common responses for offline use
        await _precache_mobile_content(current_user.id, session_data.context)
        
        # Get suggested conversation starters
        starters = await _get_conversation_starters(session_data.context)
        
        return MobileSessionResponse(
            session_id=session["session_id"],
            initial_message=conversation_result["initial_message"]["content"],
            conversation_starters=starters,
            user_level=session["user_profile_snapshot"]["level"],
            estimated_duration=session_data.estimated_duration or 15,
            offline_content=await _get_offline_content_summary(current_user.id),
            session_config={
                "auto_feedback": session_data.enable_auto_feedback,
                "pronunciation_focus": session_data.pronunciation_focus,
                "real_time_corrections": session_data.real_time_corrections
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Session start failed: {str(e)}"
        )

@router.post("/audio/upload", response_model=MobileAudioResponse)
async def upload_mobile_audio(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    session_id: str = Form(...),
    expected_text: Optional[str] = Form(None),
    analysis_type: str = Form("quick"),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Mobile-optimized audio upload with background processing
    
    Features:
    - Quick initial response for mobile UX
    - Background comprehensive analysis
    - Optimized for mobile network conditions
    """
    try:
        # Read audio data
        audio_data = await audio_file.read()
        
        # Security validation
        validation_result = await audio_validator.validate_audio_upload(
            audio_data, audio_file.filename or ""
        )
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result["error"]
            )
        
        # Quick processing for immediate feedback
        if analysis_type == "quick":
            # Basic speech-to-text for immediate response
            stt_result = await audio_processor.speech_to_text(
                audio_data, user_id=current_user.id
            )
            
            response_data = {
                "transcript": stt_result.get("transcript", ""),
                "confidence": stt_result.get("confidence", 0.0),
                "processing_type": "quick",
                "detailed_analysis_pending": True
            }
            
            # Schedule comprehensive analysis in background
            if expected_text:
                background_tasks.add_task(
                    _schedule_comprehensive_audio_analysis,
                    base64.b64encode(audio_data).decode(),
                    current_user.id,
                    expected_text,
                    session_id
                )
            
            return MobileAudioResponse(**response_data)
        
        else:
            # Comprehensive analysis (may take longer)
            stt_result = await audio_processor.speech_to_text(
                audio_data, user_id=current_user.id
            )
            
            pronunciation_result = None
            if expected_text and stt_result.get("success"):
                pronunciation_result = await elsa_service.analyze_pronunciation(
                    audio_data, expected_text, current_user.id
                )
            
            return MobileAudioResponse(
                transcript=stt_result.get("transcript", ""),
                confidence=stt_result.get("confidence", 0.0),
                pronunciation_analysis=pronunciation_result.get("analysis") if pronunciation_result and pronunciation_result.get("success") else None,
                processing_type="comprehensive",
                detailed_analysis_pending=False
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio processing failed: {str(e)}"
        )

@router.post("/writing/submit", response_model=MobileWritingResponse)
async def submit_mobile_writing(
    submission: MobileWritingSubmission,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Mobile-optimized writing submission with progressive analysis
    
    Features:
    - Immediate basic feedback
    - Progressive detailed analysis
    - Mobile-friendly response format
    """
    try:
        # Sanitize input
        clean_text = input_sanitizer.sanitize_text(submission.text)
        
        if len(clean_text.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Text too short for analysis"
            )
        
        # Quick analysis for immediate feedback
        word_count = len(clean_text.split())
        basic_score = min(100, max(0, (word_count * 2) + 50))  # Simple scoring
        
        # Basic feedback
        quick_feedback = {
            "overall_score": basic_score,
            "word_count": word_count,
            "immediate_suggestions": [
                "Great start!" if word_count > 50 else "Try writing a bit more",
                "Good vocabulary usage" if word_count > 30 else "Consider using more varied words"
            ],
            "processing_type": "quick"
        }
        
        # Schedule comprehensive analysis in background
        background_tasks.add_task(
            _schedule_comprehensive_writing_analysis,
            clean_text,
            current_user.id,
            submission.writing_type,
            current_user.current_level.value,
            submission.session_id
        )
        
        return MobileWritingResponse(
            analysis_id=f"mobile_{datetime.utcnow().timestamp()}",
            quick_feedback=quick_feedback,
            comprehensive_analysis_pending=True,
            estimated_completion_seconds=30
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Writing submission failed: {str(e)}"
        )

@router.post("/progress/sync", response_model=MobileProgressResponse)
async def sync_mobile_progress(
    progress_data: MobileProgressSync,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Sync mobile app progress with server
    
    Features:
    - Offline progress synchronization
    - Conflict resolution
    - Incremental sync for bandwidth optimization
    """
    try:
        # Process offline activities
        sync_results = {
            "synced_activities": 0,
            "conflicts_resolved": 0,
            "server_updates": []
        }
        
        # Sync conversation sessions
        for session in progress_data.offline_sessions:
            # Store offline session data
            await _store_offline_session(current_user.id, session, db)
            sync_results["synced_activities"] += 1
        
        # Sync exercise completions
        for completion in progress_data.exercise_completions:
            # Store exercise completion
            await _store_exercise_completion(current_user.id, completion, db)
            sync_results["synced_activities"] += 1
        
        # Sync study time
        if progress_data.study_time_minutes > 0:
            await _update_study_time(current_user.id, progress_data.study_time_minutes, db)
        
        # Get server updates since last sync
        last_sync = datetime.fromisoformat(progress_data.last_sync_timestamp) if progress_data.last_sync_timestamp else datetime.utcnow() - timedelta(days=7)
        server_updates = await _get_server_updates_since(current_user.id, last_sync, db)
        
        return MobileProgressResponse(
            sync_successful=True,
            synced_activities=sync_results["synced_activities"],
            conflicts_resolved=sync_results["conflicts_resolved"],
            server_updates=server_updates,
            next_sync_recommended=datetime.utcnow() + timedelta(hours=6)
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Progress sync failed: {str(e)}"
        )

@router.get("/offline/content", response_model=MobileOfflineResponse)
async def get_offline_content(
    content_request: MobileContentRequest = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Get content for offline use
    
    Features:
    - Personalized content selection
    - Optimized for mobile storage
    - Progressive download support
    """
    try:
        # Get user preferences and level
        user_level = current_user.current_level
        
        # Prepare offline content package
        offline_package = {
            "conversations": await _get_offline_conversations(current_user.id, content_request.max_conversations),
            "exercises": await _get_offline_exercises(current_user.id, user_level, content_request.max_exercises),
            "vocabulary": await _get_offline_vocabulary(current_user.id, user_level, content_request.max_vocabulary_items),
            "audio_samples": await _get_offline_audio_samples(current_user.id, content_request.include_audio),
            "ai_responses": await _get_cached_ai_responses(current_user.id, content_request.max_ai_responses)
        }
        
        # Calculate package size
        package_size_mb = _estimate_package_size(offline_package)
        
        return MobileOfflineResponse(
            content_package=offline_package,
            package_size_mb=package_size_mb,
            expires_at=datetime.utcnow() + timedelta(days=7),
            sync_required_by=datetime.utcnow() + timedelta(days=14)
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Offline content preparation failed: {str(e)}"
        )

@router.post("/practice/quick", response_model=MobilePracticeResponse)
async def quick_mobile_practice(
    practice_data: MobilePracticeSession,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Quick mobile practice session
    
    Features:
    - Instant feedback
    - No session persistence required
    - Optimized for quick interactions
    """
    try:
        if practice_data.type == "vocabulary":
            # Quick vocabulary practice
            response = await _quick_vocabulary_practice(
                practice_data.content, current_user.current_level
            )
        elif practice_data.type == "pronunciation":
            # Quick pronunciation check
            response = await _quick_pronunciation_practice(
                practice_data.audio_data, practice_data.content, current_user.id
            )
        elif practice_data.type == "grammar":
            # Quick grammar check
            response = await _quick_grammar_practice(
                practice_data.content, current_user.current_level
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported practice type"
            )
        
        return MobilePracticeResponse(
            practice_type=practice_data.type,
            feedback=response["feedback"],
            score=response["score"],
            suggestions=response["suggestions"],
            next_practice_suggestion=response.get("next_suggestion")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quick practice failed: {str(e)}"
        )

@router.post("/feedback/quick", response_model=MobileQuickFeedbackResponse)
async def get_quick_feedback(
    feedback_request: MobileQuickFeedback,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get quick AI feedback for mobile interactions
    
    Features:
    - Ultra-fast response
    - Cached common responses
    - Mobile-optimized feedback format
    """
    try:
        # Check cache first
        cache_key = f"quick_feedback:{feedback_request.type}:{hash(feedback_request.content)}"
        cached_response = await caching_service.get(cache_key)
        
        if cached_response:
            return MobileQuickFeedbackResponse(**cached_response)
        
        # Generate quick feedback
        if feedback_request.type == "text":
            feedback = await _generate_quick_text_feedback(
                feedback_request.content, current_user.current_level
            )
        elif feedback_request.type == "pronunciation":
            feedback = await _generate_quick_pronunciation_feedback(
                feedback_request.audio_data, feedback_request.content, current_user.id
            )
        else:
            feedback = {"message": "Keep practicing!", "score": 75, "tips": ["Great effort!"]}
        
        response = MobileQuickFeedbackResponse(
            feedback_message=feedback["message"],
            score=feedback["score"],
            quick_tips=feedback["tips"],
            encouragement=feedback.get("encouragement", "You're doing great!"),
            response_time_ms=feedback.get("response_time", 100)
        )
        
        # Cache response
        await caching_service.set(cache_key, response.dict(), timedelta(hours=1))
        
        return response
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quick feedback failed: {str(e)}"
        )

@router.post("/notifications/settings", response_model=MobileNotificationResponse)
async def update_notification_settings(
    settings: MobileNotificationSettings,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Update mobile notification settings
    
    Features:
    - Push notification preferences
    - Study reminder scheduling
    - Achievement notifications
    """
    try:
        # Update user notification preferences
        await _update_user_notification_settings(current_user.id, settings, db)
        
        # Schedule notifications based on preferences
        if settings.daily_reminders_enabled:
            await _schedule_daily_reminders(current_user.id, settings.reminder_time)
        
        return MobileNotificationResponse(
            settings_updated=True,
            daily_reminders_scheduled=settings.daily_reminders_enabled,
            push_notifications_enabled=settings.push_notifications_enabled,
            next_reminder=_calculate_next_reminder(settings.reminder_time) if settings.daily_reminders_enabled else None
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Notification settings update failed: {str(e)}"
        )

# Helper functions for mobile-specific operations

async def _precache_mobile_content(user_id: int, context: str):
    """Pre-cache content for mobile offline use"""
    # Cache common AI responses for the context
    common_responses = [
        "That's interesting! Can you tell me more?",
        "I understand. What do you think about that?",
        "Great! How did that make you feel?",
        "That sounds challenging. How did you handle it?",
        "Excellent! What happened next?"
    ]
    
    for i, response in enumerate(common_responses):
        cache_key = f"mobile_response:{context}:{i}"
        await caching_service.set(cache_key, response, timedelta(days=1))

async def _get_conversation_starters(context: str) -> List[str]:
    """Get conversation starters for mobile session"""
    starters = {
        "daily_life": [
            "How was your day today?",
            "What's your favorite hobby?",
            "Tell me about your weekend plans.",
        ],
        "business": [
            "What do you do for work?",
            "Describe your ideal workplace.",
            "What's your biggest professional challenge?",
        ],
        "travel": [
            "Where would you like to visit next?",
            "What's the most interesting place you've been?",
            "Do you prefer city trips or nature adventures?",
        ]
    }
    
    return starters.get(context, starters["daily_life"])

async def _get_offline_content_summary(user_id: int) -> Dict[str, Any]:
    """Get summary of available offline content"""
    return {
        "conversations_available": 10,
        "exercises_available": 25,
        "vocabulary_items": 100,
        "audio_samples": 15,
        "last_updated": datetime.utcnow().isoformat()
    }

async def _schedule_comprehensive_audio_analysis(
    audio_data_base64: str,
    user_id: int,
    expected_text: str,
    session_id: str
):
    """Schedule comprehensive audio analysis as background task"""
    task = process_audio_comprehensive.delay(
        audio_data_base64, user_id, expected_text, "comprehensive"
    )
    
    # Store task ID for mobile app to check status
    await caching_service.set(
        f"mobile_audio_task:{session_id}",
        {"task_id": task.id, "status": "processing"},
        timedelta(hours=1)
    )

async def _schedule_comprehensive_writing_analysis(
    text: str,
    user_id: int,
    writing_type: str,
    user_level: str,
    session_id: str
):
    """Schedule comprehensive writing analysis as background task"""
    task = analyze_writing_comprehensive.delay(
        text, user_id, writing_type, user_level, "comprehensive"
    )
    
    # Store task ID for mobile app to check status
    await caching_service.set(
        f"mobile_writing_task:{session_id}",
        {"task_id": task.id, "status": "processing"},
        timedelta(hours=1)
    )

# Additional helper functions (simplified implementations)
async def _store_offline_session(user_id: int, session_data: Dict, db: AsyncSession):
    """Store offline session data"""
    # Implementation would store session in database
    pass

async def _store_exercise_completion(user_id: int, completion_data: Dict, db: AsyncSession):
    """Store exercise completion data"""
    # Implementation would store completion in database
    pass

async def _update_study_time(user_id: int, minutes: int, db: AsyncSession):
    """Update user's total study time"""
    # Implementation would update user progress
    pass

async def _get_server_updates_since(user_id: int, since: datetime, db: AsyncSession) -> List[Dict]:
    """Get server updates since timestamp"""
    return []  # Mock implementation

async def _get_offline_conversations(user_id: int, max_count: int) -> List[Dict]:
    """Get conversations for offline use"""
    return []  # Mock implementation

async def _get_offline_exercises(user_id: int, level: DifficultyLevel, max_count: int) -> List[Dict]:
    """Get exercises for offline use"""
    return []  # Mock implementation

async def _get_offline_vocabulary(user_id: int, level: DifficultyLevel, max_count: int) -> List[Dict]:
    """Get vocabulary for offline use"""
    return []  # Mock implementation

async def _get_offline_audio_samples(user_id: int, include_audio: bool) -> List[Dict]:
    """Get audio samples for offline use"""
    return []  # Mock implementation

async def _get_cached_ai_responses(user_id: int, max_count: int) -> List[Dict]:
    """Get cached AI responses"""
    return []  # Mock implementation

def _estimate_package_size(package: Dict) -> float:
    """Estimate package size in MB"""
    return 5.0  # Mock implementation

async def _quick_vocabulary_practice(content: str, level: DifficultyLevel) -> Dict:
    """Quick vocabulary practice"""
    return {
        "feedback": "Good vocabulary usage!",
        "score": 85,
        "suggestions": ["Try using synonyms", "Practice with context"]
    }

async def _quick_pronunciation_practice(audio_data: Optional[str], content: str, user_id: int) -> Dict:
    """Quick pronunciation practice"""
    return {
        "feedback": "Clear pronunciation!",
        "score": 80,
        "suggestions": ["Work on intonation", "Practice word stress"]
    }

async def _quick_grammar_practice(content: str, level: DifficultyLevel) -> Dict:
    """Quick grammar practice"""
    return {
        "feedback": "Grammar looks good!",
        "score": 90,
        "suggestions": ["Check verb tenses", "Use more complex sentences"]
    }

async def _generate_quick_text_feedback(content: str, level: DifficultyLevel) -> Dict:
    """Generate quick text feedback"""
    return {
        "message": "Great writing!",
        "score": 85,
        "tips": ["Good structure", "Clear ideas"],
        "encouragement": "Keep up the excellent work!"
    }

async def _generate_quick_pronunciation_feedback(audio_data: Optional[str], content: str, user_id: int) -> Dict:
    """Generate quick pronunciation feedback"""
    return {
        "message": "Nice pronunciation!",
        "score": 82,
        "tips": ["Clear consonants", "Good rhythm"],
        "encouragement": "Your speaking is improving!"
    }

async def _update_user_notification_settings(user_id: int, settings: MobileNotificationSettings, db: AsyncSession):
    """Update user notification settings"""
    # Implementation would update user settings in database
    pass

async def _schedule_daily_reminders(user_id: int, reminder_time: str):
    """Schedule daily study reminders"""
    # Implementation would schedule notifications
    pass

def _calculate_next_reminder(reminder_time: str) -> Optional[datetime]:
    """Calculate next reminder time"""
    # Implementation would calculate next reminder
    return datetime.utcnow() + timedelta(days=1)
