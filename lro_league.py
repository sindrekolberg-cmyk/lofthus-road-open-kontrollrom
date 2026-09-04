from __future__ import annotations

from typing import Any

import pandas as pd

from lro_analysis import manager_form_from_histories, nint
from lro_fpl import current_event_id, month_phases, season_label
from lro_history import HistoryStore, normalize_text
from lro_live import LiveState, ManagerLiveState


def manager_options(managers: list[dict]) -> list[tuple[int, str]]:
    rows = []
    for m in managers:
        entry = nint(m.get("entry"))
        if entry:
            rows.append((entry, f"{m.get('player_name') or 'Ukjent'} · {m.get('entry_name') or ''}".strip(" ·")))
    return sorted(rows, key=lambda x: normalize_text(x[1]))


def manager_name(m: dict | None) -> str:
    return str((m or {}).get("canonical_name") or (m or {}).get("player_name") or "Ukjent manager")


def fallback_manager_states(managers: list[dict]) -> list[ManagerLiveState]:
    """Immediate shell state before the league-wide picks sweep is ready."""
    out: list[ManagerLiveState] = []
    for m in managers:
        entry = nint(m.get("entry"))
        if not entry:
            continue
        rank = nint(m.get("rank"))
        last = nint(m.get("last_rank"), rank)
        out.append(ManagerLiveState(
            entry=entry,
            manager=manager_name(m),
            team=str(m.get("entry_name") or ""),
            previous_rank=last,
            live_rank=rank,
            live_rank_change=(last-rank) if rank and last else 0,
            official_total=nint(m.get("total")),
            official_event_points=nint(m.get("event_total")),
            official_total_before_gw=max(0,nint(m.get("total"))-max(0,nint(m.get("event_total")))),
            live_gw_points=nint(m.get("event_total")),
            live_gw_gross=nint(m.get("event_total")),
            transfer_hits=0,
            live_total_points=nint(m.get("total")),
            captain="–", captain_element=0, vice_captain="", vice_element=0, active_chip="",
            players_started=0, players_finished=0, players_live=0, players_remaining=0,
            month_points=0, month_rank=0, team_value=0.0, bank=0.0,
        ))
    return sorted(out,key=lambda m:(m.live_rank or 10**9,-m.live_total_points,normalize_text(m.manager)))


def effective_states(managers: list[dict], state: LiveState | None) -> list[ManagerLiveState]:
    return state.manager_live if state and state.manager_live else fallback_manager_states(managers)


def form_rows(managers: list[dict], histories: dict[int, dict] | None, entry: int, state: LiveState | None, last_n: int = 5) -> list[dict[str, Any]]:
    histories = histories or {}
    form = manager_form_from_histories(managers, histories, int(entry), last_n)
    rows = form.to_dict("records") if not form.empty else []
    if state and not state.is_finished:
        m = state.manager(int(entry))
        if m:
            live_round_rank = 1 + sum(1 for other in state.manager_live if other.live_gw_points > m.live_gw_points)
            live = {
                "entry": int(entry), "event": state.event_id, "points": m.live_gw_points,
                "total_points": m.live_total_points, "round_rank": live_round_rank,
                "league_rank": m.live_rank, "is_live": True,
            }
            rows = [r for r in rows if nint(r.get("event")) != state.event_id] + [live]
    rows = sorted(rows,key=lambda r:nint(r.get("event")))[-last_n:]
    return rows


def profile_story(state: LiveState, entry: int) -> str:
    me = state.manager(int(entry))
    if not me:
        return ""
    picks = state.ownership.get("picks", pd.DataFrame())
    if picks is not None and not picks.empty:
        mine = picks[picks["entry"].map(nint) == int(entry)].copy()
        if not mine.empty:
            mine["contribution"] = pd.to_numeric(mine.get("gw_contribution",0), errors="coerce").fillna(0)
            top = mine.sort_values(["contribution","event_points"],ascending=[False,False]).iloc[0].to_dict()
            contribution = nint(top.get("contribution"))
            if contribution > 0 and me.live_gw_points:
                return f"{top.get('player')} står for {contribution} av {me.live_gw_points} poeng akkurat nå."
    if state.is_live and abs(me.live_rank_change) >= 2:
        direction = f"opp {me.live_rank_change}" if me.live_rank_change > 0 else f"ned {abs(me.live_rank_change)}"
        return f"{me.manager} er foreløpig {direction} plasser."
    if me.players_remaining:
        return f"{me.players_remaining} spillere gjenstår i GW{state.event_id}."
    return ""


def player_status_map(state: LiveState) -> dict[int, str]:
    return {p.element: p.fixture_status for p in state.player_impacts}


def auto_monthly_rows(client: Any, history: HistoryStore, league_id: int, bootstrap: dict) -> list[dict]:
    rows: list[dict] = []
    season = season_label(bootstrap)
    for phase in month_phases(bootstrap):
        # Only publish historical medals for a phase that is over according to the
        # current event metadata. Current month remains a live race, not history.
        stop = nint(phase.get("stop_event"))
        event_meta = next((e for e in bootstrap.get("events",[]) or [] if nint(e.get("id"))==stop),{})
        if not event_meta.get("finished"):
            continue
        try:
            standings = client.league_phase_standings(int(league_id), nint(phase.get("id")))
        except Exception:
            standings = []
        for place, row in enumerate(sorted(standings,key=lambda r:(nint(r.get("rank"),10**9),normalize_text(str(r.get("player_name") or ""))))[:3],start=1):
            rows.append({
                "season":season,"month":phase.get("name"),"place":place,
                "manager":history.canonical(str(row.get("player_name") or "Ukjent manager")),
                "status":"Automatisk","source":f"FPL phase {phase.get('id')}",
            })
    return rows


def fixture_scoreline(state: LiveState, bootstrap: dict) -> str:
    teams = {nint(t.get("id")):str(t.get("short_name") or t.get("name") or "") for t in bootstrap.get("teams",[]) or []}
    active = [f for f in state.fixtures if bool(f.get("started")) and not bool(f.get("finished"))]
    parts=[]
    for f in active[:4]:
        h=teams.get(nint(f.get("team_h")),"H") ; a=teams.get(nint(f.get("team_a")),"B")
        hs=nint(f.get("team_h_score")); aas=nint(f.get("team_a_score")); mins=nint(f.get("minutes"))
        parts.append(f"{h} {hs}–{aas} {a}" + (f" · {mins}'" if mins else ""))
    return " · ".join(parts)
