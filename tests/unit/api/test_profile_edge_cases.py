import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.api.routers.users import get_my_profile, register_user, update_my_profile
from app.db.models import PlayerProfile, User, Chat, Position

@pytest.mark.asyncio
async def test_get_my_profile_without_profile():
    session = AsyncMock()
    
    # 1. Mock user retrieval
    mock_user = MagicMock(spec=User)
    mock_user.user_id = 456
    mock_user.full_name = "No Profile User"
    mock_user.player_position = Position.CM
    mock_user.alt_positions = []
    
    session.get.return_value = mock_user
    
    # 2. Mock profile retrieval returning None (no profile in this chat)
    session.scalar.side_effect = [
        None, # First scalar call: PlayerProfile
        5,    # Second scalar call: games_count
        2     # Third scalar call: total_goals
    ]
    
    # Mock last 10 rating changes to be empty
    mock_history_res = MagicMock()
    mock_history_res.all.return_value = []
    session.scalars.return_value = mock_history_res
    
    # Call the router function
    result = await get_my_profile(chat_id=123, user_id=456, session=session)
    
    assert result["user_id"] == 456
    assert result["name"] == "No Profile User"
    assert result["rating"] == 100  # Default rating when no profile exists
    assert result["games_played"] == 5
    assert result["mvp_count"] == 0  # Default MVP count
    assert result["total_goals"] == 2

@pytest.mark.asyncio
async def test_register_user_without_initial_chat_profile():
    session = AsyncMock()
    
    # Mock user not existing yet
    session.get.return_value = None
    
    data = {
        "name": "New Registered User",
        "position": "CM",
        "alt_positions": ["GK"]
    }
    
    # Call register without chat_id
    result = await register_user(data=data, user_id=789, session=session)
    
    assert result["status"] == "ok"
    assert result["user_id"] == 789
    
    # Verify session added the user
    session.add.assert_called_once()
    added_obj = session.add.call_args[0][0]
    assert isinstance(added_obj, User)
    assert added_obj.user_id == 789
    assert added_obj.full_name == "New Registered User"
    
    # Verify no Chat retrieval or PlayerProfile was added
    session.get.assert_called_once_with(User, 789) # Only User fetch occurred

@pytest.mark.asyncio
async def test_update_my_profile_invalid_position_enum():
    session = AsyncMock()
    
    # Mock user exists
    mock_user = MagicMock(spec=User)
    session.get.return_value = mock_user
    
    data = {
        "position": "INVALID_POSITION",
        "alt_positions": []
    }
    
    # Expect HTTPException due to ValueError inside Position(...) instantiation
    with pytest.raises(HTTPException) as exc_info:
        await update_my_profile(data=data, user_id=456, session=session)
        
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid position"

@pytest.mark.asyncio
async def test_update_my_profile_missing_position():
    session = AsyncMock()
    
    data = {
        "alt_positions": []
    }
    
    with pytest.raises(HTTPException) as exc_info:
        await update_my_profile(data=data, user_id=456, session=session)
        
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Position required"
