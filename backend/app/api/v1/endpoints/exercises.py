from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.exercise import ExerciseType, DifficultyLevel
from app.crud.exercise import exercise_crud, exercise_attempt_crud, quiz_crud, quiz_attempt_crud
from app.crud.progress import user_progress_crud, daily_progress_crud
from app.schemas.exercise import (
    ExerciseResponse, ExercisePracticeResponse, ExerciseCreate, ExerciseUpdate,
    ExerciseAttemptResponse, ExerciseAttemptCreate,
    QuizResponse, QuizWithExercisesResponse, QuizCreate, QuizUpdate,
    QuizAttemptResponse, QuizAttemptCreate, QuizAttemptUpdate,
    ExerciseSubmissionRequest, ExerciseSubmissionResponse,
    QuizSubmissionRequest, QuizSubmissionResponse,
    ExerciseStatisticsResponse, LearningPathExerciseResponse
)
from app.services.ai_service import AIService
from datetime import datetime, date

router = APIRouter()
ai_service = AIService()

# Exercise Endpoints
@router.get("/", response_model=List[ExercisePracticeResponse])
async def get_exercises(
    level: Optional[DifficultyLevel] = None,
    exercise_type: Optional[ExerciseType] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get exercises with optional filtering"""
    if level and exercise_type:
        exercises = await exercise_crud.get_by_type_and_level(
            db, exercise_type=exercise_type, level=level, skip=skip, limit=limit
        )
    elif level:
        exercises = await exercise_crud.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    else:
        exercises = await exercise_crud.get_multi(db, skip=skip, limit=limit)
    
    return exercises

@router.get("/{exercise_id}", response_model=ExercisePracticeResponse)
async def get_exercise(
    exercise_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get specific exercise for practice (without correct answer)"""
    exercise = await exercise_crud.get(db, id=exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found"
        )
    
    if not exercise.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not available"
        )
    
    return exercise

@router.get("/random/{level}", response_model=List[ExercisePracticeResponse])
async def get_random_exercises(
    level: DifficultyLevel,
    exercise_type: Optional[ExerciseType] = None,
    count: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get random exercises for practice"""
    exercises = await exercise_crud.get_random_exercises(
        db, level=level, exercise_type=exercise_type, count=count
    )
    return exercises

@router.post("/submit", response_model=ExerciseSubmissionResponse)
async def submit_exercise(
    submission: ExerciseSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Submit exercise answer and get feedback"""
    # Get the exercise
    exercise = await exercise_crud.get(db, id=submission.exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found"
        )
    
    # Check answer correctness
    is_correct = await _check_answer_correctness(exercise, submission.user_answer)
    
    # Calculate score (simple implementation)
    score = 1.0 if is_correct else 0.0
    points_earned = exercise.points if is_correct else 0
    
    # Get AI feedback if needed
    ai_feedback = None
    if exercise.exercise_type in [ExerciseType.WRITING, ExerciseType.SPEAKING]:
        try:
            feedback_result = await ai_service.check_grammar(
                str(submission.user_answer.get('text', ''))
            )
            if feedback_result.get('success'):
                ai_feedback = feedback_result.get('content')
        except Exception as e:
            # AI feedback is optional, don't fail the submission
            pass
    
    # Create attempt record
    attempt_data = ExerciseAttemptCreate(
        user_id=current_user.id,
        exercise_id=submission.exercise_id,
        user_answer=submission.user_answer,
        time_taken_seconds=submission.time_taken_seconds
    )
    
    attempt = await exercise_attempt_crud.create(db, obj_in=attempt_data)
    
    # Update attempt with results
    attempt.is_correct = is_correct
    attempt.score = score
    attempt.ai_feedback = ai_feedback
    await db.commit()
    await db.refresh(attempt)
    
    # Update user progress
    await _update_user_progress_after_exercise(
        db, current_user.id, is_correct, points_earned, submission.time_taken_seconds or 0
    )
    
    return ExerciseSubmissionResponse(
        is_correct=is_correct,
        score=score,
        points_earned=points_earned,
        correct_answer=exercise.correct_answer,
        explanation=exercise.explanation,
        ai_feedback=ai_feedback
    )

# Exercise Attempts and Statistics
@router.get("/attempts/", response_model=List[ExerciseAttemptResponse])
async def get_exercise_attempts(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's exercise attempts"""
    attempts = await exercise_attempt_crud.get_user_attempts(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return attempts

@router.get("/statistics/", response_model=ExerciseStatisticsResponse)
async def get_exercise_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's exercise statistics"""
    stats = await exercise_attempt_crud.get_user_statistics(db, user_id=current_user.id)
    return ExerciseStatisticsResponse(**stats)

@router.get("/performance/", response_model=List[dict])
async def get_exercise_performance(
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's recent exercise performance"""
    performance = await exercise_attempt_crud.get_recent_performance(
        db, user_id=current_user.id, days=days
    )
    return performance

# Quiz Endpoints
@router.get("/quizzes/", response_model=List[QuizResponse])
async def get_quizzes(
    level: Optional[DifficultyLevel] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get available quizzes"""
    if level:
        quizzes = await quiz_crud.get_by_level(db, level=level, skip=skip, limit=limit)
    else:
        quizzes = await quiz_crud.get_multi(db, skip=skip, limit=limit)
    
    return quizzes

@router.get("/quizzes/{quiz_id}", response_model=QuizWithExercisesResponse)
async def get_quiz_with_exercises(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get quiz with its exercises"""
    quiz = await quiz_crud.get_with_exercises(db, quiz_id=quiz_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    if not quiz.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not available"
        )
    
    # Check if user can attempt this quiz
    can_attempt = await quiz_attempt_crud.can_attempt_quiz(
        db, user_id=current_user.id, quiz_id=quiz_id
    )
    
    if not can_attempt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maximum attempts reached for this quiz"
        )
    
    # Format exercises for practice (without correct answers)
    exercises = []
    for quiz_exercise in quiz.quiz_exercises:
        exercise = quiz_exercise.exercise
        exercises.append(ExercisePracticeResponse(
            id=exercise.id,
            title=exercise.title,
            description=exercise.description,
            exercise_type=exercise.exercise_type,
            difficulty_level=exercise.difficulty_level,
            question=exercise.question,
            options=exercise.options,
            audio_url=exercise.audio_url,
            image_url=exercise.image_url,
            points=exercise.points,
            time_limit_seconds=exercise.time_limit_seconds
        ))
    
    return QuizWithExercisesResponse(
        **quiz.__dict__,
        exercises=exercises
    )

@router.post("/quizzes/{quiz_id}/start", response_model=QuizAttemptResponse)
async def start_quiz_attempt(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Start a quiz attempt"""
    # Check if quiz exists and is active
    quiz = await quiz_crud.get(db, id=quiz_id)
    if not quiz or not quiz.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found or not available"
        )
    
    # Check if user can attempt this quiz
    can_attempt = await quiz_attempt_crud.can_attempt_quiz(
        db, user_id=current_user.id, quiz_id=quiz_id
    )
    
    if not can_attempt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maximum attempts reached for this quiz"
        )
    
    # Create quiz attempt
    attempt_data = QuizAttemptCreate(
        user_id=current_user.id,
        quiz_id=quiz_id
    )
    
    attempt = await quiz_attempt_crud.create(db, obj_in=attempt_data)
    return attempt

@router.post("/quizzes/submit", response_model=QuizSubmissionResponse)
async def submit_quiz(
    submission: QuizSubmissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Submit quiz answers and get results"""
    # Get the quiz
    quiz = await quiz_crud.get_with_exercises(db, quiz_id=submission.quiz_id)
    if not quiz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found"
        )
    
    # Find the active attempt
    attempts = await quiz_attempt_crud.get_quiz_attempts(
        db, user_id=current_user.id, quiz_id=submission.quiz_id
    )
    
    active_attempt = None
    for attempt in attempts:
        if not attempt.completed_at:
            active_attempt = attempt
            break
    
    if not active_attempt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active quiz attempt found"
        )
    
    # Process answers
    total_questions = len(quiz.quiz_exercises)
    correct_answers = 0
    total_points = 0
    detailed_results = []
    
    # Create a mapping of exercise_id to answer
    answers_map = {answer['exercise_id']: answer for answer in submission.answers}
    
    for quiz_exercise in quiz.quiz_exercises:
        exercise = quiz_exercise.exercise
        user_answer = answers_map.get(exercise.id, {}).get('user_answer', {})
        
        # Check if answer is correct
        is_correct = await _check_answer_correctness(exercise, user_answer)
        
        if is_correct:
            correct_answers += 1
            total_points += exercise.points
        
        detailed_results.append({
            'exercise_id': exercise.id,
            'question': exercise.question,
            'user_answer': user_answer,
            'correct_answer': exercise.correct_answer,
            'is_correct': is_correct,
            'points_earned': exercise.points if is_correct else 0,
            'explanation': exercise.explanation
        })
    
    # Calculate final score
    final_score = correct_answers / total_questions if total_questions > 0 else 0
    passed = final_score >= quiz.passing_score
    
    # Calculate time taken
    time_taken_minutes = int((datetime.utcnow() - active_attempt.started_at).total_seconds() / 60)
    
    # Update the attempt
    attempt_update = QuizAttemptUpdate(
        score=final_score,
        total_questions=total_questions,
        correct_answers=correct_answers,
        time_taken_minutes=time_taken_minutes,
        passed=passed,
        completed_at=datetime.utcnow()
    )
    
    updated_attempt = await quiz_attempt_crud.update(
        db, db_obj=active_attempt, obj_in=attempt_update
    )
    
    # Update user progress
    await _update_user_progress_after_quiz(
        db, current_user.id, passed, total_points, time_taken_minutes * 60
    )
    
    return QuizSubmissionResponse(
        quiz_attempt_id=updated_attempt.id,
        score=final_score,
        total_questions=total_questions,
        correct_answers=correct_answers,
        passed=passed,
        time_taken_minutes=time_taken_minutes,
        points_earned=total_points,
        detailed_results=detailed_results
    )

@router.get("/quizzes/attempts/", response_model=List[QuizAttemptResponse])
async def get_quiz_attempts(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's quiz attempts"""
    attempts = await quiz_attempt_crud.get_user_attempts(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return attempts

# Learning Path Exercises
@router.get("/learning-path/{level}", response_model=LearningPathExerciseResponse)
async def get_learning_path_exercises(
    level: DifficultyLevel,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get exercises organized by type for a learning path"""
    
    # Get exercises by type for the level
    vocabulary_exercises = await exercise_crud.get_by_type_and_level(
        db, exercise_type=ExerciseType.MULTIPLE_CHOICE, level=level, limit=10
    )
    
    grammar_exercises = await exercise_crud.get_by_type_and_level(
        db, exercise_type=ExerciseType.FILL_BLANK, level=level, limit=10
    )
    
    listening_exercises = await exercise_crud.get_by_type_and_level(
        db, exercise_type=ExerciseType.LISTENING, level=level, limit=5
    )
    
    reading_exercises = await exercise_crud.get_by_type_and_level(
        db, exercise_type=ExerciseType.MULTIPLE_CHOICE, level=level, limit=5
    )
    
    speaking_exercises = await exercise_crud.get_by_type_and_level(
        db, exercise_type=ExerciseType.SPEAKING, level=level, limit=3
    )
    
    writing_exercises = await exercise_crud.get_by_type_and_level(
        db, exercise_type=ExerciseType.WRITING, level=level, limit=3
    )
    
    return LearningPathExerciseResponse(
        level=level,
        vocabulary_exercises=vocabulary_exercises,
        grammar_exercises=grammar_exercises,
        listening_exercises=listening_exercises,
        reading_exercises=reading_exercises,
        speaking_exercises=speaking_exercises,
        writing_exercises=writing_exercises
    )

# Helper Functions
async def _check_answer_correctness(exercise, user_answer) -> bool:
    """Check if user answer is correct"""
    correct_answer = exercise.correct_answer
    
    # Handle case where correct_answer might be None or empty
    if not correct_answer:
        return False
    
    if exercise.exercise_type == ExerciseType.MULTIPLE_CHOICE:
        user_selected = user_answer.get('selected', '')
        correct_option = correct_answer.get('correct_option', '')
        # Both must be non-empty and equal
        if not user_selected or not correct_option:
            return False
        return user_selected.strip().lower() == correct_option.strip().lower()
    
    elif exercise.exercise_type == ExerciseType.FILL_BLANK:
        user_text = user_answer.get('text', '').strip().lower()
        # Try multiple keys for correct answer text
        correct_text = (
            correct_answer.get('text') or 
            correct_answer.get('answer') or 
            correct_answer.get('correct_option') or 
            ''
        ).strip().lower()
        
        # Both must be non-empty to be considered correct
        if not user_text or not correct_text:
            return False
        
        # Support multiple acceptable answers separated by | or /
        acceptable_answers = [
            ans.strip().lower() 
            for ans in correct_text.replace('/', '|').split('|') 
            if ans.strip()
        ]
        
        if acceptable_answers:
            return user_text in acceptable_answers
        return user_text == correct_text
    
    elif exercise.exercise_type == ExerciseType.MATCHING:
        user_matches = user_answer.get('matches', {})
        correct_matches = correct_answer.get('matches', {})
        return user_matches == correct_matches
    
    elif exercise.exercise_type in [ExerciseType.WRITING, ExerciseType.SPEAKING]:
        # For writing and speaking, we'll use AI to evaluate
        # For now, return True (will be evaluated by AI feedback)
        return True
    
    elif exercise.exercise_type == ExerciseType.TRANSLATION:
        # Simple keyword matching for translation
        user_text = user_answer.get('text', '').strip().lower()
        correct_keywords = correct_answer.get('keywords', [])
        if not user_text or not correct_keywords:
            return False
        return any(keyword.lower() in user_text for keyword in correct_keywords)
    
    return False

async def _update_user_progress_after_exercise(
    db: AsyncSession, user_id: int, is_correct: bool, points_earned: int, time_taken: int
):
    """Update user progress after completing an exercise"""
    today = date.today()
    
    # Update daily progress
    progress_data = {
        "study_time_minutes": max(1, time_taken // 60),  # At least 1 minute
        "exercises_completed": 1,
        "points_earned": points_earned,
        "accuracy_rate": 1.0 if is_correct else 0.0
    }
    
    await daily_progress_crud.create_or_update_daily(
        db, user_id=user_id, date=today, progress_data=progress_data
    )
    
    # Update overall progress
    user_progress = await user_progress_crud.get_by_user(db, user_id=user_id)
    if user_progress:
        user_progress.total_exercises_completed += 1
        user_progress.total_points_earned += points_earned
        
        # Recalculate average accuracy
        total_attempts = user_progress.total_exercises_completed
        current_correct = int(user_progress.average_accuracy * (total_attempts - 1))
        if is_correct:
            current_correct += 1
        user_progress.average_accuracy = current_correct / total_attempts
        
        await db.commit()

async def _update_user_progress_after_quiz(
    db: AsyncSession, user_id: int, passed: bool, points_earned: int, time_taken: int
):
    """Update user progress after completing a quiz"""
    today = date.today()
    
    # Update daily progress
    progress_data = {
        "study_time_minutes": max(5, time_taken // 60),  # At least 5 minutes for quiz
        "exercises_completed": 1,  # Count quiz as 1 exercise
        "points_earned": points_earned,
        "accuracy_rate": 1.0 if passed else 0.0
    }
    
    await daily_progress_crud.create_or_update_daily(
        db, user_id=user_id, date=today, progress_data=progress_data
    ) 