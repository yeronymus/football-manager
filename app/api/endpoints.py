from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.database import get_session
from app.db.models import Game, User, Chat, Signup, SignupStatus, Team, GameStats, GameStatus, Vote
import logging
from app.api.schemas import GameCreate, BalanceTeams, GameResult, GameFinishRequest, UpdateTeamsRequest, GameUpdate, AddPlayerRequest, AddGuestRequest, VoteRequest
from app.core.repositories.user_repository import UserRepository

from app.bot.elo import calculate_new_rating
from app.bot.main import bot
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
from app.core.domain.balancer import balance_teams as run_balance_teams, Player
from app.config import settings
import hashlib
import hmac
import urllib.parse
import json
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def validate_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validates Telegram WebApp initData.
    """
    try:
        # Security: Always validate hash, even in debug mode if possible, 
        # or rely on local validation. 
        # Removed simple bypass to enforce signed data usage.
        if not init_data:
            logger.warning("validate_init_data failed: Empty init_data")
            return False
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            logger.warning("validate_init_data failed: No hash in init_data")
            return False
        
        hash_value = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash != hash_value:
            logger.warning(f"validate_init_data failed: Hash mismatch. Calc: {calculated_hash}, Recieved: {hash_value}")
            return False
            
        # Check auth_date for replay attacks (Increased to 12h for ease of use)
        auth_date = int(parsed_data.get("auth_date", 0))
        if time.time() - auth_date > 43200:
            logger.warning("validate_init_data failed: Auth date expired")
            return False
            
        return True
    except Exception as e:
        logger.error(f"validate_init_data exception: {e}")
        return False

def get_user_from_init_data(init_data: str) -> int:
    if settings.debug and not init_data:
        # Default debug user ID (replace with your admin ID for testing)
        return settings.admin_ids[0] if settings.admin_ids else 123456789
        
    parsed_data = dict(urllib.parse.parse_qsl(init_data))
    user_data = json.loads(parsed_data.get("user", "{}"))
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in initData")
        
    return user_id

# Simple in-memory cache: (chat_id, user_id) -> (timestamp, is_admin)
admin_rights_cache = {}
CACHE_TTL = 300  # 5 minutes

async def check_admin_rights(chat_id: int, user_id: int):
    # System admins bypass all checks
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return True

    # 1. Check Cache
    current_time = time.time()
    cache_key = (chat_id, user_id)
    
    if cache_key in admin_rights_cache:
        timestamp, is_admin = admin_rights_cache[cache_key]
        if current_time - timestamp < CACHE_TTL:
            if not is_admin:
                raise HTTPException(status_code=403, detail="You must be an admin of the chat (Cached)")
            return True # Authorized

    # 2. Check Real (if not cached or expired)
    try:
        user_member = await bot.get_chat_member(chat_id, user_id)
        is_admin = user_member.status in ["administrator", "creator"]
        
        # Update Cache
        admin_rights_cache[cache_key] = (current_time, is_admin)
        
        if not is_admin:
             raise HTTPException(status_code=403, detail="You must be an admin of the chat")
             
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot verify user rights: {str(e)}")


@router.get("/chat/{chat_id}/admins")
async def get_chat_admins(chat_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    try:
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
async def get_chats(initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    # Return all registered chats
    result = await session.execute(select(Chat))
    chats = result.scalars().all()
    
    return [
        {"id": c.chat_id, "title": c.title} 
        for c in chats
    ]

@router.post("/update_game")
async def update_game(data: GameUpdate, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(data.initData)
    
    # Fetch game to check rights
    # Ideally Service should do it, but we need chat_id for check_admin_rights
    # or we trust Service to fail if not found and we check rights after fetching game?
    # Let's fetch game first to get chat_id.
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    try:
        # --- NEW ARCHITECTURE ---
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

        
        # --- Controller Logic (Notifications) ---
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
                 
        return {"status": "updated", "id": updated_game.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update game error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
        # --- NEW ARCHITECTURE (GameLifecycleService) ---
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.bot.admin_dashboard import update_dashboard_message
        from app.core.uow import UnitOfWork
        
        new_game = None
        
        async with UnitOfWork() as uow:
            # Instantiate Services
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            
            # Execute Domain Logic
            new_game = await lifecycle.create_game(game_data, user_id)
            
            # Channel Detection Logic
            try:
                chat_info = await bot.get_chat(game_data.chat_id)
                if chat_info.type == "channel":
                    new_game.channel_id = game_data.chat_id
                    # We leave new_game.chat_id as the channel ID for now.
                    # When Telegram auto-forwards to the Group, common.py will:
                    # 1. Detect the message via hidden link
                    # 2. Add buttons
                    # 3. Update new_game.chat_id to the Group ID
            except Exception as e:
                logger.warning(f"Failed to check chat type: {e}")

            await uow.commit() # Commit Game Creation

        
        # --- Controller Logic (Presentation/Notifications) ---
        
        # 1. Immediate Publish?
        # Logic replicated from legacy:
        # If not past AND (no publish_at OR publish_at <= now) -> Publish Now
        from datetime import datetime
        
        # Helper for timezone awareness check
        tz = new_game.date_time.tzinfo
        now_tz = datetime.now(tz) if tz else datetime.now()
        
        should_publish_now = True
        if new_game.date_time < now_tz:
             should_publish_now = False
        elif game_data.publish_at:
             # Ensure comparison compatibility
             pub_at = game_data.publish_at
             if pub_at.tzinfo is None and tz:
                 pub_at = pub_at.replace(tzinfo=tz)
             if pub_at > now_tz:
                 should_publish_now = False

        if should_publish_now:
             # Publish to Chat (with signup buttons)
             try:
                 text = await format_game_message(new_game, session, is_short=False)
                 msg = await bot.send_message(
                     chat_id=new_game.chat_id,
                     text=text,
                     reply_markup=get_game_keyboard(new_game.id)
                 )
                 new_game.message_id = msg.message_id
                 await session.commit()
                 try:
                     await bot.pin_chat_message(chat_id=new_game.chat_id, message_id=msg.message_id)
                 except: pass
             except Exception as e:
                 logger.warning(f"Failed to publish to chat: {e}")

        # 2. Update Dashboard
        try:
             success = await update_dashboard_message(bot, new_game.id, session)
             if not success:
                 await bot.send_message(
                     user_id, 
                     f"⚠️ Игра создана, но <b>Admin Dashboard</b> не отправлен (нет привязки чата). Используйте /setup."
                 )
        except Exception as e:
             logger.warning(f"Dashboard error: {e}")

        return {"game_id": new_game.id, "status": "created"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create game error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/balance_teams")
async def balance_teams_endpoint(data: BalanceTeams, session: AsyncSession = Depends(get_session)):
    """
    Balances teams for a specific game using the `balance_teams` algorithm.
    Resets current team assignments and redistributes players based on the game's team count.
    Saves the new assignments to the database and notifies the chat.
    """
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id)

    # Fetch active signups - Handled by Service
    # Fetch active signups - Handled by Service
    try:
        # --- NEW ARCHITECTURE (RosterService) ---
        from app.core.services.roster import RosterService
        from app.core.repositories.game_repo import GameRepository
        from app.core.uow import UnitOfWork
        
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            
            await service.balance_teams(data.game_id)
            await uow.commit()

        
        # Update Message
        try:
            public_text = await format_game_message(game, session)
            kb = get_game_keyboard(game.id)
            
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
                    logger.warning(f"Failed to edit message in {chat_id}: {e}")

            await safe_edit(game.chat_id, game.message_id)
            await safe_edit(game.channel_id, game.channel_message_id)
            
            # Send notification about balance - REMOVED per user request
            # await bot.send_message(game.chat_id, "⚖️ <b>Команды сбалансированы!</b>", parse_mode="HTML")
            
        except Exception as e:
            logger.warning(f"Failed to update message after balance: {e}")

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

    # Fetch active AND reserve signups - Handled by Service
    try:
        from app.core.services.roster import RosterService
        from app.core.repositories.game_repo import GameRepository
        from app.core.uow import UnitOfWork
        
        promoted_ids = []
        async with UnitOfWork() as uow:
            service = RosterService(uow) # Pass UOW, not Repo
            
            promoted_ids = await service.update_teams(
                data.game_id, 
                data.team_a, 
                data.team_b, 
                data.team_c, 
                data.positions or {}
            )
            await uow.commit()

        
        # Notify Promoted
        for uid in promoted_ids:
             try:
                 await bot.send_message(
                     uid, 
                     "<b>Ты в основном составе!</b>\nАдмин перенес тебя из резерва. <b>Подтверди в группе или админам, что будешь играть!</b>", 
                     parse_mode="HTML"
                 )
             except Exception:
                 pass
                 
        return {"status": "updated"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update teams error: {e}")
        if settings.debug:
            import traceback
            raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)} | {traceback.format_exc()[:200]}")
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")

# ... (skip to get_game_details) ...

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
    
    # Fetch players with Signup data
    result = await session.execute(
        select(User, Signup) # Select both
        .join(Signup)
        .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
    )
    players_data = result.all()
    
    def serialize_player(p_tuple):
        user, signup = p_tuple
        # Use Signup position override if available, else User default
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

@router.post("/publish_teams")
async def publish_teams(data: BalanceTeams, session: AsyncSession = Depends(get_session)):
    # Using BalanceTeams (game_id, initData)
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    # Only set to ACTIVE if it's currently OPEN. 
    # If it's FINISHED, keep it FINISHED but update the message (Retroactive Fix).
    # If it's CANCELLED, maybe reopen? Let's assume Publish means "Show Teams".
    is_update = True
    if game.status == GameStatus.OPEN:
        game.status = GameStatus.ACTIVE
        is_update = False
    elif game.status == GameStatus.CANCELLED:
         # Reopen
         game.status = GameStatus.ACTIVE
         is_update = False

    await session.commit()
    
    # Update Public Message
    from app.bot.main import bot
    try:
        public_text = await format_game_message(game, session)
        
        if game.message_id:
            try:
                await bot.edit_message_text(
                    chat_id=game.chat_id,
                    message_id=game.message_id,
                    text=public_text,
                    reply_markup=get_game_keyboard(game.id),
                    parse_mode="HTML"
                )
            except Exception as e:
                # If message not modified, it's fine. If not found, send new.
                err_str = str(e)
                if "message is not modified" in err_str:
                    pass
                elif any(x in err_str for x in ["message to edit not found", "message can't be edited", "BUTTON_TYPE_INVALID"]):
                    # Message deleted or incompatible buttons? Send new one.
                    msg = await bot.send_message(
                        chat_id=game.chat_id,
                        text=public_text,
                        reply_markup=get_game_keyboard(game.id),
                        parse_mode="HTML"
                    )
                    game.message_id = msg.message_id
                    await session.commit()
                else:
                    raise e
        else:
            # First publish or lost message
            msg = await bot.send_message(
                chat_id=game.chat_id,
                text=public_text,
                reply_markup=get_game_keyboard(game.id),
                parse_mode="HTML"
            )
            game.message_id = msg.message_id
            await session.commit()
            
        # Notification logic
        if not is_update:
             # await bot.send_message(game.chat_id, "📢 <b>Составы утверждены!</b>")
             pass
        else:
             # If strictly updating, maybe silent? User sometimes wants confirmation.
             # "Changes published"
             pass
            
    except Exception as e:
        logger.error(f"Publish error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Bot Error: {str(e)}")
        
    return {"status": "published"}

@router.get("/games/editable")
async def get_editable_games(initData: str, session: AsyncSession = Depends(get_session)):
    """Returns Open, Active, and recent Finished games for the Draft selector."""
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(initData)
    
    # Fetch user's administered chats? 
    # For simplicity, we return games from chats where user is admin.
    # But checking rights for ALL games is expensive.
    # Let's return last 10 games globally (if simple auth) 
    # OR better: client passes chat_id if context known?
    # Context: User opens WebApp via "Edit" button -> has game_id.
    # User opens via Menu -> No game_id. 
    # We show list. Filtering by admin rights is proper but tricky without Chat list.
    
    # Let's fetch last 20 games and filter by admin rights logic (cached).
    result = await session.execute(
        select(Game).order_by(Game.date_time.desc()).limit(20)
    )
    games = result.scalars().all()
    
    editable = []
    for g in games:
        try:
            # Check rights
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

    # Update game score and status - Handled by Service
    # Update game score and status - Handled by Service
    try:
        from app.infrastructure.scheduler.service import SchedulerService
        from app.core.services.stats import StatsService
        from app.core.services.game_lifecycle import GameLifecycleService
        from app.core.uow import UnitOfWork
        
        game = None
        
        async with UnitOfWork() as uow:
            # Instantiate
            scheduler = SchedulerService()
            stats = StatsService(uow.session)
            lifecycle = GameLifecycleService(uow, scheduler, stats)
            
            game = await lifecycle.finish_game(data)
            await uow.commit()

        
        # --- Controller Logic (Notifications) ---
        # 1. Construct Message
        text = f"🏁 <b>Матч завершен!</b>\n\n"
        text += f"Команда оранжевые 🟠 {game.score_a}:{game.score_b} 🟢 Команда зеленые\n"
        
        # Helper to fetch names
        async def get_names(uids):
             if not uids: return []
             res = await session.execute(select(User).where(User.user_id.in_(uids)))
             return [u.full_name for u in res.scalars().all()]

        # MVP
        mvp_ids = []
        if data.mvp_user_id: mvp_ids.append(data.mvp_user_id)
        if data.mvp_team_a: mvp_ids.append(data.mvp_team_a)
        if data.mvp_team_b: mvp_ids.append(data.mvp_team_b)
        
        if mvp_ids:
             mvp_names = await get_names(mvp_ids)
             if mvp_names:
                 text += "🌟 <b>MVP:</b> " + ", ".join(mvp_names) + "\n"
        
        # Scorers
        scorers = [p for p in data.player_stats if p.goals > 0]
        if scorers:
            text += "\n⚽ <b>Голы:</b>\n"
            scorer_ids = [s.user_id for s in scorers]
            
            # Fetch names map
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
        
        return {"status": "finished"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Finish game error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")

@router.get("/history/{chat_id}")
async def get_chat_history(chat_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    # 1. Валидация WebApp данных
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    
    # 2. Проверка доступа (Smart Security):
    # Пользователь должен быть участником этого чата, чтобы видеть его историю.
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status in ["left", "kicked"]:
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        # Если бот не может проверить (например, его кикнули), лучше отказать
        raise HTTPException(status_code=400, detail="Chat access error")

    # 3. Выборка завершенных игр
    result = await session.execute(
        select(Game)
        .where(Game.chat_id == chat_id, Game.status == GameStatus.FINISHED)
        .order_by(Game.date_time.desc())
        .limit(50) # Не грузим всю историю веков
    )
    games = result.scalars().all()
    
    # 4. Формирование ответа
    history = []
    for game in games:
        # Небольшая логика для красивого отображения победителя
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
    return history

@router.get("/users/search")
async def search_users(query: str, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    # Auth check - any valid user can search? Or only admins?
    # Let's restrict to admins for now to prevent scraping
    user_id = get_user_from_init_data(initData)
    # Check if user is admin in ANY chat? Or basically just authenticated?
    # Let's trust authentication for now, or check generic admin status if we had it.
    # We will just proceed since we validate initData.
    
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

@router.post("/debug/trigger_voting/{game_id}")
async def debug_trigger_voting(game_id: int):
    """
    Manually triggers voting for a specific game.
    """
    try:
        from app.scheduler.tasks import send_voting_message
        await send_voting_message(game_id)
        return {"status": "triggered", "game_id": game_id}
    except Exception as e:
        logger.error(f"Debug trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from app.api.schemas import AddPlayerRequest

@router.post("/admin/add_player")
async def admin_add_player(data: AddPlayerRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(data.initData)
    
    # Check Admin Rights on Game
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    # Add Player Logic
    # We can reuse GameService.join_game but that has checks for "Self" and "Max Players".
    # Admin override should bypass some checks or use a specific method?
    # GameService.join_game is for SELF join.
    # Let's do raw insert or a new Service method 'force_add_player'.
    # For now, explicit Signup creation here is fine and fast.
    
    # Check existence
    result = await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == data.user_id))
    existing = result.scalar_one_or_none()
    
    if existing:
        if existing.status != SignupStatus.ACTIVE:
            existing.status = SignupStatus.ACTIVE
            await session.commit()
            return {"status": "updated", "message": "Player restored to Active"}
        else:
            return {"status": "ok", "message": "Already active"}
            
    # Create new
    signup = Signup(game_id=data.game_id, user_id=data.user_id, status=SignupStatus.ACTIVE)
    session.add(signup)
    await session.commit()
    
    return {"status": "added"}

from app.api.schemas import AddGuestRequest

@router.post("/admin/add_guest")
async def admin_add_guest(data: AddGuestRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
        
    user_id = get_user_from_init_data(data.initData)
    
    # Check Admin Rights
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    # Generate Guest ID (Negative Timestamp)
    # We use microsecond precision to avoid collision if added quickly
    guest_id = -int(time.time() * 1000000)
    
    # Create Guest User
    # We assume simple fields for Guest
    # Position Enum check?
    try:
        from app.db.models import Position
        # Clean position string
        pos_str = data.position.upper().strip()
        # Default mapping if needed, or trust strict Enum
        if pos_str not in Position.__members__:
            pos_str = "CM" # Default fallback
            
        user = User(
            user_id=guest_id,
            full_name=f"{data.name} (Guest)",
            username=None,
            player_position=Position[pos_str],
            rating=100 # Default rating
        )
        session.add(user)
        
        # Signup
        signup = Signup(game_id=data.game_id, user_id=guest_id, status=SignupStatus.ACTIVE)
        session.add(signup)
        
        await session.commit()
    except Exception as e:
        logger.error(f"Add Guest Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add guest: {e}")
        
    return {"status": "added", "user_id": guest_id}

@router.get("/game/{game_id}/vote_data")
async def get_vote_data(game_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.bot_token):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    
    # Check if user is a participant (Active Signup)
    result = await session.execute(
         select(Signup).where(
             Signup.game_id == game_id, 
             Signup.user_id == user_id, 
             Signup.status == SignupStatus.ACTIVE
         )
    )
    if not result.scalar_one_or_none():
         raise HTTPException(status_code=403, detail="Only active players can vote")

    # Fetch all active players
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
    
    # Check if already voted
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
    
    # Check participation
    result = await session.execute(
        select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == user_id, Signup.status == SignupStatus.ACTIVE)
    )
    if not result.scalar_one_or_none():
         raise HTTPException(status_code=403, detail="Only active players can vote")
         
    # Check existing votes
    result = await session.execute(
        select(Vote).where(Vote.game_id == data.game_id, Vote.voter_id == user_id)
    )
    votes = result.scalars().all()
    if votes:
        raise HTTPException(status_code=400, detail="Already voted")
        
    # Prevent self-voting
    if data.mvp_team_a == user_id or data.mvp_team_b == user_id:
        raise HTTPException(status_code=400, detail="You cannot vote for yourself")
        
    # Create Votes
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
