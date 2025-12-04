from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game, User, Chat, Signup, SignupStatus, Team
from app.api.schemas import GameCreate, BalanceTeams, GameResult
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
