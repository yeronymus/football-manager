## 2025-05-25 - Fix SQLAlchemy N^3 Cartesian Product Anti-Pattern in Game Queries
**Learning:** When using multiple `.outerjoin` calls on user-specific datasets (like Signup, GameStats, RatingHistory) against a core model like Game, placing the user-specific filter (e.g. `user_id == user_id`) in the `.where()` clause creates massive catastrophic Cartesian products before filtering.
**Action:** Always place user-specific filtering directly in the join condition (e.g. `.outerjoin(Model, (Model.game_id == Game.id) & (Model.user_id == user_id))`) rather than in a `.where()` clause when joining multiple related tables to a core model to drastically improve query performance.

## 2025-06-01 - Avoid N+1 Queries in Route Handlers using Iterative Permission Checks
**Learning:** Iteratively querying games then sequentially calling `await check_admin_rights(game.chat_id, user_id)` within a loop results in critical N+1 queries. It triggers independent database connections/queries for `ChatAdmin` tables per loop iteration.
**Action:** Any authorization-related database logic involving multiple entities must be resolved in an SQL JOIN and encapsulated as a helper function (e.g., `build_admin_games_query` in `app/api/auth.py`) to execute a single query without leaking the domain auth logic into the router endpoint.
