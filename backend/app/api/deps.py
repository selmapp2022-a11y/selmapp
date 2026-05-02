from typing import Generator
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import verify_token
from app.core.logging import debug_log
from app.models.user import User
from app.crud.user import user_crud

security = HTTPBearer()

# Synchronous database session for endpoints that need it
def get_sync_db() -> Generator[Session, None, None]:
    """Get synchronous database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user"""
    debug_log("🔐 BACKEND AUTH: Received auth request")
    token = credentials.credentials
    debug_log(f"🔑 BACKEND AUTH: Token received: {token[:20]}...")

    user_id = verify_token(token)
    debug_log(f"👤 BACKEND AUTH: Token verification result - user_id: {user_id}")

    if not user_id:
        debug_log("❌ BACKEND AUTH: Token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    debug_log(f"🔍 BACKEND AUTH: Looking up user with ID: {user_id}")
    user = await user_crud.get(db, id=int(user_id))
    if not user:
        debug_log(f"❌ BACKEND AUTH: User not found for ID: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        debug_log(f"🚫 BACKEND AUTH: User is inactive: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    debug_log(f"✅ BACKEND AUTH: User authenticated successfully: {user.email}")
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_premium_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current premium user"""
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required"
        )
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current admin user"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def get_developer_admin_user(
    current_user: User = Depends(get_current_admin_user)
) -> User:
    """Get current user with developer admin role"""
    if current_user.admin_role != "developer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Developer admin privileges required"
        )
    return current_user

async def get_owner_admin_user(
    current_user: User = Depends(get_current_admin_user)
) -> User:
    """Get current user with owner admin role (or developer — developer has full access)"""
    if current_user.admin_role not in ("owner", "developer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner or developer admin privileges required"
        )
    return current_user

async def get_current_user_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user for WebSocket connections"""
    # Extract token from query parameters
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authentication token provided"
        )

    user_id = verify_token(token)

    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )

    user = await user_crud.get(db, id=int(user_id))
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return user 