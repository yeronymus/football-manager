"""
Real-time Server-Sent Events (SSE) Live-Stream & iCalendar (.ics) Feed Router.
- `GET /api/v1/games/{game_id}/stream`: Push-based SSE stream replacing 3-second client polling.
- `GET /api/v1/calendar/my-link`: Returns the authenticated player's personal `.ics` feed URL.
- `GET /api/v1/calendar/{token}.ics`: Serves RFC 5545 iCalendar feed for Google/Outlook/Apple Calendar.
"""

import asyncio
from datetime import datetime, timedelta
import json
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_user_from_header
from app.config import settings
from app.core.domain.ical import (
    CalendarMatchEvent,
    build_icalendar_feed,
    generate_calendar_token,
    verify_calendar_token,
)
from app.core.domain.tenant_policy import BillingMode, resolve_billing_mode
from app.core.events import (
    GameStateChangedEvent,
    GameUpdatedEvent,
    TeamsPublishedEvent,
    event_bus,
)
from app.core.services.cache import cache_service
from app.core.services.game_numbering import clean_location
from app.core.services.roster import PlayerJoinedEvent, PlayerLeftEvent
from app.db.database import get_session
from app.db.models import Chat, Game, GameStatus, Signup, SignupStatus

router = APIRouter(prefix="/v1", tags=["live-and-calendar"])

_game_versions: Dict[int, int] = {}
_game_conditions: Dict[int, asyncio.Condition] = {}


def _get_condition(game_id: int) -> asyncio.Condition:
    if game_id not in _game_conditions:
        _game_conditions[game_id] = asyncio.Condition()
    return _game_conditions[game_id]


async def _wake_local_subscribers(game_id: int) -> int:
    new_ver = _game_versions.get(game_id, 0) + 1
    _game_versions[game_id] = new_ver
    cond = _game_conditions.get(game_id)
    if cond is not None:
        async with cond:
            cond.notify_all()
    return new_ver


async def notify_game_live_subscribers(game_id: int, publish_redis: bool = True) -> int:
    """
    Bumps the live state version for `game_id`, wakes local SSE clients, and broadcasts
    across multi-worker / multi-pod replicas via Redis Pub/Sub (`live:game:{game_id}`).
    """
    new_ver = await _wake_local_subscribers(game_id)
    if publish_redis and getattr(cache_service, "redis", None) is not None:
        try:
            await cache_service.redis.publish(
                f"live:game:{game_id}",
                json.dumps({"type": "update", "game_id": game_id, "version": new_ver}),
            )
        except Exception:
            pass
    return new_ver


async def _on_domain_game_event(event) -> None:
    gid = getattr(event, "game_id", None)
    if gid is not None:
        await notify_game_live_subscribers(int(gid))


# Subscribe SSE broadcaster to domain events
for _ev_cls in (
    GameStateChangedEvent,
    GameUpdatedEvent,
    TeamsPublishedEvent,
    PlayerJoinedEvent,
    PlayerLeftEvent,
):
    event_bus.subscribe(_ev_cls, _on_domain_game_event)


@router.get("/games/{game_id}/stream")
async def stream_game_updates(
    game_id: int,
    max_events: int = Query(0, ge=0, le=100),
):
    """
    Server-Sent Events (SSE) stream for live match roster & score updates.
    Eliminates 3-second polling storms during flash-crowd registrations.
    """

    async def _event_generator():
        last_seen = _game_versions.get(game_id, 0)
        sent = 0
        # Send initial connected handshake
        yield f"data: {json.dumps({'type': 'connected', 'game_id': game_id, 'version': last_seen})}\n\n"
        if max_events == 1:
            return

        cond = _get_condition(game_id)
        pubsub = None
        pubsub_task = None

        async def _redis_pubsub_bridge():
            nonlocal pubsub
            try:
                redis_client = getattr(cache_service, "redis", None)
                if redis_client is None or not hasattr(redis_client, "pubsub"):
                    return
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(f"live:game:{game_id}")
                async for msg in pubsub.listen():
                    if msg and msg.get("type") == "message":
                        await _wake_local_subscribers(game_id)
            except Exception:
                return

        if getattr(cache_service, "redis", None) is not None:
            pubsub_task = asyncio.create_task(_redis_pubsub_bridge())

        try:
            while True:
                try:
                    async with cond:
                        await asyncio.wait_for(
                            cond.wait_for(lambda: _game_versions.get(game_id, 0) > last_seen),
                            timeout=15.0,
                        )
                    last_seen = _game_versions.get(game_id, 0)
                    payload = json.dumps(
                        {"type": "update", "game_id": game_id, "version": last_seen}
                    )
                    yield f"data: {payload}\n\n"
                    sent += 1
                    if max_events and sent >= max_events:
                        return
                except asyncio.TimeoutError:
                    # Emit SSE comment keepalive every 15s to prevent reverse-proxy idle disconnects
                    yield ": keepalive\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            if pubsub_task is not None:
                pubsub_task.cancel()
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(f"live:game:{game_id}")
                    await pubsub.close()
                except Exception:
                    pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/calendar/my-link")
async def get_my_calendar_link(
    user_id: int = Depends(get_user_from_header),
):
    """Returns the authenticated user's signed iCalendar (.ics) subscription link."""
    token = generate_calendar_token(user_id, settings.bot_token)
    return {
        "user_id": user_id,
        "token": token,
        "ics_path": f"/api/v1/calendar/{token}.ics",
    }


@router.get("/calendar/{token}.ics")
async def get_user_icalendar_feed(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Serves a live RFC 5545 iCalendar (.ics) feed containing all upcoming and recent matches
    for the user identified by the HMAC-signed `token`.
    """
    user_id = verify_calendar_token(token, settings.bot_token)
    if user_id is None:
        raise HTTPException(status_code=403, detail="Invalid calendar subscription token")

    cutoff = datetime.now() - timedelta(days=30)
    stmt = (
        select(Game, Signup, Chat)
        .join(Signup, Signup.game_id == Game.id)
        .outerjoin(Chat, Chat.chat_id == Game.chat_id)
        .where(
            Signup.user_id == user_id,
            Signup.status.in_([SignupStatus.ACTIVE, SignupStatus.RESERVE]),
            Game.status.in_([GameStatus.OPEN, GameStatus.ACTIVE]),
            Game.date_time >= cutoff,
        )
        .order_by(Game.date_time.asc())
        .limit(100)
    )
    res = await session.execute(stmt)
    rows = res.all()

    events = []
    for game, signup, chat in rows:
        b_mode = resolve_billing_mode(getattr(chat, "billing_mode", None) if chat else None)
        events.append(
            CalendarMatchEvent(
                game_id=game.id,
                sequence_number=getattr(game, "sequence_number", None) or game.id,
                title=(getattr(chat, "title", None) if chat else None) or "Sports Match",
                location=clean_location(getattr(game, "location", "")) or "Pitch",
                start_utc=game.date_time,
                duration_hours=float(getattr(game, "duration", 2.0) or 2.0),
                is_reserve=(signup.status == SignupStatus.RESERVE),
                price=int(getattr(game, "price", 0) or 0),
                currency=(getattr(chat, "currency", None) if chat else None) or "CZK",
                is_free_corporate=(b_mode == BillingMode.FREE_CORPORATE),
            )
        )

    ics_body = build_icalendar_feed(events)
    return Response(
        content=ics_body,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'inline; filename="schedule.ics"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )
