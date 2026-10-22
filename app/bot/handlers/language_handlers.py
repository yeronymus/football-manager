from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.models import User, Language, Chat
from app.core.repositories.user_repository import UserRepository
from app.bot.i18n import t

logger = logging.getLogger(__name__)

router = Router()

def get_language_selection_keyboard(current_lang: str = "en") -> InlineKeyboardMarkup:
    is_en = (current_lang == "en")
    btn_en = "✅ 🇬🇧 English" if is_en else "🇬🇧 English"
    btn_ru = "✅ 🇷🇺 Русский" if not is_en else "🇷🇺 Русский"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=btn_en, callback_data="userlang_en"),
            InlineKeyboardButton(text=btn_ru, callback_data="userlang_ru")
        ]
    ])

@router.message(Command("language"))
@router.message(Command("lang"))
async def cmd_language(message: types.Message, session: AsyncSession, _):
    """Command to choose language preference."""
    user_id = message.from_user.id
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    current_lang = "en"
    if user and user.language:
        current_lang = user.language.value if hasattr(user.language, "value") else str(user.language)
    elif message.from_user.language_code and message.from_user.language_code.startswith("ru"):
        current_lang = "ru"

    lang_display = "🇬🇧 English" if current_lang == "en" else "🇷🇺 Русский"
    text = _("lang_select_title", lang=lang_display)

    await message.answer(
        text,
        reply_markup=get_language_selection_keyboard(current_lang),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "change_user_lang")
async def cb_change_user_lang(callback: types.CallbackQuery, session: AsyncSession, _):
    """Called from Profile or Settings to change user language."""
    user_id = callback.from_user.id
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    current_lang = "en"
    if user and user.language:
        current_lang = user.language.value if hasattr(user.language, "value") else str(user.language)

    lang_display = "🇬🇧 English" if current_lang == "en" else "🇷🇺 Русский"
    text = _("lang_select_title", lang=lang_display)

    await callback.message.edit_text(
        text,
        reply_markup=get_language_selection_keyboard(current_lang),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.in_(["userlang_en", "userlang_ru"]))
async def cb_process_user_lang(callback: types.CallbackQuery, session: AsyncSession):
    """Processes user language choice and saves it persistently to the database."""
    target_lang = callback.data.replace("userlang_", "").lower()
    user_id = callback.from_user.id
    
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)
    
    if user:
        user.language = Language(target_lang)
        await session.commit()
    else:
        # If user isn't in DB yet, create a shell record so language is permanently preserved
        try:
            await user_repo.create_user(
                user_id=user_id,
                full_name=callback.from_user.full_name or "New Player",
                username=callback.from_user.username,
                position="CM",
                language=Language(target_lang)
            )
            await session.commit()
        except Exception as e:
            logger.warning(f"Could not persist user on language change: {e}")

    # Send confirmation in the newly chosen language
    if target_lang == "en":
        confirmation = t("lang_changed_en", "en")
    else:
        confirmation = t("lang_changed_ru", "ru")

    await callback.message.edit_text(
        confirmation,
        reply_markup=get_language_selection_keyboard(target_lang),
        parse_mode="HTML"
    )
    await callback.answer()
