import asyncio
import json
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import statistics
from collections import Counter
import hashlib

import google.generativeai as genai
from textstat import flesch_reading_ease, flesch_kincaid_grade
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.cache import get_redis
from app.models.content import DifficultyLevel
from app.models.writing import WritingType, WritingSkillLevel

logger = logging.getLogger(__name__)

class WritingAnalysisType(str, Enum):
    COMPREHENSIVE = "comprehensive"
    GRAMMAR_ONLY = "grammar_only"
    VOCABULARY_ONLY = "vocabulary_only"
    STRUCTURE_ONLY = "structure_only"
    STYLE_ONLY = "style_only"
    QUICK_FEEDBACK = "quick_feedback"

class FeedbackLevel(str, Enum):
    BASIC = "basic"
    DETAILED = "detailed"
    EXPERT = "expert"

class WritingAnalysisService:
    """
    Comprehensive writing analysis service providing detailed feedback
    on grammar, vocabulary, structure, style, and content quality
    """
    
    def __init__(self):
        # Initialize AI services
        if settings.GOOGLE_GEMINI_API_KEY:
            genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            self.gemini_model = None
            logger.warning("Google Gemini API key not configured")
        
        self.redis = None
        
        # Analysis configuration
        self.cache_duration_hours = 24
        self.min_text_length = 10
        self.max_text_length = 10000
        
        # Scoring weights
        self.scoring_weights = {
            "grammar": 0.25,
            "vocabulary": 0.20,
            "structure": 0.20,
            "clarity": 0.15,
            "coherence": 0.10,
            "style": 0.10
        }
        
    async def _get_redis(self):
        if not self.redis:
            self.redis = await get_redis()
        return self.redis

    async def analyze_writing_comprehensive(
        self,
        text: str,
        user_id: int,
        writing_type: WritingType = WritingType.ESSAY,
        user_level: DifficultyLevel = DifficultyLevel.B1,
        analysis_type: WritingAnalysisType = WritingAnalysisType.COMPREHENSIVE,
        feedback_level: FeedbackLevel = FeedbackLevel.DETAILED,
        target_improvements: List[str] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive writing analysis with AI-powered feedback
        
        Args:
            text: The text to analyze
            user_id: User ID for personalization and caching
            writing_type: Type of writing (essay, email, etc.)
            user_level: User's proficiency level
            analysis_type: Type of analysis to perform
            feedback_level: Level of detail in feedback
            target_improvements: Specific areas user wants to improve
            
        Returns:
            Comprehensive analysis with scores, feedback, and suggestions
        """
        try:
            # Validate input
            validation_result = self._validate_text_input(text)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result["error"],
                    "error_type": "validation_error"
                }

            # Check cache first
            cache_key = self._generate_cache_key(
                text, writing_type, user_level, analysis_type
            )
            cached_result = await self._get_cached_analysis(cache_key)
            if cached_result:
                logger.info(f"Returning cached writing analysis for user {user_id}")
                return cached_result

            # Perform basic text analysis
            basic_analysis = await self._perform_basic_text_analysis(text)
            
            # Perform AI-powered analysis
            ai_analysis = None
            if self.gemini_model and analysis_type != WritingAnalysisType.QUICK_FEEDBACK:
                ai_analysis = await self._perform_ai_analysis(
                    text, writing_type, user_level, analysis_type, feedback_level
                )

            # Perform specific analysis components
            analysis_results = {}
            
            if analysis_type in [WritingAnalysisType.COMPREHENSIVE, WritingAnalysisType.GRAMMAR_ONLY]:
                analysis_results["grammar"] = await self._analyze_grammar(
                    text, user_level, ai_analysis
                )
            
            if analysis_type in [WritingAnalysisType.COMPREHENSIVE, WritingAnalysisType.VOCABULARY_ONLY]:
                analysis_results["vocabulary"] = await self._analyze_vocabulary(
                    text, user_level, ai_analysis
                )
            
            if analysis_type in [WritingAnalysisType.COMPREHENSIVE, WritingAnalysisType.STRUCTURE_ONLY]:
                analysis_results["structure"] = await self._analyze_structure(
                    text, writing_type, ai_analysis
                )
            
            if analysis_type in [WritingAnalysisType.COMPREHENSIVE, WritingAnalysisType.STYLE_ONLY]:
                analysis_results["style"] = await self._analyze_style(
                    text, writing_type, user_level, ai_analysis
                )
            
            # Always include clarity and coherence for comprehensive analysis
            if analysis_type == WritingAnalysisType.COMPREHENSIVE:
                analysis_results["clarity"] = await self._analyze_clarity(
                    text, basic_analysis, ai_analysis
                )
                analysis_results["coherence"] = await self._analyze_coherence(
                    text, ai_analysis
                )

            # Calculate overall scores
            scores = self._calculate_comprehensive_scores(analysis_results)
            
            # Generate personalized feedback
            feedback = await self._generate_personalized_feedback(
                text, analysis_results, scores, user_level, 
                writing_type, feedback_level, target_improvements
            )
            
            # Generate improvement suggestions
            suggestions = await self._generate_improvement_suggestions(
                analysis_results, scores, user_level, target_improvements
            )
            
            # Create comprehensive result
            result = {
                "success": True,
                "analysis": {
                    "text_metadata": {
                        "word_count": basic_analysis["word_count"],
                        "sentence_count": basic_analysis["sentence_count"],
                        "paragraph_count": basic_analysis["paragraph_count"],
                        "character_count": len(text),
                        "average_sentence_length": basic_analysis["avg_sentence_length"],
                        "readability_score": basic_analysis["readability_score"],
                        "reading_level": basic_analysis["reading_level"]
                    },
                    "scores": scores,
                    "component_analysis": analysis_results,
                    "overall_feedback": feedback,
                    "improvement_suggestions": suggestions,
                    "strengths": await self._identify_strengths(analysis_results, scores),
                    "areas_for_improvement": await self._identify_weaknesses(analysis_results, scores),
                    "next_steps": await self._suggest_next_steps(analysis_results, user_level)
                },
                "metadata": {
                    "user_id": user_id,
                    "writing_type": writing_type.value,
                    "user_level": user_level.value,
                    "analysis_type": analysis_type.value,
                    "feedback_level": feedback_level.value,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "ai_powered": ai_analysis is not None
                }
            }
            
            # Cache the result
            await self._cache_analysis(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Writing analysis error: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "analysis_error"
            }

    async def analyze_writing_real_time(
        self,
        text: str,
        user_id: int,
        session_id: str,
        user_level: DifficultyLevel = DifficultyLevel.B1
    ) -> Dict[str, Any]:
        """
        Real-time writing analysis for live feedback during writing
        
        Args:
            text: Current text being written
            user_id: User ID
            session_id: Writing session ID
            user_level: User's proficiency level
            
        Returns:
            Real-time feedback and suggestions
        """
        try:
            # Quick validation
            if len(text.strip()) < 5:
                return {
                    "success": True,
                    "feedback": {
                        "message": "Keep writing...",
                        "suggestions": [],
                        "live_score": 0
                    }
                }

            # Get session context
            session_context = await self._get_writing_session_context(session_id)
            
            # Perform quick analysis
            quick_analysis = await self._perform_quick_analysis(text, user_level)
            
            # Generate real-time feedback
            live_feedback = {
                "word_count": len(text.split()),
                "character_count": len(text),
                "current_score": quick_analysis["estimated_score"],
                "immediate_suggestions": quick_analysis["immediate_suggestions"],
                "grammar_alerts": quick_analysis["grammar_alerts"],
                "vocabulary_suggestions": quick_analysis["vocabulary_suggestions"],
                "writing_flow": quick_analysis["writing_flow"],
                "session_progress": session_context.get("progress", 0)
            }
            
            # Update session context
            await self._update_writing_session_context(session_id, {
                "current_text": text,
                "live_feedback": live_feedback,
                "updated_at": datetime.utcnow().isoformat()
            })
            
            return {
                "success": True,
                "live_feedback": live_feedback,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Real-time analysis error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def compare_writing_versions(
        self,
        original_text: str,
        revised_text: str,
        user_id: int,
        user_level: DifficultyLevel = DifficultyLevel.B1
    ) -> Dict[str, Any]:
        """
        Compare two versions of writing to show improvement
        
        Args:
            original_text: Original version
            revised_text: Revised version
            user_id: User ID
            user_level: User's proficiency level
            
        Returns:
            Comparison analysis showing improvements and changes
        """
        try:
            # Analyze both versions
            original_analysis = await self.analyze_writing_comprehensive(
                original_text, user_id, user_level=user_level,
                analysis_type=WritingAnalysisType.COMPREHENSIVE
            )
            
            revised_analysis = await self.analyze_writing_comprehensive(
                revised_text, user_id, user_level=user_level,
                analysis_type=WritingAnalysisType.COMPREHENSIVE
            )
            
            if not (original_analysis["success"] and revised_analysis["success"]):
                return {
                    "success": False,
                    "error": "Failed to analyze one or both versions"
                }
            
            # Calculate improvements
            improvements = await self._calculate_improvements(
                original_analysis["analysis"], revised_analysis["analysis"]
            )
            
            # Identify specific changes
            changes = await self._identify_specific_changes(
                original_text, revised_text
            )
            
            # Generate comparison feedback
            comparison_feedback = await self._generate_comparison_feedback(
                improvements, changes, user_level
            )
            
            return {
                "success": True,
                "comparison": {
                    "original_scores": original_analysis["analysis"]["scores"],
                    "revised_scores": revised_analysis["analysis"]["scores"],
                    "improvements": improvements,
                    "specific_changes": changes,
                    "comparison_feedback": comparison_feedback,
                    "overall_improvement": improvements["overall_improvement"],
                    "recommendation": await self._generate_revision_recommendation(improvements)
                },
                "metadata": {
                    "user_id": user_id,
                    "comparison_timestamp": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Writing comparison error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_writing_suggestions(
        self,
        text: str,
        cursor_position: int,
        user_level: DifficultyLevel,
        suggestion_type: str = "all"
    ) -> Dict[str, Any]:
        """
        Get contextual writing suggestions based on cursor position
        
        Args:
            text: Current text
            cursor_position: Current cursor position in text
            user_level: User's proficiency level
            suggestion_type: Type of suggestions (vocabulary, grammar, style, all)
            
        Returns:
            Contextual suggestions for improvement
        """
        try:
            # Analyze context around cursor position
            context = self._extract_cursor_context(text, cursor_position)
            
            # Generate contextual suggestions
            suggestions = await self._generate_contextual_suggestions(
                context, user_level, suggestion_type
            )
            
            return {
                "success": True,
                "suggestions": suggestions,
                "context": context
            }
            
        except Exception as e:
            logger.error(f"Writing suggestions error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # Private helper methods
    def _validate_text_input(self, text: str) -> Dict[str, Any]:
        """Validate text input for analysis"""
        if not text or not text.strip():
            return {"valid": False, "error": "Text cannot be empty"}
        
        if len(text) < self.min_text_length:
            return {"valid": False, "error": f"Text too short (minimum {self.min_text_length} characters)"}
        
        if len(text) > self.max_text_length:
            return {"valid": False, "error": f"Text too long (maximum {self.max_text_length} characters)"}
        
        return {"valid": True}

    def _generate_cache_key(
        self, text: str, writing_type: WritingType, 
        user_level: DifficultyLevel, analysis_type: WritingAnalysisType
    ) -> str:
        """Generate cache key for writing analysis"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return f"writing_analysis:{text_hash}:{writing_type.value}:{user_level.value}:{analysis_type.value}"

    async def _get_cached_analysis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached writing analysis"""
        try:
            redis = await self._get_redis()
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
        return None

    async def _cache_analysis(self, cache_key: str, analysis: Dict[str, Any]):
        """Cache writing analysis result"""
        try:
            redis = await self._get_redis()
            await redis.setex(
                cache_key,
                timedelta(hours=self.cache_duration_hours).total_seconds(),
                json.dumps(analysis, default=str)
            )
        except Exception as e:
            logger.warning(f"Cache storage error: {e}")

    async def _perform_basic_text_analysis(self, text: str) -> Dict[str, Any]:
        """Perform basic statistical text analysis"""
        # Basic statistics
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        paragraphs = text.split('\n\n')
        
        word_count = len(words)
        sentence_count = len([s for s in sentences if s.strip()])
        paragraph_count = len([p for p in paragraphs if p.strip()])
        
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        
        # Readability analysis
        try:
            readability_score = flesch_reading_ease(text)
            reading_level = flesch_kincaid_grade(text)
        except:
            readability_score = 50  # Default moderate readability
            reading_level = 8       # Default 8th grade level
        
        return {
            "word_count": word_count,
            "sentence_count": sentence_count,
            "paragraph_count": paragraph_count,
            "avg_sentence_length": avg_sentence_length,
            "readability_score": readability_score,
            "reading_level": reading_level,
            "unique_words": len(set(word.lower() for word in words)),
            "lexical_diversity": len(set(word.lower() for word in words)) / word_count if word_count > 0 else 0
        }

    async def _perform_ai_analysis(
        self,
        text: str,
        writing_type: WritingType,
        user_level: DifficultyLevel,
        analysis_type: WritingAnalysisType,
        feedback_level: FeedbackLevel
    ) -> Optional[Dict[str, Any]]:
        """Perform AI-powered comprehensive analysis"""
        if not self.gemini_model:
            return None
        
        try:
            prompt = f"""
            Analyze this {writing_type.value} written by a {user_level.value} level English learner.
            
            Text to analyze:
            "{text}"
            
            Provide a comprehensive analysis focusing on:
            1. Grammar accuracy and errors
            2. Vocabulary usage and appropriateness
            3. Text structure and organization
            4. Writing style and tone
            5. Clarity and coherence
            6. Content quality and relevance
            
            For each aspect, provide:
            - A score from 0-100
            - Specific examples of strengths
            - Specific areas for improvement
            - Concrete suggestions for enhancement
            
            Format your response as JSON with the following structure:
            {{
                "grammar": {{
                    "score": 85,
                    "strengths": ["correct verb tenses", "proper punctuation"],
                    "weaknesses": ["subject-verb agreement errors"],
                    "suggestions": ["review subject-verb agreement rules"],
                    "errors": [
                        {{
                            "type": "subject-verb agreement",
                            "original": "The students was happy",
                            "corrected": "The students were happy",
                            "explanation": "Plural subject requires plural verb"
                        }}
                    ]
                }},
                "vocabulary": {{
                    "score": 78,
                    "level_appropriateness": "good",
                    "variety": "moderate",
                    "advanced_words": ["sophisticated", "comprehensive"],
                    "suggestions": ["use more varied vocabulary", "avoid repetition"]
                }},
                "structure": {{
                    "score": 82,
                    "organization": "clear",
                    "paragraph_structure": "good",
                    "transitions": "needs improvement",
                    "suggestions": ["add more transition words", "improve paragraph flow"]
                }},
                "style": {{
                    "score": 75,
                    "tone": "appropriate",
                    "voice": "consistent",
                    "register": "formal",
                    "suggestions": ["vary sentence structure", "improve flow"]
                }},
                "clarity": {{
                    "score": 80,
                    "clear_ideas": true,
                    "logical_flow": true,
                    "ambiguous_parts": ["unclear pronoun reference in paragraph 2"]
                }},
                "coherence": {{
                    "score": 77,
                    "logical_connections": "mostly clear",
                    "topic_consistency": "good",
                    "suggestions": ["improve transitions between ideas"]
                }}
            }}
            """
            
            response = await asyncio.to_thread(
                self.gemini_model.generate_content, prompt
            )
            
            # Parse JSON response
            try:
                ai_analysis = json.loads(response.text.strip())
                return ai_analysis
            except json.JSONDecodeError:
                # If JSON parsing fails, return basic structure
                logger.warning("Failed to parse AI analysis JSON")
                return None
                
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return None

    async def _analyze_grammar(
        self, text: str, user_level: DifficultyLevel, ai_analysis: Optional[Dict]
    ) -> Dict[str, Any]:
        """Analyze grammar with rule-based and AI approaches"""
        if ai_analysis and "grammar" in ai_analysis:
            return ai_analysis["grammar"]
        
        # Fallback rule-based grammar analysis
        grammar_score = 75  # Default score
        errors = []
        suggestions = []
        
        # Simple grammar checks
        if "don't" in text.lower() and user_level in [DifficultyLevel.A1, DifficultyLevel.A2]:
            suggestions.append("Great use of contractions! This shows natural English usage.")
        
        # Check for common errors
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            if sentence.strip():
                # Check for sentence structure
                if not sentence.strip()[0].isupper():
                    errors.append({
                        "type": "capitalization",
                        "text": sentence.strip()[:50],
                        "suggestion": "Start sentences with capital letters"
                    })
        
        return {
            "score": grammar_score,
            "errors": errors,
            "suggestions": suggestions,
            "strengths": ["Clear sentence structure"],
            "areas_for_improvement": ["Minor punctuation issues"]
        }

    async def _analyze_vocabulary(
        self, text: str, user_level: DifficultyLevel, ai_analysis: Optional[Dict]
    ) -> Dict[str, Any]:
        """Analyze vocabulary usage and appropriateness"""
        if ai_analysis and "vocabulary" in ai_analysis:
            return ai_analysis["vocabulary"]
        
        # Basic vocabulary analysis
        words = re.findall(r'\b\w+\b', text.lower())
        word_freq = Counter(words)
        unique_words = len(set(words))
        total_words = len(words)
        
        # Calculate vocabulary diversity
        diversity_ratio = unique_words / total_words if total_words > 0 else 0
        
        # Simple vocabulary level assessment
        advanced_words = [word for word in set(words) if len(word) > 7]
        
        vocab_score = min(100, int(diversity_ratio * 100 + len(advanced_words) * 2))
        
        return {
            "score": vocab_score,
            "diversity_ratio": diversity_ratio,
            "unique_words": unique_words,
            "total_words": total_words,
            "advanced_words": advanced_words[:10],  # Top 10
            "repeated_words": [word for word, count in word_freq.most_common(5) if count > 2],
            "suggestions": [
                "Try using more varied vocabulary",
                "Consider using synonyms for repeated words"
            ]
        }

    async def _analyze_structure(
        self, text: str, writing_type: WritingType, ai_analysis: Optional[Dict]
    ) -> Dict[str, Any]:
        """Analyze text structure and organization"""
        if ai_analysis and "structure" in ai_analysis:
            return ai_analysis["structure"]
        
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Basic structure analysis
        structure_score = 70
        
        # Check paragraph structure
        if len(paragraphs) > 1:
            structure_score += 10
        
        # Check sentence variety
        sentence_lengths = [len(s.split()) for s in sentences]
        if sentence_lengths:
            length_variety = statistics.stdev(sentence_lengths) if len(sentence_lengths) > 1 else 0
            if length_variety > 3:
                structure_score += 10
        
        return {
            "score": min(100, structure_score),
            "paragraph_count": len(paragraphs),
            "sentence_count": len(sentences),
            "avg_paragraph_length": sum(len(p.split()) for p in paragraphs) / len(paragraphs) if paragraphs else 0,
            "sentence_length_variety": length_variety if sentence_lengths else 0,
            "suggestions": [
                "Good paragraph structure",
                "Consider varying sentence lengths more"
            ]
        }

    async def _analyze_style(
        self, text: str, writing_type: WritingType, 
        user_level: DifficultyLevel, ai_analysis: Optional[Dict]
    ) -> Dict[str, Any]:
        """Analyze writing style and tone"""
        if ai_analysis and "style" in ai_analysis:
            return ai_analysis["style"]
        
        # Basic style analysis
        style_score = 75
        
        # Check for passive voice (simple detection)
        passive_indicators = ['was', 'were', 'been', 'being']
        passive_count = sum(1 for word in text.lower().split() if word in passive_indicators)
        
        # Check for varied sentence starters
        sentences = re.split(r'[.!?]+', text)
        sentence_starters = [s.strip().split()[0].lower() for s in sentences if s.strip() and s.strip().split()]
        starter_variety = len(set(sentence_starters)) / len(sentence_starters) if sentence_starters else 0
        
        return {
            "score": style_score,
            "tone": "appropriate",
            "passive_voice_usage": passive_count,
            "sentence_starter_variety": starter_variety,
            "suggestions": [
                "Good overall style",
                "Consider using more active voice" if passive_count > 3 else "Good use of active voice"
            ]
        }

    async def _analyze_clarity(
        self, text: str, basic_analysis: Dict, ai_analysis: Optional[Dict]
    ) -> Dict[str, Any]:
        """Analyze text clarity and readability"""
        if ai_analysis and "clarity" in ai_analysis:
            return ai_analysis["clarity"]
        
        clarity_score = 80
        
        # Use readability score from basic analysis
        readability = basic_analysis["readability_score"]
        if readability > 60:
            clarity_score += 10
        elif readability < 30:
            clarity_score -= 15
        
        return {
            "score": clarity_score,
            "readability_score": readability,
            "clear_structure": True,
            "suggestions": [
                "Text is generally clear",
                "Consider shorter sentences for better readability" if readability < 50 else "Good readability level"
            ]
        }

    async def _analyze_coherence(self, text: str, ai_analysis: Optional[Dict]) -> Dict[str, Any]:
        """Analyze text coherence and logical flow"""
        if ai_analysis and "coherence" in ai_analysis:
            return ai_analysis["coherence"]
        
        # Basic coherence analysis
        coherence_score = 75
        
        # Check for transition words
        transition_words = ['however', 'therefore', 'furthermore', 'moreover', 'additionally', 
                          'consequently', 'meanwhile', 'nevertheless', 'thus', 'hence']
        transition_count = sum(1 for word in text.lower().split() if word in transition_words)
        
        if transition_count > 0:
            coherence_score += min(15, transition_count * 3)
        
        return {
            "score": min(100, coherence_score),
            "transition_words_used": transition_count,
            "logical_flow": "good",
            "suggestions": [
                "Good logical flow",
                "Consider adding more transition words" if transition_count < 2 else "Good use of transitions"
            ]
        }

    def _calculate_comprehensive_scores(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall scores from component analyses"""
        component_scores = {}
        
        for component, analysis in analysis_results.items():
            if isinstance(analysis, dict) and "score" in analysis:
                component_scores[component] = analysis["score"]
        
        # Calculate weighted overall score
        overall_score = 0
        for component, score in component_scores.items():
            weight = self.scoring_weights.get(component, 0.1)
            overall_score += score * weight
        
        return {
            "overall": int(overall_score),
            **component_scores
        }

    async def _generate_personalized_feedback(
        self,
        text: str,
        analysis_results: Dict[str, Any],
        scores: Dict[str, Any],
        user_level: DifficultyLevel,
        writing_type: WritingType,
        feedback_level: FeedbackLevel,
        target_improvements: List[str] = None
    ) -> str:
        """Generate personalized feedback based on analysis"""
        feedback_parts = []
        
        # Overall assessment
        overall_score = scores.get("overall", 75)
        if overall_score >= 90:
            feedback_parts.append("Excellent work! Your writing demonstrates strong English skills.")
        elif overall_score >= 80:
            feedback_parts.append("Great job! Your writing is clear and well-structured.")
        elif overall_score >= 70:
            feedback_parts.append("Good effort! Your writing shows solid understanding with room for improvement.")
        else:
            feedback_parts.append("Keep practicing! Focus on the areas highlighted for improvement.")
        
        # Component-specific feedback
        for component, analysis in analysis_results.items():
            if isinstance(analysis, dict) and "score" in analysis:
                score = analysis["score"]
                if score < 70 and component in ["grammar", "vocabulary", "structure"]:
                    feedback_parts.append(f"Focus on improving your {component}.")
        
        # Level-appropriate encouragement
        if user_level in [DifficultyLevel.A1, DifficultyLevel.A2]:
            feedback_parts.append("You're making great progress in your English learning journey!")
        elif user_level in [DifficultyLevel.B1, DifficultyLevel.B2]:
            feedback_parts.append("Your intermediate skills are developing well. Keep challenging yourself!")
        else:
            feedback_parts.append("Your advanced English skills are impressive. Focus on fine-tuning for perfection!")
        
        return " ".join(feedback_parts)

    async def _generate_improvement_suggestions(
        self,
        analysis_results: Dict[str, Any],
        scores: Dict[str, Any],
        user_level: DifficultyLevel,
        target_improvements: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Generate specific improvement suggestions"""
        suggestions = []
        
        # Priority suggestions based on lowest scores
        sorted_scores = sorted(scores.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)
        
        for component, score in sorted_scores[:3]:  # Top 3 areas for improvement
            if component != "overall" and isinstance(score, (int, float)) and score < 80:
                if component == "grammar":
                    suggestions.append({
                        "category": "Grammar",
                        "priority": "high",
                        "suggestion": "Review basic grammar rules and practice with exercises",
                        "resources": ["grammar exercises", "online grammar checker"]
                    })
                elif component == "vocabulary":
                    suggestions.append({
                        "category": "Vocabulary",
                        "priority": "medium",
                        "suggestion": "Expand your vocabulary by reading more and using a thesaurus",
                        "resources": ["vocabulary building apps", "reading materials"]
                    })
                elif component == "structure":
                    suggestions.append({
                        "category": "Structure",
                        "priority": "high",
                        "suggestion": "Practice organizing your ideas with clear paragraphs and transitions",
                        "resources": ["essay structure guides", "writing templates"]
                    })
        
        return suggestions

    # Additional helper methods (simplified implementations)
    async def _identify_strengths(self, analysis_results: Dict, scores: Dict) -> List[str]:
        """Identify writing strengths"""
        strengths = []
        for component, score in scores.items():
            if isinstance(score, (int, float)) and score >= 80:
                strengths.append(f"Strong {component} skills")
        return strengths or ["Good overall effort"]

    async def _identify_weaknesses(self, analysis_results: Dict, scores: Dict) -> List[str]:
        """Identify areas needing improvement"""
        weaknesses = []
        for component, score in scores.items():
            if isinstance(score, (int, float)) and score < 70:
                weaknesses.append(f"{component.capitalize()} needs improvement")
        return weaknesses or ["Continue practicing for overall improvement"]

    async def _suggest_next_steps(self, analysis_results: Dict, user_level: DifficultyLevel) -> List[str]:
        """Suggest next steps for improvement"""
        return [
            "Practice writing similar texts to reinforce learning",
            "Focus on areas identified for improvement",
            "Read examples of good writing in this style",
            "Consider working with a tutor for personalized guidance"
        ]

    async def _perform_quick_analysis(self, text: str, user_level: DifficultyLevel) -> Dict[str, Any]:
        """Quick analysis for real-time feedback"""
        words = text.split()
        word_count = len(words)
        
        # Quick grammar check
        grammar_alerts = []
        if word_count > 5:
            # Simple checks
            if not text[0].isupper():
                grammar_alerts.append("Start with a capital letter")
        
        return {
            "estimated_score": min(100, word_count * 2 + 50),  # Simple scoring
            "immediate_suggestions": ["Keep writing!" if word_count < 10 else "Good progress!"],
            "grammar_alerts": grammar_alerts,
            "vocabulary_suggestions": [],
            "writing_flow": "good" if word_count > 20 else "developing"
        }

    async def _get_writing_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get writing session context"""
        try:
            redis = await self._get_redis()
            context = await redis.get(f"writing_session:{session_id}")
            return json.loads(context) if context else {}
        except Exception:
            return {}

    async def _update_writing_session_context(self, session_id: str, update_data: Dict[str, Any]):
        """Update writing session context"""
        try:
            redis = await self._get_redis()
            current_context = await self._get_writing_session_context(session_id)
            current_context.update(update_data)
            await redis.setex(
                f"writing_session:{session_id}",
                timedelta(hours=4).total_seconds(),
                json.dumps(current_context, default=str)
            )
        except Exception as e:
            logger.warning(f"Session context update error: {e}")

    # Placeholder methods for advanced features
    async def _calculate_improvements(self, original: Dict, revised: Dict) -> Dict[str, Any]:
        """Calculate improvements between versions"""
        return {"overall_improvement": 10, "improved_areas": ["grammar", "vocabulary"]}

    async def _identify_specific_changes(self, original: str, revised: str) -> List[Dict[str, Any]]:
        """Identify specific changes between versions"""
        return [{"type": "grammar_fix", "change": "Fixed verb tense", "improvement": True}]

    async def _generate_comparison_feedback(self, improvements: Dict, changes: List, user_level: DifficultyLevel) -> str:
        """Generate feedback comparing versions"""
        return "Great improvement! Your revised version shows better grammar and vocabulary usage."

    async def _generate_revision_recommendation(self, improvements: Dict) -> str:
        """Generate recommendation for revision"""
        return "Continue revising to improve clarity and coherence."

    def _extract_cursor_context(self, text: str, cursor_position: int) -> Dict[str, Any]:
        """Extract context around cursor position"""
        start = max(0, cursor_position - 50)
        end = min(len(text), cursor_position + 50)
        return {
            "before": text[start:cursor_position],
            "after": text[cursor_position:end],
            "current_word": "",
            "sentence_context": ""
        }

    async def _generate_contextual_suggestions(
        self, context: Dict, user_level: DifficultyLevel, suggestion_type: str
    ) -> List[Dict[str, Any]]:
        """Generate contextual suggestions"""
        return [
            {"type": "vocabulary", "suggestion": "Consider using a synonym", "replacement": "example"},
            {"type": "grammar", "suggestion": "Check verb tense", "explanation": "Present tense might be more appropriate"}
        ]
