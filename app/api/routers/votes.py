import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.core.repositories.vote_repository import VoteRepository
from app.db.database import get_session
from app.db.models import Game

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard-votes"])


def _dash():
    import app.api.routers.dashboard as dash_mod

    return dash_mod


class VoteDetailOut(BaseModel):
    voter_name: str
    voter_team: Optional[str]
    target_name: str
    vote_team: str


async def _get_game_votes_map(session: AsyncSession, game_id: int) -> dict[int, int]:
    """Helper to fetch voting results map target_id -> count."""
    repo = VoteRepository(session)
    return await repo.get_vote_counts_by_target(game_id)


@router.get("/games/{game_id}/votes/summary")
async def get_game_votes_summary(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, user_id)

    repo = VoteRepository(session)
    votes = await repo.get_votes_summary_by_name(game_id)
    return [{"name": name, "count": count} for name, count in votes]


@router.get("/games/{game_id}/votes", response_model=List[VoteDetailOut])
async def get_game_votes(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, user_id)

    repo = VoteRepository(session)
    rows = await repo.list_detailed_votes(game_id)

    return [
        VoteDetailOut(
            voter_name=voter_name,
            voter_team=voter_team.value if voter_team else None,
            target_name=target_name,
            vote_team=vote.vote_team.value,
        )
        for vote, voter_name, target_name, voter_team in rows
    ]


@router.post("/games/{game_id}/trigger_voting")
async def trigger_voting_dashboard(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, user_id, session=session)

    try:
        from app.scheduler.tasks import send_voting_message

        await send_voting_message(game_id)
        return {"status": "triggered", "game_id": game_id}
    except Exception as e:
        logger.error(f"Trigger voting dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
