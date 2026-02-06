
import asyncio
from app.bot.main import bot
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard

async def refresh():
    async with async_session_maker() as session:
        # Load Game 1
        result = await session.execute(select(Game).where(Game.id == 1))
        game = result.scalar_one_or_none()
        
        if not game:
            print("Game 1 not found")
            return

        chat_id = game.chat_id
        old_msg_id = game.message_id
        
        print(f"Refeshing Game 1 in Chat {chat_id}, Old Msg {old_msg_id}")
        
        # 1. Try to Delete Old
        if old_msg_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=old_msg_id)
                print("Deleted old message.")
            except Exception as e:
                print(f"Could not delete old message: {e}")
        
        # 2. Format & Send New
        try:
            text = await format_game_message(game, session)
            kb = get_game_keyboard(game.id)
            
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            print(f"Sent NEW message! ID: {msg.message_id}")
            
            # 3. Update DB
            game.message_id = msg.message_id
            await session.commit()
            print("DB Updated.")
            
        except Exception as e:
            print(f"FAILED to send new message: {e}")

if __name__ == "__main__":
    asyncio.run(refresh())
