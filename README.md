# Football Manager Bot ⚽️
[@fm_metabot](https://t.me/fm_metabot)

An industrial-grade multi-tenant SaaS platform for amateur football communities. The system orchestrates player registrations, dynamic ELO balancing, match tracking, and transactional analytics via a high-performance Aiogram client and FastAPI WebApp backend.

## 🏗 System Architecture & Domain Model

The system follows a Vertical Slice / Domain-Driven design (In Progress) focusing on strict process isolation and immutable build artifacts.

### Database Entities
- **`User`**: Core identity model encapsulating player statistics (`games_played`, `stats_mvp`) and ELO Rating (`rating`). 
- **`Game`**: Central transactional object representing a match event with a strict state machine (`OPEN` -> `ACTIVE` -> `FINISHED`).
- **`Signup`**: Many-to-many junction handling match-specific availability and team assignments.
- **`Chat`**: Configuration entity defining authorized Telegram groups and their corresponding admin channels.

## 🚀 Quick Start & Local Setup

### Core Dependencies
We exclusively rely on **`uv`** for deterministic dependency management. 
- **Python**: 3.11+
- **Database**: PostgreSQL 15+ & Redis 7+
- **Engine**: Docker + Compose

### 1. Environment Configuration
Copy `.env.example` to `.env` and configure:
- `INITIAL_CHATS`: JSON string defining the initial group/admin environment.
- `GHCR_PAT`: Required for CI/CD container registry access.

### 2. Launch
The infrastructure is fully automated. Simply run:
```bash
docker compose up -d
```
*Note: Database migrations (`alembic upgrade`) are automatically executed inside the container during boot.*

### 3. Data Seeding
```bash
# Initialize authorized chats from .env
docker compose exec app python manage.py db seed-chats

# Populate match history for testing
docker compose exec app python manage.py db seed-history
```

## 🔄 CI/CD & Auto-Deployment

This project utilizes a **Continuous Deployment** pipeline via GitHub Actions and **GHCR** (GitHub Container Registry).

1. **Build**: Every push to `Main` triggers a GitHub runner that compiles a sterile, immutable Docker image.
2. **Registry**: Images are tagged with `git-sha` and `latest` and pushed to `ghcr.io`.
3. **Continuous Deployment (Watchtower)**: The production server runs **Watchtower**, which monitors the registry. Once a new image is detected, Watchtower automatically:
   - Pulls the fresh image.
   - Gracefully stops the old container.
   - Runs database migrations.
   - Restarts the application.
   - **Typical delay**: ~60 seconds from build completion.

## 🖥 Deployment Infrastructure Guidelines

### Minimal System Requirements
- **CPU/RAM**: 2 vCPUs / 2 GB RAM minimum.
- **Storage**: 20 GB SSD with Docker log-rotation enabled.

### Firewall Policy
- `ALLOW 22/tcp` (SSH), `443/tcp` (HTTPS), `80/tcp` (ACME).
- **CRITICAL**: PostgreSQL (5432) and Redis (6379) MUST be restricted to the Docker bridge network only.

---
*Powered by Pydantic-Settings & Industrial-Grade CI. Reliability first.*
ootball.
