import asyncio
import base64
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from app.core.config import settings

logger = logging.getLogger(__name__)


class SpeechaceService:
    """
    Service for integrating with Speechace API for speech pronunciation assessment.

    Speechace provides comprehensive speech evaluation including:
    - Pronunciation scoring
    - Fluency analysis
    - Word-level feedback
    - Phoneme-level assessment
    """

    def __init__(self):
        self.api_key = getattr(settings, "SPEECHACE_API_KEY", None)
        self.base_url = "https://api.speechace.co"
        self.timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout

    async def assess_pronunciation(
        self,
        audio_bytes: bytes,
        reference_text: str,
        user_id: Optional[str] = None,
        include_phoneme_scores: bool = True,
        include_fluency: bool = True
    ) -> Dict[str, Any]:
        """
        Assess pronunciation using Speechace API.

        Args:
            audio_bytes: Raw audio data (WAV, MP3, etc.)
            reference_text: The text the user was supposed to speak
            user_id: Optional user identifier for tracking
            include_phoneme_scores: Whether to include detailed phoneme analysis
            include_fluency: Whether to include fluency analysis

        Returns:
            Dict containing assessment results
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Speechace API key not configured",
                "assessment": None
            }

        try:
            # Decide endpoint: use text scoring when reference_text is provided; use open-ended speech when no text.
            use_open_ended = not reference_text or reference_text.strip() == ""

            async def _post_to_speechace(endpoint: str, form: aiohttp.FormData, params: Dict[str, Any], tag: str):
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(endpoint, params=params, data=form, headers={"Accept": "application/json"}) as response:
                        ct = (response.headers.get("Content-Type") or "").lower()
                        if "application/json" in ct:
                            response_data = await response.json()
                        else:
                            response_text = await response.text()
                            logger.error(f"Speechace non-JSON response ({response.status}): {response_text[:200]}")
                            return {
                                "success": False,
                                "error": f"API request failed: {response.status}",
                                "assessment": None,
                                "raw_response": {"content_type": ct, "body": response_text[:500]}
                            }

                        if response.status == 200:
                            status_field = (response_data.get("status") or "").lower()
                            if status_field and status_field != "success":
                                return {
                                    "success": False,
                                    "error": response_data.get("detail_message") or response_data.get("short_message") or "Speechace returned error status",
                                    "assessment": None,
                                    "raw_response": response_data
                                }
                            parsed_assessment = self._parse_assessment_response(response_data)
                            return {
                                "success": True,
                                "assessment": parsed_assessment,
                                "raw_response": response_data
                            }
                        else:
                            logger.error(f"Speechace API error: {response.status} - {response_data}")
                            return {
                                "success": False,
                                "error": f"API request failed: {response.status}",
                                "assessment": None,
                                "raw_response": response_data
                            }

            # Build params common
            params = {"key": self.api_key, "dialect": "en-us"}

            # Strategy: if reference_text exists, use text scoring; otherwise open-ended speech.
            if use_open_ended:
                form = aiohttp.FormData()
                form.add_field("user_audio_file", audio_bytes, filename="audio.wav", content_type="audio/wav")
                if user_id:
                    form.add_field("user_id", user_id)
                form.add_field("include_ielts_feedback", "0")

                primary = await _post_to_speechace(f"{self.base_url}/api/scoring/speech/v9.9/json", form, params, "speech-open-ended")
                # If plan does not support open-ended and reference text is actually present, fall back to text scoring
                if (not primary.get("success")) and reference_text:
                    form_text = aiohttp.FormData()
                    form_text.add_field("text", reference_text)
                    form_text.add_field("user_audio_file", audio_bytes, filename="audio.wav", content_type="audio/wav")
                    if user_id:
                        form_text.add_field("user_id", user_id)
                    form_text.add_field("include_fluency", "true" if include_fluency else "false")
                    form_text.add_field("include_phoneme", "true" if include_phoneme_scores else "false")
                    fallback = await _post_to_speechace(f"{self.base_url}/api/scoring/text/v9.9/json", form_text, params, "text-fallback")
                    if fallback.get("success"):
                        return fallback
                return primary
            else:
                form_text = aiohttp.FormData()
                form_text.add_field("text", reference_text)
                form_text.add_field("user_audio_file", audio_bytes, filename="audio.wav", content_type="audio/wav")
                if user_id:
                    form_text.add_field("user_id", user_id)
                form_text.add_field("include_fluency", "true" if include_fluency else "false")
                form_text.add_field("include_phoneme", "true" if include_phoneme_scores else "false")

                return await _post_to_speechace(f"{self.base_url}/api/scoring/text/v9.9/json", form_text, params, "text-primary")

        except aiohttp.ClientError as e:
            logger.error(f"Speechace API network error: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "assessment": None
            }
        except Exception as e:
            logger.error(f"Speechace API unexpected error: {e}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "assessment": None
            }

    def _parse_assessment_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the Speechace API response into a standardized format.

        This method adapts the Speechace response format to our internal schema.
        """
        try:
            # Extract key metrics; support text scoring (text_score), speech scoring, and quality_score.
            text_score = response_data.get("text_score", {}) or {}
            speech_score = response_data.get("speech_score", {}) or {}
            
            # IMPORTANT: For text scoring API, the quality scores are in text_score.speechace_score
            # The structure is: text_score -> speechace_score -> {overall, pronunciation, fluency}
            quality = (
                response_data.get("quality_score", {})
                or text_score.get("speechace_score", {})  # THIS IS THE KEY FIX - text_score.speechace_score
                or speech_score.get("speechace_score", {})
                or text_score.get("quality_score", {})
                or {}
            )

            # Pronunciation score - check speechace_score first (most reliable for pronunciation-only plans)
            pronunciation = (
                quality.get("pronunciation")
                or text_score.get("pronunciation_score")
                or text_score.get("pronunciation")
                or 0.0
            )
            
            # Extract overall score - fallback to pronunciation if not available (for pronunciation-only plans)
            overall = (
                quality.get("overall")
                or text_score.get("overall_score")
                or text_score.get("overall")
                or pronunciation  # Use pronunciation as overall if no overall score available
                or 0.0
            )
            
            # Fluency score - may not be available in pronunciation-only plans
            fluency = (
                quality.get("fluency") 
                or text_score.get("fluency_score") 
                or text_score.get("fluency") 
                or 0.0
            )
            accuracy = quality.get("accuracy") or text_score.get("accuracy") or 0.0

            # Transcript is in text_score.text for text scoring API
            transcript_text = (
                text_score.get("text")  # text scoring API returns transcript here
                or text_score.get("transcript")
                or speech_score.get("transcript")
                or response_data.get("transcript", {}).get("text", "")
                or ""
            )

            # Extract detailed feedback from Speechace response
            word_scores = self._extract_word_scores(response_data)
            phoneme_scores = self._extract_phoneme_scores(response_data)
            detailed_word_feedback = self._extract_detailed_word_feedback(response_data)
            pronunciation_issues = self._extract_pronunciation_issues(detailed_word_feedback)
            
            assessment = {
                "overall_score": overall * 100 if overall <= 1 else overall,
                "pronunciation_score": pronunciation * 100 if pronunciation <= 1 else pronunciation,
                "fluency_score": fluency * 100 if fluency <= 1 else fluency,
                "accuracy_score": accuracy * 100 if accuracy <= 1 else accuracy,
                "transcribed_text": transcript_text,
                "word_scores": word_scores,
                "phoneme_scores": phoneme_scores,
                "detailed_word_feedback": detailed_word_feedback,  # New: detailed per-word feedback
                "pronunciation_issues": pronunciation_issues,  # New: issues for Flutter display
                "feedback": self._generate_feedback(response_data),
                "suggestions": self._generate_suggestions_from_words(detailed_word_feedback),
                "confidence": response_data.get("confidence", 0.0),
                "processing_time_ms": response_data.get("processing_time", 0),
                "language_detected": response_data.get("language", "en-US")
            }

            return assessment

        except Exception as e:
            logger.error(f"Error parsing Speechace response: {e}")
            return {
                "overall_score": 0.0,
                "pronunciation_score": 0.0,
                "fluency_score": 0.0,
                "accuracy_score": 0.0,
                "transcribed_text": "",
                "word_scores": {},
                "phoneme_scores": {},
                "feedback": "Assessment parsing failed",
                "suggestions": ["Please try again"],
                "confidence": 0.0,
                "processing_time_ms": 0,
                "language_detected": "unknown"
            }

    def _extract_word_scores(self, response_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract word-level pronunciation scores."""
        word_scores = {}

        try:
            # Support both text and speech responses
            words_data = response_data.get("words", [])
            if not words_data:
                words_data = response_data.get("speech_score", {}).get("word_score_list", [])
            if not words_data:
                words_data = response_data.get("text_score", {}).get("word_score_list", [])

            for word_info in words_data:
                word = word_info.get("word") or word_info.get("text") or ""
                score = (
                    word_info.get("score")
                    or word_info.get("pronunciation_score")
                    or word_info.get("quality_score")
                    or 0.0
                )
                if word:
                    word_scores[word] = score * 100 if score <= 1 else score  # normalize if 0-1
        except Exception as e:
            logger.error(f"Error extracting word scores: {e}")

        return word_scores

    def _extract_detailed_word_feedback(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract detailed word-level feedback including syllables and phonemes."""
        word_feedback = []

        try:
            words_data = response_data.get("text_score", {}).get("word_score_list", [])
            if not words_data:
                words_data = response_data.get("speech_score", {}).get("word_score_list", [])

            for word_info in words_data:
                word = word_info.get("word", "")
                quality_score = word_info.get("quality_score", 0)
                
                # Extract syllable feedback
                syllables = []
                for syl in word_info.get("syllable_score_list", []):
                    syllables.append({
                        "letters": syl.get("letters", ""),
                        "score": syl.get("quality_score", 0),
                        "stress_level": syl.get("stress_level"),
                        "stress_score": syl.get("stress_score", 0),
                    })
                
                # Extract phoneme feedback
                phonemes = []
                for phone in word_info.get("phone_score_list", []):
                    phoneme_data = {
                        "phoneme": phone.get("phone", ""),
                        "score": phone.get("quality_score", 0),
                        "sound_most_like": phone.get("sound_most_like"),
                    }
                    # Check for mispronunciation
                    if phone.get("sound_most_like") and phone.get("sound_most_like") != phone.get("phone"):
                        phoneme_data["issue"] = f"Sounds like '{phone.get('sound_most_like')}' instead of '{phone.get('phone')}'"
                    phonemes.append(phoneme_data)
                
                word_feedback.append({
                    "word": word,
                    "score": quality_score,
                    "syllables": syllables,
                    "phonemes": phonemes,
                })
        except Exception as e:
            logger.error(f"Error extracting detailed word feedback: {e}")

        return word_feedback

    def _extract_phoneme_scores(self, response_data: Dict[str, Any]) -> Dict[str, float]:
        """Extract phoneme-level pronunciation scores."""
        phoneme_scores = {}

        try:
            # For Speechace, phonemes are inside word_score_list -> phone_score_list
            words_data = response_data.get("text_score", {}).get("word_score_list", [])
            if not words_data:
                words_data = response_data.get("speech_score", {}).get("word_score_list", [])
            
            for word_info in words_data:
                for phone in word_info.get("phone_score_list", []):
                    phoneme = phone.get("phone", "")
                    score = phone.get("quality_score", 0.0)
                    if phoneme:
                        # Average scores for repeated phonemes
                        if phoneme in phoneme_scores:
                            phoneme_scores[phoneme] = (phoneme_scores[phoneme] + score) / 2
                        else:
                            phoneme_scores[phoneme] = score
        except Exception as e:
            logger.error(f"Error extracting phoneme scores: {e}")

        return phoneme_scores

    def _extract_pronunciation_issues(self, detailed_word_feedback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract pronunciation issues from detailed word feedback for Flutter display."""
        issues = []
        
        try:
            for word_data in detailed_word_feedback:
                word = word_data.get("word", "")
                score = word_data.get("score", 100)
                
                # Flag words with low scores (below 70)
                if score < 70:
                    # Check for specific phoneme issues
                    phoneme_issues = []
                    for phoneme in word_data.get("phonemes", []):
                        if phoneme.get("issue"):
                            phoneme_issues.append(phoneme["issue"])
                        elif phoneme.get("score", 100) < 50:
                            phoneme_issues.append(f"Phoneme '{phoneme.get('phoneme')}' needs work")
                    
                    issue_text = "; ".join(phoneme_issues) if phoneme_issues else f"Pronunciation score: {score}/100"
                    suggestion = f"Practice saying '{word}' more clearly"
                    
                    issues.append({
                        "word": word,
                        "issue": issue_text,
                        "suggestion": suggestion,
                        "score": score,
                    })
        except Exception as e:
            logger.error(f"Error extracting pronunciation issues: {e}")
        
        return issues[:10]  # Limit to top 10 issues

    def _generate_suggestions_from_words(self, detailed_word_feedback: List[Dict[str, Any]]) -> List[str]:
        """Generate improvement suggestions based on detailed word analysis."""
        suggestions = []
        
        try:
            # Find words that need the most improvement (lowest scores)
            problem_words = sorted(
                [w for w in detailed_word_feedback if w.get("score", 100) < 70],
                key=lambda x: x.get("score", 100)
            )[:5]
            
            if problem_words:
                word_list = ", ".join([w["word"] for w in problem_words])
                suggestions.append(f"Focus on these words: {word_list}")
            
            # Find common phoneme issues
            problem_phonemes = {}
            for word_data in detailed_word_feedback:
                for phoneme in word_data.get("phonemes", []):
                    if phoneme.get("score", 100) < 60:
                        ph = phoneme.get("phoneme", "")
                        if ph:
                            problem_phonemes[ph] = problem_phonemes.get(ph, 0) + 1
            
            if problem_phonemes:
                top_phonemes = sorted(problem_phonemes.items(), key=lambda x: -x[1])[:3]
                phoneme_list = ", ".join([f"'{p[0]}'" for p in top_phonemes])
                suggestions.append(f"Practice these sounds: {phoneme_list}")
            
            # Check for syllable stress issues
            stress_issues = 0
            for word_data in detailed_word_feedback:
                for syl in word_data.get("syllables", []):
                    if syl.get("stress_score", 100) < 70:
                        stress_issues += 1
            
            if stress_issues > 2:
                suggestions.append("Work on syllable stress and emphasis")
            
            # Default suggestions if none found
            if not suggestions:
                suggestions = [
                    "Good pronunciation overall!",
                    "Continue practicing for even better results",
                ]
        except Exception as e:
            logger.error(f"Error generating suggestions from words: {e}")
            suggestions = ["Continue practicing regularly"]
        
        return suggestions

    def _generate_feedback(self, response_data: Dict[str, Any]) -> str:
        """Generate human-readable feedback from assessment results."""
        try:
            # Get score from multiple possible locations (pronunciation-only plans may not have overall)
            text_score = response_data.get("text_score", {}) or {}
            speechace_score = text_score.get("speechace_score", {}) or {}
            overall_score = (
                response_data.get("quality_score", {}).get("overall", 0.0) * 100
                or speechace_score.get("overall", 0.0)
                or speechace_score.get("pronunciation", 0.0)  # Fallback for pronunciation-only plans
                or 0.0
            )
            # Ensure it's on 0-100 scale
            if overall_score <= 1:
                overall_score = overall_score * 100

            if overall_score >= 90:
                return "Excellent pronunciation! Keep up the great work."
            elif overall_score >= 80:
                return "Very good pronunciation with minor areas for improvement."
            elif overall_score >= 70:
                return "Good pronunciation, but there are some areas that need attention."
            elif overall_score >= 60:
                return "Fair pronunciation. Focus on the identified issues."
            else:
                return "Pronunciation needs significant improvement. Practice regularly."

        except Exception as e:
            logger.error(f"Error generating feedback: {e}")
            return "Assessment completed, but feedback generation failed."

    def _generate_suggestions(self, response_data: Dict[str, Any]) -> List[str]:
        """Generate improvement suggestions based on assessment."""
        suggestions = []

        try:
            # Analyze different aspects and provide targeted suggestions
            quality_scores = response_data.get("quality_score", {})

            pronunciation_score = quality_scores.get("pronunciation", 0.0)
            fluency_score = quality_scores.get("fluency", 0.0)

            if pronunciation_score < 0.7:
                suggestions.append("Focus on individual sound pronunciation")
                suggestions.append("Practice difficult phonemes with a mirror")

            if fluency_score < 0.7:
                suggestions.append("Work on speaking at a consistent pace")
                suggestions.append("Reduce long pauses between words")

            # Add word-specific suggestions
            words_data = response_data.get("words", [])
            difficult_words = [
                word_info.get("word") for word_info in words_data
                if word_info.get("score", 1.0) < 0.6
            ][:3]  # Limit to top 3 difficult words

            if difficult_words:
                suggestions.append(f"Practice these words: {', '.join(difficult_words)}")

            # If no specific issues found, provide general advice
            if not suggestions:
                suggestions = [
                    "Continue practicing regularly",
                    "Record yourself and compare with native speakers",
                    "Focus on natural intonation patterns"
                ]

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            suggestions = ["Practice regularly and focus on clear articulation"]

        return suggestions

    async def get_supported_languages(self) -> List[str]:
        """Get list of supported languages from Speechace."""
        # This would typically call a Speechace endpoint to get supported languages
        # For now, return common supported languages
        return ["en-US", "en-GB", "es-ES", "fr-FR", "de-DE", "it-IT", "pt-BR", "ja-JP", "ko-KR", "zh-CN"]

    async def validate_audio_format(self, audio_bytes: bytes) -> Tuple[bool, str]:
        """
        Validate that the audio format is supported by Speechace.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Basic validation - check if it's a common audio format
            # Speechace typically supports WAV, MP3, M4A, FLAC
            if len(audio_bytes) < 44:  # Minimum WAV header size
                return False, "Audio file too small"

            # Check for common audio file signatures
            signatures = {
                b'RIFF': 'WAV',
                b'\xFF\xFB': 'MP3',
                b'\xFF\xF3': 'MP3',
                b'\xFF\xF2': 'MP3',
                b'ID3': 'MP3',
                b'fLaC': 'FLAC',
                b'ftypM4A': 'M4A'
            }

            for signature, format_name in signatures.items():
                if audio_bytes.startswith(signature):
                    return True, f"Supported format: {format_name}"

            return False, "Unsupported audio format. Use WAV, MP3, M4A, or FLAC."

        except Exception as e:
            return False, f"Audio validation error: {str(e)}"




