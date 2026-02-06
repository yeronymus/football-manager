from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.database import get_session
from app.db.models import Game, User, Chat, Signup, SignupStatus, Team, GameStats, GameStatus
import logging
from app.api.schemas import GameCreate, BalanceTeams, GameResult, GameFinishRequest, UpdateTeamsRequest, GameUpdate
from app.services.user_service import UserService
from app.services.game_service import GameService
from app.bot.elo import calculate_new_rating
from app.bot.main import bot
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
from app.bot.balancer import balance_teams as run_balance_teams, Player
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
             
    except Exception as e:
        # If API fails, maybe trust cache if strictly needed? 
        # For now, just fail safe.
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
        game_service = GameService(session)
        updated_game = await game_service.update_game(data)
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
    user_service = UserService(session)
    user = await user_service.get_user(user_id)
    if not user:
        parsed_data = dict(urllib.parse.parse_qsl(game_data.initData))
        user_data = json.loads(parsed_data.get("user", "{}"))
        user = await user_service.create_user(
            user_id=user_id, 
            full_name=user_data.get("first_name", "Admin"), 
            username=user_data.get("username"),
            position="CM" # Default
        )
        await session.commit()

    try:
        game_service = GameService(session)
        new_game = await game_service.create_game(game_data, user_id)
        return {"game_id": new_game.id, "status": "created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create game error: {e}")
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
    try:
        game_service = GameService(session)
        result = await game_service.balance_teams(data.game_id)
        return result
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

    # Fetch all active signups for this game
    result = await session.execute(
        select(Signup)
        .where(Signup.game_id == data.game_id, Signup.status == SignupStatus.ACTIVE)
    )
    signups = result.scalars().all()
    
    # Map user_id to signup
    signup_map = {s.user_id: s for s in signups}
    
    team_a_users = []
    team_b_users = []
    
    # Update teams
    for uid in data.team_a:
        if uid in signup_map:
            signup_map[uid].team = Team.A
            team_a_users.append(uid)
            
    for uid in data.team_b:
        if uid in signup_map:
            signup_map[uid].team = Team.B
            team_b_users.append(uid)
            
    if data.team_c:
        for uid in data.team_c:
            if uid in signup_map:
                signup_map[uid].team = Team.C
                # team_c_users.append(uid)
            
    # Reset others to None (or handle as "Unassigned")
    # If a user is in neither list, they are effectively removed from a team but still signed up?
    # Or should we assume the lists are exhaustive?
    # Let's assume lists contain ALL assigned players.
    assigned_ids = set(data.team_a) | set(data.team_b)
    if data.team_c:
        assigned_ids |= set(data.team_c)
        
    for uid, signup in signup_map.items():
        if uid not in assigned_ids:
            signup.team = None

    # Update Positions (Per-Match Override)
    if data.positions:
        from app.db.models import Position
        
        # Map simplified Frontend slots to Concrete DB Positions
        # effectively "representative" positions for the slot
        slot_map = {
            "GK": Position.GK,
            "DEF": Position.CB,
            "MID": Position.CM,
            "FWD": Position.FWD
        }
        
        for user_id_val, pos_str in data.positions.items():
            if user_id_val in signup_map:
                try:
                    # 1. Try generic map
                    new_pos = slot_map.get(pos_str)
                    
                    # 2. If not found, try direct enum conversion (fallback)
                    if not new_pos:
                        new_pos = Position(pos_str)
                        
                    # Save into Signup
                    signup_map[user_id_val].position = new_pos
                    
                except ValueError:
                    pass
                
        await session.commit()
    
    return {"status": "updated"} # No need to fetch objs if message is disabled here

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
    
    is_update = game.status == GameStatus.ACTIVE
    game.status = GameStatus.ACTIVE
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
                if "message is not modified" in str(e):
                    pass
                elif "message to edit not found" in str(e) or "message can't be edited" in str(e):
                    # Message deleted? Send new one.
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
            
        if is_update:
            await bot.send_message(game.chat_id, "🔄 <b>Составы обновлены!</b> Проверьте изменения в закрепе.")
        else:
            await bot.send_message(game.chat_id, "📢 <b>Составы утверждены!</b> Чекайте закреп.")
            
    except Exception as e:
        logger.error(f"Publish error: {e}", exc_info=True)
        # IMPORTANT: Returning error to client so user sees it
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

    # Update game score and status - Handled by Service
    try:
        game_service = GameService(session)
        await game_service.finish_game(data)
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
    
    user_service = UserService(session)
    users = await user_service.search_users(query)
    
    return [
        {
            "id": u.user_id,
            "name": u.full_name,
            "username": u.username,
            "position": u.player_position.value if u.player_position else "DEF"
        }
        for u in users
    ]

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
