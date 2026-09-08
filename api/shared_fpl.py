from __future__ import annotations

import threading
from typing import Any

from lro_fpl import FPLClient


class SharedFPLClient(FPLClient):
    """FPL client that suppresses duplicate concurrent GETs per cache key.

    The normal FPLClient has a TTL cache, but several tenant runtimes can miss
    that cache at the same instant after a cold start. Without single-flight,
    ten leagues opening together can all request bootstrap/fixtures/live before
    the first response has populated the cache. One request now does the work
    while the other callers wait for the same cached result.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._flight_lock = threading.Lock()
        self._flights: dict[str, threading.Event] = {}
        self.flight_waits = 0

    def get_json(
        self,
        path: str,
        ttl: int = 300,
        stale_if_error: int = 1800,
        force: bool = False,
    ) -> Any:
        if force:
            return super().get_json(path, ttl=ttl, stale_if_error=stale_if_error, force=True)

        normalized = path if path.startswith("/") else f"/{path}"
        key = f"GET:{normalized}"
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        with self._flight_lock:
            event = self._flights.get(key)
            if event is None:
                event = threading.Event()
                self._flights[key] = event
                creator = True
            else:
                self.flight_waits += 1
                creator = False

        if not creator:
            # A FPL request normally has a much shorter timeout, but leave enough
            # room for the creator to fall back to stale cache on a slow upstream.
            event.wait(timeout=max(5, int(self.timeout) + 5))
            cached = self._get_cached(key)
            if cached is not None:
                return cached
            # Creator failed or timed out. Retry normally rather than returning a
            # fake empty payload; stale-if-error behavior still belongs to FPLClient.
            return super().get_json(normalized, ttl=ttl, stale_if_error=stale_if_error, force=False)

        try:
            return super().get_json(normalized, ttl=ttl, stale_if_error=stale_if_error, force=False)
        finally:
            with self._flight_lock:
                waiter = self._flights.pop(key, None)
                if waiter is not None:
                    waiter.set()

    def diagnostics(self) -> dict[str, Any]:
        body = super().diagnostics()
        with self._flight_lock:
            body["inflight_requests"] = len(self._flights)
            body["singleflight_waits"] = int(self.flight_waits)
        return body
