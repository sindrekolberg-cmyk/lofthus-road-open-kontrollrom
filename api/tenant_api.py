from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from api.league_experience_v2 import build_league_experience_v2
from api.league_intelligence_v2 import build_league_intelligence_v2
from api.league_registry import league_registry
from api.platform_store import platform_store
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
from api.service_cache import analysis_cache
from api.tenant_analysis import build_tenant_transfer_analysis, build_tenant_wildcard_analysis
from lro_analysis import nfloat, nint
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
    body["tenant"] = True
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


def _analysis_ttl(snap, *, slow: bool = False) -> int:
    if snap.state and snap.state.is_live:
        return 35 if slow else 20
    return 300 if slow else 90


def _analysis_key(runtime, snap, kind: str, *parts: Any) -> tuple[Any, ...]:
    return (runtime.league_id, snap.snapshot_id, kind, *parts)


def _ownership_payload(snap) -> dict[str, Any]:
    if not snap.state:
        return {"players": [], "league_size": len(snap.managers), "complete": False}
    payload = analysis_from_state(snap.state)
    by_element = {
        nint(row.get("id")): row
        for row in (snap.bootstrap.get("elements") or [])
        if nint(row.get("id"))
    }
    rows: list[dict[str, Any]] = []
    for source in payload.get("ownership") or []:
        row = dict(source)
        meta = by_element.get(nint(row.get("element")), {})
        league_pct = nfloat(row.get("ownership_pct"))
        global_pct = nfloat(meta.get("selected_by_percent"))
        form = nfloat(meta.get("form"))
        ppg = nfloat(meta.get("points_per_game"))
        xgi90 = nfloat(meta.get("expected_goal_involvements_per_90"))
        status = str(meta.get("status") or "a")
        rarity = max(0.0, 100.0 - league_pct) / 100.0
        differential = 100.0 * (1.0 if status == "a" else 0.55) * (
            0.48 * rarity
            + 0.19 * min(max(form / 10.0, 0.0), 1.0)
            + 0.17 * min(max(ppg / 8.0, 0.0), 1.0)
            + 0.16 * min(max(xgi90 / 0.9, 0.0), 1.0)
        )
        row.update(
            {
                "global_ownership_pct": round(global_pct, 1),
                "ownership_gap_pct": round(league_pct - global_pct, 1),
                "form": round(form, 1),
                "points_per_game": round(ppg, 1),
                "season_points": nint(meta.get("total_points")),
                "season_minutes": nint(meta.get("minutes")),
                "xgi_per90": round(xgi90, 3),
                "status": status,
                "differential_score": round(differential, 1),
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


def register_tenant_routes(app: FastAPI) -> None:
    if getattr(app.state, "tenant_routes_registered", False):
        return
    app.state.tenant_routes_registered = True

    @app.get("/api/platform/status")
    def platform_status() -> dict[str, Any]:
        return {
            "ok": True,
            "registry": league_registry.diagnostics(),
            "analysis_cache": analysis_cache.diagnostics(),
            "persistence": platform_store.diagnostics(),
        }

    @app.post("/api/profile")
    def save_profile(payload: dict[str, Any]) -> dict[str, Any]:
        installation_id = str(payload.get("installation_id") or "").strip()
        league_id = nint(payload.get("league_id"))
        entry_id = nint(payload.get("entry_id"))
        if not installation_id or not league_id or not entry_id:
            raise HTTPException(status_code=400, detail="Mangler installation_id, league_id eller entry_id.")
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        valid_entries = {row["entry"] for row in _manager_options(runtime, snap)}
        if entry_id not in valid_entries:
            raise HTTPException(status_code=400, detail="Manageren finnes ikke i denne ligaen.")
        try:
            record = platform_store.upsert_profile(
                installation_id,
                league_id=league_id,
                entry_id=entry_id,
                goal=str(payload.get("goal") or "auto"),
                app_version=str(payload.get("app_version") or ""),
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "profile": record, "durable": platform_store.durable}

    @app.get("/api/profile/{installation_id}")
    def get_profile(installation_id: str) -> dict[str, Any]:
        profile = platform_store.get_profile(installation_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profilen finnes ikke.")
        return {"ok": True, "profile": profile, "durable": platform_store.durable}

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
        key = _analysis_key(runtime, snap, "ownership")
        return analysis_cache.get_or_build(key, lambda: _ownership_payload(snap), _analysis_ttl(snap))

    @app.get("/api/tenant/{league_id}/analysis/differentials")
    def tenant_differentials(league_id: int) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        key = _analysis_key(runtime, snap, "differentials")
        def build() -> dict[str, Any]:
            payload = _ownership_payload(snap)
            players = sorted(
                payload.get("players") or [],
                key=lambda row: (-nfloat(row.get("differential_score")), -nfloat(row.get("xgi_per90")), str(row.get("player") or "")),
            )
            return {"players": players[:30], "league_size": payload.get("league_size"), "sources": payload.get("sources")}
        return analysis_cache.get_or_build(key, build, _analysis_ttl(snap))

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
        risk: int = Query(50, ge=0, le=100),
        horizon: int = Query(5, ge=5, le=10),
        target: str = Query(""),
        rival_id: int = Query(0),
        position: str = Query("all"),
    ) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        key = _analysis_key(runtime, snap, "transfers", entry_id, strategy, risk, horizon, target, rival_id, position)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_tenant_transfer_analysis(
                engine=runtime.engine,
                entry_id=entry_id,
                strategy=strategy,
                risk=risk,
                horizon=horizon,
                target=target,
                rival_id=rival_id,
                position=position,
            ),
            _analysis_ttl(snap, slow=True),
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Analysen kunne ikke bygges.")
        return body

    @app.get("/api/tenant/{league_id}/deep-analysis/wildcard")
    def tenant_wildcard(
        league_id: int,
        entry_id: int = Query(...),
        strategy: str = Query("balanced"),
        risk: int = Query(50, ge=0, le=100),
        horizon: int = Query(5, ge=5, le=10),
    ) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        key = _analysis_key(runtime, snap, "wildcard", entry_id, strategy, risk, horizon)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_tenant_wildcard_analysis(
                engine=runtime.engine,
                entry_id=entry_id,
                strategy=strategy,
                risk=risk,
                horizon=horizon,
            ),
            _analysis_ttl(snap, slow=True),
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
        snap = runtime.engine.snapshot()
        key = _analysis_key(runtime, snap, "intelligence-v2", entry_id, goal)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_league_intelligence_v2(entry_id=entry_id, goal=goal, engine=runtime.engine),
            _analysis_ttl(snap, slow=True),
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Liga-analysen kunne ikke bygges.")
        return body

    @app.get("/api/tenant/{league_id}/experience")
    def tenant_experience(
        league_id: int,
        entry_id: int = Query(...),
        goal: str = Query("auto"),
    ) -> dict[str, Any]:
        runtime = _runtime(league_id)
        snap = runtime.engine.snapshot()
        key = _analysis_key(runtime, snap, "experience-v2", entry_id, goal)
        body = analysis_cache.get_or_build(
            key,
            lambda: build_league_experience_v2(entry_id=entry_id, goal=goal, engine=runtime.engine),
            _analysis_ttl(snap, slow=True),
        )
        if not body.get("ok"):
            raise HTTPException(status_code=404, detail=body.get("error") or "Ligaopplevelsen kunne ikke bygges.")
        return body
