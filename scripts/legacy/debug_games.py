import sys
import os
import asyncio
import traceback

sys.path.append(os.getcwd())

# FORCE ENV VARS for Local Debug
os.environ["POSTGRES_HOST"] = "localhost"
# Try 5432 first, if fails maybe 5433. 
# But let's assume one. If I can't check ports, I'll try 5432.
# Or I can try to loop?
# Let's just set it to 5432 for now, as local.env suggested.
# If it fails, I'll try 5433.
os.environ["POSTGRES_PORT"] = "5432" 

try:
    from app.db.database import async_session_maker
    from app.db.models import Game
    from sqlalchemy import select
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

async def main():
    print(f"Starting debug_games... connecting to {os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}")
    try:
        async with async_session_maker() as session:
            print("Session created. Querying...")
            stmt = select(Game).order_by(Game.id.desc()).limit(10)
            res = await session.execute(stmt)
            games = res.scalars().all()
            print(f"Found {len(games)} games.")
            for g in games:
                print(f"ID: {g.id} | Status: {g.status} | Date: {g.date_time}")
    except Exception as e:
        print(f"Error executing query: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
