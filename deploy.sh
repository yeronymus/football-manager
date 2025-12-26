#!/bin/bash

# Configuration
SERVER_USER="ubuntu"
SERVER_HOST="yernur-vm1.sin.cvut.cz"
BASE_DIR="/home/ubuntu"

if [ "$1" == "prod" ]; then
    ENV_NAME="prod"
    REMOTE_DIR="$BASE_DIR/football-prod"
    ENV_FILE="production.env"
    PORT=8000
elif [ "$1" == "dev" ]; then
    ENV_NAME="dev"
    REMOTE_DIR="$BASE_DIR/football-dev"
    ENV_FILE="development.env"
    PORT=8001
else
    echo "Usage: ./deploy.sh [prod|dev]"
    exit 1
fi

echo "Deploying to $ENV_NAME environment on $SERVER_HOST..."

# 1. Create directory if not exists
ssh $SERVER_USER@$SERVER_HOST "mkdir -p $REMOTE_DIR"

# 2. Sync Files (Exclude hidden, venv, etc.)
# Using rsync if available, otherwise scp
if command -v rsync &> /dev/null; then
    rsync -avz --exclude '.git' --exclude '__pycache__' --exclude 'venv' --exclude '.env' . $SERVER_USER@$SERVER_HOST:$REMOTE_DIR/
else
    # Fallback to SCP (simplified, copies everything not ignored ideally)
    echo "Rsync not found, using SCP..."
    scp -r ./* $SERVER_USER@$SERVER_HOST:$REMOTE_DIR/
fi

# 3. Copy Secret Env File
echo "Uploading $ENV_FILE as .env..."
scp $ENV_FILE $SERVER_USER@$SERVER_HOST:$REMOTE_DIR/.env

# 4. Restart Docker
echo "Restarting services..."
ssh $SERVER_USER@$SERVER_HOST "cd $REMOTE_DIR && docker-compose down --remove-orphans && docker-compose build && docker-compose up -d"

echo "Done! $ENV_NAME is running."
