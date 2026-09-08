from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class SlidingWindowLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def allow(self, bucket: str, identity: str, *, limit: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - float(window_seconds)
        key = (bucket, identity)
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= int(limit):
                retry = max(1, int(window_seconds - (now - events[0])))
                return False, retry
            events.append(now)
            if len(self._events) > 5000:
                stale = [k for k, q in self._events.items() if not q or q[-1] <= cutoff]
                for stale_key in stale[:1000]:
                    self._events.pop(stale_key, None)
            return True, 0


_limiter = SlidingWindowLimiter()
_heavy_limit = max(1, int(os.getenv("LRO_HEAVY_CONCURRENCY", "4") or 4))
_heavy = asyncio.Semaphore(_heavy_limit)


def _client_identity(request: Request) -> str:
    forwarded = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:80]
    client = getattr(request, "client", None)
    return str(getattr(client, "host", "unknown") or "unknown")[:80]


def _rate_rule(path: str, method: str) -> tuple[str, int, int] | None:
    if path == "/api/tenant/connect":
        return "tenant-connect", 20, 60
    if path == "/api/profile" and method == "POST":
        return "profile-write", 30, 60
    if path == "/api/push/subscribe" and method == "POST":
        return "push-subscribe", 30, 60
    return None


def _is_heavy(path: str) -> bool:
    return (
        "/deep-analysis/" in path
        or path.endswith("/league-intelligence")
        or path.endswith("/experience")
        or path in {"/api/league-intelligence", "/api/league-experience"}
    )


def install_platform_middleware(app: FastAPI) -> None:
    if getattr(app.state, "platform_middleware_installed", False):
        return
    app.state.platform_middleware_installed = True

    @app.middleware("http")
    async def platform_guard(request: Request, call_next):
        started = time.perf_counter()
        request_id = str(request.headers.get("x-request-id") or "").strip()[:100] or uuid.uuid4().hex
        identity = _client_identity(request)
        rule = _rate_rule(request.url.path, request.method.upper())
        if rule:
            bucket, limit, window = rule
            allowed, retry = _limiter.allow(bucket, identity, limit=limit, window_seconds=window)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "For mange forespørsler. Prøv igjen om litt.", "request_id": request_id},
                    headers={"Retry-After": str(retry), "X-Request-ID": request_id},
                )

        acquired = False
        if _is_heavy(request.url.path):
            try:
                await asyncio.wait_for(_heavy.acquire(), timeout=8.0)
                acquired = True
            except TimeoutError:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Analysemotoren er opptatt. Prøv igjen om noen sekunder.", "request_id": request_id},
                    headers={"Retry-After": "5", "X-Request-ID": request_id},
                )

        try:
            response = await call_next(request)
        finally:
            if acquired:
                _heavy.release()

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def middleware_diagnostics() -> dict[str, Any]:
    return {"heavy_concurrency_limit": _heavy_limit, "rate_limits_enabled": True}
