from fastapi import APIRouter, Depends, HTTPException, Query, Body, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from pydantic import BaseModel
from typing import List, Optional
import datetime
import logging
import re
import json
import html

from app.db.database import get_session
from app.db.models import Chat, ChatAdmin, User, Game, Signup, SignupStatus, Language
from app.api.auth import get_user_from_header, check_admin_rights
from app.config import settings
from app.core.services.cache import cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def clean_location(loc: str) -> str:
    if not loc: return loc
    return re.sub(r'\(?https?://[^\s)]+\)?', '', loc).strip()

class GroupOut(BaseModel):
    chat_id: int
    title: str
    is_active: Optional[bool] = True
    language: Optional[Language] = Language.ru
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
    session: AsyncSession = Depends(get_session)
):
    """
    Returns groups the user has admin access to.
    Superadmins see all groups.
    """
    # Check if user is superadmin
    is_superadmin = False
    if user_id in settings.admin_ids or user_id == settings.system_owner_id:
        is_superadmin = True
    else:
        user = await session.get(User, user_id)
        if user and getattr(user, 'is_superadmin', False):
            is_superadmin = True

    if is_superadmin:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()
        logger.info(f"Dashboard: User {user_id} is superadmin, fetched {len(chats)} chats.")
    else:
        # Fetch only groups where user is ChatAdmin
        result = await session.execute(
            select(Chat).join(ChatAdmin).where(ChatAdmin.user_id == user_id)
        )
        chats = result.scalars().all()
        logger.info(f"Dashboard: User {user_id} is regular admin, fetched {len(chats)} chats.")

    return [
        GroupOut(
            chat_id=chat.chat_id,
            title=chat.title,
            is_active=chat.is_active,
            language=chat.language,
            payment_info=chat.payment_info,
            default_location=chat.default_location,
            default_price=chat.default_price,
            default_team_count=chat.default_team_count,
            default_max_players=chat.default_max_players,
            default_main_players_count=chat.default_main_players_count,
            default_duration=chat.default_duration,
            default_gk_hours=chat.default_gk_hours,
            default_registration_hours=chat.default_registration_hours,
            default_signup_limit=chat.default_signup_limit
        ) for chat in chats
    ]

class GroupUpdate(BaseModel):
    is_active: Optional[bool] = None
    language: Optional[Language] = None
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

@router.patch("/groups/{chat_id}")
async def update_group_settings(
    chat_id: int,
    data: GroupUpdate,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    await check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")
        
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chat, field, value)
        
    await session.commit()
    return {"status": "ok"}

@router.get("/groups/{chat_id}/games", response_model=List[GameSummaryOut])
async def get_group_games(
    chat_id: int,
    limit: int = Query(20, le=100),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    await check_admin_rights(chat_id, user_id, session=session)
    
    # Get games with player count and paid count
    stmt = (
        select(
            Game, 
            func.count(Signup.id).label("players_count"),
            func.sum(case((Signup.is_paid == True, 1), else_=0)).label("paid_count")
        )
        .outerjoin(Signup, (Signup.game_id == Game.id) & (Signup.status == SignupStatus.ACTIVE))
        .where(Game.chat_id == chat_id)
        .group_by(Game.id)
        .order_by(Game.date_time.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()
    
    out = []
    has_changes = False
    from app.bot.utils import get_group_game_number
    for game, count, paid_count in rows:
        cleaned_loc = clean_location(game.location)
        if cleaned_loc != game.location:
            game.location = cleaned_loc
            has_changes = True
            
        g_num = await get_group_game_number(session, game)
        out.append(
            GameSummaryOut(
                id=game.id,
                game_number=g_num,
                location=game.location,
                date_time=game.date_time,
                status=game.status.value,
                players_count=count,
                max_players=game.max_players,
                paid_count=paid_count or 0,
                team_count=game.team_count,
                score_a=game.score_a,
                score_b=game.score_b,
                score_c=game.score_c
            )
        )
    if has_changes:
        await session.commit()
    return out

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

class PlayerCardOut(BaseModel):
    id: int
    card_type: str
    weeks: int
    reason: Optional[str] = None
    issued_at: datetime.datetime
    expires_at: datetime.datetime
    days_left: int
    issued_by_name: Optional[str] = None

class IssueCardIn(BaseModel):
    card_type: str
    weeks: int = 4
    reason: Optional[str] = None

class PlayerProfileDetailOut(BaseModel):
    user_id: int
    full_name: str
    username: Optional[str] = None
    position: Optional[str] = None
    rating: int = 100
    total_games: int = 0
    total_goals: int = 0
    total_mvps: int = 0
    active_card: Optional[PlayerCardOut] = None
    recent_matches: List[PlayerHistoryGameOut]

@router.get("/groups/{chat_id}/analytics", response_model=GroupAnalyticsOut)
async def get_group_analytics(
    chat_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    await check_admin_rights(chat_id, user_id, session=session)

    from sqlalchemy import or_
    from app.core.timezone import to_prague_dt, format_prague_dt
    from app.db.models import PlayerProfile, GameStats

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    four_weeks_ago = now_utc - datetime.timedelta(days=28)

    # Subquery: Last played game per user in this chat
    last_game_subq = (
        select(
            Signup.user_id,
            func.max(Game.date_time).label("last_game_date")
        )
        .join(Game, Game.id == Signup.game_id)
        .where(
            Game.chat_id == chat_id,
            Signup.status == SignupStatus.ACTIVE
        )
        .group_by(Signup.user_id)
        .subquery()
    )

    # Subquery: Games played in last 4 weeks in this chat
    recent_games_subq = (
        select(
            Signup.user_id,
            func.count(Signup.id).label("games_last_4w")
        )
        .join(Game, Game.id == Signup.game_id)
        .where(
            Game.chat_id == chat_id,
            Signup.status == SignupStatus.ACTIVE,
            Game.date_time >= four_weeks_ago
        )
        .group_by(Signup.user_id)
        .subquery()
    )

    # Subquery: Total goals in this chat
    goals_subq = (
        select(
            GameStats.user_id,
            func.coalesce(func.sum(GameStats.goals), 0).label("group_goals")
        )
        .join(Game, Game.id == GameStats.game_id)
        .where(Game.chat_id == chat_id)
        .group_by(GameStats.user_id)
        .subquery()
    )

    # Main query
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
            last_game_subq.c.last_game_date,
            func.coalesce(recent_games_subq.c.games_last_4w, 0).label("games_last_4w"),
            User.created_at
        )
        .outerjoin(PlayerProfile, (PlayerProfile.user_id == User.user_id) & (PlayerProfile.chat_id == chat_id))
        .outerjoin(last_game_subq, last_game_subq.c.user_id == User.user_id)
        .outerjoin(recent_games_subq, recent_games_subq.c.user_id == User.user_id)
        .outerjoin(goals_subq, goals_subq.c.user_id == User.user_id)
        .where(
            User.user_id > 0,  # Exclude guest pseudo-IDs
            or_(
                PlayerProfile.chat_id == chat_id,
                last_game_subq.c.last_game_date.isnot(None)
            )
        )
        .order_by(
            recent_games_subq.c.games_last_4w.desc().nullslast(),
            PlayerProfile.rating.desc().nullslast()
        )
    )
    res = await session.execute(stmt)
    rows = res.all()

    now_prague = to_prague_dt(now_utc)
    players_out = []
    core_count = 0
    dormant_count = 0

    from app.db.models import PlayerCard
    active_cards_res = await session.execute(
        select(PlayerCard.user_id, PlayerCard.card_type)
        .where(
            PlayerCard.chat_id == chat_id,
            PlayerCard.is_active == True,
            PlayerCard.expires_at > func.now(),
        )
    )
    cards_map = {row[0]: row[1] for row in active_cards_res.all()}

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
        is_core = (recent_4w >= 2)
        is_dormant = (days_ago is not None and days_ago >= 30) or (days_ago is None and total_g == 0)

        if is_core:
            core_count += 1
        if is_dormant:
            dormant_count += 1

        pos_str = r.player_position.value if hasattr(r.player_position, "value") else str(r.player_position or "")
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
                games_last_4_weeks=recent_4w,
                last_game_date=format_prague_dt(last_dt, "%d.%m.%Y") if last_dt else None,
                days_since_last_game=days_ago,
                is_core=is_core,
                is_dormant=is_dormant,
                active_card_type=cards_map.get(uid)
            )
        )

    return GroupAnalyticsOut(
        chat_id=chat_id,
        total_players=len(players_out),
        core_count=core_count,
        dormant_count=dormant_count,
        players=players_out
    )

@router.get("/groups/{chat_id}/players/{target_user_id}", response_model=PlayerProfileDetailOut)
async def get_group_player_detail(
    chat_id: int,
    target_user_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    await check_admin_rights(chat_id, user_id, session=session)
    user = await session.get(User, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Player not found")

    from app.db.models import PlayerProfile, GameStats
    from app.core.timezone import format_prague_dt
    from app.bot.utils import get_group_game_number

    prof = await session.scalar(
        select(PlayerProfile).where(PlayerProfile.user_id == target_user_id, PlayerProfile.chat_id == chat_id)
    )
    goals_res = await session.scalar(
        select(func.coalesce(func.sum(GameStats.goals), 0))
        .join(Game, Game.id == GameStats.game_id)
        .where(Game.chat_id == chat_id, GameStats.user_id == target_user_id)
    )

    # Fetch last 10 games
    stmt = (
        select(Game, GameStats)
        .join(Signup, (Signup.game_id == Game.id) & (Signup.user_id == target_user_id))
        .outerjoin(GameStats, (GameStats.game_id == Game.id) & (GameStats.user_id == target_user_id))
        .where(Game.chat_id == chat_id, Signup.status == SignupStatus.ACTIVE)
        .order_by(Game.date_time.desc())
        .limit(10)
    )
    res = await session.execute(stmt)
    history_rows = res.all()

    recent_matches = []
    for g, gs in history_rows:
        g_num = await get_group_game_number(session, g)
        recent_matches.append(
            PlayerHistoryGameOut(
                game_id=g.id,
                game_number=g_num,
                date=format_prague_dt(g.date_time, "%d.%m.%Y"),
                location=clean_location(g.location),
                status=g.status.value,
                goals=gs.goals if gs else 0,
                is_mvp=gs.is_mvp if gs else False
            )
        )

    # Fetch active disciplinary card
    from app.db.models import PlayerCard
    from sqlalchemy import update
    active_card_obj = await session.scalar(
        select(PlayerCard)
        .where(
            PlayerCard.user_id == target_user_id,
            PlayerCard.chat_id == chat_id,
            PlayerCard.is_active == True,
            PlayerCard.expires_at > func.now()
        )
        .order_by(PlayerCard.id.desc())
        .limit(1)
    )
    active_card_out = None
    if active_card_obj and isinstance(active_card_obj, PlayerCard) and hasattr(getattr(active_card_obj, "expires_at", None), "date"):
        issued_by_user = await session.get(User, active_card_obj.issued_by) if active_card_obj.issued_by else None
        days_left = max(0, (active_card_obj.expires_at.date() - datetime.date.today()).days)
        active_card_out = PlayerCardOut(
            id=active_card_obj.id,
            card_type=active_card_obj.card_type,
            weeks=active_card_obj.weeks,
            reason=active_card_obj.reason,
            issued_at=active_card_obj.issued_at,
            expires_at=active_card_obj.expires_at,
            days_left=days_left,
            issued_by_name=issued_by_user.full_name if issued_by_user else None
        )

    pos_str = user.player_position.value if hasattr(user.player_position, "value") else str(user.player_position or "")
    return PlayerProfileDetailOut(
        user_id=user.user_id,
        full_name=user.full_name,
        username=user.username,
        position=pos_str if pos_str else None,
        rating=prof.rating if prof else (user.rating or 100),
        total_games=prof.games_played if prof else 0,
        total_goals=int(goals_res or 0),
        total_mvps=prof.stats_mvp if prof else 0,
        active_card=active_card_out,
        recent_matches=recent_matches
    )

@router.post("/groups/{chat_id}/players/{target_user_id}/card")
async def issue_player_card(
    chat_id: int,
    target_user_id: int,
    data: IssueCardIn,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    await check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")
        
    target_user = await session.get(User, target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Player not found")

    card_type = data.card_type.upper()
    if card_type not in ["YELLOW", "RED"]:
        raise HTTPException(status_code=400, detail="Invalid card_type. Must be YELLOW or RED.")

    if data.weeks < 1:
        raise HTTPException(status_code=400, detail="Duration must be at least 1 week.")

    from app.db.models import PlayerCard
    from sqlalchemy import update

    # Deactivate existing active cards
    await session.execute(
        update(PlayerCard)
        .where(
            PlayerCard.user_id == target_user_id,
            PlayerCard.chat_id == chat_id,
            PlayerCard.is_active == True
        )
        .values(is_active=False)
    )

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now_utc + datetime.timedelta(weeks=data.weeks)

    card = PlayerCard(
        user_id=target_user_id,
        chat_id=chat_id,
        card_type=card_type,
        weeks=data.weeks,
        reason=data.reason.strip() if data.reason else None,
        issued_by=user_id,
        issued_at=now_utc,
        expires_at=expires_at,
        is_active=True
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)

    # Send Telegram DM to player
    dm_status = "delivered"
    try:
        from app.bot.instance import bot
        from app.core.timezone import format_prague_dt
        exp_prague = format_prague_dt(expires_at, "%d.%m.%Y")
        group_title = chat.title or "Football Group"
        is_red = (card_type == "RED")
        
        target_lang = "ru"
        if getattr(target_user, "language", None):
            target_lang = target_user.language.value if hasattr(target_user.language, "value") else str(target_user.language)

        reason_str = html.escape(card.reason) if card.reason else None

        if target_lang == "en":
            card_title = "🟥 Red Card (Suspended)" if is_red else "🟨 Yellow Card"
            effect_txt = "\n🚫 <b>Registration for matches in this group is suspended</b> until expiration." if is_red else "\nℹ️ This is a disciplinary warning. Please respect the community fair play rules."
            reason_line = f"\n📝 Reason: {reason_str}" if reason_str else ""
            msg = (
                f"⚠️ <b>Disciplinary Notice</b>\n\n"
                f"You have been issued a <b>{card_title}</b> in group <b>{html.escape(group_title)}</b>.\n"
                f"⏱ Duration: <b>{data.weeks} week(s)</b> (until {exp_prague}){reason_line}\n"
                f"{effect_txt}"
            )
        else:
            card_title = "🟥 Красная карточка" if is_red else "🟨 Жёлтая карточка"
            effect_txt = "\n🚫 <b>Запись на матчи в этой группе приостановлена</b> на время действия дисквалификации." if is_red else "\nℹ️ Это дисциплинарное предупреждение. Пожалуйста, соблюдайте правила fair play."
            reason_line = f"\n📝 Причина: {reason_str}" if reason_str else ""
            msg = (
                f"⚠️ <b>Дисциплинарное решение</b>\n\n"
                f"Вам выдана <b>{card_title}</b> в группе <b>{html.escape(group_title)}</b>.\n"
                f"⏱ Срок действия: <b>{data.weeks} нед.</b> (до {exp_prague}){reason_line}\n"
                f"{effect_txt}"
            )

        await bot.send_message(target_user_id, msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Failed to DM card notice to {target_user_id}: {e}")
        dm_status = "failed"

    days_left = max(0, (expires_at.date() - datetime.date.today()).days)
    admin_user = await session.get(User, user_id)
    return {
        "status": "ok",
        "card": {
            "id": card.id,
            "card_type": card.card_type,
            "weeks": card.weeks,
            "reason": card.reason,
            "issued_at": card.issued_at.isoformat(),
            "expires_at": card.expires_at.isoformat(),
            "days_left": days_left,
            "issued_by_name": admin_user.full_name if admin_user else None
        },
        "dm_status": dm_status
    }

@router.delete("/groups/{chat_id}/players/{target_user_id}/card")
async def revoke_player_card(
    chat_id: int,
    target_user_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    await check_admin_rights(chat_id, user_id, session=session)
    chat = await session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Group not found")

    from app.db.models import PlayerCard
    from sqlalchemy import update

    res = await session.execute(
        update(PlayerCard)
        .where(
            PlayerCard.user_id == target_user_id,
            PlayerCard.chat_id == chat_id,
            PlayerCard.is_active == True
        )
        .values(is_active=False)
    )
    await session.commit()

    if (res.rowcount or 0) > 0:
        try:
            from app.bot.instance import bot
            target_user = await session.get(User, target_user_id)
            target_lang = "ru"
            if target_user and getattr(target_user, "language", None):
                target_lang = target_user.language.value if hasattr(target_user.language, "value") else str(target_user.language)
            group_title = chat.title or "Football Group"
            if target_lang == "en":
                msg = f"✅ Your disciplinary card in group <b>{html.escape(group_title)}</b> has been lifted by the admin."
            else:
                msg = f"✅ Дисциплинарная санкция в группе <b>{html.escape(group_title)}</b> была досрочно снята администратором."
            await bot.send_message(target_user_id, msg, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Failed to DM card lift notice to {target_user_id}: {e}")

    return {"status": "ok", "message": "Card revoked successfully"}

class PlayerDetailOut(BaseModel):
    signup_id: int
    user_id: int
    full_name: str
    status: str
    is_paid: bool
    position: Optional[str]
    team: Optional[str] = None
    goals: int = 0
    mvp_votes: int = 0
    is_mvp: bool = False
    notify_status: Optional[str] = None
    notified_at: Optional[str] = None

class GameDetailOut(BaseModel):
    id: int
    game_number: Optional[int] = None
    location: str
    date_time: datetime.datetime
    status: str
    price: int
    team_count: int
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    score_c: Optional[int] = None
    players: List[PlayerDetailOut]

async def _get_game_votes_map(session: AsyncSession, game_id: int) -> dict[int, int]:
    """Helper to fetch voting results maps target_id -> count."""
    from app.db.models import Vote
    votes_res = await session.execute(
        select(Vote.target_id, func.count(Vote.id))
        .where(Vote.game_id == game_id)
        .group_by(Vote.target_id)
    )
    return {v[0]: v[1] for v in votes_res.all()}

def _format_game_players(rows, votes_map, notify_logs=None) -> List[PlayerDetailOut]:
    """Helper to format the players list from joined query rows."""
    if notify_logs is None:
        notify_logs = {}
    players = []
    for signup, user, u_stats in rows:
        v_count = votes_map.get(user.user_id, 0)
        n_log = notify_logs.get(user.user_id, {})
        players.append(PlayerDetailOut(
            signup_id=signup.id,
            user_id=user.user_id,
            full_name=user.full_name,
            status=signup.status.value,
            is_paid=signup.is_paid,
            position=signup.position.value if signup.position else (user.player_position.value if user.player_position else None),
            team=signup.team.value if signup.team else None,
            goals=u_stats.goals if u_stats else 0,
            mvp_votes=v_count,
            is_mvp=u_stats.is_mvp if u_stats else False,
            notify_status=n_log.get("status"),
            notified_at=n_log.get("time")
        ))
    return players

@router.get("/games/{game_id}", response_model=GameDetailOut)
async def get_game_details(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    votes_map = await _get_game_votes_map(session, game_id)

    from app.db.models import GameStats
    stmt = (
        select(Signup, User, GameStats)
        .join(User, User.user_id == Signup.user_id)
        .outerjoin(GameStats, (GameStats.game_id == Signup.game_id) & (GameStats.user_id == Signup.user_id))
        .where(Signup.game_id == game_id)
        .order_by(Signup.created_at)
    )
    res = await session.execute(stmt)
    
    cleaned_loc = clean_location(game.location)
    if cleaned_loc != game.location:
        game.location = cleaned_loc
        await session.commit()

    res_rows = res.all()
    notify_logs = {}
    try:
        redis_client = cache_service._get_client()
        keys = [f"notify_log:{game_id}:{row[1].user_id}" for row in res_rows]
        if keys:
            vals = await redis_client.mget(keys)
            for k, val in zip(keys, vals):
                if val:
                    uid = int(k.split(":")[-1])
                    notify_logs[uid] = json.loads(val) if isinstance(val, str) else val
    except Exception as e:
        logger.warning(f"Failed to fetch notify logs from Redis for game {game_id}: {e}")

    players = _format_game_players(res_rows, votes_map, notify_logs)
    from app.bot.utils import get_group_game_number
    g_num = await get_group_game_number(session, game)
        
    return GameDetailOut(
        id=game.id,
        game_number=g_num,
        location=game.location,
        date_time=game.date_time,
        status=game.status.value,
        price=game.price,
        team_count=game.team_count,
        score_a=game.score_a,
        score_b=game.score_b,
        score_c=game.score_c,
        players=players
    )

@router.post("/signups/{signup_id}/toggle_pay")
async def toggle_payment(
    signup_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
        
    game = await session.get(Game, signup.game_id)
    await check_admin_rights(game.chat_id, user_id)
    
    signup.is_paid = not signup.is_paid
    await session.commit()
    return {"status": "ok", "is_paid": signup.is_paid}

class GuestCreate(BaseModel):
    name: str
    position: str

@router.post("/games/{game_id}/guests")
async def add_guest(
    game_id: int,
    data: GuestCreate,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    import time
    from app.db.models import Position
    guest_id = -int(time.time() * 1000)
    
    pos_str = data.position.upper().strip()
    if pos_str not in Position.__members__:
        pos_str = "CM"
        
    new_guest = User(
        user_id=guest_id, 
        full_name=f"{data.name} (Guest)", 
        username=None, 
        player_position=Position[pos_str], 
        rating=100
    )
    session.add(new_guest)
    
    new_signup = Signup(
        game_id=game_id, 
        user_id=guest_id, 
        status=SignupStatus.ACTIVE
    )
    session.add(new_signup)
    await session.commit()
    
    await cache_service.evict(f"game_details:{game_id}")
    
    from app.core.events import event_bus, GameStateChangedEvent
    background_tasks.add_task(event_bus.publish, GameStateChangedEvent(game_id))
    
    return {"status": "added", "user_id": guest_id}

@router.delete("/signups/{signup_id}")
async def kick_player(
    signup_id: int,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
        
    game = await session.get(Game, signup.game_id)
    await check_admin_rights(game.chat_id, user_id)
    
    from app.core.services.roster import RosterService, PlayerLeftEvent
    from app.core.uow import UnitOfWork
    from app.core.events import event_bus
    
    async with UnitOfWork() as uow:
        service = RosterService(uow)
        success, msg, promoted = await service.leave_player(signup.game_id, signup.user_id, is_admin=True)
        if success:
            await uow.commit()
        else:
            raise HTTPException(status_code=400, detail=msg)
            
    background_tasks.add_task(event_bus.publish, PlayerLeftEvent(signup.game_id, signup.user_id, msg, promoted))

    return {"status": "deleted"}

class StatusUpdate(BaseModel):
    status: str

@router.patch("/signups/{signup_id}/status")
async def update_player_status(
    signup_id: int,
    data: StatusUpdate,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
        
    game = await session.get(Game, signup.game_id)
    await check_admin_rights(game.chat_id, user_id)
    
    status_map = {
        "active": SignupStatus.ACTIVE,
        "reserve": SignupStatus.RESERVE,
        "cancelled": SignupStatus.CANCELLED
    }
    
    if data.status.lower() not in status_map:
        raise HTTPException(status_code=400, detail="Invalid status")
        
    prev_status = signup.status
    new_status = status_map[data.status.lower()]
    signup.status = new_status
    await session.commit()

    # If promoted from reserve to active, notify player in DM
    if prev_status == SignupStatus.RESERVE and new_status == SignupStatus.ACTIVE and signup.user_id >= 0:
        target_uid = signup.user_id
        target_gid = signup.game_id
        async def _notify_promoted():
            try:
                from app.db.database import async_session_maker
                from app.bot.instance import bot
                from app.bot.utils import get_group_game_number
                async with async_session_maker() as s_bg:
                    g = await s_bg.get(Game, target_gid)
                    u = await s_bg.get(User, target_uid)
                    if not g or not u:
                        return
                    p_lang = getattr(u, 'language', 'en')
                    p_lang = p_lang.value if hasattr(p_lang, 'value') else str(p_lang)
                    from app.core.timezone import format_prague_dt
                    game_num = await get_group_game_number(s_bg, g)
                    date_str = format_prague_dt(g.date_time)
                    from app.bot.i18n import t
                    text = t(
                        "promoted_by_admin",
                        locale=p_lang,
                        game_num=game_num,
                        location=html.escape(g.location),
                        date=date_str
                    )
                    await bot.send_message(target_uid, text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to notify manually promoted player {target_uid}: {e}")
        background_tasks.add_task(_notify_promoted)

    from app.core.events import event_bus, GameStateChangedEvent
    background_tasks.add_task(event_bus.publish, GameStateChangedEvent(signup.game_id))

    return {"status": "ok", "new_status": signup.status.value}

class VoteDetailOut(BaseModel):
    voter_name: str
    voter_team: Optional[str]
    target_name: str
    vote_team: str

@router.get("/games/{game_id}/votes/summary")
async def get_game_votes_summary(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    from app.db.models import Vote, User
    result = await session.execute(
        select(User.full_name, func.count(Vote.id))
        .join(Vote, User.user_id == Vote.target_id)
        .where(Vote.game_id == game_id)
        .group_by(User.full_name)
        .order_by(func.count(Vote.id).desc())
    )
    votes = result.all()
    return [{"name": name, "count": count} for name, count in votes]

@router.get("/games/{game_id}/votes", response_model=List[VoteDetailOut])
async def get_game_votes(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id)
    
    # Needs to fetch names and voter team. Let's do a join.
    from app.db.models import Vote, User, Signup
    from sqlalchemy.orm import aliased
    Voter = aliased(User)
    Target = aliased(User)
    VoterSignup = aliased(Signup)
    
    stmt = (
        select(
            Vote, 
            Voter.full_name.label("voter_name"), 
            Target.full_name.label("target_name"),
            VoterSignup.team.label("voter_team")
        )
        .join(Voter, Voter.user_id == Vote.voter_id)
        .join(Target, Target.user_id == Vote.target_id)
        .outerjoin(VoterSignup, (VoterSignup.user_id == Vote.voter_id) & (VoterSignup.game_id == game_id))
        .where(Vote.game_id == game_id)
    )
    res = await session.execute(stmt)
    
    out = []
    for vote, voter_name, target_name, voter_team in res.all():
        out.append(VoteDetailOut(
            voter_name=voter_name,
            voter_team=voter_team.value if voter_team else None,
            target_name=target_name,
            vote_team=vote.vote_team.value
        ))
        
    return out

@router.post("/games/{game_id}/notify")
async def notify_player_payment(
    game_id: int,
    data: dict = Body(...),
    admin_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    target_user_id = data.get("user_id")
    if target_user_id is None:
        raise HTTPException(status_code=400, detail="Missing user_id")
        
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, admin_id)
    
    now_str = datetime.datetime.now().strftime("%H:%M")

    # If guest
    if target_user_id < 0:
        log_entry = {"status": "guest", "time": now_str, "detail": "Гость (нет Telegram)"}
        await cache_service.set(f"notify_log:{game_id}:{target_user_id}", log_entry, ttl=86400 * 30)
        return {"status": "ok", "delivery": "guest", "time": now_str, "detail": "Игрок является гостем."}

    user = await session.get(User, target_user_id)
    from app.bot.instance import bot
    from app.bot.utils import get_group_game_number, resolve_chat_language
    from app.core.timezone import format_prague_dt
    from app.bot.i18n import t

    chat_lang = await resolve_chat_language(session, game.chat_id)
    notif_lang = chat_lang or "ru"

    game_num = await get_group_game_number(session, game)
    date_str = format_prague_dt(game.date_time)
    pay_info = game.payment_info or ""

    fallback_pay = t("pm_payment_reminder_no_details", locale=notif_lang)
    pay_display = html.escape(pay_info) if pay_info else fallback_pay
    msg = t(
        "pm_payment_reminder",
        locale=notif_lang,
        game_num=game_num,
        location=html.escape(game.location),
        date=date_str,
        price=game.price,
        payment=pay_display
    )

    try:
        await bot.send_message(target_user_id, msg, parse_mode="HTML")
        log_entry = {"status": "delivered", "time": now_str, "detail": "Доставлено в ЛС"}
        await cache_service.set(f"notify_log:{game_id}:{target_user_id}", log_entry, ttl=86400 * 30)
        return {"status": "ok", "delivery": "delivered", "time": now_str}
    except Exception as e:
        err_str = str(e)
        logger.warning(f"Failed to send payment reminder to {target_user_id}: {err_str}")
        is_blocked = any(x in err_str.lower() for x in ["blocked", "forbidden", "can't initiate", "chat not found"])
        deliv_status = "blocked" if is_blocked else "error"
        log_entry = {"status": deliv_status, "time": now_str, "detail": err_str[:60]}
        await cache_service.set(f"notify_log:{game_id}:{target_user_id}", log_entry, ttl=86400 * 30)
        return {"status": "ok", "delivery": deliv_status, "time": now_str, "detail": err_str}

@router.post("/games/{game_id}/notify_all_pm")
async def notify_all_unpaid_pm(
    game_id: int,
    admin_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    """
    Sends individual payment reminder DM to every active unpaid player.
    Updates the notify_log status cache for each player so feedback is recorded.
    """
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, admin_id)
    
    # Fetch unpaid active players
    stmt = (
        select(Signup, User)
        .join(User, User.user_id == Signup.user_id)
        .where(
            Signup.game_id == game_id,
            Signup.status == SignupStatus.ACTIVE,
            Signup.is_paid == False
        )
        .order_by(Signup.created_at)
    )
    res = await session.execute(stmt)
    unpaid_rows = res.all()
    
    if not unpaid_rows:
        return {
            "status": "ok",
            "total": 0,
            "delivered": 0,
            "blocked": 0,
            "guests": 0,
            "error": 0,
            "results": {}
        }
        
    from app.bot.instance import bot
    from app.bot.utils import get_group_game_number, resolve_chat_language
    from app.bot.i18n import t
    from app.core.timezone import format_prague_dt
    
    chat_lang = await resolve_chat_language(session, game.chat_id)
    notif_lang = chat_lang or "ru"

    game_num = await get_group_game_number(session, game)
    date_str = format_prague_dt(game.date_time)
    pay_info = game.payment_info or ""
    now_str = datetime.datetime.now().strftime("%H:%M")
    
    results = {}
    counts = {"delivered": 0, "blocked": 0, "guests": 0, "error": 0}
    
    for signup, user in unpaid_rows:
        target_uid = user.user_id
        if target_uid < 0:
            log_entry = {"status": "guest", "time": now_str, "detail": "Гость (нет Telegram)"}
            await cache_service.set(f"notify_log:{game_id}:{target_uid}", log_entry, ttl=86400 * 30)
            results[str(target_uid)] = log_entry
            counts["guests"] += 1
            continue
            
        fallback_pay = t("pm_payment_reminder_no_details", locale=notif_lang)
        pay_display = html.escape(pay_info) if pay_info else fallback_pay
        msg = t(
            "pm_payment_reminder",
            locale=notif_lang,
            game_num=game_num,
            location=html.escape(game.location),
            date=date_str,
            price=game.price,
            payment=pay_display
        )
        
        try:
            await bot.send_message(target_uid, msg, parse_mode="HTML")
            log_entry = {"status": "delivered", "time": now_str, "detail": "Доставлено в ЛС"}
            await cache_service.set(f"notify_log:{game_id}:{target_uid}", log_entry, ttl=86400 * 30)
            results[str(target_uid)] = log_entry
            counts["delivered"] += 1
        except Exception as e:
            err_str = str(e)
            logger.warning(f"Batch PM reminder to {target_uid} failed: {err_str}")
            is_blocked = any(x in err_str.lower() for x in ["blocked", "forbidden", "can't initiate", "chat not found"])
            deliv_status = "blocked" if is_blocked else "error"
            log_entry = {"status": deliv_status, "time": now_str, "detail": err_str[:60]}
            await cache_service.set(f"notify_log:{game_id}:{target_uid}", log_entry, ttl=86400 * 30)
            results[str(target_uid)] = log_entry
            counts[deliv_status] += 1
            
    return {
        "status": "ok",
        "total": len(unpaid_rows),
        "delivered": counts["delivered"],
        "blocked": counts["blocked"],
        "guests": counts["guests"],
        "error": counts["error"],
        "results": results
    }

@router.post("/games/{game_id}/notify_group")
async def notify_group_unpaid(
    game_id: int,
    admin_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, admin_id)
    
    # Fetch unpaid active players
    stmt = (
        select(Signup, User)
        .join(User, User.user_id == Signup.user_id)
        .where(
            Signup.game_id == game_id,
            Signup.status == SignupStatus.ACTIVE,
            Signup.is_paid == False
        )
        .order_by(Signup.created_at)
    )
    res = await session.execute(stmt)
    unpaid_rows = res.all()
    
    if not unpaid_rows:
        return {"status": "ok", "unpaid_count": 0, "message": "all_paid"}

    # Determine chat language
    from app.bot.utils import resolve_chat_language
    chat_lang = await resolve_chat_language(session, game.chat_id)

    from app.bot.utils import get_group_game_number
    from app.bot.instance import bot
    from app.core.timezone import format_prague_dt
    game_num = await get_group_game_number(session, game)
    date_str = format_prague_dt(game.date_time)
    pay_info = game.payment_info or ""

    from app.bot.i18n import t
    guest_label = t("debtor_guest_label", locale=chat_lang)
    debtors_list = []
    for idx, (s, u) in enumerate(unpaid_rows, start=1):
        if u.user_id < 0:
            name_display = f"{html.escape(u.full_name)} ({guest_label})"
        elif u.username:
            name_display = f"@{u.username}"
        else:
            name_display = f'<a href="tg://user?id={u.user_id}">{html.escape(u.full_name)}</a>'
        debtors_list.append(f"{idx}. {name_display}")
    debtors_text = "\n".join(debtors_list)

    fallback_pay = t("group_payment_reminder_no_details", locale=chat_lang)
    pay_display = html.escape(pay_info) if pay_info else fallback_pay
    text = t(
        "group_payment_reminder",
        locale=chat_lang,
        game_num=game_num,
        location=html.escape(game.location),
        date=date_str,
        price=game.price,
        payment=pay_display,
        count=len(unpaid_rows),
        debtors=debtors_text
    )

    try:
        await bot.send_message(chat_id=game.chat_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send group payment reminder for game {game_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to post to group: {str(e)}")

    now_str = datetime.datetime.now().strftime("%H:%M")
    await cache_service.set(
        f"notify_group_log:{game_id}",
        {"time": now_str, "unpaid_count": len(unpaid_rows)},
        ttl=86400 * 30
    )
    return {"status": "ok", "unpaid_count": len(unpaid_rows), "time": now_str}

@router.delete("/games/{game_id}")
async def delete_game(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id, session=session)
    
    # 1. Cancel scheduler tasks
    try:
        from app.infrastructure.scheduler.service import SchedulerService
        scheduler = SchedulerService()
        scheduler.cancel_game_tasks(game_id)
    except Exception as e:
        logger.warning(f"Failed to cancel scheduler tasks for game {game_id}: {e}")
        
    # 2. Try to delete public messages
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

    # 3. Evict cache
    await cache_service.evict(f"game_details:{game_id}")
        
    # 4. Delete the game itself
    await session.delete(game)
    await session.commit()
    
    return {"status": "ok", "message": "Game deleted successfully"}

@router.post("/games/{game_id}/trigger_voting")
async def trigger_voting_dashboard(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one_or_none()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, user_id, session=session)
    
    try:
        from app.scheduler.tasks import send_voting_message
        await send_voting_message(game_id)
        return {"status": "triggered", "game_id": game_id}
    except Exception as e:
        logger.error(f"Trigger voting dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
