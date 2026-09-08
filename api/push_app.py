from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import Header, HTTPException, Query

from api.app import app
from api.deep_analysis import build_deep_transfer_analysis
from api.engine import get_engine
from api.push import PushStore, is_expo_push_token, send_expo_push
from api.push_monitor import PushMonitor
from lro_odds import build_preseason_odds

push_store = PushStore()
push_monitor = PushMonitor(push_store)
if os.getenv("LRO_PUSH_MONITOR", "1") == "1":
    push_monitor.start()


def _token_from(payload: dict[str, Any]) -> str:
    token = str(payload.get("expo_push_token") or "").strip()
    if not is_expo_push_token(token):
        raise HTTPException(status_code=400, detail="Ugyldig Expo push-token.")
    return token


@app.get("/api/preseason-tip")
def preseason_tip() -> dict[str, Any]:
    eng = get_engine()
    snap = eng.snapshot()
    manager_states = list(eng.manager_states(snap))
    managers = [
        {
            "entry": m.entry,
            "player_name": m.manager,
            "rank": m.live_rank,
            "total": m.live_total_points,
        }
        for m in manager_states
    ]
    try:
        table = build_preseason_odds(managers, snap.histories or {}, eng.history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tabelltipset kunne ikke bygges: {exc}") from exc

    if table is None or table.empty:
        return {"ready": False, "rows": [], "note": "Tabelltipset er ikke klart."}

    team_by_entry = {m.entry: m.team for m in manager_states}
    rows: list[dict[str, Any]] = []
    for raw in table.to_dict("records"):
        entry = int(raw.get("entry") or 0)
        odds = float(raw.get("winner_odds") or 251.0)
        rows.append(
            {
                "entry": entry,
                "manager": str(raw.get("manager") or ""),
                "team": team_by_entry.get(entry, ""),
                "rank": int(raw.get("preseason_rank") or len(rows) + 1),
                "win_pct": round(100.0 / max(1.01, odds), 1),
                "odds": round(odds, 2),
                "preseason_odds": round(odds, 2),
                "note": "Fryst før sesongstart",
            }
        )

    rows.sort(key=lambda row: (row["rank"], row["manager"].casefold()))
    return {"ready": True, "rows": rows, "count": len(rows), "frozen": True}


@app.get("/api/deep-analysis/transfers")
def deep_analysis_transfers(
    entry_id: int = Query(...),
    strategy: str = Query("balanced"),
    risk: int = Query(50),
    horizon: int = Query(5),
    target: str = Query(""),
    rival_id: int = Query(0),
    position: str = Query("all"),
) -> dict[str, Any]:
    body = build_deep_transfer_analysis(
        entry_id=entry_id,
        strategy=strategy,
        risk=risk,
        horizon=horizon,
        target=target,
        rival_id=rival_id,
        position=position,
    )
    if not body.get("ok"):
        raise HTTPException(status_code=404, detail=body.get("error") or "Analysen kunne ikke bygges.")
    return body


@app.get("/api/push/status")
def push_status() -> dict[str, Any]:
    return {
        "ok": True,
        "subscribers": push_store.count(),
        "storage": "local-json",
        "durable": False,
        "monitor": push_monitor.status(),
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
            body="Testvarselet fra Lofthus Road Open ble sendt.",
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
