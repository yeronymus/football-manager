import asyncio
import os
import sys
from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Signup, SignupStatus, Team

USER_ID = 502389915
GAME_ID = 2

async def add_phantom():
    print(f"Adding Phantom Player {USER_ID} to Game {GAME_ID}...")
    async with async_session_maker() as session:
        # Check exists
        result = await session.execute(
            select(Signup).where(Signup.game_id == GAME_ID, Signup.user_id == USER_ID)
        )
        signup = result.scalar_one_or_none()
        
        if signup:
            print("User already signed up. Updating status...")
            signup.status = SignupStatus.ACTIVE
            if not signup.team:
                signup.team = Team.A
        else:
            print("Creating new signup...")
            signup = Signup(
                game_id=GAME_ID,
                user_id=USER_ID,
                status=SignupStatus.ACTIVE,
                team=Team.A,
                is_paid=True
            )
            session.add(signup)
            
        await session.commit()
        print("✅ User added as ACTIVE player in Team A!")

if __name__ == "__main__":
    asyncio.run(add_phantom())
