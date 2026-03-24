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
├── scripts/          # Operational & backup scripts
├── tools/            # Data processing utility scripts
├── Dockerfile        # Container specification
├── docker-compose.yml # Infrastructure orchestration
└── manage.py         # Primary administrative interface
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
- **Stats**: `python manage.py stats --game-id [N]`
- **Roster**: `python manage.py roster fix --game-id [N]`
- **Admin**: `python manage.py add_player --game-id [N] --user-id [ID]`

---

## 🖥 Deployment & Operations

### Production Release
Deploy the latest code from the **`Main`** branch (capital 'M'):

```bash
ssh yernur@10.50.109.14
cd ~/football-manager
git pull origin Main
docker compose up -d --build --force-recreate app
```

### Database Maintenance
- **Backups**: `./scripts/backup_db.sh`
- **Shell**: `docker compose exec -u postgres db psql -U postgres -d football_prod`

---
*A streamlined solution for football communities. Simple, reliable, automated.*
