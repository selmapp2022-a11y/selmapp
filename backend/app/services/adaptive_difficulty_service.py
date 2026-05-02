"""
Adaptive Difficulty Service
===========================
Analyzes user performance data (DayCompletionRecord, ExerciseAttempt, LessonProgress,
UserWeeklyProgress) to compute an adaptive difficulty level and update the
UserLearningProfile accordingly.

The service exposes a single high-level entry point:
    `compute_adaptive_difficulty(db, user_id) -> AdaptiveDifficultyResult`

which returns the recommended CEFR difficulty level, a numeric difficulty score
(0-1), and a dict of adjustments to apply to content generation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, func as sa_func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progress import (
    DayCompletionRecord,
    UserWeeklyProgress,
    UserProgress,
)
from app.models.exercise import ExerciseAttempt
from app.models.lessons import LessonProgress
from app.models.personalization import UserLearningProfile

logger = logging.getLogger(__name__)

# ── CEFR helpers ─────────────────────────────────────────────────────

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_INDEX = {lvl: idx for idx, lvl in enumerate(CEFR_LEVELS)}


def _cefr_to_score(level: str) -> float:
    """Map a CEFR level to a 0‑1 numeric score."""
    idx = CEFR_INDEX.get(level.upper(), 0)
    return idx / (len(CEFR_LEVELS) - 1)


def _score_to_cefr(score: float) -> str:
    """Map a 0‑1 score to the closest CEFR level."""
    idx = round(score * (len(CEFR_LEVELS) - 1))
    idx = max(0, min(len(CEFR_LEVELS) - 1, idx))
    return CEFR_LEVELS[idx]


# ── Result dataclass ─────────────────────────────────────────────────

@dataclass
class AdaptiveDifficultyResult:
    recommended_level: str  # CEFR level
    difficulty_score: float  # 0‑1 continuous score
    confidence: float  # 0‑1 how confident the recommendation is
    adjustments: Dict[str, Any] = field(default_factory=dict)
    analysis_summary: Dict[str, Any] = field(default_factory=dict)


# ── Service ──────────────────────────────────────────────────────────

class AdaptiveDifficultyService:
    """Stateless service — all state lives in the database."""

    # Thresholds
    ACCURACY_HIGH = 0.85   # user is excelling
    ACCURACY_LOW = 0.55    # user is struggling
    COMPLETION_LOW = 0.50  # user is abandoning content
    MIN_ATTEMPTS_FOR_ADJUSTMENT = 5  # need at least N data points
    RECENT_DAYS = 14       # look-back window

    async def compute_adaptive_difficulty(
        self,
        db: AsyncSession,
        user_id: int,
        current_level: Optional[str] = None,
    ) -> AdaptiveDifficultyResult:
        """
        Main entry point.  Gathers performance signals, computes a weighted
        difficulty score, and returns a recommendation.
        """
        # 1. Gather raw performance data
        perf = await self._gather_performance_data(db, user_id)

        # 2. Determine the baseline from current level
        if current_level is None:
            current_level = perf.get("current_level", "A1")
        baseline_score = _cefr_to_score(current_level)

        # 3. If not enough data, return baseline with low confidence
        total_attempts = perf.get("total_attempts", 0)
        if total_attempts < self.MIN_ATTEMPTS_FOR_ADJUSTMENT:
            return AdaptiveDifficultyResult(
                recommended_level=current_level,
                difficulty_score=baseline_score,
                confidence=0.2,
                adjustments={"include_hints": True},
                analysis_summary={"reason": "insufficient_data", "attempts": total_attempts},
            )

        # 4. Compute sub-scores
        accuracy_signal = self._accuracy_signal(perf)
        completion_signal = self._completion_signal(perf)
        trend_signal = self._trend_signal(perf)
        skill_balance = self._skill_balance(perf)

        # 5. Weighted combination → difficulty adjustment (-1 to +1)
        #    positive  → raise difficulty
        #    negative  → lower difficulty
        adjustment = (
            0.40 * accuracy_signal
            + 0.25 * completion_signal
            + 0.25 * trend_signal
            + 0.10 * skill_balance
        )

        # Get learning profile progression rate (default 0.1 = gradual)
        progression_rate = perf.get("preferred_difficulty_progression", 0.1)
        adjustment *= (0.5 + progression_rate)  # scale the jump

        # Clamp
        new_score = max(0.0, min(1.0, baseline_score + adjustment * 0.2))
        recommended = _score_to_cefr(new_score)

        # Confidence based on amount of data
        confidence = min(1.0, total_attempts / 30)

        # 6. Build content-generation adjustments
        adjustments = self._build_adjustments(perf, accuracy_signal, completion_signal, skill_balance)

        analysis_summary = {
            "baseline_level": current_level,
            "accuracy_signal": round(accuracy_signal, 3),
            "completion_signal": round(completion_signal, 3),
            "trend_signal": round(trend_signal, 3),
            "raw_adjustment": round(adjustment, 3),
            "total_attempts": total_attempts,
            "recent_accuracy": round(perf.get("recent_accuracy", 0), 3),
            "weak_areas": perf.get("weak_areas", []),
            "strong_areas": perf.get("strong_areas", []),
        }

        # 7. Persist updated profile values
        await self._update_learning_profile(db, user_id, new_score, perf)

        return AdaptiveDifficultyResult(
            recommended_level=recommended,
            difficulty_score=round(new_score, 4),
            confidence=round(confidence, 3),
            adjustments=adjustments,
            analysis_summary=analysis_summary,
        )

    # ── Data gathering ───────────────────────────────────────────────

    async def _gather_performance_data(
        self, db: AsyncSession, user_id: int
    ) -> Dict[str, Any]:
        """Gather all relevant performance signals from the database."""
        cutoff = datetime.utcnow() - timedelta(days=self.RECENT_DAYS)
        data: Dict[str, Any] = {}

        # Current level from UserProgress
        progress_q = select(UserProgress).where(UserProgress.user_id == user_id)
        progress_res = await db.execute(progress_q)
        progress = progress_res.scalars().first()
        if progress:
            data["current_level"] = str(progress.current_level.value) if progress.current_level else "A1"
            data["overall_accuracy"] = float(progress.average_accuracy or 0)
        else:
            data["current_level"] = "A1"
            data["overall_accuracy"] = 0.0

        # Recent exercise attempts
        attempts_q = (
            select(
                sa_func.count().label("cnt"),
                sa_func.avg(ExerciseAttempt.score).label("avg_score"),
                sa_func.sum(
                    sa_func.cast(ExerciseAttempt.is_correct, sa_func.literal_column("INTEGER"))
                ).label("correct"),
            )
            .where(and_(ExerciseAttempt.user_id == user_id, ExerciseAttempt.created_at >= cutoff))
        )
        att_res = await db.execute(attempts_q)
        att_row = att_res.one_or_none()
        total_attempts = int(att_row.cnt) if att_row and att_row.cnt else 0
        data["total_attempts"] = total_attempts
        data["recent_accuracy"] = float(att_row.avg_score) if att_row and att_row.avg_score else 0.0

        # Older accuracy for trend
        older_cutoff = cutoff - timedelta(days=self.RECENT_DAYS)
        older_q = (
            select(sa_func.avg(ExerciseAttempt.score).label("avg"))
            .where(
                and_(
                    ExerciseAttempt.user_id == user_id,
                    ExerciseAttempt.created_at >= older_cutoff,
                    ExerciseAttempt.created_at < cutoff,
                )
            )
        )
        older_res = await db.execute(older_q)
        older_row = older_res.one_or_none()
        data["older_accuracy"] = float(older_row.avg) if older_row and older_row.avg else None

        # DayCompletionRecords (recent)
        dcr_q = (
            select(DayCompletionRecord)
            .where(and_(DayCompletionRecord.user_id == user_id, DayCompletionRecord.completed_at >= cutoff))
            .order_by(DayCompletionRecord.completed_at.desc())
            .limit(14)
        )
        dcr_res = await db.execute(dcr_q)
        day_records = dcr_res.scalars().all()
        data["day_records"] = day_records

        if day_records:
            day_accuracies = [d.accuracy for d in day_records if d.accuracy is not None]
            data["day_avg_accuracy"] = sum(day_accuracies) / len(day_accuracies) if day_accuracies else 0.0
        else:
            data["day_avg_accuracy"] = 0.0

        # Lesson completion rate
        lesson_total_q = select(sa_func.count()).where(
            and_(LessonProgress.user_id == user_id, LessonProgress.created_at >= cutoff)
        )
        lesson_total = (await db.execute(lesson_total_q)).scalar() or 0

        lesson_done_q = select(sa_func.count()).where(
            and_(
                LessonProgress.user_id == user_id,
                LessonProgress.is_completed == True,
                LessonProgress.created_at >= cutoff,
            )
        )
        lesson_done = (await db.execute(lesson_done_q)).scalar() or 0
        data["lesson_completion_rate"] = (lesson_done / lesson_total) if lesson_total > 0 else 1.0

        # UserWeeklyProgress (skill scores, weak/strong areas)
        weekly_q = select(UserWeeklyProgress).where(UserWeeklyProgress.user_id == user_id)
        weekly_res = await db.execute(weekly_q)
        weekly = weekly_res.scalars().first()
        if weekly:
            data["skill_scores"] = weekly.skill_scores or {}
            data["weak_areas"] = weekly.weak_areas or []
            data["strong_areas"] = weekly.strong_areas or []
        else:
            data["skill_scores"] = {}
            data["weak_areas"] = []
            data["strong_areas"] = []

        # UserLearningProfile
        profile_q = select(UserLearningProfile).where(UserLearningProfile.user_id == user_id)
        profile_res = await db.execute(profile_q)
        profile = profile_res.scalars().first()
        if profile:
            data["learning_rate"] = float(profile.learning_rate or 1.0)
            data["retention_rate"] = float(profile.retention_rate or 0.8)
            data["challenge_preference"] = float(profile.challenge_preference or 0.5)
            data["preferred_difficulty_progression"] = float(
                profile.preferred_difficulty_progression or 0.1
            )
        else:
            data["learning_rate"] = 1.0
            data["retention_rate"] = 0.8
            data["challenge_preference"] = 0.5
            data["preferred_difficulty_progression"] = 0.1

        return data

    # ── Signal computations ──────────────────────────────────────────

    def _accuracy_signal(self, perf: Dict[str, Any]) -> float:
        """Returns -1 (struggling) to +1 (excelling) based on accuracy."""
        acc = perf.get("recent_accuracy", 0)
        if acc == 0:
            return 0.0

        # Use both exercise accuracy and day-record accuracy
        day_acc = perf.get("day_avg_accuracy", acc)
        combined = 0.6 * acc + 0.4 * day_acc

        if combined >= self.ACCURACY_HIGH:
            return min(1.0, (combined - self.ACCURACY_HIGH) / (1.0 - self.ACCURACY_HIGH) + 0.3)
        elif combined <= self.ACCURACY_LOW:
            return max(-1.0, -(self.ACCURACY_LOW - combined) / self.ACCURACY_LOW - 0.3)
        else:
            # Middle zone — slight positive bias
            mid = (self.ACCURACY_LOW + self.ACCURACY_HIGH) / 2
            return (combined - mid) / (self.ACCURACY_HIGH - self.ACCURACY_LOW)

    def _completion_signal(self, perf: Dict[str, Any]) -> float:
        """Low completion rates suggest difficulty is too high → negative signal."""
        rate = perf.get("lesson_completion_rate", 1.0)
        if rate >= 0.8:
            return 0.2  # healthy
        elif rate <= self.COMPLETION_LOW:
            return -0.6  # struggling / abandoning
        else:
            return (rate - 0.65) / 0.3  # linear interpolation

    def _trend_signal(self, perf: Dict[str, Any]) -> float:
        """Compare recent vs older accuracy to detect improvement or decline."""
        recent = perf.get("recent_accuracy", 0)
        older = perf.get("older_accuracy")
        if older is None or older == 0:
            return 0.0

        delta = recent - older
        # Clamp to [-0.5, 0.5] then scale to [-1, 1]
        delta = max(-0.5, min(0.5, delta))
        return delta * 2

    def _skill_balance(self, perf: Dict[str, Any]) -> float:
        """
        If user has large gaps between skill areas, suggest staying at current
        level to consolidate. Returns negative when imbalanced.
        """
        scores = perf.get("skill_scores", {})
        if len(scores) < 2:
            return 0.0

        values = [float(v) for v in scores.values() if isinstance(v, (int, float))]
        if not values:
            return 0.0

        spread = max(values) - min(values)
        if spread > 0.4:
            return -0.3  # big imbalance
        elif spread > 0.25:
            return -0.1
        else:
            return 0.1  # well-balanced

    # ── Adjustment builder ───────────────────────────────────────────

    def _build_adjustments(
        self,
        perf: Dict[str, Any],
        accuracy_signal: float,
        completion_signal: float,
        skill_balance: float,
    ) -> Dict[str, Any]:
        """Build a dict of content-generation adjustments."""
        adj: Dict[str, Any] = {}

        # Difficulty modifier
        if accuracy_signal < -0.2:
            adj["difficulty_modifier"] = "supportive"
            adj["include_hints"] = True
            adj["extra_examples"] = True
        elif accuracy_signal > 0.3:
            adj["difficulty_modifier"] = "challenging"
            adj["include_advanced_concepts"] = True
        else:
            adj["difficulty_modifier"] = "standard"

        # Completion-based
        if completion_signal < -0.2:
            adj["shorter_segments"] = True
            adj["more_frequent_breaks"] = True

        # Skill-specific focus
        weak = perf.get("weak_areas", [])
        if weak:
            adj["focus_areas"] = weak[:3]
            adj["reinforce_weak_skills"] = True

        strong = perf.get("strong_areas", [])
        if strong:
            adj["leverage_strengths"] = strong[:2]

        # Challenge preference from profile
        challenge_pref = perf.get("challenge_preference", 0.5)
        if challenge_pref > 0.7:
            adj["add_bonus_challenges"] = True
        elif challenge_pref < 0.3:
            adj["gentle_progression"] = True

        return adj

    # ── Profile update ───────────────────────────────────────────────

    async def _update_learning_profile(
        self,
        db: AsyncSession,
        user_id: int,
        new_score: float,
        perf: Dict[str, Any],
    ) -> None:
        """Update UserLearningProfile with latest adaptive parameters."""
        profile_q = select(UserLearningProfile).where(UserLearningProfile.user_id == user_id)
        result = await db.execute(profile_q)
        profile = result.scalars().first()

        if not profile:
            return  # no profile to update; will be created during onboarding

        recent_acc = perf.get("recent_accuracy", 0)
        older_acc = perf.get("older_accuracy")

        # Update learning_rate (how fast the user improves)
        if older_acc is not None and older_acc > 0:
            improvement = recent_acc - older_acc
            # Exponential moving average
            current_lr = float(profile.learning_rate or 1.0)
            new_lr = 0.7 * current_lr + 0.3 * (1.0 + improvement * 2)
            profile.learning_rate = max(0.3, min(2.0, new_lr))

        # Update retention_rate based on accuracy stability
        if recent_acc > 0:
            current_rr = float(profile.retention_rate or 0.8)
            profile.retention_rate = 0.8 * current_rr + 0.2 * recent_acc

        # Update challenge_preference from completion behaviour
        completion = perf.get("lesson_completion_rate", 1.0)
        current_cp = float(profile.challenge_preference or 0.5)
        if completion > 0.8 and recent_acc > self.ACCURACY_HIGH:
            # User handles challenges well → nudge up
            profile.challenge_preference = min(1.0, current_cp + 0.05)
        elif completion < self.COMPLETION_LOW:
            profile.challenge_preference = max(0.0, current_cp - 0.05)

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.warning("Failed to update learning profile for user %s", user_id)


# Global singleton
adaptive_difficulty_service = AdaptiveDifficultyService()
