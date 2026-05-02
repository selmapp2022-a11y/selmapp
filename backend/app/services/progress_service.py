from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
import logging

from app.crud.progress import (
    user_progress_crud, daily_progress_crud, achievement_crud,
    user_achievement_crud, learning_goal_crud
)
from app.crud.user import user_crud
from app.models.progress import DifficultyLevel
from app.models.user import UserLevel

logger = logging.getLogger(__name__)

class ProgressService:
    """Service for handling user progress tracking and achievements"""
    
    def __init__(self):
        self.achievement_criteria = {
            "first_exercise": {"criteria_type": "exercises", "criteria_value": 1},
            "exercise_streak_7": {"criteria_type": "streak", "criteria_value": 7},
            "exercise_streak_30": {"criteria_type": "streak", "criteria_value": 30},
            "exercise_streak_100": {"criteria_type": "streak", "criteria_value": 100},
            "exercises_100": {"criteria_type": "exercises", "criteria_value": 100},
            "exercises_500": {"criteria_type": "exercises", "criteria_value": 500},
            "exercises_1000": {"criteria_type": "exercises", "criteria_value": 1000},
            "study_time_10h": {"criteria_type": "study_time", "criteria_value": 600},  # 10 hours in minutes
            "study_time_50h": {"criteria_type": "study_time", "criteria_value": 3000},  # 50 hours
            "study_time_100h": {"criteria_type": "study_time", "criteria_value": 6000},  # 100 hours
            "points_1000": {"criteria_type": "points", "criteria_value": 1000},
            "points_5000": {"criteria_type": "points", "criteria_value": 5000},
            "points_10000": {"criteria_type": "points", "criteria_value": 10000},
            "vocabulary_master_50": {"criteria_type": "vocabulary", "criteria_value": 50},
            "vocabulary_master_200": {"criteria_type": "vocabulary", "criteria_value": 200},
            "grammar_master_20": {"criteria_type": "grammar", "criteria_value": 20},
            "level_up_a2": {"criteria_type": "level", "criteria_value": 2},  # A2 level
            "level_up_b1": {"criteria_type": "level", "criteria_value": 3},  # B1 level
            "level_up_b2": {"criteria_type": "level", "criteria_value": 4},  # B2 level
            "level_up_c1": {"criteria_type": "level", "criteria_value": 5},  # C1 level
            "level_up_c2": {"criteria_type": "level", "criteria_value": 6},  # C2 level
        }

    async def update_exercise_progress(
        self, 
        db: AsyncSession, 
        user_id: int, 
        is_correct: bool, 
        points_earned: int,
        exercise_type: str = "general",
        time_taken_seconds: int = 0
    ) -> Dict[str, Any]:
        """Update progress after completing an exercise"""
        
        try:
            # Get or create user progress
            user_progress = await user_progress_crud.get_by_user(db, user_id=user_id)
            if not user_progress:
                # Create initial progress
                user = await user_crud.get(db, id=user_id)
                progress_data = {
                    "current_level": user.current_level,
                    "level_progress_percentage": 0.0
                }
                user_progress = await user_progress_crud.create_or_update(
                    db, user_id=user_id, progress_data=progress_data
                )

            # Update overall progress
            user_progress.total_exercises_completed += 1
            user_progress.total_points_earned += points_earned
            
            # Update study time (minimum 1 minute per exercise)
            study_minutes = max(1, time_taken_seconds // 60)
            user_progress.total_study_time_minutes += study_minutes
            
            # Update accuracy
            total_attempts = user_progress.total_exercises_completed
            current_correct = int(user_progress.average_accuracy * (total_attempts - 1))
            if is_correct:
                current_correct += 1
            user_progress.average_accuracy = current_correct / total_attempts
            
            # Update specific skill counters
            if exercise_type == "vocabulary":
                if is_correct:
                    user_progress.vocabulary_mastered += 1
            elif exercise_type == "grammar":
                if is_correct:
                    user_progress.grammar_rules_learned += 1
            elif exercise_type == "speaking":
                user_progress.speaking_sessions += 1
            elif exercise_type == "listening":
                user_progress.listening_hours += study_minutes / 60
            
            await db.commit()
            await db.refresh(user_progress)
            
            # Update daily progress
            await self._update_daily_progress(
                db, user_id, study_minutes, 1, points_earned, is_correct
            )
            
            # Check for achievements
            new_achievements = await self._check_and_award_achievements(db, user_id, user_progress)
            
            # Check for level progression
            level_up_info = await self._check_level_progression(db, user_id, user_progress)
            
            return {
                "success": True,
                "user_progress": user_progress,
                "new_achievements": new_achievements,
                "level_up": level_up_info,
                "study_minutes_added": study_minutes
            }
            
        except Exception as e:
            logger.error(f"Error updating exercise progress for user {user_id}: {e}")
            await db.rollback()
            return {"success": False, "error": str(e)}

    async def update_study_streak(
        self, db: AsyncSession, user_id: int, study_date: date = None
    ) -> Dict[str, Any]:
        """Update user's study streak"""
        
        if study_date is None:
            study_date = date.today()
        
        try:
            user_progress = await user_progress_crud.get_by_user(db, user_id=user_id)
            if not user_progress:
                return {"success": False, "error": "User progress not found"}
            
            # Update streak
            await user_progress_crud.update_streak(db, user_id=user_id, study_date=study_date)
            await db.refresh(user_progress)
            
            # Check for streak achievements
            streak_achievements = await self._check_streak_achievements(db, user_id, user_progress.current_streak_days)
            
            return {
                "success": True,
                "current_streak": user_progress.current_streak_days,
                "longest_streak": user_progress.longest_streak_days,
                "new_achievements": streak_achievements
            }
            
        except Exception as e:
            logger.error(f"Error updating study streak for user {user_id}: {e}")
            return {"success": False, "error": str(e)}

    async def check_goal_progress(
        self, db: AsyncSession, user_id: int
    ) -> List[Dict[str, Any]]:
        """Check and update progress on user's learning goals"""
        
        try:
            # Get active goals
            goals = await learning_goal_crud.get_user_goals(db, user_id=user_id, active_only=True)
            user_progress = await user_progress_crud.get_by_user(db, user_id=user_id)
            
            if not user_progress:
                return []
            
            updated_goals = []
            
            for goal in goals:
                current_value = 0
                
                # Calculate current value based on goal type
                if goal.goal_type == "exercises":
                    current_value = user_progress.total_exercises_completed
                elif goal.goal_type == "study_time":
                    current_value = user_progress.total_study_time_minutes
                elif goal.goal_type == "points":
                    current_value = user_progress.total_points_earned
                elif goal.goal_type == "vocabulary":
                    current_value = user_progress.vocabulary_mastered
                elif goal.goal_type == "grammar":
                    current_value = user_progress.grammar_rules_learned
                elif goal.goal_type == "streak":
                    current_value = user_progress.current_streak_days
                
                # Update goal if value changed
                if current_value != goal.current_value:
                    updated_goal = await learning_goal_crud.update_goal_progress(
                        db, goal_id=goal.id, progress_value=current_value
                    )
                    
                    updated_goals.append({
                        "goal": updated_goal,
                        "progress_percentage": (current_value / goal.target_value * 100) if goal.target_value > 0 else 0,
                        "completed": updated_goal.is_completed
                    })
            
            return updated_goals
            
        except Exception as e:
            logger.error(f"Error checking goal progress for user {user_id}: {e}")
            return []

    async def _update_daily_progress(
        self, 
        db: AsyncSession, 
        user_id: int, 
        study_minutes: int, 
        exercises_completed: int, 
        points_earned: int, 
        is_correct: bool
    ):
        """Update daily progress"""
        today = date.today()
        
        progress_data = {
            "study_time_minutes": study_minutes,
            "exercises_completed": exercises_completed,
            "points_earned": points_earned,
            "accuracy_rate": 1.0 if is_correct else 0.0
        }
        
        await daily_progress_crud.create_or_update_daily(
            db, user_id=user_id, date=today, progress_data=progress_data
        )

    async def _check_and_award_achievements(
        self, db: AsyncSession, user_id: int, user_progress
    ) -> List[Dict[str, Any]]:
        """Check and award achievements based on current progress"""
        
        new_achievements = []
        
        try:
            # Get all active achievements
            all_achievements = await achievement_crud.get_active_achievements(db)
            
            for achievement in all_achievements:
                # Check if user already has this achievement
                has_achievement = await user_achievement_crud.has_achievement(
                    db, user_id=user_id, achievement_id=achievement.id
                )
                
                if has_achievement:
                    continue
                
                # Check if user meets the criteria
                current_value = self._get_progress_value_for_criteria(
                    user_progress, achievement.criteria_type
                )
                
                if current_value >= achievement.criteria_value:
                    # Award the achievement
                    user_achievement = await user_achievement_crud.award_achievement(
                        db, 
                        user_id=user_id, 
                        achievement_id=achievement.id, 
                        progress_value=current_value
                    )
                    
                    if user_achievement:
                        new_achievements.append({
                            "achievement": achievement,
                            "earned_at": user_achievement.earned_at,
                            "progress_value": current_value
                        })
                        
                        # Add achievement points to user's total
                        user_progress.total_points_earned += achievement.points_reward
            
            if new_achievements:
                await db.commit()
                
        except Exception as e:
            logger.error(f"Error checking achievements for user {user_id}: {e}")
        
        return new_achievements

    async def _check_streak_achievements(
        self, db: AsyncSession, user_id: int, current_streak: int
    ) -> List[Dict[str, Any]]:
        """Check for streak-specific achievements"""
        
        streak_milestones = [7, 14, 30, 60, 100, 200, 365]
        new_achievements = []
        
        try:
            for milestone in streak_milestones:
                if current_streak >= milestone:
                    # Check if there's an achievement for this streak
                    achievements = await achievement_crud.get_by_criteria(db, criteria_type="streak")
                    
                    for achievement in achievements:
                        if (achievement.criteria_value == milestone and 
                            not await user_achievement_crud.has_achievement(
                                db, user_id=user_id, achievement_id=achievement.id
                            )):
                            
                            user_achievement = await user_achievement_crud.award_achievement(
                                db, user_id=user_id, achievement_id=achievement.id, progress_value=current_streak
                            )
                            
                            if user_achievement:
                                new_achievements.append({
                                    "achievement": achievement,
                                    "earned_at": user_achievement.earned_at,
                                    "progress_value": current_streak
                                })
            
            if new_achievements:
                await db.commit()
                
        except Exception as e:
            logger.error(f"Error checking streak achievements for user {user_id}: {e}")
        
        return new_achievements

    async def _check_level_progression(
        self, db: AsyncSession, user_id: int, user_progress
    ) -> Optional[Dict[str, Any]]:
        """Check if user should level up based on progress"""
        
        try:
            # Define level progression requirements
            level_requirements = {
                UserLevel.A1: {"exercises": 50, "vocabulary": 100, "accuracy": 0.7},
                UserLevel.A2: {"exercises": 150, "vocabulary": 300, "accuracy": 0.75},
                UserLevel.B1: {"exercises": 300, "vocabulary": 600, "accuracy": 0.8},
                UserLevel.B2: {"exercises": 500, "vocabulary": 1000, "accuracy": 0.85},
                UserLevel.C1: {"exercises": 800, "vocabulary": 1500, "accuracy": 0.9},
                UserLevel.C2: {"exercises": 1200, "vocabulary": 2000, "accuracy": 0.95},
            }
            
            current_level = user_progress.current_level
            
            # Get next level
            levels = list(UserLevel)
            current_index = levels.index(current_level)
            
            if current_index < len(levels) - 1:
                next_level = levels[current_index + 1]
                requirements = level_requirements.get(next_level, {})
                
                # Check if user meets requirements for next level
                meets_exercises = user_progress.total_exercises_completed >= requirements.get("exercises", 0)
                meets_vocabulary = user_progress.vocabulary_mastered >= requirements.get("vocabulary", 0)
                meets_accuracy = user_progress.average_accuracy >= requirements.get("accuracy", 0)
                
                if meets_exercises and meets_vocabulary and meets_accuracy:
                    # Level up the user
                    user = await user_crud.get(db, id=user_id)
                    await user_crud.update(db, db_obj=user, obj_in={"current_level": next_level})
                    
                    # Update progress
                    await user_progress_crud.update(
                        db,
                        db_obj=user_progress,
                        obj_in={
                            "current_level": next_level,
                            "level_progress_percentage": 0.0,
                            "last_level_up_date": datetime.utcnow()
                        }
                    )
                    
                    return {
                        "leveled_up": True,
                        "old_level": current_level,
                        "new_level": next_level,
                        "level_up_date": datetime.utcnow()
                    }
            
            # Calculate progress towards next level
            if current_index < len(levels) - 1:
                next_level = levels[current_index + 1]
                requirements = level_requirements.get(next_level, {})
                
                exercise_progress = min(
                    user_progress.total_exercises_completed / requirements.get("exercises", 1) * 100, 100
                )
                vocab_progress = min(
                    user_progress.vocabulary_mastered / requirements.get("vocabulary", 1) * 100, 100
                )
                accuracy_progress = min(
                    user_progress.average_accuracy / requirements.get("accuracy", 1) * 100, 100
                )
                
                overall_progress = (exercise_progress + vocab_progress + accuracy_progress) / 3
                
                # Update level progress percentage
                await user_progress_crud.update(
                    db,
                    db_obj=user_progress,
                    obj_in={"level_progress_percentage": overall_progress}
                )
                
                return {
                    "leveled_up": False,
                    "current_level": current_level,
                    "progress_percentage": overall_progress,
                    "requirements": requirements,
                    "current_stats": {
                        "exercises": user_progress.total_exercises_completed,
                        "vocabulary": user_progress.vocabulary_mastered,
                        "accuracy": user_progress.average_accuracy
                    }
                }
            
        except Exception as e:
            logger.error(f"Error checking level progression for user {user_id}: {e}")
        
        return None

    def _get_progress_value_for_criteria(self, user_progress, criteria_type: str) -> int:
        """Get the current progress value for a specific criteria type"""
        
        if criteria_type == "exercises":
            return user_progress.total_exercises_completed
        elif criteria_type == "study_time":
            return user_progress.total_study_time_minutes
        elif criteria_type == "points":
            return user_progress.total_points_earned
        elif criteria_type == "streak":
            return user_progress.current_streak_days
        elif criteria_type == "vocabulary":
            return user_progress.vocabulary_mastered
        elif criteria_type == "grammar":
            return user_progress.grammar_rules_learned
        elif criteria_type == "level":
            # Convert level to numeric value
            level_values = {
                DifficultyLevel.A1: 1,
                DifficultyLevel.A2: 2,
                DifficultyLevel.B1: 3,
                DifficultyLevel.B2: 4,
                DifficultyLevel.C1: 5,
                DifficultyLevel.C2: 6
            }
            return level_values.get(user_progress.current_level, 1)
        
        return 0

# Create service instance
progress_service = ProgressService() 