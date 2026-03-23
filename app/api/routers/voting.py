import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Signup, SignupStatus, Team, Vote, User
from app.api.auth import validate_init_data, get_user_from_init_data
from app.api.schemas import VoteRequest
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/game/{game_id}/vote_data")
async def get_vote_data(game_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    
    result = await session.execute(
         select(Signup).where(
             Signup.game_id == game_id, 
             Signup.user_id == user_id, 
             Signup.status == SignupStatus.ACTIVE
         )
    )
    if not result.scalar_one_or_none():
         raise HTTPException(status_code=403, detail="Only active players can vote")

    result = await session.execute(
        select(User, Signup)
        .join(Signup)
        .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
    )
    all_players = result.all()
    
    team_a = [
        {"id": u.user_id, "name": u.full_name, "position": s.position.value if s.position else u.player_position.value}
        for u, s in all_players if s.team == Team.A
    ]
    team_b = [
        {"id": u.user_id, "name": u.full_name, "position": s.position.value if s.position else u.player_position.value}
        for u, s in all_players if s.team == Team.B
    ]
    
    result = await session.execute(
        select(Vote).where(Vote.game_id == game_id, Vote.voter_id == user_id)
    )
    existing_votes = result.scalars().all()
    has_voted = len(existing_votes) > 0
    
    return {
        "team_a": team_a,
        "team_b": team_b,
        "has_voted": has_voted
    }

@router.post("/game/vote")
async def submit_vote(data: VoteRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(
        select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == user_id, Signup.status == SignupStatus.ACTIVE)
    )
    if not result.scalar_one_or_none():
         raise HTTPException(status_code=403, detail="Only active players can vote")
         
    result = await session.execute(
        select(Vote).where(Vote.game_id == data.game_id, Vote.voter_id == user_id)
    )
    votes = result.scalars().all()
    if votes:
        raise HTTPException(status_code=400, detail="Already voted")
        
    if data.mvp_team_a == user_id or data.mvp_team_b == user_id:
        raise HTTPException(status_code=400, detail="You cannot vote for yourself")
        
    vote_a = Vote(game_id=data.game_id, voter_id=user_id, target_id=data.mvp_team_a, vote_team=Team.A)
    vote_b = Vote(game_id=data.game_id, voter_id=user_id, target_id=data.mvp_team_b, vote_team=Team.B)
    
    session.add(vote_a)
    session.add(vote_b)
    
    try:
        await session.commit()
    except Exception as e:
        logger.error(f"Vote error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save vote")
        
    return {"status": "ok"}
