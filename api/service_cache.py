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


@dataclass
class ErrorEntry:
    error: BaseException
    expires_at: float


class SingleFlightTTLCache:
    """Small process-local cache with duplicate-work suppression.

    Expensive analysis endpoints are easy to hammer accidentally from mobile
    rerenders, pull-to-refresh and several users in the same league. One builder
    runs per key; concurrent callers wait for that result instead of recomputing
    the same projection workload. Failed builders are cached briefly so a broken
    upstream does not cause an immediate retry storm.
    """

    def __init__(
        self,
        max_items: int = 256,
        *,
        wait_timeout_seconds: float = 65.0,
        error_ttl_seconds: float = 12.0,
    ):
        self.max_items = max(16, int(max_items))
        self.wait_timeout_seconds = max(1.0, float(wait_timeout_seconds))
        self.error_ttl_seconds = max(1.0, float(error_ttl_seconds))
        self._lock = threading.RLock()
        self._entries: OrderedDict[Hashable, CacheEntry] = OrderedDict()
        self._inflight: dict[Hashable, threading.Event] = {}
        self._errors: OrderedDict[Hashable, ErrorEntry] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.waits = 0
        self.builds = 0
        self.evictions = 0
        self.failures = 0
        self.wait_timeouts = 0

    def _prune(self) -> None:
        now = time.monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
        expired_errors = [key for key, entry in self._errors.items() if entry.expires_at <= now]
        for key in expired_errors:
            self._errors.pop(key, None)
        while len(self._entries) > self.max_items:
            self._entries.popitem(last=False)
            self.evictions += 1
        while len(self._errors) > self.max_items:
            self._errors.popitem(last=False)

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
            self._errors.pop(key, None)
            self._prune()
        return value

    def _raise_cached_error(self, key: Hashable) -> None:
        error_entry = self._errors.get(key)
        if error_entry is None or error_entry.expires_at <= time.monotonic():
            return
        self._errors.move_to_end(key)
        error = error_entry.error
        raise RuntimeError(str(error)) from error

    def get_or_build(self, key: Hashable, builder: Callable[[], Any], ttl_seconds: float) -> Any:
        with self._lock:
            self._prune()
            entry = self._entries.get(key)
            if entry is not None:
                self.hits += 1
                self._entries.move_to_end(key)
                return deepcopy(entry.value)

            self._raise_cached_error(key)
            event = self._inflight.get(key)
            if event is None:
                event = threading.Event()
                self._inflight[key] = event
                creator = True
                self.misses += 1
                self.builds += 1
            else:
                creator = False
                self.waits += 1

        if not creator:
            completed = event.wait(timeout=self.wait_timeout_seconds)
            if not completed:
                with self._lock:
                    self.wait_timeouts += 1
                # Never turn a timed-out waiter into another expensive builder.
                # That old behavior could multiply one wedged analysis into a
                # stampede of unique retry keys.
                raise TimeoutError("Analyseberegningen brukte for lang tid. Prøv igjen om litt.")
            with self._lock:
                self._prune()
                entry = self._entries.get(key)
                if entry is not None and entry.expires_at > time.monotonic():
                    self.hits += 1
                    self._entries.move_to_end(key)
                    return deepcopy(entry.value)
                self._raise_cached_error(key)
            raise RuntimeError("Analyseberegningen ble avsluttet uten resultat.")

        try:
            value = builder()
            self.set(key, value, ttl_seconds)
            return value
        except BaseException as exc:
            with self._lock:
                self.failures += 1
                self._errors[key] = ErrorEntry(exc, time.monotonic() + self.error_ttl_seconds)
                self._errors.move_to_end(key)
                self._prune()
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
                "cached_errors": len(self._errors),
                "max_items": self.max_items,
                "wait_timeout_seconds": self.wait_timeout_seconds,
                "error_ttl_seconds": self.error_ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "waits": self.waits,
                "builds": self.builds,
                "evictions": self.evictions,
                "failures": self.failures,
                "wait_timeouts": self.wait_timeouts,
            }


analysis_cache = SingleFlightTTLCache(
    max_items=int(os.getenv("LRO_ANALYSIS_CACHE_ITEMS", "384") or 384),
    wait_timeout_seconds=float(os.getenv("LRO_ANALYSIS_WAIT_SECONDS", "65") or 65),
    error_ttl_seconds=float(os.getenv("LRO_ANALYSIS_ERROR_TTL_SECONDS", "12") or 12),
)
