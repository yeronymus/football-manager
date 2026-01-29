
import asyncio
from sqlalchemy import delete
from app.db.database import async_session_maker
from app.db.models import User, Game, Signup, Vote, RatingHistory, GameStats

async def clear_data():
    async with async_session_maker() as session:
        print("Clearing Signups...")
        await session.execute(delete(Signup))
        
        print("Clearing Votes...")
        await session.execute(delete(Vote))
        
        print("Clearing RatingHistory...")
        await session.execute(delete(RatingHistory))

        print("Clearing GameStats...")
        await session.execute(delete(GameStats))
        
        print("Clearing Games...")
        await session.execute(delete(Game))
        
        print("Clearing Users...")
        await session.execute(delete(User))
        
        await session.commit()
        print("Data cleared successfully.")

if __name__ == "__main__":
    asyncio.run(clear_data())
