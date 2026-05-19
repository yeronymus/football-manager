from aiogram import Router, F, types
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload
from app.db.models import Chat, Game, GameStatus
from app.config import settings

router = Router()



@router.message(Command("get_id"))
async def cmd_get_id(message: types.Message, session: AsyncSession):
    # Ensure chat exists in DB
    chat = await session.get(Chat, message.chat.id)
    if not chat:
        chat = Chat(chat_id=message.chat.id, title=message.chat.title or "Unknown")
        session.add(chat)
        await session.commit()
    await message.answer(f"🆔 ID этого чата: <code>{message.chat.id}</code>\nЧат зарегистрирован.")

@router.message(Command("debug_game"))
async def cmd_debug_game(message: types.Message, command: CommandObject, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids: return
    try:
        game_id = int(command.args)
    except:
        await message.answer("Usage: /debug_game <game_id>")
        return
    game = await session.get(Game, game_id)
    if not game:
        await message.answer("Game not found.")
        return
    chat = await session.get(Chat, game.chat_id)
    txt = f"🐞 **Debug Game #{game_id}**\nChat ID: `{game.chat_id}`\nTitle: {chat.title if chat else '?'}\nAdmin Msg: `{game.admin_message_id}`"
    await message.answer(txt, parse_mode="Markdown")

# Legacy Telegram dashboard functions and "God Mode" (chat linking) were removed in favor of the TMA Admin Dashboard.
