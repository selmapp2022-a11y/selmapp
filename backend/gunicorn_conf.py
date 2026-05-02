import os

# Gunicorn configuration for FastAPI (Uvicorn worker).
#
# Key goal: make concurrency configurable per environment. On managed Postgres
# plans with low max_connections, running too many workers + large SQLAlchemy
# pools can exhaust DB connections.

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
worker_class = "uvicorn.workers.UvicornWorker"

# Default to 1 worker (safe for small DBs). Override in your platform env:
# - WEB_CONCURRENCY=2 (or higher)
workers = int(os.getenv("WEB_CONCURRENCY", "1"))

timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Log to stdout/stderr (container friendly)
loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = "-"
errorlog = "-"


