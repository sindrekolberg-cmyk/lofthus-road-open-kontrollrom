from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.engine import AppEngine, get_engine
from api.serialize import (
    analysis_from_state,
    fixture_payload,
    hall_of_fame_payload,
    history_store_payload,
    manager_payload,
    manager_profile_payload,
    pick_hero,
    player_impact_payload,
    rival_payload,
    season_from_bootstrap,
    status_payload,
)
from lro_analysis import nint
from lro_league import manager_name
from lro_rival import auto_rivals, compare_managers


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


def create_app(engine: AppEngine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if os.getenv("LRO_API_WARMUP", "1") == "1" and engine is None:
            try:
                get_engine().warmup()
            except Exception:
                pass
        yield

    app = FastAPI(title="Lofthus Road Open API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_origin_regex=_cors_regex() or None,
        allow_credentials=False,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    def engine_dep() -> AppEngine:
        return engine or get_engine()

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "lofthus-road-open"}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        eng = engine_dep()
        bootstrap, managers, errors = eng.load_shell()
        state = eng.live_state()
        return status_payload(
            name=eng.config.name,
            season=season_from_bootstrap(bootstrap, eng.config.season_fallback),
            state=state,
            managers=managers,
            live_ready=state is not None,
            histories_ready=eng.histories() is not None,
            errors=errors,
        )

    def _status(eng: AppEngine) -> dict[str, Any]:
        bootstrap, managers, errors = eng.load_shell()
        state = eng.live_state()
        return status_payload(
            name=eng.config.name,
            season=season_from_bootstrap(bootstrap, eng.config.season_fallback),
            state=state,
            managers=managers,
            live_ready=state is not None,
            histories_ready=eng.histories() is not None,
            errors=errors,
        )

    @app.get("/api/league")
    def league() -> dict[str, Any]:
        eng = engine_dep()
        states = eng.manager_states()
        st = _status(eng)
        return {
            "status": st,
            "table": [manager_payload(m) for m in states],
        }

    @app.get("/api/live")
    def live() -> dict[str, Any]:
        eng = engine_dep()
        bootstrap, _, _ = eng.load_shell()
        state = eng.live_state()
        st = _status(eng)
        if not state:
            return {
                "status": st,
                "table": [manager_payload(m) for m in eng.manager_states()],
                "gw_ranking": [],
                "fixtures": [],
                "player_impacts": [],
                "live_ready": False,
            }
        return {
            "status": st,
            "table": [manager_payload(m) for m in state.managers_by_rank()],
            "gw_ranking": [manager_payload(m) for m in state.gw_ranking()],
            "fixtures": fixture_payload(state, bootstrap),
            "player_impacts": [player_impact_payload(p) for p in state.player_impacts[:40]],
            "live_ready": True,
        }

    @app.get("/api/month")
    def month() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        st = _status(eng)
        table = [manager_payload(m) for m in (state.month_ranking() if state else [])]
        calendar = history_store_payload(eng.history, eng.auto_month_rows()).get("monthly") or []
        return {
            "status": st,
            "month_name": state.month_name if state else "",
            "table": table,
            "previous": calendar,
        }

    @app.get("/api/managers")
    def managers() -> dict[str, Any]:
        eng = engine_dep()
        _, rows, _ = eng.load_shell()
        states = {m.entry: m for m in eng.manager_states()}
        out = []
        for m in rows:
            entry = nint(m.get("entry"))
            live = states.get(entry)
            out.append({
                "entry": entry,
                "manager": live.manager if live else manager_name(m),
                "team": live.team if live else str(m.get("entry_name") or ""),
                "rank": live.live_rank if live else nint(m.get("rank")),
            })
        out.sort(key=lambda r: (r["rank"] or 10**9, r["manager"]))
        return {"managers": out}

    def _find_manager(eng: AppEngine, entry_id: int):
        return next((m for m in eng.manager_states() if m.entry == int(entry_id)), None)

    @app.get("/api/managers/{entry_id}")
    def manager_detail(entry_id: int) -> dict[str, Any]:
        eng = engine_dep()
        m = _find_manager(eng, entry_id)
        if not m:
            raise HTTPException(status_code=404, detail="Manageren finnes ikke i ligaen.")
        _, managers, _ = eng.load_shell()
        return manager_profile_payload(
            m=m,
            state=eng.live_state(),
            managers=managers,
            histories=eng.histories(),
            history=eng.history,
            auto_rows=eng.auto_month_rows(),
        )

    @app.get("/api/managers/{entry_id}/squad")
    def manager_squad_route(entry_id: int) -> dict[str, Any]:
        body = manager_detail(entry_id)
        return {"entry": entry_id, "squad": body.get("squad"), "event_id": body.get("event_id")}

    @app.get("/api/managers/{entry_id}/history")
    def manager_history_route(entry_id: int) -> dict[str, Any]:
        body = manager_detail(entry_id)
        return {
            "entry": entry_id,
            "form": body.get("form"),
            "fpl_career": body.get("fpl_career"),
            "fpl_season": body.get("fpl_season"),
            "lofthus_overall": body.get("lofthus_overall"),
            "lofthus_best_finish": body.get("lofthus_best_finish"),
        }

    @app.get("/api/managers/{entry_id}/chips")
    def manager_chips_route(entry_id: int) -> dict[str, Any]:
        body = manager_detail(entry_id)
        return {"entry": entry_id, "chips": body.get("chips"), "active_chip": (body.get("manager") or {}).get("chip")}

    @app.get("/api/managers/{entry_id}/captain")
    def manager_captain_route(entry_id: int) -> dict[str, Any]:
        body = manager_detail(entry_id)
        squad = body.get("squad") or {}
        players = list(squad.get("xi") or []) + list(squad.get("bench") or [])
        captain = next((p for p in players if p.get("is_captain")), None)
        vice = next((p for p in players if p.get("is_vice_captain")), None)
        return {
            "entry": entry_id,
            "captain": captain,
            "vice": vice,
            "chip": (body.get("manager") or {}).get("chip") or "",
        }

    @app.get("/api/rival")
    def rival(
        manager_a: int = Query(..., description="Selected manager entry id"),
        manager_b: int = Query(..., description="Rival entry id"),
    ) -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        if not state:
            raise HTTPException(status_code=503, detail="Live-data er ikke klare ennå.")
        duel = compare_managers(state, manager_a, manager_b)
        if not duel:
            raise HTTPException(status_code=400, detail="Duellen kunne ikke beregnes.")
        suggested = auto_rivals(state, manager_a, limit=5)
        return {
            **rival_payload(duel),
            "suggested_rivals": suggested,
            "provisional": not state.is_finished,
            "is_live": state.is_live,
            "event_id": state.event_id,
        }

    @app.get("/api/history")
    def history() -> dict[str, Any]:
        eng = engine_dep()
        return history_store_payload(eng.history, eng.auto_month_rows())

    @app.get("/api/hall-of-fame")
    def hall_of_fame() -> dict[str, Any]:
        eng = engine_dep()
        return {"rows": hall_of_fame_payload(eng.history, eng.auto_month_rows())}

    @app.get("/api/monthly-history")
    def monthly_history() -> dict[str, Any]:
        eng = engine_dep()
        payload = history_store_payload(eng.history, eng.auto_month_rows())
        return {"months": payload.get("monthly") or []}

    @app.get("/api/news")
    def news() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        stories = []
        for s in eng.news(limit=4):
            row = s.to_dict()
            image_url = ""
            if state and s.player_element:
                impact = state.player(s.player_element)
                if impact:
                    image_url = impact.image_url
            row["image_url"] = image_url
            stories.append(row)
        return {"stories": stories, "count": len(stories)}

    @app.get("/api/players")
    def players() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        if not state:
            return {"players": []}
        return {"players": [player_impact_payload(p) for p in state.player_impacts]}

    @app.get("/api/players/popular")
    def players_popular() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        if not state:
            return {"players": []}
        ranked = sorted(
            state.player_impacts,
            key=lambda p: (p.ownership_count, p.captain_count, p.event_points, p.impact_score),
            reverse=True,
        )
        return {"players": [player_impact_payload(p) for p in ranked[:8]]}

    @app.get("/api/analysis/captain")
    def analysis_captain() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        if not state:
            return {"players": []}
        return {"players": analysis_from_state(state)["captain"]}

    @app.get("/api/analysis/ownership")
    def analysis_ownership() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        if not state:
            return {"players": []}
        return {"players": analysis_from_state(state)["ownership"]}

    @app.get("/api/analysis/chips")
    def analysis_chips() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        if not state:
            return {"chips": []}
        return {"chips": analysis_from_state(state)["chips"]}

    @app.get("/api/analysis/differentials")
    def analysis_differentials() -> dict[str, Any]:
        eng = engine_dep()
        state = eng.live_state()
        if not state:
            return {"players": []}
        return {"players": analysis_from_state(state)["differentials"]}

    @app.get("/api/home")
    def home() -> dict[str, Any]:
        eng = engine_dep()
        bootstrap, managers, _ = eng.load_shell()
        state = eng.live_state()
        st = _status(eng)
        table = [manager_payload(m) for m in eng.manager_states()[:5]]
        news_body = news()
        popular = players_popular()
        month_table = []
        if state:
            month_table = [manager_payload(m) for m in state.month_ranking()[:3]]
        options = []
        for m in managers:
            entry = nint(m.get("entry"))
            if entry:
                options.append({"entry": entry, "manager": manager_name(m), "team": str(m.get("entry_name") or "")})
        options.sort(key=lambda r: r["manager"])
        return {
            "status": st,
            "hero": pick_hero(state),
            "top5": table,
            "news": news_body.get("stories") or [],
            "popular": popular.get("players") or [],
            "month": {"name": state.month_name if state else "", "table": month_table},
            "managers": options,
        }

    @app.get("/api/archive")
    def archive() -> dict[str, Any]:
        eng = engine_dep()
        return {"snapshots": eng.archive_index()}

    return app


app = create_app()
