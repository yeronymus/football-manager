import asyncio
import os
import sys
from sqlalchemy import text
from app.db.database import async_session_maker

USER_ID = 502389915
GAME_ID = 2

async def cleanup_test_data():
    print(f"CLEANING UP test data for User {USER_ID} in Game {GAME_ID}...")
    async with async_session_maker() as session:
        try:
            # 1. Delete Votes
            await session.execute(
                text("DELETE FROM votes WHERE game_id = :g AND voter_id = :u"),
                {"g": GAME_ID, "u": USER_ID}
            )
            print("✅ Test votes deleted.")

            # 2. Delete Signup (Phantom)
            await session.execute(
                text("DELETE FROM signups WHERE game_id = :g AND user_id = :u"),
                {"g": GAME_ID, "u": USER_ID}
            )
            print("✅ Test signup removed.")
            
            await session.commit()
            print("Cleanup complete.")
                
        except Exception as e:
            print(f"❌ Failed to cleanup: {e}")

if __name__ == "__main__":
    asyncio.run(cleanup_test_data())
