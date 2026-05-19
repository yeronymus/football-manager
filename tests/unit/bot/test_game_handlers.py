import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram import types
from app.bot.handlers.game_handlers import process_join, process_leave
from app.core.services.roster import PlayerJoinedEvent, PlayerLeftEvent

@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
@patch("app.bot.handlers.game_handlers.RosterService")
@patch("app.bot.handlers.game_handlers.event_bus")
async def test_process_join_success(mock_event_bus, mock_roster_service_class, mock_uow_class):
    # Setup UoW Mock
    mock_uow = MagicMock()
    mock_uow.commit = AsyncMock()
    mock_user_repo = AsyncMock()
    mock_user = MagicMock()
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_uow.user_repo = mock_user_repo
    
    mock_uow_class.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow_class.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup RosterService Mock
    mock_service = MagicMock()
    result = MagicMock()
    result.success = True
    result.is_reserve = False
    result.signup = MagicMock()
    result.message = "Joined"
    mock_service.join_player = AsyncMock(return_value=result)
    mock_roster_service_class.return_value = mock_service

    # Setup Event Bus Mock
    mock_event_bus.publish = AsyncMock()

    # Setup Callback mock
    callback = MagicMock()
    callback.data = "join_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()

    # Dummy translation function
    _ = lambda x: f"translated_{x}"

    await process_join(callback, _)

    # Assertions
    mock_user_repo.get_by_id.assert_called_once_with(456)
    mock_service.join_player.assert_called_once_with(123, mock_user, ignore_limit=False)
    mock_uow.commit.assert_called_once()
    mock_event_bus.publish.assert_called_once()
    callback.answer.assert_any_call("translated_user_joined_success")


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
@patch("app.bot.handlers.game_handlers.RosterService")
@patch("app.bot.handlers.game_handlers.event_bus")
async def test_process_join_reserve(mock_event_bus, mock_roster_service_class, mock_uow_class):
    # Setup UoW Mock
    mock_uow = MagicMock()
    mock_uow.commit = AsyncMock()
    mock_user_repo = AsyncMock()
    mock_user = MagicMock()
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_uow.user_repo = mock_user_repo
    
    mock_uow_class.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow_class.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup RosterService Mock
    mock_service = MagicMock()
    result = MagicMock()
    result.success = True
    result.is_reserve = True
    result.signup = MagicMock()
    result.message = "Reserve"
    mock_service.join_player = AsyncMock(return_value=result)
    mock_roster_service_class.return_value = mock_service

    # Setup Event Bus Mock
    mock_event_bus.publish = AsyncMock()

    # Setup Callback mock
    callback = MagicMock()
    callback.data = "join_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()

    # Dummy translation function
    _ = lambda x: f"translated_{x}"

    await process_join(callback, _)

    # Assertions
    mock_uow.commit.assert_called_once()
    mock_event_bus.publish.assert_called_once()
    callback.answer.assert_any_call("translated_user_joined_reserve")


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
@patch("app.bot.handlers.game_handlers.RosterService")
@patch("app.bot.handlers.game_handlers.event_bus")
async def test_process_join_registration_required(mock_event_bus, mock_roster_service_class, mock_uow_class):
    # Setup UoW Mock where user is not found in DB
    mock_uow = MagicMock()
    mock_user_repo = AsyncMock()
    mock_user_repo.get_by_id = AsyncMock(return_value=None)
    mock_uow.user_repo = mock_user_repo
    
    mock_uow_class.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow_class.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup Callback mock
    callback = MagicMock()
    callback.data = "join_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()
    callback.bot = AsyncMock()
    callback.bot.get_me = AsyncMock(return_value=MagicMock(username="my_bot"))

    # Dummy translation function
    _ = lambda x: f"translated_{x}"

    await process_join(callback, _)

    # Assertions
    callback.bot.get_me.assert_called_once()
    callback.answer.assert_called_once_with("Нужна регистрация!", url="https://t.me/my_bot?start=reg")
    mock_event_bus.publish.assert_not_called()


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
@patch("app.bot.handlers.game_handlers.RosterService")
@patch("app.bot.handlers.game_handlers.event_bus")
async def test_process_join_failure(mock_event_bus, mock_roster_service_class, mock_uow_class):
    # Setup UoW Mock
    mock_uow = MagicMock()
    mock_uow.commit = AsyncMock()
    mock_user_repo = AsyncMock()
    mock_user = MagicMock()
    mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
    mock_uow.user_repo = mock_user_repo
    
    mock_uow_class.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow_class.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup RosterService Mock returning success=False
    mock_service = MagicMock()
    result = MagicMock()
    result.success = False
    result.message = "Game is Full"
    mock_service.join_player = AsyncMock(return_value=result)
    mock_roster_service_class.return_value = mock_service

    # Setup Callback mock
    callback = MagicMock()
    callback.data = "join_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()

    # Dummy translation function
    _ = lambda x: f"translated_{x}"

    await process_join(callback, _)

    # Assertions
    mock_uow.commit.assert_not_called()
    callback.answer.assert_called_once_with("Game is Full", show_alert=True)
    mock_event_bus.publish.assert_not_called()


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
async def test_process_join_system_exception(mock_uow_class):
    # Raise exception in UoW
    mock_uow_class.side_effect = Exception("Database failure")

    callback = MagicMock()
    callback.data = "join_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()

    _ = lambda x: f"translated_{x}"

    await process_join(callback, _)

    callback.answer.assert_called_once_with("Ошибка системы. Мы уже чиним.", show_alert=True)


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
@patch("app.bot.handlers.game_handlers.RosterService")
@patch("app.bot.handlers.game_handlers.event_bus")
async def test_process_leave_success_no_promotion(mock_event_bus, mock_roster_service_class, mock_uow_class):
    # Setup UoW Mock
    mock_uow = MagicMock()
    mock_uow.commit = AsyncMock()
    
    mock_uow_class.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow_class.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup RosterService Mock
    mock_service = MagicMock()
    # success, msg, promoted
    mock_service.leave_player = AsyncMock(return_value=(True, "Left game", None))
    mock_roster_service_class.return_value = mock_service

    # Setup Event Bus Mock
    mock_event_bus.publish = AsyncMock()

    # Setup Callback mock
    callback = MagicMock()
    callback.data = "leave_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()
    callback.bot = AsyncMock()

    await process_leave(callback)

    # Assertions
    mock_service.leave_player.assert_called_once_with(123, 456, False)
    mock_uow.commit.assert_called_once()
    mock_event_bus.publish.assert_called_once()
    callback.bot.send_message.assert_not_called()
    callback.answer.assert_called_once_with("Left game")


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
@patch("app.bot.handlers.game_handlers.RosterService")
@patch("app.bot.handlers.game_handlers.event_bus")
async def test_process_leave_success_with_promotion(mock_event_bus, mock_roster_service_class, mock_uow_class):
    # Setup UoW Mock
    mock_uow = MagicMock()
    mock_uow.commit = AsyncMock()
    
    mock_uow_class.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow_class.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup RosterService Mock
    mock_service = MagicMock()
    promoted_user = MagicMock()
    promoted_user.user_id = 789
    mock_service.leave_player = AsyncMock(return_value=(True, "Left game", promoted_user))
    mock_roster_service_class.return_value = mock_service

    # Setup Event Bus Mock
    mock_event_bus.publish = AsyncMock()

    # Setup Callback mock
    callback = MagicMock()
    callback.data = "leave_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()
    callback.bot = AsyncMock()
    callback.bot.send_message = AsyncMock()

    await process_leave(callback)

    # Assertions
    mock_uow.commit.assert_called_once()
    callback.bot.send_message.assert_called_once_with(789, "🚀 Вы переведены в основной состав!")
    mock_event_bus.publish.assert_called_once()
    callback.answer.assert_called_once_with("Left game")


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
@patch("app.bot.handlers.game_handlers.RosterService")
@patch("app.bot.handlers.game_handlers.event_bus")
async def test_process_leave_failure(mock_event_bus, mock_roster_service_class, mock_uow_class):
    # Setup UoW Mock
    mock_uow = MagicMock()
    mock_uow.commit = AsyncMock()
    
    mock_uow_class.return_value.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow_class.return_value.__aexit__ = AsyncMock(return_value=False)

    # Setup RosterService Mock returning success=False
    mock_service = MagicMock()
    mock_service.leave_player = AsyncMock(return_value=(False, "Not signed up", None))
    mock_roster_service_class.return_value = mock_service

    # Setup Callback mock
    callback = MagicMock()
    callback.data = "leave_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()

    await process_leave(callback)

    # Assertions
    mock_uow.commit.assert_not_called()
    mock_event_bus.publish.assert_not_called()
    callback.answer.assert_called_once_with("Not signed up", show_alert=True)


@pytest.mark.asyncio
@patch("app.bot.handlers.game_handlers.UnitOfWork")
async def test_process_leave_system_exception(mock_uow_class):
    # Raise exception in UoW
    mock_uow_class.side_effect = Exception("Database failure")

    callback = MagicMock()
    callback.data = "leave_123"
    callback.from_user = MagicMock()
    callback.from_user.id = 456
    callback.answer = AsyncMock()

    await process_leave(callback)

    callback.answer.assert_called_once_with("Ошибка выхода.", show_alert=True)
