# Stage 1: Build virtual environment
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system libraries needed to build native extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Build the virtual environment using uv
RUN uv sync --frozen --no-cache

# Stage 2: Final lightweight runtime
FROM python:3.11-slim AS runner

WORKDIR /app

# Install only minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create non-root user with home directory
RUN groupadd -r appuser && useradd -m -r -g appuser appuser

# Copy project files and set ownership to appuser
COPY --chown=appuser:appuser . .
RUN chown -R appuser:appuser /app /home/appuser

# Final user switch to non-privileged user
USER appuser

# Start the application using python from venv directly
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python scripts/health_check.py || exit 1
