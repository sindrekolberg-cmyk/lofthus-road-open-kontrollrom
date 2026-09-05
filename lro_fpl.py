from __future__ import annotations

import copy
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Iterable

import requests

BASE_URL = "https://fantasy.premierleague.com/api"
DEFAULT_LEAGUE_ID = 25220
HEADERS = {"User-Agent": "Mozilla/5.0 Lofthus Road Open V810"}
POSITION_LABELS = {1: "Keeper", 2: "Forsvar", 3: "Midtbane", 4: "Angrep"}


class FPLError(RuntimeError):
    pass


@dataclass
class CacheItem:
    fetched_at: float
    expires_at: float
    value: Any


class FPLClient:
    """Small FPL API client with an in-process TTL cache.

    The cache intentionally lives outside Streamlit. A Streamlit rerun reuses the
    imported module in the same process, so this prevents a selectbox change from
    firing dozens of identical public API requests.
    """

    def __init__(self, base_url: str = BASE_URL, timeout: int = 25):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._cache: dict[str, CacheItem] = {}
        self._lock = threading.RLock()
        self.request_count = 0
        self.cache_hits = 0
        self.stale_fallbacks = 0
        self.last_errors: list[str] = []

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    def _get_cached(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            item = self._cache.get(key)
            if item and item.expires_at > now:
                self.cache_hits += 1
                return copy.deepcopy(item.value)
        return None

    def _get_stale(self, key: str, max_stale: int = 1800) -> Any | None:
        now = time.time()
        with self._lock:
            item = self._cache.get(key)
            if item and now - item.expires_at <= max(0, int(max_stale)):
                return copy.deepcopy(item.value)
        return None

    def _set_cached(self, key: str, value: Any, ttl: int) -> None:
        now = time.time()
        with self._lock:
            self._cache[key] = CacheItem(now, now + max(1, int(ttl)), copy.deepcopy(value))

    def get_json(self, path: str, ttl: int = 300, stale_if_error: int = 1800) -> Any:
        path = path if path.startswith("/") else f"/{path}"
        key = f"GET:{path}"
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        url = f"{self.base_url}{path}"
        try:
            self.request_count += 1
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            value = response.json()
        except Exception as exc:
            message = f"FPL-kall feilet: {path}: {exc}"
            with self._lock:
                self.last_errors = (self.last_errors + [message])[-20:]
            stale = self._get_stale(key, stale_if_error)
            if stale is not None:
                self.stale_fallbacks += 1
                return stale
            raise FPLError(message) from exc
        self._set_cached(key, value, ttl)
        return copy.deepcopy(value)

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            ages = [max(0.0, now - item.fetched_at) for item in self._cache.values()]
            return {
                "request_count": int(self.request_count),
                "cache_hits": int(self.cache_hits),
                "stale_fallbacks": int(self.stale_fallbacks),
                "cache_items": len(self._cache),
                "oldest_cache_age_seconds": round(max(ages), 1) if ages else 0.0,
                "last_errors": list(self.last_errors[-5:]),
            }

    def bootstrap(self) -> dict:
        # Event flags matter during matchday, so bootstrap cannot sit stale for ten minutes.
        data = self.get_json("/bootstrap-static/", ttl=90, stale_if_error=1800)
        return data if isinstance(data, dict) else {}

    def fixtures(self, event_id: int | None = None) -> list[dict]:
        path = "/fixtures/" if event_id is None else f"/fixtures/?event={int(event_id)}"
        data = self.get_json(path, ttl=25 if event_id else 300, stale_if_error=900)
        return data if isinstance(data, list) else []

    def event_live(self, event_id: int) -> dict:
        data = self.get_json(f"/event/{int(event_id)}/live/", ttl=22, stale_if_error=300)
        return data if isinstance(data, dict) else {}

    def entry_picks(self, entry_id: int, event_id: int) -> dict:
        # Picks are effectively frozen after deadline. A long TTL prevents navigation
        # between local pages from creating a 63-request storm.
        data = self.get_json(f"/entry/{int(entry_id)}/event/{int(event_id)}/picks/", ttl=900, stale_if_error=7200)
        return data if isinstance(data, dict) else {}

    def entry_history(self, entry_id: int) -> dict:
        data = self.get_json(f"/entry/{int(entry_id)}/history/", ttl=900, stale_if_error=21600)
        return data if isinstance(data, dict) else {}

    def league_phase_standings(self, league_id: int, phase_id: int) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while page <= 100:
            payload = self.get_json(
                f"/leagues-classic/{int(league_id)}/standings/"
                f"?page_standings={page}&page_new_entries=1&phase={int(phase_id)}",
                ttl=180,
            )
            standings = (payload or {}).get("standings", {}) or {}
            rows.extend(standings.get("results", []) or [])
            if not standings.get("has_next"):
                break
            page += 1
        return rows

    @staticmethod
    def _manager_row(row: dict, source: str) -> dict:
        entry = row.get("entry") or row.get("entry_id") or row.get("id")
        player_name = row.get("player_name") or row.get("manager_name") or row.get("player")
        if not player_name:
            player_name = f"{row.get('player_first_name') or ''} {row.get('player_last_name') or ''}".strip()
        return {
            "source": source,
            "entry": _int(entry),
            "player_name": str(player_name or "Ukjent manager").strip(),
            "entry_name": str(row.get("entry_name") or row.get("team_name") or row.get("name") or "Ukjent lag").strip(),
            "rank": _int_or_none(row.get("rank")),
            "last_rank": _int_or_none(row.get("last_rank")),
            "event_total": _int_or_none(row.get("event_total")),
            "total": _int_or_none(row.get("total")),
            "joined_time": row.get("joined_time"),
            "raw": row,
        }

    def league_managers(self, league_id: int = DEFAULT_LEAGUE_ID) -> tuple[dict | None, list[dict], dict]:
        league_info: dict | None = None
        by_entry: dict[int, dict] = {}
        debug = {"standings_pages": 0, "new_entries_pages": 0, "errors": []}

        page = 1
        while page <= 100:
            try:
                payload = self.get_json(
                    f"/leagues-classic/{int(league_id)}/standings/"
                    f"?page_standings={page}&page_new_entries=1",
                    ttl=120,
                )
            except FPLError as exc:
                debug["errors"].append(str(exc))
                break
            league_info = (payload or {}).get("league") or league_info
            standings = (payload or {}).get("standings", {}) or {}
            for row in standings.get("results", []) or []:
                item = self._manager_row(row, "tabell")
                if item["entry"]:
                    by_entry[int(item["entry"])] = item
            debug["standings_pages"] += 1
            if not standings.get("has_next"):
                break
            page += 1

        page = 1
        while page <= 100:
            try:
                payload = self.get_json(
                    f"/leagues-classic/{int(league_id)}/standings/"
                    f"?page_standings=1&page_new_entries={page}",
                    ttl=120,
                )
            except FPLError as exc:
                debug["errors"].append(str(exc))
                break
            league_info = (payload or {}).get("league") or league_info
            new_entries = (payload or {}).get("new_entries", {}) or {}
            for row in new_entries.get("results", []) or []:
                item = self._manager_row(row, "påmeldt")
                if item["entry"] and int(item["entry"]) not in by_entry:
                    by_entry[int(item["entry"])] = item
            debug["new_entries_pages"] += 1
            if not new_entries.get("has_next"):
                break
            page += 1

        managers = list(by_entry.values())
        managers.sort(key=lambda x: (x.get("rank") or 10**9, str(x.get("player_name") or "").casefold()))
        debug["manager_count"] = len(managers)
        return league_info, managers, debug

    def picks_many(
        self,
        entries: Iterable[int],
        event_id: int,
        max_workers: int = 8,
    ) -> tuple[dict[int, dict], dict[int, str]]:
        ids = sorted({int(e) for e in entries if _int(e) > 0})
        values: dict[int, dict] = {}
        errors: dict[int, str] = {}
        if not ids:
            return values, errors
        workers = min(max(1, int(max_workers)), 10, len(ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.entry_picks, entry, int(event_id)): entry for entry in ids}
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    values[entry] = future.result()
                except Exception as exc:
                    errors[entry] = str(exc)
        return values, errors

    def histories_many(
        self,
        entries: Iterable[int],
        max_workers: int = 8,
    ) -> tuple[dict[int, dict], dict[int, str]]:
        ids = sorted({int(e) for e in entries if _int(e) > 0})
        values: dict[int, dict] = {}
        errors: dict[int, str] = {}
        if not ids:
            return values, errors
        workers = min(max(1, int(max_workers)), 10, len(ids))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.entry_history, entry): entry for entry in ids}
            for future in as_completed(futures):
                entry = futures[future]
                try:
                    values[entry] = future.result()
                except Exception as exc:
                    errors[entry] = str(exc)
        return values, errors


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def season_label(bootstrap: dict) -> str:
    for event in bootstrap.get("events", []) or []:
        deadline = str(event.get("deadline_time") or "")
        if len(deadline) >= 4 and deadline[:4].isdigit():
            year = int(deadline[:4])
            return f"{year}/{str(year + 1)[-2:]}"
    return "2026/27"


def short_season_label(bootstrap: dict) -> str:
    value = season_label(bootstrap)
    if len(value) == 7 and value[:4].isdigit():
        return f"{value[2:4]}/{value[-2:]}"
    return value


def current_event_id(bootstrap: dict) -> int | None:
    events = bootstrap.get("events", []) or []
    current = next((e for e in events if e.get("is_current")), None)
    if current:
        return _int(current.get("id")) or None
    finished = [_int(e.get("id")) for e in events if e.get("finished") and _int(e.get("id"))]
    if finished:
        return max(finished)
    nxt = next((e for e in events if e.get("is_next")), None)
    return _int(nxt.get("id")) or None if nxt else None


def next_event_id(bootstrap: dict) -> int | None:
    nxt = next((e for e in bootstrap.get("events", []) or [] if e.get("is_next")), None)
    if nxt:
        return _int(nxt.get("id")) or None
    current = current_event_id(bootstrap)
    events = {_int(e.get("id")): e for e in bootstrap.get("events", []) or []}
    if current and current + 1 in events:
        return current + 1
    return None


def player_catalog(bootstrap: dict) -> dict[int, dict]:
    teams = {
        _int(team.get("id")): {
            "name": str(team.get("name") or ""),
            "short_name": str(team.get("short_name") or team.get("name") or ""),
            "strength": _int(team.get("strength")),
            "strength_overall_home": _int(team.get("strength_overall_home")),
            "strength_overall_away": _int(team.get("strength_overall_away")),
            "strength_attack_home": _int(team.get("strength_attack_home")),
            "strength_attack_away": _int(team.get("strength_attack_away")),
            "strength_defence_home": _int(team.get("strength_defence_home")),
            "strength_defence_away": _int(team.get("strength_defence_away")),
        }
        for team in bootstrap.get("teams", []) or []
        if _int(team.get("id"))
    }
    out: dict[int, dict] = {}
    for p in bootstrap.get("elements", []) or []:
        pid = _int(p.get("id"))
        if not pid:
            continue
        team_id = _int(p.get("team"))
        position_id = _int(p.get("element_type"))
        minutes = _int(p.get("minutes"))
        starts = _int(p.get("starts"))
        xg = _float(p.get("expected_goals"))
        xa = _float(p.get("expected_assists"))
        xgi = _float(p.get("expected_goal_involvements"), xg + xa)
        code = _int(p.get("code"))
        photo = str(p.get("photo") or "")
        # Premier League moved current player cut-outs to the season-namespaced
        # `premierleague25` asset tree. The FPL `photo` field is the reliable
        # asset id here (e.g. 223094.jpg). The old `.../p{id}.png` path still
        # exists for some players, but using it as the primary source caused the
        # V810 front page to render giant empty image areas when the request 404ed.
        photo_code = photo.rsplit(".", 1)[0] if photo else (str(code) if code else "")
        image_url = (
            f"https://resources.premierleague.com/premierleague25/photos/players/500x500/{photo_code}.png"
            if photo_code else ""
        )
        image_url_small = (
            f"https://resources.premierleague.com/premierleague25/photos/players/110x140/{photo_code}.png"
            if photo_code else ""
        )
        out[pid] = {
            "element_id": pid,
            "web_name": str(p.get("web_name") or p.get("second_name") or p.get("first_name") or pid),
            "code": code,
            "photo": photo,
            "image_url": image_url,
            "image_url_small": image_url_small,
            "full_name": f"{p.get('first_name') or ''} {p.get('second_name') or ''}".strip(),
            "team_id": team_id,
            "club": teams.get(team_id, {}).get("short_name", ""),
            "club_name": teams.get(team_id, {}).get("name", ""),
            "position_id": position_id,
            "position": POSITION_LABELS.get(position_id, "Ukjent"),
            # Authoritative current market price. Keep this separate from a manager's selling price.
            "current_price": round(_int(p.get("now_cost")) / 10.0, 1),
            "total_points": _int(p.get("total_points")),
            "event_points": _int(p.get("event_points")),
            "form": _float(p.get("form")),
            "points_per_game": _float(p.get("points_per_game")),
            "minutes": minutes,
            "starts": starts,
            "goals_scored": _int(p.get("goals_scored")),
            "assists": _int(p.get("assists")),
            "clean_sheets": _int(p.get("clean_sheets")),
            "bonus": _int(p.get("bonus")),
            "saves": _int(p.get("saves")),
            "xg": xg,
            "xa": xa,
            "xgi": xgi,
            "xgi_per90": round(xgi * 90.0 / minutes, 3) if minutes > 0 else 0.0,
            "expected_goals_conceded": _float(p.get("expected_goals_conceded")),
            "selected_by_pct": _float(p.get("selected_by_percent")),
            "transfers_in_event": _int(p.get("transfers_in_event")),
            "transfers_out_event": _int(p.get("transfers_out_event")),
            "status": str(p.get("status") or "a"),
            "news": str(p.get("news") or "").strip(),
            "chance_next": None if p.get("chance_of_playing_next_round") is None else _int(p.get("chance_of_playing_next_round")),
            "ict_index": _float(p.get("ict_index")),
            "influence": _float(p.get("influence")),
            "creativity": _float(p.get("creativity")),
            "threat": _float(p.get("threat")),
            "team_strength": teams.get(team_id, {}).get("strength", 0),
            "raw": p,
        }
    return out


def live_stats_map(payload: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for row in payload.get("elements", []) or []:
        pid = _int(row.get("id"))
        if not pid:
            continue
        stats = row.get("stats") or {}
        out[pid] = {
            "points": _int(stats.get("total_points")),
            "minutes": _int(stats.get("minutes")),
            "goals": _int(stats.get("goals_scored")),
            "assists": _int(stats.get("assists")),
            "clean_sheets": _int(stats.get("clean_sheets")),
            "bonus": _int(stats.get("bonus")),
        }
    return out


def finished_event_ids(bootstrap: dict) -> list[int]:
    return sorted(
        _int(e.get("id"))
        for e in bootstrap.get("events", []) or []
        if e.get("finished") and _int(e.get("id"))
    )


MONTH_NAME_NO = {
    "august": "August",
    "september": "September",
    "october": "Oktober",
    "oktober": "Oktober",
    "november": "November",
    "december": "Desember",
    "desember": "Desember",
    "january": "Januar",
    "januar": "Januar",
    "february": "Februar",
    "februar": "Februar",
    "march": "Mars",
    "mars": "Mars",
    "april": "April",
    "may": "Mai",
    "mai": "Mai",
}


def month_phases(bootstrap: dict) -> list[dict]:
    out: list[dict] = []
    for phase in bootstrap.get("phases", []) or []:
        raw = str(phase.get("name") or "").strip().casefold()
        name = MONTH_NAME_NO.get(raw)
        if not name:
            continue
        pid = _int(phase.get("id"))
        if not pid:
            continue
        out.append(
            {
                "id": pid,
                "name": name,
                "start_event": _int(phase.get("start_event")),
                "stop_event": _int(phase.get("stop_event")),
            }
        )
    return out


def current_month_phase(bootstrap: dict, now_month: int | None = None) -> dict | None:
    phases = month_phases(bootstrap)
    if not phases:
        return None
    import datetime as _dt

    names = {
        1: "Januar", 2: "Februar", 3: "Mars", 4: "April", 5: "Mai", 6: "Juni",
        7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
    }
    calendar_name = names.get(now_month or _dt.datetime.now().month)
    by_calendar = next((p for p in phases if p["name"] == calendar_name), None)
    if by_calendar:
        return by_calendar
    event_id = current_event_id(bootstrap) or 0
    by_event = next((p for p in phases if p["start_event"] <= event_id <= p["stop_event"]), None)
    return by_event or phases[0]


def fixture_window(fixtures: list[dict], team_id: int, event_ids: list[int]) -> list[dict]:
    wanted = set(int(x) for x in event_ids)
    rows: list[dict] = []
    for f in fixtures:
        event = _int(f.get("event"))
        if event not in wanted:
            continue
        home = _int(f.get("team_h")) == int(team_id)
        away = _int(f.get("team_a")) == int(team_id)
        if not (home or away):
            continue
        rows.append(
            {
                "event": event,
                "home": home,
                "opponent_id": _int(f.get("team_a" if home else "team_h")),
                "difficulty": _int(f.get("team_h_difficulty" if home else "team_a_difficulty"), 3),
                "kickoff_time": f.get("kickoff_time"),
            }
        )
    rows.sort(key=lambda x: x["event"])
    return rows


def event_ids_for_period(bootstrap: dict, period: str, phase: dict | None = None) -> list[int]:
    events = sorted(_int(e.get("id")) for e in bootstrap.get("events", []) or [] if _int(e.get("id")))
    if not events:
        return []
    current = current_event_id(bootstrap) or 0
    next_id = next_event_id(bootstrap)
    start = next_id or (current + 1 if current else events[0])
    remaining = [e for e in events if e >= start]
    if not remaining:
        remaining = [current] if current else []
    p = (period or "").casefold()
    if "neste gw" in p:
        return remaining[:1]
    if "neste 3" in p:
        return remaining[:3]
    if "neste 5" in p:
        return remaining[:5]
    if "måned" in p:
        phase = phase or current_month_phase(bootstrap)
        if not phase:
            return remaining[:4]
        return [e for e in events if max(start, phase["start_event"]) <= e <= phase["stop_event"]]
    if "sesong" in p:
        return remaining
    return remaining[:3]
