from .base import CRUDBase
from .user import user_crud
from .content import content_crud, vocabulary_crud, grammar_crud
from .progress import (
    user_progress_crud, daily_progress_crud, achievement_crud,
    user_achievement_crud, study_session_crud, learning_goal_crud
)
from .exercise import exercise_crud, exercise_attempt_crud, quiz_crud, quiz_attempt_crud
from .reading import (
    reading_text, reading_exercise, reading_attempt,
    vocabulary_highlight, reading_progress
)
from .writing import (
    writing_prompt, writing_submission, writing_feedback,
    writing_template, writing_progress, grammar_rule
)
from .listening import (
    crud_audio_content, crud_listening_exercise, crud_listening_attempt,
    crud_listening_exercise_attempt, crud_listening_progress
)
from .speaking import (
    speaking_prompt, speaking_attempt, pronunciation_exercise,
    pronunciation_attempt, speaking_progress, speaking_session,
    voice_profile
)
from .personalization import (
    learning_profile, learning_path, learning_milestone,
    content_recommendation, trainer_interaction, learning_analytics,
    adaptive_rule, user_onboarding, category_learning_template,
    user_category_preference
)
from .payment import (
    payment_crud, subscription_crud, content_access_crud,
    content_lock_config_crud, payment_webhook_crud, refund_crud
) 