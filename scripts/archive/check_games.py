import asyncio
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game

async def main():
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(Game).order_by(Game.id.desc()).limit(5))
            games = result.scalars().all()
            print(f"{'ID':<5} | {'Status':<10} | {'Location':<20} | {'Created At'}")
            print("-" * 60)
            for g in games:
                c = g.created_at.strftime("%Y-%m-%d %H:%M") if g.created_at else "N/A"
                print(f"{g.id:<5} | {g.status.value:<10} | {g.location[:20]:<20} | {c}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
