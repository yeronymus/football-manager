# Future Development Roadmap 🚀

## 1. Telegram Mini App (Frontend Evolution)
Transition core user interaction (Profile & History) from chat commands to a rich Web App.

### Features
*   **Match History**: Full-screen WebView with infinite scroll, filtering, and detailed match views (rosters, scorers, MVP).
*   **User Profile**: Visual stats dashboard (Goals, MVP, Rating Graph) and form-based profile editing (Name, Position) to eliminate chat FSMs.

---

## 2. Scalability & Multi-Tenancy (10+ Chats) 🌍
**Goal:** Enable the bot to serve 10-100 independent football communities simultaneously without conflict or performance degradation. Thanks to the Service Layer Refactoring (Phase 1-3), this is now much easier.

### A. Data Isolation
*   **Chat-Specific Configs**: Move settings (like `max_players`, `price`, `locations`) from global `settings.py` to a `ChatConfig` database table.
    *   *Benefit*: One chat plays 5v5 for Free, another plays 8v8 for $5.
*   **Contextual Logic**: Ensure all Service methods (`UserService`, `GameService`) rigorously enforce `chat_id` checks. Users can have different Profiles/Stats in different chats? (Decision needed: Global Profile vs Per-Chat Profile).

### B. Architecture
*   **Asynchronous Workers**: Move heavy calculations (ELO for 50 players, Bulk Notifications) to a background worker queue (e.g., Celery or Arq) to keep the bot responsive.
*   **Database Partitioning**: If we hit 100+ chats, consider partitioning `games` and `signups` tables by `chat_id` for query speed.

### C. Onboarding
*   **Self-Service Setup**: An admin adds the bot -> runs `/setup` -> Configures payment token and location -> Ready to go. No developer intervention needed.

---

## 3. DevOps & Infrastructure (Reliability) 🛠️
**Goal:** Professionalize the deployment pipeline to ensure "Five Nines" (99.999%) availability and ease of development.

### A. CI/CD Pipeline (GitHub Actions)
*   **Lint & Test**: Auto-run `pytest` and `flake8/ruff` on every Pull Request.
*   **Auto-Build**: On merge to `main`, build Docker Image and push to a private Container Registry (GHCR or Docker Hub).
*   **Auto-Deploy**: SSH into the production server and run a rolling update (`docker-compose up -d --build`) automatically.

### B. Monitoring & Observability
*   **Sentry**: Integrate Sentry SDK to catch unhandled exceptions in real-time and get alerts on Telegram/Email.
*   **Prometheus + Grafana**:
    *   Track metrics: "Games Created per Hour", "Average Response Time", "Error Rate".
    *    Visualize server health (CPU/RAM usage).
*   **Log Aggregation**: Use Loki or ELK to search logs across containers (instead of `docker logs`).

### C. Reliability & Maintenance
*   **Automated Backups**: Script to dump Postgres DB every 6 hours to S3/Google Drive.
*   **Staging Environment**: A separate bot instance (`@fmBot_test`) deployed from a `staging` branch to test big features (like the new Balancer) before hitting real users.
*   **Infrastructure as Code (IaC)**: Use Terraform/Ansible to provision the Server (VM), protecting against "Server died and I forgot how I set it up" scenarios.

---

## 4. API & Integrations
*   **Public API**: Allow external websites to fetch stats/rankings for a chat (e.g., for a community website).
*   **Payment Gateways**: Integrate Stripe/Telegram Stars for automatic slot booking payment.

---

## 5. Technical Debt & Refactoring 🧹
*   **Refactor Handlers**: `app/bot/game_handlers.py` currently uses direct SQLAlchemy queries. It should be refactored to fully utilize `GameService` to centralize business logic and ensure strict layering.
