from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from lro_analysis import chip_label, manager_squad, nint
from lro_fpl import season_label
from lro_history import HistoryStore
from lro_league import form_rows, player_status_map, profile_story
from lro_live import LiveState, ManagerLiveState, PlayerImpact, manager_swing_for_player
from lro_rival import RivalDuel, RivalPlayerEdge


def json_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return json_value(value.item())
        except Exception:
            pass
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return [json_value(r) for r in df.to_dict("records")]


def fixture_status_label(status: str) -> str:
    return {
        "live": "pågår",
        "finished": "ferdig",
        "not_started": "ikke spilt",
    }.get(str(status or ""), str(status or "ukjent"))


def event_status_label(status: str, is_live: bool, is_finished: bool) -> str:
    if is_live:
        return "pågår"
    if is_finished:
        return "ferdig"
    if status == "between_matches":
        return "mellom kamper"
    if status == "pre":
        return "før avspark"
    return str(status or "ukjent")


def manager_payload(m: ManagerLiveState) -> dict[str, Any]:
    return {
        "entry": m.entry,
        "manager": m.manager,
        "team": m.team,
        "rank": m.live_rank,
        "previous_rank": m.previous_rank,
        "rank_change": m.live_rank_change,
        "captain": m.captain,
        "captain_element": m.captain_element,
        "vice_captain": m.vice_captain,
        "vice_element": m.vice_element,
        "gw": m.live_gw_points,
        "gw_gross": m.live_gw_gross,
        "hits": m.transfer_hits,
        "total": m.live_total_points,
        "official_total": m.official_total,
        "official_gw": m.official_event_points,
        "chip": m.active_chip or "",
        "players_started": m.players_started,
        "players_finished": m.players_finished,
        "players_live": m.players_live,
        "players_remaining": m.players_remaining,
        "month_points": m.month_points,
        "month_rank": m.month_rank,
        "team_value": m.team_value,
        "bank": m.bank,
    }


def player_impact_payload(p: PlayerImpact) -> dict[str, Any]:
    return {
        "element": p.element,
        "player": p.player,
        "club": p.club,
        "event_points": p.event_points,
        "ownership_count": p.ownership_count,
        "ownership_pct": p.ownership_pct,
        "captain_count": p.captain_count,
        "triple_captain_count": p.triple_captain_count,
        "effective_ownership_pct": p.effective_ownership_pct,
        "live_minutes": p.live_minutes,
        "fixture_status": p.fixture_status,
        "fixture_status_label": fixture_status_label(p.fixture_status),
        "impact_score": p.impact_score,
        "image_url": p.image_url or "",
    }


def status_payload(
    *,
    name: str,
    season: str,
    state: LiveState | None,
    managers: list[dict],
    live_ready: bool,
    histories_ready: bool,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    event_id = state.event_id if state else 0
    event_status = state.event_status if state else "pre"
    is_live = bool(state and state.is_live)
    is_finished = bool(state and state.is_finished)
    return {
        "name": name,
        "season": season,
        "event_id": event_id,
        "event_status": event_status,
        "event_status_label": event_status_label(event_status, is_live, is_finished),
        "is_live": is_live,
        "is_finished": is_finished,
        "provisional": bool(state and not state.is_finished),
        "month_name": state.month_name if state else "",
        "fetched_at": state.fetched_at.isoformat() if state else None,
        "league_size": len(managers),
        "live_ready": live_ready,
        "histories_ready": histories_ready,
        "data_quality": json_value(state.data_quality) if state else {},
        "errors": list(errors or []),
    }


def fixture_payload(state: LiveState, bootstrap: dict) -> list[dict[str, Any]]:
    teams = {
        nint(t.get("id")): {
            "name": str(t.get("name") or ""),
            "short": str(t.get("short_name") or t.get("name") or ""),
        }
        for t in bootstrap.get("teams", []) or []
    }
    out = []
    for f in state.fixtures or []:
        started = bool(f.get("started"))
        finished = bool(f.get("finished"))
        if started and not finished:
            status = "live"
        elif finished:
            status = "finished"
        else:
            status = "not_started"
        hid = nint(f.get("team_h"))
        aid = nint(f.get("team_a"))
        out.append({
            "id": nint(f.get("id")),
            "kickoff": str(f.get("kickoff_time") or ""),
            "minutes": nint(f.get("minutes")),
            "status": status,
            "status_label": fixture_status_label(status),
            "home": teams.get(hid, {}).get("short") or str(hid),
            "away": teams.get(aid, {}).get("short") or str(aid),
            "home_name": teams.get(hid, {}).get("name") or "",
            "away_name": teams.get(aid, {}).get("name") or "",
            "home_score": nint(f.get("team_h_score")) if started or finished else None,
            "away_score": nint(f.get("team_a_score")) if started or finished else None,
        })
    return out


def squad_payload(state: LiveState, entry: int) -> dict[str, Any]:
    df = manager_squad(state.ownership, int(entry))
    statuses = player_status_map(state)
    rows = []
    for r in records(df):
        element = nint(r.get("element"))
        status = statuses.get(element, "not_started")
        rows.append({
            "element": element,
            "player": str(r.get("player") or ""),
            "full_name": str(r.get("full_name") or ""),
            "club": str(r.get("club") or ""),
            "position": str(r.get("position") or ""),
            "position_id": nint(r.get("position_id")),
            "squad_position": nint(r.get("squad_position")),
            "event_points": nint(r.get("event_points")),
            "gw_contribution": nint(r.get("gw_contribution")),
            "multiplier": nint(r.get("multiplier")),
            "is_captain": bool(r.get("is_captain")),
            "is_vice_captain": bool(r.get("is_vice_captain")),
            "is_triple_captain": bool(r.get("is_triple_captain")),
            "on_bench": bool(r.get("on_bench")),
            "fixture_status": status,
            "fixture_status_label": fixture_status_label(status),
            "image_url": str(r.get("image_url") or ""),
            "minutes": nint(r.get("live_minutes")),
        })
    xi = [p for p in rows if not p["on_bench"]]
    bench = [p for p in rows if p["on_bench"]]
    lines = {
        "gk": [p for p in xi if p["position_id"] == 1],
        "def": [p for p in xi if p["position_id"] == 2],
        "mid": [p for p in xi if p["position_id"] == 3],
        "fwd": [p for p in xi if p["position_id"] == 4],
    }
    return {"xi": xi, "bench": bench, "lines": lines}


def chips_payload(history_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for chip in (history_payload or {}).get("chips", []) or []:
        event = nint(chip.get("event"))
        out.append({
            "chip": chip_label(chip.get("name")),
            "event": event,
            "gw": f"GW{event}" if event else "",
        })
    return out


def fpl_career_payload(history_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for r in (history_payload or {}).get("past", []) or []:
        rows.append({
            "season": str(r.get("season_name") or ""),
            "points": nint(r.get("total_points")),
            "overall_rank": nint(r.get("rank")) or None,
        })
    return list(reversed(rows))


def fpl_season_payload(history_payload: dict[str, Any] | None) -> dict[str, Any]:
    current = (history_payload or {}).get("current", []) or []
    if not current:
        return {}
    latest = current[-1]
    return {
        "overall_rank": nint(latest.get("overall_rank")) or None,
        "total_points": nint(latest.get("total_points")),
        "value": round(nint(latest.get("value")) / 10.0, 1) if nint(latest.get("value")) else None,
    }


def merits_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return {
            "league_gold": 0,
            "league_silver": 0,
            "league_bronze": 0,
            "cup_gold": 0,
            "cup_silver": 0,
            "monthly_gold": 0,
            "monthly_silver": 0,
            "monthly_bronze": 0,
            "rank": None,
        }
    return {
        "rank": nint(raw.get("rank")) or None,
        "league_gold": nint(raw.get("league_gold")),
        "league_silver": nint(raw.get("league_silver")),
        "league_bronze": nint(raw.get("league_bronze")),
        "cup_gold": nint(raw.get("cup_gold")),
        "cup_silver": nint(raw.get("cup_silver")),
        "monthly_gold": nint(raw.get("monthly_gold")),
        "monthly_silver": nint(raw.get("monthly_silver")),
        "monthly_bronze": nint(raw.get("monthly_bronze")),
        "league_seasons": list(raw.get("league_seasons") or []),
        "cup_seasons": list(raw.get("cup_seasons") or []),
    }


def edge_payload(edge: RivalPlayerEdge, rival_name: str, state: LiveState | None = None) -> dict[str, Any]:
    swing = edge.live_swing
    event_kind = _player_event_kind(state, edge.element) if state else ""
    if swing == 0:
        headline = f"{edge.player} kan svinge duellen mot {rival_name}"
    elif event_kind:
        headline = f"{edge.player} {event_kind}: {swing:+d} mot {rival_name}"
    else:
        headline = f"{edge.player}: {swing:+d} mot {rival_name}"
    return {
        "element": edge.element,
        "player": edge.player,
        "my_multiplier": edge.my_multiplier,
        "rival_multiplier": edge.rival_multiplier,
        "multiplier_edge": edge.multiplier_edge,
        "event_points": edge.event_points,
        "live_swing": edge.live_swing,
        "status": edge.status,
        "status_label": fixture_status_label(edge.status),
        "event_kind": event_kind,
        "headline": headline,
    }


def _player_event_kind(state: LiveState, element: int) -> str:
    picks = state.ownership.get("picks", pd.DataFrame()) if state.ownership else None
    if picks is None or getattr(picks, "empty", True):
        return ""
    block = picks[picks["element"].map(nint) == int(element)]
    if block.empty:
        return ""
    row = block.iloc[0].to_dict()
    if nint(row.get("live_goals")):
        return "mål"
    if nint(row.get("live_assists")):
        return "assist"
    if nint(row.get("live_bonus")) >= 3:
        return "bonus"
    return ""


def rival_payload(duel: RivalDuel, state: LiveState | None = None) -> dict[str, Any]:
    me = manager_payload(duel.me)
    rival = manager_payload(duel.rival)
    return {
        "me": me,
        "rival": rival,
        "live_gap": duel.live_gap,
        "total_gap": duel.live_gap,
        "gw_gap": duel.me.live_gw_points - duel.rival.live_gw_points,
        "common_players": duel.common_players,
        "captains": {"me": duel.me.captain, "rival": duel.rival.captain},
        "players_remaining": {"me": duel.me.players_remaining, "rival": duel.rival.players_remaining},
        "cheer_for": [edge_payload(e, duel.rival.manager, state) for e in duel.cheer_for],
        "hope_blank": [edge_payload(e, duel.me.manager, state) for e in duel.hope_blank],
        "my_unique": [edge_payload(e, duel.rival.manager, state) for e in duel.my_unique],
        "rival_unique": [edge_payload(e, duel.me.manager, state) for e in duel.rival_unique],
        "strategy": rival_strategy_payload(duel, state),
    }


def rival_strategy_payload(duel: RivalDuel, state: LiveState | None) -> dict[str, Any]:
    gap = int(duel.live_gap)
    event_now = state.event_id if state else 1
    threshold = 28 if event_now <= 5 else 20 if event_now <= 20 else 12
    if gap >= threshold:
        context = "defend"
        text = f"Du ligger {gap} poeng foran. Dekning kan være mer verdt enn unødvendig gambling."
    elif gap <= -threshold:
        context = "chase"
        text = f"Du ligger {abs(gap)} poeng bak. Gode forskjeller kan være mer verdifulle enn ren dekning."
    else:
        context = "neutral"
        text = "Det er tett nok til at forventet poengverdi bør veie tyngst. Forskjeller er bonus, ikke mål i seg selv."
    return {"context": context, "text": text, "gap": gap, "threshold": threshold}


def history_store_payload(history: HistoryStore, auto_rows: list[dict] | None = None) -> dict[str, Any]:
    overall = []
    for r in records(history.overall_results()):
        overall.append({
            "season": r.get("season") or "",
            "winner": r.get("winner") or "",
            "runner_up": r.get("runner_up") or "",
            "third_place": r.get("third_place") or "",
            "note": r.get("note") or "",
            "status": r.get("status") or "",
        })
    cup = []
    for r in records(history.cup_results()):
        cup.append({
            "season": r.get("season") or "",
            "winner": r.get("winner") or "",
            "runner_up": r.get("runner_up") or "",
            "note": r.get("note") or "",
            "status": r.get("status") or "",
        })
    random_rows = []
    for r in records(history.random_results()):
        random_rows.append({
            "season": r.get("season") or "",
            "winner": r.get("winner") or "",
            "placement": r.get("placement") or "",
            "note": r.get("note") or "",
        })
    calendar = []
    for r in records(history.monthly_calendar(auto_rows)):
        calendar.append({
            "season": r.get("season") or "",
            "month": r.get("month") or "",
            "winner": r.get("winner") or "",
            "runner_up": r.get("runner_up") or "",
            "third": r.get("third") or "",
        })
    return {"overall": overall, "cup": cup, "random": random_rows, "monthly": calendar}


def hall_of_fame_payload(history: HistoryStore, auto_rows: list[dict] | None = None) -> list[dict[str, Any]]:
    rows = []
    for r in records(history.hall_of_fame(auto_rows)):
        rows.append({
            "rank": nint(r.get("rank")),
            "manager": str(r.get("display_name") or ""),
            "league_gold": nint(r.get("league_gold")),
            "league_silver": nint(r.get("league_silver")),
            "league_bronze": nint(r.get("league_bronze")),
            "cup_gold": nint(r.get("cup_gold")),
            "cup_silver": nint(r.get("cup_silver")),
            "monthly_gold": nint(r.get("monthly_gold")),
            "monthly_silver": nint(r.get("monthly_silver")),
            "monthly_bronze": nint(r.get("monthly_bronze")),
            "gold": nint(r.get("gold")),
            "silver": nint(r.get("silver")),
            "bronze": nint(r.get("bronze")),
            "podiums": nint(r.get("podiums")),
            "league_seasons": list(r.get("league_seasons") or []),
            "cup_seasons": list(r.get("cup_seasons") or []),
        })
    return rows


def hall_records_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def leader(field: str, label: str) -> dict[str, Any] | None:
        if not rows:
            return None
        best = max(rows, key=lambda r: (nint(r.get(field)), -nint(r.get("rank"), 999)))
        value = nint(best.get(field))
        if value <= 0:
            return None
        return {"manager": best["manager"], "value": value, "label": label, "field": field}

    return {
        "league_titles": leader("league_gold", "Ligatitler"),
        "cup_titles": leader("cup_gold", "Cuptitler"),
        "month_titles": leader("monthly_gold", "Månedstitler"),
        "podiums": leader("podiums", "Podier"),
    }


def odds_payload(
    state: LiveState | None,
    histories: dict[int, dict] | None,
    history: HistoryStore,
) -> dict[str, Any]:
    from lro_odds import build_live_market

    if not state:
        return {"rows": [], "ready": False, "note": "Live-data er ikke klare."}
    managers = [
        {
            "entry": m.entry,
            "rank": m.live_rank,
            "total": m.live_total_points,
            "player_name": m.manager,
        }
        for m in state.manager_live
    ]
    try:
        df = build_live_market(managers, histories or {}, state.event_id, history)
    except Exception:
        return {"rows": [], "ready": False, "note": "Odds kunne ikke beregnes."}
    if df is None or df.empty:
        return {"rows": [], "ready": False, "note": "For tynt grunnlag til å vise odds."}
    rows = []
    for r in df.head(12).to_dict("records"):
        rows.append({
            "entry": nint(r.get("entry")),
            "manager": str(r.get("manager") or ""),
            "rank": nint(r.get("current_rank")),
            "win_pct": round(float(r.get("win_pct") or 0), 1),
            "odds": round(float(r.get("winner_odds") or 0), 2),
            "preseason_odds": round(float(r.get("preseason_odds") or 0), 2),
            "note": str(r.get("note") or ""),
        })
    return {"rows": rows, "ready": True, "event_id": state.event_id}


def player_swing_payload(state: LiveState, element_id: int) -> dict[str, Any] | None:
    impact = state.player(int(element_id))
    if not impact:
        return None
    swings = manager_swing_for_player(state, int(element_id))
    gainers = [r for r in swings if r["swing"] > 0.05]
    losers = [r for r in swings if r["swing"] < -0.05]
    return {
        "player": player_impact_payload(impact),
        "swings": swings[:20],
        "winner": gainers[0] if gainers else None,
        "loser": losers[-1] if losers else None,
    }


def pick_hero(state: LiveState | None) -> dict[str, Any] | None:
    if not state or not state.player_impacts:
        return None
    candidates = [p for p in state.player_impacts if p.event_points or p.captain_count or p.triple_captain_count]
    if not candidates:
        candidates = list(state.player_impacts[:1])
    if state.is_live:
        live_now = [p for p in candidates if p.fixture_status == "live" and p.event_points]
        standout = live_now[0] if live_now else candidates[0]
    else:
        standout = max(candidates, key=lambda p: (p.event_points, p.impact_score))
    kicker = "LIVE" if state.is_live and standout.fixture_status == "live" else f"GW{state.event_id}"
    if standout.fixture_status == "not_started":
        headline = f"{standout.player} er i søkelyset"
        dek = f"{standout.ownership_count} eiere i Lofthus. Kampen er ikke spilt ennå."
    elif state.is_live and standout.fixture_status == "live":
        headline = f"{standout.player} herjer: {standout.event_points} poeng live"
        dek = f"{standout.ownership_count} eiere" + (f" · {standout.captain_count} kaptein{'er' if standout.captain_count != 1 else ''}" if standout.captain_count else "")
    elif standout.event_points:
        headline = f"{standout.player} leverte {standout.event_points} poeng"
        dek = f"{standout.ownership_pct:.0f} % eierskap i Lofthus."
    else:
        headline = f"{standout.player} preger runden"
        dek = f"{standout.ownership_pct:.0f} % eierskap i Lofthus."
    return {
        **player_impact_payload(standout),
        "kicker": kicker,
        "headline": headline,
        "dek": dek,
    }


def analysis_from_state(state: LiveState) -> dict[str, Any]:
    players = [player_impact_payload(p) for p in state.player_impacts]
    captains = sorted(players, key=lambda p: (-p["captain_count"], -p["event_points"], p["player"]))
    ownership = sorted(players, key=lambda p: (-p["ownership_count"], -p["captain_count"], p["player"]))
    diffs = [
        p for p in players
        if p["ownership_pct"] <= 12 and p["event_points"] > 0 and p["fixture_status"] != "not_started"
    ]
    diffs = sorted(diffs, key=lambda p: (-p["event_points"], p["ownership_pct"], p["player"]))
    events = state.ownership.get("manager_events", pd.DataFrame())
    chips = []
    if events is not None and not events.empty and "active_chip" in events.columns:
        for r in events.to_dict("records"):
            chip = str(r.get("active_chip") or "").strip()
            if chip:
                chips.append({
                    "entry": nint(r.get("entry")),
                    "manager": str(r.get("manager") or ""),
                    "chip": chip,
                    "gw": nint(r.get("gw_points")),
                })
        chips.sort(key=lambda r: (r["chip"], r["manager"]))
    return {
        "captain": captains[:25],
        "ownership": ownership[:40],
        "differentials": diffs[:25],
        "chips": chips,
    }


def manager_profile_payload(
    *,
    m: ManagerLiveState,
    state: LiveState | None,
    managers: list[dict],
    histories: dict[int, dict] | None,
    history: HistoryStore,
    auto_rows: list[dict] | None,
) -> dict[str, Any]:
    payload = (histories or {}).get(int(m.entry), {})
    merits = history.merits_for(m.manager, auto_rows or [])
    overall = history.overall_for(m.manager)
    form = form_rows(managers, histories, m.entry, state, last_n=6) if histories or state else []
    return {
        "manager": manager_payload(m),
        "story": profile_story(state, m.entry) if state else "",
        "squad": squad_payload(state, m.entry) if state else {"xi": [], "bench": [], "lines": {"gk": [], "def": [], "mid": [], "fwd": []}},
        "form": json_value(form),
        "chips": chips_payload(payload),
        "fpl_career": fpl_career_payload(payload),
        "fpl_season": fpl_season_payload(payload),
        "lofthus_merits": merits_payload(merits),
        "lofthus_overall": overall,
        "lofthus_best_finish": history.best_finish(m.manager),
        "lofthus_membership": [],
        "provisional": bool(state and not state.is_finished),
        "event_id": state.event_id if state else 0,
        "month_name": state.month_name if state else "",
        "is_live": bool(state and state.is_live),
    }


def movers_payload(rows: list[ManagerLiveState], limit: int = 3) -> dict[str, Any]:
    climbers = sorted(rows, key=lambda m: (-m.live_rank_change, m.live_rank))[:limit]
    fallers = sorted(rows, key=lambda m: (m.live_rank_change, m.live_rank))[:limit]
    return {
        "climbers": [manager_payload(m) for m in climbers if m.live_rank_change > 0],
        "fallers": [manager_payload(m) for m in fallers if m.live_rank_change < 0],
    }


def live_events_payload(state: LiveState, bootstrap: dict) -> list[dict[str, Any]]:
    fixtures = fixture_payload(state, bootstrap)
    out = []
    for f in fixtures[:8]:
        clubs = {
            str(f.get("home") or ""),
            str(f.get("away") or ""),
            str(f.get("home_name") or ""),
            str(f.get("away_name") or ""),
        }
        related_impacts = [
            p for p in state.player_impacts
            if p.club in clubs and p.event_points and p.fixture_status != "not_started"
        ]
        related_impacts.sort(key=lambda p: (-p.event_points, -p.captain_count, -p.ownership_count))
        related = [player_impact_payload(p) for p in related_impacts[:2]]
        lead = related_impacts[0] if related_impacts else None
        kind = _player_event_kind(state, lead.element) if lead else ""
        headline = ""
        winner = loser = None
        if lead:
            headline = f"{lead.player} {kind}".strip() if kind else f"{lead.player}: +{lead.event_points}"
            swings = manager_swing_for_player(state, lead.element)
            gainers = [r for r in swings if r["swing"] > 0.05]
            losers = [r for r in swings if r["swing"] < -0.05]
            if gainers:
                top = gainers[0]
                winner = {"entry": top["entry"], "manager": top["manager"], "swing": top["swing"]}
            if losers:
                bottom = losers[-1]
                loser = {"entry": bottom["entry"], "manager": bottom["manager"], "swing": bottom["swing"]}
        out.append({
            **f,
            "lofthus": related,
            "lofthus_owners": lead.ownership_count if lead else 0,
            "lofthus_captains": lead.captain_count if lead else 0,
            "lofthus_headline": headline,
            "lofthus_winner": winner,
            "lofthus_loser": loser,
        })
    return out


def story_payload(story, state: LiveState | None = None) -> dict[str, Any]:
    row = story.to_dict() if hasattr(story, "to_dict") else dict(story)
    image_url = ""
    if state and nint(row.get("player_element")):
        impact = state.player(nint(row.get("player_element")))
        if impact:
            image_url = impact.image_url
    row["image_url"] = image_url
    return row


def compare_payload(
    a: ManagerLiveState,
    b: ManagerLiveState,
    state: LiveState | None,
    managers: list[dict],
    histories: dict[int, dict] | None,
) -> dict[str, Any]:
    overlap = 0
    unique_a = unique_b = 0
    if state:
        picks = state.ownership.get("picks", pd.DataFrame())
        if picks is not None and not picks.empty:
            sa = set(picks[(picks["entry"].map(nint) == a.entry) & (picks["multiplier"].map(nint) > 0)]["element"].map(nint))
            sb = set(picks[(picks["entry"].map(nint) == b.entry) & (picks["multiplier"].map(nint) > 0)]["element"].map(nint))
            overlap = len(sa & sb)
            unique_a = len(sa - sb)
            unique_b = len(sb - sa)
    return {
        "a": manager_payload(a),
        "b": manager_payload(b),
        "total_gap": a.live_total_points - b.live_total_points,
        "gw_gap": a.live_gw_points - b.live_gw_points,
        "rank_gap": b.live_rank - a.live_rank,
        "captains": {"a": a.captain, "b": b.captain},
        "chips": {"a": a.active_chip or "", "b": b.active_chip or ""},
        "overlap": overlap,
        "unique": {"a": unique_a, "b": unique_b},
        "form_a": json_value(form_rows(managers, histories, a.entry, state, last_n=5)),
        "form_b": json_value(form_rows(managers, histories, b.entry, state, last_n=5)),
        "provisional": bool(state and not state.is_finished),
    }


def season_from_bootstrap(bootstrap: dict, fallback: str) -> str:
    try:
        return season_label(bootstrap) if bootstrap else fallback
    except Exception:
        return fallback
