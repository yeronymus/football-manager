from app.bot.i18n import t
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
    lang = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).lower()
    lang_val = lang.upper()
    
    loc_val = html.escape(tenant.default_location) if tenant.default_location else t("setup_not_set", locale=lang)
    pay_val = f"<code>{html.escape(tenant.payment_info)}</code>" if tenant.payment_info else t("setup_not_set", locale=lang)
    currency = t("setup_currency", locale=lang)
    price_val = f"{tenant.default_price or 100} {currency}"
    
    return (
        f"{t('setup_title_header', locale=lang)}\n\n"
        f"🌐 <b>{t('setup_lbl_lang', locale=lang)}:</b> {lang_val}\n"
        f"📍 <b>{t('setup_lbl_loc', locale=lang)}:</b> {loc_val}\n"
        f"💰 <b>{t('setup_lbl_fee', locale=lang)}:</b> {price_val}\n"
        f"💳 <b>{t('setup_lbl_pay', locale=lang)}:</b> {pay_val}\n\n"
        f"{t('setup_prompt_choose', locale=lang)}"
    )

def get_setup_keyboard(current_lang: str = "en"):
    lang = str(current_lang).lower()
    is_en = (lang == "en")
    btn_en = "✅ 🇬🇧 EN" if is_en else "🇬🇧 EN"
    btn_ru = "✅ 🇷🇺 RU" if not is_en else "🇷🇺 RU"
    btn_loc = t("setup_btn_loc", locale=lang)
    btn_price = t("setup_btn_price", locale=lang)
    btn_pay = t("setup_btn_payment", locale=lang)
    btn_close = t("setup_btn_close", locale=lang)
    
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
    lang = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).lower()
    prompt = t("setup_prompt_loc", locale=lang)
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()

@router.message(SetupState.waiting_for_location)
async def process_location_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    text = message.text.strip()
    lang = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).lower()

    if text == "-":
        tenant.default_location = None
        saved_display = t("setup_cleared", locale=lang)
    else:
        tenant.default_location = text[:200]
        saved_display = tenant.default_location

    await session.commit()
    await state.clear()

    msg = t("setup_saved_loc", locale=lang, loc=html.escape(saved_display))
    await message.answer(msg, parse_mode="HTML")

@router.callback_query(F.data == "setup_price")
async def process_setup_price(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return
        
    await state.set_state(SetupState.waiting_for_price)
    lang = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).lower()
    prompt = t("setup_prompt_price", locale=lang)
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()

@router.message(SetupState.waiting_for_price)
async def process_price_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    lang = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).lower()
    try:
        val = int(message.text.strip())
        if val < 0 or val > 100000:
            raise ValueError()
    except ValueError:
        err = t("setup_error_price", locale=lang)
        await message.answer(err)
        return

    tenant.default_price = val
    await session.commit()
    await state.clear()

    currency = t("setup_currency", locale=lang)
    msg = t("setup_saved_price", locale=lang, price=val, currency=currency)
    await message.answer(msg, parse_mode="HTML")

@router.callback_query(F.data == "setup_payment")
async def process_setup_payment(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return
        
    await state.set_state(SetupState.waiting_for_payment_info)
    
    lang = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).lower()
    prompt = t("setup_prompt_pay", locale=lang)
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()

@router.message(SetupState.waiting_for_payment_info)
async def process_payment_info_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    text = message.text.strip()
    lang = (tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language or "en")).lower()

    if text == "-":
        tenant.payment_info = None
        saved_display = t("setup_cleared", locale=lang)
    else:
        tenant.payment_info = text[:100]
        saved_display = tenant.payment_info

    await session.commit()
    await state.clear()

    msg = t("setup_saved_pay", locale=lang, pay=html.escape(saved_display))
    await message.answer(msg, parse_mode="HTML")

@router.callback_query(F.data == "setup_close")
async def process_setup_close(callback: types.CallbackQuery, session: AsyncSession):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        return
    await callback.message.delete()
