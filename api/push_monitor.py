from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from api.league_registry import league_registry
from api.push import DEFAULT_LEAGUE_ID, PushStore
from api.push_delivery import send_expo_messages
from api.serialize import analysis_from_state, squad_payload

MAIN_API = os.getenv("LRO_MAIN_API_URL", "https://lofthus-road-open-api.onrender.com").rstrip("/")
FPL_LIVE_URL = "https://fantasy.premierleague.com/api/event/{event_id}/live/"

EVENT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("goals_scored", "⚽", "scoret"),
    ("assists", "🅰️", "leverte målgivende"),
    ("red_cards", "🟥", "fikk rødt kort"),
    ("penalties_missed", "❌", "bommet på straffe"),
    ("own_goals", "😬", "scoret selvmål"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_json(url: str, timeout: int = 12) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Lofthus-Road-Open-Push/3.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GET {url} svarte {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET {url} feilet: {exc}") from exc
    if not isinstance(body, dict):
        raise RuntimeError(f"GET {url} ga ugyldig JSON")
    return body


def _nint(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _nfloat(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _player_stats(payload: dict[str, Any]) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}
    for row in payload.get("elements") or []:
        if not isinstance(row, dict):
            continue
        element = _nint(row.get("id"))
        stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
        if not element:
            continue
        values = {field: _nint(stats.get(field)) for field, _, _ in EVENT_FIELDS}
        values["total_points"] = _nint(stats.get("total_points"))
        out[element] = values
    return out


def _active_picks(profile: dict[str, Any]) -> dict[int, dict[str, Any]]:
    squad = profile.get("squad") if isinstance(profile.get("squad"), dict) else {}
    rows = list(squad.get("xi") or []) + list(squad.get("bench") or [])
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        element = _nint(row.get("element"))
        multiplier = _nint(row.get("multiplier"))
        if not element or multiplier <= 0:
            continue
        out[element] = {
            "player": str(row.get("player") or row.get("full_name") or f"Spiller {element}"),
            "multiplier": multiplier,
            "is_captain": bool(row.get("is_captain")),
            "is_triple_captain": bool(row.get("is_triple_captain")),
        }
    return out


def _ownership_index(payload: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], int]:
    league_size = max(1, _nint(payload.get("league_size")))
    out: dict[int, dict[str, Any]] = {}
    for row in payload.get("players") or []:
        if not isinstance(row, dict):
            continue
        element = _nint(row.get("element"))
        if element:
            out[element] = row
    return out, league_size


def _event_meta(field: str) -> tuple[str, str]:
    row = next((item for item in EVENT_FIELDS if item[0] == field), None)
    return (row[1], row[2]) if row else ("🔔", "ga ny utvikling")


def _impact_message(
    *,
    player: str,
    field: str,
    event_delta: int,
    multiplier: int,
    ownership_count: int,
    league_size: int,
    relative_swing: float,
) -> tuple[str, str]:
    icon, phrase = _event_meta(field)
    count = f" {event_delta} ganger" if event_delta > 1 else ""
    ownership = f"{ownership_count} av {league_size} i ligaen eier ham."
    if multiplier >= 3:
        own = " Han teller x3 for deg."
    elif multiplier == 2:
        own = " Han teller x2 for deg."
    elif multiplier == 1:
        own = " Han teller for deg."
    else:
        own = " Du eier ham ikke."
    if abs(relative_swing) >= 0.05:
        sign = "+" if relative_swing > 0 else "−"
        impact = f" Relativt utslag: {sign}{abs(relative_swing):.1f} poeng mot ligaen."
    else:
        impact = ""
    return f"{icon} {player}", f"{player} {phrase}{count}. {ownership}{own}{impact}"


def _league_snapshot(league_id: int) -> tuple[dict[int, dict[str, Any]], int, Any | None]:
    runtime = league_registry.get(int(league_id))
    snap = runtime.engine.snapshot()
    if not snap.state:
        return {}, len(snap.managers) or 1, None
    ownership, size = _ownership_index(analysis_from_state(snap.state))
    return ownership, size, snap.state


class PushMonitor:
    def __init__(self, store: PushStore):
        self.store = store
        self.interval = max(15, _nint(os.getenv("LRO_PUSH_POLL_SECONDS", "25")) or 25)
        self._lock = threading.Lock()
        self._started = False
        self._last_event_id = 0
        self._stats: dict[int, dict[str, int]] = {}
        self._status: dict[str, Any] = {
            "running": False,
            "last_poll": None,
            "last_error": None,
            "last_event_id": 0,
            "last_changes": 0,
            "last_sent": 0,
            "last_failed": 0,
            "last_http_batches": 0,
            "invalid_tokens_removed": 0,
            "leagues_checked": 0,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._status["running"] = True
        threading.Thread(target=self._loop, name="lofthus-push-monitor", daemon=True).start()

    def _set_status(self, **values: Any) -> None:
        with self._lock:
            self._status.update(values)

    def _loop(self) -> None:
        time.sleep(3)
        while True:
            try:
                self.poll_once()
            except Exception as exc:  # pragma: no cover - network guard
                self._set_status(last_poll=_now(), last_error=str(exc)[:500])
            time.sleep(self.interval)

    def poll_once(self) -> dict[str, Any]:
        subscribers = [
            row
            for row in self.store.list()
            if row.get("enabled", True)
            and row.get("entry_id")
            and bool((row.get("prefs") or {}).get("personal", True))
            and bool((row.get("prefs") or {}).get("live_events", True))
        ]
        if not subscribers:
            self._set_status(
                last_poll=_now(),
                last_error=None,
                last_changes=0,
                last_sent=0,
                last_failed=0,
                last_http_batches=0,
                invalid_tokens_removed=0,
                leagues_checked=0,
            )
            return self.status()

        # FPL's event clock is global, so one lightweight status call is enough to
        # decide whether player-live polling is necessary for every mini-league.
        status = _get_json(f"{MAIN_API}/api/status")
        event_id = _nint(status.get("event_id"))
        is_live = bool(status.get("is_live"))
        if not event_id or not is_live:
            if event_id and event_id != self._last_event_id:
                self._last_event_id = event_id
                self._stats = {}
            self._set_status(
                last_poll=_now(),
                last_error=None,
                last_event_id=event_id,
                last_changes=0,
                last_sent=0,
                last_failed=0,
                last_http_batches=0,
                invalid_tokens_removed=0,
                leagues_checked=0,
            )
            return self.status()

        live = _get_json(FPL_LIVE_URL.format(event_id=event_id))
        current = _player_stats(live)

        if event_id != self._last_event_id or not self._stats:
            self._last_event_id = event_id
            self._stats = current
            self._set_status(
                last_poll=_now(),
                last_error=None,
                last_event_id=event_id,
                last_changes=0,
                last_sent=0,
                last_failed=0,
                last_http_batches=0,
                invalid_tokens_removed=0,
                leagues_checked=0,
            )
            return self.status()

        changes: list[tuple[int, str, int, int]] = []
        for element, now_stats in current.items():
            before = self._stats.get(element, {})
            point_delta = _nint(now_stats.get("total_points")) - _nint(before.get("total_points"))
            for field, _, _ in EVENT_FIELDS:
                delta = _nint(now_stats.get(field)) - _nint(before.get(field))
                if delta > 0:
                    changes.append((element, field, delta, point_delta))

        league_cache: dict[int, tuple[dict[int, dict[str, Any]], int, Any | None]] = {}
        picks_cache: dict[tuple[int, int], dict[int, dict[str, Any]]] = {}
        leagues_checked: set[int] = set()
        messages: list[dict[str, Any]] = []

        if changes:
            for sub in subscribers:
                entry_id = _nint(sub.get("entry_id"))
                league_id = _nint(sub.get("league_id")) or DEFAULT_LEAGUE_ID
                token = str(sub.get("expo_push_token") or "")
                if not entry_id or not token:
                    continue

                if league_id not in league_cache:
                    try:
                        league_cache[league_id] = _league_snapshot(league_id)
                        leagues_checked.add(league_id)
                    except Exception:
                        league_cache[league_id] = ({}, 1, None)
                ownership_by_element, league_size, state = league_cache[league_id]
                if state is None:
                    continue

                cache_key = (league_id, entry_id)
                if cache_key not in picks_cache:
                    try:
                        picks_cache[cache_key] = _active_picks({"squad": squad_payload(state, entry_id)})
                    except Exception:
                        picks_cache[cache_key] = {}
                picks = picks_cache[cache_key]

                for element, field, delta, point_delta in changes:
                    ownership = ownership_by_element.get(element, {})
                    pick = picks.get(element)
                    multiplier = _nint((pick or {}).get("multiplier"))
                    impact = state.player(element)
                    player = str((pick or {}).get("player") or ownership.get("player") or getattr(impact, "player", "") or f"Spiller {element}")
                    ownership_count = _nint(ownership.get("ownership_count"))
                    effective_ownership = _nfloat(ownership.get("effective_ownership_pct")) / 100.0
                    relative_swing = point_delta * (multiplier - effective_ownership)

                    # Own active players always matter. Non-owned players are only
                    # sent when the event has a material league impact for the user.
                    if multiplier <= 0 and abs(relative_swing) < 0.9:
                        continue

                    title, body = _impact_message(
                        player=player,
                        field=field,
                        event_delta=delta,
                        multiplier=multiplier,
                        ownership_count=ownership_count,
                        league_size=league_size,
                        relative_swing=relative_swing,
                    )
                    messages.append(
                        {
                            "to": token,
                            "title": title,
                            "body": body,
                            "data": {
                                "path": "/intel",
                                "league_id": league_id,
                                "entry_id": entry_id,
                                "element": element,
                                "event_id": event_id,
                                "event_type": field,
                                "relative_swing": round(relative_swing, 2),
                            },
                        }
                    )

        delivery = send_expo_messages(messages) if messages else {
            "accepted": 0,
            "failed": 0,
            "http_batches": 0,
            "invalid_tokens": [],
        }
        removed = 0
        for token in delivery.get("invalid_tokens") or []:
            try:
                if self.store.remove(str(token)):
                    removed += 1
            except Exception:
                continue

        self._stats = current
        self._set_status(
            last_poll=_now(),
            last_error=None,
            last_event_id=event_id,
            last_changes=len(changes),
            last_sent=_nint(delivery.get("accepted")),
            last_failed=_nint(delivery.get("failed")),
            last_http_batches=_nint(delivery.get("http_batches")),
            invalid_tokens_removed=removed,
            leagues_checked=len(leagues_checked),
        )
        return self.status()
