
import asyncio
import os
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import Game
from app.bot.keyboards import get_game_keyboard

async def main():
    print("Starting script execution...", flush=True)
    # Setup DB
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Setup Bot
    bot = Bot(token=settings.bot_token)

    async with async_session() as session:
        # Fetch Game #1
        stmt = select(Game).where(Game.id == 1)
        result = await session.execute(stmt)
        game = result.scalar_one_or_none()

        if not game:
            print("Game #1 not found!")
            return

        print(f"Found Game #1: Chat {game.chat_id}, Message {game.message_id}")

        if not game.chat_id or not game.message_id:
            print("Game #1 does not have a message_id or chat_id set.")
            return

        # Generate new keyboard
        keyboard = get_game_keyboard(game.id)

        try:
            await bot.edit_message_reply_markup(
                chat_id=game.chat_id,
                message_id=game.message_id,
                reply_markup=keyboard
            )
            print("Successfully updated message markup!")
        except Exception as e:
            print(f"Failed to update message: {e}")
        finally:
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
