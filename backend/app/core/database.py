from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import make_url
import redis.asyncio as redis
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# NOTE (DigitalOcean / managed Postgres):
# - DigitalOcean provides DATABASE_URL values like:
#     postgresql://.../db?sslmode=require
# - SQLAlchemy's asyncpg dialect passes URL query params as kwargs to asyncpg.connect()
# - asyncpg does NOT accept `sslmode=...` as a kwarg, so app startup crashes with:
#     TypeError: connect() got an unexpected keyword argument 'sslmode'
#
# Best-practice fix:
# - Parse the URL (don't string-replace)
# - Remove `sslmode` from the URL query for asyncpg
# - Pass the equivalent SSL mode via connect_args={"ssl": "<mode>"}

def _build_asyncpg_url_and_connect_args(database_url: str):
    """
    Build a SQLAlchemy URL for asyncpg and a matching connect_args dict.

    This safely strips query params that asyncpg can't accept as kwargs (notably
    `sslmode`) and maps them to asyncpg's supported `ssl` option.
    """
    url = make_url(database_url)

    # Normalize common postgres schemes and force the asyncpg driver
    if url.drivername == "postgres":
        url = url.set(drivername="postgresql")
    if url.drivername.startswith("postgresql"):
        url = url.set(drivername="postgresql+asyncpg")

    query = dict(url.query)
    sslmode = query.pop("sslmode", None)
    url = url.set(query=query)

    connect_args = {}
    if sslmode:
        # asyncpg supports ssl modes like: disable|allow|prefer|require|verify-ca|verify-full
        connect_args["ssl"] = str(sslmode).lower()

    return url, connect_args

def _build_sync_url(database_url: str):
    """Build a SQLAlchemy URL for psycopg (sync) without brittle string replace."""
    url = make_url(database_url)
    if url.drivername == "postgres":
        url = url.set(drivername="postgresql")
    if url.drivername.startswith("postgresql"):
        url = url.set(drivername="postgresql+psycopg")
    return url

# Async SQLAlchemy setup with connection pooling for concurrent users
# pool_size: number of connections to keep open
# max_overflow: max additional connections when pool is exhausted
# pool_timeout: seconds to wait for a connection before giving up
# pool_recycle: recycle connections after this many seconds (prevents stale connections)
async_db_url, async_connect_args = _build_asyncpg_url_and_connect_args(settings.DATABASE_URL)
engine = create_async_engine(
    async_db_url,
    echo=True if settings.ENVIRONMENT == "development" else False,
    future=True,
    # NOTE: each Gunicorn worker process has its own pool. Keep these values
    # small by default to avoid exhausting Postgres connection limits.
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=30,  # Wait up to 30 seconds for a connection
    pool_recycle=1800,  # Recycle connections every 30 minutes
    pool_pre_ping=True,  # Verify connections before use
    connect_args=async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Synchronous SQLAlchemy setup for payment endpoints with connection pooling
sync_engine = create_engine(
    _build_sync_url(settings.DATABASE_URL),
    echo=True if settings.ENVIRONMENT == "development" else False,
    future=True,
    pool_size=settings.DB_SYNC_POOL_SIZE,
    max_overflow=settings.DB_SYNC_MAX_OVERFLOW,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)

# Redis setup
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )

async def get_db() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_async_session() -> AsyncSession:
    """Get async database session for direct use"""
    return AsyncSessionLocal()

def get_sync_db():
    """Dependency to get synchronous database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_redis():
    """Dependency to get Redis client"""
    return redis_client

async def init_db():
    """
    Initialize database connectivity at app startup.

    IMPORTANT:
    - Database schema is managed by Alembic migrations.
    - Do NOT call `Base.metadata.create_all()` here, otherwise you'll create tables
      outside Alembic and `alembic upgrade head` will later fail with
      "relation ... already exists".
    """
    async with engine.connect() as conn:
        # Lightweight connectivity check.
        await conn.execute(text("SELECT 1"))

async def close_db():
    """Close database connections"""
    await engine.dispose()
    await redis_client.close()


async def seed_admin_users():
    """
    Seed admin users on app startup.
    Creates or updates two admin accounts (developer and owner) using env vars.
    Safe to run repeatedly — will not overwrite existing admin passwords unless
    the admin user doesn't exist yet.
    """
    from app.core.security import get_password_hash
    from sqlalchemy import select

    admin_accounts = [
        {
            "email": settings.ADMIN_DEV_EMAIL,
            "username": settings.ADMIN_DEV_USERNAME,
            "password": settings.ADMIN_DEV_PASSWORD,
            "admin_role": "developer",
            "full_name": "Developer Admin",
        },
        {
            "email": settings.ADMIN_OWNER_EMAIL,
            "username": settings.ADMIN_OWNER_USERNAME,
            "password": settings.ADMIN_OWNER_PASSWORD,
            "admin_role": "owner",
            "full_name": "Owner Admin",
        },
    ]

    async with AsyncSessionLocal() as session:
        # Defensive startup guard:
        # If migrations were not applied (or DB was incorrectly stamped),
        # ORM queries against User can fail with UndefinedColumnError.
        # Check required columns first and skip seeding with an actionable log.
        result = await session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'users'
                  AND column_name IN ('is_admin', 'admin_role');
                """
            )
        )
        existing_columns = {row[0] for row in result.fetchall()}
        required_columns = {"is_admin", "admin_role"}
        missing_columns = sorted(required_columns - existing_columns)

        if missing_columns:
            logger.error(
                "Skipping admin seeding: users table is missing required columns %s. "
                "Run DB migrations before starting app traffic (recommended: python scripts/migrate.py).",
                missing_columns,
            )
            return

        # Import User model inside function to avoid circular imports
        from app.models.user import User

        for acct in admin_accounts:
            result = await session.execute(
                select(User).where(User.email == acct["email"])
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                # Create new admin user
                user = User(
                    email=acct["email"],
                    username=acct["username"],
                    hashed_password=get_password_hash(acct["password"]),
                    full_name=acct["full_name"],
                    is_active=True,
                    is_verified=True,
                    is_admin=True,
                    admin_role=acct["admin_role"],
                    has_password=True,
                    onboarding_completed=True,
                )
                session.add(user)
                logger.info("Created admin user: %s (%s)", acct["email"], acct["admin_role"])
            else:
                # Ensure existing user has admin flags set correctly
                existing.is_admin = True
                existing.admin_role = acct["admin_role"]
                existing.is_active = True
                logger.info("Updated admin flags for: %s (%s)", acct["email"], acct["admin_role"])

        await session.commit()