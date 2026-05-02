import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user_websocket
from app.models.user import User
from app.services.enhanced_ai_conversation_service import (
    EnhancedAIConversationService, ConversationContext, ConversationMode, MessageType
)
from app.services.audio_processing_service import AudioProcessingService
from app.services.elsa_service import ELSAService
from app.services.writing_analysis_service import WritingAnalysisService
from app.models.content import DifficultyLevel

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manage WebSocket connections for real-time practice sessions"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_sessions: Dict[int, str] = {}  # user_id -> session_id
        self.session_data: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str, user_id: int):
        """Accept WebSocket connection and store session info"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.user_sessions[user_id] = session_id
        self.session_data[session_id] = {
            "user_id": user_id,
            "connected_at": datetime.utcnow(),
            "session_type": "practice",
            "active": True
        }
        logger.info(f"WebSocket connected: session_id={session_id}, user_id={user_id}")
    
    def disconnect(self, session_id: str):
        """Remove connection and clean up session data"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        
        # Find and remove user session
        user_id = None
        for uid, sid in self.user_sessions.items():
            if sid == session_id:
                user_id = uid
                break
        
        if user_id:
            del self.user_sessions[user_id]
        
        if session_id in self.session_data:
            self.session_data[session_id]["active"] = False
            # Keep session data for a while for potential reconnection
        
        logger.info(f"WebSocket disconnected: session_id={session_id}")
    
    async def send_personal_message(self, session_id: str, message: Dict[str, Any]):
        """Send message to specific session"""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")
                return False
        return False
    
    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        """Send message to user's active session"""
        if user_id in self.user_sessions:
            session_id = self.user_sessions[user_id]
            return await self.send_personal_message(session_id, message)
        return False
    
    def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.session_data.get(session_id)
    
    def update_session_data(self, session_id: str, data: Dict[str, Any]):
        """Update session data"""
        if session_id in self.session_data:
            self.session_data[session_id].update(data)

# Global connection manager
manager = ConnectionManager()

class RealtimePracticeHandler:
    """Handle real-time practice WebSocket communications"""
    
    def __init__(self):
        self.conversation_service = EnhancedAIConversationService()
        self.audio_processor = AudioProcessingService()
        self.elsa_service = ELSAService()
        self.writing_analyzer = WritingAnalysisService()
    
    async def handle_connection(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession
    ):
        """Handle WebSocket connection and message routing"""
        try:
            await manager.connect(websocket, session_id, user.id)
            
            # Send connection confirmation
            await self._send_message(websocket, {
                "type": "connection_established",
                "session_id": session_id,
                "user_id": user.id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Main message handling loop
            while True:
                try:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Route message to appropriate handler
                    await self._route_message(websocket, session_id, user, db, message)
                    
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected: {session_id}")
                    break
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON format")
                except Exception as e:
                    logger.error(f"Message handling error: {e}")
                    await self._send_error(websocket, f"Message processing error: {str(e)}")
        
        except Exception as e:
            logger.error(f"Connection handling error: {e}")
        finally:
            manager.disconnect(session_id)
    
    async def _route_message(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Route incoming message to appropriate handler"""
        message_type = message.get("type")
        
        handlers = {
            "start_conversation": self._handle_start_conversation,
            "send_text_message": self._handle_text_message,
            "send_audio_message": self._handle_audio_message,
            "request_suggestions": self._handle_suggestions_request,
            "start_writing_session": self._handle_start_writing,
            "writing_update": self._handle_writing_update,
            "submit_writing": self._handle_writing_submission,
            "pronunciation_practice": self._handle_pronunciation_practice,
            "end_session": self._handle_end_session,
            "ping": self._handle_ping
        }
        
        handler = handlers.get(message_type)
        if handler:
            await handler(websocket, session_id, user, db, message)
        else:
            await self._send_error(websocket, f"Unknown message type: {message_type}")
    
    async def _handle_start_conversation(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle conversation start request"""
        try:
            context = ConversationContext(message.get("context", "daily_life"))
            mode = ConversationMode(message.get("mode", "practice"))
            difficulty_level = DifficultyLevel(message.get("difficulty_level", user.current_level.value))
            specific_topic = message.get("specific_topic")
            
            # Start conversation session
            result = await self.conversation_service.start_conversation(
                db, user.id, context, mode, difficulty_level, specific_topic
            )
            
            if result["success"]:
                # Update session data
                manager.update_session_data(session_id, {
                    "conversation_session_id": result["session"]["session_id"],
                    "context": context.value,
                    "mode": mode.value
                })
                
                # Send initial AI message
                await self._send_message(websocket, {
                    "type": "conversation_started",
                    "session_data": result["session"],
                    "initial_message": result["initial_message"]
                })
            else:
                await self._send_error(websocket, result.get("error", "Failed to start conversation"))
        
        except Exception as e:
            logger.error(f"Start conversation error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_text_message(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle text message in conversation"""
        try:
            session_data = manager.get_session_data(session_id)
            if not session_data or "conversation_session_id" not in session_data:
                await self._send_error(websocket, "No active conversation session")
                return
            
            conversation_session_id = session_data["conversation_session_id"]
            user_message = message.get("content", "")
            request_feedback = message.get("request_feedback", True)
            
            # Process message through conversation service
            result = await self.conversation_service.process_user_message(
                db, conversation_session_id, user_message, 
                MessageType.USER_TEXT, request_feedback=request_feedback
            )
            
            if result["success"]:
                # Send AI response
                await self._send_message(websocket, {
                    "type": "ai_response",
                    "response": result["ai_response"],
                    "feedback": result.get("feedback"),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Send suggestions if available
                suggestions_result = await self.conversation_service.get_conversation_suggestions(
                    conversation_session_id, "response"
                )
                if suggestions_result["success"]:
                    await self._send_message(websocket, {
                        "type": "suggestions",
                        "suggestions": suggestions_result["suggestions"]
                    })
            else:
                await self._send_error(websocket, result.get("error", "Failed to process message"))
        
        except Exception as e:
            logger.error(f"Text message error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_audio_message(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle audio message with real-time processing"""
        try:
            import base64
            
            session_data = manager.get_session_data(session_id)
            if not session_data or "conversation_session_id" not in session_data:
                await self._send_error(websocket, "No active conversation session")
                return
            
            conversation_session_id = session_data["conversation_session_id"]
            audio_base64 = message.get("audio_data", "")
            expected_text = message.get("expected_text", "")
            
            if not audio_base64:
                await self._send_error(websocket, "No audio data provided")
                return
            
            # Decode audio data
            try:
                audio_data = base64.b64decode(audio_base64)
            except Exception:
                await self._send_error(websocket, "Invalid audio data format")
                return
            
            # Send processing status
            await self._send_message(websocket, {
                "type": "audio_processing",
                "status": "processing",
                "message": "Processing your speech..."
            })
            
            # Process audio
            audio_result = await self.audio_processor.speech_to_text(
                audio_data, user_id=user.id
            )
            
            if not audio_result["success"]:
                await self._send_error(websocket, "Speech recognition failed")
                return
            
            transcribed_text = audio_result["transcript"]
            
            # Send transcription result
            await self._send_message(websocket, {
                "type": "speech_recognized",
                "transcript": transcribed_text,
                "confidence": audio_result["confidence"]
            })
            
            # Pronunciation analysis if expected text provided
            if expected_text:
                pronunciation_result = await self.elsa_service.analyze_pronunciation(
                    audio_data, expected_text, user.id
                )
                
                if pronunciation_result["success"]:
                    await self._send_message(websocket, {
                        "type": "pronunciation_analysis",
                        "analysis": pronunciation_result["analysis"]
                    })
            
            # Process through conversation service
            result = await self.conversation_service.process_user_message(
                db, conversation_session_id, transcribed_text,
                MessageType.USER_AUDIO, audio_data, request_feedback=True
            )
            
            if result["success"]:
                await self._send_message(websocket, {
                    "type": "ai_response",
                    "response": result["ai_response"],
                    "feedback": result.get("feedback"),
                    "audio_analysis": result.get("audio_analysis")
                })
            
        except Exception as e:
            logger.error(f"Audio message error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_start_writing(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle writing session start"""
        try:
            writing_session_id = str(uuid.uuid4())
            writing_type = message.get("writing_type", "essay")
            prompt = message.get("prompt", "")
            
            # Update session data
            manager.update_session_data(session_id, {
                "writing_session_id": writing_session_id,
                "writing_type": writing_type,
                "writing_prompt": prompt,
                "writing_started_at": datetime.utcnow().isoformat()
            })
            
            await self._send_message(websocket, {
                "type": "writing_session_started",
                "writing_session_id": writing_session_id,
                "prompt": prompt,
                "instructions": "Start writing and receive real-time feedback!"
            })
        
        except Exception as e:
            logger.error(f"Start writing error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_writing_update(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle real-time writing updates"""
        try:
            session_data = manager.get_session_data(session_id)
            if not session_data or "writing_session_id" not in session_data:
                await self._send_error(websocket, "No active writing session")
                return
            
            writing_session_id = session_data["writing_session_id"]
            current_text = message.get("text", "")
            
            # Real-time analysis
            analysis_result = await self.writing_analyzer.analyze_writing_real_time(
                current_text, user.id, writing_session_id, user.current_level
            )
            
            if analysis_result["success"]:
                await self._send_message(websocket, {
                    "type": "writing_feedback",
                    "live_feedback": analysis_result["live_feedback"],
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        except Exception as e:
            logger.error(f"Writing update error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_writing_submission(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle writing submission for comprehensive analysis"""
        try:
            final_text = message.get("text", "")
            writing_type = message.get("writing_type", "essay")
            
            # Send processing status
            await self._send_message(websocket, {
                "type": "analysis_processing",
                "status": "analyzing",
                "message": "Analyzing your writing..."
            })
            
            # Comprehensive analysis
            analysis_result = await self.writing_analyzer.analyze_writing_comprehensive(
                final_text, user.id, writing_type=writing_type, 
                user_level=user.current_level
            )
            
            if analysis_result["success"]:
                await self._send_message(websocket, {
                    "type": "writing_analysis_complete",
                    "analysis": analysis_result["analysis"],
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                await self._send_error(websocket, "Writing analysis failed")
        
        except Exception as e:
            logger.error(f"Writing submission error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_pronunciation_practice(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle pronunciation practice session"""
        try:
            import base64
            
            audio_base64 = message.get("audio_data", "")
            target_text = message.get("target_text", "")
            practice_type = message.get("practice_type", "word")
            
            if not audio_base64 or not target_text:
                await self._send_error(websocket, "Audio data and target text required")
                return
            
            # Decode audio
            audio_data = base64.b64decode(audio_base64)
            
            # Send processing status
            await self._send_message(websocket, {
                "type": "pronunciation_processing",
                "status": "analyzing",
                "message": "Analyzing your pronunciation..."
            })
            
            # Real-time pronunciation scoring
            if practice_type == "real_time":
                expected_phonemes = message.get("expected_phonemes", [])
                result = await self.elsa_service.real_time_pronunciation_scoring(
                    audio_data, expected_phonemes, session_id
                )
            else:
                # Comprehensive pronunciation analysis
                result = await self.elsa_service.analyze_pronunciation(
                    audio_data, target_text, user.id, user_level=user.current_level
                )
            
            if result["success"]:
                await self._send_message(websocket, {
                    "type": "pronunciation_result",
                    "analysis": result.get("analysis") or result.get("real_time_feedback"),
                    "practice_type": practice_type
                })
            else:
                await self._send_error(websocket, "Pronunciation analysis failed")
        
        except Exception as e:
            logger.error(f"Pronunciation practice error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_suggestions_request(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle request for conversation suggestions"""
        try:
            session_data = manager.get_session_data(session_id)
            if not session_data or "conversation_session_id" not in session_data:
                await self._send_error(websocket, "No active conversation session")
                return
            
            conversation_session_id = session_data["conversation_session_id"]
            suggestion_type = message.get("suggestion_type", "response")
            
            result = await self.conversation_service.get_conversation_suggestions(
                conversation_session_id, suggestion_type
            )
            
            if result["success"]:
                await self._send_message(websocket, {
                    "type": "suggestions",
                    "suggestions": result["suggestions"],
                    "suggestion_type": suggestion_type
                })
            else:
                await self._send_error(websocket, "Failed to get suggestions")
        
        except Exception as e:
            logger.error(f"Suggestions request error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_end_session(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle session end request"""
        try:
            session_data = manager.get_session_data(session_id)
            user_rating = message.get("rating")
            user_feedback = message.get("feedback")
            
            # End conversation session if active
            if session_data and "conversation_session_id" in session_data:
                conversation_session_id = session_data["conversation_session_id"]
                result = await self.conversation_service.end_conversation(
                    db, conversation_session_id, user_rating, user_feedback
                )
                
                if result["success"]:
                    await self._send_message(websocket, {
                        "type": "session_ended",
                        "summary": result["summary"],
                        "statistics": result["statistics"],
                        "insights": result["insights"]
                    })
            
            # Mark session as ended
            manager.update_session_data(session_id, {
                "ended_at": datetime.utcnow().isoformat(),
                "user_rating": user_rating,
                "user_feedback": user_feedback
            })
        
        except Exception as e:
            logger.error(f"End session error: {e}")
            await self._send_error(websocket, str(e))
    
    async def _handle_ping(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
        db: AsyncSession,
        message: Dict[str, Any]
    ):
        """Handle ping/keepalive message"""
        await self._send_message(websocket, {
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _send_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to WebSocket client"""
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
    
    async def _send_error(self, websocket: WebSocket, error_message: str):
        """Send error message to WebSocket client"""
        await self._send_message(websocket, {
            "type": "error",
            "error": error_message,
            "timestamp": datetime.utcnow().isoformat()
        })

# Global handler instance
practice_handler = RealtimePracticeHandler()

# WebSocket endpoint function
async def websocket_practice_endpoint(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time practice sessions
    
    Supports:
    - Real-time conversation with AI
    - Live pronunciation analysis
    - Real-time writing feedback
    - Interactive learning sessions
    """
    try:
        # Authenticate user (simplified - you may want to implement token-based auth)
        # For now, we'll use a query parameter or header
        user_id = websocket.query_params.get("user_id")
        if not user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User ID required")
            return
        
        # Get user from database
        user = await db.get(User, int(user_id))
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return
        
        # Handle the connection
        await practice_handler.handle_connection(websocket, session_id, user, db)
    
    except Exception as e:
        logger.error(f"WebSocket endpoint error: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal server error")
        except:
            pass
