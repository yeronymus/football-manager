#!/usr/bin/env bash
set -e

# ==============================================================================
# Prague Football Manager — Server Pre-flight & Setup Script
# ==============================================================================

echo "🚀 Preparing server environment for Prague Football Manager..."

# 1. Verify Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed. Please install Docker first: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Error: Docker Compose plugin is not installed."
    exit 1
fi

# 2. Create external persistent volumes if they do not exist
echo "📦 Verifying Docker volumes..."
for vol in football-prod_postgres_data football-prod_redis_data; do
    if ! docker volume inspect "$vol" &> /dev/null; then
        echo "Creating Docker volume: $vol"
        docker volume create --name="$vol"
    else
        echo "Docker volume exists: $vol"
    fi
done

# 3. Create .env if missing
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "📄 Generating .env from .env.example..."
        cp .env.example .env
        echo "⚠️ Created .env file. Please edit it with your real BOT_TOKEN, DB credentials, and domain!"
    else
        echo "⚠️ Warning: .env.example not found."
    fi
else
    echo "✅ .env file exists."
fi

# 4. Create Prometheus monitoring config directory if missing
if [ ! -f "monitoring/prometheus.yml" ]; then
    mkdir -p monitoring
    cat << 'EOF' > monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'football_manager_api'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['app:8000']
EOF
    echo "✅ Created monitoring/prometheus.yml"
fi

echo "🎉 Server pre-flight setup completed!"
echo "Next steps:"
echo "  1. Review and edit .env with your BOT_TOKEN and passwords"
echo "  2. Start containers: docker compose up -d --build"
echo "  3. Check container logs: docker compose logs -f"
