from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from app.db.models import Chat, PlayerProfile, User
from sqlalchemy.ext.asyncio import async_sessionmaker

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
            return await handler(event, data)


from app.config import settings

class InstanceAccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Immobilizer disabled for production use
        # if settings.SYSTEM_OWNER_ID and event.from_user and event.from_user.id != settings.SYSTEM_OWNER_ID:
        #     return
            
        return await handler(event, data)

class TenantMiddleware(BaseMiddleware):
    """
    SaaS Middleware:
    1. Intercepts events in group chats.
    2. Ensures Chat settings exist in DB.
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
            # Pass through for private PMs (no tenant context here)
            return await handler(event, data)
            
        # 1. Provide/Create Chat (Tenant)
        chat_id = tg_chat.id
        chat_obj = await session.get(Chat, chat_id)
        if not chat_obj:
            chat_obj = Chat(chat_id=chat_id, title=tg_chat.title or "Group")
            session.add(chat_obj)
            await session.commit()
        elif tg_chat.title and chat_obj.title != tg_chat.title:
            chat_obj.title = tg_chat.title
            await session.commit()
            
        data["tenant"] = chat_obj
        
        # 2. Provide/Create PlayerProfile for current user
        if tg_user:
            user_obj = await session.get(User, tg_user.id)
            if user_obj:
                stmt = select(PlayerProfile).where(
                    PlayerProfile.user_id == tg_user.id, 
                    PlayerProfile.chat_id == chat_id
                )
                result = await session.execute(stmt)
                profile = result.scalar_one_or_none()
                
                if not profile:
                    profile = PlayerProfile(user_id=tg_user.id, chat_id=chat_id)
                    session.add(profile)
                    await session.commit()
                
                data["player"] = profile
        
        return await handler(event, data)
