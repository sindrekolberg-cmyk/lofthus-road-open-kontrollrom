from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.platform_middleware as middleware


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/tenant/connect")
    def connect():
        return {"ok": True}

    @app.get("/api/deep-analysis/transfers")
    def analysis():
        return {"ok": True}

    middleware.install_platform_middleware(app)
    return app


def test_global_tenant_connect_guard_survives_ip_rotation(monkeypatch):
    monkeypatch.setattr(middleware, "_limiter", middleware.SlidingWindowLimiter())
    monkeypatch.setattr(middleware, "_tenant_global_per_minute", 2)
    client = TestClient(_app())

    assert client.get("/api/tenant/connect", headers={"x-forwarded-for": "10.0.0.1"}).status_code == 200
    assert client.get("/api/tenant/connect", headers={"x-forwarded-for": "10.0.0.2"}).status_code == 200
    blocked = client.get("/api/tenant/connect", headers={"x-forwarded-for": "10.0.0.3"})

    assert blocked.status_code == 429
    assert "nye ligatilkoblinger" in blocked.json()["detail"]
    assert int(blocked.headers["Retry-After"]) >= 1


def test_heavy_analysis_has_per_client_rate_limit(monkeypatch):
    monkeypatch.setattr(middleware, "_limiter", middleware.SlidingWindowLimiter())
    monkeypatch.setattr(middleware, "_heavy_per_minute", 2)
    client = TestClient(_app())
    headers = {"x-forwarded-for": "10.9.8.7"}

    assert client.get("/api/deep-analysis/transfers", headers=headers).status_code == 200
    assert client.get("/api/deep-analysis/transfers", headers=headers).status_code == 200
    blocked = client.get("/api/deep-analysis/transfers", headers=headers)

    assert blocked.status_code == 429
    assert "analyseforespørsler" in blocked.json()["detail"]
