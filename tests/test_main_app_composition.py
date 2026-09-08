import os

os.environ.setdefault("LRO_API_WARMUP", "0")
os.environ.setdefault("LRO_PUSH_MONITOR", "0")

from api.main_app import app


def test_production_main_app_has_product_and_platform_routes_without_push_worker():
    paths = {route.path for route in app.routes}

    assert "/api/health" in paths
    assert "/api/tenant/connect" in paths
    assert "/api/platform/status" in paths
    assert "/api/league-intelligence" in paths
    assert "/api/deep-analysis/transfers" in paths
    assert "/api/deep-analysis/wildcard" in paths
    assert "/api/preseason-tip" in paths
    assert "/api/push/status" not in paths
    assert getattr(app.state, "product_routes_registered", False) is True
    assert getattr(app.state, "tenant_routes_registered", False) is True
    assert getattr(app.state, "platform_middleware_installed", False) is True
