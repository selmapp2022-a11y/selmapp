from pydantic_settings import BaseSettings
from typing import List, Optional
import secrets

class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "SelmApp"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False  # Set to False in production
    
    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/selmapp"
    REDIS_URL: str = "redis://localhost:6379"
    # Connection pool sizing (important for managed Postgres plans with low max_connections).
    # NOTE: Each Gunicorn worker is a separate process with its own pool.
    DB_POOL_SIZE: int = 2
    DB_MAX_OVERFLOW: int = 0
    DB_SYNC_POOL_SIZE: int = 1
    DB_SYNC_MAX_OVERFLOW: int = 0
    
    # OAuth2 Settings
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    FACEBOOK_CLIENT_ID: Optional[str] = None
    FACEBOOK_CLIENT_SECRET: Optional[str] = None
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/callback"
    
    # PayPal Settings
    PAYPAL_CLIENT_ID: Optional[str] = None
    PAYPAL_CLIENT_SECRET: Optional[str] = None
    PAYPAL_MODE: str = "sandbox"  # "sandbox" or "live"
    PAYPAL_WEBHOOK_ID: Optional[str] = None
    
    # Payment Settings
    PAYMENT_CURRENCY: str = "USD"
    PAYMENT_SUCCESS_URL: str = "http://localhost:3000/payment/success"
    PAYMENT_CANCEL_URL: str = "http://localhost:3000/payment/cancel"
    
    # Content Locking Settings
    CONTENT_LOCK_ENABLED: bool = False  # Admin can toggle this
    FREE_CEFR_LEVELS: List[str] = ["A1"]  # Free CEFR levels
    FREE_MODULES: List[str] = ["reading"]  # Free modules for non-premium users
    
    # AI Services
    GOOGLE_GEMINI_API_KEY: Optional[str] = None
    GOOGLE_CLOUD_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GEMINI_TEXT_MODEL_FAST: str = "gemini-2.5-flash-lite"
    GEMINI_TEXT_MODEL_REASON: str = "gemini-2.5-pro"
    # Use Gemini TTS preview model for speech synthesis
    # Note: gemini-2.5-flash-preview-tts supports generateContent with AUDIO modality
    # gemini-2.5-flash-native-audio-preview-09-2025 does NOT support generateContent
    GEMINI_SPEECH_MODEL: str = "gemini-2.5-flash-preview-tts"
    # Preferred TTS voice
    GEMINI_TTS_VOICE: Optional[str] = "Kore"
    # TTS provider selection: "elevenlabs" or "gemini" (default keeps current behavior)
    TTS_PROVIDER: str = "gemini"
    # ElevenLabs TTS configuration
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_MODEL_ID: str = "eleven_turbo_v2_5"
    # Voice IDs (override per-deployment to change defaults)
    ELEVENLABS_VOICE_ID_AMERICAN: str = "EXAVITQu4vr4xnSDxMaL"  # Sarah
    ELEVENLABS_VOICE_ID_BRITISH: str = "XB0fDUnXU5powFXDhCwa"   # Charlotte
    ELEVENLABS_DEFAULT_ACCENT: str = "american"  # "american" | "british"
    SPEAKING_PIPELINE: str = "stt_v2+gemini"
    GCP_PROJECT_ID: Optional[str] = None
    GCP_LOCATION: str = "global"
    ELSA_API_KEY: Optional[str] = None
    ELSA_API_BASE_URL: Optional[str] = None
    SPEECHACE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    # Audio file storage (for TTS output)
    AUDIO_STORAGE_DIR: str = "storage/audio"
    AUDIO_BASE_URL: str = "/media/audio"
    AUDIO_STORAGE_MODE: str = "filesystem"  # filesystem|redis|spaces
    # Public base URL used to build absolute media links for mobile clients
    PUBLIC_BASE_URL: str = "http://localhost:8080"
    
    # DigitalOcean Spaces Configuration (S3-compatible object storage)
    SPACES_KEY: Optional[str] = None
    SPACES_SECRET: Optional[str] = None
    SPACES_REGION: str = "nyc3"
    SPACES_BUCKET: Optional[str] = None  # e.g., "selmapp" (just the bucket name, no URL)
    # IMPORTANT: SPACES_ENDPOINT should NOT include the bucket name!
    # Correct: https://nyc3.digitaloceanspaces.com
    # Wrong: https://selmapp.nyc3.digitaloceanspaces.com (bucket name should not be here)
    SPACES_ENDPOINT: Optional[str] = None  # e.g., https://nyc3.digitaloceanspaces.com
    # Optional CDN endpoint for faster delivery (if configured in DO Spaces)
    # CDN endpoint DOES include the bucket name
    SPACES_CDN_ENDPOINT: Optional[str] = None  # e.g., https://selmapp.nyc3.cdn.digitaloceanspaces.com
    
    # Audio/TTS Settings
    TTS_SERVICE: str = "google"  # google, azure, aws
    AUDIO_FORMAT: str = "mp3"

    # Content cache
    CONTENT_CACHE_ENABLED: bool = True
    
    # Email (for notifications)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Admin Seeding Credentials
    ADMIN_DEV_EMAIL: str = "dev@selmapp.com"
    ADMIN_DEV_PASSWORD: str = "ChangeMe!Dev2025"
    ADMIN_DEV_USERNAME: str = "admin_dev"
    ADMIN_OWNER_EMAIL: str = "admin@selmapp.com"
    ADMIN_OWNER_PASSWORD: str = "ChangeMe!Owner2025"
    ADMIN_OWNER_USERNAME: str = "admin_owner"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 