from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from pydantic import BaseModel
from typing import List, Optional
import datetime
import logging
import re

from app.db.database import get_session
from app.db.models import Chat, ChatAdmin, User, Game, GameStatus, Signup, SignupStatus
from app.api.auth import get_user_from_header, check_admin_rights
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def clean_location(loc: str) -> str:
    if not loc: return loc
    return re.sub(r'\(?https?://[^\s)]+\)?', '', loc).strip()

class GroupOut(BaseModel):
    chat_id: int
    title: str
    is_active: bool
    language: str
    payment_info: Optional[str]
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
    language: Optional[str] = None
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
    for game, count, paid_count in rows:
        cleaned_loc = clean_location(game.location)
        if cleaned_loc != game.location:
            game.location = cleaned_loc
            has_changes = True
            
        out.append(
            GameSummaryOut(
                id=game.id,
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

class GameDetailOut(BaseModel):
    id: int
    location: str
    date_time: datetime.datetime
    status: str
    price: int
    team_count: int
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    score_c: Optional[int] = None
    players: List[PlayerDetailOut]

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
    
    stmt = (
        select(Signup, User)
        .join(User, User.user_id == Signup.user_id)
        .where(Signup.game_id == game_id)
        .order_by(Signup.created_at)
    )
    res = await session.execute(stmt)
    
    # Also fetch GameStats
    from app.db.models import GameStats, Vote
    stats_res = await session.execute(select(GameStats).where(GameStats.game_id == game_id))
    stats_map = {s.user_id: s for s in stats_res.scalars().all()}
    
    # Also fetch Vote counts
    from sqlalchemy import func
    votes_res = await session.execute(
        select(Vote.target_id, func.count(Vote.id))
        .where(Vote.game_id == game_id)
        .group_by(Vote.target_id)
    )
    votes_map = {v[0]: v[1] for v in votes_res.all()}
    
    cleaned_loc = clean_location(game.location)
    if cleaned_loc != game.location:
        game.location = cleaned_loc
        await session.commit()

    players = []
    for signup, user in res.all():
        u_stats = stats_map.get(user.user_id)
        v_count = votes_map.get(user.user_id, 0)
        
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
            is_mvp=u_stats.is_mvp if u_stats else False
        ))
        
    return GameDetailOut(
        id=game.id,
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
        status=SignupStatus.RESERVE
    )
    session.add(new_signup)
    await session.commit()
    
    return {"status": "added", "user_id": guest_id}

@router.delete("/signups/{signup_id}")
async def kick_player(
    signup_id: int,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session)
):
    signup = await session.get(Signup, signup_id)
    if not signup:
        raise HTTPException(status_code=404, detail="Signup not found")
        
    game = await session.get(Game, signup.game_id)
    await check_admin_rights(game.chat_id, user_id)
    
    from app.core.services.roster import RosterService
    from app.core.uow import UnitOfWork
    
    async with UnitOfWork() as uow:
        service = RosterService(uow)
        success, msg, _ = await service.leave_player(signup.game_id, signup.user_id, is_admin=True)
        if success:
            await uow.commit()
        else:
            raise HTTPException(status_code=400, detail=msg)
            
    return {"status": "deleted"}

class StatusUpdate(BaseModel):
    status: str

@router.patch("/signups/{signup_id}/status")
async def update_player_status(
    signup_id: int,
    data: StatusUpdate,
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
        
    signup.status = status_map[data.status.lower()]
    await session.commit()
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
    if not target_user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")
        
    game = await session.get(Game, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    await check_admin_rights(game.chat_id, admin_id)
    
    # Send message using bot
    # We must import the bot instance carefully to avoid circular imports
    # If bot is not globally accessible, we can use dependency injection or absolute import
    try:
        from app.bot.main import bot
        
        date_str = game.date_time.strftime("%d.%m.%Y %H:%M")
        msg = (
            f"🔔 <b>Напоминание об оплате</b>\n\n"
            f"Пожалуйста, не забудьте оплатить взнос за игру:\n"
            f"📍 <b>{game.location}</b> ({date_str})\n"
            f"💰 Сумма: <b>{game.price} CZK</b>\n"
            f"💳 Реквизиты: <code>{game.payment_info}</code>"
        )
        await bot.send_message(target_user_id, msg, parse_mode="HTML")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
