import pytest
from unittest.mock import AsyncMock, MagicMock
from app.bot.handlers.vote_handlers import process_vote
from app.db.models import Signup, SignupStatus, Team, User

@pytest.mark.asyncio
async def test_process_vote_non_participant():
    callback = AsyncMock()
    callback.data = "vote_54_100"
    callback.from_user.id = 999
    
    session = AsyncMock()
    # Mock signup query returning None (not in game)
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res
    
    mock_t = MagicMock(side_effect=lambda k, **kw: f"translated_{k}")
    
    await process_vote(callback=callback, session=session, _=mock_t)
    
    callback.answer.assert_called_once_with("translated_vote_only_participants", show_alert=True)

@pytest.mark.asyncio
async def test_process_vote_self_voting():
    callback = AsyncMock()
    callback.data = "vote_54_999"
    callback.from_user.id = 999
    
    session = AsyncMock()
    mock_t = MagicMock(side_effect=lambda k, **kw: f"translated_{k}")
    
    await process_vote(callback=callback, session=session, _=mock_t)
    
    callback.answer.assert_called_once_with("translated_vote_cannot_self", show_alert=True)
