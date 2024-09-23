import threading


class ExpiringCache:
    def __init__(self, expire_seconds=60):
        self.cache = set()
        self.expire_seconds = expire_seconds

    def set(self, value):
        if value in self.cache:
            return
        self.cache.add(value)
        threading.Timer(self.expire_seconds, self._expire, args=(value,)).start()

    def _expire(self, value):
        if value in self.cache:
            self.cache.remove(value)

    def get(self, value):
        if value in self.cache:
            return value
        return None

    def __str__(self):
        return str(self.cache)
