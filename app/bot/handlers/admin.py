from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.config import settings
from app.db.models import Chat

router = Router()


def _get_lang(message_or_event: types.TelegramObject) -> str:
    from_user = getattr(message_or_event, "from_user", None)
    if from_user and from_user.language_code and not from_user.language_code.startswith("ru"):
        return "en"
    return "ru"


# Listen for bot being added to a group or promoted
@router.my_chat_member(F.new_chat_member.status.in_({"member", "administrator", "creator"}))
async def on_chat_member_update(event: ChatMemberUpdated, session: AsyncSession):
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

    user_lang = _get_lang(message)

    if message.chat.type in ["group", "supergroup"]:
        if (
            message.from_user.id not in settings.admin_ids
            and message.from_user.id != settings.system_owner_id
        ):
            return
    elif message.chat.type == "channel":
        pass
    else:
        await message.answer(
            t("register_chat_error", locale=user_lang),
            parse_mode="HTML",
        )
        return

    chat = await session.get(Chat, message.chat.id)
    if not chat:
        chat = Chat(chat_id=message.chat.id, title=message.chat.title or "Unknown Chat")
        session.add(chat)
        await session.commit()
        await message.answer(t("chat_registered_success", locale=user_lang))
    else:
        await message.answer(t("chat_already_registered", locale=user_lang))


@router.message(Command("chats"))
async def cmd_list_chats(message: types.Message, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    result = await session.execute(select(Chat))
    chats = result.scalars().all()

    if not chats:
        await message.answer(t("no_registered_chats", locale=user_lang))
        return

    text = t("registered_chats_header", locale=user_lang)
    for chat in chats:
        text += f"▪️ <b>{chat.title}</b> (ID: <code>{chat.chat_id}</code>)\n"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("merge_users"))
async def cmd_merge_users(message: types.Message, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    args = message.text.split()
    if len(args) != 3:
        await message.answer(t("merge_usage", locale=user_lang), parse_mode="Markdown")
        return

    try:
        old_id = int(args[1])
        new_id = int(args[2])
    except ValueError:
        await message.answer(t("ids_must_be_numbers", locale=user_lang))
        return

    from app.core.repositories.user_repository import UserRepository

    repo = UserRepository(session)

    try:
        await repo.merge_users(old_id, new_id)
        await session.commit()
        await message.answer(t("merge_success", locale=user_lang, old_id=old_id, new_id=new_id))
    except Exception as e:
        await session.rollback()
        await message.answer(t("merge_error", locale=user_lang, error=str(e)))
