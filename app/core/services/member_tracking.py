import logging
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, ChatAdmin, ChatMember, Position, User

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


async def sync_chat_admin_membership(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    full_name: Optional[str] = None,
    username: Optional[str] = None,
    is_admin: bool = True,
    commit: bool = True,
) -> None:
    """
    Synchronizes a user's ChatAdmin privilege row for self-service multi-tenant onboarding.
    When promoted to group admin/creator, ensures both User and ChatAdmin exist.
    When demoted or removed, revokes their ChatAdmin access for that tenant.
    """
    if user_id <= 0:
        return

    chat = await session.get(Chat, chat_id)
    if not chat:
        return

    if is_admin:
        user = await session.get(User, user_id)
        if not user:
            user = User(
                user_id=user_id,
                full_name=(full_name or username or f"Admin {user_id}")[:128],
                username=username,
                player_position=Position.PARTICIPANT,
                alt_positions=[],
                rating=100,
            )
            session.add(user)
            await session.flush()

        existing = await session.scalar(
            select(ChatAdmin).where(
                ChatAdmin.chat_id == chat_id,
                ChatAdmin.user_id == user_id,
            )
        )
        if not existing:
            session.add(
                ChatAdmin(
                    chat_id=chat_id,
                    user_id=user_id,
                    can_edit_settings=True,
                    can_manage_games=True,
                )
            )
    else:
        await session.execute(
            delete(ChatAdmin).where(
                ChatAdmin.chat_id == chat_id,
                ChatAdmin.user_id == user_id,
            )
        )

    if commit:
        await session.commit()


async def sync_group_admins_from_telegram(
    bot,
    session: AsyncSession,
    chat_id: int,
) -> int:
    """
    Fetches live administrators of a Telegram group and registers them in `chat_admins`
    so newly onboarded tenants can open the Admin Portal immediately without manual CLI setup.
    """
    try:
        admins = await bot.get_chat_administrators(chat_id)
    except Exception as e:
        logger.warning("Could not fetch chat administrators for %s: %s", chat_id, e)
        return 0

    synced = 0
    for member in admins:
        tg_user = getattr(member, "user", None)
        if not tg_user or getattr(tg_user, "is_bot", False):
            continue
        await sync_chat_admin_membership(
            session=session,
            chat_id=chat_id,
            user_id=tg_user.id,
            full_name=getattr(tg_user, "full_name", None),
            username=getattr(tg_user, "username", None),
            is_admin=True,
            commit=False,
        )
        synced += 1

    if synced:
        await session.commit()
    return synced
