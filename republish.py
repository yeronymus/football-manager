import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session_maker
from app.db.models import Game
from app.bot.main import bot
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard

async def republish_game(game_id: int):
    async with async_session_maker() as session:
        game = await session.get(Game, game_id)
        if getattr(game, 'channel_id', None):
            # Send to channel
            text_full = await format_game_message(game, session, is_short=False)
            try:
                from app.bot.keyboards import get_channel_game_keyboard
                msg = await bot.send_message(
                    chat_id=game.channel_id,
                    text=text_full,
                    reply_markup=get_channel_game_keyboard(game.id),
                    parse_mode="HTML"
                )
                game.channel_message_id = msg.message_id
                print(f"Sent to channel {game.channel_id}, msg_id {msg.message_id}")
            except Exception as e:
                print(f"Failed to send to channel: {e}")
                
        text = await format_game_message(game, session, is_short=True)
        try:
            msg = await bot.send_message(
                chat_id=game.chat_id,
                text=text,
                reply_markup=get_game_keyboard(game.id),
                parse_mode="HTML"
            )
            game.message_id = msg.message_id
            print(f"Sent to group {game.chat_id}, msg_id {msg.message_id}")
            await session.commit()
        except Exception as e:
            print(f"Failed to send to group: {e}")

if __name__ == "__main__":
    asyncio.run(republish_game(9))
