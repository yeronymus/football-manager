import logging
from aiogram import Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.member_tracking import track_chat_member

logger = logging.getLogger(__name__)

router = Router()


@router.chat_member()
async def on_chat_member_updated(
    event: types.ChatMemberUpdated,
    session: AsyncSession,
) -> None:
    """
    Listens for member joins, leaves, kicks, promotions, and demotions in groups.
    Automatically maintains real-time chat membership state in the database.
    """
    if not event.chat or event.chat.type not in ("group", "supergroup"):
        return

    tg_user = event.new_chat_member.user
    if tg_user.is_bot:
        return

    raw_status = event.new_chat_member.status
    if raw_status in ("left", "kicked"):
        member_status = raw_status
    elif raw_status in ("administrator", "creator"):
        member_status = "administrator"
    else:
        member_status = "member"

    try:
        await track_chat_member(
            session=session,
            chat_id=event.chat.id,
            user_id=tg_user.id,
            full_name=tg_user.full_name,
            username=tg_user.username,
            status=member_status,
        )
        logger.info(
            "Tracked chat_member update: chat=%s user=%s status=%s",
            event.chat.id,
            tg_user.id,
            member_status,
        )
    except Exception as e:
        logger.warning("Failed to track chat_member update: %s", e)
