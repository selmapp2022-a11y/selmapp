from typing import List, Dict, Any, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_current_user, get_db
from app.crud.personalization import (
    learning_profile, learning_path, learning_milestone,
    content_recommendation, trainer_interaction, learning_analytics,
    user_onboarding, category_learning_template, user_category_preference
)
from app.schemas.personalization import (
    UserLearningProfile, UserLearningProfileCreate, UserLearningProfileUpdate,
    PersonalizedLearningPath, PersonalizedLearningPathCreate, PersonalizedLearningPathUpdate,
    LearningPathMilestone, ContentRecommendation, ContentRecommendationCreate,
    ContentRecommendationUpdate, PersonalTrainerInteraction,
    PersonalTrainerInteractionCreate, PersonalTrainerInteractionUpdate,
    LearningAnalytics, LearningAnalyticsCreate, PersonalizationDashboard,
    ChatWithTrainerRequest, ChatWithTrainerResponse, GenerateLearningPathRequest,
    UpdateLearningProgressRequest, LearningInsights,
    UserOnboarding, UserOnboardingCreate, UserOnboardingUpdate,
    CategoryLearningTemplate, CategoryLearningTemplateCreate, CategoryLearningTemplateUpdate,
    UserCategoryPreference, UserCategoryPreferenceCreate, UserCategoryPreferenceUpdate,
    OnboardingStepRequest, OnboardingStepResponse, CategorySelectionRequest,
    LevelAssessmentRequest, LevelAssessmentResult, OnboardingCompletionSummary
)
from app.schemas.user import User
from app.services.personalization_service import PersonalizationService
from app.models.personalization import LearningGoalType, LearningStyle, PersonalityType

logger = logging.getLogger(__name__)
router = APIRouter()
personalization_service = PersonalizationService()

# Learning Profile Endpoints
@router.post("/profile/", response_model=UserLearningProfile)
async def create_learning_profile(
    *,
    db: AsyncSession = Depends(get_db),
    profile_in: UserLearningProfileCreate,
    current_user: User = Depends(get_current_user)
):
    """Create or update user learning profile"""
    try:
        result = await personalization_service.create_user_profile(
            db, user_id=current_user.id, profile_data=profile_in.dict()
        )
        return result["profile"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/profile/", response_model=UserLearningProfile)
async def get_learning_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's learning profile"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    return profile

@router.put("/profile/", response_model=UserLearningProfile)
async def update_learning_profile(
    *,
    db: AsyncSession = Depends(get_db),
    profile_update: UserLearningProfileUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update user learning profile"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    updated_profile = await learning_profile.update(db, db_obj=profile, obj_in=profile_update)
    return updated_profile

# Learning Path Endpoints
@router.post("/learning-path/generate/", response_model=PersonalizedLearningPath)
async def generate_learning_path_endpoint(
    *,
    db: AsyncSession = Depends(get_db),
    path_request: GenerateLearningPathRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate a new personalized learning path"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found. Please create a profile first."
        )
    
    try:
        result = await personalization_service.generate_learning_path(db, profile.id)
        return result["learning_path"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/learning-path/active/", response_model=Optional[PersonalizedLearningPath])
async def get_active_learning_path(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's active learning path"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    active_path = None
    if not profile:
        # Best-practice: rebuild from onboarding data so we keep the user's real choices.
        logger.info("Learning profile missing; bootstrapping from onboarding for user_id=%s", current_user.id)
        try:
            creation = await personalization_service.bootstrap_profile_from_onboarding(
                db, user_id=current_user.id
            )
            profile = creation.get("profile")
            created_path = creation.get("learning_path")
            active_path = (
                created_path.get("learning_path")
                if isinstance(created_path, dict)
                else created_path
            )
        except ValueError:
            # No onboarding data to rebuild from (common for brand-new users).
            # Returning null avoids noisy 404s in browser consoles (Flutter web logs 404s),
            # and lets the client decide to route the user into onboarding.
            return None
        except Exception as e:
            logger.error("Bootstrap learning profile failed for user_id=%s: %s", current_user.id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not restore your learning profile. Please retry."
            )

    if not active_path:
        active_path = await learning_path.get_active_path(db, user_profile_id=profile.id)

    # Repair stored path modules:
    # - older clients saved repeated ids (day_1..day_12)
    # - some paths have incorrect isUnlocked flags allowing jumping ahead
    try:
        pd_raw = getattr(active_path, "path_data", None) or {}
        pd = dict(pd_raw) if isinstance(pd_raw, dict) else {}
        if isinstance(pd, dict) and isinstance(pd.get("modules"), list):
            mods = list(pd.get("modules") or [])
            # Consecutive completed days from the start (used to enforce sequential unlocking).
            consecutive_completed = 0
            for m in mods:
                if not isinstance(m, dict):
                    break
                if m.get("isCompleted") is True or m.get("is_completed") is True:
                    consecutive_completed += 1
                else:
                    break

            fixed: list[dict] = []
            needs_save = False
            changed = {
                "id": 0,
                "isUnlocked": 0,
                "is_unlocked": 0,
                "isCompleted_reset": 0,
                "is_completed_reset": 0,
                "progressPercentage_reset": 0,
                "progress_percentage_reset": 0,
            }

            for idx, m in enumerate(mods):
                mm = dict(m) if isinstance(m, dict) else {}
                if not isinstance(m, dict):
                    needs_save = True

                # Always normalize ids to stable global day indexing: day_1..day_N
                new_id = f"day_{idx + 1}"
                if mm.get("id") != new_id:
                    mm["id"] = new_id
                    needs_save = True
                    changed["id"] += 1

                completed = mm.get("isCompleted") is True or mm.get("is_completed") is True

                # Data repair: if we have a gap (non-consecutive completion),
                # older clients could mark future days as completed due to duplicated ids.
                # Enforce a strict sequential completion model by resetting any completed
                # flags after the first incomplete day.
                if completed and idx > consecutive_completed:
                    mm["isCompleted"] = False
                    mm["is_completed"] = False
                    completed = False
                    needs_save = True
                    changed["isCompleted_reset"] += 1
                    changed["is_completed_reset"] += 1

                    # Also reset progress percentage if it looks like "completed".
                    pp = mm.get("progressPercentage")
                    if isinstance(pp, (int, float)) and float(pp) >= 100.0:
                        mm["progressPercentage"] = 0.0
                        changed["progressPercentage_reset"] += 1
                    pp2 = mm.get("progress_percentage")
                    if isinstance(pp2, (int, float)) and float(pp2) >= 100.0:
                        mm["progress_percentage"] = 0.0
                        changed["progress_percentage_reset"] += 1
                # Unlock rule: allow up to "next day" after consecutive completed streak.
                # (We do NOT unlock future "completed" days because non-consecutive completion
                # can be corrupted data.)
                should_unlocked = idx <= consecutive_completed

                if mm.get("isUnlocked") != should_unlocked:
                    mm["isUnlocked"] = should_unlocked
                    needs_save = True
                    changed["isUnlocked"] += 1
                if mm.get("is_unlocked") != should_unlocked:
                    mm["is_unlocked"] = should_unlocked
                    needs_save = True
                    changed["is_unlocked"] += 1

                fixed.append(mm)

            # Always apply repaired modules for the response (even if DB save fails).
            new_pd = dict(pd)
            new_pd["modules"] = fixed
            active_path.path_data = new_pd  # type: ignore[attr-defined]
            try:
                flag_modified(active_path, "path_data")
            except Exception:
                pass

            if needs_save:
                db.add(active_path)
                await db.commit()
                await db.refresh(active_path)
    except Exception:
        pass
    return active_path


@router.post("/learning-path/save/", response_model=Dict[str, Any])
async def save_learning_path_from_client(
    *,
    db: AsyncSession = Depends(get_db),
    path_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Save a learning path from the Flutter client.
    This endpoint receives the learning path generated by the client after onboarding
    and persists it in the backend database for reliable recovery on app restart.
    """
    try:
        logger.info("Saving learning path for user_id=%s", current_user.id)
        
        # Get or create user learning profile
        profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
        if not profile:
            # Create a basic profile from the path data
            from app.schemas.personalization import UserLearningProfileCreate
            from app.models.personalization import LearningGoalType, LearningStyle
            
            profile_create = UserLearningProfileCreate(
                user_id=current_user.id,
                target_cefr_level=path_data.get('currentLevel', 'A1'),
                primary_goal=LearningGoalType.FLUENCY,
                learning_style=LearningStyle.MIXED,
                daily_practice_minutes=path_data.get('pace', {}).get('averageDailyMinutes', 25) if isinstance(path_data.get('pace'), dict) else 25,
            )
            profile = await learning_profile.create(db, obj_in=profile_create)
            logger.info("Created learning profile for user_id=%s", current_user.id)
        
        # Parse modules from the path data
        modules_data = path_data.get('modules', [])
        categories = path_data.get('categories', [])
        current_level = path_data.get('currentLevel', 'A1')
        target_level = path_data.get('targetLevel', 'B1')

        # Normalize modules to ensure UNIQUE ids (fixes repeated day_1..day_12 loops in Journey)
        normalized_modules: list[dict] = []
        if isinstance(modules_data, list):
            for i, m in enumerate(modules_data):
                if not isinstance(m, dict):
                    continue
                mm = dict(m)
                mm["id"] = f"day_{i + 1}"
                normalized_modules.append(mm)
        modules_data = normalized_modules
        
        # Build path_data structure for database
        path_structure = {
            "categories": categories,
            "current_level": current_level,
            "target_level": target_level,
            "modules": modules_data,
            "created_from": "flutter_client",
        }
        
        # Create or update the learning path
        from app.schemas.personalization import PersonalizedLearningPathCreate
        
        # Deactivate any existing active paths
        existing_paths = await learning_path.get_by_user_profile(db, user_profile_id=profile.id)
        for existing in existing_paths:
            if existing.is_active and not existing.is_completed:
                await learning_path.update(db, db_obj=existing, obj_in={"is_active": False})
        
        # Create new active path
        path_create = PersonalizedLearningPathCreate(
            user_profile_id=profile.id,
            name=f"Personalized Path to {target_level}",
            description=f"Your learning journey from {current_level} to {target_level}",
            estimated_duration_weeks=len(modules_data) // 2 if modules_data else 12,
            total_steps=len(modules_data) if modules_data else 8,
            path_data=path_structure,
        )
        
        new_path = await learning_path.create(db, obj_in=path_create)
        logger.info("Created learning path id=%s for user_id=%s", new_path.id, current_user.id)
        
        return {
            "success": True,
            "path_id": new_path.id,
            "message": "Learning path saved successfully",
        }
        
    except Exception as e:
        logger.error("Error saving learning path for user_id=%s: %s", current_user.id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save learning path: {str(e)}"
        )

@router.get("/learning-path/", response_model=List[PersonalizedLearningPath])
async def get_learning_paths(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """Get user's learning paths"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    paths = await learning_path.get_by_user_profile(
        db, user_profile_id=profile.id, skip=skip, limit=limit
    )
    return paths

@router.put("/learning-path/{path_id}/progress/", response_model=PersonalizedLearningPath)
async def update_learning_path_progress(
    *,
    db: AsyncSession = Depends(get_db),
    path_id: int,
    progress_update: UpdateLearningProgressRequest,
    current_user: User = Depends(get_current_user)
):
    """Update learning path progress"""
    path = await learning_path.get(db, id=path_id)
    if not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    # Verify ownership
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile or path.user_profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this learning path"
        )
    
    # Update progress
    updated_path = await learning_path.update_progress(
        db,
        path_id=path_id,
        current_step=path.current_step + 1,
        performance_score=progress_update.performance_score
    )
    
    return updated_path

@router.get("/learning-path/{path_id}/milestones/", response_model=List[LearningPathMilestone])
async def get_learning_path_milestones(
    *,
    db: AsyncSession = Depends(get_db),
    path_id: int,
    current_user: User = Depends(get_current_user)
):
    """Get milestones for a learning path"""
    path = await learning_path.get(db, id=path_id)
    if not path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning path not found"
        )
    
    # Verify ownership
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile or path.user_profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this learning path"
        )
    
    milestones = await learning_milestone.get_by_learning_path(db, learning_path_id=path_id)
    return milestones

# Content Recommendation Endpoints
@router.get("/recommendations/", response_model=List[ContentRecommendation])
async def get_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    recommendation_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50)
):
    """Get personalized content recommendations"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    if recommendation_type:
        recommendations = await content_recommendation.get_by_type(
            db, user_profile_id=profile.id, recommendation_type=recommendation_type,
            skip=skip, limit=limit
        )
    else:
        recommendations = await content_recommendation.get_by_user_profile(
            db, user_profile_id=profile.id, skip=skip, limit=limit
        )
    
    return recommendations

@router.post("/recommendations/generate/", response_model=List[ContentRecommendation])
async def generate_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=20)
):
    """Generate new personalized recommendations"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    try:
        recommendations = await personalization_service.generate_recommendations(
            db, user_profile_id=profile.id, limit=limit
        )
        return recommendations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/recommendations/{recommendation_id}/accept/", response_model=ContentRecommendation)
async def accept_recommendation(
    *,
    db: AsyncSession = Depends(get_db),
    recommendation_id: int,
    current_user: User = Depends(get_current_user)
):
    """Accept a content recommendation"""
    recommendation = await content_recommendation.get(db, id=recommendation_id)
    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found"
        )
    
    # Verify ownership
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile or recommendation.user_profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this recommendation"
        )
    
    updated_recommendation = await content_recommendation.mark_as_accepted(
        db, recommendation_id=recommendation_id
    )
    return updated_recommendation

@router.put("/recommendations/{recommendation_id}/complete/", response_model=ContentRecommendation)
async def complete_recommendation(
    *,
    db: AsyncSession = Depends(get_db),
    recommendation_id: int,
    recommendation_update: ContentRecommendationUpdate,
    current_user: User = Depends(get_current_user)
):
    """Mark recommendation as completed with feedback"""
    recommendation = await content_recommendation.get(db, id=recommendation_id)
    if not recommendation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found"
        )
    
    # Verify ownership
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile or recommendation.user_profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this recommendation"
        )
    
    updated_recommendation = await content_recommendation.mark_as_completed(
        db,
        recommendation_id=recommendation_id,
        rating=recommendation_update.user_rating,
        feedback=recommendation_update.user_feedback
    )
    return updated_recommendation

# Personal Trainer Endpoints
@router.post("/trainer/chat/", response_model=ChatWithTrainerResponse)
async def chat_with_trainer(
    *,
    db: AsyncSession = Depends(get_db),
    chat_request: ChatWithTrainerRequest,
    current_user: User = Depends(get_current_user)
):
    """Chat with AI personal trainer"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    try:
        response = await personalization_service.chat_with_trainer(
            db, user_profile_id=profile.id, 
            user_message=chat_request.message,
            context=chat_request.context
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/trainer/interactions/", response_model=List[PersonalTrainerInteraction])
async def get_trainer_interactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    interaction_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """Get trainer interaction history"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    if interaction_type:
        interactions = await trainer_interaction.get_by_type(
            db, user_profile_id=profile.id, interaction_type=interaction_type,
            skip=skip, limit=limit
        )
    else:
        interactions = await trainer_interaction.get_by_user_profile(
            db, user_profile_id=profile.id, skip=skip, limit=limit
        )
    
    return interactions

@router.put("/trainer/interactions/{interaction_id}/respond/", response_model=PersonalTrainerInteraction)
async def respond_to_trainer_interaction(
    *,
    db: AsyncSession = Depends(get_db),
    interaction_id: int,
    interaction_update: PersonalTrainerInteractionUpdate,
    current_user: User = Depends(get_current_user)
):
    """Respond to a trainer interaction"""
    interaction = await trainer_interaction.get(db, id=interaction_id)
    if not interaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interaction not found"
        )
    
    # Verify ownership
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile or interaction.user_profile_id != profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to respond to this interaction"
        )
    
    updated_interaction = await trainer_interaction.update_response(
        db,
        interaction_id=interaction_id,
        user_response=interaction_update.user_response,
        engagement_score=interaction_update.user_engagement_score
    )
    return updated_interaction

# Learning Analytics Endpoints
@router.get("/analytics/", response_model=List[LearningAnalytics])
async def get_learning_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    period_type: Optional[str] = Query(None, regex="^(daily|weekly|monthly)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100)
):
    """Get learning analytics data"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    analytics = await learning_analytics.get_by_user_profile(
        db, user_profile_id=profile.id, period_type=period_type,
        skip=skip, limit=limit
    )
    return analytics

@router.post("/analytics/", response_model=LearningAnalytics)
async def create_learning_analytics(
    *,
    db: AsyncSession = Depends(get_db),
    analytics_in: LearningAnalyticsCreate,
    current_user: User = Depends(get_current_user)
):
    """Create learning analytics entry"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    analytics_in.user_profile_id = profile.id
    analytics = await learning_analytics.create(db, obj_in=analytics_in)
    return analytics

# Insights and Dashboard
@router.get("/insights/", response_model=LearningInsights)
async def get_learning_insights_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive learning insights"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    try:
        insights = await personalization_service.get_learning_insights(db, profile.id)
        return insights
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/dashboard/", response_model=PersonalizationDashboard)
async def get_personalization_dashboard_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive personalization dashboard"""
    profile = await learning_profile.get_by_user_id(db, user_id=current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning profile not found"
        )
    
    try:
        dashboard = await personalization_service.get_personalization_dashboard(db, profile.id)
        return dashboard
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Onboarding Endpoints
@router.post("/onboarding/start/", response_model=Dict[str, Any])
async def start_onboarding(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start the onboarding process for a new user"""
    try:
        result = await personalization_service.start_onboarding(db, user_id=current_user.id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/interests/", response_model=Dict[str, Any])
async def get_user_interests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the user's personal interests (free-form topics for content personalization)."""
    onboarding = await user_onboarding.get_by_user_id(db, user_id=current_user.id)
    if not onboarding:
        return {"interests": []}
    details = onboarding.assessment_details or {}
    return {"interests": details.get("interests", [])}

@router.put("/interests/", response_model=Dict[str, Any])
async def update_user_interests(
    *,
    db: AsyncSession = Depends(get_db),
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update the user's personal interests. Body: {\"interests\": [...]}."""
    raw = payload.get("interests", [])
    if not isinstance(raw, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interests must be a list of strings")
    interests = []
    seen = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        s = item.strip()[:50]
        key = s.lower()
        if s and key not in seen:
            seen.add(key)
            interests.append(s)
        if len(interests) >= 20:
            break
    onboarding = await user_onboarding.get_by_user_id(db, user_id=current_user.id)
    if not onboarding:
        started = await personalization_service.start_onboarding(db, user_id=current_user.id)
        onboarding = started.get("onboarding")
    details = dict(onboarding.assessment_details or {})
    details["interests"] = interests
    onboarding.assessment_details = details
    flag_modified(onboarding, "assessment_details")
    await db.commit()
    await db.refresh(onboarding)
    return {"interests": interests, "count": len(interests)}

@router.get("/onboarding/categories/", response_model=List[Dict[str, Any]])
def get_learning_categories():
    """Get all available learning categories with descriptions"""
    return personalization_service.get_available_categories()

@router.post("/onboarding/assessment/", response_model=Dict[str, Any])
async def submit_level_assessment(
    *,
    db: AsyncSession = Depends(get_db),
    assessment_request: LevelAssessmentRequest,
    current_user: User = Depends(get_current_user)
):
    """Submit level assessment and get results"""
    try:
        result = await personalization_service.process_level_assessment(
            db, user_id=current_user.id, 
            assessment_data=assessment_request.dict()
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/onboarding/categories/select/", response_model=Dict[str, Any])
async def select_learning_categories(
    *,
    db: AsyncSession = Depends(get_db),
    category_request: CategorySelectionRequest,
    current_user: User = Depends(get_current_user)
):
    """Select learning categories and create preferences"""
    try:
        result = await personalization_service.process_category_selection(
            db, user_id=current_user.id,
            category_data=category_request.dict()
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/onboarding/complete/", response_model=OnboardingCompletionSummary)
async def complete_onboarding(
    *,
    db: AsyncSession = Depends(get_db),
    final_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Complete onboarding and generate personalized learning path"""
    try:
        result = await personalization_service.complete_onboarding_and_generate_path(
            db, user_id=current_user.id, final_data=final_data
        )
        return OnboardingCompletionSummary(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/onboarding/status/", response_model=UserOnboarding)
async def get_onboarding_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current onboarding status"""
    onboarding = await user_onboarding.get_by_user_id(db, user_id=current_user.id)
    if not onboarding:
        # Common for brand-new users: initialize onboarding instead of returning 404.
        # This prevents noisy 404 logs in Flutter web consoles and simplifies client logic.
        try:
            started = await personalization_service.start_onboarding(db, user_id=current_user.id)
            onboarding = started.get("onboarding")
        except Exception as e:
            logger.error("Failed to auto-start onboarding for user_id=%s: %s", current_user.id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not initialize onboarding. Please retry."
            )
        if not onboarding:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not initialize onboarding. Please retry."
            )
    return onboarding

@router.put("/onboarding/step/", response_model=OnboardingStepResponse)
async def update_onboarding_step(
    *,
    db: AsyncSession = Depends(get_db),
    step_request: OnboardingStepRequest,
    current_user: User = Depends(get_current_user)
):
    """Update current onboarding step"""
    try:
        onboarding = await user_onboarding.update_step(
            db, user_id=current_user.id,
            step=step_request.step.value,
            step_data=step_request.data
        )
        
        # Determine next step
        from app.models.personalization import OnboardingStep
        step_order = list(OnboardingStep)
        current_index = next((i for i, s in enumerate(step_order) if s.value == onboarding.current_step), 0)
        next_step = step_order[current_index + 1] if current_index < len(step_order) - 1 else None
        
        return OnboardingStepResponse(
            current_step=onboarding.current_step,
            next_step=next_step.value if next_step else None,
            completion_percentage=onboarding.completion_percentage,
            step_data=step_request.data,
            recommendations=personalization_service._get_onboarding_next_steps(onboarding.current_step),
            is_completed=onboarding.is_completed
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Category Preferences Endpoints
@router.get("/category-preferences/", response_model=List[UserCategoryPreference])
async def get_user_category_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user's category preferences"""
    preferences = await user_category_preference.get_by_user_id(db, user_id=current_user.id)
    return preferences

@router.put("/category-preferences/{preference_id}/", response_model=UserCategoryPreference)
async def update_category_preference(
    *,
    db: AsyncSession = Depends(get_db),
    preference_id: int,
    preference_update: UserCategoryPreferenceUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a specific category preference"""
    preference = await user_category_preference.get(db, id=preference_id)
    if not preference:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category preference not found"
        )
    
    # Verify ownership
    if preference.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this preference"
        )
    
    updated_preference = await user_category_preference.update(
        db, db_obj=preference, obj_in=preference_update
    )
    return updated_preference

@router.get("/category-templates/", response_model=List[CategoryLearningTemplate])
async def get_category_templates(
    db: AsyncSession = Depends(get_db),
    category: Optional[str] = Query(None),
    level: Optional[str] = Query(None, regex="^(A1|A2|B1|B2|C1|C2)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50)
):
    """Get available category learning templates"""
    if category:
        templates = await category_learning_template.get_by_category(
            db, category=category, level=level, skip=skip, limit=limit
        )
    elif level:
        templates = await category_learning_template.get_by_level(
            db, level=level, skip=skip, limit=limit
        )
    else:
        templates = await category_learning_template.get_active_templates(
            db, skip=skip, limit=limit
        )
    
    return templates

# Quick Actions
@router.post("/quick-start/", response_model=Dict[str, Any])
async def quick_start_personalization(
    *,
    db: AsyncSession = Depends(get_db),
    profile_data: UserLearningProfileCreate,
    current_user: User = Depends(get_current_user)
):
    """Quick start: Create profile, generate path, and get initial recommendations"""
    try:
        # Create profile and learning path
        result = await personalization_service.create_user_profile(
            db, user_id=current_user.id, profile_data=profile_data.dict()
        )
        
        # Generate initial recommendations
        recommendations = await personalization_service.generate_recommendations(
            db, user_profile_id=result["profile"].id, limit=5
        )
        
        return {
            "profile": result["profile"],
            "learning_path": result["learning_path"],
            "recommendations": recommendations,
            "message": "Personalization setup complete! You're ready to start learning."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) 