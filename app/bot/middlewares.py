from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.core.services.member_tracking import track_chat_member
from app.db.models import Chat, PlayerProfile, User


def is_auto_approved_tenant(actor_id: int | None) -> bool:
    """Resolve whether a newly discovered Telegram group should be immediately active."""
    if actor_id is not None and (
        actor_id == settings.system_owner_id or actor_id in settings.admin_ids
    ):
        return True
    return settings.registration_mode != "approval_required"


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session
            tg_user = getattr(event, "from_user", None)
            if tg_user and not getattr(tg_user, "is_bot", False):
                try:
                    db_user = await session.get(User, tg_user.id)
                    if db_user:
                        changed = False
                        current_username = tg_user.username
                        current_full_name = tg_user.full_name
                        if current_username is not None and db_user.username != current_username:
                            db_user.username = current_username
                            changed = True
                        if current_full_name and db_user.full_name != current_full_name:
                            db_user.full_name = current_full_name
                            changed = True
                        if changed:
                            await session.commit()
                except Exception:
                    pass
            return await handler(event, data)


class InstanceAccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if settings.allowed_users and event.from_user:
            if event.from_user.id not in settings.allowed_users:
                if isinstance(event, Message):
                    try:
                        await event.answer("Staging environment. Access denied.")
                    except Exception:
                        pass
                elif isinstance(event, CallbackQuery):
                    try:
                        await event.answer("Staging environment. Access denied.", show_alert=True)
                    except Exception:
                        pass
                return

        return await handler(event, data)


class TenantMiddleware(BaseMiddleware):
    """
    Multi-Tenant Onboarding & Context Middleware:
    1. Intercepts events in group chats.
    2. Ensures Chat settings exist in DB (honoring REGISTRATION_MODE: open_saas vs approval_required).
    3. Ensures PlayerProfile exists for the user in this Chat.
    4. Injects `tenant` (Chat) and `player` (PlayerProfile) into handler data.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if not session:
            return await handler(event, data)

        tg_chat = None
        tg_user = None

        if isinstance(event, Message):
            tg_chat = event.chat
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            if event.message:
                tg_chat = event.message.chat
            tg_user = event.from_user

        if not tg_chat or tg_chat.type == "private":
            return await handler(event, data)

        chat_id = tg_chat.id
        actor_id = tg_user.id if tg_user else None
        chat_obj = await session.get(Chat, chat_id)
        if not chat_obj:
            chat_obj = Chat(
                chat_id=chat_id,
                title=tg_chat.title or "Group",
                is_active=is_auto_approved_tenant(actor_id),
            )
            session.add(chat_obj)
            await session.commit()
        elif tg_chat.title and chat_obj.title != tg_chat.title:
            chat_obj.title = tg_chat.title
            await session.commit()

        data["tenant"] = chat_obj

        if tg_user and not getattr(tg_user, "is_bot", False):
            try:
                await track_chat_member(
                    session=session,
                    chat_id=chat_id,
                    user_id=tg_user.id,
                    full_name=tg_user.full_name,
                    username=tg_user.username,
                    status="member",
                )
            except Exception:
                pass

            user_obj = await session.get(User, tg_user.id)
            if user_obj:
                stmt = select(PlayerProfile).where(
                    PlayerProfile.user_id == tg_user.id,
                    PlayerProfile.chat_id == chat_id,
                )
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()

                if not profile:
                    profile = PlayerProfile(user_id=tg_user.id, chat_id=chat_id)
                    session.add(profile)
                    await session.commit()

                data["player"] = profile

        return await handler(event, data)
