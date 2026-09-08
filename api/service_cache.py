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


def _semantic_snapshot_id(value: Any) -> Any:
    """Drop the fetch timestamp from RequestSnapshot IDs used in analysis keys.

    RequestSnapshot currently uses `<fetched_at>:<league-size>:<gw>:<seq>`. The
    fetched_at portion changes on a harmless refresh even when the live semantic
    signature did not change, which used to make a 300-second analysis TTL act
    like an 8-second cache. `seq` already advances when the engine adopts a real
    state change, so league-size + GW + seq is the correct cache generation.
    """
    if not isinstance(value, str):
        return value
    parts = value.rsplit(":", 3)
    if len(parts) != 4:
        return value
    league_size, event_id, seq = parts[1:]
    if not all(part.lstrip("-").isdigit() for part in (league_size, event_id, seq)):
        return value
    return f"snapshot:{league_size}:{event_id}:{seq}"


def _normalize_key(key: Hashable) -> Hashable:
    # Analysis keys in this project start with league_id and snapshot_id. Keep
    # arbitrary keys untouched so the cache remains useful as a small generic.
    if isinstance(key, tuple) and len(key) >= 2 and isinstance(key[0], int):
        normalized_snapshot = _semantic_snapshot_id(key[1])
        if normalized_snapshot != key[1]:
            return (key[0], normalized_snapshot, *key[2:])
    return key


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
        self.semantic_key_collapses = 0

    def _key(self, key: Hashable) -> Hashable:
        normalized = _normalize_key(key)
        if normalized != key:
            self.semantic_key_collapses += 1
        return normalized

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
            key = self._key(key)
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
            key = self._key(key)
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
            key = self._key(key)
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
                "semantic_key_collapses": self.semantic_key_collapses,
            }


analysis_cache = SingleFlightTTLCache(
    max_items=int(os.getenv("LRO_ANALYSIS_CACHE_ITEMS", "384") or 384),
    wait_timeout_seconds=float(os.getenv("LRO_ANALYSIS_WAIT_SECONDS", "65") or 65),
    error_ttl_seconds=float(os.getenv("LRO_ANALYSIS_ERROR_TTL_SECONDS", "12") or 12),
)
