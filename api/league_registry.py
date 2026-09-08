from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.engine import AppEngine, get_engine
from lro_config import LeagueConfig, load_config
from lro_fpl import FPLClient, season_label


@dataclass
class LeagueRuntime:
    league_id: int
    name: str
    engine: AppEngine
    league_info: dict[str, Any]
    created_at: float
    last_used_at: float


class LeagueRuntimeRegistry:
    """Small in-process tenant registry for arbitrary FPL classic leagues.

    Lofthus keeps its existing engine and historical archive. Other leagues get a
    clean current-season engine with no Lofthus historical files mixed in. The
    shared FPL client lets bootstrap/fixture/player responses be cached across
    leagues instead of multiplying identical public API traffic.
    """

    def __init__(self, *, max_leagues: int = 8, idle_ttl_seconds: int = 3600):
        self.default_config = load_config()
        self.default_league_id = int(self.default_config.league_id)
        self.max_leagues = max(2, int(max_leagues))
        self.idle_ttl_seconds = max(300, int(idle_ttl_seconds))
        self.client = FPLClient(timeout=15)
        self._lock = threading.RLock()
        self._items: OrderedDict[int, LeagueRuntime] = OrderedDict()

    def _tenant_data_dir(self, league_id: int) -> Path:
        root = Path(__file__).resolve().parents[1]
        return root / "data" / "_leagues" / str(int(league_id))

    def _prune(self) -> None:
        now = time.time()
        expired = [
            league_id
            for league_id, runtime in self._items.items()
            if now - runtime.last_used_at > self.idle_ttl_seconds
        ]
        for league_id in expired:
            runtime = self._items.pop(league_id, None)
            if runtime is not None:
                try:
                    runtime.engine.close()
                except Exception:
                    pass

        while len(self._items) >= self.max_leagues:
            _league_id, runtime = self._items.popitem(last=False)
            try:
                runtime.engine.close()
            except Exception:
                pass

    def _default_runtime(self) -> LeagueRuntime:
        eng = get_engine()
        now = time.time()
        return LeagueRuntime(
            league_id=self.default_league_id,
            name=eng.config.name,
            engine=eng,
            league_info={"id": self.default_league_id, "name": eng.config.name},
            created_at=now,
            last_used_at=now,
        )

    def get(self, league_id: int) -> LeagueRuntime:
        league_id = int(league_id)
        if league_id <= 0:
            raise ValueError("Ugyldig liga-ID.")
        if league_id == self.default_league_id:
            return self._default_runtime()

        with self._lock:
            self._prune()
            cached = self._items.get(league_id)
            if cached is not None:
                cached.last_used_at = time.time()
                self._items.move_to_end(league_id)
                return cached

        bootstrap = self.client.bootstrap()
        league_info, managers, debug = self.client.league_managers(league_id)
        if not managers:
            detail = "; ".join(str(item) for item in (debug.get("errors") or []) if item)
            raise ValueError(detail or "Fant ingen managere i ligaen. Kontroller liga-ID-en.")

        info = dict(league_info or {})
        name = str(info.get("name") or f"FPL-liga {league_id}").strip()
        config = LeagueConfig(
            league_id=league_id,
            name=name,
            season_fallback=season_label(bootstrap),
            data_dir=self._tenant_data_dir(league_id),
            expected_managers=None,
        )
        engine = AppEngine(config=config, client=self.client, eager=False, refresh_seconds=15)
        # load_shell will reuse the shared client's hot cache from the validation
        # call above. Starting live_state here primes the expensive picks build in
        # the background without making onboarding wait for every manager.
        try:
            engine.live_state()
        except Exception:
            pass

        runtime = LeagueRuntime(
            league_id=league_id,
            name=name,
            engine=engine,
            league_info=info,
            created_at=time.time(),
            last_used_at=time.time(),
        )
        with self._lock:
            existing = self._items.get(league_id)
            if existing is not None:
                try:
                    engine.close()
                except Exception:
                    pass
                existing.last_used_at = time.time()
                self._items.move_to_end(league_id)
                return existing
            self._items[league_id] = runtime
            self._items.move_to_end(league_id)
        return runtime

    def connect_payload(self, league_id: int) -> dict[str, Any]:
        runtime = self.get(league_id)
        eng = runtime.engine
        bootstrap, managers, errors = eng.load_shell()
        state = eng.live_state()
        by_entry = {m.entry: m for m in eng.manager_states()}
        rows: list[dict[str, Any]] = []
        for raw in managers:
            try:
                entry = int(raw.get("entry") or 0)
            except Exception:
                entry = 0
            if not entry:
                continue
            live = by_entry.get(entry)
            rows.append(
                {
                    "entry": entry,
                    "manager": live.manager if live else str(raw.get("player_name") or ""),
                    "team": live.team if live else str(raw.get("entry_name") or ""),
                    "rank": live.live_rank if live else int(raw.get("rank") or 0),
                    "gw": live.live_gw_points if live else int(raw.get("event_total") or 0),
                    "total": live.live_total_points if live else int(raw.get("total") or 0),
                    "rank_change": live.live_rank_change if live else 0,
                    "players_remaining": live.players_remaining if live else 0,
                }
            )
        rows.sort(key=lambda row: (row.get("rank") or 10**9, str(row.get("manager") or "").casefold()))
        return {
            "ok": True,
            "league": {
                "id": runtime.league_id,
                "name": runtime.name,
                "size": len(rows),
                "season": season_label(bootstrap) if bootstrap else eng.config.season_fallback,
                "is_default": runtime.league_id == self.default_league_id,
            },
            "managers": rows,
            "live_ready": state is not None,
            "errors": list(errors or []),
        }


league_registry = LeagueRuntimeRegistry()
