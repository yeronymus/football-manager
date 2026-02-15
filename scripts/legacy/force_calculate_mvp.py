import asyncio
import os
import sys
from app.scheduler.tasks import calculate_mvp

GAME_ID = 2

async def force_finish():
    print(f"FORCING MVP Calculation for Game {GAME_ID}...")
    try:
        await calculate_mvp(GAME_ID)
        print("✅ Success!")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(force_finish())
