
import asyncio
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import User

async def reset_all_ratings():
    async with async_session_maker() as session:
        print("Resetting ALL interactions to 100...")
        stmt = select(User)
        result = await session.execute(stmt)
        users = result.scalars().all()
        
        count = 0
        for user in users:
            # OPTIONAL: You can preserve ratings != 1200 if necessary, but USER asked "Make everyone 100".
            # "Even newly created guest... everyone check everywhere".
            # So I will reset EVERYONE to 100 to be safe and consistent.
            if user.rating != 100:
                user.rating = 100
                count += 1
        
        await session.commit()
        print(f"Updated {count} users to rating 100.")

if __name__ == "__main__":
    asyncio.run(reset_all_ratings())
