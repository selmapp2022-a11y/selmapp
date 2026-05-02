

from datetime import timedelta
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_password_hash,
    verify_password,
    generate_password_reset_token,
    verify_password_reset_token
)
from app.core.config import settings
from app.schemas.auth import (
    Token, LoginResponse, UserCreate, UserLogin, OAuth2LoginRequest,
    OAuth2AuthURL, OAuth2AccountResponse, PasswordReset, PasswordResetConfirm
)
from app.schemas.user import User as UserSchema
from app.models.user import User
from app.crud.user import user_crud
from app.crud.oauth2 import oauth2_account_crud
from app.api.deps import get_current_user
from app.services.oauth2_service import oauth2_service

router = APIRouter()

@router.post("/register", response_model=LoginResponse)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Register a new user and automatically log them in.
    Returns access token and refresh token along with user data.
    """
    # Check if user already exists
    existing_user = await user_crud.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    existing_username = await user_crud.get_by_username(db, username=user_in.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create new user
    user = await user_crud.create(db, obj_in=user_in)

    # Generate tokens for automatic login
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        subject=user.id, expires_delta=refresh_token_expires
    )

    # Prepare user data
    user_data = {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "current_level": user.current_level.value if user.current_level else None,
        "native_language": user.native_language,
        "target_language": user.target_language,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_premium": user.is_premium,
        "is_admin": user.is_admin,
        "admin_role": user.admin_role,
        "has_password": user.has_password,
        "onboarding_completed": user.onboarding_completed,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }

    # Update last login
    await user_crud.update_last_login(db, user_id=user.id)

    # Return tokens and user data (auto-login after registration)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user_data
    }

@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Login and get access token"""
    user = await user_crud.authenticate(
        db, email=form_data.username, password=form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        subject=user.id, expires_delta=refresh_token_expires
    )

    # Store user data before updating last login to avoid lazy loading issues
    user_data = {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "current_level": user.current_level.value if user.current_level else None,  # Convert enum to string
        "native_language": user.native_language,
        "target_language": user.target_language,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_premium": user.is_premium,
        "is_admin": user.is_admin,
        "admin_role": user.admin_role,
        "has_password": user.has_password,
        "onboarding_completed": user.onboarding_completed,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }

    # Update last login
    await user_crud.update_last_login(db, user_id=user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": user_data
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Refresh access token"""
    user_id = verify_token(refresh_token, token_type="refresh")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user = await user_crud.get(db, id=int(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    
    new_access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    new_refresh_token = create_refresh_token(
        subject=user.id, expires_delta=refresh_token_expires
    )
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.get("/me", response_model=UserSchema)
async def read_users_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get current user"""
    # Load OAuth2 accounts
    oauth_accounts = await oauth2_account_crud.get_user_oauth_accounts(db, user_id=current_user.id)
    user_dict = current_user.__dict__.copy()
    user_dict["oauth_accounts"] = oauth_accounts
    return user_dict

# OAuth2 Endpoints
@router.get("/oauth/{provider}/authorize", response_model=OAuth2AuthURL)
async def oauth_authorize(
    provider: str
) -> Any:
    """Get OAuth2 authorization URL for a provider"""
    try:
        auth_data = oauth2_service.get_authorization_url(provider)
        return auth_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )

@router.post("/oauth/{provider}/callback", response_model=Token)
async def oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from OAuth2 provider"),
    state: str = Query(None, description="State parameter for security"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Handle OAuth2 callback and authenticate user"""
    try:
        # Authenticate with OAuth2 provider
        auth_result = await oauth2_service.authenticate_with_code(
            provider=provider,
            code=code,
            state=state,
            db=db
        )
        
        user = auth_result["user"]
        
        # Generate tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        
        access_token = create_access_token(
            subject=user.id, expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(
            subject=user.id, expires_delta=refresh_token_expires
        )
        
        # Update last login
        await user_crud.update_last_login(db, user_id=user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth2 authentication failed: {str(e)}"
        )

from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi import Request
import urllib.parse

# Mobile app deep link scheme
MOBILE_DEEP_LINK_SCHEME = "selmapp"

@router.get("/oauth/{provider}/callback")
async def oauth_callback_get(
    request: Request,
    provider: str,
    code: str = Query(..., description="Authorization code from OAuth2 provider"),
    state: str = Query(None, description="State parameter for security"),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Handle OAuth2 callback via GET (Google/GitHub/Facebook redirect here).
    Exchanges the code for tokens, then redirects to the frontend with tokens.
    
    For mobile apps, this returns an HTML page that attempts to redirect to the
    app's deep link (selmapp://oauth/callback?...). If the deep link fails
    (e.g., app not installed), it falls back to showing a success page with
    manual instructions.
    """
    try:
        # Authenticate with OAuth2 provider
        auth_result = await oauth2_service.authenticate_with_code(
            provider=provider,
            code=code,
            state=state,
            db=db
        )
        
        user = auth_result["user"]
        
        # Generate tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        
        access_token = create_access_token(
            subject=user.id, expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(
            subject=user.id, expires_delta=refresh_token_expires
        )
        
        # Update last login
        await user_crud.update_last_login(db, user_id=user.id)
        
        # Prepare token params
        params = {
            "oauth_success": "true",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": str(settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        }
        encoded_params = urllib.parse.urlencode(params)
        
        # Build deep link URL for mobile app
        deep_link_url = f"{MOBILE_DEEP_LINK_SCHEME}://oauth/callback?{encoded_params}"
        
        # Build web fallback URL
        frontend_url = settings.PUBLIC_BASE_URL.rstrip("/")
        web_url = f"{frontend_url}/?{encoded_params}"
        
        # Check if request is from a mobile device (basic User-Agent detection)
        user_agent = request.headers.get("user-agent", "").lower()
        is_mobile = any(device in user_agent for device in ["android", "iphone", "ipad", "mobile"])
        
        if is_mobile:
            # For mobile devices, return an HTML page that attempts deep link first
            # then falls back to opening the app store or showing instructions
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Login Successful - SelmApp</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .container {{
            text-align: center;
            padding: 40px 20px;
        }}
        h1 {{
            font-size: 28px;
            margin-bottom: 16px;
        }}
        p {{
            font-size: 16px;
            margin-bottom: 24px;
            opacity: 0.9;
        }}
        .spinner {{
            width: 50px;
            height: 50px;
            border: 4px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .btn {{
            display: inline-block;
            padding: 14px 32px;
            background: white;
            color: #667eea;
            text-decoration: none;
            border-radius: 25px;
            font-weight: 600;
            margin-top: 20px;
        }}
        .success-icon {{
            font-size: 64px;
            margin-bottom: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✓</div>
        <h1>Login Successful!</h1>
        <p>Redirecting you to SelmApp...</p>
        <div class="spinner"></div>
        <p id="fallback-msg" style="display: none;">
            If the app doesn't open automatically, tap the button below.
        </p>
        <a id="open-app-btn" href="{deep_link_url}" class="btn" style="display: none;">
            Open SelmApp
        </a>
    </div>
    <script>
        // Try to open the app via deep link
        var deepLink = "{deep_link_url}";
        var webFallback = "{web_url}";
        
        // Attempt deep link immediately
        window.location.href = deepLink;
        
        // Show fallback button after 2 seconds if we're still on this page
        setTimeout(function() {{
            document.getElementById('fallback-msg').style.display = 'block';
            document.getElementById('open-app-btn').style.display = 'inline-block';
            document.querySelector('.spinner').style.display = 'none';
        }}, 2000);
        
        // If still on page after 5 seconds, redirect to web version
        setTimeout(function() {{
            if (document.visibilityState !== 'hidden') {{
                window.location.href = webFallback;
            }}
        }}, 5000);
    </script>
</body>
</html>
"""
            return HTMLResponse(content=html_content, status_code=200)
        else:
            # For web browsers, redirect directly to frontend
            return RedirectResponse(url=web_url, status_code=302)
        
    except HTTPException as e:
        # Redirect to frontend with error
        frontend_url = settings.PUBLIC_BASE_URL.rstrip("/")
        params = urllib.parse.urlencode({
            "oauth_error": "true",
            "error_message": str(e.detail),
        })
        return RedirectResponse(url=f"{frontend_url}/?{params}", status_code=302)
    except Exception as e:
        # Redirect to frontend with error
        frontend_url = settings.PUBLIC_BASE_URL.rstrip("/")
        params = urllib.parse.urlencode({
            "oauth_error": "true",
            "error_message": f"OAuth2 authentication failed: {str(e)}",
        })
        return RedirectResponse(url=f"{frontend_url}/?{params}", status_code=302)

@router.post("/oauth/login", response_model=Token)
async def oauth_login(
    oauth_request: OAuth2LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Login with OAuth2 authorization code (alternative to callback)"""
    try:
        # Authenticate with OAuth2 provider
        auth_result = await oauth2_service.authenticate_with_code(
            provider=oauth_request.provider,
            code=oauth_request.code,
            state=oauth_request.state,
            db=db
        )
        
        user = auth_result["user"]
        
        # Generate tokens
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        
        access_token = create_access_token(
            subject=user.id, expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(
            subject=user.id, expires_delta=refresh_token_expires
        )
        
        # Update last login
        await user_crud.update_last_login(db, user_id=user.id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth2 authentication failed: {str(e)}"
        )

@router.get("/oauth/accounts", response_model=List[OAuth2AccountResponse])
async def get_oauth_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get user's linked OAuth2 accounts"""
    oauth_accounts = await oauth2_account_crud.get_user_oauth_accounts(db, user_id=current_user.id)
    return oauth_accounts

@router.delete("/oauth/{provider}/unlink")
async def unlink_oauth_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Unlink OAuth2 account from user"""
    # Check if user has password or other OAuth2 accounts
    oauth_accounts = await oauth2_account_crud.get_user_oauth_accounts(db, user_id=current_user.id)
    
    if not current_user.has_password and len(oauth_accounts) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink the only authentication method. Please set a password first."
        )
    
    success = await oauth2_service.unlink_oauth_account(db, current_user.id, provider)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth2 account for {provider} not found"
        )
    
    return {"message": f"Successfully unlinked {provider} account"}

@router.get("/oauth/providers")
async def get_oauth_providers() -> Any:
    """Get available OAuth2 providers"""
    providers = []
    
    if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
        providers.append({
            "name": "google",
            "display_name": "Google",
            "icon": "google"
        })
    
    if settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET:
        providers.append({
            "name": "github",
            "display_name": "GitHub",
            "icon": "github"
        })
    
    if settings.FACEBOOK_CLIENT_ID and settings.FACEBOOK_CLIENT_SECRET:
        providers.append({
            "name": "facebook",
            "display_name": "Facebook",
            "icon": "facebook"
        })
    
    return {"providers": providers}


# Password Reset Endpoints
@router.post("/forgot-password")
async def forgot_password(
    request: PasswordReset,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Request a password reset email.
    
    Always returns success to prevent email enumeration attacks.
    """
    from app.services.email_service import email_service
    
    user = await user_crud.get_by_email(db, email=request.email)
    
    if user:
        # Check if user has a password (not OAuth-only)
        if user.has_password:
            # Generate password reset token
            reset_token = generate_password_reset_token(request.email)
            
            # Send password reset email
            await email_service.send_password_reset_email(
                to_email=request.email,
                reset_token=reset_token,
                user_name=user.full_name
            )
    
    # Always return success to prevent email enumeration
    return {
        "message": "If an account with that email exists, we've sent a password reset link."
    }


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Reset password using a valid reset token.
    """
    # Verify the reset token
    email = verify_password_reset_token(request.token)
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get the user
    user = await user_crud.get_by_email(db, email=email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive"
        )
    
    # Validate new password
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long"
        )
    
    # Update password
    await user_crud.update(db, db_obj=user, obj_in={"password": request.new_password})
    
    return {"message": "Password has been reset successfully"} 

# --------------------------------------------------------------------
# Native mobile sign-in (Google + Apple)
# --------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel
import jwt as _pyjwt
from jwt import PyJWKClient as _PyJWKClient

_APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUER = "https://appleid.apple.com"
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class GoogleNativeRequest(_BaseModel):
    id_token: str


class AppleNativeRequest(_BaseModel):
    identity_token: str
    full_name: str | None = None
    email: str | None = None  # Apple only sends email on first sign-in


def _build_native_token_response(user) -> dict:
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(subject=user.id, expires_delta=access_token_expires),
        "refresh_token": create_refresh_token(subject=user.id, expires_delta=refresh_token_expires),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/oauth/google/native", response_model=Token)
async def oauth_google_native(
    body: GoogleNativeRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Verify a Google ID token from the mobile app and return our JWT.

    The mobile app obtains the ID token via the native google_sign_in SDK
    and posts it here. We verify with Google's tokeninfo endpoint, then
    find/create the user and issue our own access/refresh tokens.
    """
    if not body.id_token:
        raise HTTPException(status_code=400, detail="id_token required")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(_GOOGLE_TOKENINFO_URL, params={"id_token": body.id_token})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail=f"Google ID token invalid: {r.text[:200]}")
        info = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google ID token verification failed: {e}")

    # Verify audience matches one of our Google client IDs.
    expected_auds = {
        v for v in (
            settings.GOOGLE_CLIENT_ID,
            getattr(settings, "GOOGLE_IOS_CLIENT_ID", None),
            getattr(settings, "GOOGLE_ANDROID_CLIENT_ID", None),
        ) if v
    }
    if expected_auds and info.get("aud") not in expected_auds:
        raise HTTPException(status_code=401, detail=f"Google audience mismatch: {info.get('aud')}")
    if info.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
        raise HTTPException(status_code=401, detail=f"Google issuer invalid: {info.get('iss')}")
    if not info.get("email"):
        raise HTTPException(status_code=400, detail="Google profile missing email")

    user_info = {
        "id": info.get("sub"),
        "email": info.get("email"),
        "name": info.get("name") or info.get("email", "").split("@")[0],
        "picture": info.get("picture", ""),
    }
    auth_result = await oauth2_service.authenticate_with_user_info(
        provider="google", user_info=user_info, db=db,
    )
    user = auth_result["user"]
    await user_crud.update_last_login(db, user_id=user.id)
    return _build_native_token_response(user)


@router.post("/oauth/apple/native", response_model=Token)
async def oauth_apple_native(
    body: AppleNativeRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Verify an Apple identity_token from the mobile app and return our JWT.

    Verification: fetch Apple's JWKS, validate signature + iss + aud + exp.
    Audience must match APPLE_BUNDLE_ID (iOS) or APPLE_SERVICE_ID (web).
    """
    if not body.identity_token:
        raise HTTPException(status_code=400, detail="identity_token required")
    expected_auds = {
        v for v in (
            getattr(settings, "APPLE_BUNDLE_ID", None),
            getattr(settings, "APPLE_SERVICE_ID", None),
        ) if v
    }
    if not expected_auds:
        raise HTTPException(
            status_code=503,
            detail="Apple sign-in not configured (set APPLE_BUNDLE_ID).",
        )
    try:
        jwk_client = _PyJWKClient(_APPLE_JWKS_URL)
        signing_key = jwk_client.get_signing_key_from_jwt(body.identity_token)
        # PyJWT verifies signature, exp, iss, aud automatically.
        claims = _pyjwt.decode(
            body.identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=list(expected_auds),
            issuer=_APPLE_ISSUER,
        )
    except _pyjwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Apple identity_token invalid: {e}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Apple verification failed: {e}")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=400, detail="Apple token missing subject")

    # Apple only returns email on the very first sign-in. Use cached email
    # from the user record on subsequent sign-ins; otherwise fall back to
    # the proxy email from the token, then to the body field.
    email = claims.get("email") or body.email or ""
    name = body.full_name or ""

    user_info = {
        "sub": sub,
        "email": email,
        "name": name,
    }
    try:
        auth_result = await oauth2_service.authenticate_with_user_info(
            provider="apple", user_info=user_info, db=db,
        )
    except HTTPException as e:
        # Most common: missing email on first sign-in for an account that
        # the iOS device chose to hide. Surface a clear actionable message.
        if "email" in str(e.detail).lower():
            raise HTTPException(
                status_code=400,
                detail="Apple sign-in needs your email on first sign-in. "
                       "Please choose Share My Email and try again.",
            )
        raise
    user = auth_result["user"]
    await user_crud.update_last_login(db, user_id=user.id)
    return _build_native_token_response(user)
