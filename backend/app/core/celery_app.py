from celery import Celery
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "selmapp",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.ai_tasks",
        "app.tasks.content_tasks",
        "app.tasks.analytics_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.weekly_plan_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "app.tasks.ai_tasks.*": {"queue": "ai_processing"},
        "app.tasks.content_tasks.*": {"queue": "content_generation"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics"},
        "app.tasks.notification_tasks.*": {"queue": "notifications"},
        "app.tasks.weekly_plan_tasks.*": {"queue": "weekly_plan_generation"}
    },
    
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result settings
    result_expires=3600,  # 1 hour
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        "generate-daily-content": {
            "task": "app.tasks.content_tasks.generate_daily_personalized_content",
            "schedule": 60.0 * 60.0 * 6,  # Every 6 hours
        },
        "update-user-analytics": {
            "task": "app.tasks.analytics_tasks.update_user_learning_analytics",
            "schedule": 60.0 * 60.0 * 2,  # Every 2 hours
        },
        "cleanup-expired-sessions": {
            "task": "app.tasks.analytics_tasks.cleanup_expired_sessions",
            "schedule": 60.0 * 60.0 * 24,  # Daily
        },
        "send-daily-reminders": {
            "task": "app.tasks.notification_tasks.send_daily_study_reminders",
            "schedule": 60.0 * 60.0 * 24,  # Daily
        }
    }
)
