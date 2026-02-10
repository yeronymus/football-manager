import asyncio
from typing import Callable, Any, Dict, List, Type
from dataclasses import dataclass

@dataclass
class Event:
    """Base class for all events."""
    pass

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
            # Execute handlers concurrently
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
            # In a real app, use logger
            print(f"Error handling event {event}: {e}")

# Global instance
event_bus = EventBus()
