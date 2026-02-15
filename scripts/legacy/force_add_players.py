import asyncio
import sys
import os
import logging

# Use Environment Variables
from dotenv import load_dotenv
load_dotenv()

# Fix Path
sys.path.append(os.getcwd())

from sqlalchemy import select

try:
    from app.db.database import async_session_maker
    from app.db.models import User, Signup, SignupStatus, Game
    from app.bot.utils import format_game_message
    from app.bot.keyboards import get_game_keyboard, get_channel_game_keyboard
    from app.bot.main import bot
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

# IDs
YERMAKHAN_ID = 1727698240
MEDEU_ID = 928516797
GAME_ID = 5

async def main():
    print(f"Force Adding Players to Game {GAME_ID}...")
    
    async with async_session_maker() as session:
        # 1. Fetch Game
        game = await session.get(Game, GAME_ID)
        if not game:
            print(f"Game {GAME_ID} NOT FOUND.")
            return

        print(f"Game {GAME_ID} Status: {game.status}")

        users_to_add = [YERMAKHAN_ID, MEDEU_ID]
        added_count = 0
        
        for uid in users_to_add:
            # Check exist
            stmt = select(Signup).where(Signup.game_id == GAME_ID, Signup.user_id == uid)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            
            if existing:
                print(f"User {uid} already signed up (Status: {existing.status}). Skipping.")
            else:
                print(f"Adding User {uid}...")
                signup = Signup(game_id=GAME_ID, user_id=uid, status=SignupStatus.ACTIVE)
                session.add(signup)
                added_count += 1
        
        if added_count > 0:
            await session.commit()
            print(f"Committed {added_count} new signups.")
            
            # 2. Update Message
            print("Updating Game Message...")
            # Refresh game to count new signups
            # Actually format_game_message queries signups?
            # Yes usually.
            text = await format_game_message(game, session)
            
            async def safe_edit(chat_id, msg_id, keyboard):
                if not chat_id or not msg_id: 
                    print("Skipping edit (no id)")
                    return
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    print(f"Updated message in chat {chat_id}")
                except Exception as e:
                    print(f"Failed to edit message in {chat_id}: {e}")

            await safe_edit(game.chat_id, game.message_id, get_game_keyboard(GAME_ID))
            await safe_edit(game.channel_id, game.channel_message_id, get_channel_game_keyboard(GAME_ID))
            
        else:
            print("No players added.")

if __name__ == "__main__":
    asyncio.run(main())
