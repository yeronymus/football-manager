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
from app.core.domain.tenant_policy import resolve_billing_mode, resolve_tenant_policy
from app.core.i18n import normalize_locale_code
from app.core.repositories.tenant_repository import TenantRepository
from app.core.services.audit import record_audit_log
from app.core.services.game_numbering import clean_location, get_group_game_number
from app.db.database import get_session
from app.db.models import Chat, Game, Language, Signup, SignupStatus, User

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

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="attendance_{abs(chat_id)}.csv"'
        },
    )
