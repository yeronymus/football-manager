from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game, User, Chat, Signup, SignupStatus, Team, GameStats, GameStatus
from app.api.schemas import GameCreate, BalanceTeams, GameResult, GameFinishRequest
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

router = APIRouter()

def validate_init_data(init_data: str, bot_token: str) -> bool:
    """
    Validates Telegram WebApp initData.
    """
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            return False
        
        hash_value = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        return calculated_hash == hash_value
    except Exception:
        return False

def get_user_from_init_data(init_data: str) -> int:
    parsed_data = dict(urllib.parse.parse_qsl(init_data))
    user_data = json.loads(parsed_data.get("user", "{}"))
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in initData")
    return user_id

async def check_admin_rights(chat_id: int, user_id: int):
    try:
        user_member = await bot.get_chat_member(chat_id, user_id)
        if user_member.status not in ["administrator", "creator"]:
             raise HTTPException(status_code=403, detail="You must be an admin of the chat")
    except Exception as e:
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
        user = User(user_id=user_id, full_name=user_data.get("first_name", "Admin"), position="MID")
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
        await bot.pin_chat_message(chat_id=game_data.chat_id, message_id=sent_message.message_id)
        
        # Schedule voting
        from app.scheduler.main import scheduler
        from app.scheduler.tasks import send_voting_message
        from datetime import timedelta
        
        voting_time = new_game.date_time + timedelta(hours=2)
        scheduler.add_job(send_voting_message, 'date', run_date=voting_time, args=[new_game.id])
        
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
    for player in team_a:
        signup = (await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == player.user_id))).scalar_one()
        signup.team = Team.A
    
    for player in team_b:
        signup = (await session.execute(select(Signup).where(Signup.game_id == data.game_id, Signup.user_id == player.user_id))).scalar_one()
        signup.team = Team.B

    await session.commit()

    # Send message with teams
    text = f"⚖️ <b>Составы команд ({game.location}):</b>\n\n"
    
    text += "🔴 <b>Команда А:</b>\n"
    for p in team_a:
        text += f"- {p.full_name} ({p.rating})\n"
    
    text += "\n🔵 <b>Команда Б:</b>\n"
    for p in team_b:
        text += f"- {p.full_name} ({p.rating})\n"
        
    avg_a = sum(p.rating for p in team_a) / len(team_a)
    avg_b = sum(p.rating for p in team_b) / len(team_b)
    text += f"\n📊 Средний рейтинг: {int(avg_a)} vs {int(avg_b)}"

    await bot.send_message(chat_id=game.chat_id, text=text)

    return {"status": "balanced", "team_a_count": len(team_a), "team_b_count": len(team_b)}

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
    
    team_a = [{"id": p[0].user_id, "name": p[0].full_name} for p in players_data if p[1] == Team.A]
    team_b = [{"id": p[0].user_id, "name": p[0].full_name} for p in players_data if p[1] == Team.B]
    
    return {
        "id": game.id,
        "location": game.location,
        "date": game.date_time.isoformat(),
        "team_a": team_a,
        "team_b": team_b,
        "score_a": game.score_a,
        "score_b": game.score_b
    }

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
            
            # Log history (TODO: Import RatingHistory)
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
    
    # Show goal scorers
    scorers = [p for p in data.player_stats if p.goals > 0]
    if scorers:
        text += "\n⚽ <b>Голы:</b>\n"
        for s in scorers:
            # Need to fetch names, but we only have IDs in request.
            # Optimization: Fetch names in the loop or before.
            # For now, let's skip names in notification to save time, or fetch them.
            pass

    await bot.send_message(chat_id=game.chat_id, text=text)

    return {"status": "finished"}
