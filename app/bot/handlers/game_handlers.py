import logging
from typing import Any, Callable

from aiogram import F, Router, types

from app.bot.i18n import t
from app.config import settings
from app.core.events import event_bus
from app.core.i18n import normalize_locale_code
from app.core.services.roster import PlayerJoinedEvent, PlayerLeftEvent, RosterService
from app.core.uow import UnitOfWork

router = Router()


@router.callback_query(F.data.startswith("join_"))
async def process_join(callback: types.CallbackQuery, _: Callable[..., str] = t):
    game_id = int(callback.data.split("_")[1])
    tg_id = callback.from_user.id

    alert_msg = None
    event_payload = None

    try:
        async with UnitOfWork() as uow:
            user = await uow.user_repo.get_by_id(tg_id)

            if not user:
                bot_user = await callback.bot.get_me()
                await callback.answer(
                    _("need_registration_alert"),
                    url=f"https://t.me/{bot_user.username}?start=reg",
                )
                return

            service = RosterService(uow)
            is_admin = tg_id in settings.admin_ids or tg_id == settings.system_owner_id
            result = await service.join_player(game_id, user, ignore_limit=is_admin)

            if not result.success:
                await callback.answer(result.message, show_alert=True)
                return

            if result.success and not result.is_reserve:
                alert_msg = _("user_joined_success")
            elif result.success and result.is_reserve:
                alert_msg = _("user_joined_reserve")
            else:
                alert_msg = result.message

            if result.signup:
                event_payload = PlayerJoinedEvent(
                    game_id=game_id,
                    user_id=tg_id,
                    signup=result.signup,
                    is_reserve=result.is_reserve,
                    message=alert_msg,
                )

            await uow.commit()

        if event_payload:
            await event_bus.publish(event_payload)

        await callback.answer(alert_msg)

    except Exception as e:
        logging.error(f"Critical Join Error: {e}", exc_info=True)
        await callback.answer(_("system_error_alert"), show_alert=True)


@router.callback_query(F.data.startswith("leave_"))
async def process_leave(callback: types.CallbackQuery, _: Callable[..., str] = t):
    game_id = int(callback.data.split("_")[1])
    tg_id = callback.from_user.id
    is_admin = tg_id in settings.admin_ids or tg_id == settings.system_owner_id

    try:
        promoted_lang = "en"
        async with UnitOfWork() as uow:
            service = RosterService(uow)
            success, msg, promoted = await service.leave_player(game_id, tg_id, is_admin)

            if not success:
                await callback.answer(msg, show_alert=True)
                return

            if promoted and hasattr(uow, "user_repo"):
                try:
                    res: Any = uow.user_repo.get_by_id(promoted.user_id)
                    promoted_user = await res if hasattr(res, "__await__") else res
                    if promoted_user and hasattr(promoted_user, "language"):
                        promoted_lang = normalize_locale_code(
                            getattr(promoted_user, "language", None), default="en"
                        )
                except Exception:
                    pass

            await uow.commit()

        if promoted:
            try:
                await callback.bot.send_message(
                    promoted.user_id,
                    t("promoted_to_active_msg", locale=promoted_lang),
                )
            except Exception:
                pass

        await event_bus.publish(PlayerLeftEvent(game_id, tg_id, msg, promoted))
        await callback.answer(msg)

    except Exception as e:
        logging.error(f"Critical Leave Error: {e}", exc_info=True)
        await callback.answer(_("leave_error_alert"), show_alert=True)
