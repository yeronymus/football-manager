# Migration Strategy: Strangler Fig Pattern

## Current State
The project is a legacy monolith (`app/services/game_service.py`) running in production.
We are migrating to a Modular Architecture (`app/core/`) side-by-side.

## Constraint Rules (CRITICAL)
1. **Shared Database**: Both legacy and new code MUST use `app/db/models.py`.
2. **No Breaking Schema Changes**: Do not rename columns used by legacy code. Only add new nullable columns.
3. **Implicit Coexistence**: The bot handlers will route requests to either LegacyService or NewService based on flags.
4. **Data Integrity**: New services must respect existing data constraints (e.g., `unique_signup`).

## Workflow for AI
1. When asked to refactor feature X:
   - Do NOT modify `app/services/game_service.py`.
   - Create a new service in `app/core/services/` or `app/core/domains/X/`.
   - Implement the logic using existing DB models.
   - Create an Adapter/Facade to call this service from the Bot Handler.
2. Verify that the new logic produces the exact same DB state as the old logic.

## Summary Table
| Component | Anti-Chaos Action | Risk |
| :--- | :--- | :--- |
| **Database** | Do not touch table structure. Use same `models.py`. | Low |
| **Logic Code** | Write new code in new folder. Mark old code Deprecated but DO NOT delete. | Low |
| **Bot (Handlers)** | Use `if/else` to route calls between old and new service. | Medium |
| **Scripts (`fix_*.py`)** | Leave as is. Refactor to CLI commands only after logic migrates. | Low |
| **Scheduler** | Configure JobStore in DB. | High (Risk of missing reminders) |
