from typing import Any
import html
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.models import Chat, ChatAdmin, Language

router = Router()

class SetupState(StatesGroup):
    waiting_for_payment_info = State()
    waiting_for_location = State()
    waiting_for_price = State()

async def is_user_chat_admin(session: AsyncSession, user_id: int, chat_id: int) -> bool:
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return True
    
    result = await session.execute(
        select(ChatAdmin).where(ChatAdmin.user_id == user_id, ChatAdmin.chat_id == chat_id)
    )
    admin = result.scalar_one_or_none()
    return admin is not None and admin.can_edit_settings

def format_setup_text(tenant: Chat) -> str:
    lang_val = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).upper()
    is_en = (lang_val == "EN")
    
    loc_val = html.escape(tenant.default_location) if tenant.default_location else ("Not set" if is_en else "Не указан")
    pay_val = f"<code>{html.escape(tenant.payment_info)}</code>" if tenant.payment_info else ("Not set" if is_en else "Не указаны")
    price_val = f"{tenant.default_price or 100} {'CZK' if is_en else 'крон'}"
    
    if is_en:
        return (
            f"⚙️ <b>Group Settings</b>\n\n"
            f"🌐 <b>Language:</b> {lang_val}\n"
            f"📍 <b>Default location:</b> {loc_val}\n"
            f"💰 <b>Default fee:</b> {price_val}\n"
            f"💳 <b>Payment details:</b> {pay_val}\n\n"
            f"Select what you want to change:"
        )
    else:
        return (
            f"⚙️ <b>Настройки группы</b>\n\n"
            f"🌐 <b>Язык:</b> {lang_val}\n"
            f"📍 <b>Адрес по умолчанию:</b> {loc_val}\n"
            f"💰 <b>Взнос по умолчанию:</b> {price_val}\n"
            f"💳 <b>Реквизиты:</b> {pay_val}\n\n"
            f"Выберите, что хотите изменить:"
        )

def get_setup_keyboard(current_lang: str = "en"):
    lang_upper = str(current_lang).upper()
    is_en = (lang_upper == "EN")
    btn_en = "✅ 🇬🇧 EN" if is_en else "🇬🇧 EN"
    btn_ru = "✅ 🇷🇺 RU" if not is_en else "🇷🇺 RU"
    btn_loc = "📍 " + ("Change Location" if is_en else "Изменить адрес")
    btn_price = "💰 " + ("Change Match Fee" if is_en else "Изменить взнос")
    btn_pay = "💳 " + ("Change Payment Details" if is_en else "Изменить реквизиты")
    btn_close = "❌ " + ("Close" if is_en else "Закрыть")
    
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text=btn_en, callback_data="setlang_en"),
            types.InlineKeyboardButton(text=btn_ru, callback_data="setlang_ru")
        ],
        [
            types.InlineKeyboardButton(text=btn_loc, callback_data="setup_location"),
            types.InlineKeyboardButton(text=btn_price, callback_data="setup_price")
        ],
        [
            types.InlineKeyboardButton(text=btn_pay, callback_data="setup_payment")
        ],
        [
            types.InlineKeyboardButton(text=btn_close, callback_data="setup_close")
        ]
    ])

@router.message(Command("setup"))
async def cmd_setup(message: types.Message, session: AsyncSession, tenant: Chat, _):
    if message.chat.type == "private":
        await message.answer(_("setup_group_only"))
        return
        
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await message.answer(_("setup_only_admins"))
        return

    lang_val = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).upper()
    text = format_setup_text(tenant)
    await message.answer(text, reply_markup=get_setup_keyboard(lang_val), parse_mode="HTML")

@router.callback_query(F.data.startswith("setlang_"))
async def process_setlang(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return

    lang = callback.data.split("_")[1].lower()
    tenant.language = Language(lang)
    await session.commit()
    
    msg_text = format_setup_text(tenant)

    await callback.message.edit_text(
        msg_text,
        reply_markup=get_setup_keyboard(lang),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "setup_location")
async def process_setup_location(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return
        
    await state.set_state(SetupState.waiting_for_location)
    is_en = (str(tenant.language or "en").lower() == "en")
    prompt = (
        "Send the default pitch/stadium address for this group.\n\n"
        "<i>Example: Stadion Strahov, Vaníčkova 100/2</i>\n\n"
        "(Send <code>-</code> to clear default location)"
        if is_en else
        "Отправьте адрес стадиона или площадки по умолчанию для этой группы.\n\n"
        "<i>Например: Stadion Strahov, Vaníčkova 100/2</i>\n\n"
        "(Отправьте <code>-</code>, чтобы сбросить адрес)"
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()

@router.message(SetupState.waiting_for_location)
async def process_location_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    text = message.text.strip()
    is_en = (str(tenant.language or "en").lower() == "en")

    if text == "-":
        tenant.default_location = None
        saved_display = "Cleared" if is_en else "Сброшено"
    else:
        tenant.default_location = text[:200]
        saved_display = tenant.default_location

    await session.commit()
    await state.clear()

    msg = (
        f"✅ Default location updated:\n<b>{html.escape(saved_display)}</b>"
        if is_en else
        f"✅ Адрес по умолчанию обновлен:\n<b>{html.escape(saved_display)}</b>"
    )
    await message.answer(msg, parse_mode="HTML")

@router.callback_query(F.data == "setup_price")
async def process_setup_price(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return
        
    await state.set_state(SetupState.waiting_for_price)
    is_en = (str(tenant.language or "en").lower() == "en")
    prompt = (
        "Send the default match fee in CZK (number only).\n\n"
        "<i>Example: 100</i>"
        if is_en else
        "Отправьте взнос по умолчанию в кронах (только число).\n\n"
        "<i>Например: 100</i>"
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()

@router.message(SetupState.waiting_for_price)
async def process_price_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    is_en = (str(tenant.language or "en").lower() == "en")
    try:
        val = int(message.text.strip())
        if val < 0 or val > 100000:
            raise ValueError()
    except ValueError:
        err = "Please enter a valid positive number." if is_en else "Пожалуйста, введите корректное положительное число."
        await message.answer(err)
        return

    tenant.default_price = val
    await session.commit()
    await state.clear()

    currency = "CZK" if is_en else "крон"
    msg = (
        f"✅ Default match fee updated: <b>{val} {currency}</b>"
        if is_en else
        f"✅ Взнос по умолчанию обновлен: <b>{val} {currency}</b>"
    )
    await message.answer(msg, parse_mode="HTML")

@router.callback_query(F.data == "setup_payment")
async def process_setup_payment(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return
        
    await state.set_state(SetupState.waiting_for_payment_info)
    
    is_en = (str(tenant.language or "en").lower() == "en")
    prompt = (
        "Send new payment details for this group.\n\n"
        "<i>Example: 123456789/0800 (Revolut)</i>\n\n"
        "(Send <code>-</code> to clear payment details)"
        if is_en else
        "Отправьте новые реквизиты для оплаты в эту группу.\n\n"
        "<i>Например: 123456789/0800 (Revolut)</i>\n\n"
        "(Отправьте <code>-</code>, чтобы сбросить реквизиты)"
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()

@router.message(SetupState.waiting_for_payment_info)
async def process_payment_info_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    text = message.text.strip()
    is_en = (str(tenant.language or "en").lower() == "en")

    if text == "-":
        tenant.payment_info = None
        saved_display = "Cleared" if is_en else "Сброшено"
    else:
        tenant.payment_info = text[:100]
        saved_display = tenant.payment_info

    await session.commit()
    await state.clear()

    msg = (
        f"✅ Payment details updated:\n<code>{html.escape(saved_display)}</code>"
        if is_en else
        f"✅ Реквизиты обновлены:\n<code>{html.escape(saved_display)}</code>"
    )
    await message.answer(msg, parse_mode="HTML")

@router.callback_query(F.data == "setup_close")
async def process_setup_close(callback: types.CallbackQuery, session: AsyncSession):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        return
    await callback.message.delete()
