from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.core.config import settings

# Simple password hashing without bcrypt dependencies
import hashlib
import secrets
import hmac

def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256()
    hash_obj.update((password + salt).encode('utf-8'))
    return f"sha256:{salt}:{hash_obj.hexdigest()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        method, salt, hash_value = hashed_password.split(':')
        if method != 'sha256':
            return False

        hash_obj = hashlib.sha256()
        hash_obj.update((plain_password + salt).encode('utf-8'))
        return hmac.compare_digest(hash_obj.hexdigest(), hash_value)
    except (ValueError, IndexError):
        return False

def get_password_hash(password: str) -> str:
    """Hash a password (alias for hash_password for compatibility)"""
    return hash_password(password)




def create_access_token(
    subject: Union[str, int], 
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def create_refresh_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT refresh token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> Optional[str]:
    """Verify JWT token and return subject"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        subject: str = payload.get("sub")
        token_type_payload: str = payload.get("type")
        
        if subject is None or token_type_payload != token_type:
            return None
        return subject
    except JWTError:
        return None

def generate_password_reset_token(email: str) -> str:
    """Generate password reset token"""
    delta = timedelta(hours=1)  # Token expires in 1 hour
    now = datetime.utcnow()
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email, "type": "password_reset"},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return encoded_jwt

def verify_password_reset_token(token: str) -> Optional[str]:
    """Verify password reset token"""
    try:
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if decoded_token.get("type") != "password_reset":
            return None
        return decoded_token["sub"]
    except JWTError:
        return None 