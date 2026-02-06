
import asyncio
from app.bot.main import bot
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard

async def force_update():
    async with async_session_maker() as session:
        # Get the game (assuming ID=1 based on user links, or get latest)
        game_id = 1 
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if not game:
            print("Game 1 not found!")
            return

        print(f"Found Game {game.id}. Old Chat: {game.chat_id} | Old Msg: {game.message_id}")
        
        # FIX: Hardcode the Group Chat ID provided by user
        # Link: https://t.me/c/3437568976/794 -> -1003437568976
        target_chat_id = -1003437568976 
        
        # 1. Format Text
        text = await format_game_message(game, session)
        
        # 2. Send NEW Message
        try:
            msg = await bot.send_message(
                chat_id=target_chat_id,
                text=text,
                reply_markup=get_game_keyboard(game.id),
                parse_mode="HTML"
            )
            print(f"Sent NEW message to {target_chat_id}. ID: {msg.message_id}", flush=True)
            
            # 3. Update DB
            game.chat_id = target_chat_id
            game.message_id = msg.message_id
            await session.commit()
            print("DB Updated with new Chat/Msg ID.", flush=True)
            
        except Exception as e:
            print(f"Failed to send message: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(force_update())
