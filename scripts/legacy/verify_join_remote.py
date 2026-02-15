import asyncio
import sys
import os
from datetime import datetime

# Use Environment Variables
from dotenv import load_dotenv
load_dotenv()

# Fix Path
sys.path.append(os.getcwd())
try:
    print(f"Files in app/services: {os.listdir('app/services')}")
except: print("Cannot list app/services")

try:
    print(f"Files in app/bot: {os.listdir('app/bot')}")
except: print("Cannot list app/bot")

print("Reading app/bot/game_handlers.py head...")
try:
    with open("app/bot/game_handlers.py", "r") as f:
        print(f.read(500))
except Exception as e: print(f"Cannot read handlers: {e}")

async def main():
    print("Verifying Join Logic on Remote...")
    
    async with UnitOfWork() as uow:
        print("Connected to DB via UoW.")
        
        # 1. Fetch Game 5
        game = await uow.game_repo.get_game(5)
        if not game:
            print("Game 5 NOT FOUND via Repo.")
            return

        print(f"Game 5 Found. Status: '{game.status}' (Type: {type(game.status)})")
        print(f"Enum OPEN: '{GameStatus.OPEN}' (Type: {type(GameStatus.OPEN)})")
        print(f"Match? {game.status == GameStatus.OPEN}")
        
        if game.status == GameStatus.OPEN:
            print("Status MATCHES OPEN.")
        else:
            print("Status DOES NOT MATCH OPEN.")
            
        # 2. Try Join Logic
        # Create a dummy user object (not saving to DB, just for logic)
        user = User(
            user_id=12345, 
            full_name="Test Verify", 
            player_position=Position.FWD
        )
        
        service = RosterService(uow)
        print("Calling join_player...")
        result = await service.join_player(5, user)
        
        print(f"Join Result: Success={result.success}")
        print(f"Message: '{result.message}'")
        
        if result.success:
             print("Join Logic SUCCEEDED.")
             # We won't commit, so no data changes.
        else:
             print("Join Logic FAILED.")

if __name__ == "__main__":
    asyncio.run(main())
