import asyncio
from app.db.database import async_session
from app.db.models import Game, GameStatus, Team, Signup
from app.config import settings
from sqlalchemy import select, update
import sys

# CHANGE THESE VALUES
GAME_ID = 26  # ID of the game to fix
TEAM_A_PLAYERS = ["yeronym", "player2"] # Usernames or IDs
TEAM_B_PLAYERS = ["player3", "player4"] 

# NOTE: This is a placeholder. Authentic logic requires fetching user IDs from usernames.
# For now, I will create a shell.

async def fix_roster():
    async with async_session() as session:
        result = await session.execute(select(Game).where(Game.id == GAME_ID))
        game = result.scalars().first()
        
        if not game:
            print(f"Game {GAME_ID} not found!")
            return

        print(f"fixing roster for game {game.id}...")
        
        # logic to update signups would go here
        # ...

if __name__ == "__main__":
    # verification of env
    print(f"DB: {settings.POSTGRES_DB}")
    # asyncio.run(fix_roster())
