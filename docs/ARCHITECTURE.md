# PROJECT CONSTITUTION & CODING STANDARDS

You are acting as a Senior Backend Architect. Your goal is to enforce strict architectural integrity.
Refuse to generate code that violates these rules, explaining the violation.

## 1. THE "ANTI-GRAVITY" RULE (Layer Isolation)
- **Dependency Flow:** Bot -> Services -> DB/Repositories.
- **FORBIDDEN:** Services (`app/services` or `app/core/services`) MUST NEVER import from `app/bot`.
- **Reasoning:** Services are pure business logic. They do not know Telegram exists.
- **Alternative:** If a Service needs to notify a user, it returns a `Result` object or emits an `Event`. The Bot layer handles the actual sending.

## 2. TRANSACTION SAFETY (ACID)
- **Rule:** Service methods generally SHOULD NOT call `session.commit()`.
- **Pattern:** Use the "Unit of Work" pattern. The Controller (Bot Handler) initializes the transaction, calls the Service, and commits/rollbacks based on the result.
- **Exception:** Long-running background tasks (Scheduler) may manage their own transactions explicitly.
- **Concurrency:** Any method modifying shared state (game slots, money) MUST use `with_for_update()` (SELECT FOR UPDATE) to prevent race conditions.
    - *Good:* lock row -> check count -> insert.

## 3. NO "GOD OBJECTS" (SRP)
- **Refactoring Mandate:** `GameService` is currently a God Object. Do not add new features to it directly.

- **Strategy:** Break down logic into specialized domains:
    - `RosterService`: managing signups/teams.
    - `GameLifecycleService`: create/finish/cancel, status changes, task scheduling.
    - `StatsService`: ELO/history.

## 4. STRICT TYPING & OUTPUTS
- **No Strings Attached:** Services must return Pydantic Models (DTOs) or ORM objects, NEVER formatted strings (HTML/Markdown).
- **Formatting:** String formatting happens ONLY in `app/bot/utils` or handlers. The Service provides raw data (Integers, Dates, Enums).

## 5. NO SCRIPTING
- **Rule:** Do not create root-level scripts (like `fix_roster.py`) that bypass the Service layer.
- **Solution:** Create management commands (CLI) that import and use the Services. If a Service method is missing, create it.

## 6. EXPLICIT DEPENDENCIES
- **No Global Imports:** Do not rely on global `scheduler` or `bot` instances inside function bodies.
- **Injection:** Pass dependencies via `__init__` or method arguments.

## 7. DATABASE MIGRATIONS
- **Rule:** Code changes affecting the database schema (adding columns, changing types) MUST be accompanied by a migration.

- **Production Safety:** Always verify that migrations have run before the application starts.
- **Learning Case:** The Game #6 crash occurred because local code expected `registration_hours`, but the production DB (`football_prod`) was not updated.
- **Verification:** Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` in manual or automated scripts to ensure idempotency.

## 8. PERFORMANCE & LOGGING
- **Production Logging:** `echo=True` in SQLAlchemy MUST be disabled in production. It causes massive I/O overhead.
- **Redundant Queries:** Minimize DB round-trips. If a task requires formatting multiple messages, fetch data once and pass it down.
- **I/O Awareness:** Avoid frequent `logging.warning` for debug data in hot paths (like message formatting).

## 9. INFRASTRUCTURE-FIRST MINDSET
- **Habit:** Before adding a feature, ask: "Does this change the DB schema or .env?".
- **Checklist:**
    1. Update `models.py`.
    2. Create/Verify Migration script.
    4. Deploy Infrastructure (DB changes) *before* App code if possible.

## 10. SESSION CONTINUITY & IMPROVEMENT
- **Rule:** At the end of each session, the Assistant MUST document a brief "Session Conclusion" in the repository.

- **Goal:** To ensure the project's evolution is understood and to identify areas for future optimization without re-learning the same lessons.
- **Content:** What was fixed, what "traps" were found, and what should be improved next.

## 11. MINIMAL SPAM POLICY
- **Rule:** MINIMIZE BOT MESSAGES AND SPAM AT ALL COSTS.
- **Strategy:** Instead of sending new messages for every action (e.g., "Teams balanced", "Player added"), ALWAYS try to silently update the existing game message or dashboard using `edit_message_text`.
- **Priority:** Consider message reduction as a top-tier queue item when developing or refactoring features. Users should not be overwhelmed with notifications.

---

## SESSION CONCLUSION (Game #6 Recovery)
- **What was fixed:** Manual DB migration applied, Bot performance optimized (SQL logging disabled), Registration window added.
- **Traps found:** 
    1. **I/O Wait:** The production server has extreme disk latency causing `rsync` and `scp` to hang or fail silently. 
    2. **Caching:** Telegram WebApp caches HTML forms aggressively; manual versioning in the footer/payload is needed to verify updates.
- **Next steps:** investigate move to SSD or optimize disk usage. Implement version-based cache busting for static assets.

---

## SESSION CONCLUSION (Game #8 Launch / Server Migration)
**Date:** 2026-03-04

### What was fixed:
1. **Server migration**: Old server (`yernur-vm1.sin.cvut.cz`) died. Migrated to `dmc12.sin.cvut.cz` (IP: `10.50.109.14`).
2. **HTTPS / Mini Apps**: No public DNS for new server → Used Cloudflare Quick Tunnel (`*.trycloudflare.com`) as temporary HTTPS.  
   ⚠️ **Tunnel URL changes on restart** — долгосрочно нужен домен или named tunnel.
3. **`games_id_seq` desync**: PostgreSQL sequence was at 1 while `MAX(id)=7` — caused `UniqueViolationError`. Fixed via `setval('games_id_seq', 7)`.
4. **Missing `select` import** in `game_lifecycle.py` — caused 500 on game creation.
5. **`Chat.channel_id` model mismatch**: Added column to DB but forgot to deploy updated `models.py` — caused `AttributeError` silently.
6. **Game type display bug**: `game.game_type` stored as raw string `"draft"`, not Enum. `.value` raised `AttributeError`, silently caught → showed "Общая игра". Fixed with `hasattr(game.game_type, 'value')` guard.
7. **Message not updating on join**: `message_id` was `NULL` because endpoint threw exception mid-way (before commit). Listener checked `if game.message_id` and silently skipped edit.
8. **Stats restoration**: 57 users in DB after server crash. 41 matched and restored from `FM_Player_Stats.csv`. 3 additional manual fixes for accounts with name order mismatch (`Bekmolda Daulet`) or entirely new registrations (`Zhanibek Xenbek`, `Miras Mukanov`).

### Unexpected Findings (Ловушки):
1. **`docker compose restart` does NOT reload `.env`** — нужен `docker compose up -d` для подхвата новых env vars.
2. **`check_admin_rights` breaks for chats where bot is not admin** — `getChatMember` requires bot to have admin rights. Fixed by bypassing check for `admin_ids`/`system_owner_id`.
3. **Auto-join during game creation does NOT publish to `event_bus`** — so the initial message shows `is_short=True` without a player list even after auto-join. Fixed by using `is_short=False` for the initial publish.
4. **`rsync` not installed on server** — `deploy.sh` relies on rsync but it's not on the production host. Use `scp` per-file or install rsync.
5. **Duplicate users after DB restore**: When old DB backup is restored AND players re-register, you get two user records with the same name but different Telegram IDs. Restore script must target the CURRENT account (higher user_id for newer accounts), not just first name-match.
6. **`is_short=True` vs `is_short=False` inconsistency**: Initial publish uses one mode, listener updates use another. If channel link is broken, users never see the full player list. Both should use `is_short=False` until channel flow is stable.

### Known Issues (to fix):
- [ ] **CloudFlare Quick Tunnel**: URL changes on restart → need `dmc12.sin.cvut.cz` public DNS + certbot OR named Cloudflare Tunnel with `dmc12.com` domain.
- [ ] **Channel announcement**: New code sends to `chat.channel_id` but old channel detection logic may conflict. Test and unify the two code paths.
- [ ] **Duplicate user accounts**: ~4 players have 2 Telegram accounts in DB. After Game #8, merge or delete the restored-backup duplicates.
- [ ] **Docker deploy workflow**: No `rsync`. Need to add `rsync` to server or switch to `git pull` + `docker compose up` workflow on the server itself.
- [ ] **DB schema migrations**: Still no Alembic. Every schema change requires manual `ALTER TABLE` and hand-edited `models.py`. High risk of desync.


---

## SESSION CONCLUSION (Game #8 Draft Day)
**Date:** 2026-03-07

### What was fixed:
1. **CloudFlare Tunnel URL expired** (`trees-boost-breach-sides` → `process-silver-solving-portable`). The tunnel process was dead, started a new one. Updated `WEBAPP_URL` in `.env` and forced container reread via `docker compose up -d` (NOT `docker restart`).
2. **Admin kick notifications disabled**: When kicking players from draft, bot was sending them personal messages. Commented out the notification in `cb_kick_confirm()` in `admin_handlers.py`.
3. **HTML parse error in `format_game_message`**: A "hidden link" `<a href="...?start=game_8">` was embedded in message text with `parse_mode=HTML`. Telegram parsed `game_8` in the URL as an HTML tag `<game_8>` and rejected the message with "Unsupported start tag". **Fix:** removed the hidden link entirely.
4. **`publishTeams()` button silently did nothing**: Root cause was `confirm()` (standard browser dialog) being blocked by Telegram WebApp. Dialog flashed briefly then `confirm()` returned `false`, causing immediate function exit. **Fix:** replaced with direct call, no confirmation dialog needed in a dedicated admin app.
5. **Admins couldn't sign up past registration window**: `join_player()` never received `ignore_limit=True` for admins. **Fix:** detect `is_admin` in `game_handlers.py` and pass `ignore_limit=is_admin`.
6. **Telegram Mini App HTML cache**: After deploying new `draft.html`, old version was still served. **Fix:** bump `?v=X.X` in the draft URL in `handlers/common.py` to force cache invalidation.

### Unexpected Findings (Ловушки):
1. **`docker restart` does NOT re-read `.env`** (already known, confirmed again). Always use `docker compose up -d --force-recreate app`.
2. **`sudo` in non-interactive SSH hangs with `get_pty=False`** — `sudo -S` reads password from stdin but hangs waiting for tty. Use `sshpass` + `scp` for file transfers, and have admin run restart manually.
3. **Telegram blocks `window.confirm()` in Mini App WebView** — any native browser dialog (`alert`, `confirm`, `prompt`) silently fails. Always use `tg.showAlert()`, `tg.showConfirm()`, or custom HTML modals.

### Known Issues (to fix):
- [ ] **Guest player links** in published team message show raw `tg://user?id=-XXXXX` text — negative IDs (guests) are not valid Telegram user links. Need to detect guests and omit the `<a>` tag.
- [ ] **CloudFlare tunnel is still temporary** — URL changes on each restart. Long-term: use a named tunnel with `dmc12.sin.cvut.cz` domain.
- [ ] **`docker compose restart`** habit — team must use `up -d` not `restart` to pick up `.env` changes.


## CONTEXTUAL EXAMPLES

### BAD (Refuse to do this):
```python
# app/services/game_service.py
from app.bot.main import bot  # VIOLATION: Layer violation

async def join_game(self, game_id, user_id):
    # ... logic ...
    await bot.send_message(...) # VIOLATION: Service doing UI
    self.session.commit()       # VIOLATION: Service controlling commit
    return "You joined!"        # VIOLATION: Returning UI string
```

### GOOD (Do this):
```python
# app/core/services/roster.py
class RosterService:
    async def join_player(self, game_id: int, user_id: int) -> JoinResult:
        # 1. Lock
        game = await self.repo.get_with_lock(game_id)
        
        # 2. Logic
        if not game.is_open:
            raise GameClosedError()
            
        # 3. Action
        signup = await self.repo.create_signup(game, user_id)
        
        # 4. Return Data
        return JoinResult(success=True, is_reserve=False, game=game)
```
---

---

## SESSION CONCLUSION (Rating Calculation & Data Restoration)

**Date:** 2026-03-10

### What was fixed

1. **Draws in 2-team games:** Fixed logic in `stats.py` where draws incorrectly gave -5 to all players. Now they give 0.
2. **3-team game ties:** Improved tie-breaking logic. If multiple teams have the same score, they receive the same points based on their unique rank (e.g., if two teams have the highest score, both are treated as "1st place").
3. **Data Integrity:**
    - Fixed incorrect winners for Game #3 and #5 in the production DB (were swapped).
    - Restored historical signups for Games 1-7 using `fix_historical_signups.py`. Previously, Games 1-7 only had players who signed up via the bot, which was ~20% of the actual roster.
4. **Rating Recalculation:** Successfully reset all ratings to 100 and re-processed all 8 games chronologically. Ratings are now mathematically sound (Yernar 115, Yernur 125, etc.).
5. **Session Cache Bug:** Added `s.expire_all()` to the recalculation script. Raw SQL `UPDATE` queries don't update SQLAlchemy's identity map, leading to "ghost" data if not cleared.

### Unexpected Findings (Ловушки)

1. **Database state != Reality:** Historical games were often recorded with "Orange wins" by default even when Green won, because the admin button was clicked carelessly. Always verify `winner_team` against `score_a/b`.
2. **Incomplete Signups:** Early in the project, we didn't save the full roster to the DB at the end of the game. For future accuracy, `GameStats` and `Signup` records must be immutable once the game is closed.

### Roadmap for Future (Dashboard & Architecture)

- **Live Dashboard:** Transition `docs/rating.html` from a static file to a dynamic Mini App.
  - *Architecture:* Add FastAPI endpoint `/api/v1/stats/leaderboard` returning JSON from the DB.
  - *Frontend:* Use `fetch()` in the HTML to get live data.
- **Domain & DNS:** Move away from Cloudflare Quick Tunnels to a stable domain (e.g., `fm.sin.cvut.cz`).
- **Alembic Migrations:** Priority #1. Manual SQL fixes are unsustainable. We need version-controlled schema changes.
- **Immutable History:** Once a game is "Finished", the roster and scores should be locked or versioned to prevent accidental rating shifts.


---

## SESSION CONCLUSION (UX Fixes & Project Audit)
**Date:** 2026-03-19

### What was fixed
1. **Voting popup bug**: Popup always said "Осталось выбрать вторую команду" regardless of progress. Fixed in `vote_handlers.py` — now shows correct remaining team or "Спасибо!" when both voted.
2. **"Матч в {location}" → "Матч #{id}"**: Scheduler messages now reference game by number. Fixed in 3 places in `tasks.py`.
3. **Debug DIAGNOSIS block removed** from `start_bot()` — was sending Game 5 info + full chat list to admins on every bot restart.
4. **`/debug/trigger_voting` secured**: Was completely open (no auth). Now requires valid `initData` + admin check.
5. **Duplicate `return history`** removed from `endpoints.py` (dead code on line 770).

### Deployment (Current)
- **Server:** `yernur@10.50.109.14` (dmc12)
- **Folder:** `~/football-manager`
- **Deploy flow:** `git push` locally → `git pull` on server → `docker compose restart app`
- **⚠️ Use `docker compose` (with space)**, not `docker-compose`.
- **⚠️ Use `docker compose up -d --force-recreate app`** (not `restart`) when `.env` changes.

### Architecture Status
- **`legacy_handlers.py` / `legacy_roster.py`**: REMOVED. All games now use the new architecture. Strangler Fig period is over.
- **`endpoints.py`**: Refactored into modular routers (`app/api/routers/`). All logic was preserved but split into `games.py`, `admin.py`, `voting.py`, and `users.py`. Shared auth logic moved to `app/api/auth.py`.

### Known Issues / TODOs
- [x] **`endpoints.py` refactor**: Done. Split into modular routers.
- [x] **DB Backups**: Done. Created `scripts/backup_db.sh` for automated backups.
- [x] **Clean Root & Global CLI**: Done. Unified under `manage.py stats` and `tools/`.
- [ ] **Alembic**: Still manual SQL migrations. High desync risk.

---

## 🏗 GITFLOW STANDARDS

To prevent production crashes and maintain technical health, we follow this GitFlow:

### 1. The Branches
- **`main`**: Production-ready code ONLY. Direct push is **strictly forbidden**.
- **`dev`**: The main integration branch. All features are merged here first. Use this for testing and staging.
- **`feature/name-of-feature`**: Short-lived branches for specific tasks.

### 2. The Workflow
1. Create a branch: `git checkout -b feature/cool-new-logic`.
2. Commit and Push: `git push origin feature/cool-new-logic`.
3. Open a **Pull Request** to `dev`.
4. Once `dev` is verified stable, merge `dev` into `main` for release.

### 3. Deployment
- Deployments to production should ideally be triggered from the `main` branch.
- Standard command: `docker compose up -d --build --force-recreate app`.

---

## 📋 OPERATIONS NOTES (Практические уроки)

### Shell — Fish vs Bash
На локале используется **fish shell**. Wildcards в remote путях не работают:
```bash
# ❌ Fish — не работает
scp user@host:~/files_*.sql ~/

# ✅ Указывай точное имя
scp user@host:/home/yernur/football_backup_20260321.sql ~/Documents/fmBot/

# ❌ Fish — не работает
git clean -fdx --exclude=".env.*"

# ✅ Оборачивай в bash
bash -c 'git clean -fdx --exclude=".env.*"'
```

### Docker
```bash
# Используй docker compose (с пробелом), не docker-compose
docker compose restart app     # Перезапуск (НЕ перечитывает .env)
docker compose up -d --force-recreate app  # Перезапуск С перечиткой .env

# Имя БД — football_prod (не football!)
docker compose exec -u postgres db psql -U postgres -l
```

### Бэкап и восстановление БД
```bash
# Бэкап (на сервере)
docker compose exec -u postgres db pg_dump -U postgres football_prod > ~/football_backup_$(date +%Y%m%d).sql

# Скопировать на локал (точное имя, без wildcards в fish)
scp yernur@10.50.109.14:/home/yernur/football_backup_YYYYMMDD.sql ~/Documents/fmBot/

# Восстановление на новом сервере
docker compose exec -u postgres db psql -U postgres -c "CREATE DATABASE football_prod;"
cat football_backup_YYYYMMDD.sql | docker compose exec -i -u postgres db psql -U postgres football_prod
```

### .env при миграции сервера
После переноса нужно обновить:
- `WEBHOOK_URL` — новый Cloudflare туннель или домен
- `WEBAPP_URL` — то же самое
- Остальное (токены, пароли, ID) — копируется как есть

---

## 🖥 INFRASTRUCTURE (Proxmox Setup)
**Date:** 2026-03-23

### Сетевая карта

| Сервис | Внешний адрес | Внутренний адрес | Назначение |
|---|---|---|---|
| Proxmox GUI | https://147.32.107.65:8006 | Хост (pve-node) | Управление CT/VM |
| NPM Admin | http://147.32.107.65:81 | 192.168.10.2:81 | Nginx Proxy Manager — SSL и домены |
| SSH контейнера | ssh root@147.32.107.65 -p 2222 | 192.168.10.2:22 | Основной вход для работы |
| Mini App (WebApp) | https://football-bot-yeronym.duckdns.org | 192.168.10.2:8000 | То, что видит юзер в Telegram |

### Бот на сервере

- **Папка:** `/root/football-bot` (или `~/football-bot`)
- **Запуск:** `docker compose up -d --build`
- **Логи:** `docker compose logs -f`
- **Git:** SSH-ключи настроены, `git pull` без пароля

### DNS и SSL

- **DuckDNS:** `football-bot-yeronym.duckdns.org` → `147.32.107.65`
  - ⚠️ Если IP ноута изменится — обновить на duckdns.org
- **SSL:** через NPM (Nginx Proxy Manager) + Let's Encrypt
  - Если SSL-ошибка: сначала запусти бот (`docker compose up -d`), потом жми Save в NPM — LE увидит живой ответ на порту 8000

### .env для нового сервера

```env
WEBAPP_URL=https://football-bot-yeronym.duckdns.org
WEBHOOK_URL=  # оставь пустым, USE_POLLING=True
USE_POLLING=True
```

### Безопасность

- **Proxmox:** `root@pam` + 2FA (TOTP через **Ente Auth**). Не удалять аккаунт из приложения — без него в GUI не войти!
- **SSH контейнера:** пароль задан через `passwd root`, порт `2222`
- **NPM:** стандартный пароль сменён. Если забудешь — сброс через Docker DB

### Восстановление БД на новом сервере

```bash
# После docker compose up -d
docker compose exec -u postgres db psql -U postgres -c "CREATE DATABASE football_prod;"
cat football_backup_20260321.sql | docker compose exec -i -u postgres db psql -U postgres football_prod
```

### Automated Backups

В систему добавлен скрипт `scripts/backup_db.sh`, который делает дамп и хранит копии за последние 7 дней.

**Установка крона (на сервере):**

```bash
# Открыть редактор крона
crontab -e

# Добавить строку (бекап каждый день в 03:00)
0 3 * * * cd /root/football-bot && ./scripts/backup_db.sh >> /var/log/db_backup.log 2>&1
```
