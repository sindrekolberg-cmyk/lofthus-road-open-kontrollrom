from __future__ import annotations

import threading
import time

from fastapi import FastAPI

from api.platform_store import PlatformStore
from api.service_cache import SingleFlightTTLCache
from api.tenant_api import register_tenant_routes


def test_singleflight_builds_expensive_value_once():
    cache = SingleFlightTTLCache(max_items=16)
    lock = threading.Lock()
    builds = 0
    results: list[dict] = []

    def builder():
        nonlocal builds
        with lock:
            builds += 1
        time.sleep(0.08)
        return {"value": 42}

    def worker():
        results.append(cache.get_or_build(("league", 1), builder, 30))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert builds == 1
    assert len(results) == 6
    assert all(row == {"value": 42} for row in results)
    assert cache.diagnostics()["waits"] >= 1


def test_platform_store_local_fallback_survives_new_instance(tmp_path):
    path = tmp_path / "platform.json"
    first = PlatformStore(database_url="", path=str(path))
    first.upsert_league(123, name="Testliga", season="2026/27", manager_count=4)
    saved = first.upsert_profile(
        "installation-1234567890",
        league_id=123,
        entry_id=456,
        goal="top3",
        app_version="beta",
    )
    first.set_cursor("push:test", {"event_id": 7, "stats": {"1": {"goals": 1}}})

    assert saved["league_id"] == 123
    assert first.durable is False

    second = PlatformStore(database_url="", path=str(path))
    profile = second.get_profile("installation-1234567890")
    assert profile is not None
    assert profile["entry_id"] == 456
    assert profile["goal"] == "top3"
    assert second.get_cursor("push:test") == {"event_id": 7, "stats": {"1": {"goals": 1}}}


def test_tenant_routes_are_registered_only_once():
    app = FastAPI()
    register_tenant_routes(app)
    first_paths = [route.path for route in app.routes]
    register_tenant_routes(app)
    second_paths = [route.path for route in app.routes]

    assert first_paths == second_paths
    assert first_paths.count("/api/tenant/connect") == 1
    assert first_paths.count("/api/platform/status") == 1
    assert first_paths.count("/api/tenant/{league_id}/experience") == 1
