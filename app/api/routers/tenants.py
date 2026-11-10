import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.config import settings
from app.core.domain.sport_presets import get_sport_preset
from app.core.domain.tenant_policy import (
    resolve_billing_mode,
    resolve_effective_modules,
    resolve_tenant_policy,
)
from app.core.i18n import normalize_locale_code
from app.core.repositories.tenant_repository import TenantRepository
from app.core.services.audit import record_audit_log
from app.core.services.billing import calculate_hybrid_settlement, resolve_game_billing
from app.core.services.game_numbering import clean_location, get_group_game_number
from app.core.services.saas import (
    assert_can_create_event,
    encrypt_secret_envelope,
    get_org_capabilities,
    resolve_plan_tier,
)
from app.core.services.shadow_vault import archive_and_anonymize_user, restore_user_from_vault
from app.db.database import get_session
from app.db.models import (
    Chat,
    Game,
    GameStatus,
    Language,
    Organization,
    OrganizationMember,
    PlayerProfile,
    Signup,
    SignupStatus,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard-tenants"])


def _dash():
    import app.api.routers.dashboard as dash_mod

    return dash_mod


class GroupOut(BaseModel):
    chat_id: int
    title: str
    is_active: Optional[bool] = True
    language: Optional[str] = "en"
    currency: Optional[str] = "CZK"
    timezone: Optional[str] = "Europe/Prague"
    sport_type: Optional[str] = "football"
    billing_mode: Optional[str] = "manual"
    policy: Optional[dict] = None
    payment_info: Optional[str] = None
    default_location: Optional[str] = None
    default_price: Optional[int] = None
    default_team_count: Optional[int] = None
    default_max_players: Optional[int] = None
    default_main_players_count: Optional[int] = None
    default_duration: Optional[float] = None
    default_gk_hours: Optional[int] = None
    default_registration_hours: Optional[int] = None
    default_signup_limit: Optional[int] = None


class GroupUpdate(BaseModel):
    is_active: Optional[bool] = None
    language: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    sport_type: Optional[str] = None
    billing_mode: Optional[str] = None
    policy: Optional[dict] = None
    payment_info: Optional[str] = None
    default_location: Optional[str] = None
    default_price: Optional[int] = None
    default_team_count: Optional[int] = None
    default_max_players: Optional[int] = None
    default_main_players_count: Optional[int] = None
    default_duration: Optional[float] = None
    default_gk_hours: Optional[int] = None
    default_registration_hours: Optional[int] = None
    default_signup_limit: Optional[int] = None


class GameSummaryOut(BaseModel):
    id: int
    game_number: Optional[int] = None
    location: str
    date_time: datetime.datetime
    status: str
    players_count: int
    max_players: int
    paid_count: int
    team_count: int
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    score_c: Optional[int] = None


@router.get("/groups", response_model=List[GroupOut])
async def get_dashboard_groups(
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """Returns groups the user has admin access to. Superadmins see all groups."""
    is_superadmin = False
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        is_superadmin = True
    else:
        user = await session.get(User, user_id)
        if user and getattr(user, "is_superadmin", False):
            is_superadmin = True

    tenant_repo = TenantRepository(session)
    chats = await tenant_repo.list_for_admin(user_id=user_id, is_superadmin=is_superadmin)
    logger.info(
        "Dashboard: User %s (superadmin=%s) fetched %s chats.",
        user_id,
        is_superadmin,
        len(chats),
    )

    return [
        GroupOut(
            chat_id=chat.chat_id,
            title=chat.title,
            is_active=chat.is_active,
            language=normalize_locale_code(chat.language, default="en"),
            currency=getattr(chat, "currency", None) or "CZK",
            timezone=getattr(chat, "timezone", None) or "Europe/Prague",
            sport_type=getattr(chat, "sport_type", None) or "football",
            billing_mode=resolve_billing_mode(getattr(chat, "billing_mode", None)).value,
            policy=resolve_tenant_policy(chat).model_dump(),
            payment_info=chat.payment_info,
            default_location=chat.default_location,
            default_price=chat.default_price,
            default_team_count=chat.default_team_count,
            default_max_players=chat.default_max_players,
            default_main_players_count=chat.default_main_players_count,
            default_duration=chat.default_duration,
            default_gk_hours=chat.default_gk_hours,
            default_registration_hours=chat.default_registration_hours,
            default_signup_limit=chat.default_signup_limit,
        )
        for chat in chats
    ]


@router.patch("/groups/{chat_id}")
async def update_group_settings(
    chat_id: int,
    data: GroupUpdate,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    await _dash().check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "language" and value is not None:
            norm = normalize_locale_code(value, default="en")
            try:
                chat.language = Language(norm)
            except ValueError:
                chat.language = Language.en
        elif field == "billing_mode" and value is not None:
            chat.billing_mode = resolve_billing_mode(value).value
        elif field == "currency" and value is not None:
            chat.currency = (value or "CZK").strip().upper()[:8]
        elif field == "sport_type" and value is not None:
            chat.sport_type = get_sport_preset(value).code
        elif field == "policy" and isinstance(value, dict):
            merged = dict(chat.policy or {})
            merged.update(value)
            chat.policy = resolve_tenant_policy(merged).model_dump()
        else:
            setattr(chat, field, value)

    record_audit_log(
        session,
        action="TENANT_SETTINGS_UPDATE",
        actor_user_id=user_id,
        chat_id=chat_id,
        target_type="chat",
        target_id=chat_id,
        payload=update_data,
    )
    await session.commit()
    return {
        "status": "ok",
        "group": {
            "chat_id": chat.chat_id,
            "language": normalize_locale_code(chat.language, default="en"),
            "currency": getattr(chat, "currency", None) or "CZK",
            "timezone": getattr(chat, "timezone", None) or "Europe/Prague",
            "sport_type": getattr(chat, "sport_type", None) or "football",
            "billing_mode": resolve_billing_mode(getattr(chat, "billing_mode", None)).value,
            "policy": resolve_tenant_policy(chat).model_dump(),
            "payment_info": chat.payment_info,
            "default_location": chat.default_location,
            "default_price": chat.default_price,
            "default_team_count": chat.default_team_count,
            "default_max_players": chat.default_max_players,
            "default_main_players_count": chat.default_main_players_count,
            "default_duration": chat.default_duration,
            "default_gk_hours": chat.default_gk_hours,
            "default_registration_hours": chat.default_registration_hours,
            "default_signup_limit": chat.default_signup_limit,
        },
    }


@router.get("/groups/{chat_id}/games", response_model=List[GameSummaryOut])
async def get_group_games(
    chat_id: int,
    limit: int = Query(20, le=100),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    await _dash().check_admin_rights(chat_id, user_id, session=session)

    stmt = (
        select(
            Game,
            func.count(Signup.id).label("players_count"),
            func.sum(case((Signup.is_paid == True, 1), else_=0)).label("paid_count"),  # noqa: E712
        )
        .outerjoin(
            Signup, (Signup.game_id == Game.id) & (Signup.status == SignupStatus.ACTIVE)
        )
        .where(Game.chat_id == chat_id)
        .group_by(Game.id)
        .order_by(Game.date_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    out: List[GameSummaryOut] = []
    for game, count, paid_count in rows:
        g_num = await get_group_game_number(session, game)
        out.append(
            GameSummaryOut(
                id=game.id,
                game_number=g_num,
                location=clean_location(game.location),
                date_time=game.date_time,
                status=game.status.value,
                players_count=count,
                max_players=game.max_players,
                paid_count=paid_count or 0,
                team_count=game.team_count,
                score_a=game.score_a,
                score_b=game.score_b,
                score_c=game.score_c,
            )
        )
    return out


@router.delete("/games/{game_id}")
async def delete_game(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, user_id, session=session)

    try:
        from app.infrastructure.scheduler.service import SchedulerService

        scheduler = SchedulerService()
        scheduler.cancel_game_tasks(game_id)
    except Exception as e:
        logger.warning(f"Failed to cancel scheduler tasks for game {game_id}: {e}")

    try:
        from app.bot.main import bot

        if game.chat_id and game.message_id:
            await bot.delete_message(chat_id=game.chat_id, message_id=game.message_id)
        if game.chat_id and game.admin_message_id:
            await bot.delete_message(chat_id=game.chat_id, message_id=game.admin_message_id)
        if game.chat_id and game.voting_message_id:
            await bot.delete_message(chat_id=game.chat_id, message_id=game.voting_message_id)
    except Exception as e:
        logger.warning(f"Failed to delete telegram messages for deleted game {game_id}: {e}")

    await _dash().cache_service.evict(f"game_details:{game_id}")

    record_audit_log(
        session,
        action="GAME_DELETED",
        actor_user_id=user_id,
        chat_id=getattr(game, "chat_id", None),
        target_type="game",
        target_id=game_id,
        payload={"location": getattr(game, "location", None)},
    )
    await session.delete(game)
    await session.commit()

    return {"status": "ok", "message": "Game deleted successfully"}


@router.get("/groups/{chat_id}/attendance.csv")
async def export_group_attendance_csv(
    chat_id: int,
    send_dm: bool = False,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Exports a B2B HR / Cafeteria attendance & billing register in UTF-8 CSV format
    for the specified tenant group.
    """
    import csv
    import io
    from fastapi.responses import Response
    from app.db.models import GameStats, User

    await _dash().check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    currency = (getattr(chat, "currency", None) if chat else None) or "CZK"
    billing_mode = resolve_billing_mode(getattr(chat, "billing_mode", None) if chat else None).value

    stmt = (
        select(Game, Signup, User, GameStats)
        .join(Signup, Signup.game_id == Game.id)
        .join(User, User.user_id == Signup.user_id)
        .outerjoin(
            GameStats,
            (GameStats.game_id == Game.id) & (GameStats.user_id == User.user_id),
        )
        .where(Game.chat_id == chat_id)
        .order_by(Game.date_time.desc(), Signup.id.asc())
        .limit(2000)
    )
    res = await session.execute(stmt)
    rows = res.all()

    buf = io.StringIO()
    buf.write("\ufeff")  # UTF-8 BOM for Excel / Google Sheets compatibility
    writer = csv.writer(buf)
    writer.writerow(
        [
            "game_id",
            "sequence_number",
            "date_utc",
            "location",
            "user_id",
            "full_name",
            "username",
            "status",
            "team",
            "is_paid",
            "is_late",
            "goals",
            "assists",
            "is_mvp",
            "match_fee",
            "currency",
            "billing_mode",
        ]
    )
    for game, signup, user, stats in rows:
        writer.writerow(
            [
                game.id,
                getattr(game, "sequence_number", None) or game.id,
                game.date_time.isoformat() if getattr(game, "date_time", None) else "",
                clean_location(getattr(game, "location", "")) or "",
                user.user_id,
                user.full_name,
                user.username or "",
                signup.status.value if hasattr(signup.status, "value") else str(signup.status),
                signup.team.value if getattr(signup, "team", None) and hasattr(signup.team, "value") else "",
                bool(getattr(signup, "is_paid", False)),
                bool(getattr(signup, "is_late", False)),
                getattr(stats, "goals", 0) if stats else 0,
                getattr(stats, "assists", 0) if stats else 0,
                bool(getattr(stats, "is_mvp", False)) if stats else False,
                getattr(game, "price", 0) or 0,
                currency,
                billing_mode,
            ]
        )

    csv_content = buf.getvalue()
    filename = f"attendance_{abs(chat_id)}.csv"
    should_send_dm = bool(send_dm) if not hasattr(send_dm, "default") else bool(send_dm.default)

    if should_send_dm:
        from aiogram.types import BufferedInputFile
        from fastapi.responses import JSONResponse
        from app.bot.instance import bot

        title = (getattr(chat, "title", None) if chat else None) or str(chat_id)
        doc = BufferedInputFile(csv_content.encode("utf-8"), filename=filename)
        await bot.send_document(
            chat_id=user_id,
            document=doc,
            caption=f"📊 <b>HR / Attendance CSV Export</b>\n🏟 {title} ({len(rows)} rows)",
            parse_mode="HTML",
        )
        return JSONResponse({"status": "sent_to_dm", "rows": len(rows), "filename": filename})

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


class OrganizationCreateIn(BaseModel):
    slug: str
    name: str
    plan_tier: str = "pro"
    brand_color: Optional[str] = "#3b82f6"
    logo_url: Optional[str] = None
    allowed_email_domains: List[str] = []
    custom_bot_token: Optional[str] = None
    chat_ids: List[int] = []


class QuickSettleIn(BaseModel):
    summary_note: Optional[str] = None
    photo_album_url: Optional[str] = None
    total_cost_override: Optional[int] = None


@router.get("/groups/{chat_id}/capabilities")
async def get_group_capabilities(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Returns resolved event preset metadata, localized terminology, active pluggable modules,
    and B2B SaaS tier capabilities for the specified group.
    """
    await _dash().check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")

    lang = normalize_locale_code(chat.language, default="en")
    preset = get_sport_preset(chat.sport_type)
    modules = resolve_effective_modules(chat)
    policy = resolve_tenant_policy(chat)

    org = None
    if getattr(chat, "organization_id", None):
        org = await session.get(Organization, chat.organization_id)

    saas_caps = get_org_capabilities(org.plan_tier if org else "pro")
    quota_status = await assert_can_create_event(session, chat_id, enforce_strict=False)

    return {
        "chat_id": chat.chat_id,
        "title": chat.title,
        "preset_code": preset.code,
        "category": preset.category,
        "icon": preset.icon,
        "preset_name": preset.localized_name(lang),
        "terminology": preset.localized_terminology(lang),
        "modules": modules,
        "policy": policy.model_dump(),
        "organization": (
            {
                "id": org.id,
                "slug": org.slug,
                "name": org.name,
                "plan_tier": org.plan_tier,
                "brand_color": org.brand_color,
                "logo_url": org.logo_url,
            }
            if org
            else None
        ),
        "saas": saas_caps,
        "quota": quota_status,
    }


@router.post("/groups/{chat_id}/events/{game_id}/settle")
async def settle_event_without_score(
    chat_id: int,
    game_id: int,
    data: Optional[QuickSettleIn] = None,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Universal Event Settlement endpoint for non-sport events (Trips, Book Clubs, Quizzes)
    or sport sessions where score tracking is disabled.
    Marks the event as FINISHED, increments attendance counters for active participants,
    and computes hybrid financial settlement (Co-Pay / MultiSport / SPAYD QR).
    """
    from dataclasses import asdict

    await _dash().check_admin_rights(chat_id, user_id, session=session)
    game = await session.get(Game, game_id)
    if not game or game.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Event not found in this group")

    chat = await session.get(Chat, chat_id)
    policy = resolve_tenant_policy(chat)

    signups_res = await session.execute(
        select(Signup, User)
        .join(User, User.user_id == Signup.user_id)
        .where(Signup.game_id == game_id, Signup.status == SignupStatus.ACTIVE)
    )
    active_rows = signups_res.all()

    already_finished = game.status == GameStatus.FINISHED
    game.status = GameStatus.FINISHED

    multisport_count = 0
    for signup, u in active_rows:
        if getattr(u, "has_multisport_card", False):
            multisport_count += 1
        if not already_finished:
            u.games_played = int(u.games_played or 0) + 1
            u.stats_matches = int(u.stats_matches or 0) + 1
            prof_res = await session.execute(
                select(PlayerProfile).where(
                    PlayerProfile.chat_id == chat_id,
                    PlayerProfile.user_id == u.user_id,
                )
            )
            prof = prof_res.scalar_one_or_none()
            if prof:
                prof.games_played = int(prof.games_played or 0) + 1
                prof.stats_matches = int(prof.stats_matches or 0) + 1

    participant_count = max(1, len(active_rows))
    per_person_price = int(getattr(game, "price", 0) or 0)
    total_cost = (
        data.total_cost_override
        if (data and data.total_cost_override is not None)
        else per_person_price * participant_count
    )

    hybrid = calculate_hybrid_settlement(
        total_cost=total_cost,
        participant_count=participant_count,
        multisport_count=multisport_count if policy.multisport_enabled else 0,
        employer_subsidy_pct=policy.employer_subsidy_pct,
        multisport_discount=policy.multisport_discount_amount,
    )
    billing_summary = resolve_game_billing(game, chat=chat)

    record_audit_log(
        session,
        action="EVENT_SETTLED_WITHOUT_SCORE",
        actor_user_id=user_id,
        chat_id=chat_id,
        target_type="game",
        target_id=game_id,
        payload={
            "participants": len(active_rows),
            "multisport_count": multisport_count,
            "summary_note": data.summary_note if data else None,
            "photo_album_url": data.photo_album_url if data else None,
        },
    )
    await session.commit()

    return {
        "status": "settled",
        "game_id": game.id,
        "participants_count": len(active_rows),
        "hybrid_settlement": asdict(hybrid),
        "billing": asdict(billing_summary),
    }


@router.post("/groups/{chat_id}/members/{target_user_id}/anonymize")
async def anonymize_group_member(
    chat_id: int,
    target_user_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Archives a user's real identity into the encrypted ShadowIdentityVault (cold storage)
    and anonymizes their public profile ('Former Participant #ID') for GDPR compliance.
    """
    await _dash().check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    org_id = getattr(chat, "organization_id", None) if chat else None
    try:
        res = await archive_and_anonymize_user(
            session,
            user_id=target_user_id,
            actor_user_id=user_id,
            organization_id=org_id,
            chat_id=chat_id,
            reason="admin_gdpr_erasure",
        )
        await session.commit()
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/groups/{chat_id}/members/{target_user_id}/restore")
async def restore_group_member(
    chat_id: int,
    target_user_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """Restores an anonymized user's real identity from the encrypted ShadowIdentityVault."""
    await _dash().check_admin_rights(chat_id, user_id, session=session)
    try:
        res = await restore_user_from_vault(
            session,
            user_id=target_user_id,
            actor_user_id=user_id,
            chat_id=chat_id,
        )
        await session.commit()
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/organizations")
async def create_b2b_organization(
    data: OrganizationCreateIn,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Creates a top-level B2B Organization (Company / Club) and attaches specified group chats.
    """
    clean_slug = data.slug.strip().lower().replace(" ", "-")
    existing = (
        await session.execute(select(Organization).where(Organization.slug == clean_slug))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Organization slug already exists")

    tier = resolve_plan_tier(data.plan_tier).value
    encrypted_token = (
        encrypt_secret_envelope(data.custom_bot_token) if data.custom_bot_token else None
    )

    org = Organization(
        slug=clean_slug,
        name=data.name.strip(),
        plan_tier=tier,
        brand_color=data.brand_color,
        logo_url=data.logo_url,
        allowed_email_domains=data.allowed_email_domains or [],
        custom_bot_token_encrypted=encrypted_token,
        owner_user_id=user_id,
    )
    session.add(org)
    await session.flush()

    owner_member = OrganizationMember(
        organization_id=org.id,
        user_id=user_id,
        role="owner",
        is_verified_employee=True,
    )
    session.add(owner_member)

    attached_chats = []
    for cid in data.chat_ids:
        await _dash().check_admin_rights(cid, user_id, session=session)
        chat = await session.get(Chat, cid)
        if chat:
            chat.organization_id = org.id
            attached_chats.append(cid)

    record_audit_log(
        session,
        action="ORGANIZATION_CREATED",
        actor_user_id=user_id,
        target_type="organization",
        target_id=org.id,
        payload={"slug": org.slug, "plan_tier": tier, "attached_chats": attached_chats},
    )
    await session.commit()

    return {
        "id": org.id,
        "slug": org.slug,
        "name": org.name,
        "plan_tier": org.plan_tier,
        "attached_chats": attached_chats,
        "capabilities": get_org_capabilities(org.plan_tier),
    }


@router.get("/organizations/{org_id}/analytics")
async def get_organization_wide_analytics(
    org_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Company-Wide B2B HR & Community Analytics across all attached group chats
    (e.g. Football + Volleyball + Trip to Dresden + Book Club).
    """
    org = await session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    chats = (
        await session.execute(select(Chat).where(Chat.organization_id == org_id))
    ).scalars().all()
    chat_ids = [c.chat_id for c in chats]

    if not chat_ids:
        return {
            "organization_id": org.id,
            "slug": org.slug,
            "name": org.name,
            "plan_tier": org.plan_tier,
            "branches_count": 0,
            "total_events": 0,
            "unique_active_participants": 0,
            "total_participations": 0,
            "average_utilization_pct": 0.0,
            "branches": [],
        }

    # Verify user is owner/member of org or admin of at least one attached chat
    if org.owner_user_id != user_id:
        await _dash().check_admin_rights(chat_ids[0], user_id, session=session)

    games = (
        await session.execute(select(Game).where(Game.chat_id.in_(chat_ids)))
    ).scalars().all()
    game_ids = [g.id for g in games]

    unique_users = set()
    total_participations = 0
    signups_by_game: dict[int, int] = {}

    if game_ids:
        s_rows = (
            await session.execute(
                select(Signup.game_id, Signup.user_id).where(
                    Signup.game_id.in_(game_ids),
                    Signup.status == SignupStatus.ACTIVE,
                )
            )
        ).all()
        for gid, uid in s_rows:
            if uid > 0:
                unique_users.add(uid)
            total_participations += 1
            signups_by_game[gid] = signups_by_game.get(gid, 0) + 1

    utilizations = []
    for g in games:
        cap = max(1, int(g.main_players_count or g.max_players or 1))
        filled = signups_by_game.get(g.id, 0)
        utilizations.append(min(100.0, (filled / cap) * 100.0))

    avg_util = round(sum(utilizations) / len(utilizations), 1) if utilizations else 0.0

    branches_summary = []
    for c in chats:
        preset = get_sport_preset(c.sport_type)
        c_games = [g for g in games if g.chat_id == c.chat_id]
        branches_summary.append(
            {
                "chat_id": c.chat_id,
                "title": c.title,
                "preset_code": preset.code,
                "category": preset.category,
                "icon": preset.icon,
                "events_count": len(c_games),
            }
        )

    return {
        "organization_id": org.id,
        "slug": org.slug,
        "name": org.name,
        "plan_tier": org.plan_tier,
        "branches_count": len(chats),
        "total_events": len(games),
        "unique_active_participants": len(unique_users),
        "total_participations": total_participations,
        "average_utilization_pct": avg_util,
        "branches": branches_summary,
    }

