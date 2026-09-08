from __future__ import annotations

from typing import Any

from api.platform_store import platform_store
from api.push import PushStore
from api.push_monitor import PushMonitor


CURSOR_KEY = "push:fpl-live:v1"


class DurablePushMonitor(PushMonitor):
    """PushMonitor with restart-safe FPL event cursor when persistence exists."""

    def __init__(self, store: PushStore):
        super().__init__(store)
        self._cursor_backend = platform_store.backend
        self._cursor_restored = False
        try:
            payload = platform_store.get_cursor(CURSOR_KEY) or {}
            event_id = int(payload.get("event_id") or 0)
            raw_stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
            stats: dict[int, dict[str, int]] = {}
            for raw_element, values in raw_stats.items():
                try:
                    element = int(raw_element)
                except Exception:
                    continue
                if not isinstance(values, dict):
                    continue
                stats[element] = {str(key): int(value or 0) for key, value in values.items()}
            if event_id > 0 and stats:
                self._last_event_id = event_id
                self._stats = stats
                self._cursor_restored = True
        except Exception:
            pass

    def poll_once(self) -> dict[str, Any]:
        result = super().poll_once()
        try:
            if self._last_event_id and self._stats:
                platform_store.set_cursor(
                    CURSOR_KEY,
                    {
                        "event_id": self._last_event_id,
                        "stats": {str(element): values for element, values in self._stats.items()},
                    },
                )
        except Exception:
            pass
        result = dict(result)
        result["cursor_backend"] = platform_store.backend
        result["cursor_durable"] = platform_store.durable
        result["cursor_restored"] = self._cursor_restored
        return result

    def status(self) -> dict[str, Any]:
        body = super().status()
        body["cursor_backend"] = self._cursor_backend
        body["cursor_durable"] = platform_store.durable
        body["cursor_restored"] = self._cursor_restored
        return body
