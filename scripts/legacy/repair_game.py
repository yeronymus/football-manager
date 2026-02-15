import asyncio
import sys
import os

# Setup Path
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game
from app.bot.main import bot
from app.bot.keyboards import get_game_keyboard

async def repair():
    print("Starting repair of duplicate messages...")
    
    async with async_session_maker() as session:
        # Find the game for 07.02 (Saturday)
        # Based on screenshots, it's one of the latest games.
        result = await session.execute(select(Game).order_by(Game.created_at.desc()).limit(1))
        game = result.scalar_one_or_none()
        
        if not game:
            print("No games found.")
            return

        print(f"Repairing Game #{game.id} ({game.location})")
        
        # User reported:
        # 1. Forwarded message from channel (Top)
        # 2. Bot reply message (Bottom)
        
        # Current state in DB:
        # game.chat_id and game.message_id likely point to the BOT REPLY (bottom one).
        # We need to find the FORWARDED message ID.
        
        # If handle_auto_forward was triggered, it might have stored channel_id.
        # But we need to know the message_id in the GROUP chat for the forward.
        
        # Since I cannot easily 'search' history here, I will ask the user
        # or try to guess if they followed the flow.
        
        print(f"Current Chat ID: {game.chat_id}")
        print(f"Current Message ID (Reply): {game.message_id}")
        
        msg_to_delete = game.message_id
        
        # OPTION: The user can provide the ID of the top message manually if they know it.
        # But for now, let's just fix the logic for FUTURE games and tell the user how to clean up.
        # To fix it MANUALLY for this game:
        # 1. User deletes the bottom message (bot reply).
        # 2. We set game.message_id to the TOP message (the forward).
        # 3. We attempt to add buttons to that top message.

        print("\nINSTRUCTIONS FOR MANUALLY REPAIRING THIS ONE GAME:")
        print("1. Find the FIRST (top) message in the group (the forwarded one from INFO channel).")
        print("2. Reply to it with /get_id or just guess the ID (it usually is message_id - 1 if no one talked).")
        print("Actually, easiest is to just DELETE the bottom message and let the bot fix everything on next update.")
        
        # I'll modify the handlers first so that further 'Join/Leave' clicks fix the state.
        
if __name__ == "__main__":
    asyncio.run(repair())
