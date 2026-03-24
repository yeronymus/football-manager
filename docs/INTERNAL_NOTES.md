# INTERNAL SESSION HISTORY & LESSONS LEARNED

This file contains the detailed "battle logs" and specific technical traps discovered during the development of Football Manager. Since `docs/` is `.gitignore`-d, this remains a local-only knowledge base.

---

## 🏗️ SESSION: Game #6 Recovery
- **What was fixed:** Manual DB migration applied, Bot performance optimized (SQL logging disabled), Registration window added (`registration_hours`).
- **Traps found:** 
    1. **I/O Wait:** The production server has extreme disk latency causing `rsync` and `scp` to hang or fail silently. 
    2. **Caching:** Telegram WebApp caches HTML forms aggressively; manual versioning in the footer/payload (`?v=1.x`) is needed to force updates.
- **Next steps:** investigate move to SSD. Implement version-based cache busting.

---

## 🏗️ SESSION: Server Migration (dmc12)
**Date:** 2026-03-04

### What was fixed:
1. **Server migration**: Old server (`yernur-vm1`) died. Migrated to `dmc12.sin.cvut.cz` (IP: `10.50.109.14`).
2. **`games_id_seq` desync**: PostgreSQL sequence was at 1 while `MAX(id)=7`. Fixed via `SELECT setval('games_id_seq', 7)`.
3. **Game type display bug**: `game.game_type` stored as raw string "draft" instead of Enum. Value access raised `AttributeError`, caught silently and defaulted to "Regular".
4. **Stats restoration**: 41/57 users matched and restored from CSV. Manual fixes for `Bekmolda Daulet` and others.

### Unexpected Findings (Ловушки):
1. **`docker compose restart` does NOT reload `.env`** — use `up -d --force-recreate`.
2. **`check_admin_rights` fails if bot is not admin** — `getChatMember` requires admin status. Use bypass for `admin_ids`.
3. **`rsync` missing on production server** — `deploy.sh` depends on it.

---

## 🏗️ SESSION: Game #8 Draft Day
**Date:** 2026-03-07

### What was fixed:
1. **CloudFlare Tunnel expiry**: URL changed (`trees-boost...` -> `process-silver...`). Updated `.env` and recreated app.
2. **HTML parse error in messages**: `<a href="...?start=game_8">` URL params parsed as HTML tags `<game_8>`. **Solution:** remove query params or use standard URLs.
3. **`window.confirm()` blocked**: Telegram WebApp blocks native browser dialogs. **Solution:** use `tg.showConfirm()` or custom modals.

### Known Issues:
- [ ] **Guest player links** (`tg://user?id=-XXXX`) are invalid. Need to filter negative IDs.

---

## 🏗️ SESSION: Rating & Data Restoration
**Date:** 2026-03-10

### What was fixed
1. **Draws in 2-team games:** Gave -5 incorrectly. Now 0.
2. **3-team game ties:** Implemented unique rank-based points (e.g., tie for 1st = both get 1st points).
3. **Data Integrity:** Swapped Game #3 and #5 results to match reality.
4. **Historical Signups:** Full roster restored for Games 1-7 (41 users).

---

## 🏗️ SESSION: Final Consolidation (Showcase Cleanup)
**Date:** 2026-03-24

### Major Refactoring
1. **CLI Unified**: All administrative tools moved to `manage.py`.
2. **Legacy Cleanup**: Deleted 20+ redundant scripts in `scripts/` and root.
3. **Alembic**: Proper migration track started (`8dd6e5c...`).
4. **Deploy**: CI/CD via GitHub Actions.

### Operational Wisdom
- Always check `setval` on sequences after manual ID imports.
- `docker compose` (with space) is the standard.
- `.env.example` must be kept updated for new clones.
- `docs/ARCHITECTURE.md` is the "Constitution", `INTERNAL_NOTES.md` is the "History".
