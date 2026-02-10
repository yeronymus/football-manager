import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.db.database import async_session_maker
from app.bot.main import bot
from app.bot.admin_dashboard import update_dashboard_message
from sqlalchemy import select
from app.db.models import Game

# Configure logging
logging.basicConfig(level=logging.INFO)

async def main():
    game_id = 1 # Target Game ID
    
    async with async_session_maker() as session:
        print(f"🔄 Force refreshing dashboard for Game #{game_id}...")
        
        # Check if game exists
        game = await session.get(Game, game_id)
        if not game:
            print("❌ Game not found!")
            return

        print(f"📍 Game: {game.location}, Chat ID: {game.chat_id}")
        
        # Call update
        success = await update_dashboard_message(bot, game_id, session)
        
        if success:
            print("✅ Dashboard sent/updated successfully!")
        else:
            print("⚠️ Failed to send dashboard (maybe no linked admin chat?)")

if __name__ == "__main__":
    asyncio.run(main())
