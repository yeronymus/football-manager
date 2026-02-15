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
        result = await session.execute(select(Game).where(Game.id == 5))
        game = result.scalar_one_or_none()
        
        if game:
            print(f"Game #5: chat_id={game.chat_id}, channel_id={game.channel_id}")
            
            # Check other games to compare
            result = await session.execute(select(Game).limit(5))
            games = result.scalars().all()
            for g in games:
                print(f"Game #{g.id}: chat_id={g.chat_id}, channel_id={g.channel_id}")
        else:
            print("Game #5 not found")

if __name__ == "__main__":
    asyncio.run(main())
