from fastapi import FastAPI, HTTPException, Depends, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
import uvicorn
import warnings
import logging
from pathlib import Path
from contextlib import asynccontextmanager


# Suppress pkg_resources deprecation warning from third-party libraries
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API",
    category=UserWarning
)

from app.core.config import settings
from app.core.database import init_db, close_db, get_db, seed_admin_users
from app.core.cache import get_redis
from app.api.v1.api import api_router
from app.api.v1.websockets.realtime_practice import websocket_practice_endpoint
from app.core.logging import setup_logging


# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


ASSETLINKS_FILE = (
    Path(__file__).resolve().parent / "app" / "static" / ".well-known" / "assetlinks.json"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # NOTE: Don't hard-fail app startup if the database is temporarily out of
    # connection slots during rolling deploys. The app can still boot and serve
    # /health, and DB-backed endpoints will reconnect when slots free up.
    try:
        await init_db()
    except Exception:
        logger.exception("Database connectivity check failed during startup; continuing.")
    
    # Seed admin users (safe to run repeatedly)
    try:
        await seed_admin_users()
    except Exception:
        logger.exception("Admin user seeding failed during startup; continuing.")
    
    # Ensure audio storage directory exists
    audio_dir = Path(settings.AUDIO_STORAGE_DIR)
    audio_dir.mkdir(parents=True, exist_ok=True)
    (audio_dir / "tts").mkdir(parents=True, exist_ok=True)
    
    yield
    # Shutdown
    try:
        await close_db()
    except Exception:
        logger.exception("Error while closing database/redis connections during shutdown.")

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="SelmApp - English Language Learning Application API",
    version="1.0.0",
    openapi_url=None,  # Disable default openapi
    docs_url=None,  # Disable default docs
    redoc_url="/redoc",
    lifespan=lifespan
)

# Security
security = HTTPBearer()

# Middleware



app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allow all hosts for development
)



# Include API router
#
# NOTE:
# DigitalOcean App Platform "ingress" path routing strips the matched prefix
# before forwarding the request to the component. If you route the API behind
# `/api`, a public request to `/api/v1/...` arrives at FastAPI as `/v1/...`.
#
# To keep the API reachable in both local/dev setups (often `/api/v1`) and
# reverse-proxy setups that strip `/api` (often `/v1`), we mount both prefixes.
app.include_router(api_router, prefix=settings.API_V1_STR)

# Ensure common prefixes are always available (idempotent guards).
if settings.API_V1_STR != "/v1":
    app.include_router(api_router, prefix="/v1")
if settings.API_V1_STR != "/api/v1":
    app.include_router(api_router, prefix="/api/v1")

# Audio file serving helper function
async def _serve_audio_file_impl(subpath: str, request: Request):
    """
    Internal implementation for serving audio files with CORS headers.
    """
    # Build the full path to the audio file
    audio_dir = Path(settings.AUDIO_STORAGE_DIR)
    file_path = audio_dir / subpath
    
    # Security: Ensure the path doesn't escape the audio directory
    try:
        file_path = file_path.resolve()
        audio_dir_resolved = audio_dir.resolve()
        if not str(file_path).startswith(str(audio_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Check if file exists
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Determine content type based on file extension
    suffix = file_path.suffix.lower()
    content_types = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".webm": "audio/webm",
    }
    content_type = content_types.get(suffix, "application/octet-stream")
    
    # Return file with CORS headers
    response = FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=file_path.name,
    )
    
    # Add CORS headers explicitly for audio files
    origin = request.headers.get("origin", "*")
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response


# Audio file serving endpoint with CORS support
# This replaces the static file mount to ensure CORS headers are included
@app.get("/media/audio/{subpath:path}")
async def serve_audio_file(subpath: str, request: Request):
    """
    Serve audio files with proper CORS headers for web browser playback.
    This endpoint handles audio files stored in the filesystem.
    """
    return await _serve_audio_file_impl(subpath, request)


# Duplicate endpoint for DigitalOcean ingress (which strips /media prefix)
# When DO routes /media/audio/... to backend, it becomes /audio/...
@app.get("/audio/{subpath:path}")
async def serve_audio_file_stripped(subpath: str, request: Request):
    """
    Serve audio files (for DigitalOcean path stripping).
    DigitalOcean strips the /media prefix, so /media/audio/x becomes /audio/x
    """
    return await _serve_audio_file_impl(subpath, request)


# Handle OPTIONS preflight requests for audio files
@app.options("/media/audio/{subpath:path}")
async def audio_options(subpath: str, request: Request):
    """Handle CORS preflight requests for audio files."""
    origin = request.headers.get("origin", "*")
    return Response(
        content="",
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400",
        }
    )


@app.options("/audio/{subpath:path}")
async def audio_options_stripped(subpath: str, request: Request):
    """Handle CORS preflight for stripped path."""
    origin = request.headers.get("origin", "*")
    return Response(
        content="",
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "86400",
        }
    )

# WebSocket endpoints
@app.websocket("/ws/practice/{session_id}")
async def websocket_practice(websocket: WebSocket, session_id: str, db=Depends(get_db)):
    """WebSocket endpoint for real-time practice sessions"""
    await websocket_practice_endpoint(websocket, session_id, db)


@app.get("/.well-known/assetlinks.json", include_in_schema=False)
async def assetlinks():
    """
    Digital Asset Links for Android association.
    Required for App Links + Google Password Manager / Credential Manager "credential sharing".
    """
    if ASSETLINKS_FILE.exists():
        return FileResponse(
            path=str(ASSETLINKS_FILE),
            media_type="application/json",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    # Fallback (keeps the endpoint working even if the file is missing in a build).
    return JSONResponse(
        content=[
            {
                "relation": [
                    "delegate_permission/common.handle_all_urls",
                    "delegate_permission/common.get_login_creds",
                ],
                "target": {
                    "namespace": "android_app",
                    "package_name": "com.selmapp.app",
                    "sha256_cert_fingerprints": [
                        "01:FE:76:70:13:6C:7C:36:4E:FB:93:BC:15:94:65:19:BD:BF:23:AF:2F:BB:E4:07:7B:52:97:EB:AB:88:0F:29"
                    ],
                },
            }
        ],
        headers={"Cache-Control": "public, max-age=3600"},
    )

@app.get("/")
async def root():
    return {"message": "SelmApp API", "version": "1.0.0", "status": "running"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "version": "1.0.0",
        "services": {
            "database": "connected",
            "redis": "connected",
            "ai_services": "ready"
        }
    }

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi():
    try:
        # Use FastAPI's auto-generation but with OpenAPI 3.0.0 for better compatibility
        from fastapi.openapi.utils import get_openapi
        
        if not hasattr(app, '_cached_openapi_schema'):
            # Generate the full schema
            full_schema = get_openapi(
                title="SelmApp API",
                version="1.0.0",
                description="English Language Learning Application API",
                routes=app.routes,
                openapi_version="3.0.0"  # Use 3.0.0 instead of 3.1.0
            )
            
            # Cache it to avoid regeneration
            app._cached_openapi_schema = full_schema
        
        return JSONResponse(
            content=app._cached_openapi_schema,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except Exception as e:
        # Fallback to minimal schema if auto-generation fails
        minimal_schema = {
            "openapi": "3.0.0",
            "info": {
                "title": "SelmApp API",
                "version": "1.0.0",
                "description": "English Language Learning Application API - Error in auto-generation"
            },
            "paths": {
                "/": {
                    "get": {
                        "summary": "Root endpoint",
                        "responses": {"200": {"description": "Successful Response"}}
                    }
                },
                "/health": {
                    "get": {
                        "summary": "Health Check", 
                        "responses": {"200": {"description": "Successful Response"}}
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "HTTPBearer": {"type": "http", "scheme": "bearer"}
                }
            }
        }
        
        return JSONResponse(
            content=minimal_schema,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache", 
                "Expires": "0"
            }
        )


@app.get("/api/v1/system/clear-cache")
async def clear_all_cache():
    """
    Clear all Redis cache.
    WARNING: This deletes EVERYTHING in Redis, including cached audio, sessions, etc.
    """
    try:
        redis = await get_redis()
        await redis.flushall()
        return {"success": True, "message": "Redis cache successfully cleared. All cached data will regenerate."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")

@app.get("/docs", response_class=HTMLResponse)
async def custom_swagger_ui_html():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SelmApp API Documentation</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui.css" />
        <link rel="icon" type="image/png" href="https://fastapi.tiangolo.com/img/favicon.png" />
        <style>
            html {
                box-sizing: border-box;
                overflow: -moz-scrollbars-vertical;
                overflow-y: scroll;
            }
            *, *:before, *:after {
                box-sizing: inherit;
            }
            body {
                margin:0;
                background: #fafafa;
            }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-bundle.js"></script>
        <script>
                 const ui = SwaggerUIBundle({
             url: '/openapi.json',
             dom_id: '#swagger-ui',
             presets: [
                 SwaggerUIBundle.presets.apis,
                 SwaggerUIBundle.presets.standalone
             ],
             layout: "BaseLayout",
             deepLinking: true,
             showExtensions: true,
             showCommonExtensions: true
         });
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True if settings.ENVIRONMENT == "development" else False
    ) 