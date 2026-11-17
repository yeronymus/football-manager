import logging
import random
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.core.services.sponsor_service import (
    get_localized_banner_fields,
    get_sponsor_for_chat,
    process_mvp_winners_sponsor_rewards,
)
from app.db.database import get_session
from app.db.models import AdBanner, AdBannerEvent, ChatMember, User

logger = logging.getLogger(__name__)
router = APIRouter()


class AdClickIn(BaseModel):
    chat_id: Optional[int] = None
    placement: Optional[str] = "default"


class ManualRewardIssueIn(BaseModel):
    target_user_id: int
    game_id: Optional[int] = None


@router.get("/ads/random")
async def get_random_ad(
    chat_id: int = None,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
    placement: Optional[str] = "default",
    lang: Optional[str] = "en",
):
    """
    Returns an active sponsor/ad banner for the Mini-App (enriched from sponsors.json + i18n)
    and records an impression metric.
    """
    stmt = select(AdBanner).where(AdBanner.is_active == True)  # noqa: E712
    if chat_id:
        stmt = stmt.where((AdBanner.chat_id == None) | (AdBanner.chat_id == chat_id))  # noqa: E711
    else:
        stmt = stmt.where(AdBanner.chat_id == None)  # noqa: E711

    result = await session.execute(stmt)
    ads = result.scalars().all()

    sponsor = get_sponsor_for_chat(chat_id)
    if not ads and not sponsor:
        return {"status": "no_ads", "ad": None}

    chosen_ad = None
    if ads:
        weights = [ad.show_probability for ad in ads]
        chosen_ad = random.choices(ads, weights=weights, k=1)[0]

        try:
            chosen_ad.impressions_count = int(getattr(chosen_ad, "impressions_count", 0) or 0) + 1
            if getattr(chosen_ad, "id", None) is not None:
                session.add(
                    AdBannerEvent(
                        banner_id=chosen_ad.id,
                        chat_id=chat_id,
                        user_id=user_id,
                        placement=(placement or "default")[:64],
                        event_type="impression",
                    )
                )
                await session.commit()
        except Exception as e:
            logger.debug(f"Non-fatal ad impression tracking error: {e}")

    loc_fields = get_localized_banner_fields(sponsor, lang=lang or "en") if sponsor else {}

    return {
        "status": "ok",
        "ad": {
            "id": chosen_ad.id if chosen_ad else None,
            "sponsor_id": sponsor.id if sponsor else None,
            "title": loc_fields.get("title") or (getattr(chosen_ad, "title", None) if chosen_ad else None),
            "subtitle": loc_fields.get("subtitle") or (getattr(chosen_ad, "subtitle", None) if chosen_ad else None),
            "badge_text": loc_fields.get("badge_text") or (getattr(chosen_ad, "badge_text", None) if chosen_ad else None),
            "cta_text": loc_fields.get("cta_text") or (getattr(chosen_ad, "cta_text", None) if chosen_ad else None),
            "text": (
                getattr(chosen_ad, "text", None)
                if chosen_ad and not sponsor
                else (loc_fields.get("text") or (chosen_ad.text if chosen_ad else ""))
            ),
            "image_url": (sponsor.logo_url if sponsor else None) or (chosen_ad.image_url if chosen_ad else None),
            "hero_image_url": (sponsor.hero_url if sponsor else None) or (getattr(chosen_ad, "hero_image_url", None) if chosen_ad else None),
            "link": (sponsor.instagram_url if sponsor else None) or (chosen_ad.link if chosen_ad else None),
        },
    }


@router.post("/ads/{banner_id}/click")
async def record_ad_click(
    banner_id: int,
    payload: Optional[AdClickIn] = None,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Records a user click on a sponsor banner for CTR and engagement analytics.
    """
    banner = await session.get(AdBanner, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")

    banner.clicks_count = int(getattr(banner, "clicks_count", 0) or 0) + 1
    session.add(
        AdBannerEvent(
            banner_id=banner.id,
            chat_id=payload.chat_id if payload else None,
            user_id=user_id,
            placement=((payload.placement if payload else None) or "default")[:64],
            event_type="click",
        )
    )
    await session.commit()
    return {
        "status": "ok",
        "banner_id": banner.id,
        "clicks_count": banner.clicks_count,
        "impressions_count": banner.impressions_count or 0,
    }


@router.get("/groups/{chat_id}/ads/metrics")
async def get_group_ad_metrics(
    chat_id: int,
    lang: Optional[str] = "en",
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Returns sponsor banner telemetry (impressions, clicks, CTR, unique reach, placement breakdown)
    and confirmed loyalty-card members for the Admin Hub.
    """
    from app.api.routers import dashboard as _dash

    await _dash.check_admin_rights(chat_id, user_id, session=session)

    sponsor = get_sponsor_for_chat(chat_id)
    loc_fields = get_localized_banner_fields(sponsor, lang=lang or "en") if sponsor else {}

    stmt = select(AdBanner).where(
        AdBanner.is_active == True,  # noqa: E712
        (AdBanner.chat_id == None) | (AdBanner.chat_id == chat_id),  # noqa: E711
    )
    banners = (await session.execute(stmt)).scalars().all()

    banners_out = []
    total_impressions = 0
    total_clicks = 0

    for b in banners:
        ev_stmt = (
            select(
                AdBannerEvent.event_type,
                func.count(AdBannerEvent.id),
                func.count(func.distinct(AdBannerEvent.user_id)),
            )
            .where(AdBannerEvent.banner_id == b.id)
            .where((AdBannerEvent.chat_id == chat_id) | (AdBannerEvent.chat_id.is_(None)))
            .group_by(AdBannerEvent.event_type)
        )
        ev_rows = (await session.execute(ev_stmt)).all()
        ev_map = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in ev_rows}

        imp_cnt = max(int(b.impressions_count or 0), ev_map.get("impression", (0, 0))[0])
        clk_cnt = max(int(b.clicks_count or 0), ev_map.get("click", (0, 0))[0])
        uniq_views = ev_map.get("impression", (0, 0))[1]
        uniq_clicks = ev_map.get("click", (0, 0))[1]
        ctr = round((clk_cnt / imp_cnt) * 100.0, 2) if imp_cnt > 0 else 0.0

        pl_stmt = (
            select(
                AdBannerEvent.placement,
                AdBannerEvent.event_type,
                func.count(AdBannerEvent.id),
            )
            .where(AdBannerEvent.banner_id == b.id)
            .group_by(AdBannerEvent.placement, AdBannerEvent.event_type)
        )
        pl_rows = (await session.execute(pl_stmt)).all()
        placements = {}
        for pl_name, ev_type, cnt in pl_rows:
            key = pl_name or "default"
            if key not in placements:
                placements[key] = {"impressions": 0, "clicks": 0}
            if ev_type == "impression":
                placements[key]["impressions"] += int(cnt or 0)
            elif ev_type == "click":
                placements[key]["clicks"] += int(cnt or 0)

        total_impressions += imp_cnt
        total_clicks += clk_cnt

        banners_out.append(
            {
                "id": b.id,
                "title": loc_fields.get("title") or b.title or b.text,
                "subtitle": loc_fields.get("subtitle") or b.subtitle,
                "text": loc_fields.get("text") or b.text,
                "cta_text": loc_fields.get("cta_text") or b.cta_text or "@21coffeecz ↗",
                "link": (sponsor.instagram_url if sponsor else None) or b.link,
                "image_url": (sponsor.logo_url if sponsor else None) or b.image_url,
                "hero_image_url": (sponsor.hero_url if sponsor else None) or b.hero_image_url,
                "impressions": imp_cnt,
                "unique_viewers": uniq_views,
                "clicks": clk_cnt,
                "unique_clickers": uniq_clicks,
                "ctr_percent": ctr,
                "placements": placements,
            }
        )

    loyalty_rows = (
        await session.execute(
            select(ChatMember)
            .where(
                ChatMember.chat_id == chat_id,
                ChatMember.loyalty_card_id.is_not(None),
            )
            .order_by(ChatMember.last_seen_at.desc())
        )
    ).scalars().all()

    loyalty_members = [
        {
            "user_id": m.user_id,
            "full_name": m.full_name or f"User {m.user_id}",
            "username": m.username,
            "loyalty_card_name": m.loyalty_card_id,
        }
        for m in loyalty_rows
    ]

    overall_ctr = (
        round((total_clicks / total_impressions) * 100.0, 2)
        if total_impressions > 0
        else 0.0
    )

    return {
        "chat_id": chat_id,
        "sponsor": {
            "id": sponsor.id,
            "name": sponsor.name,
            "instagram_url": sponsor.instagram_url,
            "registration_url": sponsor.registration_url,
            "owner_configured": bool(sponsor.recipient_telegram_id),
        }
        if sponsor
        else None,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "overall_ctr_percent": overall_ctr,
        "banners": banners_out,
        "loyalty_members": loyalty_members,
    }


@router.post("/groups/{chat_id}/rewards/issue")
async def manual_trigger_mvp_coffee(
    chat_id: int,
    payload: ManualRewardIssueIn,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Triggers the Bondus loyalty flow for a player:
    - If loyalty_card_id is confirmed, notifies the sponsor owner in English.
    - Otherwise sends the player the Bondus registration guide with their DB name hinted.
    """
    from app.api.routers import dashboard as _dash
    from app.bot.instance import bot

    await _dash.check_admin_rights(chat_id, user_id, session=session)

    target_user = await session.get(User, payload.target_user_id)
    cm = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == payload.target_user_id,
        )
    )
    if not target_user and not cm:
        raise HTTPException(status_code=404, detail="Player not found")

    await process_mvp_winners_sponsor_rewards(
        bot=bot,
        session=session,
        chat_id=chat_id,
        game_num=payload.game_id or 0,
        mvp_ids=[payload.target_user_id],
    )
    has_card = bool(cm and cm.loyalty_card_id)
    return {
        "status": "ok",
        "user_id": payload.target_user_id,
        "flow": "owner_notified" if has_card else "onboarding_sent",
    }
