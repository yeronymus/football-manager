# ⚽ Football Manager Bot

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2ca5e0?style=for-the-badge&logo=telegram&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=for-the-badge&logo=docker&logoColor=white)

An automated management system for amateur football matches, handling rosters, team balancing, and statistics tracking through a Telegram Bot and a WebApp dashboard.

---

## 🏗 Project Structure

A clean, modular architecture focusing on layer isolation and business logic integrity:

```text
├── app/              # Core application logic
│   ├── api/          # FastAPI WebApp & Auth
│   ├── bot/          # Telegram Bot handlers (Aiogram)
│   ├── cli/          # Unified CLI subcommands
│   ├── core/         # Business logic & Domain entities
│   └── db/           # Models & Migrations
├── alembic/          # Database versioning
├── manage.py         # Primary administrative interface
└── .github/          # CI/CD Workflows (GitHub Actions)
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+

### Local Setup
1. **Clone & Configure:**
   ```bash
   git clone https://github.com/yeronym/football-manager.git
   cd football-manager
   cp .env.example .env
   ```
2. **Launch:**
   ```bash
   docker compose up -d --build
   ```

---

## 🛠 Management CLI

Use `manage.py` for all administrative tasks. Available commands:
- **Stats**: `python manage.py stats recalculate --go`
- **Backup**: `python manage.py db backup`
- **History**: `python manage.py db seed-history`

---

## 🖥 Deployment & Operations

### CI/CD Deployment
This project uses **GitHub Actions** for automated deployment. 
- Pushing to the **`Main`** branch (capital 'M') triggers an automatic update on the production server.
- Ensure `DEPLOY_HOST`, `DEPLOY_USER`, and `DEPLOY_SSH_KEY` are set in GitHub Secrets.

### Manual Maintenance
- **Backups**: `python manage.py db backup` (creates an `.sql` dump)
- **Database Shell**: `docker compose exec -u postgres db psql -U postgres -d football_prod`

---
*A streamlined solution for football communities. Simple, reliable, automated.*
