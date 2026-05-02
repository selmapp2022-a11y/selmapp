import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import statistics
from collections import defaultdict, Counter
import numpy as np
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload

from app.core.cache import get_redis
from app.models.user import User
from app.models.progress import UserProgress, DailyProgress, StudySession
from app.models.exercise import ExerciseAttempt
from app.models.speaking import SpeakingAttempt
from app.models.writing import WritingSubmission
from app.models.personalization import PersonalTrainerInteraction, LearningAnalytics
from app.models.content import DifficultyLevel
from app.crud.progress import user_progress_crud, daily_progress_crud
from app.crud.personalization import learning_analytics

logger = logging.getLogger(__name__)

class AnalyticsMetric(str, Enum):
    """Analytics metrics types"""
    LEARNING_VELOCITY = "learning_velocity"
    SKILL_PROGRESSION = "skill_progression"
    ENGAGEMENT_LEVEL = "engagement_level"
    DIFFICULTY_ADAPTATION = "difficulty_adaptation"
    RETENTION_RATE = "retention_rate"
    MASTERY_PREDICTION = "mastery_prediction"
    WEAKNESS_IDENTIFICATION = "weakness_identification"
    STRENGTH_AMPLIFICATION = "strength_amplification"

class LearningPattern(str, Enum):
    """Learning pattern types"""
    CONSISTENT_DAILY = "consistent_daily"
    WEEKEND_WARRIOR = "weekend_warrior"
    INTENSIVE_BURST = "intensive_burst"
    GRADUAL_IMPROVEMENT = "gradual_improvement"
    PLATEAU_BREAKER = "plateau_breaker"
    RAPID_LEARNER = "rapid_learner"
    STRUGGLING_LEARNER = "struggling_learner"

@dataclass
class LearningInsight:
    """Learning insight data structure"""
    insight_type: str
    title: str
    description: str
    confidence_score: float
    actionable_recommendations: List[str]
    supporting_data: Dict[str, Any]
    priority_level: str  # low, medium, high, critical

@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    overall_score: float
    skill_scores: Dict[str, float]
    improvement_rate: float
    consistency_score: float
    engagement_score: float
    difficulty_progression: float

class LearningAnalyticsEngine:
    """
    Real-time learning analytics engine for comprehensive user analysis
    and personalized learning insights
    """
    
    def __init__(self):
        self.redis_client = None
        
        # Analytics configuration
        self.analysis_window_days = 30
        self.min_sessions_for_analysis = 5
        self.confidence_threshold = 0.7
        
        # Skill weights for overall scoring
        self.skill_weights = {
            "speaking": 0.25,
            "writing": 0.25,
            "listening": 0.20,
            "reading": 0.15,
            "vocabulary": 0.10,
            "grammar": 0.05
        }
        
        # Learning pattern thresholds
        self.pattern_thresholds = {
            "consistent_daily": {"min_days_per_week": 5, "regularity_score": 0.8},
            "weekend_warrior": {"weekend_ratio": 0.7, "weekday_ratio": 0.3},
            "intensive_burst": {"session_length_avg": 45, "frequency_variation": 0.6},
            "gradual_improvement": {"improvement_consistency": 0.8, "slope": 0.1},
            "plateau_breaker": {"plateau_duration": 7, "breakthrough_threshold": 0.15},
            "rapid_learner": {"improvement_rate": 0.3, "consistency": 0.7},
            "struggling_learner": {"decline_rate": -0.1, "low_scores": 0.6}
        }
    
    async def _get_redis(self):
        if not self.redis_client:
            self.redis_client = await get_redis()
        return self.redis_client
    
    async def analyze_user_comprehensive(
        self,
        db: AsyncSession,
        user_id: int,
        analysis_period_days: int = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive user learning analysis
        
        Args:
            db: Database session
            user_id: User ID to analyze
            analysis_period_days: Period for analysis (default: 30 days)
            
        Returns:
            Comprehensive analysis results
        """
        try:
            analysis_period = analysis_period_days or self.analysis_window_days
            cutoff_date = datetime.utcnow() - timedelta(days=analysis_period)
            
            # Get user and basic data
            user = await db.get(User, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Collect user activity data
            activity_data = await self._collect_user_activity_data(
                db, user_id, cutoff_date
            )
            
            if not self._has_sufficient_data(activity_data):
                return await self._generate_insufficient_data_response(user_id)
            
            # Perform various analyses
            analyses = await asyncio.gather(
                self._analyze_performance_metrics(activity_data),
                self._analyze_learning_patterns(activity_data),
                self._analyze_skill_progression(activity_data),
                self._analyze_engagement_levels(activity_data),
                self._analyze_difficulty_adaptation(activity_data),
                self._predict_learning_outcomes(activity_data),
                self._identify_strengths_weaknesses(activity_data),
                return_exceptions=True
            )
            
            # Combine analyses
            performance_metrics = analyses[0] if not isinstance(analyses[0], Exception) else {}
            learning_patterns = analyses[1] if not isinstance(analyses[1], Exception) else []
            skill_progression = analyses[2] if not isinstance(analyses[2], Exception) else {}
            engagement_analysis = analyses[3] if not isinstance(analyses[3], Exception) else {}
            difficulty_analysis = analyses[4] if not isinstance(analyses[4], Exception) else {}
            predictions = analyses[5] if not isinstance(analyses[5], Exception) else {}
            strengths_weaknesses = analyses[6] if not isinstance(analyses[6], Exception) else {}
            
            # Generate insights
            insights = await self._generate_learning_insights(
                user_id, performance_metrics, learning_patterns,
                skill_progression, engagement_analysis, strengths_weaknesses
            )
            
            # Generate recommendations
            recommendations = await self._generate_personalized_recommendations(
                user_id, insights, performance_metrics, predictions
            )
            
            # Create comprehensive analysis result
            analysis_result = {
                "user_id": user_id,
                "analysis_period_days": analysis_period,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "data_quality_score": self._calculate_data_quality_score(activity_data),
                "performance_metrics": performance_metrics,
                "learning_patterns": learning_patterns,
                "skill_progression": skill_progression,
                "engagement_analysis": engagement_analysis,
                "difficulty_analysis": difficulty_analysis,
                "predictions": predictions,
                "strengths_weaknesses": strengths_weaknesses,
                "insights": [insight.__dict__ for insight in insights],
                "recommendations": recommendations,
                "next_analysis_recommended": datetime.utcnow() + timedelta(days=7)
            }
            
            # Cache analysis results
            await self._cache_analysis_results(user_id, analysis_result)
            
            # Store in database
            await self._store_analysis_in_database(db, user_id, analysis_result)
            
            return {
                "success": True,
                "analysis": analysis_result
            }
            
        except Exception as e:
            logger.error(f"Comprehensive analysis error for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_type": "analysis_error"
            }
    
    async def get_real_time_insights(
        self,
        db: AsyncSession,
        user_id: int,
        recent_activity: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate real-time learning insights based on recent activity
        
        Args:
            db: Database session
            user_id: User ID
            recent_activity: Recent user activity data
            
        Returns:
            Real-time insights and recommendations
        """
        try:
            # Get cached analysis for context
            cached_analysis = await self._get_cached_analysis(user_id)
            
            # Analyze recent activity
            real_time_metrics = await self._analyze_real_time_activity(
                recent_activity, cached_analysis
            )
            
            # Generate immediate insights
            immediate_insights = await self._generate_immediate_insights(
                user_id, real_time_metrics, recent_activity
            )
            
            # Check for significant changes
            significant_changes = await self._detect_significant_changes(
                user_id, real_time_metrics, cached_analysis
            )
            
            # Generate adaptive recommendations
            adaptive_recommendations = await self._generate_adaptive_recommendations(
                user_id, real_time_metrics, immediate_insights
            )
            
            return {
                "success": True,
                "real_time_metrics": real_time_metrics,
                "immediate_insights": immediate_insights,
                "significant_changes": significant_changes,
                "adaptive_recommendations": adaptive_recommendations,
                "confidence_score": self._calculate_real_time_confidence(real_time_metrics),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Real-time insights error for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def track_learning_milestone(
        self,
        db: AsyncSession,
        user_id: int,
        milestone_type: str,
        milestone_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Track and analyze learning milestones
        
        Args:
            db: Database session
            user_id: User ID
            milestone_type: Type of milestone (level_up, skill_mastery, etc.)
            milestone_data: Milestone-specific data
            
        Returns:
            Milestone analysis and next goals
        """
        try:
            # Record milestone
            milestone_record = {
                "user_id": user_id,
                "milestone_type": milestone_type,
                "milestone_data": milestone_data,
                "achieved_at": datetime.utcnow(),
                "analysis_context": await self._get_milestone_context(db, user_id)
            }
            
            # Analyze milestone significance
            significance_analysis = await self._analyze_milestone_significance(
                milestone_record
            )
            
            # Update user learning trajectory
            trajectory_update = await self._update_learning_trajectory(
                db, user_id, milestone_record
            )
            
            # Generate next goals
            next_goals = await self._generate_next_learning_goals(
                db, user_id, milestone_record, significance_analysis
            )
            
            # Create celebration message
            celebration_message = await self._generate_celebration_message(
                milestone_type, milestone_data, significance_analysis
            )
            
            return {
                "success": True,
                "milestone_recorded": True,
                "significance_analysis": significance_analysis,
                "trajectory_update": trajectory_update,
                "next_goals": next_goals,
                "celebration_message": celebration_message,
                "milestone_id": milestone_record.get("id")
            }
            
        except Exception as e:
            logger.error(f"Milestone tracking error for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_progress_report(
        self,
        db: AsyncSession,
        user_id: int,
        report_type: str = "weekly"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive progress report
        
        Args:
            db: Database session
            user_id: User ID
            report_type: Type of report (daily, weekly, monthly)
            
        Returns:
            Comprehensive progress report
        """
        try:
            # Determine report period
            period_days = {
                "daily": 1,
                "weekly": 7,
                "monthly": 30
            }.get(report_type, 7)
            
            cutoff_date = datetime.utcnow() - timedelta(days=period_days)
            
            # Collect report data
            report_data = await self._collect_progress_report_data(
                db, user_id, cutoff_date
            )
            
            # Generate report sections
            report_sections = await asyncio.gather(
                self._generate_activity_summary(report_data),
                self._generate_skill_progress_summary(report_data),
                self._generate_achievement_summary(report_data),
                self._generate_challenge_areas_summary(report_data),
                self._generate_goal_progress_summary(db, user_id, report_data),
                return_exceptions=True
            )
            
            # Compile progress report
            progress_report = {
                "user_id": user_id,
                "report_type": report_type,
                "period_days": period_days,
                "report_date": datetime.utcnow().isoformat(),
                "activity_summary": report_sections[0] if not isinstance(report_sections[0], Exception) else {},
                "skill_progress": report_sections[1] if not isinstance(report_sections[1], Exception) else {},
                "achievements": report_sections[2] if not isinstance(report_sections[2], Exception) else {},
                "challenge_areas": report_sections[3] if not isinstance(report_sections[3], Exception) else {},
                "goal_progress": report_sections[4] if not isinstance(report_sections[4], Exception) else {},
                "overall_rating": await self._calculate_overall_period_rating(report_data),
                "motivational_message": await self._generate_motivational_message(report_data),
                "next_period_focus": await self._suggest_next_period_focus(report_data)
            }
            
            return {
                "success": True,
                "report": progress_report
            }
            
        except Exception as e:
            logger.error(f"Progress report error for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Private helper methods for data collection and analysis
    
    async def _collect_user_activity_data(
        self,
        db: AsyncSession,
        user_id: int,
        cutoff_date: datetime
    ) -> Dict[str, Any]:
        """Collect comprehensive user activity data"""
        try:
            # Get study sessions
            study_sessions_query = select(StudySession).where(
                and_(
                    StudySession.user_id == user_id,
                    StudySession.started_at >= cutoff_date
                )
            ).order_by(StudySession.started_at)
            
            study_sessions_result = await db.execute(study_sessions_query)
            study_sessions = study_sessions_result.scalars().all()
            
            # Get exercise attempts
            exercise_attempts_query = select(ExerciseAttempt).where(
                and_(
                    ExerciseAttempt.user_id == user_id,
                    ExerciseAttempt.created_at >= cutoff_date
                )
            ).order_by(ExerciseAttempt.created_at)
            
            exercise_attempts_result = await db.execute(exercise_attempts_query)
            exercise_attempts = exercise_attempts_result.scalars().all()
            
            # Get speaking attempts
            speaking_attempts_query = select(SpeakingAttempt).where(
                and_(
                    SpeakingAttempt.user_id == user_id,
                    SpeakingAttempt.created_at >= cutoff_date
                )
            ).order_by(SpeakingAttempt.created_at)
            
            speaking_attempts_result = await db.execute(speaking_attempts_query)
            speaking_attempts = speaking_attempts_result.scalars().all()
            
            # Get writing submissions
            writing_submissions_query = select(WritingSubmission).where(
                and_(
                    WritingSubmission.user_id == user_id,
                    WritingSubmission.submitted_at >= cutoff_date
                )
            ).order_by(WritingSubmission.submitted_at)
            
            writing_submissions_result = await db.execute(writing_submissions_query)
            writing_submissions = writing_submissions_result.scalars().all()
            
            # Get trainer interactions
            trainer_interactions_query = select(PersonalTrainerInteraction).where(
                and_(
                    PersonalTrainerInteraction.user_profile_id.in_(
                        select(User.id).where(User.id == user_id)
                    ),
                    PersonalTrainerInteraction.created_at >= cutoff_date
                )
            ).order_by(PersonalTrainerInteraction.created_at)
            
            trainer_interactions_result = await db.execute(trainer_interactions_query)
            trainer_interactions = trainer_interactions_result.scalars().all()
            
            return {
                "study_sessions": study_sessions,
                "exercise_attempts": exercise_attempts,
                "speaking_attempts": speaking_attempts,
                "writing_submissions": writing_submissions,
                "trainer_interactions": trainer_interactions,
                "collection_date": datetime.utcnow(),
                "period_start": cutoff_date
            }
            
        except Exception as e:
            logger.error(f"Data collection error for user {user_id}: {e}")
            return {}
    
    def _has_sufficient_data(self, activity_data: Dict[str, Any]) -> bool:
        """Check if there's sufficient data for analysis"""
        if not activity_data:
            return False
        
        total_activities = (
            len(activity_data.get("study_sessions", [])) +
            len(activity_data.get("exercise_attempts", [])) +
            len(activity_data.get("speaking_attempts", [])) +
            len(activity_data.get("writing_submissions", []))
        )
        
        return total_activities >= self.min_sessions_for_analysis
    
    async def _analyze_performance_metrics(
        self, activity_data: Dict[str, Any]
    ) -> PerformanceMetrics:
        """Analyze user performance metrics"""
        try:
            # Calculate skill scores
            skill_scores = {}
            
            # Speaking scores
            speaking_attempts = activity_data.get("speaking_attempts", [])
            if speaking_attempts:
                speaking_scores = [attempt.pronunciation_score or 0 for attempt in speaking_attempts]
                skill_scores["speaking"] = statistics.mean(speaking_scores)
            
            # Writing scores
            writing_submissions = activity_data.get("writing_submissions", [])
            if writing_submissions:
                writing_scores = [submission.overall_score or 0 for submission in writing_submissions]
                skill_scores["writing"] = statistics.mean(writing_scores)
            
            # Exercise scores
            exercise_attempts = activity_data.get("exercise_attempts", [])
            if exercise_attempts:
                exercise_scores = [attempt.score or 0 for attempt in exercise_attempts]
                skill_scores["exercises"] = statistics.mean(exercise_scores)
            
            # Calculate overall score
            overall_score = 0
            total_weight = 0
            for skill, score in skill_scores.items():
                weight = self.skill_weights.get(skill, 0.1)
                overall_score += score * weight
                total_weight += weight
            
            overall_score = overall_score / total_weight if total_weight > 0 else 0
            
            # Calculate improvement rate
            improvement_rate = await self._calculate_improvement_rate(activity_data)
            
            # Calculate consistency score
            consistency_score = await self._calculate_consistency_score(activity_data)
            
            # Calculate engagement score
            engagement_score = await self._calculate_engagement_score(activity_data)
            
            # Calculate difficulty progression
            difficulty_progression = await self._calculate_difficulty_progression(activity_data)
            
            return PerformanceMetrics(
                overall_score=overall_score,
                skill_scores=skill_scores,
                improvement_rate=improvement_rate,
                consistency_score=consistency_score,
                engagement_score=engagement_score,
                difficulty_progression=difficulty_progression
            )
            
        except Exception as e:
            logger.error(f"Performance metrics analysis error: {e}")
            return PerformanceMetrics(0, {}, 0, 0, 0, 0)
    
    async def _analyze_learning_patterns(
        self, activity_data: Dict[str, Any]
    ) -> List[LearningPattern]:
        """Analyze user learning patterns"""
        try:
            patterns = []
            study_sessions = activity_data.get("study_sessions", [])
            
            if not study_sessions:
                return patterns
            
            # Analyze session timing patterns
            session_times = [session.started_at for session in study_sessions]
            weekday_sessions = [t for t in session_times if t.weekday() < 5]
            weekend_sessions = [t for t in session_times if t.weekday() >= 5]
            
            # Check for consistent daily pattern
            unique_days = len(set(t.date() for t in session_times))
            total_days = (max(session_times) - min(session_times)).days + 1
            consistency_ratio = unique_days / total_days if total_days > 0 else 0
            
            if consistency_ratio >= self.pattern_thresholds["consistent_daily"]["regularity_score"]:
                patterns.append(LearningPattern.CONSISTENT_DAILY)
            
            # Check for weekend warrior pattern
            if len(weekend_sessions) > len(weekday_sessions) * 1.5:
                patterns.append(LearningPattern.WEEKEND_WARRIOR)
            
            # Check for intensive burst pattern
            session_durations = [session.duration or 0 for session in study_sessions]
            if session_durations:
                avg_duration = statistics.mean(session_durations)
                if avg_duration > self.pattern_thresholds["intensive_burst"]["session_length_avg"]:
                    patterns.append(LearningPattern.INTENSIVE_BURST)
            
            # Check improvement patterns
            if await self._is_gradual_improver(activity_data):
                patterns.append(LearningPattern.GRADUAL_IMPROVEMENT)
            
            if await self._is_rapid_learner(activity_data):
                patterns.append(LearningPattern.RAPID_LEARNER)
            
            if await self._is_struggling_learner(activity_data):
                patterns.append(LearningPattern.STRUGGLING_LEARNER)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Learning patterns analysis error: {e}")
            return []
    
    # Additional helper methods (simplified implementations)
    
    async def _calculate_improvement_rate(self, activity_data: Dict[str, Any]) -> float:
        """Calculate user's improvement rate"""
        # Implementation would analyze score trends over time
        return 0.15  # Mock improvement rate
    
    async def _calculate_consistency_score(self, activity_data: Dict[str, Any]) -> float:
        """Calculate user's consistency score"""
        # Implementation would analyze regularity of study sessions
        return 0.75  # Mock consistency score
    
    async def _calculate_engagement_score(self, activity_data: Dict[str, Any]) -> float:
        """Calculate user's engagement score"""
        # Implementation would analyze session lengths, completion rates, etc.
        return 0.82  # Mock engagement score
    
    async def _calculate_difficulty_progression(self, activity_data: Dict[str, Any]) -> float:
        """Calculate difficulty progression score"""
        # Implementation would analyze progression through difficulty levels
        return 0.68  # Mock difficulty progression
    
    async def _is_gradual_improver(self, activity_data: Dict[str, Any]) -> bool:
        """Check if user shows gradual improvement pattern"""
        return True  # Mock implementation
    
    async def _is_rapid_learner(self, activity_data: Dict[str, Any]) -> bool:
        """Check if user is a rapid learner"""
        return False  # Mock implementation
    
    async def _is_struggling_learner(self, activity_data: Dict[str, Any]) -> bool:
        """Check if user is struggling"""
        return False  # Mock implementation
    
    async def _generate_learning_insights(
        self, user_id: int, performance: PerformanceMetrics,
        patterns: List[LearningPattern], skill_progression: Dict,
        engagement: Dict, strengths_weaknesses: Dict
    ) -> List[LearningInsight]:
        """Generate actionable learning insights"""
        insights = []
        
        # Performance insight
        if performance.overall_score > 80:
            insights.append(LearningInsight(
                insight_type="performance",
                title="Excellent Progress!",
                description="Your overall performance is outstanding. You're mastering English skills effectively.",
                confidence_score=0.9,
                actionable_recommendations=[
                    "Challenge yourself with advanced content",
                    "Focus on specialized vocabulary",
                    "Practice complex grammar structures"
                ],
                supporting_data={"overall_score": performance.overall_score},
                priority_level="medium"
            ))
        
        # Pattern insight
        if LearningPattern.CONSISTENT_DAILY in patterns:
            insights.append(LearningInsight(
                insight_type="pattern",
                title="Consistent Daily Learner",
                description="You maintain excellent daily study habits. This consistency is key to long-term success.",
                confidence_score=0.85,
                actionable_recommendations=[
                    "Maintain your current schedule",
                    "Gradually increase session duration",
                    "Add variety to prevent monotony"
                ],
                supporting_data={"pattern": "consistent_daily"},
                priority_level="low"
            ))
        
        return insights
    
    # Additional placeholder methods for comprehensive functionality
    
    async def _analyze_skill_progression(self, activity_data: Dict) -> Dict:
        """Analyze progression in different skills"""
        return {"speaking": 0.8, "writing": 0.7, "listening": 0.9}
    
    async def _analyze_engagement_levels(self, activity_data: Dict) -> Dict:
        """Analyze user engagement patterns"""
        return {"average_session_length": 25, "completion_rate": 0.85}
    
    async def _analyze_difficulty_adaptation(self, activity_data: Dict) -> Dict:
        """Analyze how user adapts to difficulty changes"""
        return {"adaptation_rate": 0.7, "optimal_difficulty": "intermediate"}
    
    async def _predict_learning_outcomes(self, activity_data: Dict) -> Dict:
        """Predict future learning outcomes"""
        return {"next_level_eta": 30, "mastery_probability": 0.8}
    
    async def _identify_strengths_weaknesses(self, activity_data: Dict) -> Dict:
        """Identify user strengths and weaknesses"""
        return {
            "strengths": ["vocabulary", "listening"],
            "weaknesses": ["grammar", "pronunciation"]
        }
    
    async def _generate_personalized_recommendations(
        self, user_id: int, insights: List, performance: PerformanceMetrics, predictions: Dict
    ) -> List[str]:
        """Generate personalized learning recommendations"""
        return [
            "Focus more on pronunciation practice",
            "Try advanced conversation topics",
            "Practice writing longer texts"
        ]
    
    def _calculate_data_quality_score(self, activity_data: Dict) -> float:
        """Calculate quality score of available data"""
        return 0.85  # Mock quality score
    
    async def _cache_analysis_results(self, user_id: int, analysis: Dict):
        """Cache analysis results for quick access"""
        try:
            redis = await self._get_redis()
            await redis.setex(
                f"analytics:{user_id}",
                86400,  # 24 hours
                json.dumps(analysis, default=str)
            )
        except Exception as e:
            logger.error(f"Caching error: {e}")
    
    async def _store_analysis_in_database(self, db: AsyncSession, user_id: int, analysis: Dict):
        """Store analysis results in database"""
        try:
            # Create learning analytics record
            analytics_data = {
                "user_id": user_id,
                "analysis_data": analysis,
                "created_at": datetime.utcnow()
            }
            # Would store in database
        except Exception as e:
            logger.error(f"Database storage error: {e}")
    
    # More helper methods (simplified)
    async def _generate_insufficient_data_response(self, user_id: int) -> Dict:
        """Generate response when insufficient data available"""
        return {
            "success": False,
            "error": "Insufficient data for analysis",
            "recommendation": "Complete more learning activities to enable analysis"
        }
    
    async def _get_cached_analysis(self, user_id: int) -> Optional[Dict]:
        """Get cached analysis results"""
        try:
            redis = await self._get_redis()
            cached = await redis.get(f"analytics:{user_id}")
            return json.loads(cached) if cached else None
        except Exception:
            return None
    
    async def _analyze_real_time_activity(self, activity: Dict, context: Optional[Dict]) -> Dict:
        """Analyze real-time activity"""
        return {"current_performance": 0.8, "trend": "improving"}
    
    async def _generate_immediate_insights(self, user_id: int, metrics: Dict, activity: Dict) -> List[str]:
        """Generate immediate insights"""
        return ["Great session!", "Keep up the momentum"]
    
    async def _detect_significant_changes(self, user_id: int, metrics: Dict, context: Optional[Dict]) -> List[str]:
        """Detect significant changes in performance"""
        return []  # Mock implementation
    
    async def _generate_adaptive_recommendations(self, user_id: int, metrics: Dict, insights: List) -> List[str]:
        """Generate adaptive recommendations"""
        return ["Try a more challenging exercise", "Focus on weak areas"]
    
    def _calculate_real_time_confidence(self, metrics: Dict) -> float:
        """Calculate confidence in real-time analysis"""
        return 0.75  # Mock confidence
    
    async def _get_milestone_context(self, db: AsyncSession, user_id: int) -> Dict:
        """Get context for milestone achievement"""
        return {"previous_level": "B1", "study_days": 45}
    
    async def _analyze_milestone_significance(self, milestone: Dict) -> Dict:
        """Analyze significance of achieved milestone"""
        return {"significance": "high", "rarity": 0.3}
    
    async def _update_learning_trajectory(self, db: AsyncSession, user_id: int, milestone: Dict) -> Dict:
        """Update user's learning trajectory"""
        return {"trajectory_updated": True, "new_goals_set": True}
    
    async def _generate_next_learning_goals(self, db: AsyncSession, user_id: int, milestone: Dict, analysis: Dict) -> List[str]:
        """Generate next learning goals"""
        return ["Master B2 level vocabulary", "Improve pronunciation accuracy"]
    
    async def _generate_celebration_message(self, milestone_type: str, data: Dict, analysis: Dict) -> str:
        """Generate celebration message for milestone"""
        return f"Congratulations on achieving {milestone_type}! This is a significant accomplishment."
    
    # Progress report helper methods
    async def _collect_progress_report_data(self, db: AsyncSession, user_id: int, cutoff_date: datetime) -> Dict:
        """Collect data for progress report"""
        return await self._collect_user_activity_data(db, user_id, cutoff_date)
    
    async def _generate_activity_summary(self, data: Dict) -> Dict:
        """Generate activity summary for report"""
        return {"total_sessions": 15, "total_minutes": 375, "avg_session_length": 25}
    
    async def _generate_skill_progress_summary(self, data: Dict) -> Dict:
        """Generate skill progress summary"""
        return {"speaking": "+12%", "writing": "+8%", "listening": "+15%"}
    
    async def _generate_achievement_summary(self, data: Dict) -> Dict:
        """Generate achievement summary"""
        return {"new_achievements": 2, "milestones_reached": 1}
    
    async def _generate_challenge_areas_summary(self, data: Dict) -> Dict:
        """Generate challenge areas summary"""
        return {"areas": ["grammar", "pronunciation"], "improvement_suggestions": ["daily practice", "focused exercises"]}
    
    async def _generate_goal_progress_summary(self, db: AsyncSession, user_id: int, data: Dict) -> Dict:
        """Generate goal progress summary"""
        return {"goals_completed": 3, "goals_in_progress": 2, "completion_rate": 0.6}
    
    async def _calculate_overall_period_rating(self, data: Dict) -> str:
        """Calculate overall rating for the period"""
        return "excellent"  # excellent, good, fair, needs_improvement
    
    async def _generate_motivational_message(self, data: Dict) -> str:
        """Generate motivational message"""
        return "You're making fantastic progress! Your dedication is paying off."
    
    async def _suggest_next_period_focus(self, data: Dict) -> List[str]:
        """Suggest focus areas for next period"""
        return ["Advanced grammar structures", "Business vocabulary", "Pronunciation refinement"]

# Global analytics engine instance
analytics_engine = LearningAnalyticsEngine()
