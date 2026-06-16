import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.routers.users import get_leaderboard
from app.db.models import PlayerProfile, User

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
