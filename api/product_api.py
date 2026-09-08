from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from api.deep_analysis import build_deep_transfer_analysis
from api.engine import get_engine
from api.league_experience_v2 import build_league_experience_v2
from api.league_intelligence_v2 import build_league_intelligence_v2
from api.push import DEFAULT_LEAGUE_ID
from api.serialize import analysis_from_state
from api.service_cache import analysis_cache
from api.wildcard import build_wildcard_analysis
from lro_odds import build_preseason_odds


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def register_product_routes(app: FastAPI) -> None:
    """Register the default-league product endpoints on the public API.

    These used to live in the push worker, which made mobile analysis depend on
    the background notification service. Product reads now belong to the main
    API; the push service can remain a thin worker.
    """
    if getattr(app.state, "product_routes_registered", False):
        return
    app.state.product_routes_registered = True

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
        eng = get_engine()
        snap = eng.light_snapshot()
        key = (DEFAULT_LEAGUE_ID, snap.snapshot_id, "intelligence-v2", entry_id, goal)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_league_intelligence_v2(entry_id=entry_id, goal=goal, engine=eng),
            35 if snap.state and snap.state.is_live else 300,
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Liga-analysen kunne ikke bygges.")
        return body

    @app.get("/api/league-experience")
    def league_experience(
        entry_id: int = Query(...),
        goal: str = Query("auto"),
    ) -> dict[str, Any]:
        eng = get_engine()
        snap = eng.light_snapshot()
        key = (DEFAULT_LEAGUE_ID, snap.snapshot_id, "experience-v2", entry_id, goal)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_league_experience_v2(entry_id=entry_id, goal=goal, engine=eng),
            35 if snap.state and snap.state.is_live else 300,
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Ligaopplevelsen kunne ikke bygges.")
        return body

    @app.get("/api/deep-analysis/transfers")
    def deep_analysis_transfers(
        entry_id: int = Query(...),
        strategy: str = Query("balanced"),
        risk: int = Query(50, ge=0, le=100),
        horizon: int = Query(5, ge=5, le=10),
        target: str = Query(""),
        rival_id: int = Query(0),
        position: str = Query("all"),
    ) -> dict[str, Any]:
        eng = get_engine()
        snap = eng.light_snapshot()
        key = (DEFAULT_LEAGUE_ID, snap.snapshot_id, "transfer", entry_id, strategy, risk, horizon, target, rival_id, position)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_deep_transfer_analysis(
                entry_id=entry_id,
                strategy=strategy,
                risk=risk,
                horizon=horizon,
                target=target,
                rival_id=rival_id,
                position=position,
            ),
            45 if snap.state and snap.state.is_live else 300,
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
        risk: int = Query(50, ge=0, le=100),
        horizon: int = Query(5, ge=5, le=10),
    ) -> dict[str, Any]:
        eng = get_engine()
        snap = eng.light_snapshot()
        key = (DEFAULT_LEAGUE_ID, snap.snapshot_id, "wildcard", entry_id, strategy, risk, horizon)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_wildcard_analysis(
                entry_id=entry_id,
                strategy=strategy,
                risk=risk,
                horizon=horizon,
            ),
            45 if snap.state and snap.state.is_live else 300,
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Wildcard-analysen kunne ikke bygges.")
        return body

    @app.get("/api/deep-analysis/ownership")
    def deep_analysis_ownership() -> dict[str, Any]:
        eng = get_engine()
        snap = eng.light_snapshot()
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
            league_pct = _float(row.get("ownership_pct"))
            global_pct = _float(meta.get("selected_by_percent"))
            form = _float(meta.get("form"))
            ppg = _float(meta.get("points_per_game"))
            total_points = int(_float(meta.get("total_points")))
            minutes = int(_float(meta.get("minutes")))
            xgi90 = _float(meta.get("expected_goal_involvements_per_90"))
            status = str(meta.get("status") or "a")

            rarity = max(0.0, 100.0 - league_pct) / 100.0
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
                    "ownership_gap_pct": round(league_pct - global_pct, 1),
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
            "sources": ["Mini-ligaens live eierskap", "Fantasy Premier League bootstrap"],
        }
