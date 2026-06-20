import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.scheduler.tasks import send_voting_message
from app.db.models import Game, User, Team

@pytest.mark.asyncio
@patch("app.scheduler.tasks.async_session_maker")
@patch("app.scheduler.tasks.bot", new_callable=AsyncMock)
@patch("app.bot.keyboards.get_voting_keyboard")
async def test_send_voting_message_no_game(mock_get_keyboard, mock_bot, mock_session_maker):
    # Mock database session to return no game
    session = AsyncMock()
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_execute_res
    
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = session
    mock_session_maker.return_value = mock_session

    await send_voting_message(game_id=1)
    
    mock_bot.send_message.assert_not_called()

@pytest.mark.asyncio
@patch("app.scheduler.tasks.async_session_maker")
@patch("app.scheduler.tasks.bot", new_callable=AsyncMock)
@patch("app.bot.keyboards.get_voting_keyboard")
async def test_send_voting_message_success(mock_get_keyboard, mock_bot, mock_session_maker):
    session = AsyncMock()
    # Mock game
    game = Game(id=1, chat_id=-1001, voting_message_id=123)
    mock_game_res = MagicMock()
    mock_game_res.scalar_one_or_none.return_value = game
    
    # Mock players
    user_a = User(user_id=10, full_name="Player A")
    user_b = User(user_id=20, full_name="Player B")
    
    mock_players_res = MagicMock()
    mock_players_res.all.return_value = [(user_a, Team.A), (user_b, Team.B)]
    
    session.execute.side_effect = [mock_game_res, mock_players_res]
    
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = session
    mock_session_maker.return_value = mock_session
    
    # Mock keyboard and sent message
    mock_keyboard = MagicMock()
    mock_get_keyboard.return_value = mock_keyboard
    
    sent_msg = AsyncMock()
    sent_msg.message_id = 999
    mock_bot.send_message.return_value = sent_msg

    await send_voting_message(game_id=1)
    
    # Verify mock bot interactions
    mock_bot.delete_message.assert_called_once_with(chat_id=-1001, message_id=123)
    mock_bot.send_message.assert_called_once_with(
        chat_id=-1001,
        text="Матч <b>#1</b> завершен.\n\n<b>Голосование за MVP открыто!</b>\nВыберите лучших игроков (по одному от команды), нажав на кнопки ниже.",
        reply_markup=mock_keyboard,
        parse_mode="HTML"
    )
    assert game.voting_message_id == 999
    session.commit.assert_called_once()
