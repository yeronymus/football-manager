import json
import os
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
import logging

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
                lang = filename.split(".")[0]
                with open(os.path.join(self.locales_dir, filename), "r", encoding="utf-8") as f:
                    self.translations[lang] = json.load(f)
        logger.info(f"Loaded translations for: {list(self.translations.keys())}")

    def get_text(self, lang: str, key: str, **kwargs) -> str:
        # Fallback to English if language not found, or directly to key
        lang_dict = self.translations.get(lang, self.translations.get("ru", {}))
        text = lang_dict.get(key, key)
        
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.error(f"Missing format key {e} in translation string for '{key}'")
        return text

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
        # tenant is injected by TenantMiddleware
        tenant = data.get("tenant")
        lang = "ru" # default
        
        if tenant and getattr(tenant, "language", None):
            lang = tenant.language
            
        def _(key: str, **kwargs):
            return self.i18n.get_text(lang, key, **kwargs)
            
        # Inject the translation function into handler data
        data["_"] = _
        
        return await handler(event, data)
