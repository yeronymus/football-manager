from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Chat, Game
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
    from app.bot.utils import resolve_chat_language
    from app.bot.i18n import t
    chat_lang = await resolve_chat_language(session, message.chat.id)
    await message.answer(t("cmd_get_id_response", locale=chat_lang, chat_id=message.chat.id), parse_mode="HTML")

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
