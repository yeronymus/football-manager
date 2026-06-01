import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_, func, distinct
from app.db.database import get_session
from app.db.models import Chat, User, PlayerProfile, Game, RatingHistory, Signup, GameStatus, GameStats
from app.api.auth import get_user_from_header
from app.core.repositories.user_repository import UserRepository

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
        {
            "id": c.chat_id, 
            "title": c.title,
            "is_active": getattr(c, 'is_active', True) if getattr(c, 'is_active', True) is not None else True,
            "language": getattr(c, 'language', 'ru') if getattr(c, 'language', 'ru') else 'ru',
            "default_location": c.default_location,
            "default_price": c.default_price,
            "default_team_count": c.default_team_count,
            "default_max_players": c.default_max_players,
            "default_main_players_count": c.default_main_players_count,
            "default_duration": c.default_duration,
            "default_gk_hours": c.default_gk_hours,
            "default_registration_hours": c.default_registration_hours,
            "default_signup_limit": c.default_signup_limit,
            "payment_info": c.payment_info
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

@router.get("/users/me/profile")
async def get_my_profile(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    # Handle Telegram supergroup ID migration (-100 prefix) and potential legacy positive IDs
    chat_id_str = str(chat_id)
    alt_chat_id = int(chat_id_str.replace("-100", "-")) if "-100" in chat_id_str else int("-100" + chat_id_str.replace("-", ""))
    chat_ids = list(set([chat_id, alt_chat_id, abs(chat_id), abs(alt_chat_id)]))

    profile = await session.scalar(
        select(PlayerProfile)
        .where(PlayerProfile.user_id == user_id, PlayerProfile.chat_id.in_(chat_ids))
    )
    user = await session.get(User, user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # ⚡ Bolt Optimization:
    # Moved `user_id` filters from `.where()` into the `.outerjoin()` ON clauses.
    # Why: Previously, outer joining generically by game_id resulted in a Cartesian product
    # of all signups/stats for a game before filtering, causing severe performance degradation.
    # Impact: Reduces query time significantly and minimizes DB load.
    games_count = await session.scalar(
        select(func.count(distinct(Game.id)))
        .outerjoin(Signup, (Signup.game_id == Game.id) & (Signup.user_id == user_id))
        .outerjoin(GameStats, (GameStats.game_id == Game.id) & (GameStats.user_id == user_id))
        .outerjoin(RatingHistory, (RatingHistory.game_id == Game.id) & (RatingHistory.user_id == user_id))
        .where(
            Game.chat_id.in_(chat_ids),
            or_(
                Signup.id.isnot(None),
                GameStats.id.isnot(None),
                RatingHistory.id.isnot(None)
            ),
            or_(
                Game.status == GameStatus.FINISHED,
                Game.score_a.isnot(None)  # Any game with a score should probably count for history
            )
        )
    )
    
    rating = profile.rating if profile else 100
    games_played = games_count or 0
    mvps = profile.stats_mvp if profile else 0
    
    # Get last 10 rating changes for graph (legacy but keeping for logic)
    history = await session.scalars(
        select(RatingHistory)
        .join(Game, Game.id == RatingHistory.game_id)
        .where(RatingHistory.user_id == user_id, Game.chat_id.in_(chat_ids))
        .order_by(desc(RatingHistory.date))
        .limit(10)
    )
    
    # Total goals calculation
    total_goals = await session.scalar(
        select(func.sum(GameStats.goals))
        .join(Game, Game.id == GameStats.game_id)
        .where(GameStats.user_id == user_id, Game.chat_id.in_(chat_ids))
    )

    return {
        "user_id": user.user_id,
        "name": user.full_name,
        "position": user.player_position.value if user.player_position else "DEF",
        "alt_positions": user.alt_positions or [],
        "rating": rating,
        "games_played": games_played,
        "mvp_count": mvps,
        "total_goals": int(total_goals or 0)
    }

@router.get("/chats/{chat_id}/leaderboard")
async def get_leaderboard(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    """Returns top players in the group for the Mini-App with goals."""
    from sqlalchemy import func
    from app.db.models import GameStats, Game

    # Subquery to count total goals per user in this chat
    goals_sub = (
        select(GameStats.user_id, func.sum(GameStats.goals).label("total_goals"))
        .join(Game, Game.id == GameStats.game_id)
        .where(Game.chat_id == chat_id)
        .group_by(GameStats.user_id)
    ).subquery()

    profiles = await session.execute(
        select(PlayerProfile, goals_sub.c.total_goals, User)
        .join(User, User.user_id == PlayerProfile.user_id)
        .outerjoin(goals_sub, PlayerProfile.user_id == goals_sub.c.user_id)
        .where(PlayerProfile.chat_id == chat_id)
        .order_by(desc(PlayerProfile.rating))
        .limit(50)
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
        chat = await session.get(Chat, int(chat_id))
        if chat:
            stmt = select(PlayerProfile).where(
                PlayerProfile.user_id == user_id, 
                PlayerProfile.chat_id == chat.chat_id
            )
            profile = await session.scalar(stmt)
            if not profile:
                profile = PlayerProfile(user_id=user_id, chat_id=chat.chat_id, rating=100)
                session.add(profile)

    await session.commit()
    return {"status": "ok", "user_id": user_id}

@router.get("/users/me/history")
async def get_my_history(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    # Handle Telegram supergroup ID migration and potential legacy positive IDs
    chat_id_str = str(chat_id)
    alt_chat_id = int(chat_id_str.replace("-100", "-")) if "-100" in chat_id_str else int("-100" + chat_id_str.replace("-", ""))
    chat_ids = list(set([chat_id, alt_chat_id, abs(chat_id), abs(alt_chat_id)]))

    # Robust query: check Signups, GameStats AND RatingHistory.
    # If Signup was deleted, RatingHistory is the ultimate proof the user played.
    from sqlalchemy.orm import selectinload
    
    # ⚡ Bolt Optimization:
    # Moved `user_id` filters from `.where()` into the `.outerjoin()` ON clauses.
    # Why: Avoids Cartesian products from joining all users' data before filtering.
    # Impact: Massive reduction in intermediate rows and faster execution time.
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

    signups_map = {}
    gamestats_map = {}
    history_map = {}

    if game_ids:
        # Pre-fetch Signups
        s_res = await session.execute(
            select(Signup).where(Signup.game_id.in_(game_ids), Signup.user_id == user_id)
        )
        signups_map = {s.game_id: s for s in s_res.scalars().all()}

        # Pre-fetch GameStats
        gs_res = await session.execute(
            select(GameStats).where(GameStats.game_id.in_(game_ids), GameStats.user_id == user_id)
        )
        gamestats_map = {gs.game_id: gs for gs in gs_res.scalars().all()}

        # Pre-fetch RatingHistory
        rh_res = await session.execute(
            select(RatingHistory).where(RatingHistory.game_id.in_(game_ids), RatingHistory.user_id == user_id)
        )
        history_map = {rh.game_id: rh for rh in rh_res.scalars().all()}

    result = []
    for game in games:
        # We still need the signup to know which team the user was on
        s = signups_map.get(game.id)
        # If no signup, maybe check GameStats?
        if not s:
            gs = gamestats_map.get(game.id)
            my_team = gs.team.value if gs and gs.team else None
        else:
            my_team = s.team.value if s.team else None

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

