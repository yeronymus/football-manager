import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.routers.dashboard import notify_player_payment, delete_game
from app.db.models import Game

@pytest.mark.asyncio
async def test_notify_player_payment_missing_user_id():
    session = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await notify_player_payment(game_id=1, data={}, admin_id=123, session=session)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Missing user_id"

@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
@patch("app.infrastructure.scheduler.service.SchedulerService")
@patch("app.bot.main.bot", new_callable=MagicMock)
async def test_delete_game_scheduler_error(mock_bot, mock_scheduler_class, mock_check_admin):
    session = AsyncMock()
    # Mock Game object
    game = Game(id=1, chat_id=-1001, message_id=123, admin_message_id=456, voting_message_id=789)
    session.get.return_value = game
    
    # Mock SchedulerService to raise an exception
    mock_scheduler = MagicMock()
    mock_scheduler.cancel_game_tasks.side_effect = Exception("Scheduler error")
    mock_scheduler_class.return_value = mock_scheduler
    
    # Mock bot to do nothing on delete_message
    mock_bot.delete_message = AsyncMock()
    
    # Call delete_game
    res = await delete_game(game_id=1, user_id=123, session=session)
    
    # Assert result is ok and deletion happened
    assert res == {"status": "ok", "message": "Game deleted successfully"}
    session.delete.assert_called_once_with(game)
    session.commit.assert_called_once()
