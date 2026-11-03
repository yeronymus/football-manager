import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import settings
from app.core.i18n import DEFAULT_LOCALES_DIR, LocaleCatalog, normalize_locale_code
from app.db.models import Chat, User

logger = logging.getLogger(__name__)


class SimpleI18n:
    """
    Bot adapter around the unified single-source `LocaleCatalog` (`app/locales/*.json`).
    Preserves backward compatibility while enforcing 'en' as the universal fallback.
    """

    def __init__(self, locales_dir: Optional[str | Path] = None):
        self.catalog = LocaleCatalog(
            locales_dir=locales_dir or DEFAULT_LOCALES_DIR,
            default_locale=settings.default_locale or "en",
        )
        self.locales_dir = str(self.catalog.locales_dir)
        self.translations: Dict[str, Dict[str, str]] = self.catalog.translations

    def load_translations(self) -> None:
        self.catalog.reload()
        self.translations = self.catalog.translations

    def get_text(self, locale: Optional[str], key: str, /, **kwargs: Any) -> str:
        return self.catalog.translate(locale, key, **kwargs)


i18n_instance = SimpleI18n()


def t(key: str, locale: Optional[str] = None, /, **kwargs: Any) -> str:
    """Helper for translating strings outside aiogram middlewares (universal default: 'en')."""
    loc = kwargs.pop("locale", None) or locale or settings.default_locale or "en"
    return i18n_instance.get_text(loc, key, **kwargs)


class I18nMiddleware(BaseMiddleware):
    def __init__(self, i18n: SimpleI18n):
        self.i18n = i18n
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        tenant = data.get("tenant")

        tg_chat = None
        tg_user = None

        if isinstance(event, Message):
            tg_chat = event.chat
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            if event.message:
                tg_chat = event.message.chat
            tg_user = event.from_user

        default_lang = normalize_locale_code(settings.default_locale, default="en")
        lang = default_lang

        if tg_chat and tg_chat.type == "private":
            resolved = False
            if session and tg_user:
                try:
                    user_obj = await session.get(User, tg_user.id)
                    if user_obj and getattr(user_obj, "language", None):
                        lang = self.i18n.catalog.resolve_supported(user_obj.language)
                        resolved = True
                except Exception as exc:
                    logger.debug("Could not load user language in middleware: %s", exc)
            if not resolved and tg_user and isinstance(getattr(tg_user, "language_code", None), str):
                lang = self.i18n.catalog.resolve_supported(tg_user.language_code)
        else:
            if tenant and getattr(tenant, "language", None):
                lang = self.i18n.catalog.resolve_supported(tenant.language)
            elif session and tg_chat:
                try:
                    chat_obj = await session.get(Chat, tg_chat.id)
                    if chat_obj and getattr(chat_obj, "language", None):
                        lang = self.i18n.catalog.resolve_supported(chat_obj.language)
                except Exception as exc:
                    logger.debug("Could not load chat language in middleware: %s", exc)

        def _(key: str, **kwargs: Any) -> str:
            return self.i18n.get_text(lang, key, **kwargs)

        data["_"] = _
        data["lang"] = lang
        data["i18n"] = self.i18n

        return await handler(event, data)
