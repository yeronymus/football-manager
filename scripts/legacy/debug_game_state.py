import asyncio
import sys
import os
from sqlalchemy import select

# Ensure app is in path
sys.path.append(os.getcwd())

from app.db.database import init_models, get_session_maker
from app.db.models import Game

async def main():
    print("Initializing...")
    await init_models()
    
    session_maker = get_session_maker()
    async with session_maker() as session:
        game_id = 5
        print(f"Checking Game #{game_id}...")
        
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if game:
            print(f"Found Game #{game.id}")
            print(f" - Status: {game.status}")
            print(f" - Date: {game.date_time}")
            print(f" - Duration: {game.duration}")
            print(f" - Chat ID: {game.chat_id}")
            print(f" - Message ID: {game.message_id}")
            print(f" - Created By: {game.created_by}")
        else:
            print(f"Game #{game_id} NOT FOUND!")

if __name__ == "__main__":
    asyncio.run(main())
