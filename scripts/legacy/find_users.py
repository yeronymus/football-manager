import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Mock app structure
from app.db.models import User
from app.config import settings

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Search for Niyaz
        query = "Niyaz" 
        print(f"Searching for: {query}")
        
        stmt = select(User).where(
            (User.full_name.ilike(f"%{query}%")) | 
            (User.username.ilike(f"%{query}%"))
        )
        result = await session.execute(stmt)
        users = result.scalars().all()

        if not users:
            print("No users found.")
        else:
            for u in users:
                print(f"User Found: ID={u.user_id}")
                print(f"  Start Name: {u.full_name!r}") # !r for repr to see None
                print(f"  Username: {u.username!r}")
                print(f"  Position: {u.player_position}")
                print("-" * 20)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
