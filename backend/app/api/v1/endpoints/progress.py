from typing import Any, List, Optional
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.progress import DifficultyLevel
from app.crud.progress import (
    user_progress_crud, daily_progress_crud, achievement_crud,
    user_achievement_crud, study_session_crud, learning_goal_crud
)
from app.schemas.progress import (
    UserProgressResponse, UserProgressUpdate,
    DailyProgressResponse, 
    AchievementResponse, UserAchievementResponse,
    StudySessionResponse, StudySessionCreate, StudySessionUpdate,
    LearningGoalResponse, LearningGoalCreate, LearningGoalUpdate,
    ProgressDashboardResponse, WeeklyProgressResponse, 
    LevelProgressResponse, StreakResponse, LearningAnalyticsResponse
)

router = APIRouter()

# User Progress Endpoints
@router.get("/", response_model=UserProgressResponse)
async def get_user_progress(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get current user's progress"""
    progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
    
    if not progress:
        # Create initial progress if it doesn't exist
        progress_data = {
            "current_level": current_user.current_level,
            "level_progress_percentage": 0.0
        }
        progress = await user_progress_crud.create_or_update(
            db, user_id=current_user.id, progress_data=progress_data
        )
    
    return progress

@router.put("/", response_model=UserProgressResponse)
async def update_user_progress(
    progress_update: UserProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Update user's progress"""
    progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
    
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User progress not found"
        )
    
    progress = await user_progress_crud.update(
        db, db_obj=progress, obj_in=progress_update
    )
    return progress

# Daily Progress Endpoints
@router.get("/daily", response_model=List[DailyProgressResponse])
async def get_daily_progress(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to retrieve"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's daily progress for the last N days"""
    end_date = date.today()
    start_date = end_date - timedelta(days=days-1)
    
    daily_progress = await daily_progress_crud.get_user_progress_range(
        db, user_id=current_user.id, start_date=start_date, end_date=end_date
    )
    
    return daily_progress

@router.get("/daily/{target_date}", response_model=DailyProgressResponse)
async def get_daily_progress_by_date(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's progress for a specific date"""
    daily_progress = await daily_progress_crud.get_by_user_and_date(
        db, user_id=current_user.id, date=target_date
    )
    
    if not daily_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No progress found for this date"
        )
    
    return daily_progress

@router.post("/daily/update")
async def update_daily_progress(
    study_time_minutes: int = 0,
    exercises_completed: int = 0,
    points_earned: int = 0,
    accuracy_rate: float = 0.0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Update today's progress"""
    today = date.today()
    
    progress_data = {
        "study_time_minutes": study_time_minutes,
        "exercises_completed": exercises_completed,
        "points_earned": points_earned,
        "accuracy_rate": accuracy_rate,
        "daily_goal_met": study_time_minutes >= current_user.daily_goal_minutes
    }
    
    daily_progress = await daily_progress_crud.create_or_update_daily(
        db, user_id=current_user.id, date=today, progress_data=progress_data
    )
    
    # Update user's overall progress (study time)
    await user_progress_crud.update_study_time(
        db, user_id=current_user.id, minutes=study_time_minutes
    )
    
    # Update user's total points earned
    if points_earned > 0:
        user_progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
        if user_progress:
            user_progress.total_points_earned = (user_progress.total_points_earned or 0) + points_earned
            user_progress.total_exercises_completed = (user_progress.total_exercises_completed or 0) + exercises_completed
            await db.commit()
    
    # Update streak
    await user_progress_crud.update_streak(
        db, user_id=current_user.id, study_date=today
    )
    
    return {"message": "Daily progress updated", "progress": daily_progress}

# Achievement Endpoints
@router.get("/achievements", response_model=List[AchievementResponse])
async def get_all_achievements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Get all available achievements"""
    achievements = await achievement_crud.get_active_achievements(db)
    return achievements

@router.get("/achievements/earned", response_model=List[UserAchievementResponse])
async def get_user_achievements(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's earned achievements"""
    achievements = await user_achievement_crud.get_user_achievements(
        db, user_id=current_user.id
    )
    return achievements

# Study Session Endpoints
@router.get("/sessions", response_model=List[StudySessionResponse])
async def get_study_sessions(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's study sessions"""
    sessions = await study_session_crud.get_user_sessions(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return sessions

@router.post("/sessions/start", response_model=StudySessionResponse)
async def start_study_session(
    session_type: str = "practice",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Start a new study session"""
    # Check if there's already an active session
    active_session = await study_session_crud.get_active_session(
        db, user_id=current_user.id
    )
    
    if active_session:
        return active_session
    
    # Create new session
    session_data = StudySessionCreate(
        user_id=current_user.id,
        session_type=session_type
    )
    
    session = await study_session_crud.create(db, obj_in=session_data)
    return session

@router.put("/sessions/{session_id}/end", response_model=StudySessionResponse)
async def end_study_session(
    session_id: int,
    session_update: StudySessionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """End a study session"""
    session = await study_session_crud.get(db, id=session_id)
    
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Study session not found"
        )
    
    if session.ended_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already ended"
        )
    
    # Calculate duration if not provided
    if not session_update.duration_minutes:
        duration = datetime.utcnow() - session.started_at
        session_update.duration_minutes = int(duration.total_seconds() / 60)
    
    session = await study_session_crud.end_session(
        db, session_id=session_id, end_data=session_update.model_dump()
    )
    
    return session

# Learning Goals Endpoints
@router.get("/goals", response_model=List[LearningGoalResponse])
async def get_learning_goals(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's learning goals"""
    goals = await learning_goal_crud.get_user_goals(
        db, user_id=current_user.id, active_only=active_only
    )
    return goals

@router.post("/goals", response_model=LearningGoalResponse)
async def create_learning_goal(
    goal_in: LearningGoalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new learning goal"""
    goal_in.user_id = current_user.id
    goal = await learning_goal_crud.create(db, obj_in=goal_in)
    return goal

@router.put("/goals/{goal_id}", response_model=LearningGoalResponse)
async def update_learning_goal(
    goal_id: int,
    goal_update: LearningGoalUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Update a learning goal"""
    goal = await learning_goal_crud.get(db, id=goal_id)
    
    if not goal or goal.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning goal not found"
        )
    
    goal = await learning_goal_crud.update(db, db_obj=goal, obj_in=goal_update)
    return goal

# Analytics and Dashboard Endpoints
@router.get("/dashboard", response_model=ProgressDashboardResponse)
async def get_progress_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get comprehensive progress dashboard"""
    
    # Get user progress
    user_progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
    
    # Create initial progress if it doesn't exist
    if not user_progress:
        progress_data = {
            "current_level": current_user.current_level,
            "level_progress_percentage": 0.0
        }
        user_progress = await user_progress_crud.create_or_update(
            db, user_id=current_user.id, progress_data=progress_data
        )
    
    # Get recent achievements
    recent_achievements = await user_achievement_crud.get_user_achievements(
        db, user_id=current_user.id
    )
    recent_achievements = recent_achievements[:5]  # Last 5 achievements
    
    # Get last 7 days of progress
    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    daily_progress = await daily_progress_crud.get_user_progress_range(
        db, user_id=current_user.id, start_date=start_date, end_date=end_date
    )
    
    # Get active goals
    active_goals = await learning_goal_crud.get_user_goals(
        db, user_id=current_user.id, active_only=True
    )
    
    # Calculate streak info
    streak_info = {
        "current_streak": user_progress.current_streak_days if user_progress else 0,
        "longest_streak": user_progress.longest_streak_days if user_progress else 0,
        "last_study_date": user_progress.last_study_date.isoformat() if user_progress and user_progress.last_study_date else None
    }
    
    # Calculate level progress
    level_progress = {
        "current_level": user_progress.current_level if user_progress else current_user.current_level,
        "progress_percentage": user_progress.level_progress_percentage if user_progress else 0.0,
        "vocabulary_mastered": user_progress.vocabulary_mastered if user_progress else 0,
        "grammar_completed": user_progress.grammar_rules_learned if user_progress else 0
    }
    
    return ProgressDashboardResponse(
        user_progress=UserProgressResponse.model_validate(user_progress),
        recent_achievements=recent_achievements,
        daily_progress=daily_progress,
        active_goals=active_goals,
        study_streak=streak_info,
        level_progress=level_progress
    )

@router.get("/weekly", response_model=dict)
async def get_weekly_progress(
    weeks: int = Query(default=4, ge=1, le=12, description="Number of weeks to retrieve"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get weekly progress summary"""
    end_date = date.today()
    start_date = end_date - timedelta(weeks=weeks)
    
    daily_progress = await daily_progress_crud.get_user_progress_range(
        db, user_id=current_user.id, start_date=start_date, end_date=end_date
    )
    
    # Group by weeks
    weekly_data = {}
    for progress in daily_progress:
        week_start = progress.date.date() - timedelta(days=progress.date.weekday())
        week_key = week_start.isoformat()
        
        if week_key not in weekly_data:
            weekly_data[week_key] = {
                "week_start": week_start,
                "week_end": week_start + timedelta(days=6),
                "total_study_time": 0,
                "total_exercises": 0,
                "total_points": 0,
                "days_studied": 0,
                "daily_breakdown": []
            }
        
        weekly_data[week_key]["total_study_time"] += progress.study_time_minutes
        weekly_data[week_key]["total_exercises"] += progress.exercises_completed
        weekly_data[week_key]["total_points"] += progress.points_earned
        if progress.study_time_minutes > 0:
            weekly_data[week_key]["days_studied"] += 1
        weekly_data[week_key]["daily_breakdown"].append(progress)
    
    return {"weekly_progress": list(weekly_data.values())}

@router.get("/streak", response_model=dict)
async def get_streak_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get detailed streak information"""
    user_progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
    
    if not user_progress:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "last_study_date": None,
            "streak_milestones": []
        }
    
    # Define streak milestones
    milestones = [7, 14, 30, 60, 100, 200, 365]
    achieved_milestones = [m for m in milestones if user_progress.longest_streak_days >= m]
    next_milestone = next((m for m in milestones if m > user_progress.current_streak_days), None)
    
    return {
        "current_streak": user_progress.current_streak_days,
        "longest_streak": user_progress.longest_streak_days,
        "last_study_date": user_progress.last_study_date.date() if user_progress.last_study_date else None,
        "achieved_milestones": achieved_milestones,
        "next_milestone": next_milestone,
        "days_to_next_milestone": (next_milestone - user_progress.current_streak_days) if next_milestone else 0
    } 

@router.put("/daily-goal", response_model=dict)
async def update_daily_goal(
    minutes: int = Query(..., ge=1, le=600, description="Daily study goal in minutes (1-600)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update the user's daily study goal (in minutes)."""
    current_user.daily_goal_minutes = minutes
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return {
        "daily_goal_minutes": current_user.daily_goal_minutes,
        "message": "Daily goal updated",
    }


@router.get("/today", response_model=dict)
async def get_today_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Unified today view: streak + today's study minutes + daily goal status."""
    today = date.today()
    user_progress = await user_progress_crud.get_by_user(db, user_id=current_user.id)
    daily = await daily_progress_crud.get_by_user_and_date(db, user_id=current_user.id, date=today)

    goal_minutes = int(getattr(current_user, "daily_goal_minutes", 0) or 0)
    today_minutes = int(getattr(daily, "study_time_minutes", 0) or 0) if daily else 0
    progress_pct = round((today_minutes / goal_minutes * 100), 1) if goal_minutes > 0 else 0.0
    if progress_pct > 100:
        progress_pct = 100.0

    # Count vocabulary words due for review (SRS)
    from sqlalchemy import select, func, and_
    from app.models.content import UserVocabulary, VocabularyStatus
    due_reviews_count = 0
    try:
        now = datetime.utcnow()
        res = await db.execute(
            select(func.count(UserVocabulary.id)).where(
                and_(
                    UserVocabulary.user_id == current_user.id,
                    UserVocabulary.next_review_date <= now,
                    UserVocabulary.status.in_([VocabularyStatus.LEARNING, VocabularyStatus.REVIEW]),
                )
            )
        )
        due_reviews_count = int(res.scalar() or 0)
    except Exception:
        due_reviews_count = 0

    current_streak = user_progress.current_streak_days if user_progress else 0
    longest_streak = user_progress.longest_streak_days if user_progress else 0
    last_study = (
        user_progress.last_study_date.date().isoformat()
        if user_progress and user_progress.last_study_date else None
    )

    # Streak today? (last study date == today)
    streak_active_today = (
        user_progress is not None
        and user_progress.last_study_date is not None
        and user_progress.last_study_date.date() == today
    )

    return {
        "date": today.isoformat(),
        "streak": {
            "current": current_streak,
            "longest": longest_streak,
            "last_study_date": last_study,
            "active_today": streak_active_today,
        },
        "daily_goal": {
            "goal_minutes": goal_minutes,
            "minutes_today": today_minutes,
            "progress_percentage": progress_pct,
            "goal_met": today_minutes >= goal_minutes if goal_minutes > 0 else False,
            "remaining_minutes": max(0, goal_minutes - today_minutes),
        },
        "vocabulary": {
            "due_reviews": due_reviews_count,
        },
        "today": {
            "exercises_completed": int(getattr(daily, "exercises_completed", 0) or 0) if daily else 0,
            "points_earned": int(getattr(daily, "points_earned", 0) or 0) if daily else 0,
            "accuracy_rate": float(getattr(daily, "accuracy_rate", 0.0) or 0.0) if daily else 0.0,
        },
    }
