import datetime
import logging
import random
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.db.database import get_session
from app.db.models import (
    AdBanner,
    AdBannerEvent,
    ChatAdmin,
    ChatMember,
    Game,
    MvpRewardClaim,
    User,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class AdClickIn(BaseModel):
    chat_id: Optional[int] = None
    placement: Optional[str] = "default"


class RewardClaimIn(BaseModel):
    loyalty_identifier: str


class RewardStatusUpdateIn(BaseModel):
    status: str = "CREDITED"  # CREDITED | REDEEMED


class ManualRewardIssueIn(BaseModel):
    target_user_id: int
    game_id: Optional[int] = None
    reward_title: Optional[str] = None


def generate_mvp_reward_code(game_id: Optional[int] = None) -> str:
    prefix = f"21C-G{game_id}" if game_id else "21C-MVP"
    suffix = secrets.token_hex(2).upper()
    return f"{prefix}-{suffix}"


@router.get("/ads/random")
async def get_random_ad(
    chat_id: int = None,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
    placement: Optional[str] = "default",
):
    """
    Returns a random active ad banner for the Mini-App and records an impression metric.
    If chat_id is provided, it can fetch group-specific ads alongside global ads.
    """
    stmt = select(AdBanner).where(AdBanner.is_active == True)  # noqa: E712

    if chat_id:
        stmt = stmt.where((AdBanner.chat_id == None) | (AdBanner.chat_id == chat_id))  # noqa: E711
    else:
        stmt = stmt.where(AdBanner.chat_id == None)  # noqa: E711

    result = await session.execute(stmt)
    ads = result.scalars().all()

    if not ads:
        return {"status": "no_ads", "ad": None}

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

    return {
        "status": "ok",
        "ad": {
            "id": chosen_ad.id,
            "title": getattr(chosen_ad, "title", None) or "21 Coffee • Specialty Coffee & Brunch",
            "subtitle": getattr(chosen_ad, "subtitle", None)
            or "📍 Holešovice (Na Maninách 16) • Vinohrady (Londýnská)",
            "badge_text": getattr(chosen_ad, "badge_text", None) or "☕ MVP PARTNER • FREE COFFEE",
            "cta_text": getattr(chosen_ad, "cta_text", None) or "@21coffeecz ↗",
            "text": chosen_ad.text,
            "image_url": chosen_ad.image_url,
            "hero_image_url": getattr(chosen_ad, "hero_image_url", None)
            or "/web/assets/sponsors/21coffee_hero.webp",
            "link": chosen_ad.link,
            "reward_title": getattr(chosen_ad, "reward_title", None),
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
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Returns sponsor banner telemetry (impressions, clicks, CTR, unique reach, placement breakdown)
    and MVP sponsor rewards ledger for the Admin Hub.
    """
    from app.api.routers import dashboard as _dash

    await _dash.check_admin_rights(chat_id, user_id, session=session)

    stmt = select(AdBanner).where(
        AdBanner.is_active == True,  # noqa: E712
        (AdBanner.chat_id == None) | (AdBanner.chat_id == chat_id),  # noqa: E711
    )
    banners = (await session.execute(stmt)).scalars().all()

    banners_out = []
    total_impressions = 0
    total_clicks = 0

    for b in banners:
        ev_stmt = select(
            AdBannerEvent.event_type,
            func.count(AdBannerEvent.id),
            func.count(func.distinct(AdBannerEvent.user_id)),
        ).where(AdBannerEvent.banner_id == b.id)
        if chat_id:
            ev_stmt = ev_stmt.where(
                (AdBannerEvent.chat_id == chat_id) | (AdBannerEvent.chat_id.is_(None))
            )
        ev_stmt = ev_stmt.group_by(AdBannerEvent.event_type)
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
                "title": b.title or b.text,
                "subtitle": b.subtitle,
                "text": b.text,
                "link": b.link,
                "image_url": b.image_url,
                "hero_image_url": b.hero_image_url,
                "reward_title": b.reward_title,
                "impressions": imp_cnt,
                "unique_viewers": uniq_views,
                "clicks": clk_cnt,
                "unique_clickers": uniq_clicks,
                "ctr_percent": ctr,
                "placements": placements,
            }
        )

    claims_res = await session.execute(
        select(MvpRewardClaim)
        .where(MvpRewardClaim.chat_id == chat_id)
        .order_by(MvpRewardClaim.issued_at.desc())
        .limit(50)
    )
    claims = claims_res.scalars().all()
    uid_set = {c.user_id for c in claims}
    users_map = {}
    if uid_set:
        u_rows = (
            await session.execute(select(User).where(User.user_id.in_(uid_set)))
        ).scalars().all()
        users_map = {u.user_id: u for u in u_rows}

    rewards_out = []
    for c in claims:
        u = users_map.get(c.user_id)
        rewards_out.append(
            {
                "id": c.id,
                "code": c.code,
                "game_id": c.game_id,
                "user_id": c.user_id,
                "full_name": u.full_name if u else f"User {c.user_id}",
                "username": u.username if u else None,
                "sponsor_name": c.sponsor_name,
                "reward_title": c.reward_title,
                "loyalty_identifier": c.loyalty_identifier,
                "status": c.status,
                "issued_at": c.issued_at.isoformat() if c.issued_at else None,
                "claimed_at": c.claimed_at.isoformat() if c.claimed_at else None,
                "redeemed_at": c.redeemed_at.isoformat() if c.redeemed_at else None,
            }
        )

    overall_ctr = (
        round((total_clicks / total_impressions) * 100.0, 2)
        if total_impressions > 0
        else 0.0
    )

    return {
        "chat_id": chat_id,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "overall_ctr_percent": overall_ctr,
        "banners": banners_out,
        "mvp_rewards": rewards_out,
    }


@router.get("/rewards/{code}")
async def get_mvp_reward_by_code(
    code: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Returns digital MVP pass details for a specific reward code (used by /web/reward.html).
    """
    clean_code = code.strip().upper()
    claim = await session.scalar(
        select(MvpRewardClaim).where(MvpRewardClaim.code == clean_code)
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Reward voucher not found")

    user = await session.get(User, claim.user_id)
    member = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == claim.chat_id,
            ChatMember.user_id == claim.user_id,
        )
    )
    banner = await session.get(AdBanner, claim.banner_id) if claim.banner_id else None

    return {
        "code": claim.code,
        "chat_id": claim.chat_id,
        "game_id": claim.game_id,
        "user_id": claim.user_id,
        "player_name": (user.full_name if user else (member.full_name if member else f"Player {claim.user_id}")),
        "player_username": (user.username if user else (member.username if member else None)),
        "sponsor_name": claim.sponsor_name,
        "reward_title": claim.reward_title,
        "sponsor_url": claim.sponsor_url or (banner.link if banner else "https://www.instagram.com/21coffeecz/"),
        "instructions": (
            banner.reward_instructions
            if banner and banner.reward_instructions
            else "Укажи свой номер телефона или ID карты лояльности (Apple Wallet / 21coffee.eu) для начисления бесплатного кофе, либо покажи этот цифровой MVP-пасс бариста на кассе."
        ),
        "loyalty_identifier": claim.loyalty_identifier or (member.loyalty_card_id if member else None),
        "status": claim.status,
        "issued_at": claim.issued_at.isoformat() if claim.issued_at else None,
        "claimed_at": claim.claimed_at.isoformat() if claim.claimed_at else None,
        "redeemed_at": claim.redeemed_at.isoformat() if claim.redeemed_at else None,
    }


@router.post("/rewards/{code}/claim")
async def submit_mvp_reward_loyalty_id(
    code: str,
    payload: RewardClaimIn,
    session: AsyncSession = Depends(get_session),
):
    """
    Saves the MVP winner's phone number / Apple Wallet card ID so the sponsor/admin
    can credit their free coffee directly into their loyalty account.
    """
    clean_code = code.strip().upper()
    claim = await session.scalar(
        select(MvpRewardClaim).where(MvpRewardClaim.code == clean_code)
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Reward voucher not found")

    ident = (payload.loyalty_identifier or "").strip()[:128]
    if not ident:
        raise HTTPException(status_code=400, detail="Loyalty identifier is required")

    claim.loyalty_identifier = ident
    if claim.status == "ISSUED":
        claim.status = "PENDING_CREDIT"
    claim.claimed_at = datetime.datetime.now(datetime.timezone.utc)

    member = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == claim.chat_id,
            ChatMember.user_id == claim.user_id,
        )
    )
    if member:
        member.loyalty_card_id = ident

    await session.commit()

    # Notify group admins via Telegram so they or the partner can credit the card immediately
    try:
        from app.bot.instance import bot

        user = await session.get(User, claim.user_id)
        p_name = user.full_name if user else f"User {claim.user_id}"
        p_uname = f" (@{user.username})" if user and user.username else ""
        admins = (
            await session.execute(
                select(ChatAdmin.user_id).where(ChatAdmin.chat_id == claim.chat_id)
            )
        ).scalars().all()
        msg_text = (
            f"☕ <b>Запрос на начисление кофе MVP ({claim.sponsor_name})</b>\n\n"
            f"👤 Игрок: <b>{p_name}</b>{p_uname}\n"
            f"🎫 Купон: <code>{claim.code}</code>\n"
            f"📱 Карта / Телефон (Apple Wallet / 21 Coffee): <code>{ident}</code>\n\n"
            f"Начислите 1 кофе в системе лояльности и отметьте купон выполненным в Admin Hub."
        )
        for admin_uid in admins:
            try:
                await bot.send_message(chat_id=admin_uid, text=msg_text, parse_mode="HTML")
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Admin reward notification skipped: {e}")

    return {
        "status": "ok",
        "code": claim.code,
        "reward_status": claim.status,
        "loyalty_identifier": claim.loyalty_identifier,
    }


@router.post("/rewards/{code}/redeem")
async def redeem_mvp_reward(
    code: str,
    payload: Optional[RewardStatusUpdateIn] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Marks an MVP reward voucher as REDEEMED (at counter) or CREDITED (to Apple Wallet loyalty card).
    """
    clean_code = code.strip().upper()
    claim = await session.scalar(
        select(MvpRewardClaim).where(MvpRewardClaim.code == clean_code)
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Reward voucher not found")

    new_status = (payload.status if payload and payload.status else "REDEEMED").upper()
    if new_status not in ("CREDITED", "REDEEMED", "ISSUED", "PENDING_CREDIT"):
        new_status = "REDEEMED"

    claim.status = new_status
    claim.redeemed_at = datetime.datetime.now(datetime.timezone.utc)
    await session.commit()

    if new_status == "CREDITED":
        try:
            from app.bot.instance import bot

            await bot.send_message(
                chat_id=claim.user_id,
                text=(
                    f"☕🎉 <b>Твой бесплатный кофе от {claim.sponsor_name} начислен!</b>\n\n"
                    f"Награда <b>{claim.reward_title}</b> (купон <code>{claim.code}</code>) добавлена на твой аккаунт / карту лояльности (<code>{claim.loyalty_identifier or '—'}</code>).\n"
                    f"Забегай в <b>21 Coffee</b> в любое время!"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.debug(f"Could not notify user {claim.user_id} of credited coffee: {e}")

    return {
        "status": "ok",
        "code": claim.code,
        "reward_status": claim.status,
        "redeemed_at": claim.redeemed_at.isoformat() if claim.redeemed_at else None,
    }


@router.post("/groups/{chat_id}/rewards/issue")
async def manual_issue_mvp_reward(
    chat_id: int,
    payload: ManualRewardIssueIn,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Allows a group admin to manually issue a sponsor MVP reward voucher to a player
    and notify them in Telegram.
    """
    from app.api.routers import dashboard as _dash

    await _dash.check_admin_rights(chat_id, user_id, session=session)

    banner = await session.scalar(
        select(AdBanner).where(
            AdBanner.is_active == True,  # noqa: E712
            (AdBanner.chat_id == chat_id) | (AdBanner.chat_id.is_(None)),
        )
    )
    member = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == payload.target_user_id,
        )
    )

    code = generate_mvp_reward_code(payload.game_id)
    sponsor_name = (banner.title.split("•")[0].strip() if banner and banner.title else "21 Coffee")
    reward_title = (
        payload.reward_title
        or (banner.reward_title if banner and banner.reward_title else "1x Бесплатный кофе от 21 Coffee")
    )
    sponsor_url = banner.link if banner and banner.link else "https://www.instagram.com/21coffeecz/"

    claim = MvpRewardClaim(
        code=code,
        chat_id=chat_id,
        game_id=payload.game_id,
        user_id=payload.target_user_id,
        banner_id=banner.id if banner else None,
        sponsor_name=sponsor_name,
        reward_title=reward_title,
        sponsor_url=sponsor_url,
        loyalty_identifier=member.loyalty_card_id if member else None,
        status="PENDING_CREDIT" if (member and member.loyalty_card_id) else "ISSUED",
    )
    session.add(claim)
    await session.commit()

    try:
        from app.bot.instance import bot
        from app.config import settings
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

        base_url = (settings.webapp_url or "https://football.yeronym.com").rstrip("/")
        if base_url.endswith("/web"):
            reward_url = f"{base_url}/reward.html?code={code}"
        else:
            reward_url = f"{base_url}/web/reward.html?code={code}"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="☕ Забрать бесплатный кофе (MVP Pass)",
                        web_app=WebAppInfo(url=reward_url),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📸 Instagram @21coffeecz",
                        url=sponsor_url,
                    )
                ],
            ]
        )
        await bot.send_message(
            chat_id=payload.target_user_id,
            text=(
                f"🏆☕ <b>Поздравляем! Тебе начислена награда MVP от {sponsor_name}!</b>\n\n"
                f"🎁 Награда: <b>{reward_title}</b>\n"
                f"🎫 Твой код: <code>{code}</code>\n\n"
                f"Нажми кнопку ниже, чтобы привязать свою карту лояльности (Apple Wallet / номер телефона) для автоматического начисления кофе или показать MVP-пасс бариста на кассе!"
            ),
            reply_markup=kb,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning(f"Could not DM manual MVP reward to user {payload.target_user_id}: {e}")

    return {
        "status": "ok",
        "code": claim.code,
        "user_id": claim.user_id,
        "reward_title": claim.reward_title,
    }
