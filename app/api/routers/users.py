import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Chat, User
from app.api.auth import validate_init_data, get_user_from_init_data, get_user_from_header
from app.core.repositories.user_repository import UserRepository
from app.db.models import PlayerProfile, Game, RatingHistory, Signup, GameStatus
from sqlalchemy import desc

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/chat/{chat_id}/admins")
async def get_chat_admins(chat_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    try:
        from app.bot.instance import bot
        admins = await bot.get_chat_administrators(chat_id)
        result = []
        for a in admins:
            if not a.user.is_bot:
                result.append({
                    "id": a.user.id,
                    "first_name": a.user.first_name,
                    "username": a.user.username
                })
        return result
    except Exception as e:
        logger.error(f"Failed to fetch admins: {e}")
        raise HTTPException(status_code=400, detail="Failed to fetch admins")

@router.get("/chats")
async def get_chats(
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    """Returns chats where the user has a PlayerProfile."""
    result = await session.execute(
        select(Chat)
        .join(PlayerProfile, Chat.chat_id == PlayerProfile.chat_id)
        .where(PlayerProfile.user_id == user_id)
    )
    chats = result.scalars().all()
    
    return [
        {"id": c.chat_id, "title": c.title} 
        for c in chats
    ]

@router.get("/users/search")
async def search_users(query: str, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    logger.info(f"Searching users: query='{query}', user_id={user_id}")
    user_repo = UserRepository(session)
    users = await user_repo.search_users(query)
    
    return [
        {
            "id": u.user_id,
            "name": u.full_name,
            "username": u.username,
            "position": u.player_position.value if u.player_position else "DEF"
        }
        for u in users
    ]

@router.get("/users/me/profile")
async def get_my_profile(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    """Returns player profile for the specific chat/group for the Mini-App."""
    profile = await session.scalar(
        select(PlayerProfile)
        .where(PlayerProfile.user_id == user_id, PlayerProfile.chat_id == chat_id)
    )
    user = await session.get(User, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    rating = profile.rating if profile else 100
    games_played = profile.games_played if profile else 0
    mvps = profile.stats_mvp if profile else 0
    
    # Get last 10 rating changes for graph
    history = await session.scalars(
        select(RatingHistory)
        .where(RatingHistory.user_id == user_id) # Should filter by chat_id too, but RatingHistory only has game_id
        .join(Game, Game.id == RatingHistory.game_id)
        .where(Game.chat_id == chat_id)
        .order_by(desc(RatingHistory.date))
        .limit(10)
    )
    
    graph_data = [{"date": h.date.isoformat(), "rating": h.new_rating} for h in reversed(list(history))]
    
    return {
        "user_id": user.user_id,
        "name": user.full_name,
        "position": user.player_position.value,
        "rating": rating,
        "games_played": games_played,
        "mvp_count": mvps,
        "graph": graph_data
    }

@router.get("/chats/{chat_id}/leaderboard")
async def get_leaderboard(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    """Returns top players in the group for the Mini-App."""
    profiles = await session.scalars(
        select(PlayerProfile)
        .where(PlayerProfile.chat_id == chat_id)
        .order_by(desc(PlayerProfile.rating))
        .limit(50)
    )
    
    result = []
    for p in profiles:
        user = await session.get(User, p.user_id)
        if user:
            result.append({
                "user_id": user.user_id,
                "name": user.full_name,
                "rating": p.rating,
                "games": p.games_played
            })
    return result

@router.get("/users/me/history")
async def get_my_history(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    """Returns past matches for the Mini-App."""
    signups = await session.scalars(
        select(Signup)
        .join(Game)
        .where(Signup.user_id == user_id, Game.chat_id == chat_id, Game.status == GameStatus.FINISHED)
        .order_by(desc(Game.date_time))
        .limit(10)
    )
    
    result = []
    for s in signups:
        game = await session.get(Game, s.game_id)
        history_record = await session.scalar(
            select(RatingHistory)
            .where(RatingHistory.game_id == game.id, RatingHistory.user_id == user_id)
        )
        
        result.append({
            "game_id": game.id,
            "date": game.date_time.isoformat(),
            "score_a": game.score_a,
            "score_b": game.score_b,
            "my_team": s.team.value if s.team else None,
            "winner_team": game.winner_team.value if game.winner_team else None,
            "rating_change": history_record.change if history_record else 0
        })
    return result

