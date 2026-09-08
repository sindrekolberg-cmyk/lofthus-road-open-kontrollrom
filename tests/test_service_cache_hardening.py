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
