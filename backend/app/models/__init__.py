# Database Models
from .user import User, OAuth2Account, OAuthProvider
from .content import (
    Content, Vocabulary, Grammar, ContentType, DifficultyLevel, VocabularyStatus,
    UserVocabulary, VocabularySet, VocabularySetItem, VocabularyExercise
)
from .exercise import Exercise, ExerciseAttempt, Quiz, QuizExercise, QuizAttempt, ExerciseType
from .progress import UserProgress, DailyProgress, Achievement, UserAchievement, StudySession, LearningGoal
from .reading import ReadingText, ReadingExercise, ReadingAttempt, VocabularyHighlight, ReadingProgress
from .writing import WritingPrompt, WritingSubmission, WritingFeedback, WritingTemplate, WritingProgress, GrammarRule
from .listening import AudioContent, ListeningExercise, ListeningAttempt, ListeningExerciseAttempt, ListeningProgress, AudioPlaylist, AudioPlaylistItem
from .speaking import SpeakingPrompt, SpeakingAttempt, PronunciationExercise, PronunciationAttempt, SpeakingProgress, SpeakingSession, VoiceProfile
from .personalization import UserLearningProfile, PersonalizedLearningPath, LearningPathMilestone, ContentRecommendation, PersonalTrainerInteraction, LearningAnalytics, AdaptiveLearningRule, UserOnboarding, CategoryLearningTemplate, UserCategoryPreference
from .lessons import AIGeneratedLesson, LessonProgress, LessonGenerationAnalytics, LessonTemplate
from .payment import (
    Payment, Subscription, ContentAccess, ContentLockConfig,
    PaymentWebhook, Refund, SubscriptionPayment,
    PaymentStatus, PaymentMethod, SubscriptionStatus, SubscriptionPlan, ContentType
)
from .settings import AppSettings, SettingCategory
from .cache import GeneratedContentCache, DailyLearningPlan
from .assessment_job import AssessmentJob

# Import all models to ensure they are registered with SQLAlchemy
__all__ = [
    "User", "OAuth2Account", "OAuthProvider",
    "Content", "Vocabulary", "Grammar", "ContentType", "DifficultyLevel", "VocabularyStatus",
    "UserVocabulary", "VocabularySet", "VocabularySetItem", "VocabularyExercise",
    "Exercise", "ExerciseAttempt", "Quiz", "QuizExercise", "QuizAttempt", "ExerciseType",
    "UserProgress", "DailyProgress", "Achievement", "UserAchievement", "StudySession", "LearningGoal",
    "ReadingText", "ReadingExercise", "ReadingAttempt", "VocabularyHighlight", "ReadingProgress",
    "WritingPrompt", "WritingSubmission", "WritingFeedback", "WritingTemplate", "WritingProgress", "GrammarRule",
    "AudioContent", "ListeningExercise", "ListeningAttempt", "ListeningExerciseAttempt", "ListeningProgress", "AudioPlaylist", "AudioPlaylistItem",
    "SpeakingPrompt", "SpeakingAttempt", "PronunciationExercise", "PronunciationAttempt", "SpeakingProgress", "SpeakingSession", "VoiceProfile",
    "UserLearningProfile", "PersonalizedLearningPath", "LearningPathMilestone", "ContentRecommendation", "PersonalTrainerInteraction", "LearningAnalytics", "AdaptiveLearningRule",
    "UserOnboarding", "CategoryLearningTemplate", "UserCategoryPreference",
    "AIGeneratedLesson", "LessonProgress", "LessonGenerationAnalytics", "LessonTemplate",
    "Payment", "Subscription", "ContentAccess", "ContentLockConfig",
    "PaymentWebhook", "Refund", "SubscriptionPayment",
    "PaymentStatus", "PaymentMethod", "SubscriptionStatus", "SubscriptionPlan", "ContentType",
    "AppSettings", "SettingCategory",
    "AssessmentJob",
    "GeneratedContentCache", "DailyLearningPlan"
] 