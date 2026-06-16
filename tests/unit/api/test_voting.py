import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.routers.voting import get_vote_data, submit_vote
from app.db.models import Signup, User, Vote, Team, Position
from app.api.schemas import VoteRequest

@pytest.mark.asyncio
@patch("app.api.routers.voting.validate_init_data", return_value=True)
@patch("app.api.routers.voting.get_user_from_init_data", return_value=123)
async def test_get_vote_data_success(mock_get_user, mock_validate):
    session = AsyncMock()
    
    # Mock query returns
    mock_signup_check = MagicMock()
    mock_signup_check.scalar_one_or_none.return_value = MagicMock(spec=Signup)
    
    mock_players_query = MagicMock()
    mock_players_query.all.return_value = [
        (User(user_id=123, full_name="Me", player_position=Position.MID), Signup(team=Team.A)),
        (User(user_id=456, full_name="Teammate", player_position=Position.DEF), Signup(team=Team.A)),
        (User(user_id=789, full_name="Opponent", player_position=Position.FWD), Signup(team=Team.B))
    ]
    
    mock_votes_query = MagicMock()
    mock_votes_query.scalars.return_value.all.return_value = []
    
    session.execute.side_effect = [
        mock_signup_check, # Active player check
        mock_players_query, # List of all players
        mock_votes_query   # Existing votes check
    ]
    
    res = await get_vote_data(game_id=1, initData="mock_init_data", session=session)
    assert "team_a" in res
    assert "team_b" in res
    assert len(res["team_a"]) == 2
    assert len(res["team_b"]) == 1
    assert res["has_voted"] is False

@pytest.mark.asyncio
@patch("app.api.routers.voting.validate_init_data", return_value=True)
@patch("app.api.routers.voting.get_user_from_init_data", return_value=123)
async def test_submit_vote_success(mock_get_user, mock_validate):
    session = AsyncMock()
    
    # Mock query returns
    mock_signup_check = MagicMock()
    mock_signup_check.scalar_one_or_none.return_value = MagicMock(spec=Signup)
    
    mock_votes_check = MagicMock()
    mock_votes_check.scalars.return_value.all.return_value = []
    
    session.execute.side_effect = [
        mock_signup_check, # Active player check
        mock_votes_check   # Already voted check
    ]
    
    req = VoteRequest(initData="mock_init_data", game_id=1, mvp_team_a=456, mvp_team_b=789)
    res = await submit_vote(data=req, session=session)
    
    assert res == {"status": "ok"}
    assert session.add.call_count == 2
    session.commit.assert_called_once()

@pytest.mark.asyncio
@patch("app.api.routers.voting.validate_init_data", return_value=True)
@patch("app.api.routers.voting.get_user_from_init_data", return_value=123)
async def test_submit_vote_self_vote_error(mock_get_user, mock_validate):
    session = AsyncMock()
    
    # Mock query returns
    mock_signup_check = MagicMock()
    mock_signup_check.scalar_one_or_none.return_value = MagicMock(spec=Signup)
    
    mock_votes_check = MagicMock()
    mock_votes_check.scalars.return_value.all.return_value = []
    
    session.execute.side_effect = [
        mock_signup_check, # Active player check
        mock_votes_check   # Already voted check
    ]
    
    # Vote for self (mvp_team_a = voter_id = 123)
    req = VoteRequest(initData="mock_init_data", game_id=1, mvp_team_a=123, mvp_team_b=789)
    
    with pytest.raises(HTTPException) as exc_info:
        await submit_vote(data=req, session=session)
        
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "You cannot vote for yourself"
