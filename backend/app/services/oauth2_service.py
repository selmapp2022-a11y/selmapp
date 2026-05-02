from typing import Optional, Dict, Any
import secrets
import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User, OAuth2Account, OAuthProvider
from app.schemas.auth import OAuth2UserCreate
from app.crud.user import user_crud
from app.crud.oauth2 import oauth2_account_crud

class OAuth2Service:
    """Service for handling OAuth2 authentication with various providers"""
    
    def __init__(self):
        self.providers = {
            "google": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "user_info_url": "https://www.googleapis.com/oauth2/v2/userinfo",
                "scope": "openid email profile"
            },
            "github": {
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "auth_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "user_info_url": "https://api.github.com/user",
                "scope": "user:email"
            },
            "facebook": {
                "client_id": settings.FACEBOOK_CLIENT_ID,
                "client_secret": settings.FACEBOOK_CLIENT_SECRET,
                "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
                "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
                "user_info_url": "https://graph.facebook.com/v18.0/me",
                "scope": "email public_profile"
            }
        }
    
    def get_authorization_url(self, provider: str) -> Dict[str, str]:
        """Generate OAuth2 authorization URL for a provider"""
        if provider not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported OAuth2 provider: {provider}"
            )
        
        provider_config = self.providers[provider]
        
        if not provider_config["client_id"] or not provider_config["client_secret"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OAuth2 provider {provider} is not configured"
            )
        
        # Generate state for security
        state = secrets.token_urlsafe(32)
        
        # Create OAuth2 client
        client = AsyncOAuth2Client(
            client_id=provider_config["client_id"],
            client_secret=provider_config["client_secret"],
            redirect_uri=settings.OAUTH_REDIRECT_URI
        )
        
        # Generate authorization URL
        auth_url, _ = client.create_authorization_url(
            provider_config["auth_url"],
            scope=provider_config["scope"],
            state=state
        )
        
        return {
            "auth_url": auth_url,
            "state": state
        }
    
    async def authenticate_with_code(
        self, 
        provider: str, 
        code: str, 
        state: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Authenticate user with OAuth2 authorization code"""
        if provider not in self.providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported OAuth2 provider: {provider}"
            )
        
        provider_config = self.providers[provider]
        
        # Exchange code for access token
        token_data = await self._exchange_code_for_token(provider, code)
        
        # Get user info from provider
        user_info = await self._get_user_info(provider, token_data["access_token"])
        
        # Find or create user
        user = await self._find_or_create_user(db, provider, user_info, token_data)
        
        return {
            "user": user,
            "provider": provider,
            "user_info": user_info
        }
    
    async def _exchange_code_for_token(self, provider: str, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        provider_config = self.providers[provider]
        
        client = AsyncOAuth2Client(
            client_id=provider_config["client_id"],
            client_secret=provider_config["client_secret"],
            redirect_uri=settings.OAUTH_REDIRECT_URI
        )
        
        try:
            token = await client.fetch_token(
                provider_config["token_url"],
                code=code
            )
            return token
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange code for token: {str(e)}"
            )
    
    async def _get_user_info(self, provider: str, access_token: str) -> Dict[str, Any]:
        """Get user information from OAuth2 provider"""
        provider_config = self.providers[provider]
        
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Special handling for different providers
            if provider == "facebook":
                # Facebook requires fields parameter
                params = {"fields": "id,name,email,picture"}
                response = await client.get(
                    provider_config["user_info_url"],
                    headers=headers,
                    params=params
                )
            elif provider == "github":
                # GitHub requires user-agent header
                headers["User-Agent"] = "SelmApp/1.0"
                response = await client.get(
                    provider_config["user_info_url"],
                    headers=headers
                )
            else:
                response = await client.get(
                    provider_config["user_info_url"],
                    headers=headers
                )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get user info from {provider}"
                )
            
            return response.json()
    
    async def _find_or_create_user(
        self, 
        db: AsyncSession, 
        provider: str, 
        user_info: Dict[str, Any], 
        token_data: Dict[str, Any]
    ) -> User:
        """Find existing user or create new one from OAuth2 data"""
        # Extract user data based on provider
        if provider == "google":
            provider_user_id = user_info["id"]
            email = user_info["email"]
            name = user_info.get("name", "")
            avatar_url = user_info.get("picture", "")
        elif provider == "github":
            provider_user_id = str(user_info["id"])
            email = user_info.get("email", "")
            name = user_info.get("name", user_info.get("login", ""))
            avatar_url = user_info.get("avatar_url", "")
        elif provider == "facebook":
            provider_user_id = user_info["id"]
            email = user_info.get("email", "")
            name = user_info.get("name", "")
            avatar_url = user_info.get("picture", {}).get("data", {}).get("url", "")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}"
            )
        
        # Check if OAuth2 account already exists
        existing_oauth_account = await oauth2_account_crud.get_by_provider_and_user_id(
            db, provider=provider, provider_user_id=provider_user_id
        )
        
        if existing_oauth_account:
            # Update token data and return existing user
            await oauth2_account_crud.update_tokens(
                db, 
                oauth_account=existing_oauth_account,
                token_data=token_data
            )
            # IMPORTANT (SQLAlchemy async):
            # Accessing `existing_oauth_account.user` would trigger lazy-loading, which
            # causes `greenlet_spawn has not been called` errors in async context.
            # Always fetch the user explicitly instead.
            user = await user_crud.get(db, id=existing_oauth_account.user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found for OAuth2 account"
                )
            return user
        
        # Check if user exists by email
        existing_user = None
        if email:
            existing_user = await user_crud.get_by_email(db, email=email)
        
        if existing_user:
            # Link OAuth2 account to existing user
            oauth_account_data = {
                "user_id": existing_user.id,
                "provider": provider,
                "provider_user_id": provider_user_id,
                "provider_email": email,
                "provider_name": name,
                "provider_avatar_url": avatar_url,
            }
            
            oauth_account = await oauth2_account_crud.create(db, obj_in=oauth_account_data)
            # Store tokens + expiration using the shared, correct logic
            await oauth2_account_crud.update_tokens(
                db,
                oauth_account=oauth_account,
                token_data=token_data,
            )
            
            # Update user avatar if not set
            if not existing_user.avatar_url and avatar_url:
                await user_crud.update(
                    db, 
                    db_obj=existing_user, 
                    obj_in={"avatar_url": avatar_url}
                )
            
            return existing_user
        else:
            # Create new user
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email is required for account creation"
                )
            
            # Generate unique username
            username = await self._generate_unique_username(db, name or email.split("@")[0])
            
            user_data = OAuth2UserCreate(
                email=email,
                username=username,
                full_name=name,
                avatar_url=avatar_url,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=email,
                provider_name=name,
                provider_avatar_url=avatar_url
            )
            
            # Create user without password (OAuth2 only)
            user = await user_crud.create_oauth2_user(db, obj_in=user_data, token_data=token_data)
            return user
    
    async def _generate_unique_username(self, db: AsyncSession, base_username: str) -> str:
        """Generate a unique username based on the provided base"""
        # Clean the base username
        base_username = "".join(c for c in base_username if c.isalnum() or c in "_-").lower()
        if not base_username:
            base_username = "user"
        
        # Check if base username is available
        existing_user = await user_crud.get_by_username(db, username=base_username)
        if not existing_user:
            return base_username
        
        # Add numbers until we find a unique username
        counter = 1
        while True:
            username = f"{base_username}{counter}"
            existing_user = await user_crud.get_by_username(db, username=username)
            if not existing_user:
                return username
            counter += 1
    
    async def unlink_oauth_account(self, db: AsyncSession, user_id: int, provider: str) -> bool:
        """Unlink OAuth2 account from user"""
        oauth_account = await oauth2_account_crud.get_by_user_and_provider(
            db, user_id=user_id, provider=provider
        )
        
        if not oauth_account:
            return False
        
        await oauth2_account_crud.delete(db, id=oauth_account.id)
        return True

# Create service instance
oauth2_service = OAuth2Service() 