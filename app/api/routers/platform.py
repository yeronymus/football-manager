from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.domain.sport_presets import list_sport_presets
from app.core.domain.tenant_policy import (
    BillingMode,
    OrganizerContact,
    resolve_billing_mode,
    resolve_tenant_policy,
)
from app.core.i18n import catalog, normalize_locale_code
from app.core.services.billing import resolve_game_billing
from app.core.services.qr_svg import render_qr_svg
from app.db.database import get_session
from app.db.models import Chat, Game

router = APIRouter()


async def _find_chat_tolerant(session: AsyncSession, chat_id: int) -> Optional[Chat]:
    chat = await session.get(Chat, chat_id)
    if isinstance(chat, Chat):
        return chat
    chat_id_str = str(chat_id)
    alt_chat_id = (
        int(chat_id_str.replace("-100", "-"))
        if "-100" in chat_id_str
        else int("-100" + chat_id_str.replace("-", ""))
    )
    candidates = {chat_id, alt_chat_id, abs(chat_id), abs(alt_chat_id)}
    res = await session.execute(
        select(Chat).where(or_(Chat.chat_id.in_(candidates), Chat.channel_id.in_(candidates)))
    )
    found = res.scalars().first()
    return found if isinstance(found, Chat) else None


@router.get("/locales")
async def get_supported_locales():
    """Returns dynamically discovered JSON locales and the platform default locale."""
    return {
        "default_locale": normalize_locale_code(settings.default_locale, default="en"),
        "locales": catalog.available_locales(),
    }


@router.get("/locales/{lang}")
async def get_locale_dictionary(lang: str):
    """Returns merged translation dictionary (English base + target locale overrides)."""
    resolved = catalog.resolve_supported(lang)
    return {
        "locale": resolved,
        "messages": catalog.get_dictionary(resolved),
    }


@router.get("/presets/sports")
async def get_sport_presets():
    """Returns parameterized sport discipline presets (football, futsal, volleyball, etc.)."""
    return {
        "default_sport": "football",
        "presets": [preset.model_dump() for preset in list_sport_presets()],
    }


@router.get("/tenants/public-rules")
async def get_tenant_public_rules(
    chat_id: Optional[int] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """
    Returns sanitized, OPSEC-safe dynamic rules configuration for `rules.html`.
    Never exposes private bank accounts, raw chat IDs when unrequested, or personal developer handles.
    """
    chat = await _find_chat_tolerant(session, chat_id) if chat_id is not None else None
    policy = resolve_tenant_policy(chat)
    billing_mode = resolve_billing_mode(getattr(chat, "billing_mode", None) if chat else None)
    currency = (
        (getattr(chat, "currency", None) if chat else None)
        or settings.default_currency
        or "CZK"
    ).upper()

    contacts_list = list(policy.organizer_contacts)
    if not contacts_list and (settings.support_contact or "").strip():
        contacts_list = [
            OrganizerContact(
                role="Support",
                name="Platform Support",
                handle=settings.support_contact.strip(),
            )
        ]

    default_price = (
        0
        if billing_mode == BillingMode.FREE_CORPORATE
        else (chat.default_price if (chat and chat.default_price is not None) else 100)
    )

    return {
        "bot_username": settings.bot_username,
        "title": chat.title if chat else None,
        "language": normalize_locale_code(
            getattr(chat, "language", None) if chat else settings.default_locale,
            default="en",
        ),
        "currency": currency,
        "timezone": (
            (getattr(chat, "timezone", None) if chat else None)
            or settings.default_timezone
            or "Europe/Prague"
        ),
        "sport_type": (getattr(chat, "sport_type", None) if chat else None) or "football",
        "billing_mode": billing_mode.value,
        "default_price": default_price,
        "policy": policy.model_dump(),
        "contacts": [
            {
                "role": c.role,
                "name": c.name,
                "handle": c.handle,
                "url": c.url,
            }
            for c in contacts_list
        ],
    }


@router.get("/billing/games/{game_id}/spayd")
async def get_game_spayd_summary(
    game_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Returns billing mode, IBAN, and Czech QR Platba SPAYD 1.0 payload for a match."""
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    chat = await _find_chat_tolerant(session, game.chat_id) if game.chat_id else None
    summary = resolve_game_billing(game, chat=chat)
    return asdict(summary)


@router.get("/billing/games/{game_id}/qr.svg")
async def get_game_spayd_qr_svg(
    game_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Generates a crisp offline SVG QR code for Czech QR Platba (`SPAYD 1.0`) without external APIs."""
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    chat = await _find_chat_tolerant(session, game.chat_id) if game.chat_id else None
    summary = resolve_game_billing(game, chat=chat)
    if not summary.spayd_payload:
        raise HTTPException(
            status_code=404,
            detail="SPAYD QR payment is not enabled or no valid IBAN/Czech bank account is configured for this game.",
        )
    svg = render_qr_svg(summary.spayd_payload, border=3, scale=6)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=300"},
    )
