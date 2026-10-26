import json
import os
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import logging
from app.db.models import User, Chat

logger = logging.getLogger(__name__)

class SimpleI18n:
    def __init__(self, locales_dir: str):
        self.locales_dir = locales_dir
        self.translations: Dict[str, Dict[str, str]] = {}
        self.load_translations()

    def load_translations(self):
        if not os.path.exists(self.locales_dir):
            logger.warning(f"Locales dir {self.locales_dir} not found.")
            return

        for filename in os.listdir(self.locales_dir):
            if filename.endswith(".json"):
                lang = filename.split(".")[0].lower()
                with open(os.path.join(self.locales_dir, filename), "r", encoding="utf-8") as f:
                    self.translations[lang] = json.load(f)
        logger.info(f"Loaded translations for: {list(self.translations.keys())}")

    def get_text(self, locale: Optional[str], key: str, /, **kwargs) -> str:
        lang_str = str(locale or "en").lower()
        if hasattr(locale, "value"):
            lang_str = str(locale.value).lower()

        # Match en or ru, default to en
        if lang_str not in self.translations:
            lang_str = "en"

        lang_dict = self.translations.get(lang_str, {})
        text = lang_dict.get(key)
        
        # Fallback to English, then Russian, then key
        if text is None:
            text = self.translations.get("en", {}).get(key)
        if text is None:
            text = self.translations.get("ru", {}).get(key, key)
        
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing format key {e} in translation string for '{key}'")
        return text

# Global instance initialized pointing to locales folder
_locales_path = os.path.join(os.path.dirname(__file__), "locales")
i18n_instance = SimpleI18n(_locales_path)

def t(key: str, locale: str = "en", /, **kwargs) -> str:
    """Helper for translating strings anywhere outside middlewares."""
    return i18n_instance.get_text(locale, key, **kwargs)

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

        # Determine language:
        # Default language is English ("en") per user requirement: "вообще изначальный язык пусть будет английский"
        lang = "en"

        if tg_chat and tg_chat.type == "private":
            # 1. Private chat: prioritize User.language setting
            if session and tg_user:
                try:
                    user_obj = await session.get(User, tg_user.id)
                    if user_obj and getattr(user_obj, "language", None):
                        lang = user_obj.language.value if hasattr(user_obj.language, "value") else str(user_obj.language)
                    elif tg_user.language_code and tg_user.language_code.startswith("ru"):
                        lang = "ru"
                except Exception as e:
                    logger.debug(f"Could not load user language in middleware: {e}")
            elif tg_user and tg_user.language_code and tg_user.language_code.startswith("ru"):
                lang = "ru"
        else:
            # 2. Group / Supergroup / Channel: prioritize Chat.language setting
            if tenant and getattr(tenant, "language", None):
                lang = tenant.language.value if hasattr(tenant.language, "value") else str(tenant.language)
            else:
                lang = "en"

        def _(key: str, **kwargs):
            return self.i18n.get_text(lang, key, **kwargs)

        # Inject into handler data
        data["_"] = _
        data["lang"] = lang
        data["i18n"] = self.i18n

        return await handler(event, data)
