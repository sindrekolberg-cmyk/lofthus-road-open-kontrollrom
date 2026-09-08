from __future__ import annotations

import math
import random
from statistics import mean, pstdev
from typing import Any

from api.deep_analysis import DeepFPLProjectionProvider, _future_projection_bootstrap
from api.engine import get_engine
from lro_analysis import nfloat, nint
from lro_fpl import current_month_phase, fixture_window, player_catalog
from lro_transfer_strategy import horizon_event_ids

GOAL_LABELS = {
    "auto": "Automatisk",
    "win": "Vinne ligaen",
    "top3": "Topp 3",
    "top10": "Topp 10",
    "month": "Vinne måneden",
    "beat_next": "Slå nærmeste rival",
}


def _history_scores(histories: dict[int, dict] | None, entry: int) -> list[float]:
    payload = (histories or {}).get(int(entry)) or (histories or {}).get(str(int(entry))) or {}
    rows = list(payload.get("current") or []) if isinstance(payload, dict) else []
    rows.sort(key=lambda row: nint(row.get("event")))
    out: list[float] = []
    for row in rows:
        points = nfloat(row.get("points"))
        cost = nfloat(row.get("event_transfers_cost"))
        out.append(points - cost)
    return out


def _remaining_event_ids(bootstrap: dict[str, Any], current_event: int) -> list[int]:
    ids = sorted(
        nint(event.get("id"))
        for event in bootstrap.get("events", []) or []
        if nint(event.get("id")) > int(current_event)
    )
    return [event_id for event_id in ids if event_id]


def _manager_distribution(state: Any, histories: dict[int, dict] | None) -> dict[int, dict[str, float]]:
    raw_means: list[float] = []
    raw: dict[int, tuple[list[float], float]] = {}
    for manager in state.manager_live:
        scores = _history_scores(histories, manager.entry)
        recent = scores[-5:]
        season_avg = mean(scores) if scores else max(40.0, nfloat(manager.live_total_points) / max(1, state.event_id))
        recent_avg = mean(recent) if recent else season_avg
        raw[manager.entry] = (recent, recent_avg)
        raw_means.append(recent_avg)

    league_mean = mean(raw_means) if raw_means else 55.0
    out: dict[int, dict[str, float]] = {}
    for manager in state.manager_live:
        recent, recent_avg = raw.get(manager.entry, ([], league_mean))
        mu = 0.68 * recent_avg + 0.32 * league_mean
        sigma = pstdev(recent) if len(recent) >= 3 else 13.0
        sigma = max(8.0, min(22.0, sigma))
        out[manager.entry] = {
            "mean": max(30.0, min(90.0, mu)),
            "sigma": sigma,
            "sample": float(len(recent)),
        }
    return out


def _simulate_table(
    *,
    state: Any,
    histories: dict[int, dict] | None,
    bootstrap: dict[str, Any],
    entry_id: int,
    next_entry: int | None,
    simulations: int = 3500,
) -> dict[str, Any]:
    managers = list(state.manager_live)
    if not managers:
        return {}
    remaining = _remaining_event_ids(bootstrap, state.event_id)
    rounds = len(remaining)
    distributions = _manager_distribution(state, histories)
    rng = random.Random(731_000 + state.event_id * 997 + int(entry_id))
    counts = {"win": 0, "top3": 0, "top10": 0, "beat_next": 0}
    rank_sum = 0.0

    if rounds <= 0:
        me = state.manager(entry_id)
        if not me:
            return {}
        counts["win"] = simulations if me.live_rank == 1 else 0
        counts["top3"] = simulations if me.live_rank <= 3 else 0
        counts["top10"] = simulations if me.live_rank <= 10 else 0
        if next_entry:
            rival = state.manager(next_entry)
            counts["beat_next"] = simulations if rival and me.live_total_points > rival.live_total_points else 0
        return {
            "win_pct": round(100 * counts["win"] / simulations, 1),
            "top3_pct": round(100 * counts["top3"] / simulations, 1),
            "top10_pct": round(100 * counts["top10"] / simulations, 1),
            "beat_next_pct": round(100 * counts["beat_next"] / simulations, 1),
            "expected_rank": float(me.live_rank),
            "rounds_remaining": 0,
            "simulations": simulations,
        }

    for _ in range(simulations):
        projected: list[tuple[int, float]] = []
        for manager in managers:
            dist = distributions.get(manager.entry) or {"mean": 55.0, "sigma": 13.0}
            future = rng.gauss(dist["mean"] * rounds, dist["sigma"] * math.sqrt(rounds))
            projected.append((manager.entry, nfloat(manager.live_total_points) + max(0.0, future)))
        projected.sort(key=lambda item: (-item[1], item[0]))
        ranking = {entry: index + 1 for index, (entry, _score) in enumerate(projected)}
        my_rank = ranking.get(int(entry_id), len(projected))
        rank_sum += my_rank
        if my_rank == 1:
            counts["win"] += 1
        if my_rank <= 3:
            counts["top3"] += 1
        if my_rank <= 10:
            counts["top10"] += 1
        if next_entry and my_rank < ranking.get(int(next_entry), len(projected) + 1):
            counts["beat_next"] += 1

    return {
        "win_pct": round(100 * counts["win"] / simulations, 1),
        "top3_pct": round(100 * counts["top3"] / simulations, 1),
        "top10_pct": round(100 * counts["top10"] / simulations, 1),
        "beat_next_pct": round(100 * counts["beat_next"] / simulations, 1),
        "expected_rank": round(rank_sum / simulations, 1),
        "rounds_remaining": rounds,
        "simulations": simulations,
    }


def _month_probability(
    *,
    state: Any,
    histories: dict[int, dict] | None,
    bootstrap: dict[str, Any],
    entry_id: int,
    simulations: int = 2500,
) -> float:
    managers = list(state.manager_live)
    me = state.manager(entry_id)
    if not managers or not me:
        return 0.0
    phase = current_month_phase(bootstrap)
    if not phase:
        return 0.0
    remaining = [
        event_id
        for event_id in _remaining_event_ids(bootstrap, state.event_id)
        if nint(phase.get("start_event")) <= event_id <= nint(phase.get("stop_event"))
    ]
    if not remaining:
        return 100.0 if me.month_rank == 1 else 0.0
    rounds = len(remaining)
    distributions = _manager_distribution(state, histories)
    rng = random.Random(880_000 + state.event_id * 613 + int(entry_id))
    wins = 0
    for _ in range(simulations):
        projected = []
        for manager in managers:
            dist = distributions.get(manager.entry) or {"mean": 55.0, "sigma": 13.0}
            future = rng.gauss(dist["mean"] * rounds, dist["sigma"] * math.sqrt(rounds))
            projected.append((manager.entry, nfloat(manager.month_points) + max(0.0, future)))
        projected.sort(key=lambda item: (-item[1], item[0]))
        if projected and projected[0][0] == int(entry_id):
            wins += 1
    return round(100 * wins / simulations, 1)


def _goal_for_rank(rank: int) -> str:
    if rank <= 1:
        return "win"
    if rank <= 5:
        return "win"
    if rank <= 12:
        return "top3"
    return "top10"


def _target_probability(goal: str, forecast: dict[str, Any], month_pct: float) -> float:
    if goal == "win":
        return nfloat(forecast.get("win_pct"))
    if goal == "top3":
        return nfloat(forecast.get("top3_pct"))
    if goal == "top10":
        return nfloat(forecast.get("top10_pct"))
    if goal == "month":
        return nfloat(month_pct)
    if goal == "beat_next":
        return nfloat(forecast.get("beat_next_pct"))
    return nfloat(forecast.get("top3_pct"))


def _nearest_targets(state: Any, entry_id: int) -> tuple[Any | None, Any | None, list[Any]]:
    ranked = state.managers_by_rank()
    me = state.manager(entry_id)
    if not me:
        return None, None, []
    ahead = [m for m in ranked if m.live_rank < me.live_rank]
    behind = [m for m in ranked if m.live_rank > me.live_rank]
    nearest_ahead = max(ahead, key=lambda m: m.live_rank, default=None)
    nearest_behind = min(behind, key=lambda m: m.live_rank, default=None)
    if me.live_rank == 1:
        cohort = behind[:5]
    else:
        cohort = sorted(ahead, key=lambda m: m.live_rank, reverse=True)[:5]
    return nearest_ahead, nearest_behind, cohort


def _mission(state: Any, entry_id: int, goal: str, probability: float) -> dict[str, Any]:
    me = state.manager(entry_id)
    nearest_ahead, nearest_behind, cohort = _nearest_targets(state, entry_id)
    if not me:
        return {}

    if goal == "win":
        leader = state.managers_by_rank()[0]
        if me.live_rank == 1:
            gap = max(0, me.live_total_points - nfloat(getattr(nearest_behind, "live_total_points", me.live_total_points)))
            headline = "Forsvar ledelsen"
            detail = f"Ledelsen er {int(gap)} poeng til nærmeste utfordrer." if nearest_behind else "Du leder ligaen."
            target_entries = [nearest_behind.entry] if nearest_behind else []
        else:
            gap = max(0, leader.live_total_points - me.live_total_points)
            headline = "Ta innpå førsteplassen"
            detail = f"Du er {int(gap)} poeng bak {leader.manager}."
            target_entries = [leader.entry]
        target_rank = 1
    elif goal == "top3":
        third = next((m for m in state.managers_by_rank() if m.live_rank == 3), state.managers_by_rank()[min(2, state.league_size - 1)])
        gap = max(0, third.live_total_points - me.live_total_points)
        headline = "Jakt topp 3" if me.live_rank > 3 else "Hold topp 3"
        detail = f"Avstanden til 3. plass er {int(gap)} poeng." if me.live_rank > 3 else f"Du er nummer {me.live_rank}."
        target_entries = [third.entry] if third.entry != me.entry else []
        target_rank = 3
    elif goal == "top10":
        tenth = next((m for m in state.managers_by_rank() if m.live_rank == 10), state.managers_by_rank()[min(9, state.league_size - 1)])
        gap = max(0, tenth.live_total_points - me.live_total_points)
        headline = "Jakt topp 10" if me.live_rank > 10 else "Hold topp 10"
        detail = f"Avstanden til 10. plass er {int(gap)} poeng." if me.live_rank > 10 else f"Du er nummer {me.live_rank}."
        target_entries = [tenth.entry] if tenth.entry != me.entry else []
        target_rank = 10
    elif goal == "month":
        month_ranked = state.month_ranking()
        leader = month_ranked[0] if month_ranked else me
        gap = max(0, leader.month_points - me.month_points)
        headline = "Vinn måneden"
        detail = f"Du er {int(gap)} poeng bak månedslederen." if leader.entry != me.entry else "Du leder måneden."
        target_entries = [leader.entry] if leader.entry != me.entry else []
        target_rank = 1
    else:
        rival = nearest_ahead or nearest_behind
        gap = abs(nint(getattr(rival, "live_total_points", me.live_total_points)) - me.live_total_points) if rival else 0
        headline = f"Passer {rival.manager}" if rival and rival.live_rank < me.live_rank else "Hold nærmeste rival bak deg"
        detail = f"Det skiller {int(gap)} poeng." if rival else "Ingen nær rival er tilgjengelig."
        target_entries = [rival.entry] if rival else []
        target_rank = rival.live_rank if rival else me.live_rank

    rounds = max(1, 38 - state.event_id)
    if me.live_rank == 1 and goal == "win":
        risk = "lav" if probability >= 55 else "middels"
    else:
        points_per_round = gap / rounds if rounds else gap
        risk = "høy" if points_per_round >= 2.0 or probability < 15 else "middels" if points_per_round >= 0.7 or probability < 40 else "lav"

    return {
        "goal": goal,
        "goal_label": GOAL_LABELS.get(goal, goal),
        "headline": headline,
        "detail": detail,
        "target_rank": target_rank,
        "target_entries": target_entries,
        "gap_points": int(gap),
        "probability_pct": round(probability, 1),
        "recommended_risk": risk,
        "cohort": [{"entry": m.entry, "manager": m.manager, "rank": m.live_rank, "total": m.live_total_points} for m in cohort],
    }


def _pick_rows(state: Any) -> list[dict[str, Any]]:
    picks = (state.ownership or {}).get("picks")
    if picks is None:
        return []
    if hasattr(picks, "to_dict"):
        return [] if getattr(picks, "empty", True) else list(picks.to_dict("records"))
    return list(picks or [])


def _multipliers(rows: list[dict[str, Any]]) -> dict[int, dict[int, int]]:
    out: dict[int, dict[int, int]] = {}
    for row in rows:
        entry = nint(row.get("entry"))
        element = nint(row.get("element"))
        if not entry or not element:
            continue
        out.setdefault(entry, {})[element] = max(0, nint(row.get("multiplier")))
    return out


def _league_owners(rows: list[dict[str, Any]]) -> dict[int, set[int]]:
    out: dict[int, set[int]] = {}
    for row in rows:
        entry = nint(row.get("entry"))
        element = nint(row.get("element"))
        if entry and element:
            out.setdefault(element, set()).add(entry)
    return out


def _battle_and_market(state: Any, bootstrap: dict[str, Any], entry_id: int) -> dict[str, Any]:
    me = state.manager(entry_id)
    if not me:
        return {"weapons": [], "threats": [], "opportunities": [], "live_swings": []}
    _ahead, _behind, cohort = _nearest_targets(state, entry_id)
    cohort_entries = [m.entry for m in cohort]
    if not cohort_entries:
        cohort_entries = [m.entry for m in state.managers_by_rank() if m.entry != entry_id][:5]
    rows = _pick_rows(state)
    multipliers = _multipliers(rows)
    owners = _league_owners(rows)
    user_mult = multipliers.get(entry_id, {})
    league_size = max(1, state.league_size)
    cohort_size = max(1, len(cohort_entries))
    catalog = player_catalog(bootstrap)
    impact_map = {p.element: p for p in state.player_impacts}

    try:
        fixtures = list(get_engine().client.fixtures() or [])
    except Exception:
        fixtures = list(state.fixtures or [])
    projection_bootstrap, _ = _future_projection_bootstrap(bootstrap)
    event_ids = horizon_event_ids(projection_bootstrap, 5)
    provider = DeepFPLProjectionProvider(bootstrap)

    candidates: list[dict[str, Any]] = []
    for element, player in catalog.items():
        league_count = len(owners.get(element, set()))
        cohort_count = sum(1 for entry in cohort_entries if element in multipliers.get(entry, {}))
        cohort_pct = 100.0 * cohort_count / cohort_size
        league_pct = 100.0 * league_count / league_size
        team_id = nint(player.get("team_id"))
        fx = fixture_window(fixtures, team_id, event_ids)
        projection = provider.score(player, fx, 5)
        projection_index = nfloat(projection.get("index_10"))
        impact = impact_map.get(element)
        event_points = nint(getattr(impact, "event_points", 0))
        target_mult = sum(multipliers.get(entry, {}).get(element, 0) for entry in cohort_entries) / cohort_size
        my_mult = user_mult.get(element, 0)
        live_swing = round(event_points * (my_mult - target_mult), 1)
        status = str(player.get("status") or "a")
        chance = player.get("chance_next")
        if status in {"u", "s"} or (chance is not None and nint(chance) < 50):
            continue
        candidates.append(
            {
                "element": element,
                "player": str(player.get("web_name") or ""),
                "club": str(player.get("club") or ""),
                "position": str(player.get("position") or ""),
                "price": nfloat(player.get("current_price")),
                "event_points": event_points,
                "projection_index": round(projection_index, 1),
                "lofthus_ownership_pct": round(league_pct, 1),
                "target_ownership_pct": round(cohort_pct, 1),
                "global_ownership_pct": round(nfloat(player.get("selected_by_pct")), 1),
                "form": round(nfloat(player.get("form")), 1),
                "xgi_per90": round(nfloat(player.get("xgi_per90")), 3),
                "my_multiplier": my_mult,
                "target_multiplier": round(target_mult, 2),
                "live_swing": live_swing,
                "evidence": list((provider.details.get(element) or {}).get("evidence") or [])[:3],
            }
        )

    weapons = [row for row in candidates if row["my_multiplier"] > 0]
    weapons.sort(key=lambda row: (-(row["live_swing"] if state.is_live else row["projection_index"] + (100 - row["target_ownership_pct"]) / 35), row["player"]))
    threats = [row for row in candidates if row["my_multiplier"] <= 0 and row["target_ownership_pct"] > 0]
    threats.sort(key=lambda row: (-((-row["live_swing"]) if state.is_live else row["projection_index"] + row["target_ownership_pct"] / 30), row["player"]))
    opportunities = [row for row in candidates if row["my_multiplier"] <= 0 and row["projection_index"] >= 4.5]
    opportunities.sort(key=lambda row: (-(row["projection_index"] + (100 - row["target_ownership_pct"]) / 45 + row["form"] / 10), row["price"]))
    live_swings = [row for row in candidates if abs(row["live_swing"]) >= 0.5]
    live_swings.sort(key=lambda row: -abs(row["live_swing"]))

    return {
        "target_entries": cohort_entries,
        "weapons": weapons[:5],
        "threats": threats[:5],
        "opportunities": opportunities[:6],
        "live_swings": live_swings[:8],
    }


def _verdict(state: Any, entry_id: int, target_entries: list[int]) -> dict[str, Any]:
    me = state.manager(entry_id)
    if not me:
        return {}
    target = [state.manager(entry) for entry in target_entries]
    target = [manager for manager in target if manager]
    cohort_avg = mean([manager.live_gw_points for manager in target]) if target else mean([m.live_gw_points for m in state.manager_live])
    relative = round(me.live_gw_points - cohort_avg, 1)
    if me.live_rank_change > 0:
        headline = f"Opp {me.live_rank_change} plass{'er' if me.live_rank_change != 1 else ''}"
    elif me.live_rank_change < 0:
        headline = f"Ned {abs(me.live_rank_change)} plass{'er' if abs(me.live_rank_change) != 1 else ''}"
    else:
        headline = "Uendret plassering"
    return {
        "headline": headline,
        "rank": me.live_rank,
        "rank_change": me.live_rank_change,
        "gw_points": me.live_gw_points,
        "target_average_gw": round(cohort_avg, 1),
        "relative_to_target": relative,
    }


def build_league_intelligence(entry_id: int, goal: str = "auto") -> dict[str, Any]:
    eng = get_engine()
    snap = eng.snapshot()
    if not snap.state:
        return {"ok": False, "error": "Live-data er ikke klare ennå."}
    state = snap.state
    me = state.manager(int(entry_id))
    if not me:
        return {"ok": False, "error": "Manageren finnes ikke i ligaen."}

    normalized_goal = str(goal or "auto").strip().lower()
    if normalized_goal not in GOAL_LABELS:
        normalized_goal = "auto"
    if normalized_goal == "auto":
        normalized_goal = _goal_for_rank(me.live_rank)

    nearest_ahead, nearest_behind, _cohort = _nearest_targets(state, int(entry_id))
    next_rival = nearest_ahead or nearest_behind
    forecast = _simulate_table(
        state=state,
        histories=snap.histories,
        bootstrap=snap.bootstrap,
        entry_id=int(entry_id),
        next_entry=next_rival.entry if next_rival else None,
    )
    month_pct = _month_probability(
        state=state,
        histories=snap.histories,
        bootstrap=snap.bootstrap,
        entry_id=int(entry_id),
    )
    probability = _target_probability(normalized_goal, forecast, month_pct)
    mission = _mission(state, int(entry_id), normalized_goal, probability)
    battle = _battle_and_market(state, snap.bootstrap, int(entry_id))
    verdict = _verdict(state, int(entry_id), list(battle.get("target_entries") or []))

    phase = "live" if state.is_live else "verdict" if state.is_finished else "plan"
    leader = state.managers_by_rank()[0]
    gap_to_leader = max(0, leader.live_total_points - me.live_total_points)

    return {
        "ok": True,
        "phase": phase,
        "manager": {
            "entry": me.entry,
            "manager": me.manager,
            "team": me.team,
            "rank": me.live_rank,
            "total": me.live_total_points,
            "gw": me.live_gw_points,
            "month_rank": me.month_rank,
            "month_points": me.month_points,
            "rank_change": me.live_rank_change,
            "players_remaining": me.players_remaining,
            "gap_to_leader": gap_to_leader,
        },
        "goal": {"id": normalized_goal, "label": GOAL_LABELS.get(normalized_goal, normalized_goal)},
        "forecast": {
            **forecast,
            "month_win_pct": month_pct,
            "model": "Monte Carlo v1",
            "model_note": "Prognosen simulerer resten av sesongen fra live-tabellen og managerenes nylige poengnivå. Den er beslutningsstøtte, ikke bookmakerodds.",
        },
        "mission": mission,
        "battle": battle,
        "verdict": verdict,
        "next_rival": {
            "entry": next_rival.entry,
            "manager": next_rival.manager,
            "rank": next_rival.live_rank,
            "total": next_rival.live_total_points,
            "gap": abs(next_rival.live_total_points - me.live_total_points),
        } if next_rival else None,
        "event": {
            "id": state.event_id,
            "is_live": state.is_live,
            "is_finished": state.is_finished,
            "status": state.event_status,
        },
        "product_loop": {
            "plan": "Velg mål og bruk Transferstrategi før deadline.",
            "reveal": "Etter deadline identifiseres eierskap, kapteiner og viktigste forskjeller mot målgruppen.",
            "live": "Under kamp måles spillerhendelser som relativt utslag mot målgruppen.",
            "verdict": "Etter runden måles plassering, relativ gevinst og hva som drev utslaget.",
        },
        "data_sources": [
            "Fantasy Premier League bootstrap",
            "Fantasy Premier League fixtures",
            "Fantasy Premier League manager history",
            "Lofthus Road Open live ownership",
            "Lofthus Road Open live table",
        ],
    }
