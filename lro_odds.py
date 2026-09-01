from __future__ import annotations

import math
import random
from typing import Any

import pandas as pd

from lro_analysis import nfloat, nint
from lro_history import HistoryStore


def _rank_quality(rank: Any) -> float:
    r = max(1.0, nfloat(rank, 10_000_000))
    # 1st ~100, 100k ~55, 1m ~25, 10m ~0.
    return max(0.0, min(100.0, 100.0 - 25.0 * math.log10(r)))


def historical_strength(entry_history: dict, merits: dict | None = None) -> float:
    past = entry_history.get("past", []) or []
    ranks = [nint(r.get("rank"), 0) for r in past if nint(r.get("rank"), 0) > 0]
    if ranks:
        recent = ranks[-5:]
        weights = list(range(1, len(recent) + 1))
        score = sum(_rank_quality(r) * w for r, w in zip(recent, weights)) / sum(weights)
        best = max(_rank_quality(r) for r in ranks)
        score = 0.78 * score + 0.22 * best
    else:
        score = 42.0
    merits = merits or {}
    # Trophies are a small prior, never the engine.
    trophy_bonus = min(5.0, 1.0 * nint(merits.get("league_gold")) + 0.45 * nint(merits.get("cup_gold")) + 0.18 * nint(merits.get("monthly_gold")))
    return max(0.0, min(100.0, score + trophy_bonus))


def current_strength(manager: dict, entry_history: dict, team_value: float | None = None, captain_quality: float | None = None) -> float:
    current = entry_history.get("current", []) or []
    points = [nint(r.get("points")) for r in current if nint(r.get("event")) > 0]
    gw = len(points)
    latest = current[-1] if current else {}
    if gw:
        ppg = sum(points) / gw
        recent = sum(points[-5:]) / min(5, gw)
        # Calibrated to a normal FPL weekly range; intentionally coarse.
        ppg_score = max(0.0, min(100.0, (ppg - 35.0) * 2.0))
        recent_score = max(0.0, min(100.0, (recent - 35.0) * 2.0))
        rank_score = _rank_quality(latest.get("overall_rank")) if nint(latest.get("overall_rank")) else 50.0
        current_score = 0.56 * ppg_score + 0.27 * recent_score + 0.17 * rank_score
    else:
        total = nint(manager.get("total"))
        event = max(1, nint(manager.get("raw", {}).get("event"), 1))
        current_score = max(0.0, min(100.0, ((total / event) - 35.0) * 2.0)) if total else 50.0

    # Public entry history normally includes bank/value/transfer costs/bench points.
    # Use them if present; no extra 63-picks load is required for the odds model.
    if team_value is None and latest:
        raw_value = nfloat(latest.get("value"), 0.0)
        team_value = raw_value / 10.0 if raw_value > 200 else raw_value
    if team_value is not None and team_value > 0:
        current_score += max(-3.0, min(3.0, (team_value - 100.0) * 0.7))
    transfer_cost = sum(nint(r.get("event_transfers_cost")) for r in current)
    current_score -= min(4.0, transfer_cost * 0.12)
    bench_points = sum(nint(r.get("points_on_bench")) for r in current)
    if gw:
        # Only a tiny signal: bench points often reflect luck, not just poor choices.
        current_score -= min(2.0, max(0.0, bench_points / gw - 10.0) * 0.08)
    if captain_quality is not None:
        current_score += max(-3.0, min(3.0, (captain_quality - 50.0) / 12.0))
    return max(0.0, min(100.0, current_score))


def history_weight(current_event: int) -> float:
    # Explicitly fades the past as the season matures.
    if current_event <= 1:
        return 0.58
    if current_event <= 5:
        return 0.48
    if current_event <= 10:
        return 0.36
    if current_event <= 20:
        return 0.20
    if current_event <= 30:
        return 0.10
    return 0.05


def manager_strength(
    manager: dict,
    entry_history: dict,
    current_event: int,
    history_store: HistoryStore,
    team_value: float | None = None,
    captain_quality: float | None = None,
) -> dict:
    name = history_store.canonical(str(manager.get("player_name") or ""))
    merits = history_store.merits_for(name)
    past_score = historical_strength(entry_history, merits)
    now_score = current_strength(manager, entry_history, team_value, captain_quality)
    hw = history_weight(current_event)
    score = hw * past_score + (1.0 - hw) * now_score
    return {
        "entry": nint(manager.get("entry")),
        "manager": name,
        "history_score": round(past_score, 1),
        "current_score": round(now_score, 1),
        "history_weight": round(hw, 2),
        "strength": round(score, 1),
    }


def _weekly_sd(entry_history: dict) -> float:
    points = [nfloat(r.get("points")) for r in entry_history.get("current", []) or [] if nint(r.get("event")) > 0]
    if len(points) < 3:
        return 16.0
    mean = sum(points) / len(points)
    var = sum((x - mean) ** 2 for x in points) / max(1, len(points) - 1)
    return max(10.0, min(24.0, math.sqrt(var)))


def simulate_group(
    managers: list[dict],
    histories: dict[int, dict],
    current_event: int,
    history_store: HistoryStore,
    team_values: dict[int, float] | None = None,
    current_scores: dict[int, float] | None = None,
    remaining_events: int | None = None,
    simulations: int = 5000,
    seed: int = 400,
) -> pd.DataFrame:
    if not managers:
        return pd.DataFrame()
    team_values = team_values or {}
    current_scores = current_scores or {}
    remaining_events = max(0, int(remaining_events if remaining_events is not None else 38 - int(current_event)))
    strength_rows = []
    for m in managers:
        entry = nint(m.get("entry"))
        strength_rows.append(
            manager_strength(
                m,
                histories.get(entry, {}),
                current_event,
                history_store,
                team_value=team_values.get(entry),
            )
        )
    strengths = {r["entry"]: r for r in strength_rows}
    wins = {r["entry"]: 0 for r in strength_rows}
    top3 = {r["entry"]: 0 for r in strength_rows}
    rng = random.Random(seed)
    for _ in range(max(500, int(simulations))):
        totals = []
        for m in managers:
            entry = nint(m.get("entry"))
            base_total = nfloat(current_scores.get(entry, m.get("total")), 0.0)
            s = strengths[entry]["strength"]
            # Strength 50 => ~55 projected points/GW. Every 10 strength points ≈ 2.8 p/GW.
            mean_week = 55.0 + (s - 50.0) * 0.28
            hist = histories.get(entry, {})
            sd_week = _weekly_sd(hist)
            future = rng.gauss(mean_week * remaining_events, sd_week * math.sqrt(max(1, remaining_events))) if remaining_events else 0.0
            totals.append((base_total + future, entry))
        totals.sort(reverse=True)
        if totals:
            wins[totals[0][1]] += 1
            for _, entry in totals[:3]:
                top3[entry] += 1
    rows = []
    sims = max(500, int(simulations))
    for m in managers:
        entry = nint(m.get("entry"))
        rows.append({
            **strengths[entry],
            "win_pct": round(100.0 * wins[entry] / sims, 1),
            "top3_pct": round(100.0 * top3[entry] / sims, 1),
        })
    return pd.DataFrame(rows).sort_values(["win_pct", "strength"], ascending=[False, False]).reset_index(drop=True)


def compare_group_odds(
    managers: list[dict],
    histories: dict[int, dict],
    current_event: int,
    history_store: HistoryStore,
    period_events: int = 3,
    month_scores: dict[int, float] | None = None,
    simulations: int = 4000,
) -> pd.DataFrame:
    scores = month_scores or {nint(m.get("entry")): 0.0 for m in managers}
    return simulate_group(
        managers,
        histories,
        current_event,
        history_store,
        current_scores=scores,
        remaining_events=max(1, period_events),
        simulations=simulations,
        seed=401,
    )


def decimal_odds_from_pct(pct: float) -> str:
    p = max(0.2, min(99.0, nfloat(pct)))
    return f"{min(501.0, 100.0 / p):.2f}"
