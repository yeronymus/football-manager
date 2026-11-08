import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.core.repositories.disciplinary_repository import DisciplinaryRepository
from app.core.repositories.stats_repository import StatsRepository
from app.core.services.game_numbering import clean_location, get_group_game_number
from app.core.timezone import format_prague_dt, to_prague_dt
from app.db.database import get_session
from app.db.models import Game, GameStats, PlayerCard, PlayerProfile, Signup, SignupStatus, User

router = APIRouter(tags=["dashboard-leaderboards"])


def _dash():
    import app.api.routers.dashboard as dash_mod

    return dash_mod


class PlayerActivityOut(BaseModel):
    user_id: int
    full_name: str
    username: Optional[str] = None
    position: Optional[str] = None
    rating: int = 100
    total_games: int = 0
    total_goals: int = 0
    total_mvps: int = 0
    games_last_4_weeks: int = 0
    last_game_date: Optional[str] = None
    days_since_last_game: Optional[int] = None
    total_lates: int = 0
    late_percentage: float = 0.0
    is_core: bool = False
    is_dormant: bool = False
    active_card_type: Optional[str] = None


class GroupAnalyticsOut(BaseModel):
    chat_id: int
    total_players: int
    core_count: int
    dormant_count: int
    players: List[PlayerActivityOut]


class PlayerHistoryGameOut(BaseModel):
    game_id: int
    game_number: Optional[int] = None
    date: str
    location: str
    status: str
    goals: int = 0
    is_mvp: bool = False
    is_late: bool = False


class PlayerCardOut(BaseModel):
    id: int
    card_type: str
    weeks: int
    reason: Optional[str] = None
    issued_at: datetime.datetime
    expires_at: datetime.datetime
    days_left: int
    issued_by_name: Optional[str] = None


class PlayerProfileDetailOut(BaseModel):
    user_id: int
    full_name: str
    username: Optional[str] = None
    position: Optional[str] = None
    rating: int = 100
    total_games: int = 0
    total_goals: int = 0
    total_mvps: int = 0
    total_lates: int = 0
    late_percentage: float = 0.0
    active_card: Optional[PlayerCardOut] = None
    recent_matches: List[PlayerHistoryGameOut]


@router.get("/groups/{chat_id}/analytics", response_model=GroupAnalyticsOut)
async def get_group_analytics(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    await _dash().check_admin_rights(chat_id, user_id, session=session)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    four_weeks_ago = now_utc - datetime.timedelta(days=28)

    last_game_subq = (
        select(Signup.user_id, func.max(Game.date_time).label("last_game_date"))
        .join(Game, Game.id == Signup.game_id)
        .where(Game.chat_id == chat_id, Signup.status == SignupStatus.ACTIVE)
        .group_by(Signup.user_id)
        .subquery()
    )

    recent_games_subq = (
        select(Signup.user_id, func.count(Signup.id).label("games_last_4w"))
        .join(Game, Game.id == Signup.game_id)
        .where(
            Game.chat_id == chat_id,
            Signup.status == SignupStatus.ACTIVE,
            Game.date_time >= four_weeks_ago,
        )
        .group_by(Signup.user_id)
        .subquery()
    )

    goals_subq = (
        select(
            GameStats.user_id,
            func.coalesce(func.sum(GameStats.goals), 0).label("group_goals"),
        )
        .join(Game, Game.id == GameStats.game_id)
        .where(Game.chat_id == chat_id)
        .group_by(GameStats.user_id)
        .subquery()
    )

    lates_subq = (
        select(Signup.user_id, func.count(Signup.id).label("group_lates"))
        .join(Game, Game.id == Signup.game_id)
        .where(
            Game.chat_id == chat_id,
            Signup.status == SignupStatus.ACTIVE,
            Signup.is_late == True,  # noqa: E712
        )
        .group_by(Signup.user_id)
        .subquery()
    )

    stmt = (
        select(
            User.user_id,
            User.full_name,
            User.username,
            User.player_position,
            func.coalesce(PlayerProfile.rating, User.rating, 100).label("rating"),
            func.coalesce(PlayerProfile.games_played, 0).label("games_played"),
            func.coalesce(PlayerProfile.stats_mvp, 0).label("stats_mvp"),
            func.coalesce(goals_subq.c.group_goals, 0).label("goals"),
            func.coalesce(lates_subq.c.group_lates, 0).label("group_lates"),
            last_game_subq.c.last_game_date,
            func.coalesce(recent_games_subq.c.games_last_4w, 0).label("games_last_4w"),
            User.created_at,
        )
        .outerjoin(
            PlayerProfile,
            (PlayerProfile.user_id == User.user_id) & (PlayerProfile.chat_id == chat_id),
        )
        .outerjoin(last_game_subq, last_game_subq.c.user_id == User.user_id)
        .outerjoin(recent_games_subq, recent_games_subq.c.user_id == User.user_id)
        .outerjoin(goals_subq, goals_subq.c.user_id == User.user_id)
        .outerjoin(lates_subq, lates_subq.c.user_id == User.user_id)
        .where(
            User.user_id > 0,
            or_(
                PlayerProfile.chat_id == chat_id,
                last_game_subq.c.last_game_date.isnot(None),
            ),
        )
        .order_by(
            recent_games_subq.c.games_last_4w.desc().nullslast(),
            PlayerProfile.rating.desc().nullslast(),
        )
    )
    res = await session.execute(stmt)
    rows = res.all()

    now_prague = to_prague_dt(now_utc)
    players_out = []
    core_count = 0
    dormant_count = 0

    disc_repo = DisciplinaryRepository(session)
    cards_map = await disc_repo.get_active_cards_map(chat_id)

    for r in rows:
        uid = r.user_id
        last_dt = r.last_game_date
        days_ago = None
        if last_dt:
            last_dt_prague = to_prague_dt(last_dt)
            days_ago = (now_prague.date() - last_dt_prague.date()).days
        elif r.created_at:
            created_prague = to_prague_dt(r.created_at)
            days_ago = (now_prague.date() - created_prague.date()).days

        recent_4w = int(r.games_last_4w or 0)
        total_g = int(r.games_played or 0)
        is_core = recent_4w >= 2
        is_dormant = (days_ago is not None and days_ago >= 30) or (
            days_ago is None and total_g == 0
        )

        if is_core:
            core_count += 1
        if is_dormant:
            dormant_count += 1

        pos_str = (
            r.player_position.value
            if hasattr(r.player_position, "value")
            else str(r.player_position or "")
        )
        raw_lates = getattr(r, "group_lates", 0)
        tot_lates = int(raw_lates) if isinstance(raw_lates, (int, float)) else 0
        late_pct = round((tot_lates / total_g) * 100.0, 1) if total_g > 0 else 0.0

        players_out.append(
            PlayerActivityOut(
                user_id=uid,
                full_name=r.full_name,
                username=r.username,
                position=pos_str if pos_str else None,
                rating=int(r.rating or 100),
                total_games=total_g,
                total_goals=int(r.goals or 0),
                total_mvps=int(r.stats_mvp or 0),
                total_lates=tot_lates,
                late_percentage=late_pct,
                games_last_4_weeks=recent_4w,
                last_game_date=format_prague_dt(last_dt, "%d.%m.%Y") if last_dt else None,
                days_since_last_game=days_ago,
                is_core=is_core,
                is_dormant=is_dormant,
                active_card_type=cards_map.get(uid),
            )
        )

    return GroupAnalyticsOut(
        chat_id=chat_id,
        total_players=len(players_out),
        core_count=core_count,
        dormant_count=dormant_count,
        players=players_out,
    )


@router.get(
    "/groups/{chat_id}/players/{target_user_id}", response_model=PlayerProfileDetailOut
)
async def get_group_player_detail(
    chat_id: int,
    target_user_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    await _dash().check_admin_rights(chat_id, user_id, session=session)
    user = await session.get(User, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Player not found")

    prof = await session.scalar(
        select(PlayerProfile).where(
            PlayerProfile.user_id == target_user_id, PlayerProfile.chat_id == chat_id
        )
    )

    stats_repo = StatsRepository(session)
    goals_res = await stats_repo.get_user_group_goals(chat_id, target_user_id)
    history_rows = await stats_repo.get_recent_matches_for_user(
        chat_id, target_user_id, limit=10
    )

    recent_matches = []
    for g, gs, s in history_rows:
        g_num = await get_group_game_number(session, g)
        recent_matches.append(
            PlayerHistoryGameOut(
                game_id=g.id,
                game_number=g_num,
                date=format_prague_dt(g.date_time, "%d.%m.%Y"),
                location=clean_location(g.location),
                status=g.status.value,
                goals=gs.goals if gs else 0,
                is_mvp=gs.is_mvp if gs else False,
                is_late=bool(getattr(s, "is_late", False)) if s else False,
            )
        )

    total_lates = await stats_repo.get_user_group_lates(chat_id, target_user_id)
    total_games_played = prof.games_played if prof else len(history_rows)
    late_pct = (
        round((total_lates / total_games_played) * 100.0, 1)
        if total_games_played > 0
        else 0.0
    )

    disc_repo = DisciplinaryRepository(session)
    active_card_obj = await disc_repo.get_active_card(target_user_id, chat_id)
    active_card_out = None
    if (
        active_card_obj
        and isinstance(active_card_obj, PlayerCard)
        and hasattr(getattr(active_card_obj, "expires_at", None), "date")
    ):
        issued_by_user = (
            await session.get(User, active_card_obj.issued_by)
            if active_card_obj.issued_by
            else None
        )
        days_left = max(0, (active_card_obj.expires_at.date() - datetime.date.today()).days)
        active_card_out = PlayerCardOut(
            id=active_card_obj.id,
            card_type=active_card_obj.card_type,
            weeks=active_card_obj.weeks,
            reason=active_card_obj.reason,
            issued_at=active_card_obj.issued_at,
            expires_at=active_card_obj.expires_at,
            days_left=days_left,
            issued_by_name=issued_by_user.full_name if issued_by_user else None,
        )

    pos_str = (
        user.player_position.value
        if hasattr(user.player_position, "value")
        else str(user.player_position or "")
    )
    return PlayerProfileDetailOut(
        user_id=user.user_id,
        full_name=user.full_name,
        username=user.username,
        position=pos_str if pos_str else None,
        rating=prof.rating if prof else (user.rating or 100),
        total_games=prof.games_played if prof else 0,
        total_goals=int(goals_res or 0),
        total_mvps=prof.stats_mvp if prof else 0,
        total_lates=total_lates,
        late_percentage=late_pct,
        active_card=active_card_out,
        recent_matches=recent_matches,
    )
