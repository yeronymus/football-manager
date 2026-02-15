import sys
import os
import asyncio
import traceback

# Use Environment Variables
# If running inside Docker container on prod, these should be set.
# We override DB to check 'football' (legacy?)
import os
os.environ["POSTGRES_DB"] = "football"

from dotenv import load_dotenv
load_dotenv()

try:
    from app.db.database import async_session_maker
    from app.db.models import Game, GameStatus
    from sqlalchemy import select, update
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

async def main():
    print("Connecting to DB...")
    try:
        async with async_session_maker() as session:
            # 1. List recent games
            print("Listing recent games...")
            stmt = select(Game).order_by(Game.id.desc()).limit(10)
            res = await session.execute(stmt)
            games = res.scalars().all()
            
            print(f"Found {len(games)} games.")
            for g in games:
                 print(f"ID: {g.id} | Status: {g.status} | Date: {g.date_time}")
            
            # Check for 47 specifically again just in case
            g47 = next((g for g in games if g.id == 47), None)
            if g47:
                print(f"Game 47 found in recent list! Status: {g47.status}")
                if g47.status != GameStatus.ACTIVE:
                    print("Attempting to FIX Game 47 status to ACTIVE...")
                    g47.status = GameStatus.ACTIVE
                    await session.commit()
                    print("Fixed.")
                else:
                    print("Game 47 is already ACTIVE.")
            else:
                print("Game 47 NOT found in last 10 games.")

    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
