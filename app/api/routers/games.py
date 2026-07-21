from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game, User, Signup, SignupStatus, Team, GameStatus
from app.api.auth import get_user_from_header
from app.config import settings

from app.core.services.cache import cache_service

router = APIRouter()

@router.get("/game/{game_id}")
async def get_game_details(
    game_id: int, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    cache_key = f"game_details:{game_id}"
    cached_data = await cache_service.get(cache_key)
    if cached_data:
        return cached_data

    result = await session.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    # Fetch players with Signup data and GameStats
    from app.db.models import GameStats
    result = await session.execute(
        select(User, Signup, GameStats)
        .join(Signup, User.user_id == Signup.user_id)
        .outerjoin(GameStats, (GameStats.game_id == game_id) & (GameStats.user_id == User.user_id))
        .where(Signup.game_id == game_id)
        .where(Signup.status.in_([SignupStatus.ACTIVE, SignupStatus.RESERVE]))
    )
    players_data = result.all()
    
    def serialize_player(p_tuple):
        user, signup, stats = p_tuple
        eff_pos = signup.position if signup.position else user.player_position
        
        return {
            "id": user.user_id,
            "signup_id": signup.id,
            "name": user.full_name,
            "rating": user.rating,
            "position": eff_pos.value if eff_pos else "DEF",
            "original_position": user.player_position.value if user.player_position else "DEF",
            "alt_positions": user.alt_positions or [],
            "status": signup.status.value,
            "is_paid": signup.is_paid,
            "goals": stats.goals if stats else 0,
            "is_mvp": stats.is_mvp if stats else False
        }
    
    team_a = [serialize_player(p) for p in players_data if p[1].team == Team.A]
    team_b = [serialize_player(p) for p in players_data if p[1].team == Team.B]
    team_c = [serialize_player(p) for p in players_data if p[1].team == Team.C]
    unassigned = [serialize_player(p) for p in players_data if not p[1].team and p[1].status == SignupStatus.ACTIVE]
    reserve = [serialize_player(p) for p in players_data if not p[1].team and p[1].status == SignupStatus.RESERVE]
    
    response_data = {
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
        "reserve": reserve, # Added separate reserve list
        "score_a": game.score_a,
        "score_b": game.score_b,
        "score_c": game.score_c,
        "status": game.status.value,
        "has_active_gk_a": game.has_active_gk_a,
        "has_active_gk_b": game.has_active_gk_b,
        "has_active_gk_c": getattr(game, 'has_active_gk_c', True)
    }
    
    await cache_service.set(cache_key, response_data, ttl=300)
    return response_data


@router.get("/history/{chat_id}")
async def get_chat_history(
    chat_id: int, 
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
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
        history.append({
            "game_id": game.id,
            "date": game.date_time.isoformat(),
            "location": game.location,
            "score_a": game.score_a if game.score_a is not None else 0,
            "score_b": game.score_b if game.score_b is not None else 0,
            "score_c": game.score_c if game.score_c is not None else 0,
            "team_count": game.team_count,
            "winner_team": game.winner_team.value if game.winner_team else None
        })
        
    return history

@router.get("/games/open")
@router.get("/games/editable")
async def get_editable_games(
    user_id: int = Depends(get_user_from_header), 
    session: AsyncSession = Depends(get_session)
):
    from app.api.auth import build_admin_games_query

    base_query = await build_admin_games_query(user_id, session)
    stmt = base_query.order_by(Game.date_time.desc()).limit(20)

    result = await session.execute(stmt)
    games = result.scalars().all()
    
    return [
        {
            "id": g.id,
            "location": g.location,
            "date_time": g.date_time.isoformat(),
            "status": g.status.value
        }
        for g in games
    ]



async def handle_player_left_bg(event_bus, event, promoted):
    if promoted:
        try:
            from app.bot.instance import bot
            await bot.send_message(
                promoted.user_id,
                "🎉 <b>Вас перевели в основной состав!</b>\nКто-то выписался из игры.",
                parse_mode="HTML"
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to notify promoted user in API leave: {e}")
    await event_bus.publish(event)


@router.post("/game/{game_id}/join")
async def join_game(
    game_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_user_from_header)
):
    from app.core.uow import UnitOfWork
    from app.core.services.roster import RosterService, PlayerJoinedEvent
    from app.core.events import event_bus
    import logging

    try:
        async with UnitOfWork() as uow:
            user = await uow.user_repo.get_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found. Please register first.")
            
            service = RosterService(uow)
            is_admin = user_id in settings.admin_ids or user_id == settings.system_owner_id
            result = await service.join_player(game_id, user, ignore_limit=is_admin)
            
            if not result.success:
                raise HTTPException(status_code=400, detail=result.message)
            
            alert_msg = result.message
            event_payload = None
            if result.signup:
                event_payload = PlayerJoinedEvent(
                    game_id=game_id,
                    user_id=user_id,
                    signup=result.signup,
                    is_reserve=result.is_reserve,
                    message=alert_msg
                )
            
            await uow.commit()
            
        if event_payload:
            background_tasks.add_task(event_bus.publish, event_payload)
            
        return {"success": True, "message": alert_msg, "is_reserve": result.is_reserve}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"API Join Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/game/{game_id}/leave")
async def leave_game(
    game_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_user_from_header)
):
    from app.core.uow import UnitOfWork
    from app.core.services.roster import RosterService, PlayerLeftEvent
    from app.core.events import event_bus
    import logging

    try:
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            is_admin = user_id in settings.admin_ids or user_id == settings.system_owner_id
            success, msg, promoted = await service.leave_player(game_id, user_id, is_admin)
            
            if not success:
                raise HTTPException(status_code=400, detail=msg)
                
            await uow.commit()
            
        background_tasks.add_task(handle_player_left_bg, event_bus, PlayerLeftEvent(game_id, user_id, msg, promoted), promoted)
        return {"success": True, "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"API Leave Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

