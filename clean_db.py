import asyncio
import re
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select

async def main():
    async with async_session_maker() as session:
        result = await session.execute(select(Game))
        games = result.scalars().all()
        for g in games:
            if g.location and "http" in g.location:
                # Remove URLs from location string
                new_loc = re.sub(r'\(?https?://[^\s)]+\)?', '', g.location).strip()
                if new_loc != g.location:
                    print(f"Updating Game {g.id}: {g.location} -> {new_loc}")
                    g.location = new_loc
        await session.commit()
        print("Done")

if __name__ == "__main__":
    asyncio.run(main())
