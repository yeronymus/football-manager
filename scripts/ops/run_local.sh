#!/bin/bash
source venv/bin/activate

# Load local.env
export $(grep -v '^#' local.env | grep -v '^[[:space:]]*$' | xargs)

# Override for local host execution
export POSTGRES_HOST=localhost
export REDIS_HOST=localhost
export POSTGRES_PORT=5432  # Assuming docker exposes 5432:5432 or verify
export APP_PORT=8000

uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
