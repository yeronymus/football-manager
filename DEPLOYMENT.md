# 🚀 Deployment Guide

This guide describes how to deploy the Football Manager Bot to a remote server.

## Prerequisites

1.  **SSH Access**: You must have SSH access to the target server (e.g., `ubuntu@yernur-vm1.sin.cvut.cz`).
2.  **Docker**: The server must have `docker` and `docker-compose` installed.
3.  **SSH Key**: Your SSH public key must be in `~/.ssh/authorized_keys` on the server to allow passwordless login (required for the script).

## Environment Setup

The project uses two separate environment files for security:

*   **Production**: `production.env` -> Deployed to `~/football-prod/.env`
*   **Development**: `development.env` -> Deployed to `~/football-dev/.env`

**⚠️ Vital:** Never commit these files to public version control if they contain real secrets.

## 🛠 One-Command Deployment

We use a helper script `deploy.sh` to automate the process (sync files + restart containers).

### 1. Deploy to Production
Updates the running instance that users are currently using.

```bash
./deploy.sh prod
```

*   **Target**: `~/football-prod`
*   **Port**: `8000` (API), `5432` (DB)
*   **Config**: `production.env`

### 2. Deploy to Development
Updates the test instance for checking new features.

```bash
./deploy.sh dev
```

*   **Target**: `~/football-dev`
*   **Port**: `8001` (API), `5433` (DB)
*   **Config**: `development.env`

## Troubleshooting

### View Logs
To see what's happening in real-time (e.g., Python errors, SQL queries):

```bash
# Production
ssh ubuntu@yernur-vm1.sin.cvut.cz "docker logs -f football-prod_app_1"

# Development
ssh ubuntu@yernur-vm1.sin.cvut.cz "docker logs -f football-dev_app_1"
```

### Force Restart
If the bot gets stuck:
```bash
ssh ubuntu@yernur-vm1.sin.cvut.cz "cd ~/football-prod && docker-compose restart app"
```

## Infrastructure Details

*   **Database**: PostgreSQL 15 (Data stored in Docker Volume `postgres_data`)
*   **Cache**: Redis 7
*   **Reverse Proxy**: Nginx (managed externally on the host, proxies port 443 -> 8000)
