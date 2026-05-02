import logging
import time
from typing import Dict, List, Optional, Any, Callable

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import settings

logger = logging.getLogger(__name__)

class SimpleRateLimiter:
    """Simple rate limiter - always allows requests to avoid async issues"""

    def __init__(self):
        pass

    def is_rate_limited(self, identifier: str, rule_name: str = "api_general", user_tier: str = "free") -> Dict[str, Any]:
        """Simple rate limiting - always allow"""
        return {
            "is_limited": False,
            "current_count": 0,
            "max_requests": 1000,
            "window_size": 60,
            "reset_time": int(time.time()) + 60,
            "retry_after": 0,
            "rule_applied": "disabled"
        }

class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware"""
    
    def __init__(self, app, config: Dict[str, Any] = None):
        super().__init__(app)
        self.config = config or {}
        self.rate_limiter = SimpleRateLimiter()

        # Basic security configuration
        self.allowed_origins = settings.ALLOWED_ORIGINS or ["*"]
        self.max_request_size = self.config.get("max_request_size", 10 * 1024 * 1024)  # 10MB
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch"""
        start_time = time.time()
        
        try:
            # Security checks
            security_result = await self._perform_security_checks(request)
            if security_result["blocked"]:
                return JSONResponse(
                    status_code=security_result["status_code"],
                    content={"error": security_result["reason"]}
                )
            
            # Rate limiting
            rate_limit_result = await self._check_rate_limits(request)
            if rate_limit_result["is_limited"]:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": rate_limit_result["retry_after"],
                        "limit": rate_limit_result["max_requests"],
                        "window": rate_limit_result["window_size"]
                    },
                    headers={
                        "Retry-After": str(rate_limit_result["retry_after"]),
                        "X-RateLimit-Limit": str(rate_limit_result["max_requests"]),
                        "X-RateLimit-Remaining": str(
                            max(0, rate_limit_result["max_requests"] - rate_limit_result["current_count"])
                        ),
                        "X-RateLimit-Reset": str(rate_limit_result["reset_time"])
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            response = await self._add_security_headers(response)
            
            # Log request
            await self._log_request(request, response, time.time() - start_time)
            
            return response
            
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Internal server error"}
            )
    
    async def _perform_security_checks(self, request: Request) -> Dict[str, Any]:
        """Perform basic security checks (simplified to avoid async issues)"""
        client_ip = self._get_client_ip(request)

        # Basic content type validation for POST requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not any(ct in content_type for ct in [
                "application/json", "multipart/form-data",
                "application/x-www-form-urlencoded", "audio/", "image/"
            ]):
                return {
                    "blocked": True,
                    "reason": "Invalid content type",
                    "status_code": status.HTTP_400_BAD_REQUEST
                }

        return {"blocked": False}
    
    async def _check_rate_limits(self, request: Request) -> Dict[str, Any]:
        """Check rate limits based on request type and user"""
        # Temporarily disable rate limiting to avoid async issues
        return {
            "is_limited": False,
            "current_count": 0,
            "max_requests": 1000,
            "window_size": 60,
            "reset_time": int(time.time()) + 60,
            "retry_after": 0,
            "rule_applied": "disabled"
        }
    
    async def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers (common in load balancers)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        forwarded = request.headers.get("x-forwarded")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"
    
    async def _log_request(self, request: Request, response: Response, duration: float):
        """Simple request logging"""
        client_ip = self._get_client_ip(request)

        # Simple logging for errors only
        if response.status_code >= 400:
            logger.warning(f"Request failed: {client_ip} {request.method} {request.url.path} -> {response.status_code}")

class AudioSecurityValidator:
    """Security validator for audio uploads"""
    
    def __init__(self):
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.allowed_formats = ["wav", "mp3", "webm", "ogg", "m4a", "flac"]
        self.max_duration = 300  # 5 minutes
    
    async def validate_audio_upload(self, audio_data: bytes, filename: str = "") -> Dict[str, Any]:
        """Validate audio upload for security"""
        try:
            # File size check
            if len(audio_data) > self.max_file_size:
                return {
                    "valid": False,
                    "error": "File too large",
                    "max_size_mb": self.max_file_size // (1024 * 1024)
                }
            
            # File format validation (basic header check)
            if not self._is_valid_audio_format(audio_data):
                return {
                    "valid": False,
                    "error": "Invalid audio format"
                }
            
            # Malware signature check (basic)
            if self._contains_suspicious_patterns(audio_data):
                return {
                    "valid": False,
                    "error": "Suspicious file content detected"
                }
            
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"Audio validation error: {e}")
            return {
                "valid": False,
                "error": "Validation failed"
            }
    
    def _is_valid_audio_format(self, audio_data: bytes) -> bool:
        """Check if file has valid audio format headers"""
        if len(audio_data) < 12:
            return False
        
        # Check common audio format headers
        headers = [
            b"RIFF",      # WAV
            b"ID3",       # MP3
            b"\x1aE\xdf\xa3",  # WebM
            b"OggS",      # OGG
            b"fLaC",      # FLAC
            b"\x00\x00\x00\x20ftypM4A",  # M4A
        ]
        
        for header in headers:
            if audio_data.startswith(header):
                return True
        
        return False
    
    def _contains_suspicious_patterns(self, audio_data: bytes) -> bool:
        """Check for suspicious patterns in audio data"""
        # Check for embedded executable code
        suspicious_patterns = [
            b"MZ",  # PE executable header
            b"\x7fELF",  # ELF executable header
            b"<script",  # HTML/JS
            b"javascript:",
            b"eval(",
        ]
        
        for pattern in suspicious_patterns:
            if pattern in audio_data[:1024]:  # Check first 1KB
                return True
        
        return False

class InputSanitizer:
    """Input sanitization for text and data"""
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 10000) -> str:
        """Sanitize text input"""
        if not text:
            return ""
        
        # Limit length
        text = text[:max_length]
        
        # Remove null bytes
        text = text.replace("\x00", "")
        
        # Remove control characters except newlines and tabs
        text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")
        
        # Basic XSS prevention
        text = text.replace("<script", "&lt;script")
        text = text.replace("javascript:", "")
        text = text.replace("data:", "")
        
        return text.strip()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        if not filename:
            return "unnamed"
        
        # Remove path separators
        filename = filename.replace("/", "").replace("\\", "")
        
        # Remove dangerous characters
        dangerous_chars = "<>:\"|?*"
        for char in dangerous_chars:
            filename = filename.replace(char, "_")
        
        # Limit length
        filename = filename[:255]
        
        # Ensure it doesn't start with dot or dash
        if filename.startswith((".", "-")):
            filename = "file_" + filename
        
        return filename or "unnamed"

# Global instances
security_middleware = SecurityMiddleware
rate_limiter = SimpleRateLimiter()
audio_validator = AudioSecurityValidator()
input_sanitizer = InputSanitizer()
