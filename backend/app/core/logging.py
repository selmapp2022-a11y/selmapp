import logging
import sys
from pathlib import Path
from functools import wraps
from typing import Any

# Import settings lazily to avoid circular imports
_settings = None

def _get_settings():
    global _settings
    if _settings is None:
        from app.core.config import settings
        _settings = settings
    return _settings


def setup_logging():
    """Setup logging configuration"""
    settings = _get_settings()
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    log_level = logging.DEBUG if settings.DEBUG else getattr(logging, settings.LOG_LEVEL)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name"""
    return logging.getLogger(name)


def debug_log(message: str, *args: Any, logger_name: str = "selmapp") -> None:
    """
    Log a debug message only when DEBUG mode is enabled.
    This is a replacement for print() statements in production code.
    """
    settings = _get_settings()
    if settings.DEBUG or settings.ENVIRONMENT == "development":
        logger = logging.getLogger(logger_name)
        logger.debug(message, *args)

