from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any

from api.deep_analysis import DeepFPLProjectionProvider, _future_projection_bootstrap
from api.engine import get_engine
from lro_analysis import manager_squad, nfloat, nint
from lro_fpl import fixture_window, player_catalog
from lro_transfer_strategy import clamp, horizon_event_ids, select_cohort

POSITION_REQUIREMENTS = {1: 2, 2: 5, 3: 5, 4: 3}
POSITION_ORDERINGS = [
    [3, 4, 2, 1],
    [4, 3, 2, 1],
    [2, 3, 4, 1],
    [1, 3, 4, 2],
]


def _ownership_maps(state: Any, cohort_entries: list[int]) -> tuple[dict[int, int], dict[int, int]]:
    picks = (state.ownership or {}).get("picks")
    if picks is None or getattr(picks, "empty", True):
        return {}, {}
    league: dict[int, int] = {}
    cohort: dict[int, int] = {}
    cohort_set = {int(entry) for entry in cohort_entries}
    for element, block in picks.groupby("element"):
        league[int(element)] = int(block["entry"].nunique())
        if cohort_set:
            cohort[int(element)] = int(block[block["entry"].isin(cohort_set)]["entry"].nunique())
    return league, cohort


def _available_budget(state: Any, entry_id: int) -> tuple[float, bool, list[dict[str, Any]]]:
    manager = state.manager(int(entry_id))
    squad_df = manager_squad(state.ownership, int(entry_id))
    squad = [] if squad_df is None or getattr(squad_df, "empty", True) else list(squad_df.to_dict("records"))
    bank = nfloat(getattr(manager, "bank", 0.0)) if manager else 0.0
    exact = bool(squad)
    sell_total = 0.0
    for row in squad:
        selling = row.get("selling_price")
        if selling in (None, ""):
            exact = False
            selling = row.get("current_price")
        sell_total += nfloat(selling)
    if squad:
        return round(sell_total + bank, 1), exact, squad
    fallback = nfloat(getattr(manager, "team_value", 0.0)) + bank if manager else 100.0
    return round(fallback or 100.0, 1), False, squad


def _strategy_bonus(
    *,
    strategy: str,
    risk: int,
    league_pct: float,
    cohort_pct: float,
    global_pct: float,
    manager: Any,
    state: Any,
) -> float:
    risk_t = clamp((int(risk) - 50) / 50.0, -1.0, 1.0)
    rare_in_target = 1.0 - clamp(cohort_pct / 100.0, 0.0, 1.0)
    target_cover = clamp(cohort_pct / 100.0, 0.0, 1.0)
    global_cover = clamp(global_pct / 100.0, 0.0, 1.0)

    if strategy == "rapid_lofthus":
        return (1.15 + 0.55 * max(risk_t, 0.0)) * rare_in_target + 0.20 * (1.0 - global_cover)
    if strategy == "defend":
        return 1.15 * target_cover + 0.25 * global_cover
    if strategy == "climb_or":
        return 0.08 * (1.0 - league_pct / 100.0)
    if strategy == "win_month":
        return 0.95 * rare_in_target + 0.15 * target_cover
    if strategy == "win_lofthus":
        ranked = state.managers_by_rank()
        leader = ranked[0] if ranked else None
        gap = max(0, nint(getattr(leader, "live_total_points", 0)) - nint(getattr(manager, "live_total_points", 0))) if manager and leader else 0
        chase = clamp(0.25 + gap / 70.0 + max(risk_t, 0.0) * 0.25, 0.0, 1.0)
        return chase * 1.05 * rare_in_target + (1.0 - chase) * 0.70 * target_cover
    return 0.45 * rare_in_target + 0.20 * target_cover


def _candidate_rows(
    *,
    bootstrap: dict[str, Any],
    fixtures: list[dict[str, Any]],
    state: Any,
    entry_id: int,
    strategy: str,
    risk: int,
    horizon: int,
) -> tuple[list[dict[str, Any]], DeepFPLProjectionProvider, list[int], str]:
    projection_bootstrap, _first_event = _future_projection_bootstrap(bootstrap)
    event_ids = horizon_event_ids(projection_bootstrap, max(5, int(horizon or 5)))
    catalog = player_catalog(bootstrap)
    provider = DeepFPLProjectionProvider(bootstrap)
    cohort_entries, cohort_label = select_cohort(state, int(entry_id), strategy)
    if not cohort_entries:
        cohort_entries = [m.entry for m in state.managers_by_rank() if m.entry != int(entry_id)][:20]
        cohort_label = "Nærmeste ligafelt"
    league_owners, cohort_owners = _ownership_maps(state, cohort_entries)
    league_size = max(1, int(state.league_size or 1))
    cohort_size = max(1, len(cohort_entries))
    manager = state.manager(int(entry_id))

    rows: list[dict[str, Any]] = []
    for element, player in catalog.items():
        status = str(player.get("status") or "a")
        chance = player.get("chance_next")
        if status in {"u", "s"}:
            continue
        if chance is not None and nint(chance) < 25:
            continue
        price = nfloat(player.get("current_price"))
        if price <= 0:
            continue
        team_id = nint(player.get("team_id"))
        position_id = nint(player.get("position_id"))
        if position_id not in POSITION_REQUIREMENTS:
            continue
        fx = fixture_window(fixtures, team_id, event_ids)
        projection = provider.score(player, fx, max(5, int(horizon or 5)))
        league_count = int(league_owners.get(element, 0))
        cohort_count = int(cohort_owners.get(element, 0))
        league_pct = 100.0 * league_count / league_size
        cohort_pct = 100.0 * cohort_count / cohort_size
        global_pct = nfloat(player.get("selected_by_pct"))
        leverage = _strategy_bonus(
            strategy=strategy,
            risk=risk,
            league_pct=league_pct,
            cohort_pct=cohort_pct,
            global_pct=global_pct,
            manager=manager,
            state=state,
        )
        availability_penalty = 0.0
        if status != "a":
            availability_penalty += 0.8
        if chance is not None and nint(chance) < 75:
            availability_penalty += (75 - nint(chance)) / 75.0
        base_score = nfloat(projection.get("index_10"))
        squad_score = base_score + leverage - availability_penalty
        captain_score = base_score + 0.20 * nfloat(player.get("form")) + 0.35 * clamp(nfloat(player.get("xgi_per90")) / 0.8, 0.0, 1.0)
        detail = provider.details.get(element) or {}
        rows.append(
            {
                "element": element,
                "player": str(player.get("web_name") or ""),
                "club": str(player.get("club") or ""),
                "team_id": team_id,
                "position_id": position_id,
                "position": str(player.get("position") or ""),
                "price": round(price, 1),
                "projection_index": round(base_score, 2),
                "squad_score": round(squad_score, 3),
                "captain_score": round(captain_score, 3),
                "league_ownership_pct": round(league_pct, 1),
                "cohort_ownership_pct": round(cohort_pct, 1),
                "global_ownership_pct": round(global_pct, 1),
                "form": round(nfloat(player.get("form")), 1),
                "points_per_game": round(nfloat(player.get("points_per_game")), 1),
                "xgi_per90": round(nfloat(player.get("xgi_per90")), 3),
                "minutes": nint(player.get("minutes")),
                "starts": nint(player.get("starts")),
                "status": status,
                "chance_next": chance,
                "confidence": detail.get("confidence", "lav"),
                "evidence": list(detail.get("evidence") or [])[:6],
                "deep_stats": dict(detail.get("stats") or {}),
            }
        )
    return rows, provider, event_ids, cohort_label


def _minimum_remaining_cost(candidates_by_pos: dict[int, list[dict[str, Any]]], remaining: Counter[int], selected: set[int]) -> float:
    total = 0.0
    for position, count in remaining.items():
        if count <= 0:
            continue
        prices = sorted(
            nfloat(row.get("price"))
            for row in candidates_by_pos.get(position, [])
            if nint(row.get("element")) not in selected
        )
        if len(prices) < count:
            return 10**9
        total += sum(prices[:count])
    return total


def _build_one(
    candidates_by_pos: dict[int, list[dict[str, Any]]],
    budget: float,
    position_order: list[int],
    price_penalty: float,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    clubs: Counter[int] = Counter()
    remaining: Counter[int] = Counter(POSITION_REQUIREMENTS)
    cost = 0.0

    slots: list[int] = []
    for position in position_order:
        slots.extend([position] * POSITION_REQUIREMENTS[position])

    for position in slots:
        remaining[position] -= 1
        choices = sorted(
            candidates_by_pos.get(position, []),
            key=lambda row: (
                -(nfloat(row.get("squad_score")) - price_penalty * nfloat(row.get("price"))),
                -nfloat(row.get("squad_score")),
                nfloat(row.get("price")),
                str(row.get("player") or ""),
            ),
        )
        chosen = None
        for row in choices:
            element = nint(row.get("element"))
            team = nint(row.get("team_id"))
            if element in selected_ids or clubs[team] >= 3:
                continue
            trial_selected = set(selected_ids)
            trial_selected.add(element)
            minimum_rest = _minimum_remaining_cost(candidates_by_pos, remaining, trial_selected)
            if cost + nfloat(row.get("price")) + minimum_rest > budget + 1e-9:
                continue
            chosen = row
            break
        if chosen is None:
            return []
        selected.append(chosen)
        selected_ids.add(nint(chosen.get("element")))
        clubs[nint(chosen.get("team_id"))] += 1
        cost += nfloat(chosen.get("price"))
    return selected


def _best_xi(squad: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    keepers = [row for row in squad if nint(row.get("position_id")) == 1]
    outfield = [row for row in squad if nint(row.get("position_id")) != 1]
    best: list[dict[str, Any]] = []
    best_score = -10**9
    for keeper in keepers:
        for combo in combinations(outfield, 10):
            counts = Counter(nint(row.get("position_id")) for row in combo)
            if counts[2] < 3 or counts[2] > 5 or counts[3] < 2 or counts[3] > 5 or counts[4] < 1 or counts[4] > 3:
                continue
            score = nfloat(keeper.get("squad_score")) + sum(nfloat(row.get("squad_score")) for row in combo)
            if score > best_score:
                best_score = score
                best = [keeper, *combo]
    xi_ids = {nint(row.get("element")) for row in best}
    bench = [row for row in squad if nint(row.get("element")) not in xi_ids]
    bench.sort(key=lambda row: (nint(row.get("position_id")) == 1, -nfloat(row.get("squad_score"))))
    return best, bench


def _objective(squad: list[dict[str, Any]]) -> float:
    xi, bench = _best_xi(squad)
    if len(xi) != 11:
        return -10**9
    captain = max((nfloat(row.get("captain_score")) for row in xi), default=0.0)
    xi_score = sum(nfloat(row.get("squad_score")) for row in xi)
    bench_score = sum(nfloat(row.get("squad_score")) for row in bench)
    return xi_score + 0.25 * bench_score + 0.80 * captain


def _improve_squad(squad: list[dict[str, Any]], all_rows: list[dict[str, Any]], budget: float) -> list[dict[str, Any]]:
    current = list(squad)
    current_obj = _objective(current)
    for _ in range(5):
        selected_ids = {nint(row.get("element")) for row in current}
        current_cost = sum(nfloat(row.get("price")) for row in current)
        clubs = Counter(nint(row.get("team_id")) for row in current)
        best_swap = None
        best_obj = current_obj
        for idx, outgoing in enumerate(current):
            position = nint(outgoing.get("position_id"))
            for incoming in all_rows:
                if nint(incoming.get("position_id")) != position or nint(incoming.get("element")) in selected_ids:
                    continue
                out_team = nint(outgoing.get("team_id"))
                in_team = nint(incoming.get("team_id"))
                post_in_count = clubs[in_team] + 1 - (1 if in_team == out_team else 0)
                if post_in_count > 3:
                    continue
                new_cost = current_cost - nfloat(outgoing.get("price")) + nfloat(incoming.get("price"))
                if new_cost > budget + 1e-9:
                    continue
                trial = list(current)
                trial[idx] = incoming
                obj = _objective(trial)
                if obj > best_obj + 1e-6:
                    best_obj = obj
                    best_swap = trial
        if best_swap is None:
            break
        current = best_swap
        current_obj = best_obj
    return current


def _annotate(row: dict[str, Any], current_ids: set[int], xi_ids: set[int], captain_id: int, vice_id: int) -> dict[str, Any]:
    item = dict(row)
    evidence = list(item.get("evidence") or [])
    evidence.append(f"Lofthus-eierskap {nfloat(item.get('league_ownership_pct')):.0f} % · globalt {nfloat(item.get('global_ownership_pct')):.0f} %")
    item["evidence"] = evidence[:7]
    item["currently_owned"] = nint(item.get("element")) in current_ids
    item["starting_xi"] = nint(item.get("element")) in xi_ids
    item["captain"] = nint(item.get("element")) == captain_id
    item["vice_captain"] = nint(item.get("element")) == vice_id
    return item


def build_wildcard_analysis(
    *,
    entry_id: int,
    strategy: str,
    risk: int,
    horizon: int = 5,
) -> dict[str, Any]:
    eng = get_engine()
    snap = eng.snapshot()
    if not snap.state:
        return {"ok": False, "error": "Live-data er ikke klare ennå."}
    state = snap.state
    manager = state.manager(int(entry_id))
    if not manager:
        return {"ok": False, "error": "Manageren finnes ikke i ligaen."}
    try:
        fixtures = list(eng.client.fixtures() or [])
    except Exception:
        fixtures = list(state.fixtures or [])

    budget, exact_budget, current_squad = _available_budget(state, int(entry_id))
    rows, _provider, event_ids, cohort_label = _candidate_rows(
        bootstrap=snap.bootstrap,
        fixtures=fixtures,
        state=state,
        entry_id=int(entry_id),
        strategy=strategy,
        risk=int(risk),
        horizon=max(5, int(horizon or 5)),
    )
    candidates_by_pos = {
        position: sorted(
            [row for row in rows if nint(row.get("position_id")) == position],
            key=lambda row: (-nfloat(row.get("squad_score")), nfloat(row.get("price"))),
        )
        for position in POSITION_REQUIREMENTS
    }

    squads: list[list[dict[str, Any]]] = []
    for order in POSITION_ORDERINGS:
        for price_penalty in (0.00, 0.05, 0.10, 0.16, 0.22, 0.30, 0.40):
            built = _build_one(candidates_by_pos, budget, order, price_penalty)
            if built:
                squads.append(_improve_squad(built, rows, budget))
    if not squads:
        return {"ok": False, "error": "Fant ingen gyldig wildcard-tropp innenfor budsjettet."}

    squad = max(squads, key=_objective)
    squad_cost = round(sum(nfloat(row.get("price")) for row in squad), 1)
    xi, bench = _best_xi(squad)
    xi.sort(key=lambda row: (nint(row.get("position_id")), -nfloat(row.get("squad_score"))))
    captain_order = sorted(xi, key=lambda row: (-nfloat(row.get("captain_score")), -nfloat(row.get("squad_score"))))
    captain_id = nint(captain_order[0].get("element")) if captain_order else 0
    vice_id = nint(captain_order[1].get("element")) if len(captain_order) > 1 else 0
    xi_ids = {nint(row.get("element")) for row in xi}
    current_ids = {nint(row.get("element")) for row in current_squad}
    squad_ids = {nint(row.get("element")) for row in squad}

    incoming = [_annotate(row, current_ids, xi_ids, captain_id, vice_id) for row in squad if nint(row.get("element")) not in current_ids]
    outgoing = [
        {
            "element": nint(row.get("element")),
            "player": str(row.get("player") or ""),
            "position": str(row.get("position") or ""),
            "selling_price": row.get("selling_price"),
        }
        for row in current_squad
        if nint(row.get("element")) not in squad_ids
    ]

    return {
        "ok": True,
        "manager": {"entry": manager.entry, "manager": manager.manager, "team": manager.team, "rank": manager.live_rank},
        "strategy": {"id": strategy, "risk": int(risk), "horizon": max(5, int(horizon or 5)), "cohort": cohort_label},
        "budget": {"available": budget, "used": squad_cost, "remaining": round(budget - squad_cost, 1), "exact": exact_budget},
        "starting_xi": [_annotate(row, current_ids, xi_ids, captain_id, vice_id) for row in xi],
        "bench": [_annotate(row, current_ids, xi_ids, captain_id, vice_id) for row in bench],
        "squad": [_annotate(row, current_ids, xi_ids, captain_id, vice_id) for row in sorted(squad, key=lambda r: (nint(r.get("position_id")), -nfloat(r.get("squad_score"))))],
        "captain": next((_annotate(row, current_ids, xi_ids, captain_id, vice_id) for row in xi if nint(row.get("element")) == captain_id), None),
        "vice_captain": next((_annotate(row, current_ids, xi_ids, captain_id, vice_id) for row in xi if nint(row.get("element")) == vice_id), None),
        "transfers_in": sorted(incoming, key=lambda row: (nint(row.get("position_id")), -nfloat(row.get("squad_score")))),
        "transfers_out": outgoing,
        "analysis_horizon": {"event_ids": event_ids, "matches": max(5, int(horizon or 5)), "starts_after_current_deadline": True},
        "quality_control": {
            "squad_size": len(squad),
            "position_rules_checked": True,
            "max_three_per_club_checked": True,
            "selling_prices_used_for_budget": exact_budget,
            "best_xi_formation_checked": True,
            "captaincy_ranked": True,
        },
        "data_sources": [
            "Fantasy Premier League bootstrap",
            "Fantasy Premier League fixtures",
            "Lofthus Road Open live ownership",
            "Managerens faktiske salgspriser og bank når tilgjengelig",
        ],
    }
