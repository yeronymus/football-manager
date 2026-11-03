import logging

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.i18n import i18n_instance, t
from app.core.i18n import normalize_locale_code
from app.core.repositories.user_repository import UserRepository
from app.db.models import Language

logger = logging.getLogger(__name__)

router = Router()


def _format_locale_label(code: str) -> str:
    for item in i18n_instance.catalog.available_locales():
        if item["code"] == code:
            return f"{item['flag']} {item['name']}"
    return code.upper()


def _safe_language_enum(code: str) -> Language:
    norm = normalize_locale_code(code, default="en")
    try:
        return Language(norm)
    except ValueError:
        return Language.en


def get_language_selection_keyboard(current_lang: str = "en") -> InlineKeyboardMarkup:
    norm_current = normalize_locale_code(current_lang, default="en")
    available = i18n_instance.catalog.available_locales()
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for item in available:
        code = item["code"]
        prefix = "✅ " if code == norm_current else ""
        label = f"{prefix}{item['flag']} {item['name']}"
        current_row.append(InlineKeyboardButton(text=label, callback_data=f"userlang_{code}"))
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("language"))
@router.message(Command("lang"))
async def cmd_language(message: types.Message, session: AsyncSession, _):
    """Command to choose personal interface language."""
    if message.chat.type != "private":
        try:
            await message.delete()
        except Exception:
            pass
        return

    user_id = message.from_user.id
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)

    current_lang = "en"
    if user and user.language:
        current_lang = i18n_instance.catalog.resolve_supported(user.language)
    elif isinstance(getattr(message.from_user, "language_code", None), str):
        current_lang = i18n_instance.catalog.resolve_supported(message.from_user.language_code)

    lang_display = _format_locale_label(current_lang)
    text = _("lang_select_title", lang=lang_display)

    await message.answer(
        text,
        reply_markup=get_language_selection_keyboard(current_lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "change_user_lang")
async def cb_change_user_lang(callback: types.CallbackQuery, session: AsyncSession, _):
    """Called from Profile or Settings to change user language."""
    user_id = callback.from_user.id
    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)

    current_lang = "en"
    if user and user.language:
        current_lang = i18n_instance.catalog.resolve_supported(user.language)

    lang_display = _format_locale_label(current_lang)
    text = _("lang_select_title", lang=lang_display)

    await callback.message.edit_text(
        text,
        reply_markup=get_language_selection_keyboard(current_lang),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("userlang_"))
async def cb_process_user_lang(callback: types.CallbackQuery, session: AsyncSession):
    """Processes user language choice and persists it in the database."""
    raw_lang = callback.data.replace("userlang_", "").strip().lower()
    target_lang = i18n_instance.catalog.resolve_supported(raw_lang)
    lang_enum = _safe_language_enum(target_lang)
    user_id = callback.from_user.id

    user_repo = UserRepository(session)
    user = await user_repo.get_user(user_id)

    if user:
        user.language = lang_enum
        await session.commit()
    else:
        try:
            await user_repo.create_user(
                user_id=user_id,
                full_name=callback.from_user.full_name or "New Player",
                username=callback.from_user.username,
                position="CM",
                language=lang_enum,
            )
            await session.commit()
        except Exception as e:
            logger.warning("Could not persist user on language change: %s", e)

    specific_key = f"lang_changed_{target_lang}"
    if specific_key in i18n_instance.catalog.translations.get(target_lang, {}):
        confirmation = t(specific_key, target_lang)
    else:
        confirmation = t(
            "lang_changed_generic",
            target_lang,
            lang_name=_format_locale_label(target_lang),
        )

    await callback.message.edit_text(
        confirmation,
        reply_markup=get_language_selection_keyboard(target_lang),
        parse_mode="HTML",
    )
    await callback.answer()
