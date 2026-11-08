from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.base import BaseRepository
from app.db.models import GameStats, Signup, SignupStatus, User


class SignupRepository(BaseRepository[Signup]):
    """
    Repository for match registration (`Signup`) persistence, roster queries, and payment status tracking.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, Signup)

    async def get_by_game_and_user(self, game_id: int, user_id: int) -> Optional[Signup]:
        result = await self.session.execute(
            select(Signup).where(Signup.game_id == game_id, Signup.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_game_with_users_and_stats(
        self, game_id: int
    ) -> List[Tuple[Signup, User, Optional[GameStats]]]:
        stmt = (
            select(Signup, User, GameStats)
            .join(User, User.user_id == Signup.user_id)
            .outerjoin(
                GameStats,
                (GameStats.game_id == Signup.game_id) & (GameStats.user_id == Signup.user_id),
            )
            .where(Signup.game_id == game_id)
            .order_by(Signup.created_at)
        )
        res = await self.session.execute(stmt)
        return list(res.all())

    async def list_unpaid_active(self, game_id: int) -> List[Tuple[Signup, User]]:
        stmt = (
            select(Signup, User)
            .join(User, User.user_id == Signup.user_id)
            .where(
                Signup.game_id == game_id,
                Signup.status == SignupStatus.ACTIVE,
                Signup.is_paid == False,  # noqa: E712
            )
            .order_by(Signup.created_at)
        )
        res = await self.session.execute(stmt)
        return list(res.all())
