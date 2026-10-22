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

async def is_user_chat_admin(session: AsyncSession, user_id: int, chat_id: int) -> bool:
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        return True
    
    result = await session.execute(
        select(ChatAdmin).where(ChatAdmin.user_id == user_id, ChatAdmin.chat_id == chat_id)
    )
    admin = result.scalar_one_or_none()
    return admin is not None and admin.can_edit_settings

def get_setup_keyboard(current_lang: str = "en"):
    lang_upper = str(current_lang).upper()
    is_en = (lang_upper == "EN")
    btn_en = "✅ 🇬🇧 EN" if is_en else "🇬🇧 EN"
    btn_ru = "✅ 🇷🇺 RU" if not is_en else "🇷🇺 RU"
    btn_pay = "💳 " + ("Change Payment Details" if is_en else "Изменить реквизиты")
    btn_close = "❌ " + ("Close" if is_en else "Закрыть")
    
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text=btn_en, callback_data="setlang_en"),
            types.InlineKeyboardButton(text=btn_ru, callback_data="setlang_ru")
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
    payment_val = tenant.payment_info or ("Default" if lang_val == "EN" else "По умолчанию")

    text = _("setup_title", lang=lang_val, payment=payment_val)
    
    await message.answer(text, reply_markup=get_setup_keyboard(lang_val), parse_mode="HTML")

@router.callback_query(F.data.startswith("setlang_"))
async def process_setlang(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return

    lang = callback.data.split("_")[1].lower()
    tenant.language = Language(lang)
    await session.commit()
    
    lang_name = "English" if lang == "en" else "Русском"
    msg_text = _("setup_lang_changed", lang=lang.upper(), lang_name=lang_name)

    await callback.message.edit_text(
        msg_text,
        reply_markup=get_setup_keyboard(lang),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "setup_payment")
async def process_setup_payment(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer(_("setup_only_admins"), show_alert=True)
        return
        
    await state.set_state(SetupState.waiting_for_payment_info)
    
    is_en = (str(tenant.language or "en").lower() == "en")
    prompt = (
        "Send new payment details for this group.\n\n<i>Example: 123456789/0800 (Revolut)</i>"
        if is_en else
        "Отправьте новые реквизиты для оплаты в эту группу.\n\n<i>Например: 123456789/0800 (Revolut)</i>"
    )
    await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()

@router.message(SetupState.waiting_for_payment_info)
async def process_payment_info_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    tenant.payment_info = message.text[:100] # simple limit
    await session.commit()
    await state.clear()

    is_en = (str(tenant.language or "en").lower() == "en")
    success_msg = (
        f"✅ New payment details saved:\n<code>{tenant.payment_info}</code>"
        if is_en else
        f"✅ Новые реквизиты сохранены:\n<code>{tenant.payment_info}</code>"
    )
    await message.answer(success_msg, parse_mode="HTML")

@router.callback_query(F.data == "setup_close")
async def process_setup_close(callback: types.CallbackQuery, session: AsyncSession):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        return
    await callback.message.delete()
