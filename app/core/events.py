import asyncio
from dataclasses import dataclass, field
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base class for all domain events."""

    pass


# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass
class GameStateChangedEvent(Event):
    """
    Generic: fired after any state-changing operation.
    Listeners refresh dashboard + public message.
    """

    game_id: int


@dataclass
class GameMessageNeedsUpdateEvent(Event):
    """Only the public group/channel message needs a refresh."""

    game_id: int


@dataclass
class GameCreatedEvent(Event):
    """Fired after a new game is created and committed."""

    game_id: int
    chat_id: int
    creator_id: int
    should_publish: bool = False
    publish_at: object = None  # Optional[datetime], kept as object to avoid circular


@dataclass
class GameFinishedEvent(Event):
    """Fired after a game is finished. Listeners send the result summary to chat."""

    game_id: int
    chat_id: int
    message_id: int | None = None
    result_text: str = ""


@dataclass
class GameUpdatedEvent(Event):
    """Fired after game details are updated. Listeners edit the public message."""

    game_id: int
    changes: list = field(default_factory=list)


@dataclass
class TeamsPublishedEvent(Event):
    """Fired after teams/rosters are published. Listeners send/edit team message."""

    game_id: int


def serialize_event(event: Event) -> Tuple[str, Dict[str, Any]]:
    """Serializes a domain Event into a `(topic, payload_dict)` pair for Redis Streams outbox transport."""
    topic = type(event).__name__
    if isinstance(event, GameStateChangedEvent):
        return topic, {"game_id": event.game_id}
    if isinstance(event, GameMessageNeedsUpdateEvent):
        return topic, {"game_id": event.game_id}
    if isinstance(event, GameCreatedEvent):
        return topic, {
            "game_id": event.game_id,
            "chat_id": event.chat_id,
            "creator_id": event.creator_id,
            "should_publish": bool(event.should_publish),
        }
    if isinstance(event, GameFinishedEvent):
        return topic, {
            "game_id": event.game_id,
            "chat_id": event.chat_id,
            "message_id": event.message_id,
            "result_text": event.result_text or "",
        }
    if isinstance(event, GameUpdatedEvent):
        return topic, {
            "game_id": event.game_id,
            "changes": list(event.changes or []),
        }
    if isinstance(event, TeamsPublishedEvent):
        return topic, {"game_id": event.game_id}

    # Support PlayerJoinedEvent / PlayerLeftEvent defined in app.core.services.roster
    payload: Dict[str, Any] = {}
    for k, v in vars(event).items():
        if k == "promoted_user" and v is not None:
            payload["promoted_user_id"] = getattr(v, "user_id", None)
        elif isinstance(v, (int, float, str, bool, list, dict)) or v is None:
            payload[k] = v
    return topic, payload


def deserialize_event(topic: str, data: Dict[str, Any]) -> Optional[Event]:
    """Reconstructs a domain Event from its serialized `(topic, data)` representation."""
    if topic == "GameStateChangedEvent":
        return GameStateChangedEvent(game_id=int(data["game_id"]))
    if topic == "GameMessageNeedsUpdateEvent":
        return GameMessageNeedsUpdateEvent(game_id=int(data["game_id"]))
    if topic == "GameCreatedEvent":
        return GameCreatedEvent(
            game_id=int(data["game_id"]),
            chat_id=int(data["chat_id"]),
            creator_id=int(data.get("creator_id", 0)),
            should_publish=bool(data.get("should_publish", False)),
        )
    if topic == "GameFinishedEvent":
        return GameFinishedEvent(
            game_id=int(data["game_id"]),
            chat_id=int(data["chat_id"]),
            message_id=data.get("message_id"),
            result_text=str(data.get("result_text", "")),
        )
    if topic == "GameUpdatedEvent":
        return GameUpdatedEvent(
            game_id=int(data["game_id"]),
            changes=list(data.get("changes", [])),
        )
    if topic == "TeamsPublishedEvent":
        return TeamsPublishedEvent(game_id=int(data["game_id"]))
    if topic in ("PlayerJoinedEvent", "PlayerLeftEvent") and "game_id" in data:
        return GameStateChangedEvent(game_id=int(data["game_id"]))
    return None


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------


class EventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Callable[[Event], Any]]] = {}
        self._stream_forwarder: Optional[Callable[[str, Dict[str, Any]], Any]] = None

    def set_stream_forwarder(
        self, forwarder: Optional[Callable[[str, Dict[str, Any]], Any]]
    ) -> None:
        """
        Configures an optional outbox forwarder (e.g. `MessageProducer.publish_message`)
        used when API pods have no local bot listeners subscribed (`RUN_BOT=False`).
        """
        self._stream_forwarder = forwarder

    def subscribe(self, event_type: Type[Event], handler: Callable[[Event], Any]):
        """Subscribe a handler to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[Event], handler: Callable[[Event], Any]):
        """Unsubscribe a handler from an event type."""
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event, *, from_stream: bool = False):
        """
        Publish an event to all local subscribers.
        If no local subscribers exist (or stream forwarding is configured) and `from_stream=False`,
        forwards the serialized event to the distributed Redis Stream outbox.
        """
        event_type = type(event)
        handlers = self._subscribers.get(event_type, [])
        if handlers:
            await asyncio.gather(*[self._safe_invoke(h, event) for h in handlers])
        elif self._stream_forwarder is not None and not from_stream:
            topic, payload = serialize_event(event)
            try:
                res = self._stream_forwarder(topic, payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning(f"Failed to forward event {topic} to stream outbox: {e}")

    async def _safe_invoke(self, handler: Callable[[Event], Any], event: Event):
        """Execute handler and log errors instead of crashing."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(
                f"Error handling event {type(event).__name__}: {e}", exc_info=True
            )


# Global singleton
event_bus = EventBus()
