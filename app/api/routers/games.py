from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game, User, Signup, SignupStatus, Team, GameStatus
from app.api.auth import validate_init_data, get_user_from_init_data, check_admin_rights
from app.config import settings

router = APIRouter()

@router.get("/game/{game_id}")
async def get_game_details(game_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    
    result = await session.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    # Fetch players with Signup data (In Draft mode, we need both ACTIVE and RESERVE)
    result = await session.execute(
        select(User, Signup)
        .join(Signup)
        .where(Signup.game_id == game_id)
        .where(Signup.status.in_([SignupStatus.ACTIVE, SignupStatus.RESERVE]))
    )
    players_data = result.all()
    
    def serialize_player(p_tuple):
        user, signup = p_tuple
        eff_pos = signup.position if signup.position else user.player_position
        
        return {
            "id": user.user_id,
            "name": user.full_name,
            "rating": user.rating,
            "position": eff_pos.value if eff_pos else "DEF",
            "original_position": user.player_position.value if user.player_position else "DEF",
            "alt_positions": user.alt_positions or []
        }
    
    team_a = [serialize_player(p) for p in players_data if p[1].team == Team.A]
    team_b = [serialize_player(p) for p in players_data if p[1].team == Team.B]
    team_c = [serialize_player(p) for p in players_data if p[1].team == Team.C]
    unassigned = [serialize_player(p) for p in players_data if not p[1].team]
    
    return {
        "id": game.id,
        "location": game.location,
        "date": game.date_time.isoformat(),
        "max_players": game.max_players,
        "price": game.price,
        "payment_info": game.payment_info,
        "team_count": game.team_count,
        "gk_hours": game.gk_hours,
        "registration_hours": getattr(game, 'registration_hours', 0),
        "main_players_count": getattr(game, 'main_players_count', 22),
        "signup_limit": getattr(game, 'signup_limit', 999),
        "chat_id": game.chat_id,
        "team_a": team_a,
        "team_b": team_b,
        "team_c": team_c,
        "unassigned": unassigned,
        "score_a": game.score_a,
        "score_b": game.score_b,
        "status": game.status.value,
        "has_active_gk_a": game.has_active_gk_a,
        "has_active_gk_b": game.has_active_gk_b,
        "has_active_gk_c": getattr(game, 'has_active_gk_c', True)
    }

@router.get("/history/{chat_id}")
async def get_chat_history(chat_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    
    from app.bot.instance import bot
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in ["left", "kicked"]:
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=400, detail="Chat access error")

    result = await session.execute(
        select(Game)
        .where(Game.chat_id == chat_id, Game.status == GameStatus.FINISHED)
        .order_by(Game.date_time.desc())
        .limit(50)
    )
    games = result.scalars().all()
    
    history = []
    for game in games:
        winner_text = "Ничья"
        if game.winner_team == Team.A:
            winner_text = "Победа А"
        elif game.winner_team == Team.B:
            winner_text = "Победа Б"
            
        history.append({
            "id": game.id,
            "date": game.date_time.strftime("%d.%m.%Y"),
            "location": game.location,
            "score_a": game.score_a if game.score_a is not None else 0,
            "score_b": game.score_b if game.score_b is not None else 0,
            "winner": winner_text
        })
        
    return history

@router.get("/games/editable")
async def get_editable_games(initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(initData)
    
    result = await session.execute(
        select(Game).order_by(Game.date_time.desc()).limit(20)
    )
    games = result.scalars().all()
    
    editable = []
    for g in games:
        try:
            await check_admin_rights(g.chat_id, user_id)
            editable.append({
                "id": g.id,
                "location": g.location,
                "date_time": g.date_time.isoformat(),
                "status": g.status.value
            })
        except:
            pass
            
    return editable
