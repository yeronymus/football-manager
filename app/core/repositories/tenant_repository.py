from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.base import BaseRepository
from app.db.models import Chat, ChatAdmin, User


class TenantRepository(BaseRepository[Chat]):
    """
    Repository for managing multi-tenant group chats (`Chat`) and tenant administrators (`ChatAdmin`).
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, Chat)

    async def get_tenant(self, chat_id: int) -> Optional[Chat]:
        return await self.session.get(Chat, chat_id)

    async def list_for_admin(self, user_id: int, is_superadmin: bool = False) -> List[Chat]:
        if is_superadmin:
            result = await self.session.execute(select(Chat))
            return list(result.scalars().all())
        result = await self.session.execute(
            select(Chat).join(ChatAdmin).where(ChatAdmin.user_id == user_id)
        )
        return list(result.scalars().all())

    async def is_chat_admin(self, chat_id: int, user_id: int) -> bool:
        stmt = select(ChatAdmin).where(
            ChatAdmin.chat_id == chat_id,
            ChatAdmin.user_id == user_id,
        )
        row = await self.session.scalar(stmt)
        return row is not None

    async def list_chat_admins(self, chat_id: int) -> List[Tuple[ChatAdmin, User]]:
        stmt = (
            select(ChatAdmin, User)
            .join(User, User.user_id == ChatAdmin.user_id)
            .where(ChatAdmin.chat_id == chat_id)
        )
        result = await self.session.execute(stmt)
        return list(result.all())
