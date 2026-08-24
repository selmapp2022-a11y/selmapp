from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional
from urllib.parse import unquote
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
    # Sign in with Apple — bundle ID (mobile) and/or service ID (web).
    # Declared here so pydantic-settings picks them up from env vars.
    # Without the declaration, `getattr(settings, "APPLE_BUNDLE_ID", None)`
    # in auth.oauth_apple_native returns None, which trips the
    # "Apple sign-in not configured" 503 even when the env var is set.
    # That was the root cause of Apple's Guideline 2.1(a) rejection on
    # Build 35 — SIWA hit 503 instead of validating the token.
    APPLE_BUNDLE_ID: Optional[str] = None
    APPLE_SERVICE_ID: Optional[str] = None
    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/callback"
    
    # RevenueCat — shared secret for the purchase webhook.
    # DECLARED ON PURPOSE. pydantic-settings only reads env vars that are
    # declared as fields here; an env var set on the host but missing from
    # this class is silently invisible to the app. That is what happened to
    # APPLE_BUNDLE_ID (Apple Guideline 2.1(a) rejection on Build 35) and it
    # happened again here: REVENUECAT_WEBHOOK_AUTH was set as a SECRET on
    # DigitalOcean, resolved to None, and the webhook's auth check was
    # skipped entirely — any caller could post a subscription event.
    REVENUECAT_WEBHOOK_AUTH: Optional[str] = None

    # Native Google sign-in audiences. Referenced by
    # auth.oauth_google_native; undeclared until now, so setting them on the
    # host had no effect and native iOS/Android Google tokens could never
    # match the expected audience set.
    GOOGLE_IOS_CLIENT_ID: Optional[str] = None
    GOOGLE_ANDROID_CLIENT_ID: Optional[str] = None

    # Referenced via getattr() elsewhere; declared so the host can set them.
    FRONTEND_URL: Optional[str] = None
    STORAGE_PATH: str = "storage"

    # PayPal Settings
    PAYPAL_CLIENT_ID: Optional[str] = None
    PAYPAL_CLIENT_SECRET: Optional[str] = None
    PAYPAL_MODE: str = "sandbox"  # "sandbox" or "live"
    # PayPal is switched off. Purchases run through RevenueCat; selm-web has
    # no route into the PayPal flow, production ran with PAYPAL_MODE=sandbox
    # and payment_enabled=false, so no PayPal order could be created. The
    # order, capture and subscription endpoints now refuse with 410 instead
    # of appearing to work. Set this true, with live credentials and
    # PAYPAL_WEBHOOK_ID, to bring the path back.
    PAYPAL_ENABLED: bool = False
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
    # Three Gemini tiers explicitly distinguished by use case:
    #   FAST    — flash-lite. Used for fast, low-stakes interactive
    #             feedback (e.g. confirming a grammar answer). Cheap.
    #   CONTENT — pro. Used for everything the LEARNER reads or hears:
    #             reading passages, listening dialogues, exercises,
    #             vocab explanations, conversation practice. The
    #             quality jump from flash-lite → pro is large for
    #             multi-paragraph generation. Ebrahim explicitly
    #             approved the cost trade-off 2026-05-13.
    #   REASON  — pro. Heavier reasoning: assessment scoring, level
    #             determination, learner-profile analysis.
    GEMINI_TEXT_MODEL_FAST: str = "gemini-2.5-flash-lite"
    # New middle tier (2026-05-13 late): full flash for speed-sensitive
    # paths that still need decent prose — listening dialogue scripts
    # in particular, where pro takes 15-30 s for a 12-turn dialogue and
    # makes the iPhone wait too long. Falls between flash-lite and pro.
    GEMINI_TEXT_MODEL_DIALOGUE: str = "gemini-2.5-flash"
    GEMINI_TEXT_MODEL_CONTENT: str = "gemini-2.5-pro"
    GEMINI_TEXT_MODEL_REASON: str = "gemini-2.5-pro"
    # Use Gemini TTS preview model for speech synthesis
    # Note: gemini-2.5-flash-preview-tts supports generateContent with AUDIO modality
    # gemini-2.5-flash-native-audio-preview-09-2025 does NOT support generateContent
    GEMINI_SPEECH_MODEL: str = "gemini-2.5-flash-preview-tts"
    # Preferred TTS voice
    GEMINI_TTS_VOICE: Optional[str] = "Kore"
    SPEAKING_PIPELINE: str = "stt_v2+gemini"
    GCP_PROJECT_ID: Optional[str] = None
    GCP_LOCATION: str = "global"
    ELSA_API_KEY: Optional[str] = None
    ELSA_API_BASE_URL: Optional[str] = None
    SPEECHACE_API_KEY: Optional[str] = None
    # OPENAI_API_KEY removed 2026-05-08 — was declared but never imported.
    # If you want to wire OpenAI as a Gemini fallback later, re-add here and
    # in env.example, then add `import openai` to a service module.

    # OpenAI TTS — primary provider as of 2026-05-13. ``gpt-4o-mini-tts``
    # gives more natural English prosody than ElevenLabs turbo and
    # supports a free-form ``instructions`` field for voice direction.
    # Cost is also lower ($0.015/1K chars vs ElevenLabs $0.05/1K).
    # Set OPENAI_API_KEY in env to activate; without it the factory
    # falls back to ElevenLabs (or Gemini if that's also missing).
    OPENAI_API_KEY: Optional[str] = None

    # ElevenLabs TTS — secondary provider, used as fallback or when
    # ``TTS_PROVIDER=elevenlabs``. See OPENAI_API_KEY above.
    ELEVENLABS_API_KEY: Optional[str] = None
    # Optional: pin a specific ElevenLabs voice across the app. If unset, the
    # ElevenLabs service uses Rachel ("21m00Tcm4TlvDq8ikWAM") by default for
    # solo narration and assigns gender-matched voices for multi-speaker
    # listening dialogues automatically.
    ELEVENLABS_VOICE_ID: Optional[str] = None
    # TTS provider toggle. Options:
    #   "openai"     — gpt-4o-mini-tts. Default as of 2026-05-13;
    #                  best naturalness for English with voice
    #                  direction via the ``instructions`` parameter.
    #   "elevenlabs" — eleven_turbo_v2_5. Backup provider.
    #   "gemini"     — Gemini native TTS. Last-resort fallback.
    # The factory in gemini_tts_service.get_tts_service() picks the
    # provider AND falls back automatically when the chosen provider's
    # API key is missing — so a fresh dev env always produces audio.
    TTS_PROVIDER: str = "openai"

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
    
    # ── Admin Seeding Credentials ──
    #
    # ADMIN_DEV_PASSWORD and ADMIN_OWNER_PASSWORD have NO default and are
    # required. Until 2026-08-24 they defaulted to the literals
    # "ChangeMe!Dev2025" and "ChangeMe!Owner2025", neither was set on the
    # production host, and the seeder created the accounts with exactly
    # those passwords — dev@selmapp.com was still logging in with the
    # default on production. A missing value must stop the process, not
    # silently install a password that is published in this repository.
    ADMIN_DEV_EMAIL: str = "dev@selmapp.com"
    ADMIN_DEV_PASSWORD: str
    ADMIN_DEV_USERNAME: str = "admin_dev"
    ADMIN_OWNER_EMAIL: str = "admin@selmapp.com"
    ADMIN_OWNER_PASSWORD: str
    ADMIN_OWNER_USERNAME: str = "admin_owner"
    
    # ── URL-decode keys that may have been pasted in encoded form ──
    #
    # Operators sometimes paste API keys into the DigitalOcean App
    # Platform UI from an email or URL that already URL-encoded them
    # (so `/` becomes `%2F`, `+` becomes `%2B`, etc.). When we then
    # send that string back to the upstream API as a query parameter,
    # aiohttp percent-encodes it a SECOND time (`%2F` → `%252F`), the
    # upstream rejects the auth, and the app silently falls back to a
    # weaker provider. This validator detects accidental encoding and
    # restores the raw key so consumers don't have to know.
    @field_validator("SPEECHACE_API_KEY", "ELEVENLABS_API_KEY", "GOOGLE_GEMINI_API_KEY", mode="before")
    @classmethod
    def _decode_percent_encoded_keys(cls, v):
        if isinstance(v, str) and "%" in v:
            decoded = unquote(v)
            # Only adopt the decode if it actually changed something —
            # avoids false positives on keys that legitimately use `%`.
            if decoded != v:
                return decoded
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()