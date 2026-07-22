import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_, func, distinct
from app.db.database import get_session
from app.db.models import Chat, User, PlayerProfile, Game, RatingHistory, Signup, GameStatus, GameStats
from app.api.auth import get_user_from_header
from app.core.repositories.user_repository import UserRepository
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/chat/{chat_id}/admins")
async def get_chat_admins(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    
    try:
        from app.bot.instance import bot
        admins = await bot.get_chat_administrators(chat_id)
        
        # Batch-fetch User records to prevent individual N+1 lazy loading
        admin_user_ids = [a.user.id for a in admins if not a.user.is_bot]
        users_map = {}
        if admin_user_ids:
            res = await session.execute(select(User).where(User.user_id.in_(admin_user_ids)))
            users_map = {u.user_id: u for u in res.scalars().all()}
            
        result = []
        for a in admins:
            if not a.user.is_bot:
                # Fallback to telegram details if user profile not found in db
                db_user = users_map.get(a.user.id)
                first_name = db_user.full_name if db_user else a.user.first_name
                username = db_user.username if db_user else a.user.username
                result.append({
                    "id": a.user.id,
                    "first_name": first_name,
                    "username": username
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
    """Returns active chats for the Mini-App ordered by activity."""
    from app.db.models import Game
    
    # Subquery to count games per chat
    games_sub = (
        select(Game.chat_id, func.count(Game.id).label("game_count"))
        .group_by(Game.chat_id)
    ).subquery()

    result = await session.execute(
        select(Chat)
        .outerjoin(games_sub, Chat.chat_id == games_sub.c.chat_id)
        .where(Chat.chat_id != -1000000000001)
        .where(~Chat.title.ilike('%unknown%'))
        .order_by(desc(func.coalesce(games_sub.c.game_count, 0)), Chat.chat_id.desc())
    )
    chats = result.scalars().all()
    
    return [
        {
            "id": c.chat_id, 
            "title": c.title,
            "type": c.chat_type,
            "is_active": c.is_active
        }
        for c in chats
    ]

@router.get("/users/search")
async def search_users(
    query: str, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
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

def _resolve_chat_ids(chat_id: int) -> list[int]:
    """Resolves chat_id variations including legacy positive IDs."""
    chat_id_str = str(chat_id)
    alt_chat_id = int(chat_id_str.replace("-100", "-")) if "-100" in chat_id_str else int("-100" + chat_id_str.replace("-", ""))
    return list(set([chat_id, alt_chat_id, abs(chat_id), abs(alt_chat_id)]))

async def _fetch_profile_summary(session: AsyncSession, user_id: int, chat_ids: list[int]):
    """Fetches rating, games played count, MVP count, and total goals for a profile."""
    profile = await session.scalar(
        select(PlayerProfile)
        .where(PlayerProfile.user_id == user_id, PlayerProfile.chat_id.in_(chat_ids))
    )
    
    # Calculate games played directly from signups for accuracy across legacy records
    from app.db.models import GameStats, Game, SignupStatus
    games_count_res = await session.scalar(
        select(func.count(func.distinct(Game.id)))
        .join(Signup, Signup.game_id == Game.id)
        .where(
            Signup.user_id == user_id,
            Game.chat_id.in_(chat_ids),
            Signup.status.in_([SignupStatus.ACTIVE, SignupStatus.RESERVE])
        )
    )
    games_played = games_count_res if games_count_res and games_count_res > 0 else (profile.games_played if profile else 0)
    
    # Calculate total goals in this chat
    total_goals = await session.scalar(
        select(func.sum(GameStats.goals))
        .join(Game, Game.id == GameStats.game_id)
        .where(GameStats.user_id == user_id, Game.chat_id.in_(chat_ids))
    )
    
    mvps = profile.stats_mvp if profile else 0
    rating = profile.rating if profile else 100
    
    return rating, games_played, mvps, int(total_goals or 0)

@router.get("/users/me/profile")
async def get_my_profile(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    chat_ids = _resolve_chat_ids(chat_id)
    user = await session.get(User, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    rating, games_played, mvps, total_goals = await _fetch_profile_summary(session, user_id, chat_ids)

    return {
        "user_id": user.user_id,
        "name": user.full_name,
        "position": user.player_position.value if user.player_position else "DEF",
        "alt_positions": user.alt_positions or [],
        "rating": rating,
        "games_played": games_played,
        "mvp_count": mvps,
        "total_goals": total_goals
    }

@router.get("/chats/{chat_id}/leaderboard")
async def get_leaderboard(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    """Returns top players in the group for the Mini-App with goals."""
    from app.db.models import GameStats, Game

    chat_ids = _resolve_chat_ids(chat_id)

    # Subquery to count total goals per user in this chat
    goals_sub = (
        select(GameStats.user_id, func.sum(GameStats.goals).label("total_goals"))
        .join(Game, Game.id == GameStats.game_id)
        .where(Game.chat_id.in_(chat_ids))
        .group_by(GameStats.user_id)
    ).subquery()

    profiles = await session.execute(
        select(PlayerProfile, goals_sub.c.total_goals, User)
        .join(User, User.user_id == PlayerProfile.user_id)
        .outerjoin(goals_sub, PlayerProfile.user_id == goals_sub.c.user_id)
        .where(PlayerProfile.chat_id.in_(chat_ids))
        .order_by(
            desc(PlayerProfile.rating),
            desc(PlayerProfile.games_played),
            desc(func.coalesce(goals_sub.c.total_goals, 0)),
            User.full_name.asc()
        )
        .limit(100)
    )
    
    result = []
    for p, goals, user in profiles.all():
        if user:
            result.append({
                "user_id": user.user_id,
                "name": user.full_name,
                "rating": p.rating,
                "games": p.games_played,
                "goals": int(goals or 0)
            })
    return result

@router.post("/users/me/profile")
async def update_my_profile(
    data: dict,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    """Updates user's primary position."""
    from app.db.models import Position
    new_pos = data.get("position")
    alt_positions = data.get("alt_positions", [])
    
    if not new_pos:
        raise HTTPException(status_code=400, detail="Position required")
    
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        user.player_position = Position(new_pos)
        user.alt_positions = alt_positions
        await session.commit()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid position")
        
    return {"status": "ok"}

@router.post("/users/register")
async def register_user(
    data: dict,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    """Registers a new user and creates an initial profile if chat_id provided."""
    from app.db.models import Position
    name = data.get("name")
    pos = data.get("position")
    chat_id = data.get("chat_id")
    alt_positions = data.get("alt_positions", [])
    
    if not name or not pos:
        raise HTTPException(status_code=400, detail="Name and position are required")
        
    user = await session.get(User, user_id)
    if not user:
        user = User(
            user_id=user_id,
            full_name=name,
            player_position=Position(pos),
            alt_positions=alt_positions,
            rating=100
        )
        session.add(user)
    else:
        user.full_name = name
        user.player_position = Position(pos)
        user.alt_positions = alt_positions
        
    # If chat_id is provided, create a profile for that chat immediately
    if chat_id:
        try:
            resolved_cids = _resolve_chat_ids(int(chat_id))
            chat_stmt = select(Chat).where(Chat.chat_id.in_(resolved_cids))
            chat = await session.scalar(chat_stmt)
            target_chat_id = chat.chat_id if chat else int(chat_id)
            
            stmt = select(PlayerProfile).where(
                PlayerProfile.user_id == user_id, 
                PlayerProfile.chat_id == target_chat_id
            )
            profile = await session.scalar(stmt)
            if not profile:
                profile = PlayerProfile(user_id=user_id, chat_id=target_chat_id, rating=100)
                session.add(profile)
        except Exception as ex:
            logger.warning(f"Failed to create initial profile during registration: {ex}")

    await session.commit()
    return {"status": "ok", "user_id": user_id}

async def _fetch_history_details(session: AsyncSession, game_ids: list[int], user_id: int):
    """Pre-fetches signups, stats, and ELO history maps to prevent N+1 queries."""
    signups_map = {}
    gamestats_map = {}
    history_map = {}
    if game_ids:
        s_res = await session.execute(select(Signup).where(Signup.game_id.in_(game_ids), Signup.user_id == user_id))
        signups_map = {s.game_id: s for s in s_res.scalars().all()}
        
        gs_res = await session.execute(select(GameStats).where(GameStats.game_id.in_(game_ids), GameStats.user_id == user_id))
        gamestats_map = {gs.game_id: gs for gs in gs_res.scalars().all()}
        
        rh_res = await session.execute(select(RatingHistory).where(RatingHistory.game_id.in_(game_ids), RatingHistory.user_id == user_id))
        history_map = {rh.game_id: rh for rh in rh_res.scalars().all()}
    return signups_map, gamestats_map, history_map

def _format_game_history(games, signups_map, history_map) -> list[dict]:
    """Formats games list with user's specific performance details."""
    result = []
    for game in games:
        s = signups_map.get(game.id)
        my_team = s.team.value if s and s.team else None
        history_record = history_map.get(game.id)
        
        result.append({
            "game_id": game.id,
            "date": game.date_time.isoformat(),
            "location": game.location,
            "score_a": game.score_a,
            "score_b": game.score_b,
            "score_c": game.score_c,
            "team_count": game.team_count,
            "my_team": my_team,
            "winner_team": game.winner_team.value if game.winner_team else None,
            "rating_change": history_record.change if history_record else 0
        })
    return result

@router.get("/users/me/history")
async def get_my_history(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    chat_ids = _resolve_chat_ids(chat_id)
    from sqlalchemy.orm import selectinload
    
    games_res = await session.execute(
        select(Game)
        .outerjoin(Chat, Game.chat_id == Chat.chat_id)
        .outerjoin(Signup, (Signup.game_id == Game.id) & (Signup.user_id == user_id))
        .outerjoin(GameStats, (GameStats.game_id == Game.id) & (GameStats.user_id == user_id))
        .outerjoin(RatingHistory, (RatingHistory.game_id == Game.id) & (RatingHistory.user_id == user_id))
        .options(selectinload(Game.chat))
        .where(
            or_(
                Signup.id.isnot(None),
                GameStats.id.isnot(None),
                RatingHistory.id.isnot(None)
            ),
            or_(
                Game.status == GameStatus.FINISHED,
                Game.score_a.isnot(None)
            )
        )
        .distinct()
        .order_by(desc(Game.date_time))
    )
    
    games = games_res.scalars().all()
    game_ids = [game.id for game in games]
    signups_map, gamestats_map, history_map = await _fetch_history_details(session, game_ids, user_id)
    return _format_game_history(games, signups_map, history_map)

