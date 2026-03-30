import asyncio
from typing import Callable, Any, Dict, List, Type
from dataclasses import dataclass

@dataclass
class Event:
    """Base class for all events."""
    pass

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------

@dataclass
class GameStateChangedEvent(Event):
    """
    Fired by the API after any state-changing operation
    (create, update, balance, finish, add_player, etc.).

    The bot layer listens to this and refreshes the Telegram UI.
    The API layer does NOT know about the bot — it only publishes this event.
    """
    game_id: int

@dataclass
class GameMessageNeedsUpdateEvent(Event):
    """
    Fired when only the public group/channel message needs a refresh
    (e.g. player joined/left), without a full dashboard update.
    """
    game_id: int

# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

class EventBus:
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Callable[[Event], Any]]] = {}

    def subscribe(self, event_type: Type[Event], handler: Callable[[Event], Any]):
        """Subscribe a handler to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[Event], handler: Callable[[Event], Any]):
        """Unsubscribe a handler from an event type."""
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event):
        """Publish an event to all subscribers."""
        event_type = type(event)
        if event_type in self._subscribers:
            handlers = self._subscribers[event_type]
            await asyncio.gather(*[self._safe_invoke(h, event) for h in handlers])

    async def _safe_invoke(self, handler: Callable[[Event], Any], event: Event):
        """Execute handler and log errors instead of crashing."""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"Error handling event {type(event).__name__}: {e}", exc_info=True
            )

# Global singleton
event_bus = EventBus()
