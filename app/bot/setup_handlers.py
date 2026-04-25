from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.models import Chat, ChatAdmin
from app.core.uow import UnitOfWork

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

def get_setup_keyboard():
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="🇷🇺 RU", callback_data="setlang_ru"),
            types.InlineKeyboardButton(text="🇬🇧 EN", callback_data="setlang_en"),
            types.InlineKeyboardButton(text="🇨🇿 CS", callback_data="setlang_cs")
        ],
        [
            types.InlineKeyboardButton(text="💳 Изменить реквизиты", callback_data="setup_payment")
        ],
        [
            types.InlineKeyboardButton(text="❌ Закрыть", callback_data="setup_close")
        ]
    ])
    return builder

@router.message(Command("setup"))
async def cmd_setup(message: types.Message, session: AsyncSession, tenant: Chat, _):
    if message.chat.type == "private":
        await message.answer("Эта команда работает только в группах.")
        return
        
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await message.answer(_("Только администраторы могут настраивать группу!")) # fallback if not translated
        return

    text = (
        f"⚙️ <b>Настройки группы</b>\n\n"
        f"🗣 <b>Язык:</b> {tenant.language.upper()}\n"
        f"💳 <b>Реквизиты:</b> {tenant.payment_info or 'По умолчанию'}\n\n"
        f"Выберите, что хотите изменить:"
    )
    
    await message.answer(text, reply_markup=get_setup_keyboard(), parse_mode="HTML")

@router.callback_query(F.data.startswith("setlang_"))
async def process_setlang(callback: types.CallbackQuery, session: AsyncSession, tenant: Chat, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer("У вас нет прав!", show_alert=True)
        return

    lang = callback.data.split("_")[1]
    tenant.language = lang
    await session.commit()
    
    await callback.message.edit_text(
        f"✅ Язык группы успешно изменен на <b>{lang.upper()}</b>.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "setup_payment")
async def process_setup_payment(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, _):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    await state.set_state(SetupState.waiting_for_payment_info)
    await callback.message.answer(
        "Отправьте новые реквизиты для оплаты в эту группу.\n\n"
        "<i>Например: 123456789/0800 (Revolut)</i>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(SetupState.waiting_for_payment_info)
async def process_payment_info_input(message: types.Message, session: AsyncSession, tenant: Chat, state: FSMContext, _):
    if not await is_user_chat_admin(session, message.from_user.id, message.chat.id):
        await state.clear()
        return

    tenant.payment_info = message.text[:100] # simple limit
    await session.commit()
    
    await state.clear()
    await message.answer(f"✅ Новые реквизиты сохранены:\n<code>{tenant.payment_info}</code>", parse_mode="HTML")

@router.callback_query(F.data == "setup_close")
async def process_setup_close(callback: types.CallbackQuery, session: AsyncSession):
    if not await is_user_chat_admin(session, callback.from_user.id, callback.message.chat.id):
        return
    await callback.message.delete()
