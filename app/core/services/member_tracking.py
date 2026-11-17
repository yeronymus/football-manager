import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, ChatMember, User

logger = logging.getLogger(__name__)


async def track_chat_member(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
    status: str = "member",
) -> None:
    """
    Upserts a group participant's observed membership and registration status.
    Ensures safe, thread-safe tracking with zero race conditions via ON CONFLICT DO UPDATE.
    """
    if user_id <= 0:
        return

    # Check if chat exists in our db to satisfy foreign key
    chat = await session.get(Chat, chat_id)
    if not chat:
        return

    # Check if this user is a registered non-guest in the platform
    reg_user = await session.scalar(
        select(User.user_id).where(User.user_id == user_id, User.is_guest == False)
    )
    is_registered = bool(reg_user is not None)

    stmt = insert(ChatMember).values(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        full_name=full_name,
        status=status,
        is_registered=is_registered,
        last_seen_at=func.now(),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_chat_members_chat_user",
        set_={
            "username": stmt.excluded.username,
            "full_name": stmt.excluded.full_name,
            "status": stmt.excluded.status,
            "is_registered": stmt.excluded.is_registered,
            "last_seen_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()


async def sync_registered_user_to_chat_members(
    session: AsyncSession,
    user_id: int,
    full_name: str,
    username: Optional[str] = None,
) -> None:
    """
    Marks existing ChatMember rows for this user as registered and ensures a PlayerProfile
    exists for each active group they belong to so they immediately appear in Squad & Activity.
    """
    from app.db.models import PlayerProfile

    res = await session.execute(
        select(ChatMember).where(ChatMember.user_id == user_id)
    )
    memberships = res.scalars().all()
    for cm in memberships:
        cm.is_registered = True
        if full_name:
            cm.full_name = full_name
        if username is not None:
            cm.username = username
        if cm.status not in ("left", "kicked"):
            existing_prof = await session.scalar(
                select(PlayerProfile).where(
                    PlayerProfile.user_id == user_id,
                    PlayerProfile.chat_id == cm.chat_id,
                )
            )
            if not existing_prof:
                session.add(PlayerProfile(user_id=user_id, chat_id=cm.chat_id, rating=100))
    await session.commit()
