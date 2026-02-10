
import asyncio
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select

async def fix_id():
    async with async_session_maker() as session:
        result = await session.execute(select(Game).where(Game.id == 1))
        game = result.scalar_one_or_none()
        if game:
            print(f"Old Chat ID: {game.chat_id}")
            game.chat_id = -1003437568976
            await session.commit()
            print(f"New Chat ID: {game.chat_id}")
        else:
            print("Game 1 not found")

if __name__ == "__main__":
    asyncio.run(fix_id())
