import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import BackgroundTasks
from app.api.routers.games import join_game, leave_game

@pytest.mark.asyncio
async def test_leave_game_triggers_event_bus():
    background_tasks = BackgroundTasks()
    
    with patch("app.core.uow.UnitOfWork") as mock_uow_cls, \
         patch("app.core.services.roster.RosterService.leave_player", new_callable=AsyncMock) as mock_leave, \
         patch("app.core.events.event_bus.publish", new_callable=AsyncMock) as mock_publish:
         
        mock_uow = AsyncMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow_cls.return_value = mock_uow
        
        # User 123 leaves game 1, no one promoted
        mock_leave.return_value = (True, "Вы выписались.", None)
        
        res = await leave_game(game_id=1, background_tasks=background_tasks, user_id=123)
        assert res["success"] is True
        assert res["message"] == "Вы выписались."
        
        # Execute background tasks
        await background_tasks()
        
        mock_publish.assert_awaited_once()
        published_event = mock_publish.call_args[0][0]
        assert published_event.game_id == 1
        assert published_event.user_id == 123

@pytest.mark.asyncio
async def test_join_game_triggers_event_bus():
    background_tasks = BackgroundTasks()
    
    with patch("app.core.uow.UnitOfWork") as mock_uow_cls, \
         patch("app.core.services.roster.RosterService.join_player", new_callable=AsyncMock) as mock_join, \
         patch("app.core.events.event_bus.publish", new_callable=AsyncMock) as mock_publish:
         
        mock_uow = AsyncMock()
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow.user_repo.get_by_id = AsyncMock(return_value=MagicMock(user_id=123))
        mock_uow_cls.return_value = mock_uow
        
        mock_signup = MagicMock(id=10, game_id=1, user_id=123)
        mock_join_res = MagicMock(success=True, signup=mock_signup, is_reserve=False, message="Вы записаны!")
        mock_join.return_value = mock_join_res
        
        res = await join_game(game_id=1, background_tasks=background_tasks, user_id=123)
        assert res["success"] is True
        assert res["is_reserve"] is False
        
        # Execute background tasks
        await background_tasks()
        
        mock_publish.assert_awaited_once()
        published_event = mock_publish.call_args[0][0]
        assert published_event.game_id == 1
        assert published_event.user_id == 123
