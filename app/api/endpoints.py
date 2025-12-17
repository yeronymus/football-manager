from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game, User, Chat, Signup, SignupStatus, Team, GameStats, GameStatus
from app.api.schemas import GameCreate, BalanceTeams, GameResult, GameFinishRequest, UpdateTeamsRequest
from app.bot.elo import calculate_new_rating
from app.bot.main import bot
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
from app.bot.balancer import balance_teams as run_balance_teams
from app.config import settings
import hashlib
import hmac
import urllib.parse
import json
import time

router = APIRouter()

def validate_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validates Telegram WebApp initData.
    """
    try:
        if settings.DEBUG:
            return True
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            return False
        
        hash_value = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash != hash_value:
            return False
            
        # Check auth_date for replay attacks (10 minutes window)
        auth_date = int(parsed_data.get("auth_date", 0))
        if time.time() - auth_date > 600:
            return False
            
        return True
    except Exception:
        return False

def get_user_from_init_data(init_data: str) -> int:
    if settings.DEBUG and not init_data:
        # Default debug user ID (replace with your admin ID for testing)
        return settings.ADMIN_IDS[0] if settings.ADMIN_IDS else 123456789
        
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

@router.get("/chats")
async def get_chats(initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.BOT_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    
    # Get all chats from DB
    result = await session.execute(select(Chat))
    all_chats = result.scalars().all()
    
    admin_chats = []
    import asyncio
    for chat in all_chats:
        try:
            # Check if user is admin in this chat
            member = await bot.get_chat_member(chat.chat_id, user_id)
            if member.status in ["administrator", "creator"]:
                admin_chats.append({"id": chat.chat_id, "title": chat.title})
            await asyncio.sleep(0.05) # Prevent FloodWait
        except Exception:
            continue
            
    return admin_chats

@router.post("/create_game")
async def create_game(game_data: GameCreate, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(game_data.initData, settings.BOT_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(game_data.initData)
    await check_admin_rights(game_data.chat_id, user_id)

    # Ensure user exists
    result = await session.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        parsed_data = dict(urllib.parse.parse_qsl(game_data.initData))
        user_data = json.loads(parsed_data.get("user", "{}"))
        user = User(user_id=user_id, full_name=user_data.get("first_name", "Admin"), player_position="MID")
        session.add(user)
        await session.commit()

    # Ensure Chat exists
    result = await session.execute(select(Chat).where(Chat.chat_id == game_data.chat_id))
    chat = result.scalar_one_or_none()
    if not chat:
        try:
            chat_obj = await bot.get_chat(game_data.chat_id)
            chat = Chat(chat_id=game_data.chat_id, title=chat_obj.title or "Unknown Chat")
            session.add(chat)
            await session.commit()
        except:
             raise HTTPException(status_code=400, detail="Chat not found")

    new_game = Game(
        chat_id=game_data.chat_id,
        created_by=user_id,
        date_time=game_data.date_time,
        location=game_data.location,
        max_players=game_data.max_players
    )
    session.add(new_game)
    await session.commit()
    await session.refresh(new_game)

    message_text = await format_game_message(new_game, session)
    try:
        sent_message = await bot.send_message(
            chat_id=game_data.chat_id,
            text=message_text,
            reply_markup=get_game_keyboard(new_game.id)
        )
        
        new_game.message_id = sent_message.message_id
        await session.commit()
        
        await bot.pin_chat_message(chat_id=game_data.chat_id, message_id=sent_message.message_id)
        
        # Schedule voting
        from app.scheduler.main import scheduler
        from app.scheduler.tasks import send_voting_message
        from datetime import timedelta
        
        voting_time = new_game.date_time + timedelta(hours=2)
        scheduler.add_job(send_voting_message, 'date', run_date=voting_time, args=[new_game.id])
        
        # Напоминание админу через 2 часа 15 минут
        from app.scheduler.tasks import remind_admin_to_finish
        reminder_time = new_game.date_time + timedelta(hours=2, minutes=15)
        scheduler.add_job(remind_admin_to_finish, 'date', run_date=reminder_time, args=[new_game.id])
        
    except Exception:
        pass

    return {"game_id": new_game.id, "status": "created"}

@router.post("/balance_teams")
async def balance_teams_endpoint(data: BalanceTeams, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.BOT_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id)

    # Fetch active signups
    result = await session.execute(
        select(User)
        .join(Signup)
        .where(Signup.game_id == data.game_id, Signup.status == SignupStatus.ACTIVE)
    )
    players = result.scalars().all()
    
    if len(players) < 2:
        raise HTTPException(status_code=400, detail="Not enough players to balance")

    team_a, team_b = run_balance_teams(players)

    # Update DB
    # Update DB
    for player in team_a:
        signup = (await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == player.id))).scalar_one()
        signup.team = Team.A
    
    for player in team_b:
        signup = (await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == player.id))).scalar_one()
        signup.team = Team.B

    await session.commit()

    # Send message with teams
    text = f"⚖️ <b>Составы команд ({game.location}):</b>\n\n"
    
    text += "🔴 <b>Команда А:</b>\n"
    for p in team_a:
        rating_info = f" ({p.rating})" if settings.SHOW_RATING else ""
        text += f"- {p.full_name}{rating_info}\n"
    
    text += "\n🔵 <b>Команда Б:</b>\n"
    for p in team_b:
        rating_info = f" ({p.rating})" if settings.SHOW_RATING else ""
        text += f"- {p.full_name}{rating_info}\n"
        
    if settings.SHOW_RATING:
        avg_a = sum(p.rating for p in team_a) / len(team_a) if team_a else 0
        avg_b = sum(p.rating for p in team_b) / len(team_b) if team_b else 0
        text += f"\n📊 Средний рейтинг: {int(avg_a)} vs {int(avg_b)}"

    await bot.send_message(chat_id=game.chat_id, text=text)

    # OPTIONAL: Отправить админу в личку реальные цифры (God Mode View)
    try:
        if not settings.SHOW_RATING:
            admin_text = f"🕵️‍♂️ <b>Скрытые данные (Видно только вам):</b>\n\n"
            admin_text += "🔴 <b>Команда А:</b>\n"
            for p in team_a:
                admin_text += f"- {p.full_name} ({p.rating})\n"
            admin_text += "\n🔵 <b>Команда Б:</b>\n"
            for p in team_b:
                admin_text += f"- {p.full_name} ({p.rating})\n"
            
            avg_a = sum(p.rating for p in team_a) / len(team_a)
            avg_b = sum(p.rating for p in team_b) / len(team_b)
            admin_text += f"\n📊 Средний рейтинг: {int(avg_a)} vs {int(avg_b)}"
            
            await bot.send_message(chat_id=user_id, text=admin_text)
    except Exception:
        pass

    return {"status": "balanced", "team_a_count": len(team_a), "team_b_count": len(team_b)}

@router.post("/update_teams")
async def update_teams(data: UpdateTeamsRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.BOT_TOKEN):
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
            
    # Reset others to None (or handle as "Unassigned")
    # If a user is in neither list, they are effectively removed from a team but still signed up?
    # Or should we assume the lists are exhaustive?
    # Let's assume lists contain ALL assigned players.
    assigned_ids = set(data.team_a) | set(data.team_b)
    for uid, signup in signup_map.items():
        if uid not in assigned_ids:
            signup.team = None

    await session.commit()
    
    # Fetch updated player objects for message
    result = await session.execute(
        select(User).where(User.user_id.in_(team_a_users))
    )
    team_a_objs = result.scalars().all()
    
    result = await session.execute(
        select(User).where(User.user_id.in_(team_b_users))
    )
    team_b_objs = result.scalars().all()

    await session.commit()
    
    # Message removed as per user request (Save should be silent)
    # Only Publish sends notification

    return {"status": "updated"}

@router.post("/set_game_result")
async def set_game_result(data: GameResult, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.BOT_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id)

    game.winner_team = data.winner_team
    await session.commit()

    await bot.send_message(chat_id=game.chat_id, text=f"🏁 Результат матча зафиксирован! Победила команда {data.winner_team.value}!")

    return {"status": "result_set"}

@router.get("/games/open")
async def get_open_games(initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.BOT_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    # Check admin rights in general? Or just list games where user is admin?
    # For now, list ALL open games for simplicity, or filtered by chat.
    # The prompt implies scaling, so maybe just list all OPEN games.
    
    result = await session.execute(
        select(Game).where(Game.status.in_([GameStatus.OPEN, GameStatus.ACTIVE])).order_by(Game.date_time)
    )
    games = result.scalars().all()
    
    return [
        {
            "id": g.id, 
            "location": g.location, 
            "date_time": g.date_time.isoformat(),
            "chat_id": g.chat_id
        } 
        for g in games
    ]

@router.get("/game/{game_id}")
async def get_game_details(game_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(initData, settings.BOT_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid initData")
    
    user_id = get_user_from_init_data(initData)
    
    result = await session.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    # Fetch players
    result = await session.execute(
        select(User, Signup.team)
        .join(Signup)
        .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
    )
    players_data = result.all()
    
    def serialize_player(p_tuple):
        user, team = p_tuple
        return {
            "id": user.user_id,
            "name": user.full_name,
            "rating": user.rating,
            "position": user.player_position.value if user.player_position else "DEF"
        }
    
    team_a = [serialize_player(p) for p in players_data if p[1] == Team.A]
    team_b = [serialize_player(p) for p in players_data if p[1] == Team.B]
    unassigned = [serialize_player(p) for p in players_data if not p[1]]
    
    return {
        "id": game.id,
        "location": game.location,
        "date": game.date_time.isoformat(),
        "team_a": team_a,
        "team_b": team_b,
        "unassigned": unassigned,
        "score_a": game.score_a,
        "score_b": game.score_b,
        "status": game.status.value,
        "has_active_gk_a": game.has_active_gk_a,
        "has_active_gk_b": game.has_active_gk_b
    }

@router.post("/publish_teams")
async def publish_teams(data: BalanceTeams, session: AsyncSession = Depends(get_session)):
    # Using BalanceTeams (game_id, initData)
    if not validate_init_data(data.initData, settings.BOT_TOKEN):
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
    public_text = await format_game_message(game, session)
    try:
        if game.message_id:
            await bot.edit_message_text(
                chat_id=game.chat_id,
                message_id=game.message_id,
                text=public_text,
                reply_markup=get_game_keyboard(game.id),
                parse_mode="HTML"
            )
            
        if is_update:
            await bot.send_message(game.chat_id, "🔄 <b>Составы обновлены!</b> Проверьте изменения в закрепе.")
        else:
            await bot.send_message(game.chat_id, "📢 <b>Составы утверждены!</b> Чекайте закреп.")
    except Exception as e:
        print(f"Publish error: {e}")
        
    return {"status": "published"}

@router.post("/finish_game")
async def finish_game(data: GameFinishRequest, session: AsyncSession = Depends(get_session)):
    if not validate_init_data(data.initData, settings.BOT_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid initData")

    user_id = get_user_from_init_data(data.initData)
    
    result = await session.execute(select(Game).where(Game.id == data.game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await check_admin_rights(game.chat_id, user_id)

    # Update game score and status
    game.score_a = data.score_a
    game.score_b = data.score_b
    game.winner_team = data.winner_team
    game.status = GameStatus.FINISHED

    # Save player stats
    for p_stat in data.player_stats:
        if p_stat.goals > 0:
            stat = GameStats(game_id=game.id, user_id=p_stat.user_id, goals=p_stat.goals)
            session.add(stat)

    # ELO Calculation (if winner is set)
    if game.winner_team:
        # Fetch all active players with their teams
        result = await session.execute(
            select(User, Signup.team)
            .join(Signup)
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
        )
        players_data = result.all() # List of (User, Team)
        
        team_a_players = [p[0] for p in players_data if p[1] == Team.A]
        team_b_players = [p[0] for p in players_data if p[1] == Team.B]
        
        avg_a = sum(p.rating for p in team_a_players) / len(team_a_players) if team_a_players else 1200
        avg_b = sum(p.rating for p in team_b_players) / len(team_b_players) if team_b_players else 1200
        
        # Helper to update and log
        def update_player(player, opponent_avg, actual_score):
            # MVP is not known yet, so is_mvp=False for now. 
            # MVP bonus will be added later by scheduler if MVP voting is still used.
            # OR we can assume MVP voting happens BEFORE this manual finish?
            # The prompt says "Admin enters score AFTER whistle". MVP voting is usually later.
            # Let's just calculate base ELO here. MVP bonus can be a separate adjustment or we ignore it here.
            # Ideally, ELO should be calculated once.
            # If we calculate here, we should disable the scheduler calculation or make it additive.
            # Let's assume this REPLACES the scheduler calculation for ELO, but scheduler still does MVP.
            
            old_rating = player.rating
            new_rating = calculate_new_rating(player, int(opponent_avg), actual_score, is_mvp=False)
            
            player.rating = new_rating
            player.games_played += 1
            
            # Log history (Future functionality)
            # history = RatingHistory(...)
            # session.add(history)

        # Calculate for Team A
        actual_score_a = 1 if game.winner_team == Team.A else 0
        for player in team_a_players:
            update_player(player, avg_b, actual_score_a)
        
        # Calculate for Team B
        actual_score_b = 1 if game.winner_team == Team.B else 0
        for player in team_b_players:
            update_player(player, avg_a, actual_score_b)

    await session.commit()
    
    # Notify chat
    text = f"🏁 <b>Матч завершен!</b>\n"
    text += f"Счет: {game.score_a} - {game.score_b}\n"
    if game.winner_team:
        text += f"Победила команда {game.winner_team.value}!\n"
    
    if settings.SHOW_RATING and game.winner_team:
        text += f"\n📈 Рейтинги обновлены!\n"
    
    # Show goal scorers
    scorers = [p for p in data.player_stats if p.goals > 0]
    if scorers:
        text += "\n⚽ <b>Голы:</b>\n"
        scorer_ids = [s.user_id for s in scorers]
        # Fetch names
        result = await session.execute(select(User).where(User.user_id.in_(scorer_ids)))
        users_map = {u.user_id: u.full_name for u in result.scalars().all()}
        
        for s in scorers:
            name = users_map.get(s.user_id, "Неизвестный")
            text += f"- {name}: {s.goals}\n"

    await bot.send_message(chat_id=game.chat_id, text=text)

    return {"status": "finished"}

@router.get("/history/{chat_id}")
async def get_chat_history(chat_id: int, initData: str, session: AsyncSession = Depends(get_session)):
    # 1. Валидация WebApp данных
    if not validate_init_data(initData, settings.BOT_TOKEN):
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
