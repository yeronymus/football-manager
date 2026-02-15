import asyncio
import sys
import os
import traceback
from sqlalchemy import select

# Ensure app is in path
sys.path.append(os.getcwd())
sys.path.append("/app")

async def main():
    print("--- ID CHECK START ---")
    try:
        from app.db.database import async_session_maker
        from app.db.models import Game

        async with async_session_maker() as session:
            # Check Games 5, 6, 47
            result = await session.execute(select(Game).where(Game.id.in_([5, 6, 47])).order_by(Game.id))
            games = result.scalars().all()
            
            for g in games:
                print(f"Game #{g.id}: chat_id={g.chat_id}, channel_id={g.channel_id} location={g.location}")
                
    except Exception as e:
         print(f"Fatal error: {e}")
         traceback.print_exc()

    print("--- ID CHECK END ---")

if __name__ == "__main__":
    asyncio.run(main())
