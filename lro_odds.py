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


def _preseason_rank_score(rank: Any) -> float:
    """The same broad rank scale used by the old pre-season market."""
    if rank is None:
        return 0.0
    try:
        rank = max(1.0, float(rank))
    except (TypeError, ValueError):
        return 0.0
    score = 100.0 - 10.0 * math.log10(rank)
    return max(0.0, min(100.0, score))


def _mean(values: list[float]) -> float:
    vals = [float(v) for v in values if v is not None]
    return sum(vals) / len(vals) if vals else 0.0




def _preseason_merits(history_store: HistoryStore, name: str) -> dict:
    """Merits as they existed before the current 2026/27 season started.

    Crucially, this bypasses current-season fallback podiums so the published
    pre-season market does not rewrite itself after August results arrive.
    """
    key = history_store.key(name)
    overall = history_store.overall_results()
    cup = history_store.cup_results()
    official_monthly = history_store.official_monthly_titles()

    def count(df: pd.DataFrame, column: str) -> int:
        if df is None or df.empty or column not in df.columns:
            return 0
        return int(sum(1 for value in df[column].tolist() if history_store.key(str(value or "")) == key))

    return {
        "league_gold": count(overall, "winner"),
        "league_silver": count(overall, "runner_up"),
        "league_bronze": count(overall, "third_place"),
        "cup_gold": count(cup, "winner"),
        "cup_silver": count(cup, "runner_up"),
        "monthly_gold": int(official_monthly.get(key, 0)),
    }

def build_preseason_odds(
    managers: list[dict],
    histories: dict[int, dict],
    history_store: HistoryStore,
) -> pd.DataFrame:
    """Reconstruct the pre-2026/27 LRO bookmaker table from past FPL history only.

    Current-season points are deliberately excluded. This keeps the table frozen in
    spirit: it answers what the model thought before GW1, rather than quietly
    rewriting history after every weekend.
    """
    rows: list[dict] = []
    for manager in managers:
        entry = nint(manager.get("entry"))
        hist = histories.get(entry, {}) or {}
        past = sorted(hist.get("past", []) or [], key=lambda r: str(r.get("season_name") or ""))
        ranks = [nint(r.get("rank"), 0) for r in past if nint(r.get("rank"), 0) > 0]
        scores = [_preseason_rank_score(r) for r in ranks]
        last2 = scores[-2:]
        last3 = scores[-3:]
        last5 = scores[-5:]
        recent_ranks = ranks[-5:]
        seasons = len(ranks)
        best_score = max(scores) if scores else 0.0
        recent_score = _mean(last2)
        last_3_score = _mean(last3)
        last_5_score = _mean(last5)
        consistency_score = 100.0 * sum(1 for r in recent_ranks if r <= 500_000) / len(recent_ranks) if recent_ranks else 0.0
        top_100k = sum(1 for r in ranks if r <= 100_000)
        top_500k = sum(1 for r in ranks if r <= 500_000)
        top_100k_rate = top_100k / seasons * 100.0 if seasons else 0.0
        top_500k_rate = top_500k / seasons * 100.0 if seasons else 0.0
        total_rating = (
            0.45 * last_3_score
            + 0.15 * recent_score
            + 0.15 * last_5_score
            + 0.10 * best_score
            + 0.07 * consistency_score
            + 0.05 * top_100k_rate
            + 0.03 * top_500k_rate
        )
        name = history_store.canonical(str(manager.get("player_name") or "Ukjent manager"))
        merits = _preseason_merits(history_store, name)
        rows.append({
            "entry": entry,
            "manager": name,
            "seasons": seasons,
            "total_rating": total_rating,
            "last_3_score": last_3_score,
            "last_5_score": last_5_score,
            "recent_score": recent_score,
            "best_score": best_score,
            "consistency_score": consistency_score,
            "top_100k": top_100k,
            "top_500k": top_500k,
            "last_rank": ranks[-1] if ranks else 9_999_999,
            "avg3_rank": _mean([float(x) for x in ranks[-3:]]) if ranks[-3:] else 9_999_999,
            "league_gold": nint(merits.get("league_gold")),
            "league_silver": nint(merits.get("league_silver")),
            "league_bronze": nint(merits.get("league_bronze")),
            "cup_gold": nint(merits.get("cup_gold")),
            "cup_silver": nint(merits.get("cup_silver")),
            "monthly_gold": nint(merits.get("monthly_gold")),
        })

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    market_score = (
        0.30 * df["total_rating"]
        + 0.30 * df["last_3_score"]
        + 0.12 * df["recent_score"]
        + 0.10 * df["last_5_score"]
        + 0.08 * df["best_score"]
        + 0.06 * df["consistency_score"]
        + 0.04 * df["top_100k"].clip(0, 6) * 6
    )
    market_score += df["league_gold"].clip(0, 3) * 0.75
    market_score += df["league_silver"].clip(0, 3) * 0.32
    market_score += df["league_bronze"].clip(0, 3) * 0.16
    market_score += df["cup_gold"].clip(0, 4) * 0.24
    market_score += df["cup_silver"].clip(0, 4) * 0.10
    market_score += df["monthly_gold"].clip(0, 6) * 0.10
    market_score += df["top_500k"].clip(0, 12) * 0.06
    market_score = market_score.where(df["seasons"] > 2, market_score - 2.2)
    market_score = market_score.where(df["last_rank"] <= 2_000_000, market_score - 1.4)
    market_score = market_score.where(df["avg3_rank"] <= 1_700_000, market_score - 1.4)
    market_score = market_score.where(df["avg3_rank"] <= 2_500_000, market_score - 1.0)
    df["market_score"] = market_score

    max_score = float(market_score.max()) if len(df) else 0.0
    df["winner_odds"] = 3.25 * ((max_score - market_score) / 8.8).apply(math.exp)
    elite = (
        (df["avg3_rank"] <= 350_000)
        | (df["top_100k"] >= 4)
        | (((df["league_gold"] * 2 + df["league_silver"] + df["cup_gold"]) >= 2) & (df["top_500k"] >= 5))
    )
    df.loc[elite, "winner_odds"] *= 0.88
    df.loc[df["avg3_rank"] > 1_500_000, "winner_odds"] *= 1.18
    df.loc[df["last_rank"] > 2_500_000, "winner_odds"] *= 1.12
    df.loc[df["seasons"] <= 2, "winner_odds"] *= 1.18
    df["winner_odds"] = df["winner_odds"].clip(lower=3.00, upper=251.00)
    df = df.sort_values(["winner_odds", "manager"], ascending=[True, True]).reset_index(drop=True)
    for idx, cap in {0: 3.25, 1: 4.00, 2: 4.75, 3: 5.75, 4: 7.25}.items():
        if idx < len(df) and float(df.loc[idx, "winner_odds"]) > cap:
            df.loc[idx, "winner_odds"] = cap
    for idx in range(1, len(df)):
        minimum = float(df.loc[idx - 1, "winner_odds"]) + 0.10
        if float(df.loc[idx, "winner_odds"]) < minimum:
            df.loc[idx, "winner_odds"] = minimum

    top3 = []
    for odd in df["winner_odds"].astype(float):
        implied = 1.0 / max(odd, 1.01)
        factor = 2.25 if odd <= 5 else 2.05 if odd <= 10 else 1.85 if odd <= 25 else 1.65
        probability = min(max(implied * factor, 0.006), 0.56)
        top3.append(min(max(1.0 / (probability * 1.04), 1.70), 151.00))
    df["top3_odds"] = top3
    df.insert(0, "preseason_rank", range(1, len(df) + 1))
    return df


def build_live_market(
    managers: list[dict],
    histories: dict[int, dict],
    current_event: int,
    history_store: HistoryStore,
    preseason: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Update the frozen pre-season market with current LRO performance.

    The old live model rebuilt manager strength from scratch, which could make a
    manager's odds drift the wrong way after a strong start. This market treats
    the pre-season odds as the prior, then lets current points/rank gradually
    matter more as the season matures. At GW1/2 the prior still dominates; by
    spring the live table has earned the right to dominate.
    """
    if not managers:
        return pd.DataFrame()
    current_event = max(0, int(current_event or 0))
    pre = preseason.copy() if isinstance(preseason, pd.DataFrame) else pd.DataFrame()
    if pre.empty:
        pre = build_preseason_odds(managers, histories, history_store)
    if pre.empty:
        return pd.DataFrame()

    by_entry = {nint(m.get('entry')): m for m in managers if nint(m.get('entry'))}
    pre = pre.copy()
    if 'entry' not in pre.columns:
        pre['entry'] = 0
    if 'preseason_rank' not in pre.columns:
        pre = pre.sort_values(['winner_odds', 'manager'], ascending=[True, True]).reset_index(drop=True)
        pre.insert(0, 'preseason_rank', range(1, len(pre) + 1))

    # Robustly recover entry ids by canonical manager name when an old frozen CSV
    # predates the entry column.
    name_to_entry = {
        history_store.key(str(m.get('player_name') or '')): nint(m.get('entry'))
        for m in managers if nint(m.get('entry'))
    }
    for idx, row in pre.iterrows():
        if nint(row.get('entry')) <= 0:
            key = history_store.key(str(row.get('manager') or ''))
            if key in name_to_entry:
                pre.at[idx, 'entry'] = name_to_entry[key]

    rows = []
    n = max(1, len(managers))
    totals = [nfloat(m.get('total')) for m in managers]
    mean_total = sum(totals) / len(totals) if totals else 0.0
    variance = sum((x - mean_total) ** 2 for x in totals) / max(1, len(totals) - 1) if len(totals) > 1 else 1.0
    sd_total = max(8.0, math.sqrt(variance))

    for _, p in pre.iterrows():
        entry = nint(p.get('entry'))
        manager = by_entry.get(entry)
        if not manager:
            continue
        pre_odds = max(1.01, nfloat(p.get('winner_odds'), 251.0))
        prior = 1.0 / pre_odds
        current_rank = max(1, nint(manager.get('rank'), n))
        pre_rank = max(1, nint(p.get('preseason_rank'), n))
        total = nfloat(manager.get('total'))
        z_points = max(-3.0, min(3.0, (total - mean_total) / sd_total))
        # Positive means the manager is outperforming their pre-season ranking.
        rank_delta = max(-1.0, min(1.0, (pre_rank - current_rank) / max(1.0, n - 1.0)))
        current_percentile = 1.0 - (current_rank - 1.0) / max(1.0, n - 1.0)
        centered_rank = (current_percentile - 0.5) * 2.0
        evidence = 0.85 * z_points + 1.80 * rank_delta + 0.28 * centered_rank
        rows.append({
            'entry': entry,
            'manager': history_store.canonical(str(manager.get('player_name') or p.get('manager') or '')),
            'preseason_rank': pre_rank,
            'current_rank': current_rank,
            'current_points': total,
            'preseason_odds': pre_odds,
            'prior_weight': prior,
            'evidence': evidence,
        })
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # The live evidence fades in smoothly. GW2 is still mostly the pre-season
    # opinion, GW20 is roughly a 50/50 world, late spring is mostly the table.
    progress = min(1.0, max(0.0, current_event / 38.0))
    live_weight = min(0.92, 0.06 + 0.86 * (progress ** 0.72)) if current_event > 0 else 0.0
    # Log-space updates preserve the prior ordering without hard caps on PPG.
    df['market_log_weight'] = df['prior_weight'].map(lambda p: math.log(max(p, 1e-9))) + live_weight * df['evidence']
    peak = float(df['market_log_weight'].max())
    raw = (df['market_log_weight'] - peak).map(math.exp)
    total_raw = float(raw.sum()) or 1.0
    # Keep the same total implied market percentage (overround) as the frozen
    # pre-season market. This has two useful properties: at GW0 the live odds are
    # exactly the published pre-season odds, and displayed odds always remain the
    # exact inverse of the displayed implied chance.
    prior_market_sum = float(df['prior_weight'].sum()) or 1.0
    implied = raw / total_raw * prior_market_sum
    df['win_pct'] = implied * 100.0
    df['winner_odds'] = implied.map(lambda p: min(501.0, max(1.01, 1.0 / max(0.002, float(p)))))
    df['preseason_pct'] = df['preseason_odds'].map(lambda o: 100.0 / max(1.01, float(o)))
    df['odds_change'] = df['winner_odds'] - df['preseason_odds']
    df['live_weight'] = live_weight

    def note(row):
        pre_rank = int(row['preseason_rank'])
        cur_rank = int(row['current_rank'])
        if cur_rank < pre_rank:
            base = f"Bedre enn før-sesongplasseringen ({pre_rank}. → {cur_rank}.)"
        elif cur_rank > pre_rank:
            base = f"Svakere enn før-sesongplasseringen ({pre_rank}. → {cur_rank}.)"
        else:
            base = f"På nivå med før-sesongplasseringen ({pre_rank}.)"
        if row['winner_odds'] < row['preseason_odds'] - 0.05:
            return base + " · oddsen har falt"
        if row['winner_odds'] > row['preseason_odds'] + 0.05:
            return base + " · konkurrentenes utvikling trekker oddsen opp"
        return base + " · omtrent uendret odds"

    df['note'] = df.apply(note, axis=1)
    return df.sort_values(['win_pct', 'current_points'], ascending=[False, False]).reset_index(drop=True)

