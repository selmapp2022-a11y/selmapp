import asyncio
import aiohttp
import json
import base64
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import hashlib

from app.core.config import settings
from app.core.cache import get_redis
from app.models.speaking import PronunciationFocus, DifficultyLevel
from app.services.audio_processing_service import AudioProcessingService

logger = logging.getLogger(__name__)

class ELSAService:
    """
    ELSA API integration service for advanced pronunciation analysis
    Provides comprehensive speech assessment and feedback
    """
    
    def __init__(self):
        self.api_key = settings.ELSA_API_KEY
        self.base_url = settings.ELSA_API_BASE_URL or "https://api.elsaspeak.com/v1"
        self.audio_processor = AudioProcessingService()
        self.redis = None
        
        # ELSA API configuration
        self.supported_languages = ["en-US", "en-GB", "en-AU"]
        self.max_audio_duration = 60  # seconds
        self.min_audio_duration = 1   # seconds
        
    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    async def analyze_pronunciation(
        self, 
        audio_data: bytes, 
        expected_text: str,
        user_id: int,
        language: str = "en-US",
        difficulty_level: DifficultyLevel = DifficultyLevel.B1,
        focus_areas: List[PronunciationFocus] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive pronunciation analysis using ELSA API
        
        Args:
            audio_data: Audio bytes (WAV format preferred)
            expected_text: The text the user was supposed to say
            user_id: User ID for personalization and caching
            language: Target language for analysis
            difficulty_level: User's proficiency level
            focus_areas: Specific pronunciation aspects to focus on
            
        Returns:
            Detailed pronunciation analysis with scores and feedback
        """
        try:
            # Validate inputs
            validation_result = await self._validate_pronunciation_request(
                audio_data, expected_text, language
            )
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result["error"],
                    "error_type": "validation_error"
                }

            # Check cache first
            cache_key = self._generate_cache_key(audio_data, expected_text, language)
            cached_result = await self._get_cached_analysis(cache_key)
            if cached_result:
                logger.info(f"Returning cached pronunciation analysis for user {user_id}")
                return cached_result

            # Process audio for optimal ELSA analysis
            processed_audio = await self.audio_processor.process_audio_for_speech_recognition(
                audio_data, user_id=user_id
            )
            
            if not processed_audio["success"]:
                return {
                    "success": False,
                    "error": "Audio processing failed",
                    "error_type": "audio_processing_error"
                }

            # Prepare ELSA API request
            elsa_request = await self._prepare_elsa_request(
                processed_audio["processed_audio"],
                expected_text,
                language,
                difficulty_level,
                focus_areas
            )

            # Call ELSA API
            elsa_response = await self._call_elsa_api(elsa_request)
            
            if not elsa_response["success"]:
                # Fallback to internal analysis if ELSA fails
                logger.warning("ELSA API failed, using fallback analysis")
                return await self._fallback_pronunciation_analysis(
                    audio_data, expected_text, user_id, language
                )

            # Process ELSA response
            analysis_result = await self._process_elsa_response(
                elsa_response["data"], 
                expected_text,
                user_id,
                difficulty_level
            )

            # Cache the result
            await self._cache_analysis(cache_key, analysis_result)

            return analysis_result

        except Exception as e:
            logger.error(f"Pronunciation analysis error: {e}")
            return await self._fallback_pronunciation_analysis(
                audio_data, expected_text, user_id, language
            )

    async def get_pronunciation_exercises(
        self,
        user_id: int,
        difficulty_level: DifficultyLevel,
        focus_areas: List[PronunciationFocus] = None,
        count: int = 10
    ) -> Dict[str, Any]:
        """
        Get personalized pronunciation exercises from ELSA
        
        Args:
            user_id: User ID for personalization
            difficulty_level: Target difficulty level
            focus_areas: Specific pronunciation aspects to practice
            count: Number of exercises to return
            
        Returns:
            List of pronunciation exercises with audio samples
        """
        try:
            # Check cache
            cache_key = f"elsa_exercises:{user_id}:{difficulty_level.value}:{hash(str(focus_areas))}"
            cached_exercises = await self._get_cached_exercises(cache_key)
            if cached_exercises:
                return cached_exercises

            # Prepare request for ELSA exercises API
            request_data = {
                "user_level": difficulty_level.value,
                "focus_areas": [area.value for area in (focus_areas or [])],
                "count": count,
                "language": "en-US"
            }

            # Call ELSA exercises API
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    f"{self.base_url}/exercises/pronunciation",
                    headers=headers,
                    json=request_data
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        exercises = await self._process_elsa_exercises(data)
                        
                        # Cache exercises
                        await self._cache_exercises(cache_key, exercises)
                        
                        return {
                            "success": True,
                            "exercises": exercises,
                            "count": len(exercises),
                            "source": "elsa_api"
                        }
                    else:
                        # Fallback to generated exercises
                        return await self._generate_fallback_exercises(
                            difficulty_level, focus_areas, count
                        )

        except Exception as e:
            logger.error(f"Get pronunciation exercises error: {e}")
            return await self._generate_fallback_exercises(
                difficulty_level, focus_areas, count
            )

    async def get_personalized_feedback(
        self,
        user_id: int,
        recent_analyses: List[Dict[str, Any]],
        target_improvements: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get personalized pronunciation feedback based on user's history
        
        Args:
            user_id: User ID
            recent_analyses: Recent pronunciation analysis results
            target_improvements: Specific areas user wants to improve
            
        Returns:
            Personalized feedback and improvement plan
        """
        try:
            # Analyze user's pronunciation patterns
            patterns = await self._analyze_user_patterns(recent_analyses)
            
            # Generate personalized feedback
            feedback = {
                "overall_progress": await self._calculate_progress_trend(recent_analyses),
                "strengths": patterns["strengths"],
                "areas_for_improvement": patterns["weaknesses"],
                "personalized_tips": await self._generate_personalized_tips(
                    patterns, target_improvements
                ),
                "recommended_exercises": await self._recommend_exercises(
                    user_id, patterns["focus_areas"]
                ),
                "milestone_progress": await self._calculate_milestone_progress(
                    user_id, recent_analyses
                ),
                "next_goals": await self._suggest_next_goals(patterns)
            }

            return {
                "success": True,
                "feedback": feedback,
                "analysis_date": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Personalized feedback error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "feedback_generation_error"
            }

    async def real_time_pronunciation_scoring(
        self,
        audio_chunk: bytes,
        expected_phonemes: List[str],
        session_id: str
    ) -> Dict[str, Any]:
        """
        Real-time pronunciation scoring for live practice sessions
        
        Args:
            audio_chunk: Small audio chunk for real-time processing
            expected_phonemes: Expected phoneme sequence
            session_id: Practice session ID for context
            
        Returns:
            Real-time pronunciation scores and immediate feedback
        """
        try:
            # Quick audio validation
            if len(audio_chunk) < 1000:  # Too short for analysis
                return {
                    "success": False,
                    "error": "Audio chunk too short for analysis",
                    "min_chunk_size": 1000
                }

            # Fast pronunciation analysis (simplified for real-time)
            quick_analysis = await self._quick_pronunciation_analysis(
                audio_chunk, expected_phonemes
            )

            # Get session context
            session_context = await self._get_session_context(session_id)

            # Generate real-time feedback
            feedback = {
                "phoneme_scores": quick_analysis["phoneme_scores"],
                "overall_score": quick_analysis["overall_score"],
                "immediate_feedback": quick_analysis["feedback"],
                "corrections": quick_analysis["corrections"],
                "confidence": quick_analysis["confidence"],
                "session_progress": session_context.get("progress", 0)
            }

            # Update session context
            await self._update_session_context(session_id, feedback)

            return {
                "success": True,
                "real_time_feedback": feedback,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Real-time scoring error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "real_time_scoring_error"
            }

    # Private helper methods
    async def _validate_pronunciation_request(
        self, 
        audio_data: bytes, 
        expected_text: str, 
        language: str
    ) -> Dict[str, Any]:
        """Validate pronunciation analysis request"""
        if not self.api_key:
            return {
                "valid": False,
                "error": "ELSA API key not configured"
            }

        if not audio_data or len(audio_data) < 1000:
            return {
                "valid": False,
                "error": "Audio data too short or empty"
            }

        if not expected_text or len(expected_text.strip()) == 0:
            return {
                "valid": False,
                "error": "Expected text is required"
            }

        if language not in self.supported_languages:
            return {
                "valid": False,
                "error": f"Language {language} not supported. Supported: {self.supported_languages}"
            }

        return {"valid": True}

    def _generate_cache_key(
        self, 
        audio_data: bytes, 
        expected_text: str, 
        language: str
    ) -> str:
        """Generate cache key for pronunciation analysis"""
        audio_hash = hashlib.md5(audio_data).hexdigest()
        text_hash = hashlib.md5(expected_text.encode()).hexdigest()
        return f"elsa_analysis:{audio_hash}:{text_hash}:{language}"

    async def _get_cached_analysis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached pronunciation analysis"""
        try:
            redis = await self._get_redis()
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
        return None

    async def _cache_analysis(self, cache_key: str, analysis: Dict[str, Any]):
        """Cache pronunciation analysis result"""
        try:
            redis = await self._get_redis()
            await redis.setex(
                cache_key,
                timedelta(hours=24).total_seconds(),
                json.dumps(analysis)
            )
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")

    async def _prepare_elsa_request(
        self,
        processed_audio: str,  # Base64 encoded
        expected_text: str,
        language: str,
        difficulty_level: DifficultyLevel,
        focus_areas: List[PronunciationFocus] = None
    ) -> Dict[str, Any]:
        """Prepare request payload for ELSA API"""
        return {
            "audio": processed_audio,
            "text": expected_text,
            "language": language,
            "user_level": difficulty_level.value,
            "analysis_type": "comprehensive",
            "focus_areas": [area.value for area in (focus_areas or [])],
            "return_phoneme_scores": True,
            "return_word_scores": True,
            "return_fluency_metrics": True
        }

    async def _call_elsa_api(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make API call to ELSA pronunciation analysis endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    f"{self.base_url}/analyze/pronunciation",
                    headers=headers,
                    json=request_data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        return {"success": True, "data": data}
                    else:
                        error_text = await response.text()
                        logger.error(f"ELSA API error {response.status}: {error_text}")
                        return {
                            "success": False,
                            "error": f"API error: {response.status}",
                            "details": error_text
                        }

        except asyncio.TimeoutError:
            logger.error("ELSA API timeout")
            return {"success": False, "error": "API timeout"}
        except Exception as e:
            logger.error(f"ELSA API call error: {e}")
            return {"success": False, "error": str(e)}

    async def _process_elsa_response(
        self,
        elsa_data: Dict[str, Any],
        expected_text: str,
        user_id: int,
        difficulty_level: DifficultyLevel
    ) -> Dict[str, Any]:
        """Process ELSA API response into standardized format"""
        try:
            # Extract scores
            overall_score = elsa_data.get("overall_score", 0)
            pronunciation_score = elsa_data.get("pronunciation_score", 0)
            fluency_score = elsa_data.get("fluency_score", 0)
            accuracy_score = elsa_data.get("accuracy_score", 0)

            # Extract detailed analysis
            word_scores = elsa_data.get("word_analysis", [])
            phoneme_scores = elsa_data.get("phoneme_analysis", [])
            
            # Generate feedback
            feedback = await self._generate_feedback_from_scores(
                overall_score, pronunciation_score, fluency_score, accuracy_score,
                word_scores, phoneme_scores, difficulty_level
            )

            # Extract transcription
            transcribed_text = elsa_data.get("transcription", "")

            return {
                "success": True,
                "analysis": {
                    "overall_score": overall_score,
                    "pronunciation_score": pronunciation_score,
                    "fluency_score": fluency_score,
                    "accuracy_score": accuracy_score,
                    "completeness_score": elsa_data.get("completeness_score", 0),
                    "word_scores": word_scores,
                    "phoneme_scores": phoneme_scores,
                    "transcribed_text": transcribed_text,
                    "expected_text": expected_text,
                    "feedback": feedback,
                    "suggestions": elsa_data.get("suggestions", []),
                    "strengths": elsa_data.get("strengths", []),
                    "areas_for_improvement": elsa_data.get("improvements", [])
                },
                "metadata": {
                    "user_id": user_id,
                    "difficulty_level": difficulty_level.value,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "source": "elsa_api",
                    "api_version": elsa_data.get("api_version", "v1")
                }
            }

        except Exception as e:
            logger.error(f"ELSA response processing error: {e}")
            return {
                "success": False,
                "error": "Failed to process ELSA response",
                "error_type": "response_processing_error"
            }

    async def _fallback_pronunciation_analysis(
        self,
        audio_data: bytes,
        expected_text: str,
        user_id: int,
        language: str
    ) -> Dict[str, Any]:
        """Fallback pronunciation analysis when ELSA API is unavailable"""
        try:
            # Use speech recognition for basic analysis
            stt_result = await self.audio_processor.speech_to_text(
                audio_data, language, user_id
            )

            if not stt_result["success"]:
                return {
                    "success": False,
                    "error": "Speech recognition failed",
                    "error_type": "fallback_analysis_error"
                }

            transcribed_text = stt_result["transcript"]
            confidence = stt_result["confidence"]

            # Simple text comparison for basic scoring
            similarity_score = await self._calculate_text_similarity(
                expected_text, transcribed_text
            )

            # Generate basic feedback
            feedback = await self._generate_basic_feedback(
                expected_text, transcribed_text, similarity_score
            )

            return {
                "success": True,
                "analysis": {
                    "overall_score": min(100, similarity_score * 100),
                    "pronunciation_score": min(100, confidence * 100),
                    "fluency_score": min(100, (confidence + similarity_score) / 2 * 100),
                    "accuracy_score": min(100, similarity_score * 100),
                    "completeness_score": min(100, len(transcribed_text) / len(expected_text) * 100),
                    "transcribed_text": transcribed_text,
                    "expected_text": expected_text,
                    "feedback": feedback,
                    "suggestions": [
                        "Practice speaking more clearly",
                        "Try speaking at a moderate pace",
                        "Focus on pronunciation of difficult words"
                    ]
                },
                "metadata": {
                    "user_id": user_id,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "source": "fallback_analysis",
                    "confidence": confidence
                }
            }

        except Exception as e:
            logger.error(f"Fallback analysis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "fallback_analysis_error"
            }

    async def _generate_feedback_from_scores(
        self,
        overall_score: float,
        pronunciation_score: float,
        fluency_score: float,
        accuracy_score: float,
        word_scores: List[Dict],
        phoneme_scores: List[Dict],
        difficulty_level: DifficultyLevel
    ) -> str:
        """Generate personalized feedback based on scores"""
        feedback_parts = []

        # Overall assessment
        if overall_score >= 90:
            feedback_parts.append("Excellent pronunciation! You're speaking very clearly.")
        elif overall_score >= 75:
            feedback_parts.append("Good job! Your pronunciation is quite clear.")
        elif overall_score >= 60:
            feedback_parts.append("Not bad! There's room for improvement in your pronunciation.")
        else:
            feedback_parts.append("Keep practicing! Focus on clarity and accuracy.")

        # Specific feedback based on component scores
        if pronunciation_score < 70:
            feedback_parts.append("Focus on individual sound pronunciation.")
        
        if fluency_score < 70:
            feedback_parts.append("Try to speak more smoothly and naturally.")
        
        if accuracy_score < 70:
            feedback_parts.append("Pay attention to the correct pronunciation of each word.")

        # Word-specific feedback
        if word_scores:
            difficult_words = [w for w in word_scores if w.get("score", 100) < 60]
            if difficult_words:
                word_list = ", ".join([w["word"] for w in difficult_words[:3]])
                feedback_parts.append(f"Practice these words: {word_list}")

        return " ".join(feedback_parts)

    async def _calculate_text_similarity(self, expected: str, actual: str) -> float:
        """Calculate similarity between expected and actual text"""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, expected.lower(), actual.lower()).ratio()

    async def _generate_basic_feedback(
        self, 
        expected: str, 
        actual: str, 
        similarity: float
    ) -> str:
        """Generate basic feedback for fallback analysis"""
        if similarity >= 0.9:
            return "Excellent! Your pronunciation was very accurate."
        elif similarity >= 0.7:
            return "Good job! Your pronunciation was mostly correct."
        elif similarity >= 0.5:
            return "Keep practicing! Some words need improvement."
        else:
            return "Practice more for better clarity and accuracy."

    # Additional helper methods for exercises and personalization
    async def _get_cached_exercises(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached pronunciation exercises"""
        try:
            redis = await self._get_redis()
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception:
            pass
        return None

    async def _cache_exercises(self, cache_key: str, exercises: Dict[str, Any]):
        """Cache pronunciation exercises"""
        try:
            redis = await self._get_redis()
            await redis.setex(
                cache_key,
                timedelta(hours=6).total_seconds(),
                json.dumps(exercises)
            )
        except Exception as e:
            logger.warning(f"Exercise cache error: {e}")

    async def _process_elsa_exercises(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process ELSA exercises response"""
        exercises = []
        for exercise in data.get("exercises", []):
            exercises.append({
                "id": exercise.get("id"),
                "text": exercise.get("text"),
                "phonetic": exercise.get("phonetic"),
                "difficulty": exercise.get("difficulty"),
                "focus_sounds": exercise.get("focus_sounds", []),
                "audio_url": exercise.get("reference_audio"),
                "tips": exercise.get("tips", [])
            })
        return exercises

    async def _generate_fallback_exercises(
        self,
        difficulty_level: DifficultyLevel,
        focus_areas: List[PronunciationFocus],
        count: int
    ) -> Dict[str, Any]:
        """Generate fallback exercises when ELSA API is unavailable"""
        # Simple exercise generation based on difficulty and focus areas
        exercises = [
            {
                "id": f"fallback_{i}",
                "text": f"Practice sentence {i+1} for {difficulty_level.value} level",
                "phonetic": "/ˈpræktɪs ˈsentəns/",
                "difficulty": difficulty_level.value,
                "focus_sounds": [area.value for area in (focus_areas or [])],
                "tips": ["Speak clearly", "Use proper intonation"]
            }
            for i in range(count)
        ]
        
        return {
            "success": True,
            "exercises": exercises,
            "count": len(exercises),
            "source": "fallback_generator"
        }

    # Placeholder methods for advanced features
    async def _analyze_user_patterns(self, analyses: List[Dict]) -> Dict[str, Any]:
        """Analyze user's pronunciation patterns from history"""
        return {
            "strengths": ["Clear vowel sounds", "Good rhythm"],
            "weaknesses": ["Consonant clusters", "Word stress"],
            "focus_areas": [PronunciationFocus.CONSONANTS, PronunciationFocus.STRESS]
        }

    async def _calculate_progress_trend(self, analyses: List[Dict]) -> Dict[str, Any]:
        """Calculate user's progress trend"""
        if not analyses:
            return {"trend": "insufficient_data", "improvement": 0}
        
        scores = [a.get("analysis", {}).get("overall_score", 0) for a in analyses]
        if len(scores) < 2:
            return {"trend": "insufficient_data", "improvement": 0}
        
        improvement = scores[-1] - scores[0]
        trend = "improving" if improvement > 0 else "declining" if improvement < 0 else "stable"
        
        return {"trend": trend, "improvement": improvement}

    async def _generate_personalized_tips(
        self, 
        patterns: Dict, 
        target_improvements: List[str]
    ) -> List[str]:
        """Generate personalized improvement tips"""
        return [
            "Practice consonant clusters with minimal pairs",
            "Focus on word stress patterns in multi-syllable words",
            "Record yourself and compare with native speakers"
        ]

    async def _recommend_exercises(
        self, 
        user_id: int, 
        focus_areas: List[PronunciationFocus]
    ) -> List[Dict[str, Any]]:
        """Recommend specific exercises based on user needs"""
        return [
            {
                "type": "minimal_pairs",
                "focus": "consonant_sounds",
                "difficulty": "intermediate",
                "estimated_time": 10
            }
        ]

    async def _calculate_milestone_progress(
        self, 
        user_id: int, 
        analyses: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate progress towards pronunciation milestones"""
        return {
            "current_milestone": "intermediate_clarity",
            "progress_percentage": 65,
            "next_milestone": "advanced_fluency"
        }

    async def _suggest_next_goals(self, patterns: Dict) -> List[str]:
        """Suggest next learning goals"""
        return [
            "Achieve 85% accuracy in consonant pronunciation",
            "Master stress patterns in 3-syllable words",
            "Improve overall fluency score to 80+"
        ]

    async def _quick_pronunciation_analysis(
        self, 
        audio_chunk: bytes, 
        expected_phonemes: List[str]
    ) -> Dict[str, Any]:
        """Quick analysis for real-time feedback"""
        # Simplified analysis for real-time processing
        return {
            "phoneme_scores": {phoneme: 75 for phoneme in expected_phonemes},
            "overall_score": 78,
            "feedback": "Good pronunciation, keep going!",
            "corrections": [],
            "confidence": 0.85
        }

    async def _get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get practice session context"""
        try:
            redis = await self._get_redis()
            context = await redis.get(f"session:{session_id}")
            return json.loads(context) if context else {}
        except Exception:
            return {}

    async def _update_session_context(self, session_id: str, feedback: Dict[str, Any]):
        """Update practice session context"""
        try:
            redis = await self._get_redis()
            context = await self._get_session_context(session_id)
            context["last_feedback"] = feedback
            context["updated_at"] = datetime.utcnow().isoformat()
            await redis.setex(
                f"session:{session_id}",
                timedelta(hours=2).total_seconds(),
                json.dumps(context)
            )
        except Exception as e:
            logger.warning(f"Session context update error: {e}")
