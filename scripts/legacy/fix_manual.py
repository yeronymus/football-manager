import asyncio
import sys
import os

# Ensure app is in path
sys.path.append(os.getcwd())

from app.db.database import init_models
from app.scheduler.tasks import send_voting_message
from app.bot.main import bot

async def main():
    print("Initializing...")
    await init_models()
    
    game_id = 5
    print(f"Force voting for Game #{game_id}...")
    
    try:
        await send_voting_message(game_id)
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
