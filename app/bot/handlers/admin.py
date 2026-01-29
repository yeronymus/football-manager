from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Chat
from app.config import settings

router = Router()

# Listen for bot being added to a group or promoted
@router.my_chat_member(F.new_chat_member.status.in_({"member", "administrator", "creator"}))
async def on_chat_member_update(event: ChatMemberUpdated, session: AsyncSession):
    # Save chat to DB if bot is added
    chat = await session.get(Chat, event.chat.id)
    if not chat:
        chat = Chat(chat_id=event.chat.id, title=event.chat.title or "Unknown Chat")
        session.add(chat)
        await session.commit()

@router.message(Command("register_chat"))
@router.channel_post(Command("register_chat"))
async def cmd_register_chat(message: types.Message, session: AsyncSession):
    if message.is_automatic_forward:
        return

    # В каналах message.from_user может быть None.
    # Если это канал, мы считаем, что писать от имени канала может только админ.
    # Если это группа, проверяем ID юзера.
    if message.chat.type in ["group", "supergroup"]:
        if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
            return 
    elif message.chat.type == "channel":
        # В канале просто доверяем, так как постит админ
        pass
    else:
        # User is likely trying to register THEMSELVES, not a chat.
        await message.answer(
            "❌ <b>Ошибка команды</b>\n\n"
            "Команда `/register_chat` используется только для подключения <b>Группы</b> или <b>Канала</b>.\n\n"
            "👤 **Чтобы зарегистрироваться как Игрок:**\n"
            "Нажмите 👉 /start",
            parse_mode="HTML"
        )
        return

    chat = await session.get(Chat, message.chat.id)
    if not chat:
        chat = Chat(chat_id=message.chat.id, title=message.chat.title or "Unknown Chat")
        session.add(chat)
        await session.commit()
        await message.answer("✅ Чат успешно зарегистрирован! Теперь он появится в списке при создании игры.")
    else:
        await message.answer("✅ Чат уже зарегистрирован.")

@router.message(Command("chats"))
async def cmd_list_chats(message: types.Message, session: AsyncSession):
    if message.from_user.id not in settings.admin_ids and message.from_user.id != settings.system_owner_id:
        return

    result = await session.execute(select(Chat))
    chats = result.scalars().all()

    if not chats:
        await message.answer("Нет зарегистрированных чатов.")
        return

    text = "📢 **Зарегистрированные чаты:**\n\n"
    for chat in chats:
        text += f"▪️ <b>{chat.title}</b> (ID: <code>{chat.chat_id}</code>)\n"

    await message.answer(text)
