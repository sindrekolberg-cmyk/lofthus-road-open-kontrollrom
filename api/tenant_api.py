from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from api.league_intelligence_v2 import build_league_intelligence_v2
from api.league_registry import league_registry
from api.serialize import (
    analysis_from_state,
    live_events_payload,
    manager_payload,
    match_impact_payload,
    movers_payload,
    player_swing_payload,
    rival_payload,
    season_from_bootstrap,
    squad_payload,
    status_payload,
    talkers_payload,
)
from api.tenant_analysis import build_tenant_transfer_analysis, build_tenant_wildcard_analysis
from lro_analysis import nint
from lro_rival import compare_managers


def _runtime(league_id: int):
    try:
        return league_registry.get(int(league_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _status(runtime, snap) -> dict[str, Any]:
    eng = runtime.engine
    body = status_payload(
        name=runtime.name,
        season=season_from_bootstrap(snap.bootstrap, eng.config.season_fallback),
        state=snap.state,
        managers=snap.managers,
        live_ready=snap.state is not None,
        histories_ready=snap.histories is not None,
        errors=snap.errors,
    )
    body.update(snap.meta())
    body["league_id"] = runtime.league_id
    return body


def _fixture_pool(runtime, snap) -> list[dict[str, Any]]:
    rows = list((snap.state.fixtures if snap.state else []) or [])
    try:
        rows.extend(runtime.engine.client.fixtures() or [])
    except Exception:
        pass
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        fixture_id = nint(row.get("id"))
        if fixture_id:
            by_id[fixture_id] = row
    return list(by_id.values())


def _manager_options(runtime, snap) -> list[dict[str, Any]]:
    states = {m.entry: m for m in runtime.engine.manager_states(snap)}
    rows: list[dict[str, Any]] = []
    for raw in snap.managers:
        entry = nint(raw.get("entry"))
        if not entry:
            continue
        live = states.get(entry)
        rows.append(
            {
                "entry": entry,
                "manager": live.manager if live else str(raw.get("player_name") or ""),
                "team": live.team if live else str(raw.get("entry_name") or ""),
                "rank": live.live_rank if live else nint(raw.get("rank")),
                "gw": live.live_gw_points if live else nint(raw.get("event_total")),
                "total": live.live_total_points if live else nint(raw.get("total")),
                "rank_change": live.live_rank_change if live else 0,
                "players_remaining": live.players_remaining if live else 0,
            }
        )
    rows.sort(key=lambda row: (row["rank"] or 10**9, str(row["manager"]).casefold()))
    return rows


def _history_payload(histories: dict[int, dict] | None, entry: int) -> dict[str, Any]:
    return (histories or {}).get(int(entry)) or (histories or {}).get(str(int(entry))) or {}


def _form_rows(histories: dict[int, dict] | None, entry: int) -> list[dict[str, Any]]:
    mine = list((_history_payload(histories, entry).get("current") or []))
    if not mine:
        return []

    per_event: dict[int, list[tuple[int, int, int]]] = {}
    for raw_entry, payload in (histories or {}).items():
        try:
            candidate_entry = int(raw_entry)
        except Exception:
            continue
        for row in (payload or {}).get("current") or []:
            event = nint(row.get("event"))
            if event:
                per_event.setdefault(event, []).append(
                    (candidate_entry, nint(row.get("total_points")), nint(row.get("points")))
                )

    out: list[dict[str, Any]] = []
    for row in mine:
        event = nint(row.get("event"))
        if not event:
            continue
        peers = per_event.get(event, [])
        season_sorted = sorted(peers, key=lambda item: (-item[1], item[0]))
        round_sorted = sorted(peers, key=lambda item: (-item[2], item[0]))
        league_rank = next((i + 1 for i, item in enumerate(season_sorted) if item[0] == int(entry)), 0)
        round_rank = next((i + 1 for i, item in enumerate(round_sorted) if item[0] == int(entry)), 0)
        out.append(
            {
                "event": event,
                "points": nint(row.get("points")),
                "league_rank": league_rank,
                "round_rank": round_rank,
                "is_live": False,
            }
        )
    out.sort(key=lambda row: row["event"])
    return out[-10:]


def register_tenant_routes(app: FastAPI) -> None:
    @app.get("/api/tenant/connect")
    def tenant_connect(league_id: int = Query(..., gt=0)) -> dict[str, Any]:
        try:
            return league_registry.connect_payload(league_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/tenant/{league_id}/status")
    def tenant_status(league_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        return _status(runtime, snap)

    @app.get("/api/tenant/{league_id}/managers")
    def tenant_managers(league_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        return {"managers": _manager_options(runtime, snap), "status": _status(runtime, snap)}

    @app.get("/api/tenant/{league_id}/league")
    def tenant_league(league_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        states = runtime.engine.manager_states(snap)
        return {"status": _status(runtime, snap), "table": [manager_payload(m) for m in states]}

    @app.get("/api/tenant/{league_id}/home")
    def tenant_home(league_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        states = list(runtime.engine.manager_states(snap))
        state = snap.state
        status = _status(runtime, snap)
        month_table = [manager_payload(m) for m in (state.month_ranking()[:5] if state else [])]
        popular = talkers_payload(state, snap.bootstrap) if state else []
        fixtures = live_events_payload(state, snap.bootstrap, fixture_pool=_fixture_pool(runtime, snap)) if state else []
        return {
            "status": status,
            "top5": [manager_payload(m) for m in states[:5]],
            "movers": movers_payload(states),
            "news": [],
            "popular": popular,
            "month": {"name": state.month_name if state else "", "table": month_table},
            "pulse": {
                "gw": status.get("event_id") or 0,
                "label": status.get("event_status_label") or "",
                "is_live": bool(status.get("is_live")),
                "fixtures": fixtures,
            },
        }

    @app.get("/api/tenant/{league_id}/managers/{entry_id}")
    def tenant_manager(league_id: int, entry_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        if not snap.state:
            raise HTTPException(status_code=503, detail="Live-data bygges. Prøv igjen om noen sekunder.")
        manager = snap.state.manager(entry_id)
        if not manager:
            raise HTTPException(status_code=404, detail="Manageren finnes ikke i denne ligaen.")
        return {
            "manager": manager_payload(manager),
            "squad": squad_payload(snap.state, entry_id),
            "form": _form_rows(snap.histories, entry_id),
            "status": _status(runtime, snap),
        }

    @app.get("/api/tenant/{league_id}/players/{element_id}")
    def tenant_player(league_id: int, element_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        if not snap.state:
            raise HTTPException(status_code=503, detail="Live-data bygges. Prøv igjen om noen sekunder.")
        body = player_swing_payload(snap.state, element_id)
        if not body:
            raise HTTPException(status_code=404, detail="Spilleren finnes ikke i ligaens live-data.")
        body["status"] = _status(runtime, snap)
        return body

    @app.get("/api/tenant/{league_id}/matches/{fixture_id}")
    def tenant_match(league_id: int, fixture_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        if not snap.state:
            raise HTTPException(status_code=503, detail="Live-data bygges. Prøv igjen om noen sekunder.")
        body = match_impact_payload(snap.state, snap.bootstrap, fixture_id, fixture_pool=_fixture_pool(runtime, snap))
        if not body:
            raise HTTPException(status_code=404, detail="Kampen finnes ikke.")
        body["status"] = _status(runtime, snap)
        return body

    @app.get("/api/tenant/{league_id}/rival")
    def tenant_rival(
        league_id: int,
        manager_a: int = Query(...),
        manager_b: int = Query(...),
    ) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        if not snap.state:
            raise HTTPException(status_code=503, detail="Live-data bygges. Prøv igjen om noen sekunder.")
        duel = compare_managers(snap.state, manager_a, manager_b)
        if not duel:
            raise HTTPException(status_code=400, detail="Duellen kunne ikke beregnes.")
        return {
            **rival_payload(duel, snap.state),
            "provisional": not snap.state.is_finished,
            "is_live": snap.state.is_live,
            "event_id": snap.state.event_id,
            "status": _status(runtime, snap),
        }

    @app.get("/api/tenant/{league_id}/analysis/ownership")
    def tenant_ownership(league_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        if not snap.state:
            return {"players": [], "league_size": len(snap.managers), "complete": False}
        payload = analysis_from_state(snap.state)
        return {
            "players": payload["ownership"],
            "league_size": payload["league_size"],
            "loaded_managers": payload.get("loaded_managers"),
            "complete": payload.get("complete", True),
        }

    @app.get("/api/tenant/{league_id}/analysis/captain")
    def tenant_captain(league_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        if not snap.state:
            return {"players": []}
        return {"players": analysis_from_state(snap.state)["captain"]}

    @app.get("/api/tenant/{league_id}/deep-analysis/transfers")
    def tenant_transfers(
        league_id: int,
        entry_id: int = Query(...),
        strategy: str = Query("balanced"),
        risk: int = Query(50),
        horizon: int = Query(5),
        target: str = Query(""),
        rival_id: int = Query(0),
        position: str = Query("all"),
    ) -> dict[str, Any]:
        runtime = _runtime(league_id)
        body = build_tenant_transfer_analysis(
            engine=runtime.engine,
            entry_id=entry_id,
            strategy=strategy,
            risk=risk,
            horizon=max(5, horizon),
            target=target,
            rival_id=rival_id,
            position=position,
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Analysen kunne ikke bygges.")
        return body

    @app.get("/api/tenant/{league_id}/deep-analysis/wildcard")
    def tenant_wildcard(
        league_id: int,
        entry_id: int = Query(...),
        strategy: str = Query("balanced"),
        risk: int = Query(50),
        horizon: int = Query(5),
    ) -> dict[str, Any]:
        runtime = _runtime(league_id)
        body = build_tenant_wildcard_analysis(
            engine=runtime.engine,
            entry_id=entry_id,
            strategy=strategy,
            risk=risk,
            horizon=max(5, horizon),
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Wildcard-analysen kunne ikke bygges.")
        return body

    @app.get("/api/tenant/{league_id}/league-intelligence")
    def tenant_intelligence(
        league_id: int,
        entry_id: int = Query(...),
        goal: str = Query("auto"),
    ) -> dict[str, Any]:
        runtime = _runtime(league_id)
        body = build_league_intelligence_v2(entry_id=entry_id, goal=goal, engine=runtime.engine)
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Liga-analysen kunne ikke bygges.")
        return body
