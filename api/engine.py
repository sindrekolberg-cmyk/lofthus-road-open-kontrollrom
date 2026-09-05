from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lro_analysis import canonical_managers, nint
from lro_archive import SnapshotStore
from lro_config import LeagueConfig, load_config
from lro_fpl import FPLClient, current_event_id
from lro_history import HistoryStore
from lro_league import auto_monthly_rows, effective_states
from lro_live import LiveState, build_live_state
from lro_newsroom import generate_candidates, merge_persistent_stories


APP_VERSION = "lofthus-road-open-api-v1"


class AppEngine:
    """Process-wide live truth. Independent of Streamlit cache."""

    def __init__(
        self,
        config: LeagueConfig | None = None,
        client: FPLClient | None = None,
        *,
        eager: bool = False,
        refresh_seconds: int = 22,
    ):
        self.config = config or load_config()
        self.client = client or FPLClient(timeout=12)
        self.history = HistoryStore(self.config.data_dir)
        self.eager = eager
        self.refresh_seconds = refresh_seconds
        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="lro-api")
        self._bootstrap: dict = {}
        self._managers: list[dict] = []
        self._shell_errors: list[str] = []
        self._shell_at: float = 0.0
        self._live_key: tuple | None = None
        self._live_state: LiveState | None = None
        self._live_future: Future | None = None
        self._histories_key: tuple | None = None
        self._histories: dict[int, dict] | None = None
        self._histories_future: Future | None = None
        self._newsroom: list[dict[str, Any]] = []
        self._month_rows: list[dict] | None = None

    def load_shell(self, ttl: float = 90.0) -> tuple[dict, list[dict], list[str]]:
        now = datetime.now(timezone.utc).timestamp()
        with self._lock:
            if self._managers and self._bootstrap and now - self._shell_at < ttl:
                return self._bootstrap, self._managers, list(self._shell_errors)
        errors: list[str] = []
        try:
            bootstrap = self.client.bootstrap()
        except Exception as exc:
            bootstrap = {}
            errors.append(str(exc))
        managers: list[dict] = []
        if bootstrap:
            try:
                _, managers, debug = self.client.league_managers(self.config.league_id)
                managers = canonical_managers(managers, self.history)
                errors.extend(str(x) for x in debug.get("errors", []) if x)
            except Exception as exc:
                managers = []
                errors.append(str(exc))
        with self._lock:
            self._bootstrap = bootstrap or {}
            self._managers = managers
            self._shell_errors = errors
            self._shell_at = now
        return self._bootstrap, self._managers, list(errors)

    def _live_cache_key(self, managers: list[dict], bootstrap: dict) -> tuple:
        event = current_event_id(bootstrap) or 0
        entries = tuple(sorted(nint(m.get("entry")) for m in managers if nint(m.get("entry"))))
        return (self.config.league_id, int(event), entries)

    def _build_full_live(self, managers: list[dict], bootstrap: dict) -> LiveState:
        return build_live_state(
            self.client,
            [dict(m) for m in managers],
            self.history,
            self.config.league_id,
            bootstrap=dict(bootstrap),
        )

    def _picks_age_seconds(self, state: LiveState) -> float:
        raw = str((state.ownership or {}).get("_picks_fetched_at") or "")
        try:
            stamp = datetime.fromisoformat(raw)
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds())
        except Exception:
            return 10**9

    def _refresh_live(self, managers: list[dict], bootstrap: dict, state: LiveState) -> LiveState:
        try:
            fresh_bootstrap = self.client.bootstrap() or dict(bootstrap)
        except Exception:
            fresh_bootstrap = dict(bootstrap)
        refreshed = build_live_state(
            self.client,
            [dict(m) for m in managers],
            self.history,
            self.config.league_id,
            bootstrap=fresh_bootstrap,
            ownership=state.ownership,
        )
        age = self._picks_age_seconds(state)
        event_changed = refreshed.event_id != state.event_id
        left_live_play = state.is_live and not refreshed.is_live
        needs_autosub_sync = refreshed.event_status == "between_matches" and age >= 600
        finished_sync = refreshed.is_finished and age >= 120
        if event_changed or left_live_play or needs_autosub_sync or finished_sync:
            try:
                return build_live_state(
                    self.client,
                    [dict(m) for m in managers],
                    self.history,
                    self.config.league_id,
                    bootstrap=fresh_bootstrap,
                    ownership=None,
                )
            except Exception:
                return refreshed
        return refreshed

    def live_state(self) -> LiveState | None:
        bootstrap, managers, _ = self.load_shell()
        if not managers or not bootstrap:
            return None
        if self.eager:
            with self._lock:
                if self._live_state is None:
                    self._live_state = self._build_full_live(managers, bootstrap)
                return self._live_state
        key = self._live_cache_key(managers, bootstrap)
        with self._lock:
            if self._live_key != key:
                self._live_key = key
                self._live_state = None
                self._live_future = self._pool.submit(self._build_full_live, [dict(m) for m in managers], dict(bootstrap))
            future = self._live_future
            if future is not None and future.done():
                try:
                    self._live_state = future.result()
                except Exception:
                    pass
                self._live_future = None
            state = self._live_state
            if state is None:
                if self._live_future is None:
                    self._live_future = self._pool.submit(self._build_full_live, [dict(m) for m in managers], dict(bootstrap))
                return None
            age = (datetime.now(timezone.utc) - state.fetched_at).total_seconds()
            if age >= max(10, int(self.refresh_seconds)) and self._live_future is None:
                self._live_future = self._pool.submit(
                    self._refresh_live, [dict(m) for m in managers], dict(bootstrap), state
                )
            return state

    def histories(self) -> dict[int, dict] | None:
        bootstrap, managers, _ = self.load_shell()
        if not managers:
            return None
        if self.eager:
            with self._lock:
                if self._histories is None:
                    values, _ = self.client.histories_many(
                        [nint(m.get("entry")) for m in managers if nint(m.get("entry"))],
                        max_workers=10,
                    )
                    self._histories = values
                return self._histories
        event = current_event_id(bootstrap) or 0
        entries = tuple(sorted(nint(m.get("entry")) for m in managers if nint(m.get("entry"))))
        key = (event, entries)
        with self._lock:
            if self._histories_key != key:
                self._histories_key = key
                self._histories = None
                self._histories_future = self._pool.submit(self._build_histories, [dict(m) for m in managers])
            future = self._histories_future
            if future is not None and future.done():
                try:
                    self._histories = future.result()
                except Exception:
                    self._histories = None
                self._histories_future = None
            return self._histories

    def _build_histories(self, managers: list[dict]) -> dict[int, dict]:
        entries = [nint(m.get("entry")) for m in managers if nint(m.get("entry"))]
        values, _ = self.client.histories_many(entries, max_workers=10)
        return values

    def auto_month_rows(self) -> list[dict]:
        bootstrap, _, _ = self.load_shell()
        with self._lock:
            if self._month_rows is not None:
                return self._month_rows
        rows = auto_monthly_rows(self.client, self.history, self.config.league_id, bootstrap) if bootstrap else []
        with self._lock:
            self._month_rows = rows
        return rows

    def manager_states(self):
        _, managers, _ = self.load_shell()
        return effective_states(managers, self.live_state())

    def news(self, limit: int = 4):
        bootstrap, managers, _ = self.load_shell()
        state = self.live_state()
        if not state:
            return []
        candidates = generate_candidates(state, managers, bootstrap, self.history, self.histories())
        with self._lock:
            stories = merge_persistent_stories(candidates, self._newsroom, state, limit=limit)
            self._newsroom = [s.to_dict() for s in stories]
        return stories

    def archive_index(self) -> list[dict[str, Any]]:
        store = SnapshotStore(Path(self.config.data_dir) / "snapshots")
        out = []
        for path in store.list_snapshots():
            out.append({"file": path.name})
        return out

    def seed(
        self,
        bootstrap: dict,
        managers: list[dict],
        state: LiveState | None = None,
        histories: dict[int, dict] | None = None,
        errors: list[str] | None = None,
    ) -> None:
        """Test helper: inject shell + live truth without touching FPL."""
        with self._lock:
            self._bootstrap = dict(bootstrap or {})
            self._managers = canonical_managers(list(managers or []), self.history)
            self._shell_errors = list(errors or [])
            self._shell_at = datetime.now(timezone.utc).timestamp()
            self._live_state = state
            self._histories = histories if histories is not None else {}
            self.eager = True

    def warmup(self) -> None:
        self.load_shell()
        if not self.eager:
            self.live_state()
            self.histories()


_ENGINE: AppEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_engine() -> AppEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = AppEngine()
        return _ENGINE


def set_engine(engine: AppEngine | None) -> None:
    global _ENGINE
    with _ENGINE_LOCK:
        _ENGINE = engine
