from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.db.database import get_session
from app.db.models import ChatMember, PlayerProfile, User

router = APIRouter(tags=["dashboard-community"])


def _dash():
    import app.api.routers.dashboard as dash_mod

    return dash_mod


class PlayerNoteIn(BaseModel):
    note: Optional[str] = None


class PlayerKickIn(BaseModel):
    reason: Optional[str] = None


class UnregisteredWarnIn(BaseModel):
    custom_message: Optional[str] = None


@router.put("/groups/{chat_id}/players/{target_user_id}/note")
async def update_group_player_note(
    chat_id: int,
    target_user_id: int,
    payload: PlayerNoteIn,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    await _dash().check_admin_rights(chat_id, user_id, session=session)

    raw_note = (payload.note or "").strip()
    clean_note = raw_note[:500] if raw_note else None

    member_entry = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == target_user_id,
        )
    )
    if member_entry is None:
        user = await session.get(User, target_user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Player not found")
        member_entry = ChatMember(
            chat_id=chat_id,
            user_id=target_user_id,
            username=user.username,
            full_name=user.full_name,
            status="member",
            is_registered=not bool(getattr(user, "is_guest", False)),
            admin_note=clean_note,
        )
        session.add(member_entry)
    else:
        member_entry.admin_note = clean_note

    await session.commit()
    return {"status": "ok", "user_id": target_user_id, "admin_note": clean_note}


@router.post("/groups/{chat_id}/players/{target_user_id}/kick")
async def kick_group_player(
    chat_id: int,
    target_user_id: int,
    payload: Optional[PlayerKickIn] = None,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Removes a participant from the Telegram group chat via Bot API,
    marks their ChatMember status as 'kicked', and records an optional admin note.
    """
    await _dash().check_admin_rights(chat_id, user_id, session=session)

    reason = ((payload.reason if payload else None) or "").strip()[:500] or None

    from app.bot.instance import bot

    try:
        await bot.ban_chat_member(chat_id=chat_id, user_id=target_user_id)
        await bot.unban_chat_member(
            chat_id=chat_id, user_id=target_user_id, only_if_banned=True
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Telegram kick failed (check bot admin rights): {e}",
        )

    member_entry = await session.scalar(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == target_user_id,
        )
    )
    if member_entry is None:
        user = await session.get(User, target_user_id)
        member_entry = ChatMember(
            chat_id=chat_id,
            user_id=target_user_id,
            username=user.username if user else None,
            full_name=user.full_name if user else f"User {target_user_id}",
            status="kicked",
            is_registered=bool(user and not getattr(user, "is_guest", False)),
            admin_note=reason,
        )
        session.add(member_entry)
    else:
        member_entry.status = "kicked"
        if reason:
            member_entry.admin_note = reason

    await session.commit()
    return {
        "status": "ok",
        "user_id": target_user_id,
        "chat_status": "kicked",
        "admin_note": member_entry.admin_note,
    }


@router.post("/groups/{chat_id}/unregistered/warn")
async def warn_unregistered_group_members(
    chat_id: int,
    payload: Optional[UnregisteredWarnIn] = None,
    user_id: int = Depends(get_user_from_header),
    session: AsyncSession = Depends(get_session),
):
    """
    Attempts to send a private DM (NOT in the group chat) to unregistered members
    who already have an open bot conversation, and returns lists of who received it
    vs who never started the bot.
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from app.bot.instance import bot

    await _dash().check_admin_rights(chat_id, user_id, session=session)

    prof_uids_res = await session.execute(
        select(PlayerProfile.user_id).where(PlayerProfile.chat_id == chat_id)
    )
    prof_uids = {r[0] for r in prof_uids_res.all()}

    members_res = await session.execute(
        select(ChatMember).where(ChatMember.chat_id == chat_id)
    )
    all_members = members_res.scalars().all()
    unreg = [
        m
        for m in all_members
        if not m.is_registered
        and m.user_id not in prof_uids
        and m.status not in ("left", "kicked")
    ]

    if not unreg:
        return {
            "status": "ok",
            "warned_count": 0,
            "dm_sent_count": 0,
            "blocked_count": 0,
            "dm_sent_users": [],
            "blocked_users": [],
            "bot_start_url": "",
        }

    try:
        me = await bot.get_me()
        bot_username = me.username or "football_manager_bot"
    except Exception:
        bot_username = "football_manager_bot"

    start_url = f"https://t.me/{bot_username}?start=reg"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚽ Зарегистрироваться в боте (/start)",
                    url=start_url,
                )
            ]
        ]
    )

    dm_text = (
        ((payload.custom_message if payload else None) or "").strip()
        or "Привет! Зарегистрируйся, пожалуйста, в нашем футбольном боте (нажми /start), "
        "иначе нам придётся удалить тебя из группы при чистке состава 🙏"
    )

    dm_sent_count = 0
    blocked_count = 0
    dm_sent_users = []
    blocked_users = []
    for m in unreg:
        entry = {
            "user_id": m.user_id,
            "full_name": m.full_name or m.username or f"User {m.user_id}",
            "username": m.username,
        }
        try:
            await bot.send_message(
                chat_id=m.user_id,
                text=dm_text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            dm_sent_count += 1
            dm_sent_users.append(entry)
        except Exception:
            blocked_count += 1
            blocked_users.append(entry)

    return {
        "status": "ok",
        "warned_count": len(unreg),
        "dm_sent_count": dm_sent_count,
        "blocked_count": blocked_count,
        "dm_sent_users": dm_sent_users,
        "blocked_users": blocked_users,
        "bot_start_url": start_url,
    }
