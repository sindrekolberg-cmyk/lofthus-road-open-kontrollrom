from __future__ import annotations

import math
import random
from collections import Counter
from itertools import combinations
from statistics import mean, median, pstdev
from typing import Any

from api.deep_analysis import DeepFPLProjectionProvider, _future_projection_bootstrap
from api.engine import AppEngine, get_engine
from lro_analysis import nfloat, nint
from lro_fpl import current_month_phase, fixture_window, player_catalog
from lro_transfer_strategy import clamp, horizon_event_ids

GOAL_LABELS = {
    "auto": "Automatisk",
    "win": "Vinne ligaen",
    "top3": "Topp 3",
    "top10": "Topp 10",
    "month": "Vinne måneden",
    "beat_next": "Slå nærmeste rival",
}


def _history_payload(histories: dict[int, dict] | None, entry: int) -> dict[str, Any]:
    return (histories or {}).get(int(entry)) or (histories or {}).get(str(int(entry))) or {}


def _history_scores(histories: dict[int, dict] | None, entry: int) -> list[float]:
    payload = _history_payload(histories, entry)
    rows = list(payload.get("current") or []) if isinstance(payload, dict) else []
    rows.sort(key=lambda row: nint(row.get("event")))
    out: list[float] = []
    for row in rows:
        points = nfloat(row.get("points"))
        cost = nfloat(row.get("event_transfers_cost"))
        out.append(points - cost)
    return out


def _future_event_ids(bootstrap: dict[str, Any], current_event: int) -> list[int]:
    ids = sorted(
        nint(event.get("id"))
        for event in bootstrap.get("events", []) or []
        if nint(event.get("id")) > int(current_event)
    )
    return [event_id for event_id in ids if event_id]


def _pick_rows(state: Any) -> list[dict[str, Any]]:
    picks = (state.ownership or {}).get("picks")
    if picks is None:
        return []
    if hasattr(picks, "to_dict"):
        return [] if getattr(picks, "empty", True) else list(picks.to_dict("records"))
    return list(picks or [])


def _nearest(state: Any, entry_id: int) -> tuple[Any | None, Any | None]:
    me = state.manager(entry_id)
    if not me:
        return None, None
    ranked = state.managers_by_rank()
    ahead = [m for m in ranked if m.live_rank < me.live_rank]
    behind = [m for m in ranked if m.live_rank > me.live_rank]
    nearest_ahead = max(ahead, key=lambda m: m.live_rank, default=None)
    nearest_behind = min(behind, key=lambda m: m.live_rank, default=None)
    return nearest_ahead, nearest_behind


def _auto_goal(rank: int, league_size: int) -> str:
    if rank <= 1:
        return "win"
    if rank <= min(5, league_size):
        return "win"
    if rank <= min(12, league_size):
        return "top3"
    return "top10"


def _projection_map(engine: AppEngine, bootstrap: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], list[int], str]:
    try:
        fixtures = list(engine.client.fixtures() or [])
    except Exception:
        fixtures = []
    projection_bootstrap, first_event = _future_projection_bootstrap(bootstrap)
    event_ids = horizon_event_ids(projection_bootstrap, 5)
    provider = DeepFPLProjectionProvider(bootstrap)
    catalog = player_catalog(bootstrap)
    out: dict[int, dict[str, Any]] = {}
    for element, player in catalog.items():
        team_id = nint(player.get("team_id"))
        rows = fixture_window(fixtures, team_id, event_ids)
        projection = provider.score(player, rows, 5)
        detail = provider.details.get(element) or {}
        out[int(element)] = {
            "element": int(element),
            "player": str(player.get("web_name") or ""),
            "club": str(player.get("club") or ""),
            "position_id": nint(player.get("position_id")),
            "projection_index": nfloat(projection.get("index_10")),
            "xgi_per90": nfloat((detail.get("stats") or {}).get("xgi_per90")),
            "form": nfloat(player.get("form")),
            "global_ownership_pct": nfloat(player.get("selected_by_pct")),
            "evidence": list(detail.get("evidence") or [])[:3],
            "confidence": str(detail.get("confidence") or "lav"),
        }
    return out, event_ids, str(first_event or "")


def _best_future_xi(squad: list[dict[str, Any]], projections: dict[int, dict[str, Any]]) -> tuple[list[int], float]:
    players: list[dict[str, Any]] = []
    for raw in squad:
        element = nint(raw.get("element"))
        meta = projections.get(element)
        if not element or not meta:
            continue
        players.append(meta)
    keepers = [row for row in players if nint(row.get("position_id")) == 1]
    outfield = [row for row in players if nint(row.get("position_id")) in {2, 3, 4}]
    if not keepers or len(outfield) < 10:
        ranked = sorted(players, key=lambda row: -nfloat(row.get("projection_index")))[:11]
        ids = [nint(row.get("element")) for row in ranked]
        score = sum(nfloat(row.get("projection_index")) for row in ranked)
        if ranked:
            score += max(nfloat(row.get("projection_index")) for row in ranked)
        return ids, score

    best_ids: list[int] = []
    best_score = -1.0
    for keeper in keepers:
        for combo in combinations(outfield, 10):
            counts = Counter(nint(row.get("position_id")) for row in combo)
            if counts[2] < 3 or counts[2] > 5 or counts[3] < 2 or counts[3] > 5 or counts[4] < 1 or counts[4] > 3:
                continue
            xi = [keeper, *combo]
            base = sum(nfloat(row.get("projection_index")) for row in xi)
            captain = max((nfloat(row.get("projection_index")) for row in xi), default=0.0)
            score = base + captain
            if score > best_score:
                best_score = score
                best_ids = [nint(row.get("element")) for row in xi]
    return best_ids, max(0.0, best_score)


def _manager_model(
    state: Any,
    histories: dict[int, dict] | None,
    projections: dict[int, dict[str, Any]],
) -> tuple[dict[int, dict[str, float]], dict[int, list[int]]]:
    pick_rows = _pick_rows(state)
    by_entry: dict[int, list[dict[str, Any]]] = {}
    owners: dict[int, set[int]] = {}
    for row in pick_rows:
        entry = nint(row.get("entry"))
        element = nint(row.get("element"))
        if entry and element:
            by_entry.setdefault(entry, []).append(row)
            owners.setdefault(element, set()).add(entry)

    xi_by_entry: dict[int, list[int]] = {}
    strength_raw: dict[int, float] = {}
    unique_raw: dict[int, float] = {}
    league_size = max(1, state.league_size)
    for manager in state.manager_live:
        xi_ids, strength = _best_future_xi(by_entry.get(manager.entry, []), projections)
        xi_by_entry[manager.entry] = xi_ids
        strength_raw[manager.entry] = strength
        if xi_ids:
            template = mean(len(owners.get(element, set())) / league_size for element in xi_ids)
            unique_raw[manager.entry] = clamp(1.0 - template, 0.0, 1.0)
        else:
            unique_raw[manager.entry] = 0.35

    strength_values = list(strength_raw.values()) or [0.0]
    strength_mid = median(strength_values)
    strength_sd = pstdev(strength_values) if len(strength_values) >= 2 else 1.0
    strength_sd = max(1.0, strength_sd)

    historical_means: list[float] = []
    raw_scores: dict[int, tuple[list[float], float, float]] = {}
    for manager in state.manager_live:
        scores = _history_scores(histories, manager.entry)
        season_avg = mean(scores) if scores else max(35.0, nfloat(manager.live_total_points) / max(1, state.event_id))
        recent = scores[-5:]
        recent_avg = mean(recent) if recent else season_avg
        raw_scores[manager.entry] = (recent, season_avg, recent_avg)
        historical_means.append(0.55 * recent_avg + 0.45 * season_avg)
    league_mean = mean(historical_means) if historical_means else 55.0

    model: dict[int, dict[str, float]] = {}
    for manager in state.manager_live:
        recent, season_avg, recent_avg = raw_scores.get(manager.entry, ([], league_mean, league_mean))
        strength_z = clamp((strength_raw.get(manager.entry, strength_mid) - strength_mid) / strength_sd, -2.0, 2.0)
        squad_adjustment = 4.0 * strength_z
        mu = 0.36 * recent_avg + 0.29 * season_avg + 0.35 * league_mean + squad_adjustment
        mu = clamp(mu, 30.0, 95.0)
        sigma = pstdev(recent) if len(recent) >= 3 else 13.0
        sigma *= 0.90 + 0.32 * unique_raw.get(manager.entry, 0.35)
        sigma = clamp(sigma, 8.0, 23.0)
        model[manager.entry] = {
            "mu": mu,
            "sigma": sigma,
            "season_avg": season_avg,
            "recent_avg": recent_avg,
            "squad_strength": strength_raw.get(manager.entry, 0.0),
            "squad_strength_z": strength_z,
            "uniqueness": unique_raw.get(manager.entry, 0.35),
            "history_sample": float(len(_history_scores(histories, manager.entry))),
            "league_mean": league_mean,
        }
    return model, xi_by_entry


def _simulate_table(
    *,
    state: Any,
    bootstrap: dict[str, Any],
    entry_id: int,
    next_entry: int | None,
    model: dict[int, dict[str, float]],
    simulations: int = 4000,
) -> dict[str, Any]:
    managers = list(state.manager_live)
    remaining = _future_event_ids(bootstrap, state.event_id)
    rounds = len(remaining)
    if not managers:
        return {}
    if rounds <= 0:
        me = state.manager(entry_id)
        return {
            "win_pct": 100.0 if me and me.live_rank == 1 else 0.0,
            "top3_pct": 100.0 if me and me.live_rank <= 3 else 0.0,
            "top10_pct": 100.0 if me and me.live_rank <= 10 else 0.0,
            "beat_next_pct": 0.0,
            "expected_rank": float(me.live_rank if me else 0),
            "rounds_remaining": 0,
            "simulations": simulations,
        }

    near_rounds = min(5, rounds)
    far_rounds = max(0, rounds - near_rounds)
    rng = random.Random(2_706_001 + state.event_id * 997 + int(entry_id))
    counts = {"win": 0, "top3": 0, "top10": 0, "beat_next": 0}
    rank_sum = 0.0

    for _ in range(simulations):
        common_near = rng.gauss(0.0, 5.5 * math.sqrt(max(1, near_rounds))) if near_rounds else 0.0
        common_far = rng.gauss(0.0, 5.0 * math.sqrt(max(1, far_rounds))) if far_rounds else 0.0
        projected: list[tuple[int, float]] = []
        for manager in managers:
            cfg = model.get(manager.entry) or {"mu": 55.0, "sigma": 13.0, "league_mean": 55.0}
            mu = nfloat(cfg.get("mu"), 55.0)
            league_mean = nfloat(cfg.get("league_mean"), 55.0)
            sigma = nfloat(cfg.get("sigma"), 13.0)
            near_mean = mu * near_rounds
            far_mu = 0.62 * mu + 0.38 * league_mean
            far_mean = far_mu * far_rounds
            independent_sd = sigma * math.sqrt(max(1, rounds)) * 0.96
            common = 0.28 * (common_near + common_far)
            future = near_mean + far_mean + common + rng.gauss(0.0, independent_sd)
            projected.append((manager.entry, nfloat(manager.live_total_points) + max(0.0, future)))
        projected.sort(key=lambda item: (-item[1], item[0]))
        ranking = {entry: index + 1 for index, (entry, _score) in enumerate(projected)}
        my_rank = ranking.get(int(entry_id), len(projected))
        rank_sum += my_rank
        counts["win"] += int(my_rank == 1)
        counts["top3"] += int(my_rank <= 3)
        counts["top10"] += int(my_rank <= 10)
        if next_entry:
            counts["beat_next"] += int(my_rank < ranking.get(int(next_entry), len(projected) + 1))

    return {
        "win_pct": round(100.0 * counts["win"] / simulations, 1),
        "top3_pct": round(100.0 * counts["top3"] / simulations, 1),
        "top10_pct": round(100.0 * counts["top10"] / simulations, 1),
        "beat_next_pct": round(100.0 * counts["beat_next"] / simulations, 1),
        "expected_rank": round(rank_sum / simulations, 1),
        "rounds_remaining": rounds,
        "simulations": simulations,
    }


def _month_probability(
    *,
    state: Any,
    bootstrap: dict[str, Any],
    entry_id: int,
    model: dict[int, dict[str, float]],
    simulations: int = 2400,
) -> float:
    phase = current_month_phase(bootstrap)
    if not phase:
        return 0.0
    remaining = [
        event_id
        for event_id in _future_event_ids(bootstrap, state.event_id)
        if nint(phase.get("start_event")) <= event_id <= nint(phase.get("stop_event"))
    ]
    me = state.manager(entry_id)
    if not me:
        return 0.0
    if not remaining:
        return 100.0 if me.month_rank == 1 else 0.0
    rounds = len(remaining)
    rng = random.Random(3_911_119 + state.event_id * 613 + int(entry_id))
    wins = 0
    managers = list(state.manager_live)
    for _ in range(simulations):
        common = rng.gauss(0.0, 5.5 * math.sqrt(rounds))
        projected: list[tuple[int, float]] = []
        for manager in managers:
            cfg = model.get(manager.entry) or {"mu": 55.0, "sigma": 13.0}
            future = nfloat(cfg.get("mu"), 55.0) * rounds + 0.28 * common + rng.gauss(0.0, nfloat(cfg.get("sigma"), 13.0) * math.sqrt(rounds) * 0.96)
            projected.append((manager.entry, nfloat(manager.month_points) + max(0.0, future)))
        projected.sort(key=lambda item: (-item[1], item[0]))
        wins += int(bool(projected) and projected[0][0] == int(entry_id))
    return round(100.0 * wins / simulations, 1)


def _target_probability(goal: str, forecast: dict[str, Any], month_pct: float) -> float:
    if goal == "win":
        return nfloat(forecast.get("win_pct"))
    if goal == "top3":
        return nfloat(forecast.get("top3_pct"))
    if goal == "top10":
        return nfloat(forecast.get("top10_pct"))
    if goal == "month":
        return month_pct
    if goal == "beat_next":
        return nfloat(forecast.get("beat_next_pct"))
    return nfloat(forecast.get("top3_pct"))


def _target_cohort(state: Any, entry_id: int, goal: str) -> list[Any]:
    me = state.manager(entry_id)
    if not me:
        return []
    ranked = state.managers_by_rank()
    if goal == "month":
        month = [m for m in state.month_ranking() if m.entry != entry_id]
        return month[:6]
    if goal == "win":
        if me.live_rank == 1:
            return [m for m in ranked if m.entry != entry_id][:5]
        return [m for m in ranked if m.live_rank < me.live_rank][:8]
    if goal == "top3":
        return [m for m in ranked if m.entry != entry_id and m.live_rank <= max(5, min(me.live_rank, 8))][:8]
    if goal == "top10":
        low = max(1, min(me.live_rank, 10) - 4)
        high = min(state.league_size, max(10, me.live_rank) + 3)
        return [m for m in ranked if m.entry != entry_id and low <= m.live_rank <= high][:10]
    ahead, behind = _nearest(state, entry_id)
    return [m for m in [ahead, behind] if m is not None][:2]


def _mission(state: Any, entry_id: int, goal: str, probability: float, rounds: int) -> dict[str, Any]:
    me = state.manager(entry_id)
    if not me:
        return {}
    ranked = state.managers_by_rank()
    ahead, behind = _nearest(state, entry_id)
    target = None
    defending = False
    target_rank = me.live_rank

    if goal == "win":
        target_rank = 1
        if me.live_rank == 1:
            target = behind
            defending = True
            headline = "Forsvar ledelsen"
        else:
            target = ranked[0]
            headline = "Jakt førsteplassen"
    elif goal == "top3":
        target_rank = 3
        if me.live_rank <= 3:
            target = next((m for m in ranked if m.live_rank == 4), behind)
            defending = True
            headline = "Hold topp 3"
        else:
            target = next((m for m in ranked if m.live_rank == 3), ranked[min(2, len(ranked) - 1)])
            headline = "Jakt topp 3"
    elif goal == "top10":
        target_rank = min(10, state.league_size)
        if me.live_rank <= target_rank:
            target = next((m for m in ranked if m.live_rank == target_rank + 1), behind)
            defending = True
            headline = "Hold topp 10"
        else:
            target = next((m for m in ranked if m.live_rank == target_rank), ranked[min(target_rank - 1, len(ranked) - 1)])
            headline = "Jakt topp 10"
    elif goal == "month":
        target_rank = 1
        month = state.month_ranking()
        target = month[0] if month else None
        defending = bool(target and target.entry == me.entry)
        if defending:
            target = next((m for m in month if m.entry != me.entry), None)
            headline = "Forsvar månedsledelsen"
        else:
            headline = "Jakt månedsseieren"
    else:
        target = ahead or behind
        defending = bool(target and target.live_rank > me.live_rank)
        target_rank = target.live_rank if target else me.live_rank
        headline = "Slå nærmeste rival"

    if goal == "month":
        my_points = nfloat(me.month_points)
        target_points = nfloat(getattr(target, "month_points", my_points))
    else:
        my_points = nfloat(me.live_total_points)
        target_points = nfloat(getattr(target, "live_total_points", my_points))
    gap = abs(target_points - my_points) if target else 0.0
    rounds = max(1, rounds)
    required = gap / rounds

    if defending:
        detail = f"Marginen er {int(round(gap))} poeng."
    elif target:
        detail = f"Du trenger å hente inn {int(round(gap))} poeng."
    else:
        detail = "Ingen relevant målmanager er tilgjengelig akkurat nå."

    if defending:
        risk = "lav" if probability >= 55 else "middels"
        strategy = "defend"
    else:
        risk = "høy" if required >= 1.5 or probability < 15 else "middels" if required >= 0.55 or probability < 40 else "lav"
        if goal == "month":
            strategy = "win_month"
        elif goal == "win":
            strategy = "win_lofthus"
        elif goal in {"top3", "top10", "beat_next"}:
            strategy = "rapid_lofthus" if risk in {"middels", "høy"} else "balanced"
        else:
            strategy = "balanced"

    return {
        "goal": goal,
        "goal_label": GOAL_LABELS.get(goal, goal),
        "headline": headline,
        "detail": detail,
        "target_rank": target_rank,
        "target_entries": [target.entry] if target else [],
        "target_manager": target.manager if target else "",
        "gap_points": round(gap, 1),
        "required_gain_per_round": round(required, 2),
        "probability_pct": round(probability, 1),
        "recommended_risk": risk,
        "recommended_strategy": strategy,
        "defending": defending,
    }


def _battle(
    state: Any,
    entry_id: int,
    cohort: list[Any],
    projections: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    rows = _pick_rows(state)
    me = state.manager(entry_id)
    if not me:
        return {"weapons": [], "threats": [], "opportunities": [], "live_swings": [], "target_entries": []}
    cohort_entries = [m.entry for m in cohort if m.entry != entry_id]
    if not cohort_entries:
        cohort_entries = [m.entry for m in state.managers_by_rank() if m.entry != entry_id][:5]
    target_size = max(1, len(cohort_entries))

    multipliers: dict[int, dict[int, int]] = {}
    ownership: dict[int, set[int]] = {}
    for row in rows:
        entry = nint(row.get("entry"))
        element = nint(row.get("element"))
        if not entry or not element:
            continue
        multipliers.setdefault(entry, {})[element] = max(0, nint(row.get("multiplier")))
        ownership.setdefault(element, set()).add(entry)
    mine = multipliers.get(int(entry_id), {})

    candidates: list[dict[str, Any]] = []
    for element, meta in projections.items():
        target_mult = sum(multipliers.get(entry, {}).get(element, 0) for entry in cohort_entries)
        target_effective = 100.0 * target_mult / target_size
        target_owners = sum(1 for entry in cohort_entries if element in multipliers.get(entry, {}))
        target_ownership = 100.0 * target_owners / target_size
        my_mult = mine.get(element, 0)
        impact = state.player(element)
        event_points = nint(getattr(impact, "event_points", 0)) if impact else 0
        live_swing = event_points * (my_mult - target_mult / target_size)
        row = {
            **meta,
            "my_multiplier": my_mult,
            "target_ownership_pct": round(target_ownership, 1),
            "target_effective_ownership_pct": round(target_effective, 1),
            "league_ownership_pct": round(100.0 * len(ownership.get(element, set())) / max(1, state.league_size), 1),
            "event_points": event_points,
            "live_swing": round(live_swing, 1),
        }
        candidates.append(row)

    weapons = [row for row in candidates if row["my_multiplier"] > 0 and row["target_ownership_pct"] <= 55 and row["projection_index"] >= 4.0]
    weapons.sort(key=lambda row: (-row["projection_index"], row["target_ownership_pct"], row["player"]))
    threats = [row for row in candidates if row["my_multiplier"] <= 0 and row["target_ownership_pct"] >= 25 and row["projection_index"] >= 4.0]
    threats.sort(key=lambda row: (-(row["projection_index"] * (0.45 + row["target_ownership_pct"] / 100.0)), row["player"]))
    opportunities = [row for row in candidates if row["my_multiplier"] <= 0 and row["target_ownership_pct"] <= 30 and row["projection_index"] >= 5.0]
    opportunities.sort(key=lambda row: (-row["projection_index"], row["target_ownership_pct"], row["player"]))
    live_swings = [row for row in candidates if abs(nfloat(row["live_swing"])) >= 0.1]
    live_swings.sort(key=lambda row: (-abs(nfloat(row["live_swing"])), row["player"]))

    return {
        "target_entries": cohort_entries,
        "target_managers": [m.manager for m in cohort if m.entry in cohort_entries],
        "weapons": weapons[:6],
        "threats": threats[:6],
        "opportunities": opportunities[:6],
        "live_swings": live_swings[:8],
    }


def _verdict(state: Any, entry_id: int, target_entries: list[int]) -> dict[str, Any]:
    me = state.manager(entry_id)
    if not me:
        return {}
    targets = [state.manager(entry) for entry in target_entries]
    targets = [m for m in targets if m is not None]
    target_avg = mean([nfloat(m.live_gw_points) for m in targets]) if targets else 0.0
    relative = nfloat(me.live_gw_points) - target_avg if targets else 0.0
    if targets:
        headline = "Du tok poeng på målgruppen" if relative > 0.5 else "Du tapte poeng til målgruppen" if relative < -0.5 else "Runden var omtrent nøytral"
    else:
        headline = "Runden er registrert"
    return {
        "headline": headline,
        "gw_points": me.live_gw_points,
        "target_average_gw": round(target_avg, 1),
        "relative_to_target": round(relative, 1),
        "rank": me.live_rank,
        "rank_change": me.live_rank_change,
    }


def build_league_intelligence_v2(
    *,
    entry_id: int,
    goal: str = "auto",
    engine: AppEngine | None = None,
) -> dict[str, Any]:
    eng = engine or get_engine()
    snap = eng.snapshot()
    if not snap.state:
        return {"ok": False, "error": "Live-data bygges. Prøv igjen om noen sekunder."}
    state = snap.state
    me = state.manager(int(entry_id))
    if not me:
        return {"ok": False, "error": "Manageren finnes ikke i ligaen."}

    normalized_goal = str(goal or "auto").strip().lower()
    if normalized_goal not in GOAL_LABELS:
        normalized_goal = "auto"
    if normalized_goal == "auto":
        normalized_goal = _auto_goal(me.live_rank, state.league_size)

    projections, horizon_events, first_event = _projection_map(eng, snap.bootstrap)
    manager_model, xi_by_entry = _manager_model(state, snap.histories, projections)
    ahead, behind = _nearest(state, int(entry_id))
    next_rival = ahead or behind
    forecast = _simulate_table(
        state=state,
        bootstrap=snap.bootstrap,
        entry_id=int(entry_id),
        next_entry=next_rival.entry if next_rival else None,
        model=manager_model,
    )
    month_pct = _month_probability(
        state=state,
        bootstrap=snap.bootstrap,
        entry_id=int(entry_id),
        model=manager_model,
    )
    probability = _target_probability(normalized_goal, forecast, month_pct)
    mission = _mission(state, int(entry_id), normalized_goal, probability, nint(forecast.get("rounds_remaining")))
    cohort = _target_cohort(state, int(entry_id), normalized_goal)
    battle = _battle(state, int(entry_id), cohort, projections)
    verdict = _verdict(state, int(entry_id), list(battle.get("target_entries") or []))

    phase = "live" if state.is_live else "verdict" if state.is_finished else "plan"
    leader = state.managers_by_rank()[0]
    my_model = manager_model.get(int(entry_id), {})
    coverage = {
        "league_size": state.league_size,
        "loaded_managers": nint((state.ownership or {}).get("loaded_managers")),
        "history_managers": sum(1 for m in state.manager_live if _history_scores(snap.histories, m.entry)),
        "projected_players": len(projections),
        "fixture_horizon_events": horizon_events,
        "first_future_event": first_event,
        "ownership_complete": bool((state.ownership or {}).get("complete", True)),
    }

    return {
        "ok": True,
        "phase": phase,
        "league": {"id": eng.config.league_id, "name": eng.config.name, "size": state.league_size},
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
            "gap_to_leader": max(0, leader.live_total_points - me.live_total_points),
        },
        "goal": {"id": normalized_goal, "label": GOAL_LABELS.get(normalized_goal, normalized_goal)},
        "forecast": {
            **forecast,
            "month_win_pct": month_pct,
            "model": "League Intelligence Monte Carlo v2",
            "model_note": "Modellen kombinerer live-tabellen, sesong- og femrundersform, variasjon i managerresultater, dagens 15-mannstropper, beste sannsynlige ellever, kapteinsverdi, kommende kampprogram og korrelert rundevarians. Tallene er prognoser, ikke bookmakerodds.",
            "manager_expected_gw": round(nfloat(my_model.get("mu")), 1),
            "manager_volatility": round(nfloat(my_model.get("sigma")), 1),
            "manager_uniqueness_pct": round(100.0 * nfloat(my_model.get("uniqueness")), 1),
            "squad_strength_index": round(nfloat(my_model.get("squad_strength")), 1),
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
        "current_best_xi": xi_by_entry.get(int(entry_id), []),
        "event": {
            "id": state.event_id,
            "is_live": state.is_live,
            "is_finished": state.is_finished,
            "status": state.event_status,
        },
        "coverage": coverage,
        "product_loop": {
            "plan": "Mål, risiko og strategisk målgruppe fastsettes før deadline.",
            "reveal": "Etter deadline kan samme målgruppe brukes til å måle kapteiner, chips, eierskap og differensialer.",
            "live": "Under kamp måles hvert relevant spillerutfall relativt til målgruppen.",
            "verdict": "Etter runden måles gevinst eller tap mot målgruppen og ny sannsynlighet beregnes.",
        },
        "data_sources": [
            "Fantasy Premier League bootstrap",
            "Fantasy Premier League fixtures",
            "Fantasy Premier League manager history",
            "Fantasy Premier League live player points",
            "Mini-ligaens live eierskap og kapteinsmultiplikatorer",
        ],
    }
