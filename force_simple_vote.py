import asyncio
import os
from app.db.database import async_session_maker
from app.db.models import Game, Signup, User, Team, SignupStatus
from sqlalchemy import select
from app.bot.main import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def send_chat_voting():
    async with async_session_maker() as session:
        # Find Game 2
        result = await session.execute(select(Game).where(Game.id == 2))
        game = result.scalar_one_or_none()
        
        if not game:
            print("Game 2 not found")
            return

        print(f"Targeting Game {game.id}")
        
        # Get Players with Teams
        result = await session.execute(
            select(Signup, User)
            .join(User)
            .where(Signup.game_id == game.id, Signup.status == SignupStatus.ACTIVE)
            .order_by(Signup.team, User.full_name) # Group by team
        )
        players = result.all()
        
        team_a = []
        team_b = []
        
        for s, u in players:
            if s.team == Team.A:
                team_a.append((s, u))
            elif s.team == Team.B:
                team_b.append((s, u))
        
        print(f"Found {len(team_a)} in A, {len(team_b)} in B")
        
        # Build Keyboard
        keyboard = []
        
        # Team A Header (Dummy Button)
        keyboard.append([InlineKeyboardButton(text="🟠 --- КОМАНДА А --- 🟠", callback_data="ignore")])
        
        # Team A Players (2 per row?)
        row = []
        for s, u in team_a:
            if len(row) == 2:
                keyboard.append(row)
                row = []
            btn_text = f"{u.full_name}"
            # Callback: vote_GAMEID_PLAYERID
            cb_data = f"vote_{game.id}_{u.user_id}"
            row.append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
        if row:
            keyboard.append(row)

        # Spacer
        keyboard.append([InlineKeyboardButton(text=" ", callback_data="ignore")])

        # Team B Header
        keyboard.append([InlineKeyboardButton(text="🟢 --- КОМАНДА Б --- 🟢", callback_data="ignore")])
        
        # Team B Players
        row = []
        for s, u in team_b:
            if len(row) == 2:
                keyboard.append(row)
                row = []
            btn_text = f"{u.full_name}"
            cb_data = f"vote_{game.id}_{u.user_id}"
            row.append(InlineKeyboardButton(text=btn_text, callback_data=cb_data))
        if row:
            keyboard.append(row)

        kb_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Send
        try:
            await bot.send_message(
                chat_id=game.chat_id,
                text=f"🗳 <b>Голосование за MVP (Матч #{game.id})</b>\n\n"
                     f"Выберите <b>одного игрока из каждой команды</b>, который, по вашему мнению, был лучшим.\n"
                     f"<i>(Нажмите на кнопки с именами)</i>",
                reply_markup=kb_markup,
                parse_mode="HTML"
            )
            print("Chat voting message sent successfully.")
        except Exception as e:
            print(f"Failed to send chat voting: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(send_chat_voting())
    except Exception as e:
        print(f"Critical Error: {e}")
