import datetime
import html
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.core.i18n import normalize_locale_code, t
from app.core.repositories.disciplinary_repository import DisciplinaryRepository
from app.core.services.audit import record_audit_log
from app.core.timezone import format_prague_dt
from app.db.database import get_session
from app.db.models import Chat, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard-disciplinary"])


def _dash():
    import app.api.routers.dashboard as dash_mod

    return dash_mod


class IssueCardIn(BaseModel):
    card_type: str
    weeks: int = 4
    reason: Optional[str] = None


@router.post("/groups/{chat_id}/players/{target_user_id}/card")
async def issue_player_card(
    chat_id: int,
    target_user_id: int,
    data: IssueCardIn,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    await _dash().check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")

    target_user = await session.get(User, target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Player not found")

    card_type = data.card_type.upper()
    if card_type not in ["YELLOW", "RED"]:
        raise HTTPException(
            status_code=400, detail="Invalid card_type. Must be YELLOW or RED."
        )

    if data.weeks < 1:
        raise HTTPException(status_code=400, detail="Duration must be at least 1 week.")

    disc_repo = DisciplinaryRepository(session)
    card = await disc_repo.issue_card(
        user_id=target_user_id,
        chat_id=chat_id,
        card_type=card_type,
        weeks=data.weeks,
        reason=data.reason,
        issued_by=user_id,
    )
    record_audit_log(
        session,
        action="DISCIPLINARY_CARD_ISSUED",
        actor_user_id=user_id,
        chat_id=chat_id,
        target_type="user",
        target_id=target_user_id,
        payload={"card_type": card_type, "weeks": data.weeks, "reason": data.reason},
    )
    await session.commit()
    await session.refresh(card)

    dm_status = "delivered"
    try:
        from app.bot.instance import bot

        exp_prague = format_prague_dt(card.expires_at, "%d.%m.%Y")
        group_title = chat.title or "Football Group"
        is_red = card_type == "RED"

        target_lang = normalize_locale_code(
            getattr(target_user, "language", None), default="en"
        )

        reason_str = html.escape(card.reason) if card.reason else None
        reason_line = (
            t("card_reason_line", locale=target_lang, reason=reason_str)
            if reason_str
            else ""
        )
        card_title = t(
            "card_red_title" if is_red else "card_yellow_title", locale=target_lang
        )
        effect_txt = t(
            "card_notice_red_effect" if is_red else "card_notice_yellow_effect",
            locale=target_lang,
        )

        msg = t(
            "card_dm_issued",
            locale=target_lang,
            card_title=card_title,
            group_title=html.escape(group_title),
            weeks=data.weeks,
            exp_date=exp_prague,
            reason_line=reason_line,
            effect_text=effect_txt,
        )

        await bot.send_message(target_user_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Failed to DM card notice to {target_user_id}: {e}")
        dm_status = "failed"

    days_left = max(0, (card.expires_at.date() - datetime.date.today()).days)
    admin_user = await session.get(User, user_id)
    return {
        "status": "ok",
        "card": {
            "id": card.id,
            "card_type": card.card_type,
            "weeks": card.weeks,
            "reason": card.reason,
            "issued_at": card.issued_at.isoformat(),
            "expires_at": card.expires_at.isoformat(),
            "days_left": days_left,
            "issued_by_name": admin_user.full_name if admin_user else None,
        },
        "dm_status": dm_status,
    }


@router.delete("/groups/{chat_id}/players/{target_user_id}/card")
async def revoke_player_card(
    chat_id: int,
    target_user_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    await _dash().check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")

    disc_repo = DisciplinaryRepository(session)
    revoked_count = await disc_repo.revoke_active_cards(target_user_id, chat_id)
    await session.commit()

    if revoked_count > 0:
        try:
            from app.bot.instance import bot

            target_user = await session.get(User, target_user_id)
            target_lang = normalize_locale_code(
                getattr(target_user, "language", None) if target_user else None,
                default="en",
            )
            group_title = chat.title or "Football Group"
            msg = t(
                "card_dm_revoked",
                locale=target_lang,
                group_title=html.escape(group_title),
            )
            await bot.send_message(target_user_id, msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to DM card lift notice to {target_user_id}: {e}")

    return {"status": "ok", "message": "Card revoked successfully"}
