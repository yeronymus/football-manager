import asyncio
import sys
import os
import argparse

# Setup Path
sys.path.append(os.getcwd())

from app.db.database import async_session_maker
from app.core.repositories.game_repo import GameRepository
from app.core.services.roster import RosterService
from app.db.models import Game

async def fix(game_id: int):
    from app.core.uow import UnitOfWork
    
    async with UnitOfWork() as uow:
        print(f"Fixing Roster for Game #{game_id}...")
        
        service = RosterService(uow)
        
        # 1. Recalculate
        success = await service.recalculate_roster(game_id)
        
        if not success:
            print("Failed to recalculate (Game not found?)")
            return
            
        await uow.commit()
        print("Database updated.")
        
        # 2. Refresh Messages
        print("Refreshing messages...")
        try:
            from app.bot.main import bot
            from app.bot.utils import format_game_message
            from app.bot.keyboards import get_game_keyboard
            
            game = await session.get(Game, game_id)
            if not game: return
            
            text = await format_game_message(game, session)
            kb = get_game_keyboard(game.id)
            
            # Update Chat
            if game.chat_id and game.message_id:
                try:
                    await bot.edit_message_text(
                         chat_id=game.chat_id,
                         message_id=game.message_id,
                         text=text,
                         reply_markup=kb,
                         parse_mode="HTML"
                    )
                    print(f"Chat message updated.")
                except Exception as e:
                    print(f"Chat update failed: {e}")

            # Update Channel
            if game.channel_id and game.channel_message_id:
                try:
                    await bot.edit_message_text(
                         chat_id=game.channel_id,
                         message_id=game.channel_message_id,
                         text=text,
                         reply_markup=kb,
                         parse_mode="HTML"
                    )
                    print(f"Channel message updated.")
                except Exception as e:
                    print(f"Channel update failed: {e}")
                    
        except Exception as e:
            print(f"Message refresh failed: {e}")


async def fix_roster_command(game_id: int):
    await fix(game_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix Game Roster")
    parser.add_argument("game_id", type=int, help="ID of the game to fix")
    args = parser.parse_args()
    
    asyncio.run(fix_roster_command(args.game_id))
