import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.bot.listeners import TelegramRenderDebouncer
from app.core.events import (
    EventBus,
    GameCreatedEvent,
    GameFinishedEvent,
    GameStateChangedEvent,
    deserialize_event,
    serialize_event,
)
from app.core.uow import UnitOfWork
from app.infrastructure.messaging import MessageConsumer, get_dynamic_consumer_name


@pytest.mark.asyncio
async def test_uow_post_commit_cache_eviction_and_rollback():
    """
    Verifies that UnitOfWork.defer_cache_eviction and defer_post_commit only execute
    after session.commit() succeeds, and are cleared if rollback() occurs.
    """
    mock_session = AsyncMock()
    callback_called = []

    with patch("app.core.services.cache.cache_service.evict", new_callable=AsyncMock) as mock_evict:
        async with UnitOfWork(session=mock_session) as uow:
            uow.defer_cache_eviction("game_details:77")
            uow.defer_cache_eviction("game_details:77")  # deduplicated
            uow.defer_post_commit(lambda: callback_called.append("committed"))
            assert mock_evict.await_count == 0
            await uow.commit()

        mock_session.commit.assert_awaited_once()
        mock_evict.assert_awaited_once_with("game_details:77")
        assert callback_called == ["committed"]

    # Rollback clears deferred cache keys and callbacks without executing them
    mock_session_rb = AsyncMock()
    rb_callbacks = []
    with patch("app.core.services.cache.cache_service.evict", new_callable=AsyncMock) as mock_evict_rb:
        async with UnitOfWork(session=mock_session_rb) as uow:
            uow.defer_cache_eviction("game_details:88")
            uow.defer_post_commit(lambda: rb_callbacks.append("should_not_run"))
            await uow.rollback()

        mock_evict_rb.assert_not_awaited()
        assert rb_callbacks == []


@pytest.mark.asyncio
async def test_event_bus_serialization_and_outbox_forwarder():
    """Verifies serialize_event, deserialize_event, and EventBus stream outbox forwarding."""
    ev = GameCreatedEvent(game_id=15, chat_id=-100555, creator_id=42, should_publish=True)
    topic, payload = serialize_event(ev)
    assert topic == "GameCreatedEvent"
    restored = deserialize_event(topic, payload)
    assert isinstance(restored, GameCreatedEvent)
    assert restored.game_id == 15
    assert restored.chat_id == -100555
    assert restored.should_publish is True

    fin_ev = GameFinishedEvent(game_id=15, chat_id=-100555, message_id=99, result_text="Won")
    f_topic, f_payload = serialize_event(fin_ev)
    assert isinstance(deserialize_event(f_topic, f_payload), GameFinishedEvent)

    # When no local subscribers are registered (e.g. API container with RUN_BOT=False),
    # EventBus forwards the event to the configured stream outbox forwarder.
    bus = EventBus()
    forwarder = AsyncMock()
    bus.set_stream_forwarder(forwarder)

    await bus.publish(GameStateChangedEvent(game_id=99))
    forwarder.assert_awaited_once_with("GameStateChangedEvent", {"game_id": 99})


@pytest.mark.asyncio
async def test_message_consumer_idempotency_and_xautoclaim():
    """
    Verifies dynamic consumer naming, idempotent deduplication of re-delivered messages,
    and XAUTOCLAIM recovery of stale PEL messages.
    """
    cname = get_dynamic_consumer_name()
    assert cname.startswith("consumer-")

    consumer = MessageConsumer(consumer_name="consumer-test-pod-1", max_dedup_size=10)
    mock_redis = AsyncMock()
    # Simulate XAUTOCLAIM returning the same event twice (re-delivery)
    raw_entry = {
        "event_id": "evt-unique-123",
        "topic": "GameStateChangedEvent",
        "data": '{"game_id": 501}',
    }
    mock_redis.xautoclaim = AsyncMock(
        return_value=(
            "0-0",
            [
                ("1700000000-0", raw_entry),
                ("1700000001-0", raw_entry),  # duplicate event_id
            ],
            [],
        )
    )
    consumer._client = mock_redis
    consumer.process_event = AsyncMock()

    reclaimed = await consumer.reclaim_stale_messages(min_idle_ms=5000)
    assert reclaimed == 2
    # Processed only once due to idempotency window, but XACKed twice
    consumer.process_event.assert_awaited_once_with("GameStateChangedEvent", {"game_id": 501})
    assert mock_redis.xack.await_count == 2


@pytest.mark.asyncio
async def test_telegram_render_debouncer_flash_crowd_coalescing():
    """
    Verifies that a burst of 15 rapid trigger() calls for the same game_id
    executes 1 leading-edge render immediately and coalesces the remaining 14 triggers
    into a single trailing-edge render after the cooldown window.
    """
    rendered_games = []

    async def fake_render(game_id: int):
        rendered_games.append(game_id)

    debouncer = TelegramRenderDebouncer(fake_render, cooldown_seconds=0.05)

    # Fire 15 rapid triggers for game 100
    for _ in range(15):
        await debouncer.trigger(100)

    # Immediately after the burst, only the 1st leading-edge render has executed
    assert len(rendered_games) == 1
    assert debouncer.coalesced_drops == 14

    # Wait for the trailing-edge flush
    await asyncio.sleep(0.08)
    assert len(rendered_games) == 2
