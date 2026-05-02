from typing import Optional, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.crud.base import CRUDBase
from app.models.user import OAuth2Account, OAuthProvider
from app.schemas.auth import OAuth2AccountResponse


def _normalize_provider(provider: Union[str, OAuthProvider]) -> OAuthProvider:
    """Convert provider string to OAuthProvider enum, handling case-insensitivity."""
    if isinstance(provider, OAuthProvider):
        return provider
    # Normalize to lowercase and look up enum by value
    provider_lower = provider.lower()
    for p in OAuthProvider:
        if p.value == provider_lower:
            return p
    raise ValueError(f"Unknown OAuth provider: {provider}")


class CRUDOAuth2Account(CRUDBase[OAuth2Account, dict, dict]):
    async def get_by_provider_and_user_id(
        self, 
        db: AsyncSession, 
        *, 
        provider: Union[str, OAuthProvider], 
        provider_user_id: str
    ) -> Optional[OAuth2Account]:
        """Get OAuth2 account by provider and provider user ID"""
        provider_enum = _normalize_provider(provider)
        result = await db.execute(
            select(OAuth2Account).where(
                OAuth2Account.provider == provider_enum,
                OAuth2Account.provider_user_id == provider_user_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_user_and_provider(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int, 
        provider: Union[str, OAuthProvider]
    ) -> Optional[OAuth2Account]:
        """Get OAuth2 account by user ID and provider"""
        provider_enum = _normalize_provider(provider)
        result = await db.execute(
            select(OAuth2Account).where(
                OAuth2Account.user_id == user_id,
                OAuth2Account.provider == provider_enum
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_oauth_accounts(
        self, 
        db: AsyncSession, 
        *, 
        user_id: int
    ) -> list[OAuth2Account]:
        """Get all OAuth2 accounts for a user"""
        result = await db.execute(
            select(OAuth2Account).where(OAuth2Account.user_id == user_id)
        )
        return result.scalars().all()
    
    async def create(
        self, 
        db: AsyncSession, 
        *, 
        obj_in: Dict[str, Any]
    ) -> OAuth2Account:
        """Create OAuth2 account"""
        # Normalize provider to enum if provided as string
        if "provider" in obj_in and not isinstance(obj_in["provider"], OAuthProvider):
            obj_in = dict(obj_in)  # Don't mutate the original dict
            obj_in["provider"] = _normalize_provider(obj_in["provider"])
        db_obj = OAuth2Account(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update_tokens(
        self, 
        db: AsyncSession, 
        *, 
        oauth_account: OAuth2Account, 
        token_data: Dict[str, Any]
    ) -> OAuth2Account:
        """Update OAuth2 account tokens"""
        oauth_account.access_token = token_data.get("access_token")
        oauth_account.refresh_token = token_data.get("refresh_token")
        
        # Handle token expiration
        if "expires_at" in token_data:
            oauth_account.token_expires_at = datetime.fromtimestamp(token_data["expires_at"])
        elif "expires_in" in token_data:
            oauth_account.token_expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
        
        oauth_account.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(oauth_account)
        return oauth_account
    
    async def delete(self, db: AsyncSession, *, id: int) -> bool:
        """Delete OAuth2 account"""
        result = await db.execute(
            select(OAuth2Account).where(OAuth2Account.id == id)
        )
        oauth_account = result.scalar_one_or_none()
        
        if oauth_account:
            await db.delete(oauth_account)
            await db.commit()
            return True
        return False

oauth2_account_crud = CRUDOAuth2Account(OAuth2Account) 