import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

LOCALE_ALIASES: Dict[str, str] = {
    "cz": "cs",
    "ces": "cs",
    "cze": "cs",
    "cs-cz": "cs",
    "cs_cz": "cs",
    "en-us": "en",
    "en_us": "en",
    "en-gb": "en",
    "en_gb": "en",
    "ru-ru": "ru",
    "ru_ru": "ru",
}

CURRENCY_LOCALIZED_LABELS: Dict[str, Dict[str, str]] = {
    "CZK": {"en": "CZK", "ru": "крон", "cs": "Kč"},
    "EUR": {"en": "EUR", "ru": "EUR", "cs": "EUR"},
    "USD": {"en": "USD", "ru": "USD", "cs": "USD"},
}


def format_currency_unit(currency: Optional[str], locale: str = "en") -> str:
    """Returns localized currency label while preserving ISO code fallback."""
    code = (currency or settings.default_currency or "CZK").upper().strip()
    norm_loc = normalize_locale_code(locale)
    if code in CURRENCY_LOCALIZED_LABELS:
        return CURRENCY_LOCALIZED_LABELS[code].get(norm_loc, code)
    return code


def normalize_locale_code(locale: Any, default: str = "en") -> str:
    """Normalizes enum/BCP-47/alias locale identifiers (e.g. 'cz' -> 'cs', None -> 'en')."""
    if locale is None:
        return default
    raw = locale.value if hasattr(locale, "value") else locale
    if not isinstance(raw, str):
        return default
    cleaned = raw.strip().lower()
    if not cleaned:
        return default
    if cleaned in LOCALE_ALIASES:
        return LOCALE_ALIASES[cleaned]
    primary = re.split(r"[-_]", cleaned)[0]
    return LOCALE_ALIASES.get(primary, primary)


class LocaleCatalog:
    """
    Single-source JSON internationalization catalog with dynamic locale auto-discovery.
    Any `<lang>.json` file placed in `locales_dir` is discovered automatically without code changes.
    Universal fallback order: requested locale -> 'en' -> raw key.
    """

    def __init__(self, locales_dir: Optional[Path | str] = None, default_locale: str = "en"):
        resolved_dir = Path(locales_dir) if locales_dir else DEFAULT_LOCALES_DIR
        # Transparently redirect legacy 'app/bot/locales' references to unified 'app/locales'
        if not resolved_dir.exists() and DEFAULT_LOCALES_DIR.exists():
            resolved_dir = DEFAULT_LOCALES_DIR
        self.locales_dir: Path = resolved_dir
        self.default_locale: str = normalize_locale_code(default_locale, default="en")
        self.translations: Dict[str, Dict[str, str]] = {}
        self.reload()

    def reload(self) -> None:
        self.translations.clear()
        if not self.locales_dir.exists():
            logger.warning("Locales directory %s does not exist.", self.locales_dir)
            return

        for file_path in sorted(self.locales_dir.glob("*.json")):
            lang_code = normalize_locale_code(file_path.stem)
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.translations[lang_code] = {
                        str(k): str(v) for k, v in data.items()
                    }
            except Exception as exc:
                logger.error("Failed to load locale file %s: %s", file_path, exc)

        logger.info("Discovered locales: %s", sorted(self.translations.keys()))

    def supported_codes(self) -> List[str]:
        codes = list(self.translations.keys())
        ordered: List[str] = []
        for preferred in ("en", "ru", "cs"):
            if preferred in codes:
                ordered.append(preferred)
        for code in sorted(codes):
            if code not in ordered:
                ordered.append(code)
        return ordered

    def resolve_supported(self, locale: Any) -> str:
        norm = normalize_locale_code(locale, default=self.default_locale)
        if norm in self.translations:
            return norm
        if self.default_locale in self.translations:
            return self.default_locale
        return "en"

    def available_locales(self) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for code in self.supported_codes():
            d = self.translations.get(code, {})
            out.append(
                {
                    "code": code,
                    "name": d.get("_locale_name", code.upper()),
                    "flag": d.get("_locale_flag", "🌐"),
                }
            )
        return out

    def get_dictionary(self, locale: Any) -> Dict[str, str]:
        """Returns merged dictionary (en base + target locale overrides) for WebApps/API."""
        resolved = self.resolve_supported(locale)
        base = dict(self.translations.get("en", {}))
        if resolved != "en" and resolved in self.translations:
            base.update(self.translations[resolved])
        return base

    def translate(self, locale: Any, key: str, /, **kwargs: Any) -> str:
        resolved = self.resolve_supported(locale)
        lang_dict = self.translations.get(resolved, {})
        text = lang_dict.get(key)

        if text is None and resolved != "en":
            text = self.translations.get("en", {}).get(key)
        if text is None:
            text = key

        # Inject safe defaults for parameterized currency/policy placeholders when omitted
        fmt_kwargs = dict(kwargs)
        if "{currency}" in text and "currency" not in fmt_kwargs:
            fmt_kwargs["currency"] = format_currency_unit(settings.default_currency, resolved)
        elif "currency" in fmt_kwargs and fmt_kwargs["currency"] in ("CZK", "EUR", "USD"):
            fmt_kwargs["currency"] = format_currency_unit(str(fmt_kwargs["currency"]), resolved)
        if "{mvp_bonus}" in text and "mvp_bonus" not in fmt_kwargs:
            fmt_kwargs["mvp_bonus"] = 5
        if "{window_hours}" in text and "window_hours" not in fmt_kwargs:
            fmt_kwargs["window_hours"] = 24
        if "{cancel_hours}" in text and "cancel_hours" not in fmt_kwargs:
            fmt_kwargs["cancel_hours"] = 24

        if fmt_kwargs:
            try:
                text = text.format(**fmt_kwargs)
            except KeyError as exc:
                logger.error("Missing format placeholder %s in key '%s' (%s)", exc, key, resolved)
        return text


catalog = LocaleCatalog()
