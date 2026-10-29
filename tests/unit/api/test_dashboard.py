import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.routers.dashboard import notify_player_payment, notify_group_unpaid, delete_game
from app.db.models import Game, User

@pytest.mark.asyncio
async def test_notify_player_payment_missing_user_id():
    session = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await notify_player_payment(game_id=1, data={}, admin_id=123, session=session)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Missing user_id"

@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.dashboard.cache_service")
@patch("app.bot.instance.bot")
async def test_notify_player_payment_success(mock_bot, mock_cache, mock_check_admin):
    import datetime
    session = AsyncMock()
    game = Game(id=1, chat_id=-1001, location="Arena", date_time=datetime.datetime.now(), price=150, payment_info="123456")
    user = User(user_id=777, full_name="Player One", language="en")
    
    async def mock_get(model, pk):
        if model == Game: return game
        if model == User: return user
        return None
    session.get.side_effect = mock_get
    mock_cache.set = AsyncMock()
    mock_bot.send_message = AsyncMock()
    
    res = await notify_player_payment(game_id=1, data={"user_id": 777}, admin_id=123, session=session)
    assert res["status"] == "ok"
    assert res["delivery"] == "delivered"
    mock_bot.send_message.assert_awaited_once()

@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.dashboard.cache_service")
async def test_notify_player_payment_guest(mock_cache, mock_check_admin):
    session = AsyncMock()
    game = Game(id=1, chat_id=-1001)
    session.get.return_value = game
    mock_cache.set = AsyncMock()
    
    res = await notify_player_payment(game_id=1, data={"user_id": -999}, admin_id=123, session=session)
    assert res["status"] == "ok"
    assert res["delivery"] == "guest"

@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.dashboard.cache_service")
@patch("app.bot.instance.bot")
async def test_notify_player_payment_blocked(mock_bot, mock_cache, mock_check_admin):
    import datetime
    session = AsyncMock()
    game = Game(id=1, chat_id=-1001, location="Arena", date_time=datetime.datetime.now(), price=150)
    user = User(user_id=888, full_name="Blocked User")
    
    async def mock_get(model, pk):
        if model == Game: return game
        if model == User: return user
        return None
    session.get.side_effect = mock_get
    mock_cache.set = AsyncMock()
    mock_bot.send_message.side_effect = Exception("Forbidden: bot was blocked by the user")
    
    res = await notify_player_payment(game_id=1, data={"user_id": 888}, admin_id=123, session=session)
    assert res["status"] == "ok"
    assert res["delivery"] == "blocked"

@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.dashboard.cache_service")
@patch("app.bot.instance.bot")
async def test_notify_group_unpaid(mock_bot, mock_cache, mock_check_admin):
    import datetime
    from app.db.models import Signup, SignupStatus, Chat
    session = AsyncMock()
    game = Game(id=1, chat_id=-1001, location="Arena", date_time=datetime.datetime.now(), price=150)
    chat = Chat(chat_id=-1001, language="en")
    
    async def mock_get(model, pk):
        if model == Game: return game
        if model == Chat: return chat
        return None
    session.get.side_effect = mock_get
    
    signup1 = Signup(game_id=1, user_id=111, is_paid=False, status=SignupStatus.ACTIVE)
    user1 = User(user_id=111, full_name="User One", username="user1")
    
    mock_res = MagicMock()
    mock_res.all.return_value = [(signup1, user1)]
    session.execute.return_value = mock_res
    mock_cache.set = AsyncMock()
    mock_bot.send_message = AsyncMock()
    
    res = await notify_group_unpaid(game_id=1, admin_id=123, session=session)
    assert res["status"] == "ok"
    assert res["unpaid_count"] == 1
    mock_bot.send_message.assert_awaited_once()

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

@pytest.mark.asyncio
async def test_add_guest_game_not_found():
    from app.api.routers.dashboard import add_guest, GuestCreate
    session = AsyncMock()
    session.get.return_value = None
    data = GuestCreate(name="John Doe", position="CM")
    with pytest.raises(HTTPException) as exc_info:
        await add_guest(game_id=999, data=data, user_id=123, session=session)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Game not found"

@pytest.mark.asyncio
async def test_get_game_votes_game_not_found():
    from app.api.routers.dashboard import get_game_votes
    session = AsyncMock()
    session.get.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await get_game_votes(game_id=999, user_id=123, session=session)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Game not found"

@pytest.mark.asyncio
async def test_update_player_status_invalid_status():
    from app.api.routers.dashboard import update_player_status, StatusUpdate
    from app.db.models import Signup, Game
    session = AsyncMock()
    
    signup = Signup(game_id=1, user_id=123)
    game = Game(chat_id=-1001)
    
    # Mocking session.get calls (first for Signup, second for Game)
    def mock_get(model, ident):
        if model == Signup:
            return signup
        if model == Game:
            return game
        return None
    session.get.side_effect = mock_get
    
    data = StatusUpdate(status="invalid_status")
    with patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock) as mock_check_admin:
        with pytest.raises(HTTPException) as exc_info:
            await update_player_status(signup_id=1, data=data, user_id=123, session=session)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid status"
        mock_check_admin.assert_called_once_with(-1001, 123)

@pytest.mark.asyncio
async def test_update_player_status_signup_not_found():
    from app.api.routers.dashboard import update_player_status, StatusUpdate
    session = AsyncMock()
    session.get.return_value = None
    data = StatusUpdate(status="active")
    with pytest.raises(HTTPException) as exc_info:
        await update_player_status(signup_id=999, data=data, user_id=123, session=session)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Signup not found"

@pytest.mark.asyncio
async def test_kick_player_signup_not_found():
    from app.api.routers.dashboard import kick_player
    session = AsyncMock()
    session.get.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await kick_player(signup_id=999, user_id=123, session=session)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Signup not found"

@pytest.mark.asyncio
async def test_delete_game_not_found():
    from app.api.routers.dashboard import delete_game
    session = AsyncMock()
    session.get.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await delete_game(game_id=999, user_id=123, session=session)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Game not found"

@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
@patch("app.api.routers.dashboard.cache_service")
async def test_add_guest_invalid_position_fallback(mock_cache, mock_check_admin):
    from app.api.routers.dashboard import add_guest, GuestCreate
    from app.db.models import Game, Position
    mock_cache.evict = AsyncMock()
    session = AsyncMock()
    game = Game(id=1, chat_id=-1001)
    session.get.return_value = game

    data = GuestCreate(name="Guest Alex", position="INVALID_POS")
    res = await add_guest(game_id=1, data=data, user_id=123, session=session)

    assert res["status"] == "added"
    # Find user added to session
    added_users = [arg[0][0] for arg in session.add.call_args_list if hasattr(arg[0][0], "player_position")]
    assert len(added_users) == 1
    assert added_users[0].player_position == Position.CM


@pytest.mark.asyncio
async def test_toggle_payment_signup_not_found():
    from app.api.routers.dashboard import toggle_payment
    session = AsyncMock()
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await toggle_payment(signup_id=999, user_id=123, session=session)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Signup not found"


@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
async def test_toggle_payment_success(mock_check_admin):
    from app.api.routers.dashboard import toggle_payment
    from app.db.models import Signup, Game
    session = AsyncMock()
    signup = Signup(id=10, game_id=1, user_id=456, is_paid=False)
    game = Game(id=1, chat_id=-1001)

    async def mock_get(model, pk):
        if model is Signup:
            return signup
        if model is Game:
            return game
        return None

    session.get.side_effect = mock_get
    res = await toggle_payment(signup_id=10, user_id=123, session=session)

    assert res["status"] == "ok"
    assert res["is_paid"] is True
    assert signup.is_paid is True
    session.commit.assert_awaited_once()


