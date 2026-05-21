import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from sqlalchemy import select
from app.db.models import Game, Signup, SignupStatus, GameStatus, User
from app.scheduler.tasks import release_gk_slots

@pytest.mark.asyncio
async def test_release_gk_slots(session):
    # Setup: Create a user and a game
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
        status=GameStatus.OPEN
    )
    session.add(game)
    await session.commit()
    
    # Add 1 active and 1 reserve
    s1 = Signup(game_id=game.id, user_id=1, status=SignupStatus.ACTIVE)
    s2 = Signup(game_id=game.id, user_id=2, status=SignupStatus.RESERVE)
    session.add_all([s1, s2])
    await session.commit()
    
    # Mock bot and other dependencies
    # Use a context manager to yield the session as async_session_maker does
    class MockSessionMaker:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        def __call__(self):
            return self

    mock_dashboard_module = MagicMock()
    mock_dashboard_module.update_dashboard_message = AsyncMock()

    with patch("app.scheduler.tasks.bot", new_callable=AsyncMock) as mock_bot, \
         patch("app.scheduler.tasks.async_session_maker", return_value=MockSessionMaker(session)), \
         patch("app.bot.utils.format_game_message", new_callable=AsyncMock) as mock_format, \
         patch.dict("sys.modules", {"app.bot.admin_dashboard": mock_dashboard_module}):
        
        mock_format.return_value = "Updated Game Message"
        
        # Run the task
        await release_gk_slots(game.id)
        
        # Refresh and verify
        await session.refresh(s2)
        assert s2.status == SignupStatus.ACTIVE
        
        # Verify notification was sent
        assert mock_bot.send_message.called
        # s2.user_id is 2
        assert mock_bot.send_message.call_args[0][0] == 2
        assert "Бронь вратарей снята" in mock_bot.send_message.call_args[0][1]

@pytest.mark.asyncio
async def test_release_gk_slots_no_room(session):
    # Setup: Create users and a game, but no room
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
        status=GameStatus.OPEN
    )
    session.add(game)
    await session.commit()
    
    # Add 1 active (fills max) and 1 reserve
    s1 = Signup(game_id=game.id, user_id=1, status=SignupStatus.ACTIVE)
    s2 = Signup(game_id=game.id, user_id=2, status=SignupStatus.RESERVE)
    session.add_all([s1, s2])
    await session.commit()
    
    # Run the task with mocked session
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
    
    # Refresh and verify s2 is STILL RESERVE
    await session.refresh(s2)
    assert s2.status == SignupStatus.RESERVE
