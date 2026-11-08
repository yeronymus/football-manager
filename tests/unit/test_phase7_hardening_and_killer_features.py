from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Response
import pytest

from app.api.routers.games import get_game_details
from app.api.routers.live import (
    get_my_calendar_link,
    get_user_icalendar_feed,
    notify_game_live_subscribers,
    stream_game_updates,
)
from app.api.routers.tenants import export_group_attendance_csv
from app.bot.listeners import TelegramRenderDebouncer
from app.core.domain.ical import (
    CalendarMatchEvent,
    build_icalendar_feed,
    generate_calendar_token,
    verify_calendar_token,
)
from app.db.models import (
    Chat,
    Game,
    GameStats,
    GameStatus,
    Position,
    Signup,
    SignupStatus,
    Team,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_games_router_enforces_bola_on_cached_finished_game():
    """
    Verifies that GET /api/game/{id} checks verify_tenant_membership even on a Redis
    Cache Hit when the match is not OPEN, blocking cross-tenant IDOR probing.
    """
    session = AsyncMock()
    empty_res = MagicMock()
    empty_res.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=empty_res)

    cached_payload = {
        "id": 99,
        "chat_id": -100777888,
        "status": GameStatus.FINISHED.value,
        "location": "Private Corporate Arena",
    }
    with patch(
        "app.api.routers.games.cache_service.get",
        new_callable=AsyncMock,
        return_value=cached_payload,
    ):
        with pytest.raises(HTTPException) as exc:
            await get_game_details(
                game_id=99,
                response=Response(),
                user_id=999111,  # Unaffiliated outsider
                session=session,
            )
        assert exc.value.status_code == 403


def test_ical_token_and_rfc5545_feed_generation():
    """
    Verifies stateless HMAC calendar token signing/verification and RFC 5545
    VCALENDAR + VEVENT + VALARM generation for ACTIVE and RESERVE matches.
    """
    secret = "test-calendar-secret-key"
    token = generate_calendar_token(424242, secret)
    assert verify_calendar_token(token, secret) == 424242
    assert verify_calendar_token("424242.forgedsignature", secret) is None
    assert verify_calendar_token("malformed", secret) is None

    events = [
        CalendarMatchEvent(
            game_id=10,
            sequence_number=5,
            title="Acme Corp Futsal",
            location="Arena Sparta",
            start_utc=datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc),
            duration_hours=1.5,
            is_reserve=False,
            is_free_corporate=True,
        ),
        CalendarMatchEvent(
            game_id=11,
            sequence_number=6,
            title="Acme Corp Futsal",
            location="Arena Sparta",
            start_utc=datetime(2026, 11, 22, 18, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            is_reserve=True,
            price=150,
            currency="CZK",
        ),
    ]
    ics = build_icalendar_feed(events, calendar_name="Acme Sports")
    assert "BEGIN:VCALENDAR\r\n" in ics
    assert "SUMMARY:Acme Corp Futsal #5\r\n" in ics
    assert "STATUS:CONFIRMED\r\n" in ics
    assert "SUMMARY:[RESERVE] Acme Corp Futsal #6\r\n" in ics
    assert "STATUS:TENTATIVE\r\n" in ics
    assert "TRIGGER:-PT2H\r\n" in ics
    assert "Covered by Organization" in ics


@pytest.mark.asyncio
async def test_ical_endpoint_and_my_link():
    """Verifies /api/v1/calendar/my-link and /api/v1/calendar/{token}.ics endpoints."""
    link_info = await get_my_calendar_link(user_id=7001)
    assert link_info["user_id"] == 7001
    token = link_info["token"]

    session = AsyncMock()
    game = Game(
        id=55,
        sequence_number=12,
        chat_id=-100500,
        location="Corporate Pitch",
        date_time=datetime(2026, 12, 1, 19, 0, tzinfo=timezone.utc),
        duration=2.0,
        price=0,
        status=GameStatus.OPEN,
    )
    signup = Signup(game_id=55, user_id=7001, status=SignupStatus.ACTIVE)
    chat = Chat(chat_id=-100500, title="TechCorp FC", billing_mode="free_corporate")

    mock_res = MagicMock()
    mock_res.all.return_value = [(game, signup, chat)]
    session.execute = AsyncMock(return_value=mock_res)

    resp = await get_user_icalendar_feed(token=token, session=session)
    assert resp.media_type == "text/calendar; charset=utf-8"
    body = resp.body.decode("utf-8")
    assert "TechCorp FC #12" in body
    assert "STATUS:CONFIRMED" in body


@pytest.mark.asyncio
async def test_sse_live_stream_handshake_and_notify():
    """Verifies SSE /api/v1/games/{id}/stream initial handshake and version increment."""
    ver_before = await notify_game_live_subscribers(321)
    assert ver_before >= 1

    stream_resp = await stream_game_updates(game_id=321, max_events=1)
    assert stream_resp.media_type == "text/event-stream"
    assert stream_resp.headers.get("X-Accel-Buffering") == "no"

    chunks = []
    async for chunk in stream_resp.body_iterator:
        chunks.append(chunk)
    assert len(chunks) == 1
    assert '"type": "connected"' in chunks[0]
    assert '"game_id": 321' in chunks[0]


@pytest.mark.asyncio
async def test_b2b_hr_attendance_csv_export():
    """Verifies /api/dashboard/groups/{chat_id}/attendance.csv exports valid UTF-8 BOM CSV."""
    session = AsyncMock()
    chat = Chat(
        chat_id=-100888,
        title="Enterprise Group",
        currency="EUR",
        billing_mode="free_corporate",
    )
    session.get = AsyncMock(return_value=chat)

    game = Game(
        id=1,
        sequence_number=1,
        chat_id=-100888,
        date_time=datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc),
        location="Pitch A",
        price=0,
    )
    user = User(
        user_id=101,
        full_name="Alice Employee",
        username="alice_corp",
        player_position=Position.CM,
    )
    signup = Signup(
        id=1,
        game_id=1,
        user_id=101,
        status=SignupStatus.ACTIVE,
        team=Team.A,
        is_paid=True,
        is_late=False,
    )
    stats = GameStats(game_id=1, user_id=101, goals=2, assists=1, is_mvp=True)

    rows_res = MagicMock()
    rows_res.all.return_value = [(game, signup, user, stats)]
    session.execute = AsyncMock(return_value=rows_res)

    with patch("app.api.routers.dashboard.check_admin_rights", new_callable=AsyncMock):
        resp = await export_group_attendance_csv(
            chat_id=-100888, user_id=1, session=session
        )

    text = resp.body.decode("utf-8-sig")
    assert "game_id,sequence_number,date_utc,location,user_id,full_name" in text
    assert "Alice Employee,alice_corp,active,A,True,False,2,1,True,0,EUR,free_corporate" in text


@pytest.mark.asyncio
async def test_distributed_redis_debouncer_slot_lock():
    """Verifies TelegramRenderDebouncer coalesces when another worker holds the Redis NX lock."""
    rendered = []

    async def fake_render(gid: int):
        rendered.append(gid)

    mock_redis = AsyncMock()
    # Simulate another pod already holding render_lock:game:555 (SET NX returns False)
    mock_redis.set = AsyncMock(return_value=False)

    debouncer = TelegramRenderDebouncer(
        fake_render, cooldown_seconds=0.05, redis_client=mock_redis
    )
    await debouncer.trigger(555)
    # Did not execute leading-edge render because another pod holds the Redis lock
    assert rendered == []
    assert debouncer.coalesced_drops == 1


def test_frontend_xss_and_url_token_leak_invariants():
    """
    Static security gate across app/web/ and deploy/k8s/:
    - Zero `?initData=` or `&initData=` leaks in fetch() or iframe URLs.
    - `admin.js` escapes `p.full_name`.
    - `deploy/k8s/deployment.yaml` mounts `/tmp` emptyDir and probes `/health/ready`.
    """
    web_dir = REPO_ROOT / "app" / "web"
    for fpath in web_dir.rglob("*"):
        if fpath.is_file() and fpath.suffix in {".html", ".js"}:
            content = fpath.read_text(encoding="utf-8")
            assert "initData=${encodeURIComponent" not in content, (
                f"Found initData URL query leak in {fpath.name}"
            )
            assert "'/api/chats?initData='" not in content, (
                f"Found initData URL query leak in {fpath.name}"
            )

    admin_js = (web_dir / "js" / "admin.js").read_text(encoding="utf-8")
    assert "${escapeHtml(p.full_name)}" in admin_js

    k8s_deploy = (REPO_ROOT / "deploy" / "k8s" / "deployment.yaml").read_text(
        encoding="utf-8"
    )
    assert "mountPath: /tmp" in k8s_deploy
    assert "path: /health/ready" in k8s_deploy
    assert (REPO_ROOT / "deploy" / "k8s" / "job-migration.yaml").is_file()
