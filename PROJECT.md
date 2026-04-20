# Football Manager Bot — Project Constitution

Automated management system for amateur football matches in Prague. 
Organizes games, balances teams by ELO/Position, and tracks historical stats.

## 🛠 Technology Stack
- **Backend:** Python 3.11, FastAPI (REST API)
- **Bot:** Aiogram 3.x (Telegram Interface)
- **Database:** PostgreSQL 15, SQLAlchemy ORM, Alembic Migrations
- **Cache/FSM:** Redis 7
- **Deployment:** Docker, Docker Compose, GitHub Actions (CI/CD)

## 🏗 Architecture (AS-IS)
The project is currently a **Layered Monolith**.
- **`app/api`**: FastAPI routers and WebApp auth.
- **`app/bot`**: Telegram event handlers and UI formatting.
- **`app/core`**: Business logic, domain entities, and services.
- **`app/db`**: Database models and repository implementations.
- **`app/infrastructure`**: External integrations (Scheduler).

### Operational Logic
- **"Anti-Gravity" Rule:** Services MUST NOT import from `app.bot`. Bot layer handles all UI formatting.
- **Unit of Work:** All DB operations within a request share a single session managed by UoW.
- **Transactional Safety:** Critical state changes (joining matches) use `SELECT FOR UPDATE`.

## 🖥 Production Environment
- **Host:** `147.32.107.65` (Proxmox VM)
- **SSH Port:** `2222` (User: `root`)
- **Container Name:** `football-manager-app-1`
- **Backups:** Managed via `manage.py db backup`.
- **Sudo/Credentials:** Managed via `.env` secrets. Standard `sudo` privileges are required for Docker operations.

## 📂 Project-Specific .gitignore Rules
- `PROJECT.md`, `AGENTS.md`, `BACKLOG.md`: Internal documentation and agent configs.
- `docs/`: Historical documentation (now consolidated).
- `backups/`: SQL dumps and data restoration files.
- `*.db`: Local SQLite databases.
- `Draft_Stats*.md`: Temporary statistics exports.
- `temp/`: Disposable scripts for data migration or inspection.
