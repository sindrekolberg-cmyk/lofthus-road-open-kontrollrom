from __future__ import annotations

import math
from collections import Counter
from typing import Any

import pandas as pd

from lro_fpl import FPLClient, POSITION_LABELS, current_event_id, event_ids_for_period, fixture_window, live_stats_map, player_catalog
from lro_history import HistoryStore, normalize_text


def nint(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "" or pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def nfloat(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "" or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def price_from_tenths(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value) / 10.0, 1)
    except Exception:
        return None


def chip_label(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    return {
        "3xc": "Triple Captain",
        "bboost": "Bench Boost",
        "bbost": "Bench Boost",
        "freehit": "Free Hit",
        "wildcard": "Wildcard",
    }.get(raw, str(value or "").strip())


def canonical_managers(managers: list[dict], history: HistoryStore) -> list[dict]:
    out = []
    for m in managers:
        row = dict(m)
        row["canonical_name"] = history.canonical(str(m.get("player_name") or "Ukjent manager"))
        out.append(row)
    return out


def _empty_ownership(event_id: int | None, league_size: int, errors: list | None = None) -> dict:
    return {
        "event": event_id,
        "players": pd.DataFrame(),
        "picks": pd.DataFrame(),
        "manager_events": pd.DataFrame(),
        "loaded_managers": 0,
        "league_size": league_size,
        "errors": errors or [],
    }


def build_ownership(
    client: FPLClient,
    managers: list[dict],
    history: HistoryStore,
    event_id: int | None = None,
    only_entries: list[int] | None = None,
    max_workers: int = 8,
) -> dict:
    """Builds ownership from public picks.

    Current market price always comes from bootstrap `now_cost`. Manager-specific
    purchase/selling prices stay separate and are never used as the public price.
    """
    bootstrap = client.bootstrap()
    event_id = event_id or current_event_id(bootstrap)
    if event_id is None:
        return _empty_ownership(None, len(managers), ["Fant ingen relevant FPL-runde."])
    catalog = player_catalog(bootstrap)
    live = live_stats_map(client.event_live(int(event_id)))
    manager_map = {nint(m.get("entry")): m for m in managers if nint(m.get("entry"))}
    entries = only_entries or list(manager_map)
    entries = [int(e) for e in entries if int(e) in manager_map]
    payloads, fetch_errors = client.picks_many(entries, int(event_id), max_workers=max_workers)

    pick_rows: list[dict] = []
    manager_rows: list[dict] = []
    errors: list[dict] = []
    for entry in entries:
        manager = manager_map[entry]
        payload = payloads.get(entry)
        if not payload:
            errors.append({"entry": entry, "manager": history.canonical(manager.get("player_name", "")), "error": fetch_errors.get(entry, "Ingen picks")})
            continue
        picks = payload.get("picks", []) or []
        if not picks:
            errors.append({"entry": entry, "manager": history.canonical(manager.get("player_name", "")), "error": "Ingen picks"})
            continue
        e_hist = payload.get("entry_history", {}) or {}
        active_chip = chip_label(payload.get("active_chip"))
        manager_name = history.canonical(str(manager.get("player_name") or "Ukjent manager"))
        manager_rows.append({
            "entry": entry,
            "manager": manager_name,
            "team": str(manager.get("entry_name") or "Ukjent lag"),
            "rank": nint(manager.get("rank"), 999999),
            "last_rank": nint(manager.get("last_rank"), 999999),
            "gw_points": nint(e_hist.get("points"), nint(manager.get("event_total"))),
            "total_points": nint(e_hist.get("total_points"), nint(manager.get("total"))),
            "active_chip": active_chip,
            "event_transfers": nint(e_hist.get("event_transfers")),
            "event_transfers_cost": nint(e_hist.get("event_transfers_cost")),
            "points_on_bench": nint(e_hist.get("points_on_bench")),
            "bank_tenths": nint(e_hist.get("bank")),
            "bank": round(nint(e_hist.get("bank")) / 10.0, 1),
            "team_value_tenths": nint(e_hist.get("value")),
            "team_value": round(nint(e_hist.get("value")) / 10.0, 1),
        })
        for p in picks:
            element = nint(p.get("element"))
            if not element:
                continue
            meta = catalog.get(element, {
                "element_id": element, "web_name": f"Spiller {element}", "full_name": "", "club": "",
                "team_id": 0, "position_id": 0, "position": "Ukjent", "current_price": None, "total_points": 0,
            })
            squad_pos = nint(p.get("position"))
            multiplier = nint(p.get("multiplier"))
            live_meta = live.get(element, {})
            purchase = price_from_tenths(p.get("purchase_price"))
            selling = price_from_tenths(p.get("selling_price"))
            pick_rows.append({
                "entry": entry,
                "manager": manager_name,
                "team": str(manager.get("entry_name") or "Ukjent lag"),
                "rank": nint(manager.get("rank"), 999999),
                "element": element,
                "player": meta.get("web_name"),
                "full_name": meta.get("full_name"),
                "club": meta.get("club"),
                "team_id": nint(meta.get("team_id")),
                "position_id": nint(meta.get("position_id")),
                "position": meta.get("position") or POSITION_LABELS.get(nint(meta.get("position_id")), "Ukjent"),
                "current_price": meta.get("current_price"),
                "purchase_price": purchase,
                "selling_price": selling,
                "squad_position": squad_pos,
                "multiplier": multiplier,
                "is_captain": bool(p.get("is_captain")),
                "is_vice_captain": bool(p.get("is_vice_captain")),
                "on_bench": squad_pos > 11,
                "active_chip": active_chip,
                "is_triple_captain": bool(p.get("is_captain")) and (multiplier >= 3 or active_chip == "Triple Captain"),
                "event_points": nint(live_meta.get("points")),
                "live_minutes": nint(live_meta.get("minutes")),
                "season_points": nint(meta.get("total_points")),
                "gw_contribution": nint(live_meta.get("points")) * max(multiplier, 0),
            })

    picks_df = pd.DataFrame(pick_rows)
    manager_events = pd.DataFrame(manager_rows)
    if picks_df.empty:
        return {**_empty_ownership(event_id, len(entries), errors), "manager_events": manager_events}

    loaded = int(picks_df["entry"].nunique())
    player_rows = []
    for element, block in picks_df.groupby("element", sort=False):
        first = block.iloc[0]
        captains = block[block["is_captain"]]
        triples = block[block["is_triple_captain"]]
        owners = sorted(block["manager"].astype(str).unique().tolist(), key=normalize_text)
        captain_names = sorted(captains["manager"].astype(str).unique().tolist(), key=normalize_text)
        tc_names = sorted(triples["manager"].astype(str).unique().tolist(), key=normalize_text)
        benched = sorted(block[block["on_bench"]]["manager"].astype(str).unique().tolist(), key=normalize_text)
        owner_count = int(block["entry"].nunique())
        captain_count = int(captains["entry"].nunique())
        tc_count = int(triples["entry"].nunique())
        eo_count = int(block["multiplier"].clip(lower=0).sum())
        player_rows.append({
            "element": int(element),
            "player": str(first.get("player") or ""),
            "full_name": str(first.get("full_name") or ""),
            "club": str(first.get("club") or ""),
            "team_id": nint(first.get("team_id")),
            "position_id": nint(first.get("position_id")),
            "position": str(first.get("position") or ""),
            "current_price": first.get("current_price"),
            "ownership_count": owner_count,
            "ownership_pct": round(owner_count / loaded * 100, 1) if loaded else 0.0,
            "captain_count": captain_count,
            "captain_pct": round(captain_count / loaded * 100, 1) if loaded else 0.0,
            "triple_captain_count": tc_count,
            "bench_count": len(benched),
            "vice_count": int(block[block["is_vice_captain"]]["entry"].nunique()),
            "effective_ownership_count": eo_count,
            "effective_ownership_pct": round(eo_count / loaded * 100, 1) if loaded else 0.0,
            "event_points": nint(first.get("event_points")),
            "live_minutes": nint(first.get("live_minutes")),
            "season_points": nint(first.get("season_points")),
            "owners": owners,
            "captains": captain_names,
            "triple_captains": tc_names,
            "benched_by": benched,
        })
    players_df = pd.DataFrame(player_rows).sort_values(
        ["ownership_count", "captain_count", "season_points", "player"], ascending=[False, False, False, True]
    ).reset_index(drop=True)
    return {
        "event": int(event_id),
        "players": players_df,
        "picks": picks_df,
        "manager_events": manager_events,
        "loaded_managers": loaded,
        "league_size": len(entries),
        "errors": errors,
    }


def manager_squad(ownership: dict, entry: int) -> pd.DataFrame:
    picks = ownership.get("picks", pd.DataFrame())
    if picks is None or picks.empty:
        return pd.DataFrame()
    out = picks[picks["entry"] == int(entry)].copy()
    if out.empty:
        return out
    return out.sort_values(["on_bench", "squad_position"]).reset_index(drop=True)


def player_lookup(ownership: dict, element: int) -> dict | None:
    players = ownership.get("players", pd.DataFrame())
    if players is None or players.empty:
        return None
    block = players[players["element"] == int(element)]
    return block.iloc[0].to_dict() if not block.empty else None


def manager_form_from_histories(
    managers: list[dict],
    histories: dict[int, dict],
    target_entry: int,
    last_n: int = 5,
) -> pd.DataFrame:
    """Reconstruct LRO round rank and LRO table rank from all available entry histories."""
    manager_names = {nint(m.get("entry")): str(m.get("player_name") or "") for m in managers}
    rows = []
    for entry, history in histories.items():
        for r in history.get("current", []) or []:
            event = nint(r.get("event"))
            if not event:
                continue
            rows.append({
                "entry": int(entry),
                "manager": manager_names.get(int(entry), str(entry)),
                "event": event,
                "points": nint(r.get("points")),
                "total_points": nint(r.get("total_points")),
                "overall_rank": nint(r.get("overall_rank"), 0),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()
    out_rows = []
    for event, block in df.groupby("event"):
        block = block.copy()
        block["round_rank"] = block["points"].rank(method="min", ascending=False).astype(int)
        block["league_rank"] = block["total_points"].rank(method="min", ascending=False).astype(int)
        out_rows.extend(block.to_dict("records"))
    out = pd.DataFrame(out_rows)
    out = out[out["entry"] == int(target_entry)].sort_values("event").tail(last_n).reset_index(drop=True)
    return out


def round_movements(managers: list[dict], history: HistoryStore | None = None) -> dict:
    rows = []
    for m in managers:
        rank = nint(m.get("rank"), 999999)
        last = nint(m.get("last_rank"), rank)
        if rank >= 999999:
            continue
        move = last - rank
        rows.append({
            "entry": nint(m.get("entry")),
            "manager": history.canonical(m.get("player_name", "")) if history else str(m.get("player_name") or ""),
            "team": str(m.get("entry_name") or ""),
            "rank": rank,
            "last_rank": last,
            "move": move,
            "gw": nint(m.get("event_total")),
            "total": nint(m.get("total")),
        })
    if not rows:
        return {}
    best = max(rows, key=lambda x: (x["move"], x["gw"]))
    worst = min(rows, key=lambda x: (x["move"], -x["gw"]))
    gw_winner = max(rows, key=lambda x: (x["gw"], -x["rank"]))
    leader = min(rows, key=lambda x: x["rank"])
    return {"best_climber": best, "biggest_fall": worst, "gw_winner": gw_winner, "leader": leader, "rows": rows}


def fixture_outlook(player: dict, fixtures: list[dict]) -> dict:
    """Explainable, position-aware outlook for a player over a fixture window.

    This is deliberately a decision-support model, not an xPts oracle. It blends
    current FPL output, minutes, xGI and fixture difficulty into a stable score.
    """
    if not fixtures:
        return {"score": 0.0, "expected_low": 0, "expected_high": 0, "avg_fdr": None, "label": "Ingen programdata", "fixtures": []}
    form = nfloat(player.get("form"))
    ppg = nfloat(player.get("points_per_game"))
    minutes = nfloat(player.get("minutes"))
    starts = nfloat(player.get("starts"))
    xgi90 = nfloat(player.get("xgi_per90"))
    cs = nfloat(player.get("clean_sheets"))
    saves = nfloat(player.get("saves"))
    pos = nint(player.get("position_id"))
    avg_fdr = sum(max(1, min(5, nint(f.get("difficulty"), 3))) for f in fixtures) / len(fixtures)
    fixture_factor = max(0.72, min(1.28, 1.18 - 0.09 * (avg_fdr - 2.0)))
    # Estimate availability and likely minutes without pretending to know lineups.
    status = str(player.get("status") or "a")
    chance = player.get("chance_next")
    availability = 1.0
    if status != "a":
        availability = (nfloat(chance, 50.0) / 100.0) if chance is not None else 0.55
    start_rate = min(1.0, starts / max(1.0, starts + max(0.0, (minutes / 30.0) - starts))) if minutes > 0 else 0.0
    minute_factor = max(0.35, min(1.0, (minutes / max(1.0, starts * 90.0)) if starts > 0 else start_rate)) if minutes > 0 else 0.35

    base = 0.52 * ppg + 0.33 * form
    if pos in (3, 4):
        base += 2.6 * xgi90
    elif pos == 2:
        base += 1.5 * xgi90 + 0.035 * cs
    elif pos == 1:
        base += 0.045 * cs + 0.008 * saves
    expected_per_game = max(0.5, base * fixture_factor * availability * max(0.65, minute_factor))
    expected_total = expected_per_game * len(fixtures)
    # A wide range is more honest than a fake decimal projection.
    low = max(0, int(math.floor(expected_total * 0.68)))
    high = max(low + 1, int(math.ceil(expected_total * 1.34 + 1)))
    score = max(0.0, min(100.0, 12.0 * expected_per_game + 14.0 * availability + 8.0 * minute_factor))
    if avg_fdr <= 2.35:
        label = "Sterkt program"
    elif avg_fdr <= 3.05:
        label = "Greit program"
    else:
        label = "Tøffere program"
    return {
        "score": round(score, 1),
        "expected_low": low,
        "expected_high": high,
        "expected_total": round(expected_total, 1),
        "avg_fdr": round(avg_fdr, 2),
        "label": label,
        "availability": round(availability, 2),
        "fixtures": fixtures,
    }


def build_player_outlooks(client: FPLClient, period: str) -> tuple[pd.DataFrame, list[int]]:
    bootstrap = client.bootstrap()
    catalog = player_catalog(bootstrap)
    phase = None
    event_ids = event_ids_for_period(bootstrap, period, phase)
    all_fixtures = client.fixtures(None)
    rows = []
    for pid, p in catalog.items():
        window = fixture_window(all_fixtures, nint(p.get("team_id")), event_ids)
        outlook = fixture_outlook(p, window)
        rows.append({**p, **{f"outlook_{k}": v for k, v in outlook.items() if k != "fixtures"}, "fixture_window": window})
    return pd.DataFrame(rows), event_ids


def fixture_labels_for_player(player_row: dict, bootstrap: dict, fixtures: list[dict]) -> list[str]:
    teams = {nint(t.get("id")): str(t.get("short_name") or t.get("name") or "?") for t in bootstrap.get("teams", []) or []}
    labels = []
    for f in fixtures:
        opp = teams.get(nint(f.get("opponent_id")), "?")
        labels.append(f"{opp} {'H' if f.get('home') else 'B'}")
    return labels


def _relevance_filter(df: pd.DataFrame, current_event: int) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    # Early season has little sample. Later, minutes/start thresholds can be stronger.
    min_minutes = 1 if current_event <= 2 else 90 if current_event <= 5 else 180
    status_ok = work["status"].isin(["a", "d"])
    relevant = status_ok & (
        (pd.to_numeric(work["minutes"], errors="coerce").fillna(0) >= min_minutes)
        | (pd.to_numeric(work["total_points"], errors="coerce").fillna(0) >= 8)
        | (pd.to_numeric(work["transfers_in_event"], errors="coerce").fillna(0) >= 15000)
    )
    return work[relevant].copy()


def rival_analysis(
    client: FPLClient,
    managers: list[dict],
    history: HistoryStore,
    me_entry: int,
    rival_entries: list[int],
    period: str,
    risk: str,
    goal: str,
    selected_ownership: dict | None = None,
) -> dict:
    bootstrap = client.bootstrap()
    event = current_event_id(bootstrap) or 1
    selected_entries = [int(me_entry)] + [int(x) for x in rival_entries if int(x) != int(me_entry)]
    ownership = selected_ownership or build_ownership(client, managers, history, event, only_entries=selected_entries, max_workers=6)
    picks = ownership.get("picks", pd.DataFrame())
    events = ownership.get("manager_events", pd.DataFrame())
    if picks.empty:
        return {"ownership": ownership, "error": "Lagene kunne ikke lastes."}
    me = set(picks[picks["entry"] == int(me_entry)]["element"].astype(int).tolist())
    rivals = picks[picks["entry"].isin([int(x) for x in rival_entries])]
    rival_sets = {int(e): set(b["element"].astype(int).tolist()) for e, b in rivals.groupby("entry")}
    rival_counts = Counter()
    for s in rival_sets.values():
        rival_counts.update(s)
    rival_n = max(1, len(rival_sets))

    # Context matters: defending a lead and chasing a deficit are different games.
    me_event = events[events["entry"] == int(me_entry)]
    rival_event_rows = events[events["entry"].isin([int(x) for x in rival_entries])]
    my_total = nfloat(me_event.iloc[0].get("total_points")) if not me_event.empty else 0.0
    rival_totals = pd.to_numeric(rival_event_rows.get("total_points", pd.Series(dtype=float)), errors="coerce").dropna().tolist()
    best_rival_total = max(rival_totals) if rival_totals else my_total
    worst_rival_total = min(rival_totals) if rival_totals else my_total
    gap_to_best = my_total - best_rival_total
    event_now = current_event_id(bootstrap) or 1
    threshold = 28 if event_now <= 5 else 20 if event_now <= 20 else 12
    if gap_to_best >= threshold:
        strategy_context = "defend"
        strategy_text = f"Du ligger minst {int(round(gap_to_best))} poeng foran den sterkeste valgte rivalen. Dekning kan være mer verdt enn unødvendig gambling."
    elif gap_to_best <= -threshold:
        strategy_context = "chase"
        strategy_text = f"Du ligger {int(round(abs(gap_to_best)))} poeng bak den sterkeste valgte rivalen. Gode forskjeller kan være mer verdifulle enn ren dekning."
    else:
        strategy_context = "neutral"
        strategy_text = "Det er tett nok til at forventet poengverdi bør veie tyngst. Forskjeller er bonus, ikke mål i seg selv."

    player_df, event_ids = build_player_outlooks(client, period)
    player_df["rival_count"] = player_df["element_id"].map(lambda x: int(rival_counts.get(int(x), 0)))
    player_df["rival_pct"] = player_df["rival_count"].map(lambda x: 100 * x / rival_n)
    player_df["i_own"] = player_df["element_id"].isin(me)
    player_df = _relevance_filter(player_df, event)

    they_have_i_lack = player_df[(~player_df["i_own"]) & (player_df["rival_count"] > 0)].copy()
    they_have_i_lack["danger_score"] = (
        pd.to_numeric(they_have_i_lack["outlook_score"], errors="coerce").fillna(0)
        * (0.65 + 0.35 * they_have_i_lack["rival_count"] / rival_n)
    )
    they_have_i_lack = they_have_i_lack.sort_values(["danger_score", "rival_count"], ascending=[False, False])

    i_have_they_lack = player_df[player_df["i_own"] & (player_df["rival_count"] < rival_n)].copy()
    i_have_they_lack["edge_score"] = pd.to_numeric(i_have_they_lack["outlook_score"], errors="coerce").fillna(0) * (1 - i_have_they_lack["rival_count"] / rival_n)
    i_have_they_lack = i_have_they_lack.sort_values("edge_score", ascending=False)

    nobody = player_df[(~player_df["i_own"]) & (player_df["rival_count"] == 0)].copy()
    nobody["opportunity_score"] = pd.to_numeric(nobody["outlook_score"], errors="coerce").fillna(0)
    nobody = nobody.sort_values(["opportunity_score", "total_points"], ascending=[False, False])

    common = player_df[player_df["i_own"] & (player_df["rival_count"] == rival_n)].copy().sort_values("total_points", ascending=False)

    my_bank = nfloat(me_event.iloc[0].get("bank")) if not me_event.empty else 0.0
    my_squad = picks[picks["entry"] == int(me_entry)].copy()
    suggestions = transfer_suggestions(
        player_df=player_df,
        my_squad=my_squad,
        rival_counts=rival_counts,
        rival_n=rival_n,
        bank=my_bank,
        risk=risk,
        goal=goal,
        strategy_context=strategy_context,
    )
    captains = captain_recommendations(player_df, my_squad, rival_counts, rival_n, risk, strategy_context=strategy_context)
    return {
        "ownership": ownership,
        "player_df": player_df,
        "event_ids": event_ids,
        "they_have_i_lack": they_have_i_lack,
        "i_have_they_lack": i_have_they_lack,
        "nobody_has": nobody,
        "common": common,
        "suggestions": suggestions,
        "captains": captains,
        "my_bank": my_bank,
        "rival_n": rival_n,
        "strategy_context": strategy_context,
        "strategy_text": strategy_text,
        "gap_to_best": round(gap_to_best, 1),
        "error": "",
    }


def _candidate_strategy_bonus(rival_count: int, rival_n: int, risk: str) -> float:
    ratio = rival_count / max(1, rival_n)
    r = (risk or "Balansert").casefold()
    if "trygt" in r:
        return 13.0 * ratio
    if "aggress" in r:
        return 17.0 * (1.0 - ratio)
    return 6.0 * (0.5 + abs(0.5 - ratio) * 0.2)


def transfer_suggestions(
    player_df: pd.DataFrame,
    my_squad: pd.DataFrame,
    rival_counts: Counter,
    rival_n: int,
    bank: float,
    risk: str,
    goal: str,
    strategy_context: str = "neutral",
) -> pd.DataFrame:
    if player_df.empty or my_squad.empty:
        return pd.DataFrame()
    my_ids = set(my_squad["element"].astype(int).tolist())
    club_counts = Counter(my_squad["team_id"].astype(int).tolist())
    rows = []
    by_id = player_df.set_index("element_id", drop=False)
    for out_pick in my_squad.to_dict("records"):
        out_id = int(out_pick["element"])
        if out_id not in by_id.index:
            continue
        out_p = by_id.loc[out_id].to_dict()
        out_value = nfloat(out_p.get("outlook_score"))
        selling = out_pick.get("selling_price")
        exact_selling = selling is not None and not pd.isna(selling)
        sell_price = nfloat(selling, nfloat(out_pick.get("current_price")))
        budget = round(bank + sell_price, 1)
        pos = nint(out_pick.get("position_id"))
        for cand in player_df[player_df["position_id"] == pos].to_dict("records"):
            in_id = nint(cand.get("element_id"))
            if not in_id or in_id in my_ids:
                continue
            price = nfloat(cand.get("current_price"), 999.0)
            if price > budget + 1e-9:
                continue
            team_id = nint(cand.get("team_id"))
            post_club = club_counts.copy()
            post_club[nint(out_pick.get("team_id"))] -= 1
            post_club[team_id] += 1
            if post_club[team_id] > 3:
                continue
            rcount = int(rival_counts.get(in_id, 0))
            base_gain = nfloat(cand.get("outlook_score")) - out_value
            strategy = _candidate_strategy_bonus(rcount, rival_n, risk)
            if strategy_context == "defend":
                strategy += 7.0 * (rcount / max(1, rival_n))
            elif strategy_context == "chase":
                strategy += 9.0 * (1.0 - rcount / max(1, rival_n))
            status_penalty = 0.0 if str(cand.get("status")) == "a" else 18.0
            transfer_score = base_gain + strategy - status_penalty
            # Do not recommend a weak novelty just because nobody owns him.
            if nfloat(cand.get("outlook_score")) < max(28.0, out_value - 5.0):
                transfer_score -= 18.0
            reasons = []
            if rcount == 0:
                reasons.append(f"Ingen av {rival_n} rivaler eier ham")
            elif rcount == rival_n:
                reasons.append("Alle rivalene dine eier ham")
            else:
                reasons.append(f"{rcount} av {rival_n} rivaler eier ham")
            reasons.append(str(cand.get("outlook_label") or "Program vurdert"))
            reasons.append(f"Forventet område {nint(cand.get('outlook_expected_low'))}–{nint(cand.get('outlook_expected_high'))} p i perioden")
            if price < sell_price:
                reasons.append(f"Frigjør £{sell_price - price:.1f}")
            rows.append({
                "out_element": out_id,
                "out_player": str(out_pick.get("player") or ""),
                "out_price": nfloat(out_pick.get("current_price")),
                "selling_price": sell_price,
                "selling_price_exact": exact_selling,
                "in_element": in_id,
                "in_player": str(cand.get("web_name") or ""),
                "club": str(cand.get("club") or ""),
                "position": str(cand.get("position") or ""),
                "in_price": price,
                "budget": budget,
                "budget_after": round(budget - price, 1),
                "rival_count": rcount,
                "rival_n": rival_n,
                "outlook_score": nfloat(cand.get("outlook_score")),
                "outlook_label": str(cand.get("outlook_label") or ""),
                "expected_low": nint(cand.get("outlook_expected_low")),
                "expected_high": nint(cand.get("outlook_expected_high")),
                "score": round(transfer_score, 2),
                "reasons": reasons[:4],
                "fixture_window": cand.get("fixture_window") or [],
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values(["score", "outlook_score"], ascending=[False, False])
    # Avoid showing six variants of the same incoming player.
    df = df.drop_duplicates(subset=["in_element"], keep="first").head(8).reset_index(drop=True)
    return df


def captain_recommendations(
    player_df: pd.DataFrame,
    my_squad: pd.DataFrame,
    rival_counts: Counter,
    rival_n: int,
    risk: str,
    strategy_context: str = "neutral",
) -> pd.DataFrame:
    if player_df.empty or my_squad.empty:
        return pd.DataFrame()
    my_ids = set(my_squad[~my_squad["on_bench"]]["element"].astype(int).tolist())
    pool = player_df[player_df["element_id"].isin(my_ids)].copy()
    if pool.empty:
        return pool
    pool["rival_count"] = pool["element_id"].map(lambda x: int(rival_counts.get(int(x), 0)))
    pool["captain_score"] = pd.to_numeric(pool["outlook_score"], errors="coerce").fillna(0)
    r = (risk or "Balansert").casefold()
    if "trygt" in r:
        pool["captain_score"] += 9.0 * pool["rival_count"] / max(1, rival_n)
    elif "aggress" in r:
        pool["captain_score"] += 10.0 * (1.0 - pool["rival_count"] / max(1, rival_n))
    if strategy_context == "defend":
        pool["captain_score"] += 5.0 * pool["rival_count"] / max(1, rival_n)
    elif strategy_context == "chase":
        pool["captain_score"] += 6.0 * (1.0 - pool["rival_count"] / max(1, rival_n))
    return pool.sort_values("captain_score", ascending=False).head(3).reset_index(drop=True)


def stories(managers: list[dict], ownership: dict | None, history: HistoryStore) -> list[str]:
    move = round_movements(managers, history)
    out: list[str] = []
    if ownership and not ownership.get("picks", pd.DataFrame()).empty:
        picks = ownership["picks"]
        tc = picks[picks["is_triple_captain"]]
        for row in tc.head(2).to_dict("records"):
            out.append(f"{row['manager']} brukte Triple Captain på {row['player']}.")
    if move.get("best_climber") and move["best_climber"]["move"] >= 8:
        r = move["best_climber"]
        out.append(f"{r['manager']} klatret {r['move']} plasser.")
    if move.get("biggest_fall") and move["biggest_fall"]["move"] <= -8:
        r = move["biggest_fall"]
        out.append(f"{r['manager']} falt {abs(r['move'])} plasser.")
    if ownership and not ownership.get("players", pd.DataFrame()).empty:
        top = ownership["players"].sort_values("ownership_count", ascending=False).iloc[0]
        without = max(0, int(ownership.get("loaded_managers", 0)) - nint(top.get("ownership_count")))
        if ownership.get("loaded_managers", 0):
            out.append(f"Bare {without} av {ownership['loaded_managers']} går uten {top['player']}.")
    if move.get("leader"):
        out.append(f"{move['leader']['manager']} leder ligaen.")
    unique = []
    for text in out:
        if text not in unique:
            unique.append(text)
    return unique[:4]
