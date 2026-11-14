import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.routers.leaderboards import PlayerActivityOut
from app.core.services.member_tracking import track_chat_member
from app.db.models import Chat, ChatMember, User


def test_player_activity_sort_priority_invariants():
    """
    Invariants verification:
    1. Registered members currently in chat come first (Core -> Regular -> Dormant).
    2. Registered members who left the group come penultimate.
    3. Unregistered participants come last.
    """
    p_core = PlayerActivityOut(
        user_id=1, full_name="Alpha Core", is_core=True, is_dormant=False,
        is_registered=True, is_in_chat=True, games_last_4_weeks=3, rating=120
    )
    p_regular = PlayerActivityOut(
        user_id=2, full_name="Beta Regular", is_core=False, is_dormant=False,
        is_registered=True, is_in_chat=True, games_last_4_weeks=1, rating=110
    )
    p_dormant = PlayerActivityOut(
        user_id=3, full_name="Gamma Dormant", is_core=False, is_dormant=True,
        is_registered=True, is_in_chat=True, games_last_4_weeks=0, rating=105
    )
    p_left_group = PlayerActivityOut(
        user_id=4, full_name="Delta Left", is_core=False, is_dormant=True,
        is_registered=True, is_in_chat=False, chat_status="left", total_games=5, rating=130
    )
    p_unregistered = PlayerActivityOut(
        user_id=5, full_name="Epsilon Unregistered", is_core=False, is_dormant=False,
        is_registered=False, is_in_chat=True, chat_status="member", total_games=0, rating=0
    )

    players = [p_unregistered, p_left_group, p_dormant, p_regular, p_core]

    def _sort_key(p: PlayerActivityOut):
        if p.is_registered and p.is_in_chat:
            sub = 0 if p.is_core else (2 if p.is_dormant else 1)
            return (0, sub, -p.games_last_4_weeks, -p.rating)
        if p.is_registered and not p.is_in_chat:
            return (1, 0, -p.total_games, -p.rating)
        return (2, 0, 0, p.full_name.lower())

    players.sort(key=_sort_key)

    # Invariants assert:
    # 0: Core
    assert players[0].user_id == 1
    # 1: Regular
    assert players[1].user_id == 2
    # 2: Dormant (in group)
    assert players[2].user_id == 3
    # 3: Left group (penultimate)
    assert players[3].user_id == 4
    # 4: Unregistered (last)
    assert players[4].user_id == 5


@pytest.mark.asyncio
async def test_track_chat_member_service():
    session = AsyncMock()
    session.get.return_value = Chat(chat_id=-100, title="Test Club")
    session.scalar.return_value = None  # Not registered

    await track_chat_member(
        session=session,
        chat_id=-100,
        user_id=999,
        full_name="New Member",
        username="newbie",
        status="member",
    )

    session.execute.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_group_player_note_saves_and_clears(monkeypatch):
    from app.api.routers import leaderboards

    dash_mock = MagicMock()
    dash_mock.check_admin_rights = AsyncMock()
    monkeypatch.setattr(leaderboards, "_dash", lambda: dash_mock)

    member = ChatMember(
        chat_id=-100,
        user_id=42,
        username="late_guy",
        full_name="Late Guy",
        status="kicked",
        is_registered=True,
        admin_note=None,
    )
    session = AsyncMock()
    session.scalar.return_value = member

    res = await leaderboards.update_group_player_note(
        chat_id=-100,
        target_user_id=42,
        payload=leaderboards.PlayerNoteIn(note="  Опоздал на игру; не заплатил  "),
        user_id=1,
        session=session,
    )
    assert res == {
        "status": "ok",
        "user_id": 42,
        "admin_note": "Опоздал на игру; не заплатил",
    }
    assert member.admin_note == "Опоздал на игру; не заплатил"
    session.commit.assert_awaited()

    res_clear = await leaderboards.update_group_player_note(
        chat_id=-100,
        target_user_id=42,
        payload=leaderboards.PlayerNoteIn(note="   "),
        user_id=1,
        session=session,
    )
    assert res_clear["admin_note"] is None
    assert member.admin_note is None


@pytest.mark.asyncio
async def test_get_group_player_detail_unregistered_member(monkeypatch):
    from app.api.routers import leaderboards

    dash_mock = MagicMock()
    dash_mock.check_admin_rights = AsyncMock()
    monkeypatch.setattr(leaderboards, "_dash", lambda: dash_mock)

    member = ChatMember(
        chat_id=-100,
        user_id=777,
        username="ghost777",
        full_name="Ghost User",
        status="left",
        is_registered=False,
        admin_note="Не отвечал",
    )
    session = AsyncMock()
    session.get.return_value = None
    session.scalar.return_value = member

    detail = await leaderboards.get_group_player_detail(
        chat_id=-100,
        target_user_id=777,
        user_id=1,
        session=session,
    )
    assert detail.user_id == 777
    assert detail.is_registered is False
    assert detail.is_in_chat is False
    assert detail.chat_status == "left"
    assert detail.admin_note == "Не отвечал"
