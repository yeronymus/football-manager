import datetime
import html
import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.core.events import GameStateChangedEvent, event_bus
from app.core.i18n import t
from app.core.repositories.signup_repository import SignupRepository
from app.core.repositories.vote_repository import VoteRepository
from app.core.services.audit import record_audit_log
from app.core.services.game_numbering import clean_location, get_group_game_number
from app.core.services.roster import PlayerLeftEvent, RosterService
from app.core.timezone import format_prague_dt
from app.core.uow import UnitOfWork
from app.db.database import async_session_maker, get_session
from app.db.models import Game, Position, Signup, SignupStatus, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard-rosters"])


def _dash():
    import app.api.routers.dashboard as dash_mod

    return dash_mod


class PlayerDetailOut(BaseModel):
    signup_id: int
    user_id: int
    full_name: str
    status: str
    is_paid: bool
    is_late: bool = False
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


class GuestCreate(BaseModel):
    name: str
    position: str


class StatusUpdate(BaseModel):
    status: str


def _format_game_players(rows, votes_map, notify_logs=None) -> List[PlayerDetailOut]:
    """Helper to format the players list from joined query rows."""
    if notify_logs is None:
        notify_logs = {}
    players = []
    for signup, user, u_stats in rows:
        v_count = votes_map.get(user.user_id, 0)
        n_log = notify_logs.get(user.user_id, {})
        players.append(
            PlayerDetailOut(
                signup_id=signup.id,
                user_id=user.user_id,
                full_name=user.full_name,
                status=signup.status.value,
                is_paid=signup.is_paid,
                is_late=bool(getattr(signup, "is_late", False)),
                position=signup.position.value
                if signup.position
                else (user.player_position.value if user.player_position else None),
                team=signup.team.value if signup.team else None,
                goals=u_stats.goals if u_stats else 0,
                mvp_votes=v_count,
                is_mvp=u_stats.is_mvp if u_stats else False,
                notify_status=n_log.get("status"),
                notified_at=n_log.get("time"),
            )
        )
    return players


@router.get("/games/{game_id}", response_model=GameDetailOut)
async def get_game_details(
    game_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, user_id)

    vote_repo = VoteRepository(session)
    votes_map = await vote_repo.get_vote_counts_by_target(game_id)

    signup_repo = SignupRepository(session)
    res_rows = await signup_repo.list_by_game_with_users_and_stats(game_id)

    notify_logs = {}
    try:
        redis_client = _dash().cache_service._get_client()
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
    g_num = await get_group_game_number(session, game)

    return GameDetailOut(
        id=game.id,
        game_number=g_num,
        location=clean_location(game.location),
        date_time=game.date_time,
        status=game.status.value,
        price=game.price,
        team_count=game.team_count,
        score_a=game.score_a,
        score_b=game.score_b,
        score_c=game.score_c,
        players=players,
    )


@router.post("/signups/{signup_id}/toggle_late")
async def toggle_signup_late(
    signup_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """Toggles the late arrival status of a player in a game."""
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")

    game = await session.get(Game, signup.game_id)
    await _dash().check_admin_rights(game.chat_id, user_id)

    signup.is_late = not signup.is_late
    record_audit_log(
        session,
        action="ROSTER_LATE_TOGGLED",
        actor_user_id=user_id,
        chat_id=getattr(game, "chat_id", None),
        target_type="signup",
        target_id=signup.id,
        payload={"is_late": signup.is_late, "user_id": getattr(signup, "user_id", None)},
    )
    await session.commit()

    await _dash().cache_service.evict(f"game_details:{game.id}")

    return {"status": "ok", "signup_id": signup.id, "is_late": signup.is_late}


@router.post("/games/{game_id}/guests")
async def add_guest(
    game_id: int,
    data: GuestCreate,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    await _dash().check_admin_rights(game.chat_id, user_id)

    guest_id = -int(time.time() * 1000)

    pos_str = data.position.upper().strip()
    if pos_str not in Position.__members__:
        pos_str = "CM"

    new_guest = User(
        user_id=guest_id,
        full_name=f"{data.name} (Guest)",
        username=None,
        player_position=Position[pos_str],
        rating=100,
        is_guest=True,
    )
    session.add(new_guest)

    new_signup = Signup(
        game_id=game_id,
        user_id=guest_id,
        status=SignupStatus.ACTIVE,
    )
    session.add(new_signup)
    record_audit_log(
        session,
        action="ROSTER_GUEST_ADDED",
        actor_user_id=user_id,
        chat_id=getattr(game, "chat_id", None),
        target_type="game",
        target_id=game_id,
        payload={"guest_id": guest_id, "name": data.name, "position": pos_str},
    )
    await session.commit()

    await _dash().cache_service.evict(f"game_details:{game_id}")
    background_tasks.add_task(event_bus.publish, GameStateChangedEvent(game_id))

    return {"status": "added", "user_id": guest_id}


@router.delete("/signups/{signup_id}")
async def kick_player(
    signup_id: int,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")

    game = await session.get(Game, signup.game_id)
    await _dash().check_admin_rights(game.chat_id, user_id)

    async with UnitOfWork() as uow:
        service = RosterService(uow)
        success, msg, promoted = await service.leave_player(
            signup.game_id, signup.user_id, is_admin=True
        )
        if success:
            record_audit_log(
                session,
                action="ROSTER_PLAYER_KICKED",
                actor_user_id=user_id,
                chat_id=getattr(game, "chat_id", None),
                target_type="signup",
                target_id=signup_id,
                payload={"game_id": signup.game_id, "kicked_user_id": signup.user_id},
            )
            await uow.commit()
        else:
            raise HTTPException(status_code=400, detail=msg)

    background_tasks.add_task(
        event_bus.publish,
        PlayerLeftEvent(signup.game_id, signup.user_id, msg, promoted),
    )

    return {"status": "deleted"}


@router.patch("/signups/{signup_id}/status")
async def update_player_status(
    signup_id: int,
    data: StatusUpdate,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")

    game = await session.get(Game, signup.game_id)
    await _dash().check_admin_rights(game.chat_id, user_id)

    status_map = {
        "active": SignupStatus.ACTIVE,
        "reserve": SignupStatus.RESERVE,
        "cancelled": SignupStatus.CANCELLED,
    }

    if data.status.lower() not in status_map:
        raise HTTPException(status_code=400, detail="Invalid status")

    prev_status = signup.status
    new_status = status_map[data.status.lower()]
    signup.status = new_status
    record_audit_log(
        session,
        action="ROSTER_STATUS_UPDATED",
        actor_user_id=user_id,
        chat_id=getattr(game, "chat_id", None),
        target_type="signup",
        target_id=signup_id,
        payload={"from": getattr(prev_status, "value", str(prev_status)), "to": new_status.value},
    )
    await session.commit()

    if (
        prev_status == SignupStatus.RESERVE
        and new_status == SignupStatus.ACTIVE
        and signup.user_id >= 0
    ):
        target_uid = signup.user_id
        target_gid = signup.game_id

        async def _notify_promoted():
            try:
                from app.bot.instance import bot

                async with async_session_maker() as s_bg:
                    g = await s_bg.get(Game, target_gid)
                    u = await s_bg.get(User, target_uid)
                    if not g or not u:
                        return
                    p_lang = getattr(u, "language", "en")
                    p_lang = p_lang.value if hasattr(p_lang, "value") else str(p_lang)
                    game_num = await get_group_game_number(s_bg, g)
                    date_str = format_prague_dt(g.date_time)
                    text = t(
                        "promoted_by_admin",
                        locale=p_lang,
                        game_num=game_num,
                        location=html.escape(g.location),
                        date=date_str,
                    )
                    await bot.send_message(target_uid, text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to notify manually promoted player {target_uid}: {e}")

        background_tasks.add_task(_notify_promoted)

    background_tasks.add_task(event_bus.publish, GameStateChangedEvent(signup.game_id))

    return {"status": "ok", "new_status": signup.status.value}
