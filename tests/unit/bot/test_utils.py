import sys
import types
from unittest.mock import AsyncMock, MagicMock

# Inject mock app.bot.admin_dashboard module to avoid ImportError or resolver issues
mock_dashboard_module = types.ModuleType("app.bot.admin_dashboard")
mock_dashboard_module.update_dashboard_message = AsyncMock()
sys.modules["app.bot.admin_dashboard"] = mock_dashboard_module

import pytest
import html
from datetime import datetime, timezone
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game, Signup, User, SignupStatus, Position, Team, GameStatus, GameType, Chat, Language
from app.bot.utils import format_game_message, update_game_message, format_positions, get_group_game_number

async def setup_base_entities(session: AsyncSession):
    creator = User(
        user_id=1,
        username="creator",
        full_name="Creator User",
        player_position=Position.MID,
        alt_positions=["DEF", "FWD"],
        language=Language.ru
    )
    chat = Chat(chat_id=-1001, title="Test Chat", language=Language.ru)
    session.add(creator)
    session.add(chat)
    await session.commit()
    return creator, chat

@pytest.mark.asyncio
async def test_format_positions():
    user = User(player_position=Position.MID, alt_positions=["DEF", "FWD"])
    signup_no_override = Signup(position=None)
    signup_override = Signup(position=Position.GK)
    
    assert format_positions(user, signup_no_override) == "MID (DEF, FWD)"
    assert format_positions(user, signup_override) == "GK (DEF, FWD)"
    
    user_no_alt = User(player_position=Position.ST, alt_positions=[])
    assert format_positions(user_no_alt, signup_no_override) == "ST"

@pytest.mark.asyncio
async def test_format_game_message_empty(session: AsyncSession):
    creator, chat = await setup_base_entities(session)
    
    game = Game(
        id=123,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Prague Stadium",
        max_players=14,
        price=150,
        payment_info="Test Pay Info",
        team_count=2,
        status=GameStatus.OPEN,
        game_type=GameType.REGULAR,
        duration=1.5
    )
    session.add(game)
    await session.commit()
    
    # 1. Test short version
    text_short = await format_game_message(game, session, is_short=True, signups=[])
    assert "🟢 <b>Общая игра</b>" in text_short
    assert "#1" in text_short
    assert "Prague Stadium" in text_short
    assert "Игроков" in text_short
    assert "0/14" in text_short
    
    # 2. Test full version (no teams show because status is OPEN)
    text_full = await format_game_message(game, session, is_short=False, signups=[])
    assert "🟢 <b>Общая игра</b>" in text_full
    assert "Игроки" in text_full
    assert "0/" in text_full
    assert "Пока никого... 🦗" in text_full
    assert "Взнос" in text_full
    assert "150 крон" in text_full
    assert "Test Pay Info" in text_full

@pytest.mark.asyncio
async def test_format_game_message_massive_rosters(session: AsyncSession):
    creator, chat = await setup_base_entities(session)
    
    game = Game(
        id=124,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Strahov Pitch",
        max_players=10,
        price=0, # Free game
        team_count=2,
        status=GameStatus.OPEN,
        game_type=GameType.DRAFT
    )
    session.add(game)
    await session.commit()
    
    # Construct 12 signups (10 active, 2 reserve)
    signups = []
    for i in range(1, 13):
        status = SignupStatus.ACTIVE if i <= 10 else SignupStatus.RESERVE
        player = User(
            user_id=100 + i,
            username=f"player{i}",
            full_name=f"Player {i}",
            player_position=Position.DEF,
            alt_positions=[]
        )
        session.add(player)
        signup = Signup(
            game_id=game.id,
            user_id=player.user_id,
            status=status,
            position=None
        )
        session.add(signup)
        signups.append((signup, player))
        
    await session.commit()
    
    text = await format_game_message(game, session, is_short=False, signups=signups)
    assert "🎯 <b>Драфт</b>" in text
    assert "Игроки" in text
    assert "10/" in text
    assert "Player 1" in text
    assert "Player 10" in text
    assert "Резерв" in text
    assert "2" in text
    assert "Player 11" in text
    assert "Player 12" in text
    assert "Взнос" not in text # Because price is 0

@pytest.mark.asyncio
async def test_format_game_message_special_characters(session: AsyncSession):
    creator, chat = await setup_base_entities(session)
    
    game = Game(
        id=125,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="<script>alert('xss')</script> Field & Pitch",
        max_players=10,
        price=100,
        payment_info="<b>HTML Pay</b>",
        team_count=2,
        status=GameStatus.OPEN,
        game_type=GameType.REGULAR
    )
    session.add(game)
    
    player = User(
        user_id=200,
        username="hacker",
        full_name="<b>Hacker</b> & <Code>",
        player_position=Position.FWD,
        alt_positions=[]
    )
    session.add(player)
    signup = Signup(game_id=game.id, user_id=player.user_id, status=SignupStatus.ACTIVE)
    session.add(signup)
    
    await session.commit()
    
    text = await format_game_message(game, session, is_short=False, signups=[(signup, player)])
    
    # Assert location, payment info, and full_name are html-escaped
    assert html.escape(game.location) in text
    assert html.escape(game.payment_info) in text
    assert html.escape(player.full_name) in text
    assert "<script>" not in text
    assert "<b>Hacker</b>" not in text

@pytest.mark.asyncio
async def test_format_game_message_teams(session: AsyncSession):
    creator, chat = await setup_base_entities(session)
    
    game = Game(
        id=126,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Team Field",
        max_players=12,
        price=100,
        team_count=2,
        status=GameStatus.ACTIVE, # ACTIVE state triggers team display
        game_type=GameType.REGULAR,
        has_active_gk_a=True,
        has_active_gk_b=True
    )
    session.add(game)
    
    # Signups:
    # 2 in Team A (1 GK, 1 DEF)
    # 2 in Team B (1 GK, 1 DEF)
    # 1 Unassigned active
    p1 = User(user_id=301, full_name="A GK", player_position=Position.GK)
    p2 = User(user_id=302, full_name="A DEF", player_position=Position.DEF)
    p3 = User(user_id=303, full_name="B GK", player_position=Position.GK)
    p4 = User(user_id=304, full_name="B DEF", player_position=Position.DEF)
    p5 = User(user_id=305, full_name="Unassigned Player", player_position=Position.MID)
    session.add_all([p1, p2, p3, p4, p5])
    
    s1 = Signup(game_id=game.id, user_id=p1.user_id, status=SignupStatus.ACTIVE, team=Team.A)
    s2 = Signup(game_id=game.id, user_id=p2.user_id, status=SignupStatus.ACTIVE, team=Team.A)
    s3 = Signup(game_id=game.id, user_id=p3.user_id, status=SignupStatus.ACTIVE, team=Team.B)
    s4 = Signup(game_id=game.id, user_id=p4.user_id, status=SignupStatus.ACTIVE, team=Team.B)
    s5 = Signup(game_id=game.id, user_id=p5.user_id, status=SignupStatus.ACTIVE, team=None)
    session.add_all([s1, s2, s3, s4, s5])
    
    await session.commit()
    
    signups = [(s1, p1), (s2, p2), (s3, p3), (s4, p4), (s5, p5)]
    text = await format_game_message(game, session, is_short=False, signups=signups)
    
    assert "Команда А" in text
    assert "Команда Б" in text
    assert "A GK" in text
    assert "B GK" in text
    assert "Нераспределенные" in text
    assert "Unassigned Player" in text

@pytest.mark.asyncio
async def test_update_game_message_success(session: AsyncSession):
    creator, chat = await setup_base_entities(session)
    
    game = Game(
        id=127,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Stadium",
        max_players=10,
        status=GameStatus.OPEN,
        message_id=9901,
        channel_id=-1002,
        channel_message_id=9902
    )
    session.add(game)
    await session.commit()
    
    bot = MagicMock()
    bot.edit_message_text = AsyncMock()
    
    # Reset mock_dashboard_module
    mock_dashboard_module.update_dashboard_message.reset_mock()
    
    await update_game_message(bot, game, session)
    
    # Verify both public message and channel message edit_message_text were called
    assert bot.edit_message_text.call_count == 2
    # Verify admin dashboard update triggered
    mock_dashboard_module.update_dashboard_message.assert_called_once_with(bot, game.id, session)

@pytest.mark.asyncio
async def test_update_game_message_telegram_bad_request(session: AsyncSession):
    creator, chat = await setup_base_entities(session)
    
    game = Game(
        id=128,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Stadium",
        max_players=10,
        status=GameStatus.OPEN,
        message_id=9903,
        channel_id=-1002,
        channel_message_id=9904
    )
    session.add(game)
    await session.commit()
    
    bot = MagicMock()
    # Mock bot.edit_message_text to raise TelegramBadRequest
    bot.edit_message_text = AsyncMock(
        side_effect=TelegramBadRequest(
            method="editMessageText",
            message="message is not modified: specified new message content and reply markup are exactly the same as a current..."
        )
    )
    
    # Reset mock_dashboard_module
    mock_dashboard_module.update_dashboard_message.reset_mock()
    
    # This call should not raise an error as TelegramBadRequest is caught and logged
    await update_game_message(bot, game, session)
    
    assert bot.edit_message_text.call_count == 2
    mock_dashboard_module.update_dashboard_message.assert_called_once_with(bot, game.id, session)

@pytest.mark.asyncio
async def test_update_game_message_telegram_generic_exception(session: AsyncSession):
    creator, chat = await setup_base_entities(session)
    
    game = Game(
        id=129,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Stadium",
        max_players=10,
        status=GameStatus.OPEN,
        message_id=9905,
        channel_id=-1002,
        channel_message_id=9906
    )
    session.add(game)
    await session.commit()
    
    bot = MagicMock()
    # Mock bot.edit_message_text to raise a generic Exception
    bot.edit_message_text = AsyncMock(
        side_effect=Exception("Unknown telegram network error")
    )
    
    # Reset mock_dashboard_module
    mock_dashboard_module.update_dashboard_message.reset_mock()
    
    # This call should not raise an error as general Exception is caught and logged
    await update_game_message(bot, game, session)
    
    assert bot.edit_message_text.call_count == 2
    mock_dashboard_module.update_dashboard_message.assert_called_once_with(bot, game.id, session)


@pytest.mark.asyncio
async def test_get_group_game_number_sequential_and_cancelled(session: AsyncSession):
    """
    Verifies that:
    1. Active/finished games increment sequential number: 1..18.
    2. Cancelled games (19..43) are excluded from the sequential count.
    3. Game #44 is correctly numbered as 19, resolving the bug:
       'Почему-то после 18-ой игры начинается 44-ая'.
    """
    creator, chat = await setup_base_entities(session)

    # Create 18 finished/open games
    games = []
    for i in range(1, 19):
        g = Game(
            id=i,
            chat_id=chat.chat_id,
            created_by=creator.user_id,
            date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
            location="Stadium",
            status=GameStatus.FINISHED if i < 18 else GameStatus.OPEN
        )
        session.add(g)
        games.append(g)
    await session.commit()

    # Check game 18 is #18
    num_18 = await get_group_game_number(session, games[17])
    assert num_18 == 18

    # Create 25 CANCELLED games (IDs 19..43)
    cancelled_games = []
    for i in range(19, 44):
        g = Game(
            id=i,
            chat_id=chat.chat_id,
            created_by=creator.user_id,
            date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
            location="Stadium",
            status=GameStatus.CANCELLED
        )
        session.add(g)
        cancelled_games.append(g)
    await session.commit()

    # Create Game with ID 44 as OPEN
    game_44 = Game(
        id=44,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Stadium",
        status=GameStatus.OPEN
    )
    session.add(game_44)
    await session.commit()

    # Crucial test: Game 44 should be sequentially numbered as 19, NOT 44!
    num_44 = await get_group_game_number(session, game_44)
    assert num_44 == 19


@pytest.mark.asyncio
async def test_get_group_game_number_fallback_safety(session: AsyncSession):
    """Fallback when game is None or chat_id is missing returns 1, not 0 or raw ID."""
    assert await get_group_game_number(session, None) == 1

    game_no_chat = Game(id=44, chat_id=None)
    assert await get_group_game_number(session, game_no_chat) == 1



@pytest.mark.asyncio
async def test_format_game_message_english(session: AsyncSession):
    creator = User(
        user_id=200,
        username="en_creator",
        full_name="English Creator",
        player_position=Position.MID,
        language=Language.en
    )
    chat = Chat(chat_id=-1002, title="English Chat", language=Language.en)
    session.add(creator)
    session.add(chat)
    await session.commit()

    game = Game(
        id=999,
        chat_id=chat.chat_id,
        created_by=creator.user_id,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Prague Stadium",
        max_players=14,
        price=150,
        payment_info="Test Pay Info",
        team_count=2,
        status=GameStatus.OPEN,
        game_type=GameType.REGULAR,
        duration=1.5
    )
    session.add(game)
    await session.commit()

    text_en = await format_game_message(game, session, is_short=False, signups=[])
    assert "🟢 <b>General Match</b>" in text_en
    assert "Players" in text_en
    assert "Match fee" in text_en
    assert "150 CZK" in text_en

@pytest.mark.asyncio
async def test_resolve_chat_language_scenarios(session: AsyncSession):
    from app.bot.utils import resolve_chat_language
    
    # 1. Missing or None chat_id defaults to 'ru'
    assert await resolve_chat_language(session, None) == "ru"
    assert await resolve_chat_language(session, 0) == "ru"
    
    # 2. Non-existent chat defaults to 'ru'
    assert await resolve_chat_language(session, -999999999) == "ru"
    
    # 3. Direct match with Russian chat
    chat_ru = Chat(chat_id=-1005555, title="RU Group", language=Language.ru, channel_id=-1007777)
    session.add(chat_ru)
    await session.commit()
    assert await resolve_chat_language(session, -1005555) == "ru"
    
    # 4. Supergroup vs regular group prefix tolerance (-1005555 vs -5555)
    assert await resolve_chat_language(session, -5555) == "ru"
    
    # 5. Linked channel resolution (-1007777 -> chat_ru)
    assert await resolve_chat_language(session, -1007777) == "ru"
    assert await resolve_chat_language(session, -7777) == "ru"
    
    # 6. English chat
    chat_en = Chat(chat_id=-1006666, title="EN Group", language=Language.en)
    session.add(chat_en)
    await session.commit()
    assert await resolve_chat_language(session, -1006666) == "en"
    assert await resolve_chat_language(session, -6666) == "en"


@pytest.mark.asyncio
async def test_finish_announcement_localization(session: AsyncSession):
    from app.api.routers.admin import _build_finish_announcement
    from app.core.domain.dto import PlayerStatDTO
    
    # Setup users
    u1 = User(user_id=501, full_name="Yeronym", player_position=Position.MID)
    u2 = User(user_id=502, full_name="Alex", player_position=Position.FWD)
    session.add_all([u1, u2])
    
    # 1. Russian Chat
    chat_ru = Chat(chat_id=-1008881, title="RU League", language=Language.ru)
    session.add(chat_ru)
    await session.commit()
    
    game_ru = Game(
        id=701,
        chat_id=chat_ru.chat_id,
        created_by=501,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Field 1",
        score_a=3,
        score_b=2,
        status=GameStatus.FINISHED
    )
    session.add(game_ru)
    await session.commit()
    
    class MockFinishData:
        mvp_team_a = 501
        mvp_team_b = None
        player_stats = [PlayerStatDTO(user_id=502, goals=2)]
        
    text_ru = await _build_finish_announcement(
        session=session,
        game=game_ru,
        voting_results=[("Yeronym", 5)],
        data=MockFinishData()
    )
    assert "Матч #1 завершен!" in text_ru
    assert "Команда оранжевые 🟠 3:2 🟢 Команда зеленые" in text_ru
    assert "MVP:</b> Yeronym" in text_ru
    assert "Голоса за MVP:" in text_ru
    assert "Голы:" in text_ru
    assert "Alex: 2" in text_ru
    
    # 2. English Chat
    chat_en = Chat(chat_id=-1008882, title="EN League", language=Language.en)
    session.add(chat_en)
    await session.commit()
    
    game_en = Game(
        id=702,
        chat_id=chat_en.chat_id,
        created_by=501,
        date_time=datetime(2026, 5, 20, 18, 0, tzinfo=timezone.utc),
        location="Field 2",
        score_a=4,
        score_b=1,
        status=GameStatus.FINISHED
    )
    session.add(game_en)
    await session.commit()
    
    text_en = await _build_finish_announcement(
        session=session,
        game=game_en,
        voting_results=[("Yeronym", 7)],
        data=MockFinishData()
    )
    assert "Match #1 finished!" in text_en
    assert "Team Orange 🟠 4:1 🟢 Team Green" in text_en
    assert "MVP:</b> Yeronym" in text_en
    assert "MVP Votes:" in text_en
    assert "Goals:" in text_en
    assert "Alex: 2" in text_en
