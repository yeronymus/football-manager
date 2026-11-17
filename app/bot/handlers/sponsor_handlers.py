import html
import logging
from typing import Callable

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import t
from app.core.services.sponsor_service import (
    get_sponsor_by_id,
    get_sponsor_for_chat,
    notify_owner_of_mvp_reward,
)
from app.db.models import ChatMember, User

logger = logging.getLogger(__name__)
router = Router()


class SponsorLoyaltyState(StatesGroup):
    waiting_for_card_name = State()


async def _upsert_loyalty_card_name(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    loyalty_name: str,
) -> None:
    cm = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id,
        )
    )
    if cm is None:
        user = await session.get(User, user_id)
        cm = ChatMember(
            chat_id=chat_id,
            user_id=user_id,
            username=user.username if user else None,
            full_name=user.full_name if user else loyalty_name,
            status="member",
            is_registered=bool(user and not getattr(user, "is_guest", False)),
            loyalty_card_id=loyalty_name,
        )
        session.add(cm)
    else:
        cm.loyalty_card_id = loyalty_name
    await session.commit()


@router.callback_query(F.data.startswith("mvp_loyalty_confirm:"))
async def on_mvp_loyalty_confirm(
    callback: types.CallbackQuery,
    session: AsyncSession,
    _: Callable[..., str] = t,
) -> None:
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Invalid data", show_alert=True)
        return

    chat_id = int(parts[1])
    game_num = int(parts[2])
    sponsor_id = parts[3]
    user_id = callback.from_user.id

    user = await session.get(User, user_id)
    loyalty_name = (
        (user.full_name if user and user.full_name else None)
        or callback.from_user.full_name
        or f"Player {user_id}"
    ).strip()[:128]
    lang = (getattr(user, "language", None) or "ru") if user else "ru"

    await _upsert_loyalty_card_name(session, chat_id, user_id, loyalty_name)

    sponsor = get_sponsor_by_id(sponsor_id) or get_sponsor_for_chat(chat_id)
    if sponsor:
        await notify_owner_of_mvp_reward(
            bot=callback.bot,
            session=session,
            chat_id=chat_id,
            game_num=game_num,
            player_user_id=user_id,
            loyalty_name=loyalty_name,
            sponsor=sponsor,
        )

    done_text = _(
        "mvp_coffee_saved_and_notified",
        locale=lang,
        sponsor_name=html.escape(sponsor.name if sponsor else "21 Coffee"),
        loyalty_name=html.escape(loyalty_name),
    )
    try:
        await callback.message.edit_text(done_text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(done_text, parse_mode="HTML")
    await callback.answer("✅")


@router.callback_query(F.data.startswith("mvp_loyalty_rename:"))
async def on_mvp_loyalty_rename(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    _: Callable[..., str] = t,
) -> None:
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Invalid data", show_alert=True)
        return

    chat_id = int(parts[1])
    game_num = int(parts[2])
    sponsor_id = parts[3]

    user = await session.get(User, callback.from_user.id)
    lang = (getattr(user, "language", None) or "ru") if user else "ru"

    await state.set_state(SponsorLoyaltyState.waiting_for_card_name)
    await state.update_data(
        loyalty_chat_id=chat_id,
        loyalty_game_num=game_num,
        loyalty_sponsor_id=sponsor_id,
    )
    await callback.message.answer(
        _("mvp_coffee_ask_name", locale=lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SponsorLoyaltyState.waiting_for_card_name, F.text)
async def on_mvp_loyalty_name_entered(
    message: types.Message,
    state: FSMContext,
    session: AsyncSession,
    _: Callable[..., str] = t,
) -> None:
    clean_name = (message.text or "").strip()[:128]
    if not clean_name or clean_name.startswith("/"):
        return

    data = await state.get_data()
    chat_id = int(data.get("loyalty_chat_id"))
    game_num = int(data.get("loyalty_game_num", 0))
    sponsor_id = str(data.get("loyalty_sponsor_id") or "21coffee")
    user_id = message.from_user.id

    user = await session.get(User, user_id)
    lang = (getattr(user, "language", None) or "ru") if user else "ru"

    await _upsert_loyalty_card_name(session, chat_id, user_id, clean_name)

    sponsor = get_sponsor_by_id(sponsor_id) or get_sponsor_for_chat(chat_id)
    if sponsor:
        await notify_owner_of_mvp_reward(
            bot=message.bot,
            session=session,
            chat_id=chat_id,
            game_num=game_num,
            player_user_id=user_id,
            loyalty_name=clean_name,
            sponsor=sponsor,
        )

    await state.clear()
    await message.answer(
        _(
            "mvp_coffee_saved_and_notified",
            locale=lang,
            sponsor_name=html.escape(sponsor.name if sponsor else "21 Coffee"),
            loyalty_name=html.escape(clean_name),
        ),
        parse_mode="HTML",
    )
