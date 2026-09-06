from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from lro_analysis import nint
from lro_live import LiveState, PlayerImpact


STALE_LIVE_SECONDS = 90.0


@dataclass(frozen=True)
class PulseEvent:
    event_id: str
    fixture_id: int
    event_type: str
    player_id: int
    player_name: str
    team: str
    timestamp: str
    old_points: int
    new_points: int
    point_delta: int
    snapshot_id: str
    label: str
    banner: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def source_updated_at(state: LiveState | None) -> str | None:
    if not state:
        return None
    return state.fetched_at.isoformat()


def snapshot_age_seconds(state: LiveState | None, now: datetime | None = None) -> float:
    if not state:
        return 10**9
    now = now or datetime.now(timezone.utc)
    fetched = state.fetched_at
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    return max(0.0, (now - fetched).total_seconds())


def is_stale(state: LiveState | None, now: datetime | None = None) -> bool:
    if not state or not state.is_live:
        return False
    return snapshot_age_seconds(state, now) > STALE_LIVE_SECONDS


def round_kicker(event_id: int, is_live: bool, is_finished: bool, event_status: str) -> str:
    gw = int(event_id or 0)
    if is_live:
        return f"Live · Runde {gw} pågår"
    if is_finished:
        return f"Runde {gw} ferdig"
    if event_status == "between_matches":
        return f"Runde {gw}"
    if event_status == "pre":
        return f"Runde {gw}"
    return f"Runde {gw}" if gw else "Runde"


def _pick_map(state: LiveState | None) -> dict[int, dict[str, Any]]:
    if not state or not state.ownership:
        return {}
    picks = state.ownership.get("picks")
    if picks is None or not isinstance(picks, pd.DataFrame) or picks.empty:
        return {}
    out: dict[int, dict[str, Any]] = {}
    for row in picks.to_dict("records"):
        element = nint(row.get("element"))
        if element and element not in out:
            out[element] = row
    return out


def _player_map(state: LiveState | None) -> dict[int, PlayerImpact]:
    if not state:
        return {}
    return {p.element: p for p in state.player_impacts}


def _classify_stat_change(old_row: dict[str, Any] | None, new_row: dict[str, Any] | None) -> str:
    old_row = old_row or {}
    new_row = new_row or {}
    checks = (
        ("live_goals", "goal"),
        ("live_assists", "assist"),
        ("live_cs", "clean_sheet"),
        ("live_yc", "yellow_card"),
        ("live_rc", "red_card"),
        ("live_saves", "saves"),
        ("live_bonus", "bonus"),
        ("live_minutes", "minutes"),
    )
    hits = []
    for field, kind in checks:
        if nint(new_row.get(field)) > nint(old_row.get(field)):
            hits.append(kind)
        if field == "live_cs" and nint(old_row.get(field)) and not nint(new_row.get(field)):
            hits.append("clean_sheet_lost")
    if "goal" in hits:
        return "goal"
    if "assist" in hits:
        return "assist"
    if "clean_sheet_lost" in hits:
        return "clean_sheet_lost"
    if "clean_sheet" in hits:
        return "clean_sheet"
    if "red_card" in hits:
        return "red_card"
    if "yellow_card" in hits:
        return "yellow_card"
    if "saves" in hits:
        return "saves"
    if "bonus" in hits:
        return "bonus"
    if "minutes" in hits:
        return "minutes"
    return ""


def _banner(event_type: str, player: str, club: str, delta: int) -> tuple[str, str]:
    club_bit = f" · {club}" if club else ""
    if event_type == "goal":
        return f"{player}{club_bit}", "Mål"
    if event_type == "assist":
        return f"{player}{club_bit}", "Assist"
    if event_type == "bonus":
        return f"{player} +{delta}" if delta > 0 else f"{player} {delta}", "Bonus oppdatert"
    if event_type == "autosub":
        return player, "Autosub"
    if event_type == "captain_fallback":
        return player, "VC inn"
    if event_type == "clean_sheet_lost":
        return f"{player}{club_bit}", "CS tapt"
    signed = f"+{delta}" if delta > 0 else str(delta)
    return f"{player} {signed}", "Poeng"


def _event(
    *,
    kind: str,
    player_id: int,
    player_name: str,
    team: str,
    old_points: int,
    new_points: int,
    snapshot_id: str,
    fixture_id: int = 0,
    stamp: str = "",
) -> PulseEvent:
    delta = int(new_points) - int(old_points)
    label, kicker = _banner(kind, player_name, team, delta)
    return PulseEvent(
        event_id=f"{snapshot_id}:{kind}:{player_id}:{old_points}:{new_points}",
        fixture_id=int(fixture_id or 0),
        event_type=kind,
        player_id=int(player_id),
        player_name=player_name,
        team=team,
        timestamp=stamp,
        old_points=int(old_points),
        new_points=int(new_points),
        point_delta=delta,
        snapshot_id=snapshot_id,
        label=label,
        banner=kicker,
    )


def diff_live_states(old: LiveState | None, new: LiveState | None, snapshot_id: str) -> list[PulseEvent]:
    if not new or old is None:
        return []
    if old.event_id != new.event_id:
        return []
    stamp = new.fetched_at.isoformat()
    events: list[PulseEvent] = []
    old_players = _player_map(old)
    new_players = _player_map(new)
    old_picks = _pick_map(old)
    new_picks = _pick_map(new)

    for element, impact in new_players.items():
        prev = old_players.get(element)
        old_pts = prev.event_points if prev else 0
        if impact.event_points == old_pts and prev:
            kind = _classify_stat_change(old_picks.get(element), new_picks.get(element))
            if not kind:
                continue
        elif impact.event_points != old_pts:
            kind = _classify_stat_change(old_picks.get(element), new_picks.get(element)) or "player_points_changed"
        else:
            continue
        if impact.fixture_status not in {"live", "pause"}:
            continue
        events.append(
            _event(
                kind=kind,
                player_id=element,
                player_name=impact.player,
                team=impact.club,
                old_points=old_pts,
                new_points=impact.event_points,
                snapshot_id=snapshot_id,
                stamp=stamp,
            )
        )

    old_autos = {
        nint(r.get("element"))
        for r in (old.ownership or {}).get("picks", pd.DataFrame()).to_dict("records")
        if bool(r.get("autosub_in"))
    } if old.ownership else set()
    new_rows = []
    picks = (new.ownership or {}).get("picks")
    if isinstance(picks, pd.DataFrame) and not picks.empty:
        new_rows = picks.to_dict("records")
    for row in new_rows:
        if not bool(row.get("autosub_in")):
            continue
        element = nint(row.get("element"))
        if element in old_autos:
            continue
        events.append(
            _event(
                kind="autosub",
                player_id=element,
                player_name=str(row.get("player") or ""),
                team=str(row.get("club") or ""),
                old_points=0,
                new_points=nint(row.get("event_points")),
                snapshot_id=snapshot_id,
                stamp=stamp,
            )
        )

    old_caps = {m.entry: m.captain_element for m in old.manager_live}
    for manager in new.manager_live:
        prev_cap = old_caps.get(manager.entry)
        if prev_cap and manager.captain_element and prev_cap != manager.captain_element:
            events.append(
                _event(
                    kind="captain_fallback",
                    player_id=manager.captain_element,
                    player_name=manager.captain,
                    team="",
                    old_points=0,
                    new_points=manager.live_gw_points,
                    snapshot_id=snapshot_id,
                    stamp=stamp,
                )
            )

    seen: set[str] = set()
    unique: list[PulseEvent] = []
    for event in events:
        if event.event_id in seen:
            continue
        seen.add(event.event_id)
        unique.append(event)
    return unique


class PulseHub:
    def __init__(self, history_limit: int = 40):
        self.seq = 0
        self.history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self.last_payload: dict[str, Any] | None = None
        self._cv = __import__("threading").Condition()

    def publish(self, payload: dict[str, Any], events: list[PulseEvent]) -> int:
        with self._cv:
            self.seq += 1
            for event in events:
                self.history.appendleft(event.to_dict())
            body = dict(payload)
            body["seq"] = self.seq
            body["events"] = [e.to_dict() for e in events]
            body["event_history"] = list(self.history)
            self.last_payload = body
            self._cv.notify_all()
            return self.seq

    def wait(self, last_seq: int, timeout: float = 15.0) -> tuple[int, dict[str, Any] | None]:
        with self._cv:
            if self.seq > last_seq:
                return self.seq, self.last_payload
            self._cv.wait(timeout)
            return self.seq, self.last_payload


def is_newer_snapshot(incoming_seq: int, current_seq: int) -> bool:
    return int(incoming_seq) > int(current_seq)
