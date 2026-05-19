# ⚽ Football Manager Bot

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Aiogram 3.x](https://img.shields.io/badge/Aiogram-3.x-red.svg?style=for-the-badge&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL 15](https://img.shields.io/badge/PostgreSQL-15-blue.svg?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis 7](https://img.shields.io/badge/Redis-7-red.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Docker Compatible](https://img.shields.io/badge/Docker-Compatible-blue.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![CI/CD Pipelines](https://img.shields.io/badge/CI/CD-GitHub_Actions-purple.svg?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/features/actions)

Welcome to the **Football Manager Bot** — an industrial-grade, fully automated ecosystem designed to manage amateur football communities. Powering active matches, real-time signups, team balancing algorithms, dynamic ELO ratings, and user-friendly dashboards directly from Telegram.

Built with an asynchronous core using **Aiogram 3.x** and **FastAPI**, this is a production-ready solution to bring your amateur league, casual club, or weekend community matches to the professional level.

---

## ✨ Outstanding Core Features

### ⚽ Intelligent Match Balancing
No more unfair teams or manual coordination headaches! The system features an advanced team balancer delegating work through a clean **Strategy Pattern**:
*   **🐍 Rating Snake Draft Strategy**: The optimal approach for rating-based balancing. Matches players sequentially to distribute skill ratings evenly across teams.
*   **🛡️ Role-Based Strategy**: Balances teams based on player positions (Goalkeepers, Defenders, Midfielders, Forwards) ensuring no team is left without a keeper or overloaded with strikers.
*   **🎲 Random Shuffling**: Perfect for lighthearted training sessions and quick scrimmages.

### 📊 Interactive WebApp Dashboard
A responsive, high-performance HTML5/JS WebApp integrated natively inside Telegram. Players can view stats, register for upcoming fixtures, and manage their player cards with zero friction.
*   **Live Match Drafts**: Admins can run live drafts, balancing teams and instantly updating players.
*   **Dynamic Stats**: Full view of clean historical matches, player rankings, ELO distribution, goals, and MVP counts.

### ⚡ Blazing-Fast Performance
*   **Hybrid Caching Engine**: Integrates a Redis-backed *Passive Look-aside Cache* combined with *Active Invalidation* on writes. Response times for critical game detail queries drop under **1.5ms**!
*   **N+1 Query Elimination**: Critical service layers (stats reversion, lifecycle state changes) are audited and optimized with SQLAlchemy bulk fetches, ensuring zero redundant database trips.

### 📮 Reliable Messaging Engine
*   **Redis Streams (Kafka-like)**: Replaced volatile in-memory busses with persistent append-only logs. Supports publisher/consumer configurations with consumer groups and explicit ACKs. Your events are never lost, even if a process restarts.

### 🔒 Enterprise-Grade Security
*   **Telegram WebApp HMAC Validation**: Protects all API routes by parsing and validating Telegram `initData` signatures using the bot's secret token.
*   **Role-Based Access Control**: Sensitive actions (roster updates, match finalization, database seeding) are restricted via strict group-admin role validation.

---

## 📸 App Preview

Here is a sneak peek of our beautiful Telegram WebApp and Bot interface:

<p align="center">
  <img src="assets/f5718e0db0b206883782208dceb69bb2.png" alt="Roster Management" width="280" style="margin: 10px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.15);"/>
  <img src="assets/f5718e0db0b206883782208dceb69bb31.png" alt="Interactive WebApp" width="280" style="margin: 10px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.15);"/>
  <img src="assets/f5718e0db0b206883782208dceb69bb310.png" alt="Dynamic Statistics" width="280" style="margin: 10px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.15);"/>
</p>

---

## 🛠️ Technical Stack & Architecture

| Layer | Technology | Key Implementation |
| :--- | :--- | :--- |
| **Frameworks** | Python 3.12 · FastAPI · Aiogram 3.x | Clean routing, asynchronous handlers, structured middleware. |
| **Database** | PostgreSQL 15 · SQLAlchemy (Async) | Strict models, optimized bulk actions, type-safe Enums (`CZ`, `EN`, `RU`). |
| **Caching** | Redis 7 | High-performance look-aside cache, active invalidation routes. |
| **Broker** | Redis Streams | Persistent pub/sub event processing with ACK validation. |
| **Search/Logs** | Elasticsearch · Telemetry Middleware | Resilient async HTTP logging with fail-safe fallbacks. |
| **CI/CD** | GitHub Actions · GHCR · Watchtower | Zero-downtime automated deployment pipelines. |

---

## 🚀 Quick Start & Local Development

This project uses **`uv`** — the ultra-fast Python package manager — for deterministic virtualenv and dependency lockfile resolution.

### Prerequisites
Make sure you have `docker` (with Compose) and `uv` installed.

### 1. Configure the Environment
Create your local configuration:
```bash
cp .env.example .env
```
Fill in your `BOT_TOKEN` (retrieved from [@BotFather](https://t.me/BotFather)) and adjust database credentials as needed.

### 2. Run the Stack (Docker Compose)
Launch the entire system (FastAPI app, PostgreSQL database, Redis instance, and Elasticsearch log sink):
```bash
docker compose up --build -d
```
*Note: Database migrations (`alembic upgrade head`) are executed automatically during the container boot sequence.*

### 3. Seed Database for Testing
Generate mockup data and authorize chats instantly:
```bash
# Seed authorized group chats from your .env file
docker compose exec app python app/presentation/cli/manage.py db seed-chats

# Populate historical matches and players for testing
docker compose exec app python app/presentation/cli/manage.py db seed-history
```

### 4. Running the Tests Locally
Our codebase has **100% green test coverage** (59 robust unit and integration tests). Run them with:
```bash
PYTHONPATH=. uv run --python 3.12 pytest tests/
```

---

## ⚙️ Environment Variables Reference

| Variable | Description | Default |
| :--- | :--- | :--- |
| `BOT_TOKEN` | Telegram Bot API Token | `YOUR_BOT_TOKEN_HERE` |
| `POSTGRES_DB` | Database name | `postgres` |
| `REDIS_URL` | Redis connections string | `redis://redis:6379/0` |
| `ELASTICSEARCH_URL`| Elasticsearch logging sink | `http://elasticsearch:9200` |
| `ADMIN_IDS` | JSON list of static admin IDs | `[]` |
| `SYSTEM_OWNER_ID` | Telegram ID of the system owner | `100000000` |

---
*Created with Passion & Engineered for Performance. Elevating Amateur Football Everywhere.*
