from datetime import datetime, timedelta
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
import urllib.parse

from fastapi import FastAPI
from pydantic import ValidationError
import pytest

from app.api.main import app as main_app
from app.api.routers import nss
from app.config import Settings, settings
from app.core.domain.dto import FinishGameDTO
from app.core.services.game_lifecycle import GameLifecycleService
from app.core.services.roster import RosterService
from app.core.services.stats import StatsService
from app.core.uow import UnitOfWork
from app.db.database import get_session
from app.db.models import (
    Chat,
    Game,
    GameStatus,
    PlayerProfile,
    Position,
    Signup,
    SignupStatus,
    Team,
    User,
    Vote,
)
from app.scheduler.tasks import calculate_mvp


async def _asgi_request(
    asgi_app,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    query_string: str = "",
) -> tuple[int, dict]:
    """Lightweight pure-ASGI request runner (exercises full FastAPI routing & Depends)."""
    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query_string.encode("ascii"),
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    sent_events = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent_events.append(message)

    await asgi_app(scope, receive, send)
    status_code = next(
        e["status"] for e in sent_events if e["type"] == "http.response.start"
    )
    body_bytes = b"".join(
        e.get("body", b"") for e in sent_events if e["type"] == "http.response.body"
    )
    return status_code, (json.loads(body_bytes.decode("utf-8")) if body_bytes else {})


def _make_tma_header(bot_token: str, user_id: int) -> str:
    data = {
        "auth_date": str(int(time.time())),
        "user": f'{{"id": {user_id}, "first_name": "Tester"}}',
    }
    check_str = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    return f"tma {urllib.parse.urlencode(data)}"


# ==============================================================================
# 1. Fail-Closed Config & Logical Redis DB Isolation
# ==============================================================================


def test_dev_auth_bypass_blocked_in_production_and_staging():
    with pytest.raises(ValidationError, match="DEV_AUTH_BYPASS"):
        Settings(
            _env_file=None,
            bot_token="123456:dummy",
            app_env="production",
            dev_auth_bypass=True,
        )

    with pytest.raises(ValidationError, match="DEV_AUTH_BYPASS"):
        Settings(
            _env_file=None,
            bot_token="123456:dummy",
            app_env="staging",
            dev_auth_bypass=True,
        )


def test_dev_auth_bypass_allowed_only_in_local_dev_and_redis_dbs_isolated():
    cfg = Settings(
        _env_file=None,
        bot_token="123456:dummy",
        app_env="local_dev",
        dev_auth_bypass=True,
        redis_host="redis.internal",
        redis_port=6379,
        redis_password="secret",
        redis_fsm_db=0,
        redis_cache_db=1,
        redis_stream_db=2,
    )
    assert cfg.dev_auth_bypass is True
    assert cfg.REDIS_URL.endswith("/0")
    assert cfg.REDIS_CACHE_URL.endswith("/1")
    assert cfg.REDIS_STREAM_URL.endswith("/2")


# ==============================================================================
# 2. /api/nss/* RBAC, DEV_AUTH_BYPASS & Error Handling
# ==============================================================================


@pytest.mark.asyncio
async def test_nss_routes_require_system_owner_and_preserve_400(session):
    test_app = FastAPI()
    test_app.include_router(nss.router, prefix="/api")
    test_app.dependency_overrides[get_session] = lambda: session

    bot_token = "123456:nss_test_secret_token"
    owner_id = 777001
    intruder_id = 888002

    with (
        patch.object(settings, "bot_token", bot_token),
        patch.object(settings, "system_owner_id", owner_id),
        patch.object(settings, "admin_ids", []),
        patch.object(settings, "app_env", "staging"),
        patch.object(settings, "dev_auth_bypass", False),
        patch("app.api.routers.nss.cache_service") as mock_cache,
    ):
        mock_cache.get_status.return_value = {"status": "connected", "db": 1}

        # 1) Unauthenticated -> 401
        code_unauth, _ = await _asgi_request(test_app, "GET", "/api/nss/cache/status")
        assert code_unauth == 401

        # 2) Valid TMA user who is NOT system owner -> 403
        code_forbidden, _ = await _asgi_request(
            test_app,
            "GET",
            "/api/nss/cache/status",
            headers={"Authorization": _make_tma_header(bot_token, intruder_id)},
        )
        assert code_forbidden == 403

        # 3) System owner -> 200
        owner_hdr = {"Authorization": _make_tma_header(bot_token, owner_id)}
        code_ok, body_ok = await _asgi_request(
            test_app, "GET", "/api/nss/cache/status", headers=owner_hdr
        )
        assert code_ok == 200
        assert body_ok["status"] == "connected"

        # 4) Missing both key and all_keys -> 400 (NOT swallowed as 500)
        code_bad, _ = await _asgi_request(
            test_app, "POST", "/api/nss/cache/evict", headers=owner_hdr
        )
        assert code_bad == 400


# ==============================================================================
# 3. Kubernetes Liveness & Readiness Probes
# ==============================================================================


@pytest.mark.asyncio
async def test_health_live_and_ready_probes():
    code_live, body_live = await _asgi_request(main_app, "GET", "/health/live")
    assert code_live == 200
    assert body_live["status"] == "ok"

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=1)
    mock_cm = MagicMock()
    mock_cm.return_value.__aenter__.return_value = mock_session
    mock_cm.return_value.__aexit__.return_value = False

    with (
        patch("app.db.database.async_session_maker", mock_cm),
        patch(
            "app.core.services.cache.cache_service.ping",
            new=AsyncMock(return_value=True),
        ),
    ):
        code_ready, body_ready = await _asgi_request(main_app, "GET", "/health/ready")
        assert code_ready == 200
        assert body_ready["checks"] == {"postgres": "up", "redis": "up"}

    # Simulate Redis outage -> must return HTTP 503
    with (
        patch("app.db.database.async_session_maker", mock_cm),
        patch(
            "app.core.services.cache.cache_service.ping",
            new=AsyncMock(side_effect=RuntimeError("Redis unreachable")),
        ),
    ):
        code_deg, body_deg = await _asgi_request(main_app, "GET", "/health/ready")
        assert code_deg == 503
        assert body_deg["status"] == "degraded"
        assert body_deg["checks"]["redis"] == "down"


# ==============================================================================
# 4. Domain Data-Integrity Fixes (Roster, Finish score_c, Delta Revert, MVP)
# ==============================================================================


@pytest.mark.asyncio
async def test_balance_teams_does_not_mutate_global_user_rating(session):
    chat = Chat(chat_id=-100501, title="Tenant Alpha")
    u1 = User(user_id=501, full_name="Alice", player_position=Position.ST, rating=100)
    u2 = User(user_id=502, full_name="Bob", player_position=Position.CB, rating=100)
    p1 = PlayerProfile(user_id=501, chat_id=-100501, rating=250)
    p2 = PlayerProfile(user_id=502, chat_id=-100501, rating=80)
    session.add_all([chat, u1, u2, p1, p2])
    await session.commit()

    game = Game(
        chat_id=-100501,
        created_by=501,
        date_time=datetime.now() + timedelta(days=1),
        location="Pitch 1",
        max_players=10,
        team_count=2,
        status=GameStatus.OPEN,
    )
    session.add(game)
    await session.commit()

    session.add_all(
        [
            Signup(game_id=game.id, user_id=501, status=SignupStatus.ACTIVE),
            Signup(game_id=game.id, user_id=502, status=SignupStatus.ACTIVE),
        ]
    )
    await session.commit()

    async with UnitOfWork(session=session) as uow:
        roster = RosterService(uow)
        await roster.balance_teams(game.id)
        await uow.commit()

    await session.refresh(u1)
    await session.refresh(u2)
    assert u1.rating == 100
    assert u2.rating == 100


@pytest.mark.asyncio
async def test_finish_game_persists_score_c_and_revert_preserves_later_deltas(session):
    chat = Chat(chat_id=-100601, title="Three Team League")
    u1 = User(user_id=601, full_name="P1", player_position=Position.ST, rating=100)
    u2 = User(user_id=602, full_name="P2", player_position=Position.CB, rating=100)
    u3 = User(user_id=603, full_name="P3", player_position=Position.GK, rating=100)
    session.add_all([chat, u1, u2, u3])
    await session.commit()

    g1 = Game(
        chat_id=-100601,
        created_by=601,
        date_time=datetime.now() - timedelta(days=2),
        location="Arena A",
        team_count=3,
        status=GameStatus.ACTIVE,
    )
    g2 = Game(
        chat_id=-100601,
        created_by=601,
        date_time=datetime.now() - timedelta(days=1),
        location="Arena B",
        team_count=2,
        status=GameStatus.ACTIVE,
    )
    session.add_all([g1, g2])
    await session.commit()

    session.add_all(
        [
            Signup(game_id=g1.id, user_id=601, status=SignupStatus.ACTIVE, team=Team.A),
            Signup(game_id=g1.id, user_id=602, status=SignupStatus.ACTIVE, team=Team.B),
            Signup(game_id=g1.id, user_id=603, status=SignupStatus.ACTIVE, team=Team.C),
            Signup(game_id=g2.id, user_id=603, status=SignupStatus.ACTIVE, team=Team.A),
            Signup(game_id=g2.id, user_id=602, status=SignupStatus.ACTIVE, team=Team.B),
        ]
    )
    await session.commit()

    mock_scheduler = MagicMock()

    async with UnitOfWork(session=session) as uow:
        stats = StatsService(uow.session)
        lifecycle = GameLifecycleService(uow, mock_scheduler, stats)
        await lifecycle.finish_game(
            FinishGameDTO(
                game_id=g1.id, score_a=3, score_b=1, score_c=7, winner_team=Team.C
            )
        )
        await uow.commit()

    await session.refresh(g1)
    await session.refresh(u3)
    assert g1.score_c == 7
    assert u3.rating == 110

    async with UnitOfWork(session=session) as uow:
        stats = StatsService(uow.session)
        lifecycle = GameLifecycleService(uow, mock_scheduler, stats)
        await lifecycle.finish_game(
            FinishGameDTO(game_id=g2.id, score_a=5, score_b=2, winner_team=Team.A)
        )
        await uow.commit()

    await session.refresh(u3)
    assert u3.rating == 120

    # Revert Game 1: u3 must lose ONLY Game 1's +10 delta (-> 110), NOT snap back to 100!
    stats_svc = StatsService(session)
    await stats_svc.revert_stats(g1.id)
    await session.commit()

    await session.refresh(u3)
    assert u3.rating == 110


@pytest.mark.asyncio
async def test_calculate_mvp_escapes_html_and_is_idempotent(session):
    chat = Chat(chat_id=-100701, title="Security Club")
    xss_user = User(
        user_id=701,
        full_name="<b>Evil & <script>alert(1)</script>",
        player_position=Position.ST,
        rating=100,
        stats_mvp=0,
    )
    voter = User(
        user_id=702,
        full_name="Normal Voter",
        player_position=Position.CM,
        rating=100,
        stats_mvp=0,
    )
    session.add_all([chat, xss_user, voter])
    await session.commit()

    game = Game(
        chat_id=-100701,
        created_by=702,
        date_time=datetime.now() - timedelta(hours=3),
        location="Pitch Sec",
        team_count=2,
        score_a=4,
        score_b=2,
        status=GameStatus.FINISHED,
    )
    session.add(game)
    await session.commit()

    session.add_all(
        [
            Signup(game_id=game.id, user_id=701, status=SignupStatus.ACTIVE, team=Team.A),
            Signup(game_id=game.id, user_id=702, status=SignupStatus.ACTIVE, team=Team.B),
            Vote(game_id=game.id, voter_id=702, target_id=701, vote_team=Team.A),
        ]
    )
    await session.commit()

    class MockSessionMaker:
        def __init__(self, s):
            self.s = s

        async def __aenter__(self):
            return self.s

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        def __call__(self):
            return self

    with (
        patch("app.scheduler.tasks.bot", new_callable=AsyncMock) as mock_bot,
        patch(
            "app.scheduler.tasks.async_session_maker",
            return_value=MockSessionMaker(session),
        ),
    ):
        await calculate_mvp(game.id)
        assert mock_bot.send_message.called
        sent_html = mock_bot.send_message.call_args[1]["text"]
        assert "<script>" not in sent_html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in sent_html
        assert "&amp;" in sent_html

        await session.refresh(xss_user)
        assert xss_user.stats_mvp == 1
        assert xss_user.rating == 105

        # Calling calculate_mvp a second time MUST be idempotent
        await calculate_mvp(game.id)
        await session.refresh(xss_user)
        assert xss_user.stats_mvp == 1
        assert xss_user.rating == 105
