import time
from typing import Any, Optional


class TTLCache:
    """
    Stale-while-revalidate in-memory cache.

    Each entry lives in two phases:
      fresh  (0 → ttl):               return immediately
      stale  (ttl → ttl + stale_extra): return old value so callers can still
                                        serve data while a background refresh runs
      dead   (> ttl + stale_extra):    return None — must fetch fresh

    Usage:
        val = cache.get(key)          # None if dead
        if cache.is_stale(key):
            asyncio.create_task(refresh(...))  # kick off background refresh
    """

    def __init__(self):
        self._store: dict[str, dict] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        now = time.time()
        if now <= entry["stale_until"]:
            return entry["value"]          # fresh OR stale — both usable
        del self._store[key]
        return None                        # fully expired

    def is_stale(self, key: str) -> bool:
        """True when data exists but is past its *fresh* window."""
        entry = self._store.get(key)
        if entry is None:
            return False
        return time.time() > entry["fresh_until"]

    def set(self, key: str, value: Any, ttl: int = 25, stale_extra: int = None):
        """
        ttl         – seconds data is fresh (no background refresh needed)
        stale_extra – extra seconds stale data is served while refreshing
                      defaults to 2×ttl
        """
        if stale_extra is None:
            stale_extra = ttl * 2
        now = time.time()
        self._store[key] = {
            "value":       value,
            "fresh_until": now + ttl,
            "stale_until": now + ttl + stale_extra,
            "set_at":      now,
        }

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

    def evict_expired(self):
        """Housekeeping — remove fully dead entries."""
        now = time.time()
        dead = [k for k, v in self._store.items() if now > v["stale_until"]]
        for k in dead:
            del self._store[k]


cache = TTLCache()
