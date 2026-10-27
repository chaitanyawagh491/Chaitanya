import time
from typing import Dict, Any, Optional

class DataCache:
    def __init__(self, expiry_seconds: int = 300):
        self.expiry = expiry_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            entry = self._store[key]
            if time.time() - entry["timestamp"] < self.expiry:
                return entry["value"]
            else:
                del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = {
            "value": value,
            "timestamp": time.time()
        }

    def clear(self) -> None:
        self._store.clear()
