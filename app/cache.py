import time
from typing import Any, Optional

class TTLCache:
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self._store:
            value, expires = self._store[key]
            if time.time() < expires:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 25):
        self._store[key] = (value, time.time() + ttl)

    def clear(self):
        self._store.clear()

cache = TTLCache()
