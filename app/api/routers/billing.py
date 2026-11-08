import datetime
import html
import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.core.domain.tenant_policy import BillingMode, resolve_billing_mode
from app.core.i18n import t
from app.core.repositories.signup_repository import SignupRepository
from app.core.services.game_numbering import get_group_game_number
from app.core.timezone import format_prague_dt
from app.db.database import get_session
from app.db.models import Chat, Game, Signup, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard-billing"])


def _dash():
    import app.api.routers.dashboard as dash_mod

    return dash_mod


@router.post("/signups/{signup_id}/toggle_pay")
async def toggle_payment(
    signup_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")

    game = await session.get(Game, signup.game_id)
    await _dash().check_admin_rights(game.chat_id, user_id)

    signup.is_paid = not signup.is_paid
    await session.commit()
    return {"status": "ok", "is_paid": signup.is_paid}


@router.post("/games/{game_id}/notify")
async def notify_player_payment(
    game_id: int,
    data: dict = Body(...),
    admin_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    target_user_id = data.get("user_id")
    if target_user_id is None:
        raise HTTPException(status_code=400, detail="Missing user_id")

    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, admin_id)

    now_str = datetime.datetime.now().strftime("%H:%M")

    if target_user_id < 0:
        log_entry = {"status": "guest", "time": now_str, "detail": "Гость (нет Telegram)"}
        await _dash().cache_service.set(
            f"notify_log:{game_id}:{target_user_id}", log_entry, ttl=86400 * 30
        )
        return {
            "status": "ok",
            "delivery": "guest",
            "time": now_str,
            "detail": "Игрок является гостем.",
        }

    await session.get(User, target_user_id)
    from app.bot.instance import bot
    from app.bot.utils import resolve_chat_language

    chat = await session.get(Chat, game.chat_id)
    if (
        chat
        and isinstance(chat, Chat)
        and resolve_billing_mode(getattr(chat, "billing_mode", None)) == BillingMode.FREE_CORPORATE
    ):
        raise HTTPException(
            status_code=400,
            detail="Payment reminders are disabled in Free / Corporate billing mode.",
        )

    chat_lang = await resolve_chat_language(session, game.chat_id)
    notif_lang = chat_lang or "en"
    currency = (getattr(chat, "currency", None) if isinstance(chat, Chat) else None) or "CZK"

    game_num = await get_group_game_number(session, game)
    date_str = format_prague_dt(game.date_time)
    pay_info = game.payment_info or ""

    fallback_pay = t("pm_payment_reminder_no_details", locale=notif_lang)
    pay_display = html.escape(pay_info) if pay_info else fallback_pay
    msg = t(
        "pm_payment_reminder",
        locale=notif_lang,
        game_num=game_num,
        location=html.escape(game.location),
        date=date_str,
        price=game.price,
        currency=currency,
        payment=pay_display,
    )

    try:
        await bot.send_message(target_user_id, msg, parse_mode="HTML")
        log_entry = {"status": "delivered", "time": now_str, "detail": "Доставлено в ЛС"}
        await _dash().cache_service.set(
            f"notify_log:{game_id}:{target_user_id}", log_entry, ttl=86400 * 30
        )
        return {"status": "ok", "delivery": "delivered", "time": now_str}
    except Exception as e:
        err_str = str(e)
        logger.warning(f"Failed to send payment reminder to {target_user_id}: {err_str}")
        is_blocked = any(
            x in err_str.lower()
            for x in ["blocked", "forbidden", "can't initiate", "chat not found"]
        )
        deliv_status = "blocked" if is_blocked else "error"
        log_entry = {"status": deliv_status, "time": now_str, "detail": err_str[:60]}
        await _dash().cache_service.set(
            f"notify_log:{game_id}:{target_user_id}", log_entry, ttl=86400 * 30
        )
        return {
            "status": "ok",
            "delivery": deliv_status,
            "time": now_str,
            "detail": err_str,
        }


@router.post("/games/{game_id}/notify_all_pm")
async def notify_all_unpaid_pm(
    game_id: int,
    admin_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Sends individual payment reminder DM to every active unpaid player.
    Updates the notify_log status cache for each player so feedback is recorded.
    """
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, admin_id)

    signup_repo = SignupRepository(session)
    unpaid_rows = await signup_repo.list_unpaid_active(game_id)

    if not unpaid_rows:
        return {
            "status": "ok",
            "total": 0,
            "delivered": 0,
            "blocked": 0,
            "guests": 0,
            "error": 0,
            "results": {},
        }

    from app.bot.instance import bot
    from app.bot.utils import resolve_chat_language

    chat = await session.get(Chat, game.chat_id)
    if (
        chat
        and isinstance(chat, Chat)
        and resolve_billing_mode(getattr(chat, "billing_mode", None)) == BillingMode.FREE_CORPORATE
    ):
        raise HTTPException(
            status_code=400,
            detail="Payment reminders are disabled in Free / Corporate billing mode.",
        )

    chat_lang = await resolve_chat_language(session, game.chat_id)
    notif_lang = chat_lang or "en"
    currency = (getattr(chat, "currency", None) if isinstance(chat, Chat) else None) or "CZK"

    game_num = await get_group_game_number(session, game)
    date_str = format_prague_dt(game.date_time)
    pay_info = game.payment_info or ""
    now_str = datetime.datetime.now().strftime("%H:%M")

    results = {}
    counts = {"delivered": 0, "blocked": 0, "guests": 0, "error": 0}

    for signup, user in unpaid_rows:
        target_uid = user.user_id
        if target_uid < 0:
            log_entry = {
                "status": "guest",
                "time": now_str,
                "detail": "Guest (no Telegram)",
            }
            await _dash().cache_service.set(
                f"notify_log:{game_id}:{target_uid}", log_entry, ttl=86400 * 30
            )
            results[str(target_uid)] = log_entry
            counts["guests"] += 1
            continue

        fallback_pay = t("pm_payment_reminder_no_details", locale=notif_lang)
        pay_display = html.escape(pay_info) if pay_info else fallback_pay
        msg = t(
            "pm_payment_reminder",
            locale=notif_lang,
            game_num=game_num,
            location=html.escape(game.location),
            date=date_str,
            price=game.price,
            currency=currency,
            payment=pay_display,
        )

        try:
            await bot.send_message(target_uid, msg, parse_mode="HTML")
            log_entry = {
                "status": "delivered",
                "time": now_str,
                "detail": "Доставлено в ЛС",
            }
            await _dash().cache_service.set(
                f"notify_log:{game_id}:{target_uid}", log_entry, ttl=86400 * 30
            )
            results[str(target_uid)] = log_entry
            counts["delivered"] += 1
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Batch PM reminder to {target_uid} failed: {err_str}")
            is_blocked = any(
                x in err_str.lower()
                for x in ["blocked", "forbidden", "can't initiate", "chat not found"]
            )
            deliv_status = "blocked" if is_blocked else "error"
            log_entry = {
                "status": deliv_status,
                "time": now_str,
                "detail": err_str[:60],
            }
            await _dash().cache_service.set(
                f"notify_log:{game_id}:{target_uid}", log_entry, ttl=86400 * 30
            )
            results[str(target_uid)] = log_entry
            counts[deliv_status] += 1

    return {
        "status": "ok",
        "total": len(unpaid_rows),
        "delivered": counts["delivered"],
        "blocked": counts["blocked"],
        "guests": counts["guests"],
        "error": counts["error"],
        "results": results,
    }


@router.post("/games/{game_id}/notify_group")
async def notify_group_unpaid(
    game_id: int,
    admin_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, admin_id)

    signup_repo = SignupRepository(session)
    unpaid_rows = await signup_repo.list_unpaid_active(game_id)

    if not unpaid_rows:
        return {"status": "ok", "unpaid_count": 0, "message": "all_paid"}

    chat = await session.get(Chat, game.chat_id)
    if (
        chat
        and isinstance(chat, Chat)
        and resolve_billing_mode(getattr(chat, "billing_mode", None)) == BillingMode.FREE_CORPORATE
    ):
        raise HTTPException(
            status_code=400,
            detail="Payment reminders are disabled in Free / Corporate billing mode.",
        )
    currency = (getattr(chat, "currency", None) if isinstance(chat, Chat) else None) or "CZK"

    from app.bot.instance import bot
    from app.bot.utils import resolve_chat_language

    chat_lang = await resolve_chat_language(session, game.chat_id)
    game_num = await get_group_game_number(session, game)
    date_str = format_prague_dt(game.date_time)
    pay_info = game.payment_info or ""

    guest_label = t("debtor_guest_label", locale=chat_lang)
    debtors_list = []
    for idx, (s, u) in enumerate(unpaid_rows, start=1):
        if u.user_id < 0:
            name_display = f"{html.escape(u.full_name)} ({guest_label})"
        elif u.username:
            name_display = f"@{u.username}"
        else:
            name_display = f'<a href="tg://user?id={u.user_id}">{html.escape(u.full_name)}</a>'
        debtors_list.append(f"{idx}. {name_display}")
    debtors_text = "\n".join(debtors_list)

    fallback_pay = t("group_payment_reminder_no_details", locale=chat_lang)
    pay_display = html.escape(pay_info) if pay_info else fallback_pay
    text = t(
        "group_payment_reminder",
        locale=chat_lang,
        game_num=game_num,
        location=html.escape(game.location),
        date=date_str,
        price=game.price,
        currency=currency,
        payment=pay_display,
        count=len(unpaid_rows),
        debtors=debtors_text,
    )

    try:
        await bot.send_message(chat_id=game.chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send group payment reminder for game {game_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to post to group: {str(e)}")

    now_str = datetime.datetime.now().strftime("%H:%M")
    await _dash().cache_service.set(
        f"notify_group_log:{game_id}",
        {"time": now_str, "unpaid_count": len(unpaid_rows)},
        ttl=86400 * 30,
    )
    return {"status": "ok", "unpaid_count": len(unpaid_rows), "time": now_str}
