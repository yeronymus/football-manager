import pytest
import datetime
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch, MagicMock
from app.api.routers.admin import create_game, update_game, admin_balance_teams
from app.api.schemas import GameCreate, GameUpdate, BalanceTeams
from app.db.models import Game

@pytest.mark.asyncio
@patch("app.api.routers.admin.validate_init_data")
@patch("app.api.routers.admin.get_user_from_init_data")
@patch("app.api.routers.admin.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.admin._ensure_creator_exists", new_callable=AsyncMock)
@patch("app.api.routers.admin.cache_service")
async def test_create_game_success(mock_cache, mock_creator, mock_admin_rights, mock_get_user, mock_validate, mock_event_bus=None):
    mock_validate.return_value = True
    mock_get_user.return_value = 123
    mock_cache.evict = AsyncMock()
    
    # Mock database session
    session = AsyncMock()
    
    # Mock GameLifecycleService
    with patch("app.core.services.game_lifecycle.GameLifecycleService.create_game", new_callable=AsyncMock) as mock_lifecycle_create_game:
        created_game = Game(id=777, chat_id=-1001, date_time=datetime.datetime(2026, 6, 20, 15, 0))
        mock_lifecycle_create_game.return_value = created_game
        
        data = GameCreate(
            initData="mock_init_data",
            chat_id=-1001,
            date_time=datetime.datetime(2026, 6, 20, 15, 0),
            location="Plaminkove",
            max_players=22
        )
        
        bg_tasks = MagicMock()
        
        res = await create_game(data=data, background_tasks=bg_tasks, session=session)
        
        assert res == {"game_id": 777, "status": "created"}
        mock_lifecycle_create_game.assert_called_once()
        mock_cache.evict.assert_called_once_with("game_details:777")
        bg_tasks.add_task.assert_called_once()

@pytest.mark.asyncio
@patch("app.api.routers.admin.validate_init_data")
async def test_create_game_invalid_init_data(mock_validate):
    mock_validate.return_value = False
    data = GameCreate(
        initData="invalid_init_data",
        chat_id=-1001,
        date_time=datetime.datetime(2026, 6, 20, 15, 0),
        location="Plaminkove",
        max_players=22
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_game(data=data, background_tasks=MagicMock(), session=AsyncMock())
    assert exc_info.value.status_code == 403

@pytest.mark.asyncio
@patch("app.api.routers.admin.validate_init_data")
@patch("app.api.routers.admin.get_user_from_init_data")
@patch("app.api.routers.admin.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.admin.cache_service")
async def test_update_game_success(mock_cache, mock_admin_rights, mock_get_user, mock_validate):
    mock_validate.return_value = True
    mock_get_user.return_value = 123
    mock_cache.evict = AsyncMock()
    
    session = AsyncMock()
    game = Game(id=1, chat_id=-1001)
    
    # Mock select execute
    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = game
    session.execute.return_value = mock_exec_res
    
    with patch("app.core.services.game_lifecycle.GameLifecycleService.update_game", new_callable=AsyncMock) as mock_lifecycle_update:
        mock_lifecycle_update.return_value = (game, ["location"])
        
        data = GameUpdate(
            initData="mock_init_data",
            game_id=1,
            location="New Location"
        )
        bg_tasks = MagicMock()
        
        res = await update_game(data=data, background_tasks=bg_tasks, session=session)
        assert res == {"status": "updated", "id": 1}
        mock_cache.evict.assert_called_once_with("game_details:1")

@pytest.mark.asyncio
@patch("app.api.routers.admin.validate_init_data")
@patch("app.api.routers.admin.get_user_from_init_data")
@patch("app.api.routers.admin.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.admin.cache_service")
async def test_admin_balance_teams_success(mock_cache, mock_admin_rights, mock_get_user, mock_validate):
    mock_validate.return_value = True
    mock_get_user.return_value = 123
    mock_cache.evict = AsyncMock()
    
    session = AsyncMock()
    game = Game(id=1, chat_id=-1001)
    
    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = game
    session.execute.return_value = mock_exec_res
    
    with patch("app.core.services.roster.RosterService.balance_teams", new_callable=AsyncMock) as mock_balance:
        data = BalanceTeams(initData="mock_init_data", game_id=1)
        bg_tasks = MagicMock()
        
        res = await admin_balance_teams(data=data, background_tasks=bg_tasks, session=session)
        assert res == {"status": "balanced"}
        mock_balance.assert_called_once_with(1)
        mock_cache.evict.assert_called_once_with("game_details:1")
