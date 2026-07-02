
import sys
import os

# Setup Path
sys.path.append(os.getcwd())

from app.db.database import async_session_maker
from app.core.repositories.game_repo import GameRepository
from app.core.services.roster import RosterService, SignupStatus
from app.db.models import Game, User, Position

from app.core.uow import UnitOfWork

async def add_player_command(game_id: int, user_id: int, force: bool = False):
    async with UnitOfWork() as uow:
        print(f"Adding player {user_id} to Game #{game_id}...")
        
        service = RosterService(uow)
        
        # We need a User object. If it doesn't exist, we might fail or need to create?
        # For CLI, we assume user exists or we create a dummy wrapper if service allows.
        # Service expects a User model.
        
        user = await uow.session.get(User, user_id)
        if not user:
            print(f"User {user_id} not found in DB.")
            return

        result = await service.join_player(game_id, user, ignore_limit=force)
        
        if result.success:
            print(f"Success: {result.message}")
            if result.is_reserve:
                print("(Reserved)")
            await uow.commit()
        else:
            print(f"Failed: {result.message}")

async def renumber_game_command(old_id: int, new_id: int):
    """Renumber a game ID and all related records."""
    async with async_session_maker() as session:
        from sqlalchemy import text
        print(f"Renumbering Game {old_id} -> {new_id}...")
        
        # 1. Verify IDs
        res_old = await session.execute(
            text("SELECT id FROM games WHERE id = :old_id"),
            {"old_id": old_id}
        )
        if not res_old.scalar():
            print(f"Game {old_id} not found. Aborting.")
            return

        res_new = await session.execute(
            text("SELECT id FROM games WHERE id = :new_id"),
            {"new_id": new_id}
        )
        if res_new.scalar():
            print(f"Game {new_id} ALREADY exists. Aborting.")
            return

        # 2. Update Foreign Keys and Game ID
        queries = [
            "UPDATE signups SET game_id = :new_id WHERE game_id = :old_id",
            "UPDATE votes SET game_id = :new_id WHERE game_id = :old_id",
            "UPDATE rating_history SET game_id = :new_id WHERE game_id = :old_id",
            "UPDATE game_stats SET game_id = :new_id WHERE game_id = :old_id",
            "UPDATE games SET id = :new_id WHERE id = :old_id"
        ]
        
        for query in queries:
            await session.execute(
                text(query),
                {"new_id": new_id, "old_id": old_id}
            )

        
        # 4. Optional: Reset sequence if new_id is the latest
        await session.execute(text("SELECT setval('games_id_seq', (SELECT MAX(id) FROM games))"))
        
        await session.commit()
        print(f"SUCCESS: Game {old_id} is now Game {new_id}.")

async def kick_player_command(game_id: int, user_id: int):
    async with UnitOfWork() as uow:
        print(f"Kicking player {user_id} from Game #{game_id}...")
        
        service = RosterService(uow)
        
        success, msg, promoted = await service.leave_player(game_id, user_id, is_admin=True)
        
        if success:
            print(f"Success: {msg}")
            if promoted:
                print(f"Promoted user: {promoted.full_name} ({promoted.user_id})")
            await uow.commit()
        else:
            print(f"Failed: {msg}")

if __name__ == "__main__":
    pass # Managed by manage.py
