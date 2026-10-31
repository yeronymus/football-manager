import re
from typing import Callable

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import Registration
from app.bot.i18n import t
from app.bot.keyboards import get_multiselect_keyboard, get_primary_select_keyboard, get_game_keyboard
from app.core.repositories.user_repository import UserRepository
from app.db.models import Game, Language

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


@router.message(Registration.waiting_for_name)
async def process_name(
    message: types.Message,
    state: FSMContext,
    _: Callable[..., str] = t,
):
    # Validation: Latin letters only
    if not re.match(r"^[a-zA-Z\s]+$", message.text):
        await message.answer(_("reg_enter_name"))
        return

    await state.update_data(full_name=message.text, alt_positions=[])
    await message.answer(_("reg_choose_alts"), reply_markup=get_multiselect_keyboard([]))
    await state.set_state(Registration.waiting_for_alt_positions)


@router.callback_query(Registration.waiting_for_alt_positions, F.data.startswith("toggle_"))
async def process_alt_position_toggle(callback: types.CallbackQuery, state: FSMContext):
    pos = callback.data.split("_")[1]
    data = await state.get_data()
    selected = data.get("alt_positions", [])

    if pos in selected:
        selected.remove(pos)
    else:
        selected.append(pos)

    await state.update_data(alt_positions=selected)
    await callback.message.edit_reply_markup(reply_markup=get_multiselect_keyboard(selected))
    await callback.answer()


@router.callback_query(Registration.waiting_for_alt_positions, F.data == "done_alt_pos")
async def process_alt_position_done(
    callback: types.CallbackQuery,
    state: FSMContext,
    _: Callable[..., str] = t,
):
    data = await state.get_data()
    selected = data.get("alt_positions", [])

    if not selected:
        await callback.answer(_("reg_choose_at_least_one"), show_alert=True)
        return

    await callback.message.edit_text(
        _("reg_choose_primary"),
        reply_markup=get_primary_select_keyboard(selected),
    )
    await state.set_state(Registration.waiting_for_position)


@router.callback_query(Registration.waiting_for_position, F.data.startswith("primary_"))
async def process_position(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    _: Callable[..., str] = t,
):
    position_value = callback.data.split("_")[1]
    user_data = await state.get_data()
    full_name = user_data["full_name"]
    alt_positions = user_data.get("alt_positions", [])
    pending_game_id = user_data.get("pending_game_id")

    if position_value in alt_positions:
        alt_positions.remove(position_value)

    # Save to DB via Repository
    user_repo = UserRepository(session)
    init_lang = (
        Language.ru
        if (not callback.from_user.language_code or callback.from_user.language_code.startswith("ru"))
        else Language.en
    )
    await user_repo.create_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=full_name,
        position=position_value,
        alt_positions=alt_positions,
        language=init_lang,
    )
    await session.commit()

    user_lang = init_lang.value if hasattr(init_lang, "value") else str(init_lang)

    full_pos_str = position_value
    if alt_positions:
        full_pos_str += f" ({', '.join(alt_positions)})"

    await callback.message.edit_text(
        t("reg_success", locale=user_lang, full_name=full_name, full_pos=full_pos_str)
    )
    await state.clear()

    # Redirect to pending game if any
    if pending_game_id:
        result = await session.execute(select(Game).where(Game.id == pending_game_id))
        game = result.scalar_one_or_none()
        if game:
            from app.bot.utils import format_game_message, resolve_chat_language

            match_lang = await resolve_chat_language(session, game.chat_id)
            text = await format_game_message(game, session, lang=match_lang)
            await callback.message.answer(
                text,
                reply_markup=get_game_keyboard(pending_game_id, lang=match_lang),
            )

            # TRIGGER DASHBOARD UPDATE
            try:
                from app.bot.admin_dashboard import update_dashboard_message

                await update_dashboard_message(callback.bot, game.id, session)
            except (ImportError, Exception):
                pass
        else:
            await callback.message.answer(t("reg_pending_game_not_found", locale=user_lang))
