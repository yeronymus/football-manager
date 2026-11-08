from typing import Any, Dict, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.repositories.base import BaseRepository
from app.db.models import Signup, User, Vote


class VoteRepository(BaseRepository[Vote]):
    """
    Repository for MVP ballot (`Vote`) persistence and aggregation.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, Vote)

    async def get_vote_counts_by_target(self, game_id: int) -> Dict[int, int]:
        res = await self.session.execute(
            select(Vote.target_id, func.count(Vote.id))
            .where(Vote.game_id == game_id)
            .group_by(Vote.target_id)
        )
        return {row[0]: int(row[1]) for row in res.all()}

    async def get_votes_summary_by_name(self, game_id: int) -> List[Tuple[str, int]]:
        res = await self.session.execute(
            select(User.full_name, func.count(Vote.id))
            .join(Vote, User.user_id == Vote.target_id)
            .where(Vote.game_id == game_id)
            .group_by(User.full_name)
            .order_by(func.count(Vote.id).desc())
        )
        return [(name, int(count)) for name, count in res.all()]

    async def list_detailed_votes(self, game_id: int) -> List[Tuple[Vote, str, str, Any]]:
        voter = aliased(User)
        target = aliased(User)
        voter_signup = aliased(Signup)

        stmt = (
            select(
                Vote,
                voter.full_name.label("voter_name"),
                target.full_name.label("target_name"),
                voter_signup.team.label("voter_team"),
            )
            .join(voter, voter.user_id == Vote.voter_id)
            .join(target, target.user_id == Vote.target_id)
            .outerjoin(
                voter_signup,
                (voter_signup.user_id == Vote.voter_id) & (voter_signup.game_id == game_id),
            )
            .where(Vote.game_id == game_id)
        )
        res = await self.session.execute(stmt)
        return list(res.all())
