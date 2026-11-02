import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.scheduler.tasks import send_voting_message
from app.db.models import Game, User, Team, Chat, Language

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
    chat = Chat(chat_id=-1001, title="Test Chat", language=Language.en)
    session.get.return_value = chat
    
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
        text="Match <b>#1</b> is finished.\n\n🏆 <b>Voting for MVP is open!</b>\nVote for the best players using the buttons below.",
        reply_markup=mock_keyboard,
        parse_mode="HTML"
    )
    assert game.voting_message_id == 999
    session.commit.assert_called_once()

@pytest.mark.asyncio
@patch("app.scheduler.tasks.async_session_maker")
@patch("app.scheduler.tasks.bot", new_callable=AsyncMock)
@patch("app.bot.keyboards.get_voting_keyboard")
async def test_send_voting_message_russian(mock_get_keyboard, mock_bot, mock_session_maker):
    session = AsyncMock()
    game = Game(id=2, chat_id=-1002, voting_message_id=None)
    mock_game_res = MagicMock()
    mock_game_res.scalar_one_or_none.return_value = game
    chat = Chat(chat_id=-1002, title="Russian Chat", language=Language.ru)
    session.get.return_value = chat
    
    user_a = User(user_id=10, full_name="Игрок А")
    user_b = User(user_id=20, full_name="Игрок Б")
    mock_players_res = MagicMock()
    mock_players_res.all.return_value = [(user_a, Team.A), (user_b, Team.B)]
    session.execute.side_effect = [mock_game_res, mock_players_res]
    
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = session
    mock_session_maker.return_value = mock_session
    
    mock_keyboard = MagicMock()
    mock_get_keyboard.return_value = mock_keyboard
    
    sent_msg = AsyncMock()
    sent_msg.message_id = 888
    mock_bot.send_message.return_value = sent_msg

    await send_voting_message(game_id=2)
    
    expected_text = (
        "Матч <b>#1</b> завершен.\n\n"
        "🏆 <b>Голосование за MVP открыто!</b>\n"
        "Выберите лучших игроков, нажав на кнопки ниже."
    )
    mock_bot.send_message.assert_called_once_with(
        chat_id=-1002,
        text=expected_text,
        reply_markup=mock_keyboard,
        parse_mode="HTML"
    )
    assert game.voting_message_id == 888


def test_format_votes_count():
    from app.scheduler.tasks import format_votes_count
    # Russian
    assert format_votes_count(1, "ru") == "1 голос"
    assert format_votes_count(2, "ru") == "2 голоса"
    assert format_votes_count(4, "ru") == "4 голоса"
    assert format_votes_count(5, "ru") == "5 голосов"
    assert format_votes_count(11, "ru") == "11 голосов"
    assert format_votes_count(21, "ru") == "21 голос"
    assert format_votes_count(23, "ru") == "23 голоса"

    # English
    assert format_votes_count(1, "en") == "1 vote"
    assert format_votes_count(2, "en") == "2 votes"
    assert format_votes_count(5, "en") == "5 votes"


@pytest.mark.asyncio
@patch("app.scheduler.tasks.async_session_maker")
@patch("app.scheduler.tasks.bot", new_callable=AsyncMock)
async def test_calculate_mvp_with_runners_up_en(mock_bot, mock_session_maker):
    from app.scheduler.tasks import calculate_mvp
    from app.db.models import GameStatus, SignupStatus

    session = AsyncMock()
    game = Game(id=4, chat_id=-1004, status=GameStatus.FINISHED, voting_message_id=555)
    chat = Chat(chat_id=-1004, title="Perfect Wind Footballers", language=Language.en)
    session.get.side_effect = lambda model, obj_id: chat if model == Chat else (game if model == Game else None)

    # 1. Game query
    mock_game_res = MagicMock()
    mock_game_res.scalar_one_or_none.return_value = game

    # 2. Signups query
    mock_signups_res = MagicMock()
    mock_signups_res.all.return_value = [(101, Team.A), (102, Team.A), (201, Team.B)]

    # 3. Votes query: Team A has winner 101 (3 votes) and runner-up 102 (1 vote)
    mock_votes_res = MagicMock()
    mock_votes_res.all.return_value = [
        (Team.A, 101, 3),
        (Team.A, 102, 1),
        (Team.B, 201, 2),
    ]

    # 4. User names
    mock_users_res = MagicMock()
    mock_users_res.all.return_value = [
        (101, "John Winner"),
        (102, "Alex RunnerUp"),
        (201, "Bob Winner"),
    ]

    # 5. GameStats query for stats application
    mock_stat_res = MagicMock()
    mock_stat_res.scalar_one_or_none.return_value = None

    # Mock user fetches for ratings
    u101 = User(user_id=101, full_name="John Winner", rating=100)
    u201 = User(user_id=201, full_name="Bob Winner", rating=100)
    session.get.side_effect = lambda model, uid: {
        Game: game,
        Chat: chat,
        User: (u101 if uid == 101 else (u201 if uid == 201 else None))
    }.get(model)

    # get_group_game_number query
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1

    session.execute.side_effect = [
        mock_game_res,
        mock_count_res,
        mock_signups_res,
        mock_votes_res,
        mock_users_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
    ]

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = session
    mock_session_maker.return_value = mock_session

    await calculate_mvp(game_id=4)

    assert mock_bot.send_message.called
    call_text = mock_bot.send_message.call_args.kwargs["text"]
    
    # Assert English header
    assert "MVP Voting Results" in call_text
    # Assert winner line
    assert "John Winner" in call_text
    # Assert runner-up is listed with votes
    assert "Alex RunnerUp — 1 vote" in call_text
    assert "Bob Winner" in call_text


@pytest.mark.asyncio
@patch("app.scheduler.tasks.async_session_maker")
@patch("app.scheduler.tasks.bot", new_callable=AsyncMock)
async def test_calculate_mvp_with_runners_up_ru(mock_bot, mock_session_maker):
    from app.scheduler.tasks import calculate_mvp
    from app.db.models import GameStatus, SignupStatus

    session = AsyncMock()
    game = Game(id=5, chat_id=-1005, status=GameStatus.FINISHED, voting_message_id=666)
    chat = Chat(chat_id=-1005, title="Russian Group", language=Language.ru)

    mock_game_res = MagicMock()
    mock_game_res.scalar_one_or_none.return_value = game

    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1

    mock_signups_res = MagicMock()
    mock_signups_res.all.return_value = [(101, Team.A), (102, Team.A), (103, Team.A), (201, Team.B)]

    mock_votes_res = MagicMock()
    mock_votes_res.all.return_value = [
        (Team.A, 101, 5),
        (Team.A, 102, 3),
        (Team.A, 103, 1),
        (Team.B, 201, 4),
    ]

    mock_users_res = MagicMock()
    mock_users_res.all.return_value = [
        (101, "Иван Победитель"),
        (102, "Алексей Второй"),
        (103, "Дмитрий Третий"),
        (201, "Петр Лучший"),
    ]

    mock_stat_res = MagicMock()
    mock_stat_res.scalar_one_or_none.return_value = None

    u101 = User(user_id=101, full_name="Иван Победитель", rating=100)
    u201 = User(user_id=201, full_name="Петр Лучший", rating=100)
    session.get.side_effect = lambda model, uid: {
        Game: game,
        Chat: chat,
        User: (u101 if uid == 101 else (u201 if uid == 201 else None))
    }.get(model)

    session.execute.side_effect = [
        mock_game_res,
        mock_count_res,
        mock_signups_res,
        mock_votes_res,
        mock_users_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
        mock_stat_res,
    ]

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = session
    mock_session_maker.return_value = mock_session

    await calculate_mvp(game_id=5)

    assert mock_bot.send_message.called
    call_text = mock_bot.send_message.call_args.kwargs["text"]

    # Assert Russian header
    assert "Итоги голосования за MVP" in call_text
    assert "Иван Победитель" in call_text
    # Assert runner-ups with proper Russian grammar (3 -> 3 голоса, 1 -> 1 голос)
    assert "Алексей Второй — 3 голоса" in call_text
    assert "Дмитрий Третий — 1 голос" in call_text
    assert "Петр Лучший" in call_text
