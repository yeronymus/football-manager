import asyncio
import os
import sys
from sqlalchemy import text
from app.db.database import async_session_maker

async def fix_vote_constraint():
    print("FIXING Vote Constraints...")
    async with async_session_maker() as session:
        try:
            # 1. Drop old constraint 'unique_vote' if exists
            try:
                await session.execute(text("ALTER TABLE votes DROP CONSTRAINT IF EXISTS unique_vote"))
                print("Old constraint 'unique_vote' dropped.")
            except Exception as e:
                print(f"Failed to drop old constraint: {e}")

            # 2. Add new constraint 'unique_vote_team' (game_id, voter_id, vote_team)
            # Check if exists first? Or just try adding.
            try:
                await session.execute(text(
                    "ALTER TABLE votes ADD CONSTRAINT unique_vote_team UNIQUE (game_id, voter_id, vote_team)"
                ))
                print("New constraint 'unique_vote_team' added.")
            except Exception as e:
                print(f"Constraint 'unique_vote_team' likely exists or failed: {e}")
                
            await session.commit()
            print("✅ Constraints updated successfully!")
                
        except Exception as e:
            print(f"❌ Failed to fix constraints: {e}")

if __name__ == "__main__":
    asyncio.run(fix_vote_constraint())
