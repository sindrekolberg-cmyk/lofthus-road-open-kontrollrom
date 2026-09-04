from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from lro_analysis import build_ownership, nfloat, nint, refresh_ownership_live
from lro_fpl import FPLClient, current_event_id, current_month_phase, player_catalog
from lro_history import HistoryStore, normalize_text


@dataclass(frozen=True)
class ManagerLiveState:
    entry: int
    manager: str
    team: str
    previous_rank: int
    live_rank: int
    live_rank_change: int
    official_total: int
    official_event_points: int
    official_total_before_gw: int
    live_gw_points: int
    live_gw_gross: int
    transfer_hits: int
    live_total_points: int
    captain: str
    captain_element: int
    vice_captain: str
    vice_element: int
    active_chip: str
    players_started: int
    players_finished: int
    players_live: int
    players_remaining: int
    month_points: int
    month_rank: int
    team_value: float
    bank: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlayerImpact:
    element: int
    player: str
    club: str
    event_points: int
    ownership_count: int
    ownership_pct: float
    captain_count: int
    triple_captain_count: int
    effective_ownership_pct: float
    live_minutes: int
    fixture_status: str
    impact_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveState:
    event_id: int
    event_status: str
    is_live: bool
    is_finished: bool
    fetched_at: datetime
    fixtures: list[dict]
    manager_live: list[ManagerLiveState]
    player_impacts: list[PlayerImpact]
    ownership: dict
    month_name: str
    data_quality: dict[str, Any] = field(default_factory=dict)

    @property
    def league_size(self) -> int:
        return len(self.manager_live)

    def manager(self, entry: int) -> ManagerLiveState | None:
        entry = int(entry)
        return next((m for m in self.manager_live if m.entry == entry), None)

    def managers_by_rank(self) -> list[ManagerLiveState]:
        return sorted(self.manager_live, key=lambda m: (m.live_rank, -m.live_total_points, normalize_text(m.manager)))

    def top(self, n: int = 5) -> list[ManagerLiveState]:
        return self.managers_by_rank()[: max(0, int(n))]

    def gw_ranking(self) -> list[ManagerLiveState]:
        return sorted(self.manager_live, key=lambda m: (-m.live_gw_points, m.live_rank, normalize_text(m.manager)))

    def month_ranking(self) -> list[ManagerLiveState]:
        return sorted(self.manager_live, key=lambda m: (m.month_rank or 10**9, -m.month_points, normalize_text(m.manager)))

    def player(self, element: int) -> PlayerImpact | None:
        element = int(element)
        return next((p for p in self.player_impacts if p.element == element), None)

    def to_debug(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_status": self.event_status,
            "is_live": self.is_live,
            "is_finished": self.is_finished,
            "fetched_at": self.fetched_at.isoformat(),
            "manager_count": len(self.manager_live),
            "loaded_managers": nint(self.ownership.get("loaded_managers")),
            "league_size": nint(self.ownership.get("league_size")),
            "month_name": self.month_name,
            "data_quality": dict(self.data_quality),
        }


def _event_meta(bootstrap: dict, event_id: int) -> dict:
    return next((dict(e) for e in bootstrap.get("events", []) or [] if nint(e.get("id")) == int(event_id)), {})


def _event_status(meta: dict, fixtures: list[dict]) -> tuple[str, bool, bool]:
    finished = bool(meta.get("finished"))
    active = any(bool(f.get("started")) and not bool(f.get("finished")) for f in fixtures)
    if active:
        return "live", True, False
    if finished:
        return "finished", False, True
    if bool(meta.get("is_current")):
        return "between_matches", False, False
    return "pre", False, False


def _fixture_team_states(fixtures: list[dict]) -> dict[int, str]:
    """Collapse current-event fixture state to one useful status per team.

    Double gameweeks are handled conservatively: live beats not-started, and a team
    is only 'finished' when every scheduled fixture in the event is finished.
    """
    states: dict[int, list[str]] = {}
    for f in fixtures:
        if bool(f.get("started")) and not bool(f.get("finished")):
            status = "live"
        elif bool(f.get("finished")):
            status = "finished"
        else:
            status = "not_started"
        for key in ("team_h", "team_a"):
            team = nint(f.get(key))
            if team:
                states.setdefault(team, []).append(status)
    out: dict[int, str] = {}
    for team, values in states.items():
        if "live" in values:
            out[team] = "live"
        elif "not_started" in values:
            out[team] = "not_started"
        else:
            out[team] = "finished"
    return out


def _month_base(client: FPLClient, league_id: int, bootstrap: dict) -> tuple[dict | None, dict[int, int]]:
    phase = current_month_phase(bootstrap)
    if not phase:
        return None, {}
    try:
        rows = client.league_phase_standings(league_id, nint(phase.get("id")))
    except Exception:
        rows = []
    return phase, {nint(r.get("entry")): nint(r.get("total")) for r in rows if nint(r.get("entry"))}


def _pick_meta(ownership: dict, catalog: dict[int, dict]) -> tuple[dict[int, dict], dict[int, list[dict]]]:
    picks = ownership.get("picks", pd.DataFrame())
    by_entry: dict[int, dict] = {}
    rows_by_entry: dict[int, list[dict]] = {}
    if picks is None or picks.empty:
        return by_entry, rows_by_entry
    for entry, block in picks.groupby("entry"):
        records = block.to_dict("records")
        rows_by_entry[int(entry)] = records
        cap = next((r for r in records if bool(r.get("is_captain"))), None)
        vice = next((r for r in records if bool(r.get("is_vice_captain"))), None)
        active_chip = str(records[0].get("active_chip") or "") if records else ""
        cap_name = str(cap.get("player") or "") if cap else ""
        vice_name = str(vice.get("player") or "") if vice else ""
        if cap and cap_name:
            is_tc = bool(cap.get("is_triple_captain")) or nint(cap.get("multiplier")) >= 3 or active_chip == "Triple Captain"
            cap_label = f"{cap_name} ({'TC' if is_tc else 'C'})"
        else:
            cap_label = "–"
        by_entry[int(entry)] = {
            "captain": cap_label,
            "captain_name": cap_name,
            "captain_element": nint(cap.get("element")) if cap else 0,
            "vice": vice_name,
            "vice_element": nint(vice.get("element")) if vice else 0,
            "chip": active_chip,
        }
    return by_entry, rows_by_entry


def _manager_event_map(ownership: dict) -> dict[int, dict]:
    events = ownership.get("manager_events", pd.DataFrame())
    if events is None or events.empty:
        return {}
    return {nint(r.get("entry")): r for r in events.to_dict("records") if nint(r.get("entry"))}


def _count_player_states(picks: list[dict], team_states: dict[int, str]) -> tuple[int, int, int, int]:
    # `multiplier > 0` reflects the currently scoring XI and Bench Boost. A player
    # with multiplier 0 is bench cover and should not inflate "players remaining".
    relevant = [p for p in picks if nint(p.get("multiplier")) > 0]
    statuses = [team_states.get(nint(p.get("team_id")), "not_started") for p in relevant]
    started = sum(1 for s in statuses if s in {"live", "finished"})
    finished = sum(1 for s in statuses if s == "finished")
    live = sum(1 for s in statuses if s == "live")
    remaining = sum(1 for s in statuses if s == "not_started")
    return started, finished, live, remaining


def _rank_min(values: dict[int, int]) -> dict[int, int]:
    return {entry: 1 + sum(1 for other in values.values() if other > points) for entry, points in values.items()}


def _build_player_impacts(ownership: dict, team_states: dict[int, str]) -> list[PlayerImpact]:
    players = ownership.get("players", pd.DataFrame())
    if players is None or players.empty:
        return []
    out: list[PlayerImpact] = []
    for row in players.to_dict("records"):
        points = nint(row.get("event_points"))
        owners = nint(row.get("ownership_count"))
        caps = nint(row.get("captain_count"))
        tcs = nint(row.get("triple_captain_count"))
        eo = nfloat(row.get("effective_ownership_pct"))
        status = team_states.get(nint(row.get("team_id")), "not_started")
        # Weight actual points most heavily. Captaincy and TC make the same goal
        # matter more to the league even when ordinary ownership is high.
        importance = abs(points) * (8.0 + caps * 1.35 + tcs * 3.2) + owners * 0.18
        if status == "live":
            importance += 8.0
        out.append(PlayerImpact(
            element=nint(row.get("element")),
            player=str(row.get("player") or ""),
            club=str(row.get("club") or ""),
            event_points=points,
            ownership_count=owners,
            ownership_pct=nfloat(row.get("ownership_pct")),
            captain_count=caps,
            triple_captain_count=tcs,
            effective_ownership_pct=eo,
            live_minutes=nint(row.get("live_minutes")),
            fixture_status=status,
            impact_score=round(importance, 2),
        ))
    return sorted(out, key=lambda p: (-p.impact_score, -p.event_points, normalize_text(p.player)))


def build_live_state(
    client: FPLClient,
    managers: list[dict],
    history: HistoryStore,
    league_id: int,
    bootstrap: dict | None = None,
    ownership: dict | None = None,
) -> LiveState:
    """Build the single authoritative matchday state used by every V800 page."""
    bootstrap = bootstrap or client.bootstrap()
    event_id = current_event_id(bootstrap) or 0
    if not event_id:
        return LiveState(0, "pre", False, False, datetime.now(timezone.utc), [], [], [], {}, "", {"reason": "no_event"})

    fixtures = client.fixtures(int(event_id))
    meta = _event_meta(bootstrap, int(event_id))
    status, is_live, is_finished = _event_status(meta, fixtures)

    if ownership is None:
        ownership = build_ownership(client, managers, history, event_id=int(event_id), max_workers=10)
        ownership["_picks_fetched_at"] = datetime.now(timezone.utc).isoformat()
    try:
        ownership = refresh_ownership_live(ownership, client.event_live(int(event_id)))
    except Exception:
        ownership = ownership or {}

    catalog = player_catalog(bootstrap)
    pick_meta, pick_rows = _pick_meta(ownership, catalog)
    event_map = _manager_event_map(ownership)
    team_states = _fixture_team_states(fixtures)
    phase, month_base = _month_base(client, int(league_id), bootstrap)

    live_gw: dict[int, int] = {}
    base_total: dict[int, int] = {}
    manager_by_entry = {nint(m.get("entry")): m for m in managers if nint(m.get("entry"))}
    for entry, m in manager_by_entry.items():
        ev = event_map.get(entry, {})
        official_event = nint(m.get("event_total"))
        official_total = nint(m.get("total"))
        live = nint(ev.get("live_gw_points"), official_event)
        live_gw[entry] = live
        # Classic standings can update during a GW. Removing their event_total
        # gives a stable pre-GW baseline before our own live score is added back.
        base_total[entry] = max(0, official_total - max(0, official_event))

    live_totals = {entry: base_total.get(entry, 0) + live_gw.get(entry, 0) for entry in manager_by_entry}
    live_ranks = _rank_min(live_totals)

    # FPL phase standings are treated as the completed-round monthly baseline.
    # Add the active event only while it is unfinished and inside this phase.
    phase_start = nint((phase or {}).get("start_event"))
    phase_stop = nint((phase or {}).get("stop_event"))
    add_live_month = bool(phase and not is_finished and phase_start <= int(event_id) <= phase_stop)
    month_points = {
        entry: nint(month_base.get(entry)) + (live_gw.get(entry, 0) if add_live_month else 0)
        for entry in manager_by_entry
    }
    month_ranks = _rank_min(month_points) if month_points else {}

    manager_states: list[ManagerLiveState] = []
    for entry, m in manager_by_entry.items():
        ev = event_map.get(entry, {})
        pm = pick_meta.get(entry, {})
        started, finished, playing, remaining = _count_player_states(pick_rows.get(entry, []), team_states)
        official_rank = nint(m.get("rank"), live_ranks.get(entry, 0))
        previous_rank = nint(m.get("last_rank"), official_rank or live_ranks.get(entry, 0))
        rank = live_ranks.get(entry, official_rank)
        manager_states.append(ManagerLiveState(
            entry=entry,
            manager=history.canonical(str(m.get("player_name") or "Ukjent manager")),
            team=str(m.get("entry_name") or "Ukjent lag"),
            previous_rank=previous_rank,
            live_rank=rank,
            live_rank_change=(previous_rank - rank) if previous_rank and rank else 0,
            official_total=nint(m.get("total")),
            official_event_points=nint(m.get("event_total")),
            official_total_before_gw=base_total.get(entry, 0),
            live_gw_points=live_gw.get(entry, 0),
            live_gw_gross=nint(ev.get("live_gw_gross"), live_gw.get(entry, 0) + nint(ev.get("event_transfers_cost"))),
            transfer_hits=nint(ev.get("event_transfers_cost")),
            live_total_points=live_totals.get(entry, nint(m.get("total"))),
            captain=str(pm.get("captain") or "–"),
            captain_element=nint(pm.get("captain_element")),
            vice_captain=str(pm.get("vice") or ""),
            vice_element=nint(pm.get("vice_element")),
            active_chip=str(pm.get("chip") or ""),
            players_started=started,
            players_finished=finished,
            players_live=playing,
            players_remaining=remaining,
            month_points=nint(month_points.get(entry)),
            month_rank=nint(month_ranks.get(entry)),
            team_value=nfloat(ev.get("team_value")),
            bank=nfloat(ev.get("bank")),
        ))

    loaded = nint(ownership.get("loaded_managers"))
    expected = len(managers)
    missing_entries = sorted(set(manager_by_entry) - set(event_map))
    quality = {
        "loaded_managers": loaded,
        "league_size": expected,
        "complete": bool(expected and loaded >= expected),
        "missing_entries": missing_entries,
        "errors": list(ownership.get("errors") or []),
    }
    return LiveState(
        event_id=int(event_id),
        event_status=status,
        is_live=is_live,
        is_finished=is_finished,
        fetched_at=datetime.now(timezone.utc),
        fixtures=fixtures,
        manager_live=sorted(manager_states, key=lambda m: (m.live_rank, -m.live_total_points, normalize_text(m.manager))),
        player_impacts=_build_player_impacts(ownership, team_states),
        ownership=ownership,
        month_name=str((phase or {}).get("name") or ""),
        data_quality=quality,
    )


def manager_swing_for_player(state: LiveState, element: int) -> list[dict[str, Any]]:
    """Return each manager's points swing versus league-average effective ownership."""
    picks = state.ownership.get("picks", pd.DataFrame())
    impact = state.player(int(element))
    if picks is None or picks.empty or impact is None:
        return []
    league_n = max(1, nint(state.data_quality.get("loaded_managers"), state.league_size))
    eo_multiplier = impact.effective_ownership_pct / 100.0
    managers = {m.entry: m for m in state.manager_live}
    block = picks[picks["element"].map(nint) == int(element)].copy()
    multiplier_by_entry = {nint(r.get("entry")): max(0, nint(r.get("multiplier"))) for r in block.to_dict("records")}
    rows = []
    for entry, manager in managers.items():
        mult = multiplier_by_entry.get(entry, 0)
        swing = (mult - eo_multiplier) * impact.event_points
        rows.append({
            "entry": entry,
            "manager": manager.manager,
            "team": manager.team,
            "multiplier": mult,
            "swing": round(swing, 2),
            "contribution": int(mult * impact.event_points),
        })
    return sorted(rows, key=lambda r: (-r["swing"], normalize_text(r["manager"])))
