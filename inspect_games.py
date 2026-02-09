import asyncio
from sqlalchemy import select
from app.db.database import get_session
from app.db.models import Game

async def list_games():
    async for session in get_session():
        result = await session.execute(select(Game).order_by(Game.id))
        games = result.scalars().all()
        print(f"Total Games Found: {len(games)}")
        for g in games:
            print(f"ID: {g.id}, Date: {g.date_time}, Location: {g.location}")

if __name__ == "__main__":
    asyncio.run(list_games())
