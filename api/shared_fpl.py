from __future__ import annotations

import threading
import time
from typing import Any

from lro_fpl import FPLClient, FPLError


class SharedFPLClient(FPLClient):
    """FPL client that suppresses duplicate concurrent GETs per cache key.

    The normal FPLClient has a TTL cache, but several tenant runtimes can miss
    that cache at the same instant after a cold start. Without single-flight,
    ten leagues opening together can all request bootstrap/fixtures/live before
    the first response has populated the cache. One request now does the work
    while the other callers wait for the same cached result. Short-lived shared
    failures prevent all waiters from retrying the same broken upstream at once.
    """

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._flight_lock = threading.Lock()
        self._flights: dict[str, threading.Event] = {}
        self._flight_errors: dict[str, tuple[str, float]] = {}
        self.flight_error_ttl = 3.0
        self.flight_waits = 0
        self.shared_failures = 0
        self.flight_timeouts = 0

    def _recent_error_locked(self, key: str) -> str | None:
        row = self._flight_errors.get(key)
        if row is None:
            return None
        message, created_at = row
        if time.monotonic() - created_at >= self.flight_error_ttl:
            self._flight_errors.pop(key, None)
            return None
        return message

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
            recent_error = self._recent_error_locked(key)
            if recent_error:
                self.shared_failures += 1
                raise FPLError(recent_error)
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
            completed = event.wait(timeout=max(5, int(self.timeout) + 5))
            cached = self._get_cached(key)
            if cached is not None:
                return cached
            with self._flight_lock:
                recent_error = self._recent_error_locked(key)
                if recent_error:
                    self.shared_failures += 1
                    raise FPLError(recent_error)
                if not completed:
                    self.flight_timeouts += 1
                    raise FPLError(f"FPL-kall ventet for lenge på delt forespørsel: {normalized}")
            # The creator completed but produced neither cache nor an explicit
            # error. Fail closed instead of letting every waiter stampede FPL.
            raise FPLError(f"FPL-kall ga ikke noe delt resultat: {normalized}")

        try:
            value = super().get_json(normalized, ttl=ttl, stale_if_error=stale_if_error, force=False)
            with self._flight_lock:
                self._flight_errors.pop(key, None)
            return value
        except Exception as exc:
            with self._flight_lock:
                self._flight_errors[key] = (str(exc)[:500], time.monotonic())
            raise
        finally:
            with self._flight_lock:
                waiter = self._flights.pop(key, None)
                if waiter is not None:
                    waiter.set()

    def diagnostics(self) -> dict[str, Any]:
        body = super().diagnostics()
        with self._flight_lock:
            for key in list(self._flight_errors):
                self._recent_error_locked(key)
            body["inflight_requests"] = len(self._flights)
            body["singleflight_waits"] = int(self.flight_waits)
            body["shared_failure_hits"] = int(self.shared_failures)
            body["flight_timeouts"] = int(self.flight_timeouts)
            body["recent_shared_errors"] = len(self._flight_errors)
        return body
