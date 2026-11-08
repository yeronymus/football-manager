from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.base import BaseRepository
from app.db.models import Game, GameStats, Signup, SignupStatus


class StatsRepository(BaseRepository[GameStats]):
    """
    Repository for player match statistics (`GameStats`), late arrival counts, and match history queries.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, GameStats)

    async def get_user_group_goals(self, chat_id: int, user_id: int) -> int:
        res = await self.session.scalar(
            select(func.coalesce(func.sum(GameStats.goals), 0))
            .join(Game, Game.id == GameStats.game_id)
            .where(Game.chat_id == chat_id, GameStats.user_id == user_id)
        )
        return int(res or 0)

    async def get_user_group_lates(self, chat_id: int, user_id: int) -> int:
        res = await self.session.scalar(
            select(func.count(Signup.id))
            .join(Game, Game.id == Signup.game_id)
            .where(
                Game.chat_id == chat_id,
                Signup.user_id == user_id,
                Signup.status == SignupStatus.ACTIVE,
                Signup.is_late == True,  # noqa: E712
            )
        )
        return int(res or 0)

    async def get_recent_matches_for_user(
        self, chat_id: int, user_id: int, limit: int = 10
    ) -> List[Tuple[Game, Optional[GameStats], Signup]]:
        stmt = (
            select(Game, GameStats, Signup)
            .join(Signup, (Signup.game_id == Game.id) & (Signup.user_id == user_id))
            .outerjoin(
                GameStats,
                (GameStats.game_id == Game.id) & (GameStats.user_id == user_id),
            )
            .where(Game.chat_id == chat_id, Signup.status == SignupStatus.ACTIVE)
            .order_by(Game.date_time.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.all())
