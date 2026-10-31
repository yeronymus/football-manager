import pytest
import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from app.db.models import User, Chat, PlayerCard, Position, Game, GameStatus, Signup, SignupStatus
from app.core.repositories.user_repository import UserRepository
from app.core.services.roster import RosterService
from app.api.routers.dashboard import issue_player_card, revoke_player_card, IssueCardIn, get_group_player_detail, get_group_analytics
from app.api.routers.users import get_my_profile
from app.bot.middlewares import DbSessionMiddleware


@pytest.mark.asyncio
async def test_user_repository_card_lifecycle(session):
    # Setup chat and user
    chat = Chat(chat_id=-100123, title="Test FC")
    user = User(user_id=999, full_name="Sanctioned Player", username="player999", player_position=Position.MID)
    session.add(chat)
    session.add(user)
    await session.commit()

    repo = UserRepository(session)

    # 1. No card initially
    card = await repo.get_active_card(999, -100123)
    assert card is None

    # 2. Issue Yellow card
    y_card = await repo.issue_card(999, -100123, "YELLOW", weeks=4, reason="Late arrival", issued_by=1)
    await session.commit()
    assert y_card.card_type == "YELLOW"
    assert y_card.weeks == 4
    assert y_card.reason == "Late arrival"
    assert y_card.is_active is True

    fetched = await repo.get_active_card(999, -100123)
    assert fetched is not None
    assert fetched.id == y_card.id
    assert fetched.card_type == "YELLOW"

    # 3. Issue Red card -> deactivates Yellow card
    r_card = await repo.issue_card(999, -100123, "RED", weeks=2, reason="Violent conduct", issued_by=1)
    await session.commit()
    assert r_card.card_type == "RED"
    assert r_card.weeks == 2

    # Check that previous yellow card is deactivated
    await session.refresh(y_card)
    assert y_card.is_active is False

    active_now = await repo.get_active_card(999, -100123)
    assert active_now is not None
    assert active_now.id == r_card.id
    assert active_now.card_type == "RED"

    # 4. Revoke card
    revoked = await repo.revoke_card(999, -100123)
    await session.commit()
    assert revoked is True

    card_after_revoke = await repo.get_active_card(999, -100123)
    assert card_after_revoke is None


@pytest.mark.asyncio
async def test_roster_blocks_player_with_active_red_card():
    class MockGameRepo:
        async def get_with_lock(self, game_id):
            return Game(id=game_id, chat_id=-1001, status=GameStatus.OPEN, max_players=20, date_time=datetime.datetime.now() + datetime.timedelta(days=1))
        async def get_signup(self, game_id, user_id):
            return None
        async def get_active_signups_count(self, game_id):
            return 5
        def create_signup(self, gid, uid, status):
            return Signup(game_id=gid, user_id=uid, status=status)

    class MockUserRepo:
        def __init__(self, card):
            self._card = card
        async def get_active_card(self, user_id, chat_id):
            return self._card

    class MockUOW:
        def __init__(self, card):
            self.game_repo = MockGameRepo()
            self.user_repo = MockUserRepo(card)

    user = User(user_id=42, full_name="Banned Player", player_position=Position.FWD)
    exp = datetime.datetime.now() + datetime.timedelta(days=14)

    # 1. Red Card active -> Join blocked
    red_card = PlayerCard(id=1, user_id=42, chat_id=-1001, card_type="RED", weeks=2, reason="Foul language", expires_at=exp, is_active=True)
    service_blocked = RosterService(MockUOW(red_card))
    res_blocked = await service_blocked.join_player(game_id=1, user=user)

    assert res_blocked.success is False
    assert "красная карточка" in res_blocked.message.lower()
    assert "Foul language" in res_blocked.message

    # 2. Yellow Card active -> Join allowed
    yellow_card = PlayerCard(id=2, user_id=42, chat_id=-1001, card_type="YELLOW", weeks=4, expires_at=exp, is_active=True)
    service_allowed = RosterService(MockUOW(yellow_card))
    res_yellow = await service_allowed.join_player(game_id=1, user=user)
    assert res_yellow.success is True

    # 3. Red card with ignore_limit=True (Admin bypass)
    res_forced = await service_blocked.join_player(game_id=1, user=user, ignore_limit=True)
    assert res_forced.success is True

    # 4. English user gets English blocking notice
    user_en = User(user_id=43, full_name="English Player", player_position=Position.FWD, language="en")
    res_en = await service_blocked.join_player(game_id=1, user=user_en)
    assert res_en.success is False
    assert "red card" in res_en.message.lower()
    assert "Registration closed" in res_en.message


@pytest.mark.asyncio
@patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock)
@patch("app.bot.instance.bot")
async def test_dashboard_issue_and_revoke_endpoints(mock_bot, mock_check_admin, session):
    mock_bot.send_message = AsyncMock()

    from app.db.models import PlayerProfile
    chat = Chat(chat_id=-100555, title="Champions Group")
    admin = User(user_id=100, full_name="Head Admin", player_position=Position.GK)
    player = User(user_id=200, full_name="Offender Player", username="offender", player_position=Position.DEF)
    prof = PlayerProfile(user_id=200, chat_id=-100555, rating=105, games_played=1)
    session.add_all([chat, admin, player, prof])
    await session.commit()

    # Issue Red Card
    issue_data = IssueCardIn(card_type="RED", weeks=3, reason="Unsportsmanlike conduct")
    res_issue = await issue_player_card(
        chat_id=-100555,
        target_user_id=200,
        data=issue_data,
        user_id=100,
        session=session
    )

    assert res_issue["status"] == "ok"
    assert res_issue["card"]["card_type"] == "RED"
    assert res_issue["card"]["weeks"] == 3
    assert res_issue["card"]["reason"] == "Unsportsmanlike conduct"
    mock_bot.send_message.assert_awaited()
    sent_text = mock_bot.send_message.call_args[0][1]
    assert "Красная карточка" in sent_text or "Red Card" in sent_text
    assert "Champions Group" in sent_text

    # Detail endpoint returns active_card
    detail = await get_group_player_detail(
        chat_id=-100555,
        target_user_id=200,
        user_id=100,
        session=session
    )
    assert detail.active_card is not None
    assert detail.active_card.card_type == "RED"
    assert detail.active_card.weeks == 3

    # Analytics returns active_card_type
    analytics = await get_group_analytics(
        chat_id=-100555,
        user_id=100,
        session=session
    )
    matching_p = next((p for p in analytics.players if p.user_id == 200), None)
    assert matching_p is not None
    assert matching_p.active_card_type == "RED"

    # Revoke Card
    mock_bot.send_message.reset_mock()
    res_revoke = await revoke_player_card(
        chat_id=-100555,
        target_user_id=200,
        user_id=100,
        session=session
    )
    assert res_revoke["status"] == "ok"
    mock_bot.send_message.assert_awaited()
    revoke_text = mock_bot.send_message.call_args[0][1]
    assert "снята" in revoke_text.lower() or "lifted" in revoke_text.lower()


@pytest.mark.asyncio
async def test_get_my_profile_returns_active_card(session):
    chat = Chat(chat_id=-100777, title="My Group")
    user = User(user_id=300, full_name="Carded User", username="carded", player_position=Position.CAM)
    now = datetime.datetime.now(datetime.timezone.utc)
    card = PlayerCard(
        user_id=300,
        chat_id=-100777,
        card_type="YELLOW",
        weeks=4,
        reason="Warning for missed game",
        issued_at=now,
        expires_at=now + datetime.timedelta(weeks=4),
        is_active=True
    )
    session.add_all([chat, user, card])
    await session.commit()

    prof = await get_my_profile(
        chat_id=-100777,
        user_id=300,
        authorization=None,
        session=session
    )

    assert prof["active_card"] is not None
    assert prof["active_card"]["card_type"] == "YELLOW"
    assert prof["active_card"]["weeks"] == 4
    assert prof["active_card"]["reason"] == "Warning for missed game"
    assert prof["active_card"]["days_left"] > 20


@pytest.mark.asyncio
async def test_auto_sync_username_on_bot_interaction(session):
    user = User(user_id=400, username="old_handle", full_name="Adok Old", player_position=Position.ST)
    session.add(user)
    await session.commit()

    # Session pool returning our test session
    session_pool = MagicMock()
    session_pool.return_value.__aenter__ = AsyncMock(return_value=session)
    session_pool.return_value.__aexit__ = AsyncMock(return_value=None)

    middleware = DbSessionMiddleware(session_pool)

    # Mock Telegram event with new username
    tg_user = MagicMock()
    tg_user.id = 400
    tg_user.username = "adok0625"
    tg_user.full_name = "Adok New"
    tg_user.is_bot = False

    event = MagicMock()
    event.from_user = tg_user

    async def dummy_handler(ev, data):
        return "handled"

    res = await middleware(dummy_handler, event, {})
    assert res == "handled"

    # User in DB must now have updated username and full_name
    await session.refresh(user)
    assert user.username == "adok0625"
    assert user.full_name == "Adok New"
