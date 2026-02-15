import asyncio
import sys
import os
from sqlalchemy import select

# Ensure app is in path
sys.path.append(os.getcwd())
sys.path.append("/app")

async def main():
    from app.db.database import async_session_maker
    from app.db.models import Game

    async with async_session_maker() as session:
        result = await session.execute(select(Game).where(Game.id.in_([5, 6, 47])))
        games = result.scalars().all()
        
        for game in games:
            print(f"Game #{game.id}: chat_id={game.chat_id}, channel_id={game.channel_id}")

if __name__ == "__main__":
    asyncio.run(main())
