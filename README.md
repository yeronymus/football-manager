# Football Manager Bot

An automated multi-tenant SaaS platform for amateur football communities, handling player registrations, dynamic ELO balancing, match tracking, and transactional analytics via a Telegram Bot API and a FastAPI-based WebApp backend.

## 🏗 System Architecture & Domain Model

The system follows a layered monolithic architecture strictly delineating the Telegram Client layer from the internal EventBus and Domain services. The primary entities and relationships form the following domain structure:

### Database Entities
- **`User`**: Core identity model encapsulating player statistics (`games_played`, `stats_mvp`, `stats_matches`) and ELO Rating (`rating`). Maps 1:1 with Telegram accounts. Maintains a `player_position` enum (GK, Defenders, Midfielders, Forwards).
- **`Game`**: The central transactional object representing a match event. Tracks `status` state machine (`OPEN` -> `ACTIVE` -> `FINISHED` | `CANCELLED`), financial details (`price`, `payment_info`), and roster caps (`max_players`, `signup_limit`). Has multiple `Signup` models.
- **`Signup`**: A many-to-many junction that dictates user availability per `Game`. Subject to state transitions (`ACTIVE`, `RESERVE`, `CANCELLED`) and handles match-specific position overrides.
- **`Vote`**: Represents peer-to-peer reputation mechanisms within a `Game` context for MVP calculations.
- **`RatingHistory`**: Immutable append-only ledger tracking ELO fluctuations `old_rating` -> `new_rating` with the calculated `change` delta per `Game`.

### Architectural Boundaries
* **Transport Layer:** Commands coming from Aiogram are converted to domain-agnostic DTOs before traversing into the business logic.
* **Service Layer:** Resolves player balancing algorithms using the ELO rating stored in `User` and generates a state payload.
* **Storage Layer:** PostgreSQL handled asynchronously via `asyncpg` and SQLAlchemy 2.0 ORM. Uses Alembic for schema versioning.

## 🚀 Quick Start & Local Setup

### Core Dependencies
We exclusively rely on modern dependency management tools for deterministic builds. Ensure you have `uv` installed, as this project uses a `pyproject.toml` definition paired with an immutable `uv.lock`. This guarantees zero drift between environments.

### Environment Schema (`.env`)
You must define the environment exactly, utilizing `.env.example` as a template. Below are critical constraints:
- `BOT_TOKEN`: The 46-character alphanumeric Telegram Bot token from @BotFather. This is strictly required for application boot.
- `SYSTEM_OWNER_ID`: 9-10 digit Telegram integer ID of the super-admin. Grants access to `manage.py` webhook overrides and infrastructure alerts.
- `WEBHOOK_URL`: Required if running in non-polling mode (Production). Format must be `https://<FQDN>/api/v1/webhook`.
- `POSTGRES_*`: Required connection parameters. Example DSN built internally: `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}`.

### Spin-Up Command
1. Clone and seed environment variables.
2. Build and initiate containers:
```bash
docker compose up -d --build
```
3. Run schema migrations via container execution:
```bash
docker compose exec app alembic upgrade head
```

### Seeding Test Data
Generate mock users, completed past matches, and ratings to populate the local WebApp dashboard:
```bash
docker compose exec app python manage.py db seed-history
```

## 🖥 Deployment Infrastructure

The infrastructure guarantees identical bit-for-bit deployment via `uv` strict locking. Operations are fully automated through **GitHub Actions**, triggering on pushes to `Main`.

### Minimal System Requirements (Target VM)
- **CPU**: 2 vCPUs (1 for DB, 1 for FastAPI App + Redis).
- **RAM**: 2 GB Minimum (PostgreSQL heap buffer + Python async event loops).
- **Storage**: 20 GB SSD (Log rotation + DB capacity).

### Security & Networking (Firewall)
Your cloud VM firewall (e.g. `ufw` or AWS Security Groups) must be strictly partitioned:
- `ALLOW 22/tcp` (SSH, restricted to safe IP).
- `ALLOW 443/tcp` (HTTPS Ingress for Webhook and WebApp).
- `ALLOW 80/tcp` (Let's Encrypt ACME challenges).
- `DENY EVERYTHING ELSE` (DB port 5432 and Redis port 6379 must remain isolated on localhost bridge `127.0.0.1`).

### Reverse Proxy (Nginx / Traefik)
The bot webhook requires terminating TLS before passing to the Uvicorn workers. An Nginx configuration must target `http://127.0.0.1:<APP_PORT>` with standard `proxy_set_header X-Forwarded-Proto https` enabled.

### Log Rotation Policy
Logs emitted by the WebApp and Aiogram workers are captured by the Docker daemon. Ensure `/etc/docker/daemon.json` limits log sprawl:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
```

---
*An industrial-grade solution for amateur football.
