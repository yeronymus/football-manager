from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.base import BaseRepository
from app.db.models import PlayerCard


class DisciplinaryRepository(BaseRepository[PlayerCard]):
    """
    Repository for managing disciplinary Yellow and Red cards (`PlayerCard`) per tenant group.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, PlayerCard)

    async def get_active_card(self, user_id: int, chat_id: int) -> Optional[PlayerCard]:
        stmt = (
            select(PlayerCard)
            .where(
                PlayerCard.user_id == user_id,
                PlayerCard.chat_id == chat_id,
                PlayerCard.is_active == True,  # noqa: E712
                PlayerCard.expires_at > func.now(),
            )
            .order_by(PlayerCard.id.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def get_active_cards_map(self, chat_id: int) -> Dict[int, str]:
        res = await self.session.execute(
            select(PlayerCard.user_id, PlayerCard.card_type).where(
                PlayerCard.chat_id == chat_id,
                PlayerCard.is_active == True,  # noqa: E712
                PlayerCard.expires_at > func.now(),
            )
        )
        return {row[0]: row[1] for row in res.all()}

    async def issue_card(
        self,
        user_id: int,
        chat_id: int,
        card_type: str,
        weeks: int = 4,
        reason: Optional[str] = None,
        issued_by: Optional[int] = None,
    ) -> PlayerCard:
        await self.session.execute(
            update(PlayerCard)
            .where(
                PlayerCard.user_id == user_id,
                PlayerCard.chat_id == chat_id,
                PlayerCard.is_active == True,  # noqa: E712
            )
            .values(is_active=False)
        )

        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(weeks=weeks)

        card = PlayerCard(
            user_id=user_id,
            chat_id=chat_id,
            card_type=card_type.upper(),
            weeks=weeks,
            reason=reason.strip() if reason else None,
            issued_by=issued_by,
            issued_at=now_utc,
            expires_at=expires_at,
            is_active=True,
        )
        self.session.add(card)
        return card

    async def revoke_active_cards(self, user_id: int, chat_id: int) -> int:
        res = await self.session.execute(
            update(PlayerCard)
            .where(
                PlayerCard.user_id == user_id,
                PlayerCard.chat_id == chat_id,
                PlayerCard.is_active == True,  # noqa: E712
            )
            .values(is_active=False)
        )
        return int(res.rowcount or 0)
