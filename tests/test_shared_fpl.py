import threading
import time

from api.shared_fpl import SharedFPLClient
from lro_fpl import FPLClient, FPLError


def test_concurrent_identical_fpl_gets_share_one_builder(monkeypatch):
    calls = 0
    calls_lock = threading.Lock()

    def fake_parent_get(self, path, ttl=300, stale_if_error=1800, force=False):
        nonlocal calls
        normalized = path if path.startswith("/") else f"/{path}"
        with calls_lock:
            calls += 1
        time.sleep(0.08)
        value = {"ok": True, "path": normalized}
        self._set_cached(f"GET:{normalized}", value, ttl)
        return value

    monkeypatch.setattr(FPLClient, "get_json", fake_parent_get)
    client = SharedFPLClient(timeout=1)
    results = []

    def worker():
        results.append(client.get_json("/bootstrap-static/", ttl=30))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert len(results) == 5
    assert all(row["ok"] for row in results)
    assert client.diagnostics()["singleflight_waits"] >= 1


def test_concurrent_upstream_failure_is_not_retried_by_every_waiter(monkeypatch):
    calls = 0
    calls_lock = threading.Lock()
    failures = []

    def fake_parent_get(self, path, ttl=300, stale_if_error=1800, force=False):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.08)
        raise FPLError("upstream down")

    monkeypatch.setattr(FPLClient, "get_json", fake_parent_get)
    client = SharedFPLClient(timeout=1)

    def worker():
        try:
            client.get_json("/fixtures/", ttl=30)
        except FPLError as exc:
            failures.append(str(exc))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert len(failures) == 5
    assert all("upstream down" in message for message in failures)
    diagnostics = client.diagnostics()
    assert diagnostics["shared_failure_hits"] >= 1
    assert diagnostics["recent_shared_errors"] == 1
