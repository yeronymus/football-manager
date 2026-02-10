import asyncio
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game

async def main():
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(Game).where(Game.id == 1))
            game = result.scalar_one_or_none()
            if game:
                print(f"Game ID: {game.id}")
                print(f"Date Time: {game.date_time}")
                print(f"Created At: {game.created_at}")
                print(f"Status: {game.status}")
            else:
                print("Game 1 not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
