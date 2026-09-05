from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from lro_analysis import canonical_managers, nint
from lro_config import LeagueConfig
from lro_fpl import FPLClient, current_event_id
from lro_history import HistoryStore
from lro_live import LiveState, build_live_state


@st.cache_resource
def get_client() -> FPLClient:
    return FPLClient(timeout=12)


@st.cache_resource
def get_history_store(data_dir: str, version: str) -> HistoryStore:
    # version deliberately participates in the cache key so code deploys never
    # keep an object built against an older set of fallbacks/corrections.
    return HistoryStore(data_dir)


@st.cache_resource
def _pool() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=3, thread_name_prefix="lro-v810")


@st.cache_resource
def _state_box() -> dict[str, Any]:
    return {
        "lock": threading.RLock(),
        "live_key": None,
        "live_state": None,
        "live_future": None,
        "histories_key": None,
        "histories": None,
        "histories_future": None,
    }


def load_shell(config: LeagueConfig, client: FPLClient, history: HistoryStore) -> tuple[dict, list[dict], list[str]]:
    errors: list[str] = []
    try:
        bootstrap = client.bootstrap()
    except Exception as exc:
        return {}, [], [str(exc)]
    try:
        _, managers, debug = client.league_managers(config.league_id)
        managers = canonical_managers(managers, history)
        errors.extend(str(x) for x in debug.get("errors", []) if x)
    except Exception as exc:
        managers = []
        errors.append(str(exc))
    return bootstrap, managers, errors


def _live_key(config: LeagueConfig, managers: list[dict], bootstrap: dict) -> tuple:
    event = current_event_id(bootstrap) or 0
    entries = tuple(sorted(nint(m.get("entry")) for m in managers if nint(m.get("entry"))))
    return (config.league_id, int(event), entries)


def _build_full_live(config: LeagueConfig, managers: list[dict], bootstrap: dict, version: str) -> LiveState:
    bg_client = FPLClient(timeout=10)
    history = HistoryStore(config.data_dir)
    return build_live_state(bg_client, [dict(m) for m in managers], history, config.league_id, bootstrap=dict(bootstrap))


def _picks_age_seconds(state: LiveState) -> float:
    raw = str((state.ownership or {}).get("_picks_fetched_at") or "")
    try:
        stamp = datetime.fromisoformat(raw)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds())
    except Exception:
        return 10**9


def _refresh_live(config: LeagueConfig, managers: list[dict], bootstrap: dict, state: LiveState) -> LiveState:
    bg_client = FPLClient(timeout=8)
    history = HistoryStore(config.data_dir)
    try:
        fresh_bootstrap = bg_client.bootstrap() or dict(bootstrap)
    except Exception:
        fresh_bootstrap = dict(bootstrap)

    # Cheap path: frozen picks + fresh event-live/fixtures. This is the normal
    # 20–30 second matchday refresh.
    refreshed = build_live_state(
        bg_client,
        [dict(m) for m in managers],
        history,
        config.league_id,
        bootstrap=fresh_bootstrap,
        ownership=state.ownership,
    )

    # Picks are nearly static after deadline, except for FPL's eventual autosubs
    # and captain fallback. Refresh all 63 only at meaningful boundaries or at a
    # deliberately slow cadence between matches.
    age = _picks_age_seconds(state)
    event_changed = refreshed.event_id != state.event_id
    left_live_play = state.is_live and not refreshed.is_live
    needs_autosub_sync = refreshed.event_status == "between_matches" and age >= 600
    finished_sync = refreshed.is_finished and age >= 120
    if event_changed or left_live_play or needs_autosub_sync or finished_sync:
        try:
            return build_live_state(
                bg_client,
                [dict(m) for m in managers],
                history,
                config.league_id,
                bootstrap=fresh_bootstrap,
                ownership=None,
            )
        except Exception:
            return refreshed
    return refreshed


def live_state_async(config: LeagueConfig, managers: list[dict], bootstrap: dict, version: str, refresh_seconds: int = 22) -> LiveState | None:
    """Stale-while-refresh state.

    First load starts the expensive 63-manager picks sweep in the background.
    Later calls return the last valid state immediately and refresh only the cheap
    live payload in a worker when it is old enough.
    """
    if not managers or not bootstrap:
        return None
    box = _state_box()
    key = _live_key(config, managers, bootstrap)
    with box["lock"]:
        if box.get("live_key") != key:
            box["live_key"] = key
            box["live_state"] = None
            box["live_future"] = _pool().submit(_build_full_live, config, [dict(m) for m in managers], dict(bootstrap), version)

        future: Future | None = box.get("live_future")
        if future is not None and future.done():
            try:
                box["live_state"] = future.result()
            except Exception:
                # Keep any previously valid state. A later call can try again.
                pass
            box["live_future"] = None

        state: LiveState | None = box.get("live_state")
        if state is None:
            if box.get("live_future") is None:
                box["live_future"] = _pool().submit(_build_full_live, config, [dict(m) for m in managers], dict(bootstrap), version)
            return None

        age = (datetime.now(timezone.utc) - state.fetched_at).total_seconds()
        if age >= max(10, int(refresh_seconds)) and box.get("live_future") is None:
            box["live_future"] = _pool().submit(_refresh_live, config, [dict(m) for m in managers], dict(bootstrap), state)
        return state


def _build_histories(managers: list[dict]) -> dict[int, dict]:
    client = FPLClient(timeout=9)
    entries = [nint(m.get("entry")) for m in managers if nint(m.get("entry"))]
    values, _ = client.histories_many(entries, max_workers=10)
    return values


def histories_async(managers: list[dict], bootstrap: dict) -> dict[int, dict] | None:
    if not managers:
        return None
    event = current_event_id(bootstrap) or 0
    entries = tuple(sorted(nint(m.get("entry")) for m in managers if nint(m.get("entry"))))
    key = (event, entries)
    box = _state_box()
    with box["lock"]:
        if box.get("histories_key") != key:
            box["histories_key"] = key
            box["histories"] = None
            box["histories_future"] = _pool().submit(_build_histories, [dict(m) for m in managers])
        future: Future | None = box.get("histories_future")
        if future is not None and future.done():
            try:
                box["histories"] = future.result()
            except Exception:
                box["histories"] = None
            box["histories_future"] = None
        return box.get("histories")


def runtime_debug() -> dict[str, Any]:
    box = _state_box()
    with box["lock"]:
        state: LiveState | None = box.get("live_state")
        return {
            "live_key": str(box.get("live_key")),
            "live_ready": state is not None,
            "live_refresh_running": bool(box.get("live_future") is not None),
            "histories_ready": box.get("histories") is not None,
            "histories_refresh_running": bool(box.get("histories_future") is not None),
            "live": state.to_debug() if state else None,
        }
