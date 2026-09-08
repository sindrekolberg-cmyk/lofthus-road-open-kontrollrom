from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import Header, HTTPException, Query

from api.app import app
from api.deep_analysis import build_deep_transfer_analysis
from api.engine import get_engine
from api.league_intelligence import build_league_intelligence
from api.push import PushStore, is_expo_push_token, send_expo_push
from api.push_monitor import PushMonitor
from api.serialize import analysis_from_state
from api.wildcard import build_wildcard_analysis
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


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


@app.get("/api/league-intelligence")
def league_intelligence(
    entry_id: int = Query(...),
    goal: str = Query("auto"),
) -> dict[str, Any]:
    body = build_league_intelligence(entry_id=entry_id, goal=goal)
    if not body.get("ok"):
        raise HTTPException(status_code=404, detail=body.get("error") or "Liga-analysen kunne ikke bygges.")
    return body


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
    ranked = list(body.get("ranked") or [])
    if ranked:
        body["recommendations"] = ranked[:5]
    return body


@app.get("/api/deep-analysis/wildcard")
def deep_analysis_wildcard(
    entry_id: int = Query(...),
    strategy: str = Query("balanced"),
    risk: int = Query(50),
    horizon: int = Query(5),
) -> dict[str, Any]:
    body = build_wildcard_analysis(
        entry_id=entry_id,
        strategy=strategy,
        risk=risk,
        horizon=max(5, horizon),
    )
    if not body.get("ok"):
        raise HTTPException(status_code=404, detail=body.get("error") or "Wildcard-analysen kunne ikke bygges.")
    return body


@app.get("/api/deep-analysis/ownership")
def deep_analysis_ownership() -> dict[str, Any]:
    """Combine Lofthus ownership with the global FPL market and free FPL stats."""
    eng = get_engine()
    snap = eng.snapshot()
    if not snap.state:
        raise HTTPException(status_code=503, detail="Live-data er ikke klare ennå.")

    payload = analysis_from_state(snap.state)
    by_element = {
        int(row.get("id") or 0): row
        for row in (snap.bootstrap.get("elements") or [])
        if int(row.get("id") or 0)
    }

    rows: list[dict[str, Any]] = []
    for source in payload.get("ownership") or []:
        row = dict(source)
        meta = by_element.get(int(row.get("element") or 0), {})
        lofthus_pct = _float(row.get("ownership_pct"))
        global_pct = _float(meta.get("selected_by_percent"))
        form = _float(meta.get("form"))
        ppg = _float(meta.get("points_per_game"))
        total_points = int(_float(meta.get("total_points")))
        minutes = int(_float(meta.get("minutes")))
        xgi90 = _float(meta.get("expected_goal_involvements_per_90"))
        status = str(meta.get("status") or "a")

        rarity = max(0.0, 100.0 - lofthus_pct) / 100.0
        form_signal = min(max(form / 10.0, 0.0), 1.0)
        ppg_signal = min(max(ppg / 8.0, 0.0), 1.0)
        xgi_signal = min(max(xgi90 / 0.9, 0.0), 1.0)
        availability = 1.0 if status == "a" else 0.55
        differential_score = 100.0 * availability * (
            0.48 * rarity + 0.19 * form_signal + 0.17 * ppg_signal + 0.16 * xgi_signal
        )

        row.update(
            {
                "global_ownership_pct": round(global_pct, 1),
                "ownership_gap_pct": round(lofthus_pct - global_pct, 1),
                "form": round(form, 1),
                "points_per_game": round(ppg, 1),
                "season_points": total_points,
                "season_minutes": minutes,
                "xgi_per90": round(xgi90, 3),
                "status": status,
                "differential_score": round(differential_score, 1),
            }
        )
        rows.append(row)

    return {
        "players": rows,
        "league_size": payload.get("league_size"),
        "loaded_managers": payload.get("loaded_managers"),
        "complete": payload.get("complete", True),
        "sources": [
            "Lofthus Road Open live ownership",
            "Fantasy Premier League bootstrap",
        ],
    }


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
