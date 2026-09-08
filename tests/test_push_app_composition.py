import os

os.environ.setdefault("LRO_PUSH_MONITOR", "0")
os.environ.setdefault("LRO_API_WARMUP", "0")

from api.push_app import app


def test_push_worker_only_exposes_push_routes():
    paths = {route.path for route in app.routes}

    assert "/api/health" in paths
    assert "/api/push/status" in paths
    assert "/api/push/subscribe" in paths
    assert "/api/push/unsubscribe" in paths
    assert "/api/tenant/connect" not in paths
    assert "/api/league-intelligence" not in paths
    assert "/api/deep-analysis/transfers" not in paths
