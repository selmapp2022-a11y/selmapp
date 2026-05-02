from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, func, select, update
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.crud.base import CRUDBase
from app.models.personalization import (
    UserLearningProfile, PersonalizedLearningPath, LearningPathMilestone,
    ContentRecommendation, PersonalTrainerInteraction, LearningAnalytics,
    AdaptiveLearningRule, UserOnboarding, CategoryLearningTemplate, UserCategoryPreference
)
from app.schemas.personalization import (
    UserLearningProfileCreate, UserLearningProfileUpdate,
    PersonalizedLearningPathCreate, PersonalizedLearningPathUpdate,
    LearningPathMilestoneCreate, ContentRecommendationCreate,
    ContentRecommendationUpdate, PersonalTrainerInteractionCreate,
    PersonalTrainerInteractionUpdate, LearningAnalyticsCreate,
    AdaptiveLearningRuleCreate, AdaptiveLearningRuleUpdate,
    UserOnboardingCreate, UserCategoryPreferenceCreate
)

class CRUDUserLearningProfile(CRUDBase[UserLearningProfile, UserLearningProfileCreate, UserLearningProfileUpdate]):
    async def get_by_user_id(self, db: AsyncSession, *, user_id: int) -> Optional[UserLearningProfile]:
        result = await db.execute(
            select(UserLearningProfile).where(UserLearningProfile.user_id == user_id)
        )
        return result.scalars().first()
    
    async def create_or_update_profile(self, db: AsyncSession, *, user_id: int, profile_data: UserLearningProfileCreate) -> UserLearningProfile:
        existing_profile = await self.get_by_user_id(db, user_id=user_id)
        if existing_profile:
            profile_update = UserLearningProfileUpdate(**profile_data.dict(exclude={'user_id'}))
            return await self.update(db, db_obj=existing_profile, obj_in=profile_update)
        return await self.create(db, obj_in=profile_data)
    
    async def get_profiles_by_learning_style(self, db: AsyncSession, *, learning_style: str, skip: int = 0, limit: int = 100) -> List[UserLearningProfile]:
        result = await db.execute(
            select(UserLearningProfile)
            .where(UserLearningProfile.learning_style == learning_style)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_profiles_by_goal(self, db: AsyncSession, *, primary_goal: str, skip: int = 0, limit: int = 100) -> List[UserLearningProfile]:
        result = await db.execute(
            select(UserLearningProfile)
            .where(UserLearningProfile.primary_goal == primary_goal)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update_learning_metrics(self, db: AsyncSession, *, user_id: int, learning_rate: float, retention_rate: float) -> Optional[UserLearningProfile]:
        profile = await self.get_by_user_id(db, user_id=user_id)
        if profile:
            profile.learning_rate = learning_rate
            profile.retention_rate = retention_rate
            await db.commit()
            await db.refresh(profile)
        return profile

class CRUDPersonalizedLearningPath(CRUDBase[PersonalizedLearningPath, PersonalizedLearningPathCreate, PersonalizedLearningPathUpdate]):
    async def get_by_user_profile(self, db: AsyncSession, *, user_profile_id: int, skip: int = 0, limit: int = 100) -> List[PersonalizedLearningPath]:
        result = await db.execute(
            select(PersonalizedLearningPath)
                .options(selectinload(PersonalizedLearningPath.milestones))
                .where(PersonalizedLearningPath.user_profile_id == user_profile_id)
                .offset(skip)
                .limit(limit)
        )
        return result.scalars().all()
    
    async def get_active_path(self, db: AsyncSession, *, user_profile_id: int) -> Optional[PersonalizedLearningPath]:
        result = await db.execute(
            select(PersonalizedLearningPath)
            .options(selectinload(PersonalizedLearningPath.milestones))
            .where(
                and_(
                    PersonalizedLearningPath.user_profile_id == user_profile_id,
                    PersonalizedLearningPath.is_active.is_(True),
                    PersonalizedLearningPath.is_completed.is_(False),
                )
            )
        )
        return result.scalars().first()
    
    async def update_progress(self, db: AsyncSession, *, path_id: int, current_step: int, performance_score: float) -> Optional[PersonalizedLearningPath]:
        path = await self.get(db, id=path_id)
        if path:
            path.current_step = current_step
            path.completion_percentage = (current_step / path.total_steps) * 100
            path.average_performance = (path.average_performance + performance_score) / 2
            path.last_activity_date = datetime.utcnow()
            
            if current_step >= path.total_steps:
                path.is_completed = True
                path.is_active = False
            
            await db.commit()
            await db.refresh(path)
        return path
    
    async def get_completed_paths(self, db: AsyncSession, *, user_profile_id: int) -> List[PersonalizedLearningPath]:
        result = await db.execute(
            select(PersonalizedLearningPath).where(
                and_(
                    PersonalizedLearningPath.user_profile_id == user_profile_id,
                    PersonalizedLearningPath.is_completed.is_(True)
                )
            )
        )
        return result.scalars().all()
    
    async def apply_adaptive_adjustment(self, db: AsyncSession, *, path_id: int, adjustments: Dict[str, Any]) -> Optional[PersonalizedLearningPath]:
        path = await self.get(db, id=path_id)
        if path:
            if not path.adaptive_adjustments:
                path.adaptive_adjustments = {}
            path.adaptive_adjustments.update(adjustments)
            await db.commit()
            await db.refresh(path)
        return path

class CRUDLearningPathMilestone(CRUDBase[LearningPathMilestone, LearningPathMilestoneCreate, Dict]):
    async def get_by_learning_path(self, db: AsyncSession, *, learning_path_id: int) -> List[LearningPathMilestone]:
        result = await db.execute(
            select(LearningPathMilestone)
            .where(LearningPathMilestone.learning_path_id == learning_path_id)
            .order_by(LearningPathMilestone.step_number)
        )
        return result.scalars().all()
    
    async def get_current_milestone(self, db: AsyncSession, *, learning_path_id: int, current_step: int) -> Optional[LearningPathMilestone]:
        result = await db.execute(
            select(LearningPathMilestone).where(
                and_(
                    LearningPathMilestone.learning_path_id == learning_path_id,
                    LearningPathMilestone.step_number == current_step
                )
            )
        )
        return result.scalars().first()
    
    async def complete_milestone(self, db: AsyncSession, *, milestone_id: int, performance_score: float) -> Optional[LearningPathMilestone]:
        milestone = await self.get(db, id=milestone_id)
        if milestone:
            milestone.is_completed = True
            milestone.completion_date = datetime.utcnow()
            milestone.performance_score = performance_score
            await db.commit()
            await db.refresh(milestone)
        return milestone
    
    async def get_completed_milestones(self, db: AsyncSession, *, learning_path_id: int) -> List[LearningPathMilestone]:
        result = await db.execute(
            select(LearningPathMilestone).where(
                and_(
                    LearningPathMilestone.learning_path_id == learning_path_id,
                    LearningPathMilestone.is_completed.is_(True)
                )
            )
        )
        return result.scalars().all()

class CRUDContentRecommendation(CRUDBase[ContentRecommendation, ContentRecommendationCreate, ContentRecommendationUpdate]):
    async def get_by_user_profile(self, db: AsyncSession, *, user_profile_id: int, active_only: bool = True, skip: int = 0, limit: int = 100) -> List[ContentRecommendation]:
        stmt = select(ContentRecommendation).where(
            ContentRecommendation.user_profile_id == user_profile_id
        )
        
        if active_only:
            stmt = stmt.where(
                and_(
                    ContentRecommendation.is_active.is_(True),
                    or_(
                        ContentRecommendation.expires_at.is_(None),
                        ContentRecommendation.expires_at > datetime.utcnow()
                    )
                )
            )
        
        stmt = stmt.order_by(desc(ContentRecommendation.priority_score)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_by_type(self, db: AsyncSession, *, user_profile_id: int, recommendation_type: str, skip: int = 0, limit: int = 100) -> List[ContentRecommendation]:
        result = await db.execute(
            select(ContentRecommendation)
            .where(
                and_(
                    ContentRecommendation.user_profile_id == user_profile_id,
                    ContentRecommendation.recommendation_type == recommendation_type,
                    ContentRecommendation.is_active.is_(True)
                )
            )
            .order_by(desc(ContentRecommendation.relevance_score))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_high_priority(self, db: AsyncSession, *, user_profile_id: int, priority_threshold: float = 0.7) -> List[ContentRecommendation]:
        result = await db.execute(
            select(ContentRecommendation)
            .where(
                and_(
                    ContentRecommendation.user_profile_id == user_profile_id,
                    ContentRecommendation.priority_score >= priority_threshold,
                    ContentRecommendation.is_active.is_(True)
                )
            )
            .order_by(desc(ContentRecommendation.priority_score))
        )
        return result.scalars().all()
    
    async def mark_as_accepted(self, db: AsyncSession, *, recommendation_id: int) -> Optional[ContentRecommendation]:
        recommendation = await self.get(db, id=recommendation_id)
        if recommendation:
            recommendation.is_accepted = True
            await db.commit()
            await db.refresh(recommendation)
        return recommendation
    
    async def mark_as_completed(self, db: AsyncSession, *, recommendation_id: int, rating: Optional[int] = None, feedback: Optional[str] = None) -> Optional[ContentRecommendation]:
        recommendation = await self.get(db, id=recommendation_id)
        if recommendation:
            recommendation.is_completed = True
            if rating is not None:
                recommendation.user_rating = rating
            if feedback:
                recommendation.user_feedback = feedback
            await db.commit()
            await db.refresh(recommendation)
        return recommendation
    
    async def expire_old_recommendations(self, db: AsyncSession) -> int:
        stmt = (
            update(ContentRecommendation)
            .where(
                and_(
                    ContentRecommendation.expires_at < datetime.utcnow(),
                    ContentRecommendation.is_active.is_(True)
                )
            )
            .values(is_active=False)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0

class CRUDPersonalTrainerInteraction(CRUDBase[PersonalTrainerInteraction, PersonalTrainerInteractionCreate, PersonalTrainerInteractionUpdate]):
    async def get_by_user_profile(self, db: AsyncSession, *, user_profile_id: int, skip: int = 0, limit: int = 100) -> List[PersonalTrainerInteraction]:
        result = await db.execute(
            select(PersonalTrainerInteraction)
            .where(PersonalTrainerInteraction.user_profile_id == user_profile_id)
            .order_by(desc(PersonalTrainerInteraction.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_session(self, db: AsyncSession, *, session_id: str) -> List[PersonalTrainerInteraction]:
        result = await db.execute(
            select(PersonalTrainerInteraction)
            .where(PersonalTrainerInteraction.session_id == session_id)
            .order_by(PersonalTrainerInteraction.created_at)
        )
        return result.scalars().all()
    
    async def get_recent_interactions(self, db: AsyncSession, *, user_profile_id: int, hours: int = 24) -> List[PersonalTrainerInteraction]:
        since_time = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(PersonalTrainerInteraction)
            .where(
                and_(
                    PersonalTrainerInteraction.user_profile_id == user_profile_id,
                    PersonalTrainerInteraction.created_at >= since_time
                )
            )
            .order_by(desc(PersonalTrainerInteraction.created_at))
        )
        return result.scalars().all()
    
    async def get_by_type(self, db: AsyncSession, *, user_profile_id: int, interaction_type: str, skip: int = 0, limit: int = 100) -> List[PersonalTrainerInteraction]:
        result = await db.execute(
            select(PersonalTrainerInteraction)
            .where(
                and_(
                    PersonalTrainerInteraction.user_profile_id == user_profile_id,
                    PersonalTrainerInteraction.interaction_type == interaction_type
                )
            )
            .order_by(desc(PersonalTrainerInteraction.created_at))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update_response(self, db: AsyncSession, *, interaction_id: int, user_response: str, engagement_score: Optional[float] = None) -> Optional[PersonalTrainerInteraction]:
        interaction = await self.get(db, id=interaction_id)
        if interaction:
            interaction.user_response = user_response
            interaction.responded_at = datetime.utcnow()
            if engagement_score is not None:
                interaction.user_engagement_score = engagement_score
            await db.commit()
            await db.refresh(interaction)
        return interaction
    
    async def get_unanswered_interactions(self, db: AsyncSession, *, user_profile_id: int) -> List[PersonalTrainerInteraction]:
        result = await db.execute(
            select(PersonalTrainerInteraction)
            .where(
                and_(
                    PersonalTrainerInteraction.user_profile_id == user_profile_id,
                    PersonalTrainerInteraction.user_response.is_(None)
                )
            )
            .order_by(PersonalTrainerInteraction.created_at)
        )
        return result.scalars().all()

class CRUDLearningAnalytics(CRUDBase[LearningAnalytics, LearningAnalyticsCreate, Dict]):
    async def get_by_user_profile(self, db: AsyncSession, *, user_profile_id: int, period_type: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[LearningAnalytics]:
        stmt = select(LearningAnalytics).where(LearningAnalytics.user_profile_id == user_profile_id)
        if period_type:
            stmt = stmt.where(LearningAnalytics.period_type == period_type)
        stmt = stmt.order_by(desc(LearningAnalytics.date)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_date_range(self, db: AsyncSession, *, user_profile_id: int, start_date: datetime, end_date: datetime) -> List[LearningAnalytics]:
        result = await db.execute(
            select(LearningAnalytics)
            .where(
                and_(
                    LearningAnalytics.user_profile_id == user_profile_id,
                    LearningAnalytics.date >= start_date,
                    LearningAnalytics.date <= end_date
                )
            )
            .order_by(LearningAnalytics.date)
        )
        return result.scalars().all()
    
    async def get_latest_analytics(self, db: AsyncSession, *, user_profile_id: int, period_type: str) -> Optional[LearningAnalytics]:
        result = await db.execute(
            select(LearningAnalytics)
            .where(
                and_(
                    LearningAnalytics.user_profile_id == user_profile_id,
                    LearningAnalytics.period_type == period_type
                )
            )
            .order_by(desc(LearningAnalytics.date))
        )
        return result.scalars().first()
    
    async def create_or_update_daily(self, db: AsyncSession, *, user_profile_id: int, analytics_data: Dict[str, Any]) -> LearningAnalytics:
        today = datetime.utcnow().date()
        result = await db.execute(
            select(LearningAnalytics).where(
                and_(
                    LearningAnalytics.user_profile_id == user_profile_id,
                    LearningAnalytics.period_type == "daily",
                    func.date(LearningAnalytics.date) == today
                )
            )
        )
        existing = result.scalars().first()
        
        if existing:
            for key, value in analytics_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            await db.commit()
            await db.refresh(existing)
            return existing
        
        new_analytics = LearningAnalyticsCreate(
            user_profile_id=user_profile_id,
            date=datetime.utcnow(),
            period_type="daily",
            **analytics_data
        )
        return await self.create(db, obj_in=new_analytics)
    
    async def get_performance_trends(self, db: AsyncSession, *, user_profile_id: int, days: int = 30) -> List[LearningAnalytics]:
        since_date = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(LearningAnalytics)
            .where(
                and_(
                    LearningAnalytics.user_profile_id == user_profile_id,
                    LearningAnalytics.date >= since_date,
                    LearningAnalytics.period_type == "daily"
                )
            )
            .order_by(LearningAnalytics.date)
        )
        return result.scalars().all()

    async def get_recent_analytics(self, db: AsyncSession, *, user_profile_id: int, days: int = 30) -> List[LearningAnalytics]:
        since_date = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(LearningAnalytics)
            .where(
                and_(
                    LearningAnalytics.user_profile_id == user_profile_id,
                    LearningAnalytics.date >= since_date
                )
            )
            .order_by(desc(LearningAnalytics.date))
        )
        return result.scalars().all()

class CRUDAdaptiveLearningRule(CRUDBase[AdaptiveLearningRule, AdaptiveLearningRuleCreate, AdaptiveLearningRuleUpdate]):
    async def get_active_rules(self, db: AsyncSession, *, rule_type: Optional[str] = None) -> List[AdaptiveLearningRule]:
        stmt = select(AdaptiveLearningRule).where(AdaptiveLearningRule.is_active.is_(True))
        if rule_type:
            stmt = stmt.where(AdaptiveLearningRule.rule_type == rule_type)
        stmt = stmt.order_by(desc(AdaptiveLearningRule.priority))
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def increment_trigger_count(self, db: AsyncSession, *, rule_id: int) -> Optional[AdaptiveLearningRule]:
        rule = await self.get(db, id=rule_id)
        if rule:
            rule.trigger_count += 1
            await db.commit()
            await db.refresh(rule)
        return rule
    
    async def update_success_rate(self, db: AsyncSession, *, rule_id: int, success: bool) -> Optional[AdaptiveLearningRule]:
        rule = await self.get(db, id=rule_id)
        if rule:
            if rule.trigger_count > 0:
                current_successes = rule.success_rate * rule.trigger_count
                new_successes = current_successes + (1 if success else 0)
                rule.success_rate = new_successes / rule.trigger_count
            else:
                rule.success_rate = 1.0 if success else 0.0
            await db.commit()
            await db.refresh(rule)
        return rule
    
    async def get_rules_by_type(self, db: AsyncSession, *, rule_type: str) -> List[AdaptiveLearningRule]:
        result = await db.execute(
            select(AdaptiveLearningRule)
            .where(
                and_(
                    AdaptiveLearningRule.rule_type == rule_type,
                    AdaptiveLearningRule.is_active.is_(True)
                )
            )
            .order_by(desc(AdaptiveLearningRule.priority))
        )
        return result.scalars().all()

# Create CRUD instances
learning_profile = CRUDUserLearningProfile(UserLearningProfile)
learning_path = CRUDPersonalizedLearningPath(PersonalizedLearningPath)
learning_milestone = CRUDLearningPathMilestone(LearningPathMilestone)
content_recommendation = CRUDContentRecommendation(ContentRecommendation)
trainer_interaction = CRUDPersonalTrainerInteraction(PersonalTrainerInteraction)
learning_analytics = CRUDLearningAnalytics(LearningAnalytics)
adaptive_rule = CRUDAdaptiveLearningRule(AdaptiveLearningRule)

# Add new CRUD classes for onboarding models
class CRUDUserOnboarding(CRUDBase):
    def __init__(self, model):
        super().__init__(model)
    
    async def get_by_user_id(self, db: AsyncSession, *, user_id: int):
        result = await db.execute(select(self.model).where(self.model.user_id == user_id))
        return result.scalars().first()
    
    async def create_for_user(self, db: AsyncSession, *, user_id: int, obj_in: Dict[str, Any] = None):
        if obj_in is None:
            obj_in = {}
        obj_in['user_id'] = user_id
        create_data = UserOnboardingCreate(**obj_in)
        return await self.create(db, obj_in=create_data)
    
    async def update_step(self, db: AsyncSession, *, user_id: int, step: str, step_data: Dict[str, Any] = None):
        from app.models.personalization import OnboardingStep
        
        onboarding = await self.get_by_user_id(db, user_id=user_id)
        if not onboarding:
            # Create new onboarding record
            onboarding = await self.create_for_user(db, user_id=user_id, obj_in={"current_step": step})
        
        # Calculate completion percentage
        step_order = [
            OnboardingStep.WELCOME.value,
            OnboardingStep.LEVEL_ASSESSMENT.value,
            OnboardingStep.CATEGORY_SELECTION.value,
            OnboardingStep.GOALS_SETTING.value,
            OnboardingStep.PREFERENCES_SETUP.value,
            OnboardingStep.LEARNING_PATH_GENERATION.value,
            OnboardingStep.COMPLETED.value
        ]
        current_index = next((i for i, s in enumerate(step_order) if s == step), 0)
        completion_percentage = (current_index / (len(step_order) - 1)) * 100
        
        update_data = {
            "current_step": step,
            "completion_percentage": completion_percentage,
            "last_step_completed_at": func.now(),
            "is_completed": step == OnboardingStep.COMPLETED.value
        }
        
        if step == OnboardingStep.COMPLETED.value:
            update_data["completed_at"] = func.now()
        
        if step_data:
            # Merge step-specific data
            if step == OnboardingStep.LEVEL_ASSESSMENT.value:
                update_data.update({
                    "assessed_level": step_data.get("assessed_level"),
                    "assessment_score": step_data.get("assessment_score"),
                    "assessment_details": step_data.get("assessment_details", {})
                })
            elif step == OnboardingStep.CATEGORY_SELECTION.value:
                update_data.update({
                    "selected_categories": step_data.get("selected_categories", []),
                    "primary_category": step_data.get("primary_category"),
                    "category_priorities": step_data.get("category_priorities", {})
                })
            elif step == OnboardingStep.GOALS_SETTING.value:
                update_data.update({
                    "learning_goals": step_data.get("learning_goals", []),
                    "motivation_factors": step_data.get("motivation_factors", []),
                    "target_timeline": step_data.get("target_timeline"),
                    "daily_study_commitment": step_data.get("daily_study_commitment", 30)
                })
            elif step == OnboardingStep.PREFERENCES_SETUP.value:
                update_data.update({
                    "preferred_learning_style": step_data.get("preferred_learning_style"),
                    "preferred_difficulty": step_data.get("preferred_difficulty", "gradual"),
                    "preferred_content_types": step_data.get("preferred_content_types", [])
                })
        
        return await self.update(db, db_obj=onboarding, obj_in=update_data)
    
    async def complete_onboarding(self, db: AsyncSession, *, user_id: int, feedback: str = None, rating: int = None):
        onboarding = await self.get_by_user_id(db, user_id=user_id)
        if not onboarding:
            raise ValueError("Onboarding record not found")
        
        update_data = {
            "current_step": "completed",
            "is_completed": True,
            "completion_percentage": 100.0,
            "completed_at": func.now(),
            "onboarding_feedback": feedback,
            "onboarding_rating": rating
        }
        
        return await self.update(db, db_obj=onboarding, obj_in=update_data)

class CRUDCategoryLearningTemplate(CRUDBase):
    def __init__(self, model):
        super().__init__(model)
    
    async def get_by_category(self, db: AsyncSession, *, category: str, level: str = None, skip: int = 0, limit: int = 100):
        stmt = select(self.model).where(
            self.model.category == category,
            self.model.is_active.is_(True)
        )
        
        if level:
            # Filter templates that support the given level
            stmt = stmt.where(self.model.target_levels.contains([level]))
        
        result = await db.execute(stmt.offset(skip).limit(limit))
        return result.scalars().all()
    
    async def get_active_templates(self, db: AsyncSession, *, skip: int = 0, limit: int = 100):
        result = await db.execute(
            select(self.model)
            .where(self.model.is_active.is_(True))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_level(self, db: AsyncSession, *, level: str, skip: int = 0, limit: int = 100):
        result = await db.execute(
            select(self.model)
            .where(
                self.model.target_levels.contains([level]),
                self.model.is_active.is_(True)
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def increment_usage(self, db: AsyncSession, *, template_id: int):
        template = await self.get(db, id=template_id)
        if template:
            template.usage_count += 1
            await db.commit()
            await db.refresh(template)
        return template

class CRUDUserCategoryPreference(CRUDBase):
    def __init__(self, model):
        super().__init__(model)
    
    async def get_by_user_id(self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100):
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_by_user_and_category(self, db: AsyncSession, *, user_id: int, category: str):
        result = await db.execute(
            select(self.model).where(
                self.model.user_id == user_id,
                self.model.category == category
            )
        )
        return result.scalars().first()
    
    async def get_user_priorities(self, db: AsyncSession, *, user_id: int):
        result = await db.execute(
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.is_active.is_(True)
            )
            .order_by(self.model.priority_level.asc())
        )
        return result.scalars().all()
    
    async def create_from_onboarding(self, db: AsyncSession, *, user_id: int, categories: List[str], 
                             primary_category: str, priorities: Dict[str, int] = None):
        preferences = []
        
        for i, category in enumerate(categories):
            priority = priorities.get(category, i + 1) if priorities else i + 1
            interest_score = 1.0 if category == primary_category else 0.8
            
            preference_data = UserCategoryPreferenceCreate(
                user_id=user_id,
                category=category,
                priority_level=priority,
                interest_score=interest_score
            )
            
            preference = await self.create(db, obj_in=preference_data)
            preferences.append(preference)
        
        return preferences

# New CRUD instances
user_onboarding = CRUDUserOnboarding(UserOnboarding)
category_learning_template = CRUDCategoryLearningTemplate(CategoryLearningTemplate)
user_category_preference = CRUDUserCategoryPreference(UserCategoryPreference) 