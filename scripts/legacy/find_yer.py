
import asyncio
import sys
sys.path.append('/app')
from app.db.database import async_session_maker
from app.db.models import User
from sqlalchemy import select

async def find():
    async with async_session_maker() as session:
        res = await session.execute(select(User).where(User.full_name.ilike('%Yer%')))
        for u in res.scalars():
            print(f"ID: {u.user_id}, Name: {u.full_name}, User: {u.username}")

if __name__ == "__main__":
    asyncio.run(find())
