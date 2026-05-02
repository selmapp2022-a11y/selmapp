# FROM python:3.11-slim AS base

# # Set environment variables
# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1
# ENV PYTHONPATH=/app

# # Set work directory
# WORKDIR /app

# # Install system dependencies
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends \
#     libsndfile1 \
#     ffmpeg \
#     build-essential \
#     libpq-dev \
#     ffmpeg \
#     curl \
#     && rm -rf /var/lib/apt/lists/*

# # Install Python dependencies
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Production stage
# FROM base AS production

# # Copy project
# COPY . .

# # Create necessary directories
# RUN mkdir -p uploads logs storage/audio

# # Create non-root user for security
# RUN adduser --disabled-password --gecos '' appuser && \
#     chown -R appuser:appuser /app
# USER appuser

# # Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:8000/health || exit 1

# # Expose port
# EXPOSE 8000


# # Run the application with gunicorn for production
# CMD ["gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]

# # Development stage
# FROM base AS development

# # Copy project
# COPY . .

# # Create necessary directories
# RUN mkdir -p uploads logs storage/audio

# EXPOSE 8000

# # Run with reload for development
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies (including build-essential for webrtcvad/librosa)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------------------------
# Development Stage (Moved UP - will not be used for deployment)
# -------------------------------------------------------------------
FROM base AS development
COPY . .
RUN mkdir -p uploads logs storage/audio
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# -------------------------------------------------------------------
# Production Stage (Moved DOWN - THIS is what DigitalOcean builds)
# -------------------------------------------------------------------
FROM base AS production

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p uploads logs storage/audio

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run with Gunicorn (production)
# NOTE: workers are configured via WEB_CONCURRENCY (default: 1) in gunicorn_conf.py
CMD ["gunicorn", "-c", "gunicorn_conf.py", "main:app"]