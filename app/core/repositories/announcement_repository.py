from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.base import BaseRepository
from app.db.models import AdBanner


class AnnouncementRepository(BaseRepository[AdBanner]):
    """
    Repository for tenant and global announcements / sponsor banners (`AdBanner`).
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, AdBanner)

    async def list_active(self, chat_id: Optional[int] = None) -> List[AdBanner]:
        stmt = select(AdBanner).where(AdBanner.is_active == True)  # noqa: E712
        if chat_id is not None:
            stmt = stmt.where(or_(AdBanner.chat_id == chat_id, AdBanner.chat_id.is_(None)))
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
