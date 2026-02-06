import asyncio
import sys
import os

# Setup Path
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import Game, Signup, User, SignupStatus, Position

async def fix():
    async with async_session_maker() as session:
        game_id = 2
        game = await session.get(Game, game_id)
        if not game:
            print("Game 2 not found")
            return

        # Fetch ALL signups for this game (active + reserve)
        # We will re-sort them based on join time and recreate the list
        result = await session.execute(
            select(Signup, User)
            .join(User)
            .where(Signup.game_id == game_id)
            .order_by(Signup.created_at.asc()) # FIFO
        )
        all_signups = result.all()

        active_pole_count = 0
        active_gk_count = 0
        max_pole = 18 # (10v10 minus 2 reserved GK slots)
        
        print(f"Checking Game #{game.id} Roster Logic...")
        
        for signup, user in all_signups:
            is_gk = user.player_position == Position.GK
            
            if is_gk:
                # GKs are always active if under max_players
                if (active_pole_count + active_gk_count) < game.max_players:
                    signup.status = SignupStatus.ACTIVE
                    active_gk_count += 1
                    print(f"GK {user.full_name}: ACTIVE")
                else:
                    signup.status = SignupStatus.RESERVE
                    print(f"GK {user.full_name}: RESERVE (Full)")
            else:
                # Pole players
                if active_pole_count < max_pole:
                    signup.status = SignupStatus.ACTIVE
                    active_pole_count += 1
                    print(f"Pole {user.full_name}: ACTIVE ({active_pole_count}/18)")
                else:
                    signup.status = SignupStatus.RESERVE
                    print(f"Pole {user.full_name}: RESERVE")

        await session.commit()
        print("\nDatabase updated. Refreshing messages...")
        
        # Refresh messages
        from app.bot.main import bot
        from app.bot.utils import format_game_message
        from app.bot.keyboards import get_game_keyboard
        
        text = await format_game_message(game, session)
        kb = get_game_keyboard(game.id)
        
        # Note: We must update BOTH messages (Channel and Group)
        for chat_id, msg_id in [(game.chat_id, game.message_id), (game.channel_id, game.channel_message_id)]:
            if chat_id and msg_id:
                try:
                    await bot.edit_message_text(
                        chat_id=chat_id, 
                        message_id=msg_id, 
                        text=text, 
                        reply_markup=kb, 
                        parse_mode='HTML'
                    )
                    print(f"Successfully updated message in {chat_id}")
                except Exception as e:
                    print(f"Failed to update message in {chat_id}: {e}")

if __name__ == "__main__":
    asyncio.run(fix())
