# Architecture & Migration Summary (Handoff)

## 1. Context: Strangler Fig Transition
We are migrating from a monolithic legacy system to a **Modular Monolith** with a pure Domain Layer.

**Current State (COMPLETED):**
- **UnitOfWork (UoW)**: Implemented in `app/core/uow.py` to manage multi-repository transactions.
- **RosterService**: A pure domain service in `app/core/services/roster.py` (Stateless, Logic-only).
- **Repositories**: `GameRepository` and `UserRepository` created to isolate SQL.
- **Switchman (Router)**: Implemented in `app/bot/game_handlers.py`.
  - **Game ID <= 5**: Routes to `app/bot/legacy_handlers.py` (Legacy Code).
  - **Game ID > 5**: Routes to New Core (`UnitOfWork` + `RosterService`).
- **ID Correction**: Previous "Game 47" has been renumbered to **Game #5**. Sequence reset to 6.

## 2. The Project Constitution (Core Rules)
1. **Anti-Gravity Rule**: `app/core` (Business Logic) must **never** import from `app/bot` or `aiogram`.
2. **Transaction Boundary**: Services **never** call `.commit()`. Commits are managed only by the Controller layer (Handlers/CLI) using `uow.commit()`.
3. **Concurrency Safety**: All state changes start with `get_with_lock` (DB-level `SELECT ... FOR UPDATE`).
4. **No Raw SQL in UI**: Handlers must use Repositories via UoW, never manual `session.execute` for domain objects.

## 3. Component Responsibilities
- **Handlers (`app/bot/`)**: Pure Controllers. Accept input, call Services, handle UI side-effects (Events/Notifications).
- **UnitOfWork (`app/core/uow.py`)**: Transaction orchestrator. Houses repositories.
- **Services (`app/core/services/`)**: The "Brain". Knows business rules and domain logic.
- **Repositories (`app/core/repositories/`)**: The "Muscles". Knows SQL and data mapping.

## 4. Next Steps for Tomorrow
- **Monitor Game #5**: Ensure legacy logic continues to work for the current game.
- **Test Game #6**: Create a new game (ID will be 6) and verify it correctly triggers the New Core logic.
- **Expansion**: Continue migrating remaining logic (Stats calculation, ELO) into the new architecture.

---
*Signed, Antigravity (Senior Architect Mode)*
