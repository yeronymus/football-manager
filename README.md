# ⚽ Football Manager Bot

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2ca5e0?style=for-the-badge&logo=telegram&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=for-the-badge&logo=docker&logoColor=white)
![Status](https://img.shields.io/badge/Status-Production-success?style=for-the-badge)

**Automated system for organizing amateur football matches.**
The bot acts as a digital captain, handling roster management, team balancing, payment tracking, and statistics.

---

## 🌟 Key Features

### 🎮 Game Management

- **Automated Rosters**: People join via buttons. No more "I'm in" spam.
- **Queue System**: If the game is full (e.g., 14/14), new players go to the `Reserve` list.
- **Smart Balancing**: Algorithms balance teams based on player ratings (ELO-like system).
- **Payment Tracking**: Mark who paid via an Admin Dashboard.

### 📊 Stats & MVP

- **Rating System**: Players earn/lose points based on match results and individual performance.
- **MVP Voting**: Post-match voting integration.
- **Detailed History**: WebApp interface to view past games and personal stats.

---

## 🏗 Architecture (Modular Monolith)

This project has evolved from a simple script to a production-grade **Modular Monolith**.

### 1. Layers (`The Anti-Gravity Rule`)

We strictly enforce layer isolation to prevent spaghetti code:

- **Presentation (`app/bot`, `app/api`)**: Handles Telegram updates and WebApp requests. **Never** touches the DB directly.
- **Application (`app/core/services`)**: Pure business logic (e.g., "Joining a game", "Calculating ELO"). agnostic of the UI.
- **Domain (`app/core/domain`)**: Core entities and algorithms (e.g., Team Balancing logic).
- **Infrastructure (`app/infrastructure`, `app/db`)**: Databases, Schedulers available via repositories.

### 2. Transaction Management

We use the **Unit of Work (UoW)** pattern to ensure data consistency.

```python
async with UnitOfWork() as uow:
    service = RosterService(uow)
    await service.join_player(game_id, user_id)
    await uow.commit() # Atomic Commit
```

### 3. The Strangler Fig Pattern 🪴

We are currently migrating from a Legacy architecture to the New Core.

- **Legacy Games (ID <= 5)**: Handled by old monolithic scripts.
- **New Games (ID > 5)**: Handled by the new Service Layer.
- **Router**: Automatically directs user actions to the correct logic based on Game ID.

---

### 🚀 Deployment

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local dev)

### Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-username/football-manager-bot.git
cd football-manager-bot

# 2. Configure Environment
cp .env.example .env
# Edit .env with your BOT_TOKEN and DB credentials

# 3. Running
./scripts/ops/run_local.sh # or ./scripts/ops/prod.sh
```

### Documentation
See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for full details.

### Management CLI

We use `manage.py` for administrative tasks:

```bash
# Run inside container
docker-compose exec app python manage.py --help

# Example: Fix roster for a game
docker-compose exec app python manage.py roster fix --game-id 15
```

---

## 🛠 Tech Stack

- **Backend**: Python 3.11, Aiogram 3, SQLAlchemy (Async), FastAPI
- **Database**: PostgreSQL (Data), Redis (FSM & Cache)
- **Frontend**: Telegram WebApps (HTML/JS)
- **Infrastructure**: Docker Compose, Nginx (Reverse Proxy)

---

## 🛡 Security Note

This repository contains the **Source Code** of the bot.

- **Secrets** (Tokens, Passwords) are loaded from `.env` files (excluded from git).
- **Database Backups** are excluded.
- **Personal Data**: The production database is NOT included.

---
*Created by Yeronym. Open for engineering contributions.*
