from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api.engine import AppEngine, RequestSnapshot, get_engine
from api.serialize import (
    analysis_from_state,
    compare_payload,
    fixture_payload,
    hall_of_fame_payload,
    history_store_payload,
    live_events_payload,
    manager_payload,
    manager_profile_payload,
    movers_payload,
    player_impact_payload,
    rival_payload,
    season_from_bootstrap,
    status_payload,
    story_payload,
)
from lro_analysis import nint
from lro_league import manager_name
from lro_membership import load_membership, membership_for
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
    return os.getenv(
        "LRO_CORS_ORIGIN_REGEX",
        r"https://([a-z0-9-]+\.)*vercel\.app",
    ).strip()


def _safe_warmup() -> None:
    try:
        get_engine().warmup()
    except Exception:
        pass


def create_app(engine: AppEngine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if os.getenv("LRO_API_WARMUP", "1") == "1" and engine is None:
            threading.Thread(target=_safe_warmup, name="lro-warmup", daemon=True).start()
        yield

    app = FastAPI(title="Lofthus Road Open API", version="2.0.0", lifespan=lifespan)
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

    def snap() -> RequestSnapshot:
        return engine_dep().snapshot()

    def status_from(s: RequestSnapshot) -> dict[str, Any]:
        eng = engine_dep()
        body = status_payload(
            name=eng.config.name,
            season=season_from_bootstrap(s.bootstrap, eng.config.season_fallback),
            state=s.state,
            managers=s.managers,
            live_ready=s.state is not None,
            histories_ready=s.histories is not None,
            errors=s.errors,
        )
        body.update(s.meta())
        return body

    def find_manager(s: RequestSnapshot, entry_id: int):
        return next((m for m in engine_dep().manager_states(s) if m.entry == int(entry_id)), None)

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "service": "lofthus-road-open"}

    @app.get("/")
    def root() -> dict[str, Any]:
        return {"ok": True, "service": "lofthus-road-open", "health": "/api/health"}

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return status_from(snap())

    @app.get("/api/league")
    def league() -> dict[str, Any]:
        s = snap()
        return {"status": status_from(s), "table": [manager_payload(m) for m in engine_dep().manager_states(s)]}

    @app.get("/api/live")
    def live() -> dict[str, Any]:
        s = snap()
        st = status_from(s)
        if not s.state:
            return {
                "status": st,
                "table": [manager_payload(m) for m in engine_dep().manager_states(s)],
                "gw_ranking": [],
                "fixtures": [],
                "player_impacts": [],
                "live_ready": False,
            }
        return {
            "status": st,
            "table": [manager_payload(m) for m in s.state.managers_by_rank()],
            "gw_ranking": [manager_payload(m) for m in s.state.gw_ranking()],
            "fixtures": fixture_payload(s.state, s.bootstrap),
            "player_impacts": [player_impact_payload(p) for p in s.state.player_impacts[:40]],
            "live_ready": True,
        }

    @app.get("/api/month")
    def month() -> dict[str, Any]:
        s = snap()
        eng = engine_dep()
        table = [manager_payload(m) for m in (s.state.month_ranking() if s.state else [])]
        calendar = history_store_payload(eng.history, eng.auto_month_rows(s.bootstrap)).get("monthly") or []
        return {
            "status": status_from(s),
            "month_name": s.state.month_name if s.state else "",
            "table": table,
            "previous": calendar,
        }

    @app.get("/api/managers")
    def managers() -> dict[str, Any]:
        s = snap()
        states = {m.entry: m for m in engine_dep().manager_states(s)}
        out = []
        for m in s.managers:
            entry = nint(m.get("entry"))
            live = states.get(entry)
            out.append({
                "entry": entry,
                "manager": live.manager if live else manager_name(m),
                "team": live.team if live else str(m.get("entry_name") or ""),
                "rank": live.live_rank if live else nint(m.get("rank")),
                "gw": live.live_gw_points if live else nint(m.get("event_total")),
                "total": live.live_total_points if live else nint(m.get("total")),
                "rank_change": live.live_rank_change if live else 0,
            })
        out.sort(key=lambda r: (r["rank"] or 10**9, r["manager"]))
        return {"managers": out, "status": status_from(s)}

    @app.get("/api/managers/{entry_id}")
    def manager_detail(entry_id: int) -> dict[str, Any]:
        s = snap()
        eng = engine_dep()
        m = find_manager(s, entry_id)
        if not m:
            raise HTTPException(status_code=404, detail="Manageren finnes ikke i ligaen.")
        body = manager_profile_payload(
            m=m,
            state=s.state,
            managers=s.managers,
            histories=s.histories,
            history=eng.history,
            auto_rows=eng.auto_month_rows(s.bootstrap),
        )
        members = load_membership(eng.config.data_dir)
        body["lofthus_membership"] = membership_for(members, entry_id=entry_id, manager=m.manager)
        body["status"] = status_from(s)
        return body

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
            "lofthus_membership": body.get("lofthus_membership"),
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
        manager_a: int = Query(...),
        manager_b: int = Query(...),
    ) -> dict[str, Any]:
        s = snap()
        if not s.state:
            raise HTTPException(status_code=503, detail="Live-data er ikke klare ennå.")
        duel = compare_managers(s.state, manager_a, manager_b)
        if not duel:
            raise HTTPException(status_code=400, detail="Duellen kunne ikke beregnes.")
        return {
            **rival_payload(duel, s.state),
            "suggested_rivals": auto_rivals(s.state, manager_a, limit=5),
            "provisional": not s.state.is_finished,
            "is_live": s.state.is_live,
            "event_id": s.state.event_id,
            "status": status_from(s),
        }

    @app.get("/api/compare")
    def compare(
        manager_a: int = Query(...),
        manager_b: int = Query(...),
    ) -> dict[str, Any]:
        s = snap()
        a = find_manager(s, manager_a)
        b = find_manager(s, manager_b)
        if not a or not b:
            raise HTTPException(status_code=404, detail="Begge managere må finnes i ligaen.")
        return {**compare_payload(a, b, s.state, s.managers, s.histories), "status": status_from(s)}

    @app.get("/api/history")
    def history() -> dict[str, Any]:
        eng = engine_dep()
        s = snap()
        return history_store_payload(eng.history, eng.auto_month_rows(s.bootstrap))

    @app.get("/api/hall-of-fame")
    def hall_of_fame() -> dict[str, Any]:
        eng = engine_dep()
        s = snap()
        auto = eng.auto_month_rows(s.bootstrap)
        hist = history_store_payload(eng.history, auto)
        return {
            "rows": hall_of_fame_payload(eng.history, auto),
            "overall": hist.get("overall") or [],
            "cup": hist.get("cup") or [],
            "monthly": hist.get("monthly") or [],
            "random": hist.get("random") or [],
        }

    @app.get("/api/monthly-history")
    def monthly_history() -> dict[str, Any]:
        eng = engine_dep()
        s = snap()
        return {"months": history_store_payload(eng.history, eng.auto_month_rows(s.bootstrap)).get("monthly") or []}

    @app.get("/api/news")
    def news() -> dict[str, Any]:
        s = snap()
        stories = [story_payload(st, s.state) for st in engine_dep().news(limit=4, snap=s)]
        seen: set[str] = set()
        unique = []
        for row in stories:
            key = str(row.get("key") or "")
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return {"stories": unique, "count": len(unique), "status": status_from(s)}

    @app.get("/api/players")
    def players() -> dict[str, Any]:
        s = snap()
        if not s.state:
            return {"players": []}
        return {"players": [player_impact_payload(p) for p in s.state.player_impacts]}

    @app.get("/api/players/popular")
    def players_popular() -> dict[str, Any]:
        s = snap()
        if not s.state:
            return {"players": []}
        ranked = sorted(
            s.state.player_impacts,
            key=lambda p: (p.ownership_count, p.captain_count, p.event_points, p.impact_score),
            reverse=True,
        )
        return {"players": [player_impact_payload(p) for p in ranked[:8]]}

    @app.get("/api/analysis/captain")
    def analysis_captain() -> dict[str, Any]:
        s = snap()
        if not s.state:
            return {"players": []}
        return {"players": analysis_from_state(s.state)["captain"]}

    @app.get("/api/analysis/ownership")
    def analysis_ownership() -> dict[str, Any]:
        s = snap()
        if not s.state:
            return {"players": []}
        return {"players": analysis_from_state(s.state)["ownership"]}

    @app.get("/api/analysis/chips")
    def analysis_chips() -> dict[str, Any]:
        s = snap()
        if not s.state:
            return {"chips": []}
        return {"chips": analysis_from_state(s.state)["chips"]}

    @app.get("/api/analysis/differentials")
    def analysis_differentials() -> dict[str, Any]:
        s = snap()
        if not s.state:
            return {"players": []}
        return {"players": analysis_from_state(s.state)["differentials"]}

    @app.get("/api/home")
    def home() -> dict[str, Any]:
        s = snap()
        eng = engine_dep()
        st = status_from(s)
        states = eng.manager_states(s)
        stories = [story_payload(item, s.state) for item in eng.news(limit=4, snap=s)]
        seen: set[str] = set()
        unique_stories = []
        for row in stories:
            key = str(row.get("key") or row.get("headline") or "")
            if key in seen:
                continue
            seen.add(key)
            unique_stories.append(row)
        hero_story = unique_stories[0] if unique_stories else None
        hero_player = None
        if s.state and hero_story and nint(hero_story.get("player_element")):
            impact = s.state.player(nint(hero_story.get("player_element")))
            if impact:
                hero_player = player_impact_payload(impact)
        month_table = [manager_payload(m) for m in (s.state.month_ranking()[:5] if s.state else [])]
        popular = []
        if s.state:
            ranked = sorted(
                s.state.player_impacts,
                key=lambda p: (p.ownership_count, p.captain_count, p.event_points),
                reverse=True,
            )
            popular = [player_impact_payload(p) for p in ranked[:6]]
        options = []
        by_live = {m.entry: m for m in states}
        for m in s.managers:
            entry = nint(m.get("entry"))
            if not entry:
                continue
            live = by_live.get(entry)
            options.append({
                "entry": entry,
                "manager": live.manager if live else manager_name(m),
                "team": live.team if live else str(m.get("entry_name") or ""),
                "rank": live.live_rank if live else nint(m.get("rank")),
                "gw": live.live_gw_points if live else nint(m.get("event_total")),
                "total": live.live_total_points if live else nint(m.get("total")),
                "rank_change": live.live_rank_change if live else 0,
            })
        options.sort(key=lambda r: r["manager"])
        return {
            "status": st,
            "hero": {"story": hero_story, "player": hero_player},
            "top5": [manager_payload(m) for m in states[:5]],
            "movers": movers_payload(states),
            "news": unique_stories,
            "popular": popular,
            "month": {"name": s.state.month_name if s.state else "", "table": month_table},
            "events": live_events_payload(s.state, s.bootstrap) if s.state else [],
            "managers": options,
            "pulse": {
                "gw": st.get("event_id") or 0,
                "label": st.get("event_status_label") or "",
                "is_live": bool(st.get("is_live")),
                "fixtures": (live_events_payload(s.state, s.bootstrap) if s.state else [])[:6],
            },
        }

    @app.get("/api/archive")
    def archive() -> dict[str, Any]:
        return {"snapshots": engine_dep().archive_index()}

    return app


app = create_app()
