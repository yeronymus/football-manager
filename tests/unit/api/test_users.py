import pytest
from unittest.mock import AsyncMock, MagicMock
from app.api.routers.users import get_leaderboard, get_chats
from app.db.models import PlayerProfile, User, Chat, Language

@pytest.mark.asyncio
async def test_get_leaderboard_success():
    session = AsyncMock()
    
    # Mock data
    mock_profile = MagicMock(spec=PlayerProfile)
    mock_profile.rating = 1500
    mock_profile.games_played = 10
    mock_profile.user_id = 1
    
    mock_user = MagicMock(spec=User)
    mock_user.user_id = 1
    mock_user.full_name = "Test User"
    
    mock_goals = 5
    
    # profiles.all() returns list of tuples (PlayerProfile, goals, User)
    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_profile, mock_goals, mock_user)]
    session.execute.return_value = mock_result
    
    # Call the function
    # We pass session directly since we are testing the function
    result = await get_leaderboard(chat_id=123, user_id=1, session=session)
    
    assert len(result) == 1
    assert result[0]["name"] == "Test User"
    assert result[0]["rating"] == 1500
    assert result[0]["goals"] == 5
    assert result[0]["games"] == 10

@pytest.mark.asyncio
async def test_get_leaderboard_empty():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    session.execute.return_value = mock_result
    
    result = await get_leaderboard(chat_id=123, user_id=1, session=session)
    assert result == []

@pytest.mark.asyncio
async def test_get_chats_includes_group_defaults():
    session = AsyncMock()
    mock_chat = MagicMock(spec=Chat)
    mock_chat.chat_id = -100123456789
    mock_chat.title = "Test Group"
    mock_chat.is_active = True
    mock_chat.language = Language.ru
    mock_chat.payment_info = "123456/0800"
    mock_chat.default_location = "Field 1"
    mock_chat.default_price = 100
    mock_chat.default_team_count = 2
    mock_chat.default_max_players = 20
    mock_chat.default_main_players_count = 18
    mock_chat.default_duration = 1.5
    mock_chat.default_gk_hours = 0
    mock_chat.default_registration_hours = 96
    mock_chat.default_signup_limit = 50

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_chat]
    session.execute.return_value = mock_result

    chats = await get_chats(user_id=1, session=session)
    assert len(chats) == 1
    c = chats[0]
    assert c["id"] == -100123456789
    assert c["title"] == "Test Group"
    assert c["default_price"] == 100
    assert c["default_duration"] == 1.5
    assert c["default_location"] == "Field 1"
    assert c["payment_info"] == "123456/0800"
    assert c["default_max_players"] == 20
    assert c["default_main_players_count"] == 18
    assert c["default_team_count"] == 2
    assert c["default_gk_hours"] == 0
    assert c["default_registration_hours"] == 96
    assert c["default_signup_limit"] == 50
