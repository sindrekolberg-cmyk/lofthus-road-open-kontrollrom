from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import Header, HTTPException

from api.app import app
from api.push import PushStore, is_expo_push_token, send_expo_push

push_store = PushStore()


def _token_from(payload: dict[str, Any]) -> str:
    token = str(payload.get("expo_push_token") or "").strip()
    if not is_expo_push_token(token):
        raise HTTPException(status_code=400, detail="Ugyldig Expo push-token.")
    return token


@app.get("/api/push/status")
def push_status() -> dict[str, Any]:
    return {
        "ok": True,
        "subscribers": push_store.count(),
        "storage": "local-json",
        "durable": False,
    }


@app.post("/api/push/subscribe")
def push_subscribe(payload: dict[str, Any]) -> dict[str, Any]:
    token = _token_from(payload)
    entry_raw = payload.get("entry_id")
    entry_id: int | None
    try:
        entry_id = int(entry_raw) if entry_raw is not None else None
    except (TypeError, ValueError):
        entry_id = None

    record = push_store.upsert(
        token,
        platform=str(payload.get("platform") or ""),
        entry_id=entry_id,
        prefs=payload.get("prefs") if isinstance(payload.get("prefs"), dict) else {},
    )
    return {
        "ok": True,
        "stored": True,
        "subscription": {
            "platform": record.get("platform"),
            "entry_id": record.get("entry_id"),
            "prefs": record.get("prefs"),
            "updated_at": record.get("updated_at"),
        },
    }


@app.post("/api/push/unsubscribe")
def push_unsubscribe(payload: dict[str, Any]) -> dict[str, Any]:
    token = _token_from(payload)
    removed = push_store.remove(token)
    return {"ok": True, "removed": removed}


@app.post("/api/push/test")
def push_test(payload: dict[str, Any]) -> dict[str, Any]:
    token = _token_from(payload)
    if not push_store.get(token):
        raise HTTPException(status_code=404, detail="Denne mobilen er ikke registrert for push.")

    try:
        receipts = send_expo_push(
            [token],
            title="Lofthus Road Open",
            body="Push fra Lofthus-serveren virker. Nå begynner det å ligne noe.",
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

    rows = [row for row in push_store.list() if row.get("enabled", True)]
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

    return {"ok": True, "sent": len(tokens), "expo": receipts}
