
import asyncio
import logging
from app.bot.main import bot
from app.db.database import async_session_maker
from app.db.models import Game
from sqlalchemy import select
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard

# Configure logging to file
logging.basicConfig(
    filename='/app/restore_log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

async def restore():
    print("Starting restoration...")
    logging.info("Starting restoration...")
    
    async with async_session_maker() as session:
        game_id = 1
        result = await session.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one_or_none()
        
        if not game:
            msg = "Game 1 not found."
            print(msg)
            logging.error(msg)
            return

        # Correct ID logic
        target_chat_id = -1003437568976
        logging.info(f"Target Chat ID: {target_chat_id}")
        
        # Format
        try:
            text = await format_game_message(game, session)
            kb = get_game_keyboard(game.id)
            
            # Send
            logging.info("Sending message...")
            sent_msg = await bot.send_message(
                chat_id=target_chat_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
            
            logging.info(f"Message sent! ID: {sent_msg.message_id}")
            print(f"Success: {sent_msg.message_id}")
            
            # Update DB
            game.chat_id = target_chat_id
            game.message_id = sent_msg.message_id
            await session.commit()
            logging.info("Database updated.")
            
        except Exception as e:
            logging.error(f"Error sending/updating: {e}")
            print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(restore())
    except Exception as e:
        # Fallback logging
        with open("/app/restore_log.txt", "a") as f:
            f.write(f"CRITICAL FAILURE: {e}\n")
