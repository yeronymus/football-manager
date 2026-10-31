import logging
import time

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import GuestAddition
from app.bot.i18n import t
from app.bot.keyboards import get_primary_select_keyboard
from app.config import settings
from app.core.uow import UnitOfWork
from app.db.models import Signup, User, SignupStatus, Position

logger = logging.getLogger(__name__)

router = Router()


def _get_lang(message_or_callback: types.TelegramObject) -> str:
    from_user = getattr(message_or_callback, "from_user", None)
    if from_user and from_user.language_code and not from_user.language_code.startswith("ru"):
        return "en"
    return "ru"


@router.message(Command("create"))
async def cmd_create(message: types.Message):
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return

    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    web_app_url = f"{settings.webapp_url.rstrip('/')}/web/index.html?v={settings.webapp_version}"
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=t("btn_create_new_game", locale=user_lang),
                    web_app=types.WebAppInfo(url=web_app_url),
                )
            ]
        ]
    )

    await message.answer(
        t("cmd_create_prompt", locale=user_lang),
        reply_markup=kb,
    )


@router.message(Command("dashboard"))
async def cmd_dashboard(message: types.Message, session: AsyncSession, _=t):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        from app.db.models import ChatAdmin
        res = await session.execute(select(ChatAdmin).where(ChatAdmin.user_id == message.from_user.id))
        is_admin = res.first() is not None

        user_res = await session.execute(select(User).where(User.user_id == message.from_user.id))
        user = user_res.scalar_one_or_none()
        is_super = user and getattr(user, "is_superadmin", False)

        if not (is_admin or is_super):
            return

    try:
        webapp_url = f"{settings.webapp_url.rstrip('/')}/web/admin.html?v={settings.webapp_version}"
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=_("btn_open_dashboard"),
                        web_app=types.WebAppInfo(url=webapp_url),
                    )
                ]
            ]
        )

        await message.answer(_("dashboard_welcome"), reply_markup=kb)
    except Exception as e:
        logger.error(f"Dashboard Command Error: {e}")
        await message.answer(f"Error: {e}")


@router.message(Command("force_refresh"))
async def cmd_force_refresh(message: types.Message, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer(t("force_refresh_usage", locale=user_lang), parse_mode="Markdown")
            return

        game_id = int(args[1])

        from app.bot.listeners import update_game_ui
        await update_game_ui(game_id)

        await message.answer(t("force_refresh_done", locale=user_lang))

    except ValueError:
        await message.answer(t("game_id_must_be_number", locale=user_lang))
    except Exception as e:
        logger.error(f"Force refresh error: {e}")
        await message.answer(f"❌ Error: {e}")


@router.message(Command("republish"))
async def cmd_republish(message: types.Message, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer(t("republish_usage", locale=user_lang), parse_mode="Markdown")
            return

        game_id = int(args[1])

        from app.scheduler.tasks import publish_game_task
        await publish_game_task(game_id)

        await message.answer(t("republish_success", locale=user_lang, game_num=game_id))

    except ValueError:
        await message.answer(t("game_id_must_be_number", locale=user_lang))
    except Exception as e:
        logger.error(f"Republish error: {e}")
        await message.answer(f"❌ Error: {e}")


@router.message(Command("start_voting"))
async def cmd_start_voting(message: types.Message, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer(t("start_voting_usage", locale=user_lang), parse_mode="Markdown")
            return

        game_id = int(args[1])

        from app.scheduler.tasks import send_voting_message
        await send_voting_message(game_id)

        await message.answer(t("voting_triggered_success", locale=user_lang, game_num=game_id))

    except ValueError:
        await message.answer(t("game_id_must_be_number", locale=user_lang))
    except Exception as e:
        logger.error(f"Manual voting trigger error: {e}")
        await message.answer(f"❌ Error: {e}")


@router.message(Command("add_player"))
async def cmd_add_player(message: types.Message, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    args = message.text.split()
    if len(args) != 3:
        await message.answer(t("add_player_usage", locale=user_lang), parse_mode="Markdown")
        return

    try:
        game_id = int(args[1])
        user_input = args[2]

        target_user = None

        if user_input.isdigit():
            target_user = await session.get(User, int(user_input))

        if not target_user:
            await message.answer(t("user_not_found_db", locale=user_lang, user=user_input))
            return

        from app.core.services.roster import RosterService

        async with UnitOfWork() as uow:
            service = RosterService(uow)
            result = await service.join_player(game_id, target_user, ignore_limit=True)

            if result.success:
                await uow.commit()

        if result.success:
            await message.answer(
                t(
                    "player_added_success",
                    locale=user_lang,
                    name=target_user.full_name,
                    game_id=game_id,
                    message=result.message,
                )
            )
            try:
                target_lang = "ru"
                if target_user and getattr(target_user, "language", None):
                    target_lang = (
                        target_user.language.value
                        if hasattr(target_user.language, "value")
                        else str(target_user.language)
                    )
                await message.bot.send_message(
                    target_user.user_id,
                    t("admin_added_you_msg", locale=target_lang, game_id=game_id),
                )
            except Exception:
                pass

            from app.core.events import event_bus
            from app.core.services.roster import PlayerJoinedEvent

            if result.signup:
                await event_bus.publish(
                    PlayerJoinedEvent(
                        game_id=game_id,
                        user_id=target_user.user_id,
                        signup=result.signup,
                        is_reserve=result.is_reserve,
                        message=result.message,
                    )
                )
        else:
            await message.answer(t("player_add_failed", locale=user_lang, message=result.message))

    except Exception as e:
        logger.error(f"Add Player Error: {e}")
        await message.answer(f"❌ Error: {e}")


# --- Guest Addition Flow ---


@router.message(GuestAddition.waiting_for_name)
async def process_guest_name(message: types.Message, state: FSMContext):
    user_lang = _get_lang(message)
    name = message.text.strip()
    if not name:
        await message.answer(t("guest_name_empty", locale=user_lang))
        return

    await state.update_data(guest_name=name)
    await state.set_state(GuestAddition.waiting_for_position)

    await message.answer(
        t("guest_choose_pos", locale=user_lang, name=name),
        reply_markup=get_primary_select_keyboard([pos.value for pos in Position]),
        parse_mode="HTML",
    )


@router.callback_query(GuestAddition.waiting_for_position, F.data.startswith("primary_"))
async def process_guest_position(
    callback: types.CallbackQuery, state: FSMContext, session: AsyncSession
):
    user_lang = _get_lang(callback)
    data = await state.get_data()
    game_id = data.get("guest_game_id")
    name = data.get("guest_name")
    primary_str = callback.data.split("_")[1]

    if not game_id or not name:
        await callback.answer(t("guest_data_error", locale=user_lang))
        await state.clear()
        return

    guest_id = -int(time.time() * 1000)

    try:
        new_guest = User(
            user_id=guest_id,
            full_name=f"{name} (Guest)",
            username=None,
            player_position=Position(primary_str),
            rating=100,
        )
        session.add(new_guest)

        new_signup = Signup(
            game_id=game_id,
            user_id=guest_id,
            status=SignupStatus.ACTIVE,
        )
        session.add(new_signup)

        await session.commit()

        await callback.message.edit_text(
            t("guest_added_success", locale=user_lang, name=name, game_id=game_id),
            parse_mode="HTML",
        )
        await state.clear()

        from app.bot.listeners import update_game_ui
        await update_game_ui(game_id)

    except Exception as e:
        logger.error(f"Bot Guest Addition Error: {e}")
        await session.rollback()
        await callback.message.answer(t("guest_add_error", locale=user_lang, error=str(e)))
        await state.clear()


@router.callback_query(GuestAddition.waiting_for_position, F.data == "delete_msg")
async def cancel_guest_addition(callback: types.CallbackQuery, state: FSMContext):
    user_lang = _get_lang(callback)
    await state.clear()
    await callback.message.delete()
    await callback.answer(t("guest_cancelled", locale=user_lang))


@router.message(Command("promote"))
async def cmd_promote_admin(message: types.Message, session: AsyncSession):
    if (
        message.from_user.id not in settings.admin_ids
        and message.from_user.id != settings.system_owner_id
    ):
        return

    user_lang = _get_lang(message)
    parts = message.text.split()
    if message.chat.type == "private":
        if len(parts) != 3:
            await message.answer(t("promote_usage_private", locale=user_lang), parse_mode="Markdown")
            return
        chat_id = int(parts[2])
    else:
        if len(parts) != 2:
            await message.answer(t("promote_usage_group", locale=user_lang))
            return
        chat_id = message.chat.id

    try:
        target_uid = int(parts[1])

        from app.db.models import ChatAdmin

        res = await session.execute(
            select(ChatAdmin).where(ChatAdmin.user_id == target_uid, ChatAdmin.chat_id == chat_id)
        )
        if res.first():
            await message.answer(t("already_admin", locale=user_lang))
            return

        ca = ChatAdmin(user_id=target_uid, chat_id=chat_id, can_edit_settings=True)
        session.add(ca)
        await session.commit()

        await message.answer(
            t("promoted_admin_success", locale=user_lang, user_id=target_uid, chat_id=chat_id)
        )
    except ValueError:
        await message.answer(t("ids_must_be_numbers", locale=user_lang))
    except Exception as e:
        await message.answer(f"Error: {e}")
