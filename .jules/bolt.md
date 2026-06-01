## 2025-05-25 - Fix SQLAlchemy N^3 Cartesian Product Anti-Pattern in Game Queries
**Learning:** When using multiple `.outerjoin` calls on user-specific datasets (like Signup, GameStats, RatingHistory) against a core model like Game, placing the user-specific filter (e.g. `user_id == user_id`) in the `.where()` clause creates massive catastrophic Cartesian products before filtering.
**Action:** Always place user-specific filtering directly in the join condition (e.g. `.outerjoin(Model, (Model.game_id == Game.id) & (Model.user_id == user_id))`) rather than in a `.where()` clause when joining multiple related tables to a core model to drastically improve query performance.

## 2023-10-27 - Fix N+1 Query in Game Editing Permissions
**Learning:** Calling authorization functions like `check_admin_rights` within a loop after fetching multiple rows creates a severe N+1 query bottleneck. It also leads to a subtle logical bug when used alongside `.limit()` since it fetches the most recent global items and then filters them out, potentially returning an empty list.
**Action:** Push authorization checks to the database level. Encapsulate the permission logic in a query builder function (like `build_admin_games_query` in the `auth` module) and apply filters *before* limiting the result set.
