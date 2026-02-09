import asyncio
from sqlalchemy import select, func
from app.db.database import get_session
from app.db.models import User

async def count_users():
    async for session in get_session():
        result = await session.execute(select(func.count(User.id)))
        count = result.scalar()
        print(f"Total Users: {count}")

if __name__ == "__main__":
    asyncio.run(count_users())
