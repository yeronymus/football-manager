## 2024-05-24 - [Avoid Multiple Outerjoins on user specific datasets against a core model]
**Learning:** Using `.outerjoin()` directly with a general clause like `Signup.game_id == Game.id` without restricting by `user_id` inside the join clause creates catastrophic Cartesian products, particularly when followed by a `.where(Signup.user_id == user_id)` filter.
**Action:** Always include the specific constraints (like `& (Model.user_id == user_id)`) *inside* the `.outerjoin` condition instead of the `.where` clause for user-specific aggregations.
