
import asyncio
import sys
import os
import argparse

# Setup Path
sys.path.append(os.getcwd())

from app.db.database import async_session_maker
from app.core.repositories.game_repo import GameRepository
from app.core.services.roster import RosterService, SignupStatus
from app.db.models import Game, User, Position

async def add_player_command(game_id: int, user_id: int, force: bool = False):
    async with async_session_maker() as session:
        print(f"Adding player {user_id} to Game #{game_id}...")
        
        repo = GameRepository(session)
        service = RosterService(repo)
        
        # We need a User object. If it doesn't exist, we might fail or need to create?
        # For CLI, we assume user exists or we create a dummy wrapper if service allows.
        # Service expects a User model.
        
        user = await session.get(User, user_id)
        if not user:
            print(f"User {user_id} not found in DB.")
            return

        result = await service.join_player(game_id, user, ignore_limit=force)
        
        if result.success:
            print(f"Success: {result.message}")
            if result.is_reserve:
                print("(Reserved)")
            await session.commit()
        else:
            print(f"Failed: {result.message}")

async def kick_player_command(game_id: int, user_id: int):
    async with async_session_maker() as session:
        print(f"Kicking player {user_id} from Game #{game_id}...")
        
        repo = GameRepository(session)
        service = RosterService(repo)
        
        success, msg, promoted = await service.leave_player(game_id, user_id, is_admin=True)
        
        if success:
            print(f"Success: {msg}")
            if promoted:
                print(f"Promoted user: {promoted.full_name} ({promoted.user_id})")
            await session.commit()
        else:
            print(f"Failed: {msg}")

if __name__ == "__main__":
    pass # Managed by manage.py
