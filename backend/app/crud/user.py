from typing import Any, Dict, Optional, Union
import hashlib
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from sqlalchemy.sql import func
from datetime import datetime, timedelta

from app.crud.base import CRUDBase
from app.models.user import User, OAuth2Account, OAuthProvider
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.auth import UserCreate as AuthUserCreate, OAuth2UserCreate
from app.core.security import get_password_hash, verify_password

class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """Get user by email"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[User]:
        """Get user by username"""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, *, obj_in: Union[UserCreate, AuthUserCreate]) -> User:
        """Create user with hashed password"""
        create_data = obj_in.model_dump()
        create_data.pop("password")
        db_obj = User(
            **create_data,
            hashed_password=get_password_hash(obj_in.password)
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def create_oauth2_user(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: OAuth2UserCreate, 
        token_data: Dict[str, Any]
    ) -> User:
        """Create user from OAuth2 data"""
        # Create user without password
        user_data = obj_in.model_dump()
        # Remove OAuth2 specific fields
        oauth_fields = ["provider", "provider_user_id", "provider_email", "provider_name", "provider_avatar_url"]
        for field in oauth_fields:
            user_data.pop(field, None)
        
        db_obj = User(
            **user_data,
            hashed_password=None,
            has_password=False,
            is_verified=True  # OAuth2 users are considered verified
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        
        # Create OAuth2 account
        oauth_account_data = {
            "user_id": db_obj.id,
            "provider": obj_in.provider,
            "provider_user_id": obj_in.provider_user_id,
            "provider_email": obj_in.provider_email,
            "provider_name": obj_in.provider_name,
            "provider_avatar_url": obj_in.provider_avatar_url,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
        }
        
        # Handle token expiration
        if "expires_at" in token_data:
            oauth_account_data["token_expires_at"] = datetime.fromtimestamp(token_data["expires_at"])
        elif "expires_in" in token_data:
            oauth_account_data["token_expires_at"] = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        oauth_account = OAuth2Account(**oauth_account_data)
        db.add(oauth_account)
        await db.commit()
        
        return db_obj

    async def update(
        self, db: AsyncSession, *, db_obj: User, obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """Update user"""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        if "password" in update_data:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
            update_data["has_password"] = True
        
        return await super().update(db, db_obj=db_obj, obj_in=update_data)

    async def authenticate(self, db: AsyncSession, *, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await self.get_by_email(db, email=email)
        if not user:
            return None
        if not user.has_password or not user.hashed_password:
            return None  # OAuth2 only user
        if not verify_password(password, user.hashed_password):
            return None
        return user

    async def can_authenticate_with_password(self, db: AsyncSession, *, email: str) -> bool:
        """Check if user can authenticate with password"""
        user = await self.get_by_email(db, email=email)
        return user is not None and user.has_password and user.hashed_password is not None

    async def is_active(self, user: User) -> bool:
        """Check if user is active"""
        return user.is_active

    async def is_premium(self, user: User) -> bool:
        """Check if user has premium subscription"""
        return user.is_premium

    async def update_last_login(self, db: AsyncSession, *, user_id: int) -> None:
        """Update user's last login timestamp"""
        await db.execute(
            update(User).where(User.id == user_id).values(last_login=func.now())
        )
        await db.commit()

    async def soft_delete(self, db: AsyncSession, *, user: User) -> bool:
        """
        Soft delete a user account - anonymizes email and username to allow re-registration.
        
        This implements best practices for GDPR/data protection:
        1. Stores SHA256 hash of original email for audit purposes
        2. Replaces email with unique deleted identifier
        3. Replaces username with unique deleted identifier
        4. Sets deleted_at timestamp
        5. Deactivates the account
        6. Preserves related data for analytics (but anonymized)
        
        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            # Generate hash of original email for audit trail
            original_email_hash = hashlib.sha256(user.email.encode()).hexdigest()
            
            # Generate unique identifiers for anonymization
            unique_id = uuid.uuid4().hex[:12]
            deleted_email = f"deleted_{unique_id}@deleted.selmapp.local"
            deleted_username = f"deleted_user_{unique_id}"
            
            # Update user with anonymized data
            await db.execute(
                update(User)
                .where(User.id == user.id)
                .values(
                    email=deleted_email,
                    username=deleted_username,
                    full_name="Deleted User",
                    avatar_url=None,
                    is_active=False,
                    deleted_at=func.now(),
                    original_email_hash=original_email_hash,
                    # Clear sensitive data
                    hashed_password=None,
                    has_password=False,
                )
            )
            await db.commit()
            return True
        except Exception as e:
            await db.rollback()
            raise e

    async def get_by_email_including_deleted(
        self, db: AsyncSession, *, email: str
    ) -> Optional[User]:
        """Get user by email, including soft-deleted users (for admin purposes)"""
        # First check if there's an active user with this email
        result = await db.execute(
            select(User).where(
                and_(
                    User.email == email,
                    User.deleted_at.is_(None)
                )
            )
        )
        user = result.scalar_one_or_none()
        if user:
            return user
        
        # Check if there was a deleted user with this email hash
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        result = await db.execute(
            select(User).where(User.original_email_hash == email_hash)
        )
        return result.scalar_one_or_none()

    async def can_register_email(self, db: AsyncSession, *, email: str) -> bool:
        """
        Check if an email can be used for registration.
        Returns True if:
        - No active user exists with this email
        - Previous user with this email was soft-deleted (can re-register)
        """
        result = await db.execute(
            select(User).where(
                and_(
                    User.email == email,
                    User.deleted_at.is_(None)  # Only check non-deleted users
                )
            )
        )
        existing_user = result.scalar_one_or_none()
        return existing_user is None

user_crud = CRUDUser(User) 