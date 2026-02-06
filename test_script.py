import asyncio
import sys
import os

print("1. Start", flush=True)

try:
    from app.db.database import async_session_maker
    print("2. DB imported", flush=True)
except Exception as e:
    print(f"DB Import Error: {e}", flush=True)

try:
    from app.db.models import User, Game
    print("3. Models imported", flush=True)
except Exception as e:
    print(f"Models Import Error: {e}", flush=True)

try:
    from app.bot.elo import calculate_new_rating
    print("4. ELO imported", flush=True)
except Exception as e:
    print(f"ELO Import Error: {e}", flush=True)

async def main():
    print("5. Main running", flush=True)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
