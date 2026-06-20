import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import json
import urllib.parse
import time

from app.db.database import get_session
from app.db.models import Game, User, Signup, SignupStatus, GameStatus
from app.api.auth import validate_init_data, get_user_from_init_data, check_admin_rights
from app.api.schemas import GameCreate, BalanceTeams, GameFinishRequest, UpdateTeamsRequest, GameUpdate, AddPlayerRequest, AddGuestRequest
from app.core.repositories.user_repository import UserRepository
from app.config import settings
from app.core.events import (
    event_bus, GameStateChangedEvent, GameCreatedEvent, 
    GameFinishedEvent, GameUpdatedEvent, TeamsPublishedEvent
)
from app.core.domain.dto import CreateGameDTO, UpdateGameDTO, FinishGameDTO, PlayerStatDTO
from app.core.services.cache import cache_service

logger = logging.getLogger(__name__)
router = APIRouter()

def _interpret_prague_tz(dt):
    if dt and dt.tzinfo is None:
        try:
            import zoneinfo
            prague_tz = zoneinfo.ZoneInfo("Europe/Prague")
            return dt.replace(tzinfo=prague_tz)
        except ImportError:
            pass
    return dt

def _should_publish_game_now(game_datetime, publish_at) -> bool:
    from datetime import datetime
    tz = game_datetime.tzinfo
    now_tz = datetime.now(tz) if tz else datetime.now()
    
    if game_datetime < now_tz:
        return False
    if publish_at:
        pub_at = publish_at
        if pub_at.tzinfo is None and tz:
            pub_at = pub_at.replace(tzinfo=tz)
        if pub_at > now_tz:
            return False
    return True

async def _ensure_creator_exists(user_id: int, init_data: str, session: AsyncSession) -> User:
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    if not user:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        user_data = json.loads(parsed_data.get("user", "{}"))
        user = await user_repo.create_user(
            user_id=user_id, 
            full_name=user_data.get("first_name", "Admin"), 
            username=user_data.get("username"),
            position="CM" # Default
        )
        await session.commit()
    return user

@router.post("/create_game")
async def create_game(data: GameCreate, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    await check_admin_rights(data.chat_id, user_id, session=session)
    await _ensure_creator_exists(user_id, data.initData, session)

    game_dt = _interpret_prague_tz(data.date_time)
    publish_dt = _interpret_prague_tz(data.publish_at)

    try:
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.core.uow import UnitOfWork
        
        dto = CreateGameDTO(
            chat_id=data.chat_id,
            date_time=game_dt,
            location=data.location,
            max_players=data.max_players,
            price=data.price,
            payment_info=data.payment_info,
            team_count=data.team_count,
            gk_hours=data.gk_hours,
            duration=data.duration,
            registration_hours=data.registration_hours,
            game_type=data.game_type,
            auto_join_ids=data.auto_join_ids,
            publish_at=publish_dt,
            main_players_count=data.main_players_count,
            signup_limit=data.signup_limit,
        )

        async with UnitOfWork(session=session) as uow:
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            new_game = await lifecycle.create_game(dto, user_id)
            await uow.commit()

            should_publish_now = _should_publish_game_now(new_game.date_time, data.publish_at)

            background_tasks.add_task(event_bus.publish, GameCreatedEvent(
                game_id=new_game.id,
                chat_id=data.chat_id,
                creator_id=user_id,
                should_publish=should_publish_now,
                publish_at=data.publish_at,
            ))
            await cache_service.evict(f"game_details:{new_game.id}")
            return {"game_id": new_game.id, "status": "created"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create game error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/update_game")
async def update_game(data: GameUpdate, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id, session=session)
    
    # Interpret naive datetime from WebApp as Prague time
    game_dt = data.date_time
    if game_dt and game_dt.tzinfo is None:
        try:
            import zoneinfo
            prague_tz = zoneinfo.ZoneInfo("Europe/Prague")
            game_dt = game_dt.replace(tzinfo=prague_tz)
        except ImportError:
            pass

    try:
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.core.uow import UnitOfWork
        
        # Map Pydantic schema -> Domain DTO
        dto = UpdateGameDTO(
            game_id=data.game_id,
            location=data.location,
            date_time=game_dt,
            max_players=data.max_players,
            price=data.price,
            payment_info=data.payment_info,
            gk_hours=data.gk_hours,
            duration=data.duration,
            registration_hours=data.registration_hours,
            main_players_count=data.main_players_count,
            signup_limit=data.signup_limit,
        )

        updated_game = None
        changes = []
        async with UnitOfWork(session=session) as uow:
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            updated_game, changes = await lifecycle.update_game(dto)
            await uow.commit()

        # Delegate messaging to bot layer
        await cache_service.evict(f"game_details:{updated_game.id}")
        background_tasks.add_task(event_bus.publish, GameUpdatedEvent(game_id=updated_game.id, changes=changes))
        return {"status": "updated", "id": updated_game.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update game error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/balance_teams")
async def admin_balance_teams(data: BalanceTeams, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id, session=session)

    try:
        from app.core.services.roster import RosterService
        from app.core.uow import UnitOfWork
        
        async with UnitOfWork(session=session) as uow:
            service = RosterService(uow)
            await service.balance_teams(data.game_id)
            await uow.commit()

        await cache_service.evict(f"game_details:{data.game_id}")
        background_tasks.add_task(event_bus.publish, GameStateChangedEvent(game_id=data.game_id))
        return {"status": "balanced"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Balance error for game {data.game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Balance error: {str(e)}")

@router.post("/update_teams")
async def admin_update_teams(data: UpdateTeamsRequest, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    await check_admin_rights(game.chat_id, user_id, session=session)
    try:
        from app.core.services.roster import RosterService
        from app.core.uow import UnitOfWork
        
        promoted_ids = []
        async with UnitOfWork(session=session) as uow:
            service = RosterService(uow)
            promoted_ids = await service.update_teams(
                data.game_id, 
                data.team_a, 
                data.team_b, 
                data.team_c, 
                data.unassigned or [], 
                data.reserve or [], # Pass reserve
                data.positions or {}
            )
            await uow.commit()

        if promoted_ids:
            from app.bot.instance import bot as _bot
            import asyncio
            
            async def send_notify(uid):
                try:
                    await _bot.send_message(
                        uid,
                        "<b>Ты в основном составе!</b>\nАдмин перенес тебя из резерва. <b>Подтверди в группе или админам, что будешь играть!</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify promoted user {uid}: {e}")
            
            await asyncio.gather(*(send_notify(uid) for uid in promoted_ids))

        await cache_service.evict(f"game_details:{data.game_id}")
        background_tasks.add_task(event_bus.publish, GameStateChangedEvent(game_id=data.game_id))
        return {"status": "updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update teams error for game {data.game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update error: {str(e)}")

@router.post("/publish_teams")
async def admin_publish_teams(data: BalanceTeams, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id, session=session)
    
    is_update = True
    if game.status == GameStatus.OPEN:
        game.status = GameStatus.ACTIVE
        is_update = False
    elif game.status == GameStatus.CANCELLED:
        game.status = GameStatus.ACTIVE
        is_update = False

    await session.commit()

    # Delegate messaging to bot layer
    background_tasks.add_task(event_bus.publish, TeamsPublishedEvent(game_id=game.id))
    return {"status": "published"}

async def _get_voting_results(session: AsyncSession, game_id: int):
    """Helper to fetch top 5 MVP voting results for finished game."""
    from app.db.models import Vote
    res_v = await session.execute(
        select(User.full_name, func.count(Vote.id))
        .join(Vote, User.user_id == Vote.target_id)
        .where(Vote.game_id == game_id)
        .group_by(User.full_name)
        .order_by(func.count(Vote.id).desc())
        .limit(5)
    )
    return res_v.all()

async def _build_finish_announcement(session: AsyncSession, game, voting_results, data) -> str:
    """Helper to build HTML announcement message text for a finished game."""
    text = f"🏁 <b>Матч завершен!</b>\n\n"
    text += f"Команда оранжевые 🟠 {game.score_a}:{game.score_b} 🟢 Команда зеленые\n"
    
    async def get_names(uids):
        if not uids: return []
        res = await session.execute(select(User).where(User.user_id.in_(uids)))
        return [u.full_name for u in res.scalars().all()]

    mvp_ids = []
    if data.mvp_team_a: mvp_ids.append(data.mvp_team_a)
    if data.mvp_team_b: mvp_ids.append(data.mvp_team_b)
    
    if mvp_ids:
        mvp_names = await get_names(mvp_ids)
        if mvp_names:
            text += "🌟 <b>MVP:</b> " + ", ".join(mvp_names) + "\n"
    
    if voting_results:
        text += "\n⭐ <b>Голоса за MVP:</b>\n"
        text += "\n".join([f"- {name}: {count}" for name, count in voting_results]) + "\n"

    scorers = [p for p in data.player_stats if p.goals > 0]
    if scorers:
        text += "\n⚽ <b>Голы:</b>\n"
        scorer_ids = [s.user_id for s in scorers]
        res = await session.execute(select(User.user_id, User.full_name).where(User.user_id.in_(scorer_ids)))
        users_map = {uid: name for uid, name in res.all()}
        text += "\n".join([f"- {users_map.get(s.user_id, 'Неизвестный')}: {s.goals}" for s in scorers]) + "\n"
    return text

@router.post("/finish_game")
async def finish_game(data: GameFinishRequest, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id, session=session)

    try:
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.core.uow import UnitOfWork
        
        dto = FinishGameDTO(
            game_id=data.game_id,
            score_a=data.score_a,
            score_b=data.score_b,
            winner_team=data.winner_team,
            mvp_team_a=data.mvp_team_a,
            mvp_team_b=data.mvp_team_b,
            player_stats=[PlayerStatDTO(user_id=p.user_id, goals=p.goals) for p in data.player_stats],
        )

        async with UnitOfWork(session=session) as uow:
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            game = await lifecycle.finish_game(dto)
            await uow.commit()

        voting_results = await _get_voting_results(session, game.id)
        text = await _build_finish_announcement(session, game, voting_results, data)

        background_tasks.add_task(event_bus.publish, GameFinishedEvent(
            game_id=game.id,
            chat_id=game.chat_id,
            message_id=game.message_id,
            result_text=text,
        ))
        return {"status": "finished"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Finish game error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add_player")
async def admin_add_player(data: AddPlayerRequest, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    await check_admin_rights(game.chat_id, user_id, session=session)
    
    result = await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == data.user_id))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.status != SignupStatus.ACTIVE:
            existing.status = SignupStatus.ACTIVE
            await session.commit()
            await cache_service.evict(f"game_details:{data.game_id}")
            background_tasks.add_task(event_bus.publish, GameStateChangedEvent(game_id=data.game_id))
            return {"status": "updated", "message": "Player restored to Active"}
        else: return {"status": "ok", "message": "Already active"}
            
    signup = Signup(game_id=data.game_id, user_id=data.user_id, status=SignupStatus.ACTIVE)
    session.add(signup)
    await session.commit()
    await cache_service.evict(f"game_details:{data.game_id}")
    background_tasks.add_task(event_bus.publish, GameStateChangedEvent(game_id=data.game_id))
    return {"status": "added"}

def _create_guest_user(session: AsyncSession, name: str, position_str: str, guest_id: int, alt_positions: list):
    """Helper to create and add a guest User record to the session."""
    from app.db.models import Position
    pos_str = position_str.upper().strip()
    if pos_str not in Position.__members__:
        pos_str = "CM"
    new_guest = User(
        user_id=guest_id, 
        full_name=f"{name} (Guest)", 
        username=None, 
        player_position=Position[pos_str], 
        alt_positions=alt_positions or [],
        rating=100
    )
    session.add(new_guest)
    return new_guest

@router.post("/add_guest")
async def admin_add_guest(data: AddGuestRequest, background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        logger.warning(f"Invalid initData in add_guest for game {data.game_id}")
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    await check_admin_rights(game.chat_id, user_id, session=session)
    guest_id = -int(time.time() * 1000)
    
    try:
        logger.info(f"Adding guest '{data.name}' to game {data.game_id} with ID {guest_id}")
        _create_guest_user(session, data.name, data.position, guest_id, data.alt_positions)
        
        new_signup = Signup(game_id=data.game_id, user_id=guest_id, status=SignupStatus.ACTIVE)
        session.add(new_signup)
        
        await session.commit()
        logger.info(f"Guest {guest_id} successfully added and committed")
        
        await cache_service.evict(f"game_details:{data.game_id}")
        background_tasks.add_task(event_bus.publish, GameStateChangedEvent(game_id=data.game_id))
        return {"status": "added", "user_id": guest_id}
        
    except Exception as e:
        logger.error(f"Add Guest Error for game {data.game_id}: {e}", exc_info=True)
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/trigger_voting/{game_id}")
async def debug_trigger_voting(game_id: int, initData: str = "", session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    user_id = get_user_from_init_data(initData)
    if user_id not in settings.admin_ids and user_id != settings.system_owner_id:
        raise HTTPException(status_code=403, detail="Admins only")
    try:
        from app.scheduler.tasks import send_voting_message
        await send_voting_message(game_id)
        return {"status": "triggered", "game_id": game_id}
    except Exception as e:
        logger.error(f"Debug trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
