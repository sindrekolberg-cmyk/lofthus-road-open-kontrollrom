from __future__ import annotations

from typing import Any

from api.deep_analysis import (
    DeepFPLProjectionProvider,
    _enrich_rows,
    _fetch_recent_summaries,
    _future_projection_bootstrap,
    _rerank_with_recent,
    _squad_rows,
    _transfer_feasibility,
)
from api.engine import AppEngine
from api.wildcard import (
    POSITION_ORDERINGS,
    POSITION_REQUIREMENTS,
    _available_budget,
    _best_xi,
    _build_one,
    _candidate_rows,
    _improve_squad,
    _objective,
)
from lro_analysis import nfloat, nint
from lro_transfer_strategy import build_transfer_strategy


def _neutralize(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    for key in ("why", "evidence"):
        if isinstance(item.get(key), list):
            item[key] = [
                str(value)
                .replace("Lofthus-eierskap", "Ligaeierskap")
                .replace("Lofthus", "ligaen")
                for value in item[key]
            ]
    return item


def build_tenant_transfer_analysis(
    *,
    engine: AppEngine,
    entry_id: int,
    strategy: str,
    risk: int,
    horizon: int,
    target: str = "",
    rival_id: int = 0,
    position: str = "all",
) -> dict[str, Any]:
    snap = engine.snapshot()
    if not snap.state:
        return {"ok": False, "error": "Live-data bygges. Prøv igjen om noen sekunder."}
    try:
        fixtures = list(engine.client.fixtures() or [])
    except Exception:
        fixtures = list(snap.state.fixtures or [])

    horizon = max(5, int(horizon or 5))
    projection_bootstrap, first_event_id = _future_projection_bootstrap(snap.bootstrap)
    provider = DeepFPLProjectionProvider(snap.bootstrap)
    body = build_transfer_strategy(
        state=snap.state,
        bootstrap=projection_bootstrap,
        fixtures=fixtures,
        entry_id=int(entry_id),
        strategy=strategy,
        risk=int(risk),
        horizon=horizon,
        target=target,
        rival_id=int(rival_id or 0),
        position=position,
        provider=provider,
    )
    if not body.get("ok"):
        return body

    base_ranked = _enrich_rows(list(body.get("ranked") or []), provider)
    recent_payloads = _fetch_recent_summaries(engine.client, base_ranked)
    ranked = _rerank_with_recent(base_ranked, recent_payloads)
    squad = _squad_rows(snap.state, int(entry_id))
    bank_raw = (body.get("manager") or {}).get("bank")
    bank = None if bank_raw in (None, "") else nfloat(bank_raw)

    legal_ranked: list[dict[str, Any]] = []
    for row in ranked:
        feasibility = _transfer_feasibility(row, squad, bank)
        row["transfer_feasibility"] = feasibility
        if feasibility.get("legal"):
            legal_ranked.append(_neutralize(row))
    body["ranked"] = legal_ranked[:12]
    body["recommendations"] = legal_ranked[:5]

    for key in ("safe", "aggressive", "differentials"):
        enriched = _enrich_rows(list(body.get(key) or []), provider)
        kept = []
        for row in enriched:
            feasibility = _transfer_feasibility(row, squad, bank)
            row["transfer_feasibility"] = feasibility
            if feasibility.get("legal"):
                kept.append(_neutralize(row))
        body[key] = kept[:3]

    body["projection_source"] = provider.source
    body["analysis_horizon"] = {
        "matches": horizon,
        "first_event_id": first_event_id,
        "starts_after_current_deadline": True,
    }
    body["quality_control"] = {
        "club_limit_checked": True,
        "budget_checked_when_selling_price_is_known": True,
        "recent_player_history_loaded": bool(recent_payloads),
        "shortlisted_before_recent_history": len(base_ranked),
        "legal_shortlist": len(legal_ranked),
    }
    body["coverage"] = {
        "fpl_native": True,
        "league_context": True,
        "fixture_strength": True,
        "set_piece_role": True,
        "recent_match_history": True,
        "event_level_situational_matchups": False,
        "note": "Situasjonsspesifikk motstanderanalyse krever en ekstern event-datakilde. Modellen markerer dette eksplisitt i stedet for å gjette.",
    }
    body["data_sources"] = [
        "Fantasy Premier League bootstrap",
        "Fantasy Premier League fixtures",
        "Fantasy Premier League element history",
        "Mini-ligaens live eierskap",
    ]
    return body


def _annotate_neutral(
    row: dict[str, Any],
    current_ids: set[int],
    xi_ids: set[int],
    captain_id: int,
    vice_id: int,
) -> dict[str, Any]:
    item = _neutralize(dict(row))
    evidence = list(item.get("evidence") or [])
    evidence.append(
        f"Ligaeierskap {nfloat(item.get('league_ownership_pct')):.0f} % · globalt {nfloat(item.get('global_ownership_pct')):.0f} %"
    )
    item["evidence"] = evidence[:7]
    element = nint(item.get("element"))
    item["currently_owned"] = element in current_ids
    item["starting_xi"] = element in xi_ids
    item["captain"] = element == captain_id
    item["vice_captain"] = element == vice_id
    return item


def build_tenant_wildcard_analysis(
    *,
    engine: AppEngine,
    entry_id: int,
    strategy: str,
    risk: int,
    horizon: int = 5,
) -> dict[str, Any]:
    snap = engine.snapshot()
    if not snap.state:
        return {"ok": False, "error": "Live-data bygges. Prøv igjen om noen sekunder."}
    state = snap.state
    manager = state.manager(int(entry_id))
    if not manager:
        return {"ok": False, "error": "Manageren finnes ikke i ligaen."}
    try:
        fixtures = list(engine.client.fixtures() or [])
    except Exception:
        fixtures = list(state.fixtures or [])

    horizon = max(5, int(horizon or 5))
    budget, exact_budget, current_squad = _available_budget(state, int(entry_id))
    rows, _provider, event_ids, cohort_label = _candidate_rows(
        bootstrap=snap.bootstrap,
        fixtures=fixtures,
        state=state,
        entry_id=int(entry_id),
        strategy=strategy,
        risk=int(risk),
        horizon=horizon,
    )
    rows = [_neutralize(row) for row in rows]
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
    captain_order = sorted(
        xi,
        key=lambda row: (-nfloat(row.get("captain_score")), -nfloat(row.get("squad_score"))),
    )
    captain_id = nint(captain_order[0].get("element")) if captain_order else 0
    vice_id = nint(captain_order[1].get("element")) if len(captain_order) > 1 else 0
    xi_ids = {nint(row.get("element")) for row in xi}
    current_ids = {nint(row.get("element")) for row in current_squad}
    squad_ids = {nint(row.get("element")) for row in squad}

    incoming = [
        _annotate_neutral(row, current_ids, xi_ids, captain_id, vice_id)
        for row in squad
        if nint(row.get("element")) not in current_ids
    ]
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

    annotated_xi = [_annotate_neutral(row, current_ids, xi_ids, captain_id, vice_id) for row in xi]
    annotated_bench = [_annotate_neutral(row, current_ids, xi_ids, captain_id, vice_id) for row in bench]
    annotated_squad = [
        _annotate_neutral(row, current_ids, xi_ids, captain_id, vice_id)
        for row in sorted(squad, key=lambda r: (nint(r.get("position_id")), -nfloat(r.get("squad_score"))))
    ]

    return {
        "ok": True,
        "manager": {"entry": manager.entry, "manager": manager.manager, "team": manager.team, "rank": manager.live_rank},
        "strategy": {"id": strategy, "risk": int(risk), "horizon": horizon, "cohort": cohort_label},
        "budget": {"available": budget, "used": squad_cost, "remaining": round(budget - squad_cost, 1), "exact": exact_budget},
        "starting_xi": annotated_xi,
        "bench": annotated_bench,
        "squad": annotated_squad,
        "captain": next((row for row in annotated_xi if row.get("captain")), None),
        "vice_captain": next((row for row in annotated_xi if row.get("vice_captain")), None),
        "transfers_in": sorted(incoming, key=lambda row: (nint(row.get("position_id")), -nfloat(row.get("squad_score")))),
        "transfers_out": outgoing,
        "analysis_horizon": {"event_ids": event_ids, "matches": horizon, "starts_after_current_deadline": True},
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
            "Mini-ligaens live eierskap",
            "Managerens salgspriser og bank når tilgjengelig",
        ],
    }
