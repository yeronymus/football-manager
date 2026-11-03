from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import Game, GameStatus, Signup, SignupStatus, Team, User
from app.scheduler.tasks import release_gk_slots, send_voting_message


@pytest.mark.asyncio
async def test_release_gk_slots(session):
    user = User(user_id=1, full_name="User 1", player_position="GK")
    user2 = User(user_id=2, full_name="User 2", player_position="CM")
    session.add_all([user, user2])
    await session.commit()

    game = Game(
        chat_id=-1001,
        created_by=1,
        date_time=datetime.now() + timedelta(days=2),
        location="GK Test Arena",
        max_players=2,
        status=GameStatus.OPEN,
    )
    session.add(game)
    await session.commit()

    s1 = Signup(game_id=game.id, user_id=1, status=SignupStatus.ACTIVE)
    s2 = Signup(game_id=game.id, user_id=2, status=SignupStatus.RESERVE)
    session.add_all([s1, s2])
    await session.commit()

    class MockSessionMaker:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def __call__(self):
            return self

    with (
        patch("app.scheduler.tasks.bot", new_callable=AsyncMock) as mock_bot,
        patch("app.scheduler.tasks.async_session_maker", return_value=MockSessionMaker(session)),
        patch("app.bot.utils.format_game_message", new_callable=AsyncMock) as mock_format,
    ):
        mock_format.return_value = "Updated Game Message"

        await release_gk_slots(game.id)

        await session.refresh(s2)
        assert s2.status == SignupStatus.ACTIVE
        assert not mock_bot.send_message.called


@pytest.mark.asyncio
async def test_release_gk_slots_no_room(session):
    user = User(user_id=1, full_name="User 1", player_position="GK")
    user2 = User(user_id=2, full_name="User 2", player_position="CM")
    session.add_all([user, user2])
    await session.commit()

    game = Game(
        chat_id=-1002,
        created_by=1,
        date_time=datetime.now() + timedelta(days=2),
        location="GK Full Arena",
        max_players=1,
        status=GameStatus.OPEN,
    )
    session.add(game)
    await session.commit()

    s1 = Signup(game_id=game.id, user_id=1, status=SignupStatus.ACTIVE)
    s2 = Signup(game_id=game.id, user_id=2, status=SignupStatus.RESERVE)
    session.add_all([s1, s2])
    await session.commit()

    class MockSessionMaker:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def __call__(self):
            return self

    with patch("app.scheduler.tasks.async_session_maker", return_value=MockSessionMaker(session)):
        await release_gk_slots(game.id)

    await session.refresh(s2)
    assert s2.status == SignupStatus.RESERVE


@pytest.mark.asyncio
async def test_send_voting_message_success(session):
    u1 = User(user_id=10, full_name="Alpha Player", player_position="ST")
    u2 = User(user_id=20, full_name="Beta Player", player_position="CB")
    u3 = User(user_id=30, full_name="Gamma Player", player_position="GK")
    session.add_all([u1, u2, u3])
    await session.commit()

    game = Game(
        chat_id=-1001000000001,
        created_by=10,
        date_time=datetime.now() - timedelta(hours=2),
        location="Central Sports Arena",
        max_players=18,
        status=GameStatus.ACTIVE,
    )
    session.add(game)
    await session.commit()

    s1 = Signup(game_id=game.id, user_id=10, status=SignupStatus.ACTIVE, team=Team.A)
    s2 = Signup(game_id=game.id, user_id=20, status=SignupStatus.ACTIVE, team=Team.B)
    s3 = Signup(game_id=game.id, user_id=30, status=SignupStatus.ACTIVE, team=Team.C)
    session.add_all([s1, s2, s3])
    await session.commit()

    class MockSessionMaker:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def __call__(self):
            return self

    mock_msg = MagicMock()
    mock_msg.message_id = 9999

    with (
        patch("app.scheduler.tasks.bot", new_callable=AsyncMock) as mock_bot,
        patch("app.scheduler.tasks.async_session_maker", return_value=MockSessionMaker(session)),
    ):
        mock_bot.send_message.return_value = mock_msg

        await send_voting_message(game.id)

        assert mock_bot.send_message.called
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == game.chat_id
        assert "Voting for MVP is open!" in call_kwargs["text"]
        kb = call_kwargs["reply_markup"]
        all_btn_texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("TEAM C" in t for t in all_btn_texts)
        assert "Gamma Player" in all_btn_texts

        await session.refresh(game)
        assert game.voting_message_id == 9999


@pytest.mark.asyncio
async def test_send_voting_message_channel_fallback(session):
    from aiogram.exceptions import TelegramBadRequest

    u1 = User(user_id=101, full_name="Player One", player_position="ST")
    session.add(u1)
    await session.commit()

    game = Game(
        chat_id=-1002000000002,
        created_by=101,
        date_time=datetime.now() - timedelta(hours=2),
        location="Channel Arena",
        max_players=18,
        status=GameStatus.ACTIVE,
    )
    session.add(game)
    await session.commit()

    s1 = Signup(game_id=game.id, user_id=101, status=SignupStatus.ACTIVE, team=Team.A)
    session.add(s1)
    await session.commit()

    class MockSessionMaker:
        def __init__(self, session):
            self.session = session

        async def __aenter__(self):
            return self.session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def __call__(self):
            return self

    mock_msg = MagicMock()
    mock_msg.message_id = 8888

    with (
        patch("app.scheduler.tasks.bot", new_callable=AsyncMock) as mock_bot,
        patch("app.scheduler.tasks.async_session_maker", return_value=MockSessionMaker(session)),
    ):
        mock_bot.send_message.side_effect = [
            TelegramBadRequest(method="sendMessage", message="Bad Request: BUTTON_TYPE_INVALID"),
            mock_msg,
        ]

        await send_voting_message(game.id)

        assert mock_bot.send_message.call_count == 2
        fallback_call = mock_bot.send_message.call_args_list[1][1]
        kb = fallback_call["reply_markup"]
        assert len(kb.inline_keyboard) > 0
        assert kb.inline_keyboard[0][0].url is not None
        assert f"start=vote_{game.id}" in kb.inline_keyboard[0][0].url
