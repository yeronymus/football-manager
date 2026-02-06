
import asyncio
import os
import sys
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import User

# Mock env if needed (usually loaded by config, but let's be safe)
os.environ.setdefault("BOT_TOKEN", "123")

async def check_mmr():
    async with async_session_maker() as session:
        print("🔍 Checking User Ratings ( != 100 )...")
        result = await session.execute(select(User).where(User.rating != 100))
        users = result.scalars().all()
        
        if not users:
            print("ℹ️ No users with rating != 100 found.")
        else:
            print(f"✅ Found {len(users)} users with updated ratings:")
            for u in users:
                print(f"   - {u.full_name}: {u.rating}")

if __name__ == "__main__":
    asyncio.run(check_mmr())
