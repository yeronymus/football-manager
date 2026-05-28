## 2025-05-25 - Fix SQLAlchemy N^3 Cartesian Product Anti-Pattern in Game Queries
**Learning:** When using multiple `.outerjoin` calls on user-specific datasets (like Signup, GameStats, RatingHistory) against a core model like Game, placing the user-specific filter (e.g. `user_id == user_id`) in the `.where()` clause creates massive catastrophic Cartesian products before filtering.
**Action:** Always place user-specific filtering directly in the join condition (e.g. `.outerjoin(Model, (Model.game_id == Game.id) & (Model.user_id == user_id))`) rather than in a `.where()` clause when joining multiple related tables to a core model to drastically improve query performance.
## 2025-05-25 - Fix N+1 queries by replacing iterative permission checks with a single JOIN
**Learning:** Checking permissions inside a loop by making a separate database query for each item (N+1 query problem) scales poorly.
**Action:** Use a single database JOIN against the permissions table (`ChatAdmin`) when filtering large lists instead of validating permissions per item in Python.
