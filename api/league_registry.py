from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.engine import AppEngine, RequestSnapshot, get_engine
from api.platform_store import platform_store
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
    """Process-local tenant manager for arbitrary FPL classic mini-leagues.

    The registry shares global FPL calls across tenants, keeps each mini-league's
    live ownership isolated, suppresses duplicate cold starts and evicts idle
    runtimes before they turn a small service into a thread farm.
    """

    def __init__(self, *, max_leagues: int | None = None, idle_ttl_seconds: int | None = None):
        self.default_config = load_config()
        self.default_league_id = int(self.default_config.league_id)
        self.max_leagues = max(2, int(max_leagues or os.getenv("LRO_TENANT_MAX_LEAGUES", "12") or 12))
        self.idle_ttl_seconds = max(
            300,
            int(idle_ttl_seconds or os.getenv("LRO_TENANT_IDLE_TTL_SECONDS", "3600") or 3600),
        )
        self.client = FPLClient(timeout=15)
        self._lock = threading.RLock()
        self._items: OrderedDict[int, LeagueRuntime] = OrderedDict()
        self._creating: dict[int, threading.Event] = {}
        self._creation_errors: dict[int, str] = {}
        self._created_total = 0
        self._evicted_total = 0
        self._default: LeagueRuntime | None = None

    def _tenant_data_dir(self, league_id: int) -> Path:
        root = Path(__file__).resolve().parents[1]
        return root / "data" / "_leagues" / str(int(league_id))

    @staticmethod
    def _close_runtime(runtime: LeagueRuntime) -> None:
        try:
            pool = getattr(runtime.engine, "_pool", None)
            if pool is not None:
                pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [
            league_id
            for league_id, runtime in self._items.items()
            if now - runtime.last_used_at > self.idle_ttl_seconds
        ]
        for league_id in expired:
            runtime = self._items.pop(league_id, None)
            if runtime is not None:
                self._close_runtime(runtime)
                self._evicted_total += 1
        while len(self._items) >= self.max_leagues:
            _league_id, runtime = self._items.popitem(last=False)
            self._close_runtime(runtime)
            self._evicted_total += 1

    def _default_runtime(self) -> LeagueRuntime:
        with self._lock:
            if self._default is None:
                eng = get_engine()
                now = time.time()
                self._default = LeagueRuntime(
                    league_id=self.default_league_id,
                    name=eng.config.name,
                    engine=eng,
                    league_info={"id": self.default_league_id, "name": eng.config.name},
                    created_at=now,
                    last_used_at=now,
                )
            self._default.last_used_at = time.time()
            return self._default

    @staticmethod
    def _light_snapshot(
        eng: AppEngine,
        bootstrap: dict[str, Any],
        managers: list[dict[str, Any]],
        errors: list[str],
        state: Any,
    ) -> RequestSnapshot:
        """Build an onboarding snapshot without fetching every manager history."""
        generated = datetime.now(timezone.utc).isoformat()
        stamp = state.fetched_at.isoformat() if state else "none"
        seq = eng.pulse.seq
        return RequestSnapshot(
            bootstrap=bootstrap,
            managers=managers,
            errors=list(errors),
            state=state,
            histories=None,
            snapshot_id=f"{stamp}:{len(managers)}:{state.event_id if state else 0}:{seq}",
            generated_at=generated,
            seq=seq,
        )

    def _build_runtime(self, league_id: int) -> LeagueRuntime:
        bootstrap = self.client.bootstrap()
        league_info, managers, debug = self.client.league_managers(league_id)
        if not managers:
            detail = "; ".join(str(item) for item in (debug.get("errors") or []) if item)
            raise ValueError(detail or "Fant ingen managere i ligaen. Kontroller liga-ID-en.")

        info = dict(league_info or {})
        name = str(info.get("name") or f"FPL-liga {league_id}").strip()
        season = season_label(bootstrap)
        config = LeagueConfig(
            league_id=league_id,
            name=name,
            season_fallback=season,
            data_dir=self._tenant_data_dir(league_id),
            expected_managers=None,
        )
        engine = AppEngine(config=config, client=self.client, eager=False, refresh_seconds=20)
        engine.load_shell()
        try:
            # Start the expensive picks/live build only. Histories are deliberately
            # lazy and are first requested by features that actually need them.
            engine.live_state()
        except Exception:
            pass

        platform_store.upsert_league(
            league_id,
            name=name,
            season=season,
            manager_count=len(managers),
            is_default=False,
            metadata={"source": "fpl-classic", "validation_errors": debug.get("errors") or []},
        )
        return LeagueRuntime(
            league_id=league_id,
            name=name,
            engine=engine,
            league_info=info,
            created_at=time.time(),
            last_used_at=time.time(),
        )

    def get(self, league_id: int) -> LeagueRuntime:
        league_id = int(league_id)
        if league_id <= 0:
            raise ValueError("Ugyldig liga-ID.")
        if league_id == self.default_league_id:
            return self._default_runtime()

        with self._lock:
            self._prune_locked()
            cached = self._items.get(league_id)
            if cached is not None:
                cached.last_used_at = time.time()
                self._items.move_to_end(league_id)
                return cached
            event = self._creating.get(league_id)
            if event is None:
                event = threading.Event()
                self._creating[league_id] = event
                self._creation_errors.pop(league_id, None)
                creator = True
            else:
                creator = False

        if not creator:
            event.wait(timeout=60)
            with self._lock:
                cached = self._items.get(league_id)
                if cached is not None:
                    cached.last_used_at = time.time()
                    self._items.move_to_end(league_id)
                    return cached
                error = self._creation_errors.get(league_id)
            raise ValueError(error or "Ligaen brukte for lang tid på å koble til. Prøv igjen.")

        runtime: LeagueRuntime | None = None
        try:
            runtime = self._build_runtime(league_id)
            with self._lock:
                self._prune_locked()
                self._items[league_id] = runtime
                self._items.move_to_end(league_id)
                self._created_total += 1
            return runtime
        except Exception as exc:
            if runtime is not None:
                self._close_runtime(runtime)
            with self._lock:
                self._creation_errors[league_id] = str(exc)[:500]
            if isinstance(exc, ValueError):
                raise
            raise ValueError(f"Kunne ikke koble til ligaen: {exc}") from exc
        finally:
            with self._lock:
                waiter = self._creating.pop(league_id, None)
                if waiter is not None:
                    waiter.set()

    def connect_payload(self, league_id: int) -> dict[str, Any]:
        runtime = self.get(league_id)
        eng = runtime.engine
        bootstrap, managers, errors = eng.load_shell()
        state = eng.live_state()
        snap = self._light_snapshot(eng, bootstrap, managers, errors, state)
        by_entry = {m.entry: m for m in eng.manager_states(snap)}
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
        season = season_label(bootstrap) if bootstrap else eng.config.season_fallback
        platform_store.upsert_league(
            runtime.league_id,
            name=runtime.name,
            season=season,
            manager_count=len(rows),
            is_default=runtime.league_id == self.default_league_id,
        )
        return {
            "ok": True,
            "league": {
                "id": runtime.league_id,
                "name": runtime.name,
                "size": len(rows),
                "season": season,
                "is_default": runtime.league_id == self.default_league_id,
            },
            "managers": rows,
            "live_ready": state is not None,
            "warming": state is None,
            "snapshot_id": snap.snapshot_id,
            "errors": list(errors or []),
        }

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            self._prune_locked()
            now = time.time()
            tenants = [
                {
                    "league_id": league_id,
                    "name": runtime.name,
                    "age_seconds": round(now - runtime.created_at, 1),
                    "idle_seconds": round(now - runtime.last_used_at, 1),
                }
                for league_id, runtime in self._items.items()
            ]
            creating = sorted(self._creating)
        return {
            "default_league_id": self.default_league_id,
            "active_tenants": len(tenants),
            "max_tenants": self.max_leagues,
            "idle_ttl_seconds": self.idle_ttl_seconds,
            "created_total": self._created_total,
            "evicted_total": self._evicted_total,
            "creating": creating,
            "tenants": tenants,
            "shared_fpl_client": self.client.diagnostics(),
        }


league_registry = LeagueRuntimeRegistry()
