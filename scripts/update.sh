#!/bin/bash
set -e

echo "Pulling latest application image from GHCR..."
docker compose pull app

echo "Running DDL database migrations securely..."
docker compose run --rm app alembic upgrade head

echo "Restarting application container pool..."
docker compose up -d --force-recreate app

echo "Update process completed. Server is live."
