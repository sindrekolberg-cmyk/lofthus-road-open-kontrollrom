from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from api.push import PushStore, send_expo_push

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
            "User-Agent": "Lofthus-Road-Open-Push/1.0",
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


def _player_stats(payload: dict[str, Any]) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}
    for row in payload.get("elements") or []:
        if not isinstance(row, dict):
            continue
        element = _nint(row.get("id"))
        stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
        if not element:
            continue
        out[element] = {field: _nint(stats.get(field)) for field, _, _ in EVENT_FIELDS}
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


def _event_message(player: str, field: str, delta: int, multiplier: int) -> tuple[str, str]:
    meta = next((row for row in EVENT_FIELDS if row[0] == field), None)
    icon, phrase = (meta[1], meta[2]) if meta else ("🔔", "ga ny utvikling")
    count = f" {delta} ganger" if delta > 1 else ""
    mult = ""
    if multiplier == 3:
        mult = " Han teller x3 for deg."
    elif multiplier == 2:
        mult = " Han teller x2 for deg."
    title = f"{icon} {player}"
    body = f"{player} {phrase}{count}.{mult}"
    return title, body


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
            self._set_status(last_poll=_now(), last_error=None, last_changes=0, last_sent=0)
            return self.status()

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
            )
            return self.status()

        changes: list[tuple[int, str, int]] = []
        for element, now_stats in current.items():
            before = self._stats.get(element, {})
            for field, _, _ in EVENT_FIELDS:
                delta = _nint(now_stats.get(field)) - _nint(before.get(field))
                if delta > 0:
                    changes.append((element, field, delta))

        sent = 0
        profile_cache: dict[int, dict[str, Any]] = {}
        picks_cache: dict[int, dict[int, dict[str, Any]]] = {}
        if changes:
            for sub in subscribers:
                entry_id = _nint(sub.get("entry_id"))
                token = str(sub.get("expo_push_token") or "")
                if not entry_id or not token:
                    continue
                try:
                    if entry_id not in profile_cache:
                        profile_cache[entry_id] = _get_json(f"{MAIN_API}/api/managers/{entry_id}")
                        picks_cache[entry_id] = _active_picks(profile_cache[entry_id])
                    picks = picks_cache.get(entry_id, {})
                except RuntimeError:
                    continue

                for element, field, delta in changes:
                    pick = picks.get(element)
                    if not pick:
                        continue
                    player = str(pick.get("player") or f"Spiller {element}")
                    multiplier = _nint(pick.get("multiplier")) or 1
                    title, body = _event_message(player, field, delta, multiplier)
                    try:
                        send_expo_push(
                            [token],
                            title=title,
                            body=body,
                            data={
                                "path": f"/manager/{entry_id}",
                                "entry_id": entry_id,
                                "element": element,
                                "event_id": event_id,
                                "event_type": field,
                            },
                        )
                        sent += 1
                    except RuntimeError:
                        continue

        self._stats = current
        self._set_status(
            last_poll=_now(),
            last_error=None,
            last_event_id=event_id,
            last_changes=len(changes),
            last_sent=sent,
        )
        return self.status()
