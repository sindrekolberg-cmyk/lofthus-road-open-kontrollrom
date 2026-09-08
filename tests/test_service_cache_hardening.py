import threading
import time

import pytest

from api.service_cache import SingleFlightTTLCache


def test_failed_builder_is_briefly_negative_cached():
    cache = SingleFlightTTLCache(error_ttl_seconds=10)
    calls = 0

    def fail():
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        cache.get_or_build("same", fail, 30)
    with pytest.raises(RuntimeError, match="boom"):
        cache.get_or_build("same", fail, 30)

    assert calls == 1
    assert cache.diagnostics()["cached_errors"] == 1


def test_waiter_timeout_does_not_start_second_builder():
    cache = SingleFlightTTLCache(wait_timeout_seconds=0.05, error_ttl_seconds=2)
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def slow():
        nonlocal calls
        calls += 1
        started.set()
        release.wait(timeout=1)
        return {"ok": True}

    creator = threading.Thread(target=lambda: cache.get_or_build("same", slow, 30))
    creator.start()
    assert started.wait(timeout=1)

    with pytest.raises(TimeoutError, match="brukte for lang tid"):
        cache.get_or_build("same", slow, 30)

    release.set()
    creator.join(timeout=1)

    assert calls == 1
    assert cache.diagnostics()["wait_timeouts"] == 1


def test_equivalent_refresh_timestamps_share_analysis_cache_generation():
    cache = SingleFlightTTLCache()
    calls = 0

    def build():
        nonlocal calls
        calls += 1
        return {"build": calls}

    first = (25220, "2026-09-08T15:00:00+00:00:63:4:17", "transfer", 123)
    refreshed = (25220, "2026-09-08T15:00:08+00:00:63:4:17", "transfer", 123)
    changed = (25220, "2026-09-08T15:00:09+00:00:63:4:18", "transfer", 123)

    assert cache.get_or_build(first, build, 300)["build"] == 1
    assert cache.get_or_build(refreshed, build, 300)["build"] == 1
    assert cache.get_or_build(changed, build, 300)["build"] == 2
    assert calls == 2
    assert cache.diagnostics()["semantic_key_collapses"] >= 3
