from __future__ import annotations

import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.league_journal import league_journal
from lro_analysis import canonical_managers, nint
from lro_archive import SnapshotStore
from lro_config import LeagueConfig, load_config
from lro_fpl import FPLClient, current_event_id, finished_event_ids
from lro_history import HistoryStore
from lro_league import auto_monthly_rows, effective_states
from lro_live import LiveState, build_live_state
from lro_newsroom import generate_candidates, merge_persistent_stories
from lro_pulse import PulseHub, diff_live_states


APP_VERSION = "lofthus-road-open-api-v2"


@dataclass
class RequestSnapshot:
    """One consistent live truth for a single API request."""

    bootstrap: dict
    managers: list[dict]
    errors: list[str]
    state: LiveState | None
    histories: dict[int, dict] | None
    snapshot_id: str
    generated_at: str
    seq: int = 0

    def meta(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "generated_at": self.generated_at,
            "gw": self.state.event_id if self.state else 0,
            "phase": self.state.event_status if self.state else "pre",
            "is_live": bool(self.state and self.state.is_live),
            "is_finished": bool(self.state and self.state.is_finished),
            "source_updated_at": self.state.fetched_at.isoformat() if self.state else None,
            "seq": self.seq,
        }


class AppEngine:
    """Process-wide live truth. Independent of Streamlit cache."""

    def __init__(
        self,
        config: LeagueConfig | None = None,
        client: FPLClient | None = None,
        *,
        eager: bool = False,
        refresh_seconds: int = 10,
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
        self._month_rows_key: tuple | None = None
        self._journal_marked: set[tuple[int, str]] = set()
        self.pulse = PulseHub()
        self._pulse_thread: threading.Thread | None = None

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
                self.client.invalidate_picks(refreshed.event_id)
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

    def _signature(self, state: LiveState | None) -> tuple:
        if not state:
            return ()
        managers = tuple(
            (m.entry, m.live_total_points, m.live_rank, m.live_gw_points, m.players_remaining, m.captain_element)
            for m in sorted(state.manager_live, key=lambda row: row.entry)
        )
        players = tuple((p.element, p.event_points, p.fixture_status) for p in state.player_impacts[:80])
        fixtures = tuple(
            (
                int(f.get("id") or 0),
                int(f.get("team_h_score") or 0),
                int(f.get("team_a_score") or 0),
                int(f.get("minutes") or 0),
                bool(f.get("started")),
                bool(f.get("finished")),
            )
            for f in (state.fixtures or [])
        )
        return (state.event_id, state.event_status, managers, players, fixtures)

    @staticmethod
    def _journal_kind(state: LiveState) -> str | None:
        if state.is_finished:
            return "verdict"
        # Picks are public after the deadline. `reveal` is first-write-wins in
        # LeagueJournal, so the first state adopted after deadline becomes the
        # frozen lineup reveal even as later live refreshes keep arriving.
        if state.is_live or state.event_status == "between_matches":
            return "reveal"
        return None

    def _schedule_journal(self, state: LiveState) -> None:
        kind = self._journal_kind(state)
        event_id = int(state.event_id or 0)
        if not kind or not event_id:
            return
        key = (event_id, kind)
        if key in self._journal_marked:
            return
        self._journal_marked.add(key)

        def write() -> None:
            try:
                league_journal.record(self, state, kind)
            except Exception:
                # Journal memory is useful but must never take the live engine
                # down. LeagueJournal itself already falls back to local JSON.
                pass

        threading.Thread(
            target=write,
            name=f"lro-journal-{self.config.league_id}-{event_id}-{kind}",
            daemon=True,
        ).start()

    def _adopt_live(self, state: LiveState | None) -> None:
        if state is None:
            return
        old = self._live_state
        if old is not None and self._signature(old) == self._signature(state):
            self._live_state = state
            return
        stamp = state.fetched_at.isoformat()
        snapshot_id = f"{stamp}:{len(state.manager_live)}:{state.event_id}:{self.pulse.seq + 1}"
        events = diff_live_states(old, state, snapshot_id)
        self._live_state = state
        self._schedule_journal(state)
        self.pulse.publish(
            {
                "type": "snapshot_updated",
                "snapshot_id": snapshot_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source_updated_at": stamp,
                "gw": state.event_id,
                "phase": state.event_status,
                "is_live": state.is_live,
                "stale": False,
            },
            events,
        )

    def start_pulse(self) -> None:
        if self._pulse_thread and self._pulse_thread.is_alive():
            return
        self._pulse_thread = threading.Thread(target=self._pulse_loop, name="lro-pulse", daemon=True)
        self._pulse_thread.start()

    def _pulse_loop(self) -> None:
        while True:
            try:
                state = self.live_state()
                delay = 8 if state and state.is_live else 40
            except Exception:
                delay = 20
            time.sleep(delay)

    def wait_pulse(self, last_seq: int, timeout: float = 15.0) -> tuple[int, dict[str, Any] | None]:
        return self.pulse.wait(last_seq, timeout)

    def live_state(self) -> LiveState | None:
        bootstrap, managers, _ = self.load_shell()
        if not managers or not bootstrap:
            return None
        if self.eager:
            with self._lock:
                if self._live_state is None:
                    self._adopt_live(self._build_full_live(managers, bootstrap))
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
                    self._adopt_live(future.result())
                except Exception:
                    pass
                self._live_future = None
            state = self._live_state
            if state is None:
                if self._live_future is None:
                    self._live_future = self._pool.submit(self._build_full_live, [dict(m) for m in managers], dict(bootstrap))
                return None
            age = (datetime.now(timezone.utc) - state.fetched_at).total_seconds()
            cadence = 8 if state.is_live else max(10, int(self.refresh_seconds))
            if age >= cadence and self._live_future is None:
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

    def auto_month_rows(self, bootstrap: dict | None = None) -> list[dict]:
        bootstrap = bootstrap if bootstrap is not None else self.load_shell()[0]
        key = tuple(finished_event_ids(bootstrap))
        with self._lock:
            if self._month_rows is not None and self._month_rows_key == key:
                return self._month_rows
        rows = auto_monthly_rows(self.client, self.history, self.config.league_id, bootstrap) if bootstrap else []
        with self._lock:
            self._month_rows = rows
            self._month_rows_key = key
        return rows

    def snapshot(self, *, include_histories: bool = True) -> RequestSnapshot:
        bootstrap, managers, errors = self.load_shell()
        state = self.live_state()
        histories = self.histories() if include_histories else self._histories
        generated = datetime.now(timezone.utc).isoformat()
        stamp = state.fetched_at.isoformat() if state else "none"
        seq = self.pulse.seq
        return RequestSnapshot(
            bootstrap=bootstrap,
            managers=managers,
            errors=list(errors),
            state=state,
            histories=histories,
            snapshot_id=f"{stamp}:{len(managers)}:{state.event_id if state else 0}:{seq}",
            generated_at=generated,
            seq=seq,
        )

    def light_snapshot(self) -> RequestSnapshot:
        """Snapshot for routes that do not need a full manager-history sweep."""
        return self.snapshot(include_histories=False)

    def manager_states(self, snap: RequestSnapshot | None = None):
        if snap is None:
            snap = self.snapshot()
        return effective_states(snap.managers, snap.state)

    def news(self, limit: int = 4, snap: RequestSnapshot | None = None):
        if snap is None:
            snap = self.snapshot()
        if not snap.state:
            return []
        candidates = generate_candidates(snap.state, snap.managers, snap.bootstrap, self.history, snap.histories)
        with self._lock:
            stories = merge_persistent_stories(candidates, self._newsroom, snap.state, limit=limit)
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
            self._month_rows = None
            self._month_rows_key = None
            self._journal_marked = set()
            self.eager = True
            self.pulse = PulseHub()

    def warmup(self) -> None:
        self.load_shell()
        if not self.eager:
            self.live_state()
            if os.getenv("LRO_WARM_HISTORIES", "0") == "1":
                self.histories()
        self.start_pulse()


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
