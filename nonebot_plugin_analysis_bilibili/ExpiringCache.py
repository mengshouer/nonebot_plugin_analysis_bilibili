import time
from typing import Any, Dict, Optional


class ExpiringCache:
    def __init__(self, expire_seconds: float = 0):
        self.cache: Dict[Any, float] = {}
        self.expire_seconds = expire_seconds

    def _evict_expired(self) -> None:
        if self.expire_seconds <= 0:
            return
        now = time.monotonic()
        while self.cache:
            oldest_key = next(iter(self.cache))
            if self.cache[oldest_key] <= now:
                del self.cache[oldest_key]
            else:
                break

    def set(self, value: Any) -> None:
        self._evict_expired()
        if value in self.cache:
            return
        if self.expire_seconds <= 0:
            self.cache.clear()
            self.cache[value] = 0.0
        else:
            self.cache[value] = time.monotonic() + self.expire_seconds

    def get(self, value: Any) -> Optional[Any]:
        exp = self.cache.get(value)
        if exp is None:
            return None
        if self.expire_seconds > 0 and exp <= time.monotonic():
            del self.cache[value]
            return None
        return value

    def __str__(self) -> str:
        self._evict_expired()
        return str(set(self.cache.keys()))
