# Football Manager Bot — Semestrální projekt B6B36NSS

Tento repozitář obsahuje semestrální projekt předmětu **B6B36NSS (Návrh softwarových systémů)** na ČVUT FEL. Projekt vyvíjím **samostatně**.

Jedná se o produkční systém pro kompletní správu amatérské fotbalové komunity v Praze prostřednictvím Telegram Botu (Aiogram 3.x) a doprovodného WebApp rozhraní (FastAPI).

---

## 📂 Architektonická dokumentace (Milestones)

Veškeré podklady pro semestrální práci byly úspěšně vypracovány a jsou uloženy ve vyhrazené složce repozitáře:

1. **[Milestone 1 Zpráva](nss_docs/NSS_milestone1.md)** — Architektonická zpráva obsahující analýzu stávajícího stavu (**AS-IS**), návrh cílové modularizované architektury (**TO-BE**), UML diagramy a specifikaci požadavků.
2. **[Milestone 2 Zpráva](nss_docs/NSS_milestone2.md)** — **Architektonická implementace** obsahující detailní popis 5 implementovaných návrhových vzorů (Strategy, Facade, Repository, Unit of Work, Observer), hybridní kešovací vrstvy (Passive + Active Invalidation), message brokeru na Redis Streams (Kafka-like spotřebitelské skupiny), HTTP Interceptoru s asynchronním logováním do Elasticsearch a detailní zabezpečení.

---

## 🛠️ Aktuálně hotová funkcionalita a změny

- **Datová vrstva:** Podle požadavků cvičícího byla provedena revize datových typů. Sloupec `Chat.language` byl plně refaktorován z obecného řetězce (`String`) na typově bezpečný výčtový typ **`Language` Enum (`RU`, `CZ`, `EN`)** (implementováno v `app/db/models.py`).
- **Příprava na Milestone 2:**
  - Infrastruktura pro transakční **Unit of Work** (`app/core/uow.py`).
  - Rozhraní a implementace repozitářů (`app/core/repositories/`).
  - Asynchronní event dispatcher (`app/core/events.py`).

---

## 🚀 Rychlé spuštění a testování

Projekt využívá moderní balíčkovač **`uv`** pro deterministickou správu závislostí a bezproblémové spuštění na stabilním Python 3.12.

### Spuštění testů
Pro lokální ověření funkčnosti a integrity datových modelů spusťte sadu unit testů:
```bash
PYTHONPATH=. uv run --python 3.12 pytest tests/
```

### Spuštění aplikace v Dockeru
Kompletní aplikační stack (FastAPI + PostgreSQL + Redis) lze spustit pomocí Docker Compose:
```bash
docker compose up -d
```
*Note: Database migrations (`alembic upgrade`) are automatically executed inside the container during boot.*

### 3. Data Seeding
```bash
# Initialize authorized chats from .env
docker compose exec app python app/presentation/cli/manage.py db seed-chats

# Populate match history for testing
docker compose exec app python app/presentation/cli/manage.py db seed-history
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
