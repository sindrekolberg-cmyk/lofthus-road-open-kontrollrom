from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Hashable


@dataclass
class CacheEntry:
    value: Any
    expires_at: float
    created_at: float


class SingleFlightTTLCache:
    """Tiny process-local cache with duplicate-work suppression.

    Expensive analysis endpoints are easy to hammer accidentally from mobile
    rerenders, pull-to-refresh and several users in the same league. One builder
    runs per key; concurrent callers wait for that result instead of recomputing
    the same Monte Carlo / projection workload.
    """

    def __init__(self, max_items: int = 256):
        self.max_items = max(16, int(max_items))
        self._lock = threading.RLock()
        self._entries: OrderedDict[Hashable, CacheEntry] = OrderedDict()
        self._inflight: dict[Hashable, threading.Event] = {}
        self._errors: dict[Hashable, BaseException] = {}
        self.hits = 0
        self.misses = 0
        self.waits = 0
        self.builds = 0
        self.evictions = 0

    def _prune(self) -> None:
        now = time.monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
        while len(self._entries) > self.max_items:
            self._entries.popitem(last=False)
            self.evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._errors.clear()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            self._prune()
            entry = self._entries.get(key)
            if entry is None:
                self.misses += 1
                return None
            self.hits += 1
            self._entries.move_to_end(key)
            return deepcopy(entry.value)

    def set(self, key: Hashable, value: Any, ttl_seconds: float) -> Any:
        ttl = max(1.0, float(ttl_seconds))
        now = time.monotonic()
        with self._lock:
            self._entries[key] = CacheEntry(deepcopy(value), now + ttl, now)
            self._entries.move_to_end(key)
            self._prune()
        return value

    def get_or_build(self, key: Hashable, builder: Callable[[], Any], ttl_seconds: float) -> Any:
        with self._lock:
            self._prune()
            entry = self._entries.get(key)
            if entry is not None:
                self.hits += 1
                self._entries.move_to_end(key)
                return deepcopy(entry.value)

            event = self._inflight.get(key)
            if event is None:
                event = threading.Event()
                self._inflight[key] = event
                self._errors.pop(key, None)
                creator = True
                self.misses += 1
                self.builds += 1
            else:
                creator = False
                self.waits += 1

        if not creator:
            event.wait(timeout=90)
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and entry.expires_at > time.monotonic():
                    self.hits += 1
                    self._entries.move_to_end(key)
                    return deepcopy(entry.value)
                error = self._errors.get(key)
            if error is not None:
                raise RuntimeError(str(error)) from error
            # The original builder may have died or timed out. Build once here
            # rather than leaving this caller permanently stuck.
            return self.get_or_build((key, "retry", time.monotonic_ns()), builder, ttl_seconds)

        try:
            value = builder()
            self.set(key, value, ttl_seconds)
            return value
        except BaseException as exc:
            with self._lock:
                self._errors[key] = exc
            raise
        finally:
            with self._lock:
                waiter = self._inflight.pop(key, None)
                if waiter is not None:
                    waiter.set()

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            self._prune()
            return {
                "items": len(self._entries),
                "inflight": len(self._inflight),
                "max_items": self.max_items,
                "hits": self.hits,
                "misses": self.misses,
                "waits": self.waits,
                "builds": self.builds,
                "evictions": self.evictions,
            }


analysis_cache = SingleFlightTTLCache(
    max_items=int(os.getenv("LRO_ANALYSIS_CACHE_ITEMS", "384") or 384)
)
