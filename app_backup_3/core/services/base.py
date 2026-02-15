from app.core.events import EventBus, event_bus

class BaseService:
    def __init__(self, bus: EventBus = event_bus):
        self.bus = bus

    # Common service logic can go here
