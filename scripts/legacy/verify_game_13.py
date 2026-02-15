import asyncio
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.db.models import Game, Signup, User

# Setup minimal DB connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql+asyncpg://postgres:password@db:5432/football"

engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def verify():
    async with async_session() as session:
        print("--- VERIFYING GAME 13 DATA ---")
        
        # 1. Game Check
        game = await session.get(Game, 13)
        if not game:
            print("❌ Game 13 MISSING")
            return
            
        print(f"✅ Game 13 Exists. Slots: {game.max_players}")
        print(f"   Chat ID: {game.chat_id}")
        
        # 2. Signup Count
        stmt = select(Signup, User).join(User).where(Signup.game_id == 13).order_by(Signup.created_at)
        res = await session.execute(stmt)
        rows = res.all()
        
        print(f"✅ Signups Found: {len(rows)}")
        
        if len(rows) == 0:
            print("⚠️ WARNING: ZERO SIGNUPS FOUND (Data Loss Persists?)")
        
        for i, (signup, user) in enumerate(rows, 1):
             print(f"   {i}. {user.full_name} ({signup.status})")

if __name__ == "__main__":
    asyncio.run(verify())
