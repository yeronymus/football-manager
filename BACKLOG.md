# Project Backlog & Todo List

## 🏗 Architectural Debt (High Priority)
- [ ] **Decouple Bot & API:** Move to separate processes to prevent "Fate Sharing" (one crashing the other).
- [ ] **Persistent Event Bus:** Move from in-memory `EventBus` to Redis Streams or RabbitMQ (Reliability).
- [ ] **Router Refactoring:** Split `app/api/routers/admin.py` (400+ lines) into smaller, domain-focused routers.
- [ ] **Hexagonal Architecture:** Remove SQLAlchemy model dependencies from the Core layer (use DTOs/Entities).
- [ ] **Error Handling:** Replace `except: pass` (13+ instances) with structured logging and user-facing errors.
- [ ] **Hardcoded Contracts:** Centralize API URL registry instead of using f-strings everywhere.

## 🚀 Feature Roadmap
- [ ] **Live Dashboard 2.0:** Dynamic FastAPI-backed Mini App for real-time rating updates.
- [ ] **Position-Aware Balancing:** Improve algorithm to ensure GKs and Defenders are split evenly.
- [ ] **Historical Chemistry:** Track pairs of players who perform better together.
- [ ] **Monitoring:** Integrate Sentry for error tracking and Health-checks.
- [ ] **Security:** Implement OAuth2/Session management for the WebApp.
- [ ] **Elasticsearch:** Add full-text search for players and history.

## 🌍 SaaS Migration (DEADLINE: May 1st, 2026)
- [ ] **Data Core:** `PlayerProfile`, `ChatSettings`, `ChatAdmin` models.
- [ ] **Rating:** Algorithm update for 2, 3, and 4 teams.
- [ ] **Auth:** Telegram `initData` validation + JWT.
- [ ] **Bot:** Localization (RU/EN/CS) & `/setup` wizard.
- [ ] **Mini-App:** Player profiles, Leaderboards, Match history.
- [ ] **Ads:** Global & Per-group ad management with analytics.
- [ ] **Admin:** Superadmin & Group Admin web dashboards.

## 💅 UX & Quality of Life
- [ ] **Deduplicate Logs:** Prevent error spam to the system owner.
- [ ] **Context-Aware Buttons:** Automatically switch between WebApp and DeepLinks in channels.
- [ ] **Static Assets:** Versioning for WebApp forms (`?v=1.x`) to force Telegram cache refresh.
