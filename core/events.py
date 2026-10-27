from typing import Callable, Dict, List

class EventHub:
    _subscribers: Dict[str, List[Callable]] = {}

    @classmethod
    def subscribe(cls, event_type: str, callback: Callable) -> None:
        if event_type not in cls._subscribers:
            cls._subscribers[event_type] = []
        cls._subscribers[event_type].append(callback)

    @classmethod
    def unsubscribe(cls, event_type: str, callback: Callable) -> None:
        if event_type in cls._subscribers:
            try:
                cls._subscribers[event_type].remove(callback)
            except ValueError:
                pass

    @classmethod
    def publish(cls, event_type: str, *args, **kwargs) -> None:
        if event_type in cls._subscribers:
            for callback in cls._subscribers[event_type]:
                try:
                    callback(*args, **kwargs)
                except Exception:
                    pass
