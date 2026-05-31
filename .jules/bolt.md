## 2025-05-25 - Fix SQLAlchemy N^3 Cartesian Product Anti-Pattern in Game Queries
**Learning:** When using multiple `.outerjoin` calls on user-specific datasets (like Signup, GameStats, RatingHistory) against a core model like Game, placing the user-specific filter (e.g. `user_id == user_id`) in the `.where()` clause creates massive catastrophic Cartesian products before filtering.
**Action:** Always place user-specific filtering directly in the join condition (e.g. `.outerjoin(Model, (Model.game_id == Game.id) & (Model.user_id == user_id))`) rather than in a `.where()` clause when joining multiple related tables to a core model to drastically improve query performance.
## 2025-05-31 - Fix Iterative API Auth N+1 Query Bottleneck
**Learning:** Iterative API auth checks within loops (like `await check_admin_rights(g.chat_id, user_id)` for a list of games) create N+1 query bottlenecks that kill list endpoint performance.
**Action:** Encapsulate JOIN-based optimization helper methods within the `auth` module (e.g. `build_admin_games_query`) and use them to construct a single performant database query instead of looping over auth checks.
