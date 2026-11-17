import html
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import DEFAULT_LOCALES_DIR, LocaleCatalog
from app.db.models import Chat, ChatAdmin, ChatMember, User

logger = logging.getLogger(__name__)
_catalog = LocaleCatalog(locales_dir=DEFAULT_LOCALES_DIR, default_locale="en")


def _t(key: str, locale: str = "en", **kwargs: Any) -> str:
    return _catalog.translate(locale, key, **kwargs)

SPONSORS_PATH = Path(__file__).resolve().parent.parent / "presets" / "sponsors.json"


@dataclass(frozen=True)
class SponsorConfig:
    id: str
    name: str
    instagram_url: str
    registration_url: str
    recipient_telegram_id: Optional[int]
    chat_ids: List[int]
    is_default: bool
    reward_type: str
    logo_url: str
    hero_url: str
    i18n_prefix: str


def _load_raw_sponsors() -> Dict[str, Any]:
    if not SPONSORS_PATH.exists():
        return {"default_sponsor_id": None, "sponsors": {}}
    with SPONSORS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _to_config(raw: Dict[str, Any]) -> SponsorConfig:
    assets = raw.get("assets") or {}
    return SponsorConfig(
        id=str(raw["id"]),
        name=str(raw["name"]),
        instagram_url=str(raw.get("instagram_url") or ""),
        registration_url=str(raw.get("registration_url") or ""),
        recipient_telegram_id=raw.get("recipient_telegram_id"),
        chat_ids=[int(cid) for cid in (raw.get("chat_ids") or [])],
        is_default=bool(raw.get("is_default", False)),
        reward_type=str(raw.get("reward_type") or "free_coffee"),
        logo_url=str(assets.get("logo") or ""),
        hero_url=str(assets.get("hero") or ""),
        i18n_prefix=str(raw.get("i18n_prefix") or f"sponsor_{raw['id']}"),
    )


def get_sponsor_by_id(sponsor_id: str) -> Optional[SponsorConfig]:
    data = _load_raw_sponsors()
    raw = (data.get("sponsors") or {}).get(sponsor_id)
    return _to_config(raw) if raw else None


def get_sponsor_for_chat(chat_id: Optional[int] = None) -> Optional[SponsorConfig]:
    data = _load_raw_sponsors()
    sponsors_dict = data.get("sponsors") or {}
    configs = [_to_config(raw) for raw in sponsors_dict.values()]

    if chat_id is not None:
        for cfg in configs:
            if chat_id in cfg.chat_ids:
                return cfg

    default_id = data.get("default_sponsor_id")
    if default_id and default_id in sponsors_dict:
        return _to_config(sponsors_dict[default_id])

    for cfg in configs:
        if cfg.is_default:
            return cfg
    return configs[0] if configs else None


def get_localized_banner_fields(sponsor: SponsorConfig, lang: str = "en") -> Dict[str, str]:
    prefix = sponsor.i18n_prefix
    return {
        "title": _t(f"{prefix}_title", locale=lang),
        "subtitle": _t(f"{prefix}_subtitle", locale=lang),
        "badge_text": _t(f"{prefix}_badge", locale=lang),
        "text": _t(f"{prefix}_text", locale=lang),
        "cta_text": _t(f"{prefix}_cta", locale=lang),
    }


async def notify_owner_of_mvp_reward(
    bot: Any,
    session: AsyncSession,
    chat_id: int,
    game_num: int,
    player_user_id: int,
    loyalty_name: str,
    sponsor: SponsorConfig,
) -> int:
    """
    Sends an English notification to the coffee shop owner (recipient_telegram_id from sponsors.json,
    falling back to group admins if not yet configured) to credit 1 Free Coffee.
    """
    chat = await session.get(Chat, chat_id)
    chat_title = html.escape(chat.title if chat and chat.title else f"Group {chat_id}")
    user = await session.get(User, player_user_id)
    username_display = f"@{html.escape(user.username)}" if user and user.username else f"id:{player_user_id}"
    safe_loyalty_name = html.escape(loyalty_name)

    owner_msg = (
        f"☕ <b>New MVP Reward — {html.escape(sponsor.name)}</b>\n\n"
        f"🏆 Match: <b>#{game_num}</b> ({chat_title})\n"
        f"👤 Customer Name (Bondus): <code>{safe_loyalty_name}</code>\n"
        f"📱 Telegram: {username_display}\n"
        f"🎁 Reward: <b>1 Free Coffee</b>\n\n"
        f"Please credit 1 free coffee to this customer in your loyalty system."
    )

    recipients: List[int] = []
    if sponsor.recipient_telegram_id:
        recipients = [int(sponsor.recipient_telegram_id)]
    else:
        admin_rows = await session.execute(
            select(ChatAdmin.user_id).where(ChatAdmin.chat_id == chat_id)
        )
        recipients = [int(r[0]) for r in admin_rows.all()]

    sent = 0
    for target_uid in recipients:
        try:
            await bot.send_message(chat_id=target_uid, text=owner_msg, parse_mode="HTML")
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to notify sponsor recipient {target_uid}: {e}")
    return sent


async def process_mvp_winners_sponsor_rewards(
    bot: Any,
    session: AsyncSession,
    chat_id: int,
    game_num: int,
    mvp_ids: List[int],
) -> None:
    """
    For each newly awarded MVP winner:
    - If `loyalty_card_id` is already saved, immediately notifies the sponsor owner in English.
    - Otherwise, sends the Bondus loyalty card registration guide with the player's DB name hinted
      so they register with the exact matching name and confirm in 1 tap.
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    sponsor = get_sponsor_for_chat(chat_id)
    if not sponsor or not mvp_ids:
        return

    for mvp_uid in mvp_ids:
        user = await session.get(User, mvp_uid)
        cm = await session.scalar(
            select(ChatMember).where(
                ChatMember.chat_id == chat_id,
                ChatMember.user_id == mvp_uid,
            )
        )
        player_lang = (getattr(user, "language", None) or "ru") if user else "ru"
        saved_loyalty_name = getattr(cm, "loyalty_card_id", None) if cm else None

        if saved_loyalty_name:
            await notify_owner_of_mvp_reward(
                bot=bot,
                session=session,
                chat_id=chat_id,
                game_num=game_num,
                player_user_id=mvp_uid,
                loyalty_name=saved_loyalty_name,
                sponsor=sponsor,
            )
            try:
                msg = _t(
                    "mvp_coffee_already_linked_notified",
                    locale=player_lang,
                    game_num=game_num,
                    sponsor_name=html.escape(sponsor.name),
                    loyalty_name=html.escape(saved_loyalty_name),
                )
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=f"📸 {sponsor.name}",
                                url=sponsor.instagram_url,
                            )
                        ]
                    ]
                )
                await bot.send_message(
                    chat_id=mvp_uid, text=msg, reply_markup=kb, parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not DM MVP coffee confirmation to {mvp_uid}: {e}")
        else:
            db_name = (
                (user.full_name if user and user.full_name else None)
                or (cm.full_name if cm and cm.full_name else None)
                or f"Player {mvp_uid}"
            )
            safe_db_name = html.escape(db_name)
            msg = _t(
                "mvp_coffee_guide",
                locale=player_lang,
                game_num=game_num,
                sponsor_name=html.escape(sponsor.name),
                db_name=safe_db_name,
                registration_url=sponsor.registration_url,
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=_t("mvp_coffee_btn_open_reg", locale=player_lang),
                            url=sponsor.registration_url,
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=_t(
                                "mvp_coffee_btn_confirm",
                                locale=player_lang,
                                db_name=db_name[:28],
                            ),
                            callback_data=f"mvp_loyalty_confirm:{chat_id}:{game_num}:{sponsor.id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=_t("mvp_coffee_btn_other_name", locale=player_lang),
                            callback_data=f"mvp_loyalty_rename:{chat_id}:{game_num}:{sponsor.id}",
                        )
                    ],
                ]
            )
            try:
                await bot.send_message(
                    chat_id=mvp_uid, text=msg, reply_markup=kb, parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not DM MVP coffee guide to {mvp_uid}: {e}")
