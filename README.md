# ⚽ Football Manager Bot

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2ca5e0?style=for-the-badge&logo=telegram&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=for-the-badge&logo=docker&logoColor=white)

An automated management system for amateur football matches, handling rosters, team balancing, and statistics tracking through a Telegram Bot and a WebApp dashboard.

---

## 🏗 Project Structure

The project follows a **Modular Monolith** architecture with strict layer isolation:

```text
├── app/
│   ├── api/          # FastAPI WebApp & Auth logic
│   ├── bot/          # Telegram Bot handlers & logic (Aiogram)
│   ├── cli/          # Administrative CLI commands (manage.py)
│   ├── core/
│   │   ├── domain/   # Core entities, algorithms & historical data
│   │   ├── services/ # Business logic (Pure Python, UI agnostic)
│   │   └── uow.py    # Unit of Work for database transactions
│   ├── db/           # Database models & session management
│   └── infrastructure/ # External integrations & schedulers
├── alembic/          # Database migrations
├── tools/            # Legitimate utility scripts (not in CLI)
├── scripts/          # Operational & deployment scripts
└── manage.py         # Primary administrative interface
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+

### Installation & Local Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/yeronym/football-manager.git
   cd football-manager
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your BOT_TOKEN, DB credentials, and URLs
   ```

3. **Run with Docker:**
   ```bash
   docker compose up -d --build
   ```

---

## 🛠 Management CLI

The project uses `manage.py` as a centralized tool for administrative tasks. Run these commands inside the app container:

### Common Commands
- **Check Help:**  
  `python manage.py --help`
- **Generate Statistics (Excel):**  
  `python manage.py stats --game-id 7 --output FM_Stats_G7.xlsx`
- **Fix Roster for a Game:**  
  `python manage.py roster fix --game-id 15`
- **Add/Kick Player:**  
  `python manage.py add_player --game-id 15 --user-id 12345`
  `python manage.py kick_player --game-id 15 --user-id 12345`

---

## 🛡 Security & Best Practices
- **Secrets:** Never commit `.env` files. Use `.env.example` for templates.
- **Layers:** Business logic stays in `app/core/services`. Handlers (Bot/API) only manage presentation.
- **Database:** All schema changes must go through Alembic migrations.

---
*Developed for amateur football enthusiasts. Open for contributions.*
