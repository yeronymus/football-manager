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
