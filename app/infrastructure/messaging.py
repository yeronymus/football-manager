from abc import ABC, abstractmethod
import asyncio
from collections import deque
import json
import logging
import os
import socket
import uuid
from typing import Deque, Optional, Set

import redis.asyncio as aioredis

from app.config import settings
from app.core.events import deserialize_event, event_bus

logger = logging.getLogger(__name__)

STREAM_NAME = "domain_events_stream"
GROUP_NAME = "platform_consumer_group"
CONSUMER_NAME = f"consumer-{socket.gethostname()}-{os.getpid()}"
STREAM_MAXLEN = 10000
STALE_IDLE_MS = 30000  # 30 seconds before unacknowledged PEL entries are reclaimed


def get_dynamic_consumer_name() -> str:
    """Returns a pod/process-unique consumer identity for multi-replica deployments."""
    return f"consumer-{socket.gethostname()}-{os.getpid()}"


class MessageBroker(ABC):
    """Interface for the asynchronous event stream broker."""

    @abstractmethod
    async def publish_message(
        self, topic: str, data: dict, idempotency_key: Optional[str] = None
    ) -> str:
        """Publishes a structured event message to the broker."""
        pass


class MessageProducer(MessageBroker):
    """Redis Streams implementation isolated onto REDIS_STREAM_DB with bounded MAXLEN."""

    def __init__(self):
        self.redis_url = settings.REDIS_STREAM_URL
        self._client: Optional[aioredis.Redis] = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def publish_message(
        self, topic: str, data: dict, idempotency_key: Optional[str] = None
    ) -> str:
        client = self._get_client()
        event_id = idempotency_key or str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "topic": topic,
            "data": json.dumps(data),
        }
        msg_id = await client.xadd(
            STREAM_NAME, payload, maxlen=STREAM_MAXLEN, approximate=True
        )
        logger.info(
            f"Published stream event topic={topic} event_id={event_id} id={msg_id}"
        )
        return msg_id


producer = MessageProducer()


class MessageConsumer:
    """
    Fault-tolerant Redis Streams Consumer Group worker (ADR-05):
    - Dynamic consumer name `consumer-{hostname}-{pid}` so multiple worker replicas never collide.
    - Idempotent deduplication window (`_processed_event_ids`) to guarantee at-most-once side effects
      over at-least-once stream delivery.
    - `reclaim_stale_messages()` using `XAUTOCLAIM` to recover unacknowledged PEL messages from crashed pods.
    - Dispatches deserialized domain events directly into `event_bus`.
    """

    def __init__(self, consumer_name: Optional[str] = None, max_dedup_size: int = 2048):
        self.redis_url = settings.REDIS_STREAM_URL
        self.consumer_name = consumer_name or get_dynamic_consumer_name()
        self._client: Optional[aioredis.Redis] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._max_dedup_size = max_dedup_size
        self._processed_order: Deque[str] = deque()
        self._processed_set: Set[str] = set()

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def _mark_processed(self, dedup_id: str) -> bool:
        """
        Records `dedup_id` in the bounded idempotency window.
        Returns True if this is the first time seeing `dedup_id`, or False if duplicate.
        """
        if dedup_id in self._processed_set:
            return False
        if len(self._processed_order) >= self._max_dedup_size:
            oldest = self._processed_order.popleft()
            self._processed_set.discard(oldest)
        self._processed_order.append(dedup_id)
        self._processed_set.add(dedup_id)
        return True

    async def initialize_group(self):
        """Creates the consumer group idempotently."""
        client = self._get_client()
        try:
            await client.xgroup_create(STREAM_NAME, GROUP_NAME, id="0", mkstream=True)
            logger.info(f"Consumer Group '{GROUP_NAME}' initialized.")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer Group '{GROUP_NAME}' already exists.")
            else:
                logger.error(f"Failed to create consumer group: {e}")

    async def reclaim_stale_messages(self, min_idle_ms: int = STALE_IDLE_MS) -> int:
        """
        Uses XAUTOCLAIM to reclaim pending entries idle for more than `min_idle_ms` from dead consumers,
        processes them idempotently, and XACKs them.
        """
        client = self._get_client()
        reclaimed_count = 0
        try:
            if not hasattr(client, "xautoclaim"):
                return 0
            result = await client.xautoclaim(
                name=STREAM_NAME,
                groupname=GROUP_NAME,
                consumername=self.consumer_name,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=20,
            )
            # redis-py xautoclaim returns (next_start_id, [(msg_id, payload), ...], deleted_ids)
            messages = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else []
            for msg_id, payload in messages:
                if not payload:
                    await client.xack(STREAM_NAME, GROUP_NAME, msg_id)
                    continue
                await self._handle_raw_entry(client, msg_id, payload)
                reclaimed_count += 1
        except Exception as e:
            logger.debug(f"XAUTOCLAIM check skipped or failed: {e}")
        return reclaimed_count

    async def _handle_raw_entry(
        self, client: aioredis.Redis, msg_id: str, payload: dict
    ) -> None:
        dedup_key = payload.get("event_id") or msg_id
        if self._mark_processed(dedup_key):
            topic = payload.get("topic", "")
            data_str = payload.get("data", "{}")
            data = json.loads(data_str) if isinstance(data_str, str) else dict(data_str)
            await self.process_event(topic, data)
        else:
            logger.debug(f"Skipped duplicate stream event dedup_key={dedup_key}")
        await client.xack(STREAM_NAME, GROUP_NAME, msg_id)

    async def start(self):
        self._running = True
        await self.initialize_group()
        self._task = asyncio.create_task(self._loop())
        logger.info(f"MessageConsumer started with consumer_id={self.consumer_name}.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MessageConsumer stopped.")

    async def _loop(self):
        client = self._get_client()
        tick = 0
        while self._running:
            try:
                tick += 1
                if tick % 15 == 1:
                    await self.reclaim_stale_messages()

                response = await client.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=self.consumer_name,
                    streams={STREAM_NAME: ">"},
                    count=10,
                    block=1000,
                )

                if not response:
                    continue

                for _, messages in response:
                    for msg_id, payload in messages:
                        await self._handle_raw_entry(client, msg_id, payload)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Consumer stream loop: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def process_event(self, topic: str, data: dict):
        logger.debug(f"Processing stream event topic={topic} payload={data}")
        domain_event = deserialize_event(topic, data)
        if domain_event is not None:
            await event_bus.publish(domain_event, from_stream=True)


consumer = MessageConsumer()
