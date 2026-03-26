import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import urllib.parse
import time

from app.db.database import get_session
from app.db.models import Game, User, Signup, SignupStatus, Team, GameStatus
from app.api.auth import validate_init_data, get_user_from_init_data, check_admin_rights
from app.api.schemas import GameCreate, BalanceTeams, GameFinishRequest, UpdateTeamsRequest, GameUpdate, AddPlayerRequest, AddGuestRequest
from app.core.repositories.user_repository import UserRepository
from app.config import settings
from app.bot.main import bot
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard

from app.bot.admin_dashboard import update_dashboard_message
logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/create_game")
async def create_game(game_data: GameCreate, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(game_data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(game_data.initData)
    await check_admin_rights(game_data.chat_id, user_id)

    # Ensure user exists (Creator)
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    if not user:
        parsed_data = dict(urllib.parse.parse_qsl(game_data.initData))
        user_data = json.loads(parsed_data.get("user", "{}"))
        user = await user_repo.create_user(
            user_id=user_id, 
            full_name=user_data.get("first_name", "Admin"), 
            username=user_data.get("username"),
            position="CM" # Default
        )
        await session.commit()

    try:
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.core.uow import UnitOfWork
        
        new_game = None
        async with UnitOfWork() as uow:
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            
            new_game = await lifecycle.create_game(game_data, user_id)
            
            try:
                chat_info = await bot.get_chat(game_data.chat_id)
                if chat_info.type == "channel":
                    new_game.channel_id = game_data.chat_id
            except Exception as e:
                logger.warning(f"Failed to check chat type: {e}")

            await uow.commit() # Commit Initial Game Creation
            
            from datetime import datetime
            tz = new_game.date_time.tzinfo
            now_tz = datetime.now(tz) if tz else datetime.now()
            
            should_publish_now = True
            if new_game.date_time < now_tz:
                 should_publish_now = False
            elif game_data.publish_at:
                 pub_at = game_data.publish_at
                 if pub_at.tzinfo is None and tz:
                     pub_at = pub_at.replace(tzinfo=tz)
                 if pub_at > now_tz:
                     should_publish_now = False

            if should_publish_now:
                try:
                    text = await format_game_message(new_game, uow.session, is_short=False)
                    msg = await bot.send_message(
                        chat_id=new_game.chat_id,
                        text=text,
                        reply_markup=get_game_keyboard(new_game.id),
                        parse_mode="HTML"
                    )
                    new_game.message_id = msg.message_id
                    if new_game.channel_id == new_game.chat_id:
                        new_game.channel_message_id = msg.message_id
                        
                    await uow.commit()  # Save message_id to DB ASAP
                    
                    try:
                        await bot.pin_chat_message(chat_id=new_game.chat_id, message_id=msg.message_id)
                    except: pass
                except Exception as e:
                    logger.warning(f"Failed to publish to chat: {e}")

            # Update Dashboard
            try:
                 success = await update_dashboard_message(bot, new_game.id, uow.session)
                 if not success:
                     await bot.send_message(user_id, f"⚠️ Игра создана, но <b>Admin Dashboard</b> не отправлен (нет привязки чата). Используйте /setup.")
            except Exception as e:
                 logger.warning(f"Dashboard error: {e}")

            return {"game_id": new_game.id, "status": "created"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create game error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/update_game")
async def update_game(data: GameUpdate, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    try:
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.core.uow import UnitOfWork
        
        updated_game = None
        changes = []
        async with UnitOfWork() as uow:
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            
            updated_game, changes = await lifecycle.update_game(data)
            await uow.commit()

        if changes:
             try:
                public_text = await format_game_message(updated_game, session)
                kb = get_game_keyboard(updated_game.id)
                
                async def safe_edit(chat_id, msg_id):
                    if not chat_id or not msg_id: return
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=msg_id,
                            text=public_text,
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                         logger.warning(f"Failed to edit msg in {chat_id}: {e}")

                await safe_edit(updated_game.chat_id, updated_game.message_id)
                await safe_edit(updated_game.channel_id, updated_game.channel_message_id)
             except Exception as e:
                 logger.warning(f"Failed to notify update: {e}")
                 
        from app.bot.main import bot
        await update_dashboard_message(bot, updated_game.id, session)
        return {"status": "updated", "id": updated_game.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update game error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/balance_teams")
async def balance_teams(data: BalanceTeams, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id)

    try:
        from app.core.services.roster import RosterService
        from app.core.uow import UnitOfWork
        
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            await service.balance_teams(data.game_id)
            await uow.commit()

        try:
            public_text = await format_game_message(game, session)
            kb = get_game_keyboard(game.id)
            
            async def safe_edit(chat_id, msg_id):
                if not chat_id or not msg_id: return
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=public_text, reply_markup=kb, parse_mode="HTML")
                except Exception as e:
                    logger.warning(f"Failed to edit message in {chat_id}: {e}")

            await safe_edit(game.chat_id, game.message_id)
            await safe_edit(game.channel_id, game.channel_message_id)
        except Exception as e:
            logger.warning(f"Failed to update message after balance: {e}")

        from app.bot.main import bot
        await update_dashboard_message(bot, game.id, session)
        return {"status": "balanced"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Balance error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

@router.post("/update_teams")
async def update_teams(data: UpdateTeamsRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id)

    try:
        from app.core.services.roster import RosterService
        from app.core.uow import UnitOfWork
        
        promoted_ids = []
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            promoted_ids = await service.update_teams(data.game_id, data.team_a, data.team_b, data.team_c, data.positions or {})
            await uow.commit()

        for uid in promoted_ids:
             try:
                 await bot.send_message(uid, "<b>Ты в основном составе!</b>\nАдмин перенес тебя из резерва. <b>Подтверди в группе или админам, что будешь играть!</b>", parse_mode="HTML")
             except: pass
                 
        from app.bot.main import bot
        await update_dashboard_message(bot, data.game_id, session)
        return {"status": "updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update teams error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/publish_teams")
async def publish_teams(data: BalanceTeams, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    is_update = True
    if game.status == GameStatus.OPEN:
        game.status = GameStatus.ACTIVE
        is_update = False
    elif game.status == GameStatus.CANCELLED:
         game.status = GameStatus.ACTIVE
         is_update = False

    await session.commit()
    
    try:
        public_text = await format_game_message(game, session)
        if game.message_id:
            try:
                await bot.edit_message_text(chat_id=game.chat_id, message_id=game.message_id, text=public_text, reply_markup=get_game_keyboard(game.id), parse_mode="HTML")
            except Exception as e:
                err_str = str(e)
                if "message is not modified" in err_str: pass
                elif any(x in err_str for x in ["message to edit not found", "message can't be edited", "BUTTON_TYPE_INVALID"]):
                    msg = await bot.send_message(chat_id=game.chat_id, text=public_text, reply_markup=get_game_keyboard(game.id), parse_mode="HTML")
                    game.message_id = msg.message_id
                    await session.commit()
                else: raise e
        else:
            msg = await bot.send_message(chat_id=game.chat_id, text=public_text, reply_markup=get_game_keyboard(game.id), parse_mode="HTML")
            game.message_id = msg.message_id
            await session.commit()
            
    except Exception as e:
        logger.error(f"Publish error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Bot Error: {str(e)}")
        
    return {"status": "published"}

@router.post("/finish_game")
async def finish_game(data: GameFinishRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id)

    try:
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.core.uow import UnitOfWork
        
        async with UnitOfWork() as uow:
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            game = await lifecycle.finish_game(data)
            await uow.commit()

        text = f"🏁 <b>Матч завершен!</b>\n\n"
        text += f"Команда оранжевые 🟠 {game.score_a}:{game.score_b} 🟢 Команда зеленые\n"
        
        async def get_names(uids):
             if not uids: return []
             res = await session.execute(select(User).where(User.user_id.in_(uids)))
             return [u.full_name for u in res.scalars().all()]

        mvp_ids = []
        if data.mvp_user_id: mvp_ids.append(data.mvp_user_id)
        if data.mvp_team_a: mvp_ids.append(data.mvp_team_a)
        if data.mvp_team_b: mvp_ids.append(data.mvp_team_b)
        
        if mvp_ids:
             mvp_names = await get_names(mvp_ids)
             if mvp_names:
                 text += "🌟 <b>MVP:</b> " + ", ".join(mvp_names) + "\n"
        
        scorers = [p for p in data.player_stats if p.goals > 0]
        if scorers:
            text += "\n⚽ <b>Голы:</b>\n"
            scorer_ids = [s.user_id for s in scorers]
            res = await session.execute(select(User).where(User.user_id.in_(scorer_ids)))
            users_map = {u.user_id: u.full_name for u in res.scalars().all()}
            for s in scorers:
                 name = users_map.get(s.user_id, "Неизвестный")
                 text += f"- {name}: {s.goals}\n"

        if game.message_id:
            try:
                await bot.send_message(chat_id=game.chat_id, text=text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to send finish message: {e}")
        
        from app.bot.main import bot
        await update_dashboard_message(bot, game.id, session)
        return {"status": "finished"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Finish game error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add_player")
async def admin_add_player(data: AddPlayerRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    await check_admin_rights(game.chat_id, user_id)
    
    result = await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == data.user_id))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.status != SignupStatus.ACTIVE:
            existing.status = SignupStatus.ACTIVE
            await session.commit()
            return {"status": "updated", "message": "Player restored to Active"}
        else: return {"status": "ok", "message": "Already active"}
            
    signup = Signup(game_id=data.game_id, user_id=data.user_id, status=SignupStatus.ACTIVE)
    session.add(signup)
    await session.commit()
    from app.bot.main import bot
    await update_dashboard_message(bot, data.game_id, session)
    return {"status": "added"}

@router.post("/add_guest")
async def admin_add_guest(data: AddGuestRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        logger.warning(f"Invalid initData in add_guest for game {data.game_id}")
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(data.initData)
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    await check_admin_rights(game.chat_id, user_id)
    
    # Generate unique negative ID for guest
    guest_id = -int(time.time() * 1000) # Reduced precision to stay safe within some JS limits, but still unique enough
    
    try:
        from app.db.models import Position
        pos_str = data.position.upper().strip()
        if pos_str not in Position.__members__:
            pos_str = "CM"
        
        logger.info(f"Adding guest '{data.name}' to game {data.game_id} with ID {guest_id}")
        
        new_guest = User(
            user_id=guest_id, 
            full_name=f"{data.name} (Guest)", 
            username=None, 
            player_position=Position[pos_str], 
            rating=100
        )
        session.add(new_guest)
        
        # Use relationship-aware signup
        new_signup = Signup(
            game_id=data.game_id, 
            user_id=guest_id, 
            status=SignupStatus.ACTIVE
        )
        session.add(new_signup)
        
        await session.commit()
        logger.info(f"Guest {guest_id} successfully added and committed")
        
        from app.bot.main import bot
        await update_dashboard_message(bot, data.game_id, session)
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
