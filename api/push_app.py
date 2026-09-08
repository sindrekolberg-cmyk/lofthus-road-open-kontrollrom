from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.durable_push_monitor import DurablePushMonitor
from api.platform_middleware import install_platform_middleware, middleware_diagnostics
from api.platform_store import platform_store
from api.push import DEFAULT_LEAGUE_ID, PushStore, is_expo_push_token, send_expo_push

MAIN_API = os.getenv("LRO_MAIN_API_URL", "https://lofthus-road-open-api.onrender.com").rstrip("/")

push_store = PushStore()
push_monitor = DurablePushMonitor(push_store)


def _cors_origins() -> list[str]:
    raw = os.getenv(
        "LRO_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://localhost:3002,http://127.0.0.1:3002",
    )
    origins = [part.strip() for part in raw.split(",") if part.strip()]
    extra = os.getenv("LRO_FRONTEND_ORIGIN", "").strip()
    if extra and extra not in origins:
        origins.append(extra)
    return origins


def _cors_regex() -> str:
    return os.getenv("LRO_CORS_ORIGIN_REGEX", r"https://([a-z0-9-]+\.)*vercel\.app").strip()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("LRO_PUSH_MONITOR", "1") == "1":
        push_monitor.start()
    yield


app = FastAPI(title="Lofthus Road Open Push", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_regex() or None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
install_platform_middleware(app)


def _token_from(payload: dict[str, Any]) -> str:
    token = str(payload.get("expo_push_token") or "").strip()
    if not is_expo_push_token(token):
        raise HTTPException(status_code=400, detail="Ugyldig Expo push-token.")
    return token


def _manager_url(league_id: int, entry_id: int) -> str:
    if int(league_id) == DEFAULT_LEAGUE_ID:
        return f"{MAIN_API}/api/managers/{int(entry_id)}"
    return f"{MAIN_API}/api/tenant/{int(league_id)}/managers/{int(entry_id)}"


def _validate_subscription(league_id: int, entry_id: int | None) -> None:
    if not entry_id:
        return
    url = _manager_url(league_id, entry_id)
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Lofthus-Push-Subscribe/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            if response.status != 200:
                raise HTTPException(status_code=400, detail="Manageren finnes ikke i den valgte ligaen.")
            payload = json.loads(response.read().decode("utf-8"))
        manager = payload.get("manager") if isinstance(payload, dict) else None
        if not isinstance(manager, dict) or int(manager.get("entry") or 0) != int(entry_id):
            raise HTTPException(status_code=400, detail="Manageren finnes ikke i den valgte ligaen.")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=400, detail="Manageren finnes ikke i den valgte ligaen.") from exc
        raise HTTPException(status_code=503, detail="Kunne ikke validere manageren akkurat nå.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Kunne ikke validere manageren akkurat nå.") from exc


@app.get("/")
def root() -> dict[str, Any]:
    return {"ok": True, "service": "lofthus-road-open-push", "health": "/api/health"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "lofthus-road-open-push"}


@app.get("/api/push/status")
def push_status() -> dict[str, Any]:
    return {
        "ok": True,
        "subscribers": push_store.count(),
        "storage": push_store.backend,
        "durable": push_store.durable,
        "database_error": push_store.last_db_error or None,
        "platform_persistence": platform_store.diagnostics(),
        "middleware": middleware_diagnostics(),
        "monitor": push_monitor.status(),
        "main_api": MAIN_API,
    }


@app.post("/api/push/subscribe")
def push_subscribe(payload: dict[str, Any]) -> dict[str, Any]:
    token = _token_from(payload)
    try:
        entry_id = int(payload.get("entry_id")) if payload.get("entry_id") is not None else None
    except (TypeError, ValueError):
        entry_id = None
    try:
        league_id = int(payload.get("league_id")) if payload.get("league_id") is not None else DEFAULT_LEAGUE_ID
    except (TypeError, ValueError):
        league_id = DEFAULT_LEAGUE_ID
    if league_id <= 0:
        raise HTTPException(status_code=400, detail="Ugyldig liga-ID.")
    _validate_subscription(league_id, entry_id)

    record = push_store.upsert(
        token,
        platform=str(payload.get("platform") or ""),
        entry_id=entry_id,
        league_id=league_id,
        prefs=payload.get("prefs") if isinstance(payload.get("prefs"), dict) else {},
    )
    return {
        "ok": True,
        "stored": True,
        "durable": push_store.durable,
        "subscription": {
            "platform": record.get("platform"),
            "entry_id": record.get("entry_id"),
            "league_id": record.get("league_id"),
            "prefs": record.get("prefs"),
            "updated_at": record.get("updated_at"),
        },
    }


@app.post("/api/push/unsubscribe")
def push_unsubscribe(payload: dict[str, Any]) -> dict[str, Any]:
    token = _token_from(payload)
    return {"ok": True, "removed": push_store.remove(token)}


@app.post("/api/push/test")
def push_test(payload: dict[str, Any]) -> dict[str, Any]:
    token = _token_from(payload)
    if not push_store.get(token):
        raise HTTPException(status_code=404, detail="Denne mobilen er ikke registrert for push.")
    try:
        receipts = send_expo_push(
            [token],
            title="Lofthus Road Open",
            body="Testvarselet fra serveren ble sendt.",
            data={"path": "/"},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "sent": 1, "expo": receipts}


@app.post("/api/push/broadcast")
def push_broadcast(
    payload: dict[str, Any],
    x_lro_push_key: str | None = Header(default=None),
) -> dict[str, Any]:
    expected = os.getenv("LRO_PUSH_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Broadcast er ikke aktivert på serveren.")
    if not x_lro_push_key or not secrets.compare_digest(x_lro_push_key, expected):
        raise HTTPException(status_code=403, detail="Feil push-nøkkel.")

    title = str(payload.get("title") or "Lofthus Road Open").strip()[:100]
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Mangler meldingstekst.")
    try:
        league_filter = int(payload.get("league_id") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Ugyldig liga-ID.")
    rows = [row for row in push_store.list() if row.get("enabled", True)]
    if league_filter:
        rows = [row for row in rows if int(row.get("league_id") or DEFAULT_LEAGUE_ID) == league_filter]
    tokens = [str(row.get("expo_push_token") or "") for row in rows]
    try:
        receipts = send_expo_push(
            tokens,
            title=title,
            body=body,
            data=payload.get("data") if isinstance(payload.get("data"), dict) else {},
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "sent": len(tokens), "league_id": league_filter or None, "expo": receipts}
