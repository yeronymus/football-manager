import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.models import Base, Chat, ChatAdmin, User
from app.config import settings

async def debug():
    # Attempt to connect using the configured DB URL
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            print(f"Connecting to: {settings.postgres_host}")
            print("Fetching all chats...")
            res = await session.execute(select(Chat))
            chats = res.scalars().all()
            print(f"Found {len(chats)} chats.")
            for c in chats:
                print(f"Chat: {c.chat_id}, Title: {c.title}, Language: {c.language}")
                
            print("\nFetching chat admins...")
            res = await session.execute(select(ChatAdmin))
            admins = res.scalars().all()
            print(f"Found {len(admins)} chat admins.")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(debug())
