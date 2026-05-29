## 2025-05-25 - Fix SQLAlchemy N^3 Cartesian Product Anti-Pattern in Game Queries
**Learning:** When using multiple `.outerjoin` calls on user-specific datasets (like Signup, GameStats, RatingHistory) against a core model like Game, placing the user-specific filter (e.g. `user_id == user_id`) in the `.where()` clause creates massive catastrophic Cartesian products before filtering.
**Action:** Always place user-specific filtering directly in the join condition (e.g. `.outerjoin(Model, (Model.game_id == Game.id) & (Model.user_id == user_id))`) rather than in a `.where()` clause when joining multiple related tables to a core model to drastically improve query performance.
## 2025-05-25 - Missing Indexes on Association Tables
**Learning:** Relational tables tracking history and statistics (`RatingHistory`, `GameStats`, `Vote`) were lacking indexes on foreign key columns (`game_id`, `user_id`), causing sequential scans during lookups.
**Action:** Ensure frequently queried `ForeignKey` fields are explicitly declared with `index=True` in SQLAlchemy models to improve JOIN performance.

## 2025-05-25 - Avoid N+1 permission checks
**Learning:** Checking permissions like `check_admin_rights` iteratively inside loops (like `get_editable_games`) creates classic N+1 query bottlenecks.
**Action:** Lift the user's role logic outside the loop, determine if they're a superadmin via one query, and rewrite the data query to perform a single JOIN on tables like `ChatAdmin` filtering by `user_id` when the user is restricted.
