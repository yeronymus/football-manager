import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.db.models import Signup, User, Game, GameStatus, SignupStatus
from app.api.routers.dashboard import (
    toggle_signup_late,
    PlayerActivityOut,
    PlayerProfileDetailOut,
    PlayerHistoryGameOut,
)


@pytest.mark.asyncio
async def test_toggle_signup_late_endpoint():
    game = Game(id=10, chat_id=-1001, status=GameStatus.OPEN)
    signup = Signup(id=101, game_id=10, user_id=202, is_late=False)

    session = AsyncMock()
    session.get.side_effect = lambda model, ident: {
        (Signup, 101): signup,
        (Game, 10): game,
    }.get((model, ident))

    with patch("app.api.routers.dashboard.check_admin_rights", new=AsyncMock()):
        with patch("app.core.services.cache.cache_service.evict", new=AsyncMock()):
            with patch("app.bot.utils.evict_game_signups_cache"):
                # First toggle: False -> True
                res1 = await toggle_signup_late(signup_id=101, user_id=999, session=session)
                assert res1["status"] == "ok"
                assert res1["is_late"] is True
                assert signup.is_late is True

                # Second toggle: True -> False
                res2 = await toggle_signup_late(signup_id=101, user_id=999, session=session)
                assert res2["status"] == "ok"
                assert res2["is_late"] is False
                assert signup.is_late is False


def test_late_percentage_math():
    # User example: 10 games played, 8 lates -> 80%
    total_games = 10
    total_lates = 8
    pct = round((total_lates / total_games) * 100.0, 1)
    assert pct == 80.0

    p_out = PlayerActivityOut(
        user_id=123,
        full_name="Late Player",
        total_games=total_games,
        total_lates=total_lates,
        late_percentage=pct,
    )
    assert p_out.total_lates == 8
    assert p_out.late_percentage == 80.0

    # User with 0 games
    zero_games = 0
    zero_lates = 0
    zero_pct = round((zero_lates / zero_games) * 100.0, 1) if zero_games > 0 else 0.0
    assert zero_pct == 0.0


def test_player_history_game_out_is_late():
    game_hist = PlayerHistoryGameOut(
        game_id=5,
        date="03.11.2026",
        location="Arena Prague",
        status="open",
        is_late=True
    )
    assert game_hist.is_late is True
