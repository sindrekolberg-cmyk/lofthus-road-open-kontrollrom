from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from lro_analysis import manager_squad, nfloat, nint
from lro_fpl import current_event_id, fixture_window, player_catalog


# ---------------------------------------------------------------------------
# Central strategy configuration. All ranking weights live here.
# ---------------------------------------------------------------------------

STRATEGY_META = {
    "rapid_lofthus": {
        "id": "rapid_lofthus",
        "label": "Klatre raskt i Lofthus",
        "blurb": "Jakte de foran deg med spillere de ikke har.",
    },
    "win_lofthus": {
        "id": "win_lofthus",
        "label": "Vinne Lofthus",
        "blurb": "Avstanden til førsteplass styrer hvor hardt du må spille.",
    },
    "defend": {
        "id": "defend",
        "label": "Forsvare posisjonen min",
        "blurb": "Beskytt plassen mot det feltet rundt deg allerede eier.",
    },
    "win_month": {
        "id": "win_month",
        "label": "Vinne måneden",
        "blurb": "Månedstabellen, ikke sesongen, er rivalgruppen.",
    },
    "beat_rival": {
        "id": "beat_rival",
        "label": "Slå en bestemt rival",
        "blurb": "Ett navn. Innhente eller holde unna.",
    },
    "climb_or": {
        "id": "climb_or",
        "label": "Klatre jevnt på OR",
        "blurb": "Trygg output, minutter og kampprogram — ikke Lofthus-poker.",
    },
    "balanced": {
        "id": "balanced",
        "label": "Balansert",
        "blurb": "En blanding av kvalitet og litt Lofthus-leverage.",
    },
}

# Component weights sum conceptually around 100 before risk blending.
STRATEGY_WEIGHTS: dict[str, dict[str, float]] = {
    "climb_or": {
        "projection": 28,
        "minutes": 18,
        "fixture": 16,
        "form": 8,
        "value": 6,
        "captain": 10,
        "availability": 12,
        "league_leverage": 1,
        "target_leverage": 0,
        "upside": 2,
        "downside_protection": 10,
        "risk_penalty": 14,
    },
    "rapid_lofthus": {
        "projection": 16,
        "minutes": 10,
        "fixture": 12,
        "form": 6,
        "value": 4,
        "captain": 5,
        "availability": 10,
        "league_leverage": 8,
        "target_leverage": 24,
        "upside": 16,
        "downside_protection": 2,
        "risk_penalty": 4,
    },
    "defend": {
        "projection": 22,
        "minutes": 14,
        "fixture": 12,
        "form": 6,
        "value": 4,
        "captain": 6,
        "availability": 12,
        "league_leverage": 4,
        "target_leverage": 6,
        "upside": 2,
        "downside_protection": 22,
        "risk_penalty": 16,
    },
    "win_month": {
        "projection": 24,
        "minutes": 12,
        "fixture": 14,
        "form": 8,
        "value": 4,
        "captain": 8,
        "availability": 10,
        "league_leverage": 4,
        "target_leverage": 16,
        "upside": 10,
        "downside_protection": 6,
        "risk_penalty": 8,
    },
    "beat_rival": {
        "projection": 16,
        "minutes": 10,
        "fixture": 12,
        "form": 6,
        "value": 4,
        "captain": 8,
        "availability": 10,
        "league_leverage": 4,
        "target_leverage": 22,
        "upside": 14,
        "downside_protection": 8,
        "risk_penalty": 6,
    },
    "balanced": {
        "projection": 20,
        "minutes": 12,
        "fixture": 12,
        "form": 8,
        "value": 6,
        "captain": 8,
        "availability": 10,
        "league_leverage": 6,
        "target_leverage": 10,
        "upside": 8,
        "downside_protection": 8,
        "risk_penalty": 8,
    },
    "win_lofthus": {
        "projection": 18,
        "minutes": 11,
        "fixture": 12,
        "form": 6,
        "value": 4,
        "captain": 6,
        "availability": 10,
        "league_leverage": 6,
        "target_leverage": 16,
        "upside": 12,
        "downside_protection": 10,
        "risk_penalty": 8,
    },
}

POSITION_FILTER = {
    "all": None,
    "gk": 1,
    "keeper": 1,
    "def": 2,
    "forsvar": 2,
    "mid": 3,
    "midtbane": 3,
    "fwd": 4,
    "angrep": 4,
}

UNAVAILABLE = {"u", "s"}
INJURED = {"i"}


class ProjectionProvider(Protocol):
    source: str

    def score(self, player: dict[str, Any], fixture_rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
        ...


class HeuristicProjectionProvider:
    """Transparent FPL-bootstrap heuristic. Not an xPts model."""

    source = "heuristic_projection"

    def score(self, player: dict[str, Any], fixture_rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
        form = nfloat(player.get("form"))
        ppg = nfloat(player.get("points_per_game"))
        minutes = nfloat(player.get("minutes"))
        starts = nfloat(player.get("starts"))
        xgi90 = nfloat(player.get("xgi_per90"))
        ict = nfloat(player.get("ict_index"))
        events_played = max(starts, minutes / 80.0, 1.0)
        minutes_rate = min(1.0, minutes / max(events_played * 80.0, 1.0))
        start_rate = min(1.0, starts / max(events_played, 1.0)) if starts else minutes_rate
        role = 0.55 * min(1.0, ppg / 7.0) + 0.25 * min(1.0, form / 8.0) + 0.20 * min(1.0, xgi90 / 0.7)
        fixture = fixture_quality(fixture_rows, horizon)
        projection = clamp(0.42 * role + 0.28 * start_rate + 0.18 * fixture + 0.12 * min(1.0, ict / 250.0), 0, 1)
        minutes_score = clamp(0.65 * start_rate + 0.35 * minutes_rate, 0, 1)
        return {
            "source": self.source,
            "projection": projection,
            "minutes": minutes_score,
            "form": clamp(form / 8.0, 0, 1),
            "fixture": fixture,
            "index_10": round(projection * 10, 1),
        }


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def fixture_quality(rows: list[dict[str, Any]], horizon: int) -> float:
    if not rows:
        return 0.45
    weights = [1.0, 0.72, 0.52, 0.38, 0.28][: max(1, horizon)]
    scored = 0.0
    total_w = 0.0
    for i, row in enumerate(rows[:horizon]):
        w = weights[i] if i < len(weights) else 0.22
        diff = nint(row.get("difficulty"), 3)
        scored += w * clamp((6 - diff) / 4.0, 0, 1)
        total_w += w
    return scored / total_w if total_w else 0.45


def blend_weights(strategy: str, risk: int, chase_mix: float = 0.0) -> dict[str, float]:
    key = strategy if strategy in STRATEGY_WEIGHTS else "balanced"
    if key == "win_lofthus":
        rapid = STRATEGY_WEIGHTS["rapid_lofthus"]
        defend = STRATEGY_WEIGHTS["defend"]
        base = {k: (1 - chase_mix) * defend[k] + chase_mix * rapid[k] for k in rapid}
    else:
        base = dict(STRATEGY_WEIGHTS[key])
    t = clamp((nint(risk, 50) - 50) / 50.0, -1, 1)
    out = dict(base)
    out["upside"] = base["upside"] * (1 + 0.5 * t)
    out["target_leverage"] = base["target_leverage"] * (1 + 0.42 * t)
    out["risk_penalty"] = base["risk_penalty"] * (1 - 0.6 * t)
    out["minutes"] = base["minutes"] * (1 - 0.18 * t)
    out["downside_protection"] = base["downside_protection"] * (1 - 0.4 * t)
    out["projection"] = base["projection"] * (1 - 0.08 * t)
    return out


def tier(score: float) -> str:
    if score >= 0.78:
        return "very_high"
    if score >= 0.62:
        return "high"
    if score >= 0.42:
        return "medium"
    return "low"


def tier_label(score: float) -> str:
    return {
        "very_high": "Svært høy",
        "high": "Høy",
        "medium": "Middels",
        "low": "Lav",
    }[tier(score)]


def data_ground(player: dict[str, Any], fixture_rows: list[dict[str, Any]]) -> str:
    chance = player.get("chance_next")
    if player.get("status") in UNAVAILABLE | INJURED and (chance is None or nint(chance) < 50):
        return "svakt"
    if not fixture_rows or nfloat(player.get("minutes")) < 90:
        return "svakt"
    if nfloat(player.get("starts")) < 2:
        return "middels"
    return "sterkt"


@dataclass
class StrategyContext:
    entry_id: int
    squad_elements: set[int]
    squad_by_position: dict[int, list[dict[str, Any]]]
    squad_team_counts: dict[int, int]
    bank: float | None
    selling_known: bool
    selling_prices: dict[int, float | None]
    chip: str
    live_rank: int
    live_total: int
    league_size: int
    gap_to_leader: int
    gap_to_top10: int
    rounds_remaining: int
    cohort_entries: list[int]
    cohort_label: str
    rival_id: int | None
    chasing_rival: bool
    owned_by: dict[int, set[int]]
    league_owners: dict[int, int]
    month_name: str
    warnings: list[str] = field(default_factory=list)


def _pick_rows(ownership: dict) -> list[dict[str, Any]]:
    picks = ownership.get("picks")
    if picks is None:
        return []
    if hasattr(picks, "to_dict"):
        if getattr(picks, "empty", False):
            return []
        return picks.to_dict("records")
    return list(picks or [])


def _manager_event_row(ownership: dict, entry_id: int) -> dict[str, Any]:
    events = ownership.get("manager_events")
    rows: list[dict[str, Any]] = []
    if events is not None and hasattr(events, "to_dict") and not getattr(events, "empty", True):
        rows = events.to_dict("records")
    elif isinstance(events, list):
        rows = events
    return next((r for r in rows if nint(r.get("entry")) == int(entry_id)), {})


def rounds_remaining(bootstrap: dict) -> int:
    current = current_event_id(bootstrap) or 0
    ids = [nint(e.get("id")) for e in bootstrap.get("events", []) or [] if nint(e.get("id"))]
    return max(1, sum(1 for i in ids if i >= current))


def horizon_event_ids(bootstrap: dict, horizon: int) -> list[int]:
    current = current_event_id(bootstrap) or 0
    ids = sorted(nint(e.get("id")) for e in bootstrap.get("events", []) or [] if nint(e.get("id")))
    remaining = [i for i in ids if i >= current]
    return remaining[: max(1, min(5, int(horizon or 3)))]


def _rank_list(state: Any, month: bool) -> list[Any]:
    if month:
        return list(state.month_ranking())
    return list(state.managers_by_rank())


def select_cohort(
    state: Any,
    entry_id: int,
    strategy: str,
    target: str = "",
    rival_id: int = 0,
) -> tuple[list[int], str]:
    me = state.manager(entry_id)
    if not me:
        return [], "Ingen målgruppe"
    ranked = _rank_list(state, month=strategy == "win_month")
    if strategy == "win_month":
        ranked = _rank_list(state, True)
        ahead = [m.entry for m in ranked if m.entry != entry_id and (m.month_rank or 10**9) <= max(me.month_rank or 10**9, 1)]
        near = [m.entry for m in ranked if m.entry != entry_id][:12]
        chosen = ahead[:16] or near
        return chosen, f"Månedsfeltet ({len(chosen)})"
    if strategy == "beat_rival" and rival_id:
        return [int(rival_id)], "Valgt rival"
    want = (target or "").strip().casefold()
    others = [m for m in ranked if m.entry != entry_id]
    ahead = [m for m in others if m.live_rank < me.live_rank]
    if want in {"top_10", "topp 10"}:
        chosen = [m.entry for m in ranked if m.entry != entry_id and m.live_rank <= 10][:10]
        return chosen, "Topp 10"
    if want in {"top_20", "topp 20"}:
        chosen = [m.entry for m in ranked if m.entry != entry_id and m.live_rank <= 20][:20]
        return chosen, "Topp 20"
    if want in {"next_10", "neste 10"}:
        pool = ahead[:10] or others[:10]
        return [m.entry for m in pool], "De neste 10"
    if want in {"next_20", "neste 20"}:
        pool = ahead[:20] or others[:20]
        return [m.entry for m in pool], "De neste 20"
    if strategy == "defend":
        around = [m for m in ranked if m.entry != entry_id and abs(m.live_rank - me.live_rank) <= 8][:16]
        if not around:
            around = others[:12]
        return [m.entry for m in around], "Nærmeste rivaler"
    pool = ahead[:15] or others[:15]
    return [m.entry for m in pool], "De nærmeste foran deg"


def build_context(state: Any, bootstrap: dict, entry_id: int, strategy: str, target: str, rival_id: int) -> StrategyContext:
    me = state.manager(int(entry_id))
    if not me:
        raise ValueError("manager")
    squad = manager_squad(state.ownership, int(entry_id))
    rows = squad.to_dict("records") if squad is not None and not squad.empty else []
    elements = {nint(r.get("element")) for r in rows if nint(r.get("element"))}
    team_counts: dict[int, int] = {}
    by_pos: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: [], 4: []}
    selling: dict[int, float | None] = {}
    selling_known = False
    for r in rows:
        el = nint(r.get("element"))
        tid = nint(r.get("team_id"))
        pid = nint(r.get("position_id"))
        team_counts[tid] = team_counts.get(tid, 0) + 1
        if pid in by_pos:
            by_pos[pid].append(r)
        sp = r.get("selling_price")
        if sp is None or sp == "":
            selling[el] = None
        else:
            selling[el] = nfloat(sp)
            selling_known = True
    event_row = _manager_event_row(state.ownership, int(entry_id))
    bank_raw = event_row.get("bank")
    bank = None if bank_raw is None or bank_raw == "" else nfloat(bank_raw)
    owned_by: dict[int, set[int]] = {}
    league_owners: dict[int, int] = {}
    for r in _pick_rows(state.ownership):
        el = nint(r.get("element"))
        ent = nint(r.get("entry"))
        if not el or not ent:
            continue
        owned_by.setdefault(el, set()).add(ent)
        league_owners[el] = league_owners.get(el, 0) + 1
    ranked = state.managers_by_rank()
    leader = ranked[0] if ranked else me
    tenth = next((m for m in ranked if m.live_rank == 10), ranked[min(9, len(ranked) - 1)] if ranked else me)
    cohort, label = select_cohort(state, int(entry_id), strategy, target, rival_id)
    rival = state.manager(int(rival_id)) if rival_id else None
    chasing = bool(rival and me.live_total_points < rival.live_total_points)
    warnings: list[str] = []
    chip = str(me.active_chip or event_row.get("active_chip") or "").strip()
    if chip.lower() in {"wildcard", "free hit", "freehit"}:
        warnings.append("Aktiv sjetong. Dette er ikke en vanlig én-bytte-uke.")
    return StrategyContext(
        entry_id=int(entry_id),
        squad_elements=elements,
        squad_by_position=by_pos,
        squad_team_counts=team_counts,
        bank=bank,
        selling_known=selling_known,
        selling_prices=selling,
        chip=chip,
        live_rank=me.live_rank,
        live_total=me.live_total_points,
        league_size=state.league_size,
        gap_to_leader=max(0, leader.live_total_points - me.live_total_points),
        gap_to_top10=max(0, (tenth.live_total_points if tenth else me.live_total_points) - me.live_total_points),
        rounds_remaining=rounds_remaining(bootstrap),
        cohort_entries=cohort,
        cohort_label=label,
        rival_id=int(rival_id) if rival_id else None,
        chasing_rival=chasing,
        owned_by=owned_by,
        league_owners=league_owners,
        month_name=str(state.month_name or ""),
        warnings=warnings,
    )


def availability_score(player: dict[str, Any]) -> tuple[float, str]:
    status = str(player.get("status") or "a").casefold()
    chance = player.get("chance_next")
    news = str(player.get("news") or "").strip()
    if status in UNAVAILABLE:
        return 0.0, news or "Utilgjengelig"
    if status == "s":
        return 0.0, news or "Karantene"
    if chance is not None and nint(chance) <= 0:
        return 0.0, news or "Usikker spilletid"
    if status in INJURED:
        c = 40 if chance is None else nint(chance)
        return clamp(c / 100.0 * 0.45, 0, 0.45), news or "Skade"
    if status == "d" or (chance is not None and nint(chance) < 75):
        c = 50 if chance is None else nint(chance)
        return clamp(c / 100.0, 0, 0.85), news or "Usikker"
    return 1.0, news


def excluded_unavailable(player: dict[str, Any]) -> bool:
    score, _ = availability_score(player)
    return score <= 0.05


def cohort_stats(element: int, ctx: StrategyContext) -> dict[str, Any]:
    owners = ctx.owned_by.get(int(element), set())
    cohort = [e for e in ctx.cohort_entries if e]
    n = len(cohort) or 1
    owned = sum(1 for e in cohort if e in owners)
    return {
        "owners": owned,
        "size": len(cohort),
        "pct": round(100.0 * owned / n, 1) if cohort else 0.0,
        "nonowners": max(0, len(cohort) - owned),
    }


def league_stats(element: int, ctx: StrategyContext) -> dict[str, Any]:
    owned = ctx.league_owners.get(int(element), 0)
    n = max(1, ctx.league_size)
    return {"owners": owned, "size": ctx.league_size, "pct": round(100.0 * owned / n, 1)}


def feature_vector(
    player: dict[str, Any],
    proj: dict[str, Any],
    ctx: StrategyContext,
    strategy: str,
) -> dict[str, float]:
    el = nint(player.get("element_id") or player.get("id"))
    coh = cohort_stats(el, ctx)
    av, _ = availability_score(player)
    price = nfloat(player.get("current_price"), 6.0)
    value = clamp((proj["projection"] * 10) / max(price, 4.0), 0, 1)
    captain = clamp(proj["projection"] * (0.7 + 0.3 * proj["minutes"]), 0, 1)
    nonown_frac = coh["nonowners"] / max(1, coh["size"] or 1)
    own_frac = coh["owners"] / max(1, coh["size"] or 1)
    target_leverage = clamp(nonown_frac * proj["projection"], 0, 1)
    if strategy == "beat_rival" and ctx.rival_id:
        rival_owns = ctx.rival_id in ctx.owned_by.get(el, set())
        if ctx.chasing_rival:
            target_leverage = 0.85 * (0.0 if rival_owns else 1.0) * proj["projection"] + 0.15 * target_leverage
        else:
            target_leverage = 0.75 * (1.0 if rival_owns else 0.15) * proj["projection"] + 0.25 * target_leverage
    league_own = ctx.league_owners.get(el, 0) / max(1, ctx.league_size)
    league_leverage = clamp((1 - league_own) * proj["projection"], 0, 1)
    downside = clamp(own_frac * proj["projection"], 0, 1)
    risk = clamp((1 - proj["minutes"]) * 0.55 + (1 - av) * 0.45 + max(0, 0.35 - proj["projection"]), 0, 1)
    upside = clamp(proj["projection"] * (0.35 + 0.65 * nonown_frac), 0, 1)
    return {
        "projection": proj["projection"],
        "minutes": proj["minutes"],
        "fixture": proj["fixture"],
        "form": proj["form"],
        "value": value,
        "captain": captain,
        "availability": av,
        "league_leverage": league_leverage,
        "target_leverage": target_leverage,
        "upside": upside,
        "downside_protection": downside,
        "risk_penalty": risk,
    }


def strategy_score(features: dict[str, float], weights: dict[str, float]) -> float:
    total = 0.0
    mass = 0.0
    for key, w in weights.items():
        if w <= 0:
            continue
        val = features.get(key, 0.0)
        if key == "risk_penalty":
            total += w * (1.0 - val)
        else:
            total += w * val
        mass += w
    return 10.0 * (total / mass) if mass else 0.0


def explanation_facts(player: dict[str, Any], features: dict[str, float], coh: dict[str, Any], strategy: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if coh["size"] and strategy not in {"climb_or"}:
        facts.append({"code": "target_nonowners", "n": coh["nonowners"], "of": coh["size"]})
    facts.append({"code": "projection_tier", "tier": tier(features["projection"])})
    facts.append({"code": "fixture_tier", "tier": tier(features["fixture"])})
    facts.append({"code": "minutes_tier", "tier": tier(features["minutes"])})
    if features["availability"] < 0.85:
        facts.append({"code": "availability", "tier": tier(features["availability"])})
    if features["downside_protection"] >= 0.55 and strategy in {"defend", "win_lofthus", "climb_or"}:
        facts.append({"code": "template_cover", "n": coh["owners"], "of": coh["size"]})
    return facts[:4]


def why_lines(facts: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for f in facts:
        code = f.get("code")
        if code == "target_nonowners":
            lines.append(f"{f['n']} av {f['of']} i målgruppen mangler ham")
        elif code == "projection_tier":
            lines.append(f"Vurdering: { {'very_high': 'svært høy', 'high': 'høy', 'medium': 'middels', 'low': 'lav'}[f['tier']] }")
        elif code == "fixture_tier":
            lines.append(f"Kampprogram: { {'very_high': 'svært godt', 'high': 'godt', 'medium': 'middels', 'low': 'krevende'}[f['tier']] }")
        elif code == "minutes_tier":
            lines.append(f"Spilletid: { {'very_high': 'trygg', 'high': 'trygg', 'medium': 'usikker', 'low': 'tvilsom'}[f['tier']] }")
        elif code == "availability":
            lines.append("Usikkerhet rundt spilletid")
        elif code == "template_cover":
            lines.append(f"{f['n']} av {f['of']} nære rivaler eier ham")
    return lines


def fixture_labels(rows: list[dict[str, Any]], teams: dict[int, str], limit: int) -> list[str]:
    out = []
    for row in rows[:limit]:
        opp = teams.get(nint(row.get("opponent_id")), "?")
        side = "H" if row.get("home") else "B"
        out.append(f"{opp} ({side})")
    return out


def serialize_player(
    player: dict[str, Any],
    score: float,
    features: dict[str, float],
    ctx: StrategyContext,
    fixture_rows: list[dict[str, Any]],
    teams: dict[int, str],
    horizon: int,
    strategy: str,
    budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    el = nint(player.get("element_id"))
    coh = cohort_stats(el, ctx)
    lig = league_stats(el, ctx)
    facts = explanation_facts(player, features, coh, strategy)
    _, news = availability_score(player)
    return {
        "element": el,
        "player": player.get("web_name"),
        "full_name": player.get("full_name"),
        "club": player.get("club"),
        "club_name": player.get("club_name"),
        "team_id": nint(player.get("team_id")),
        "position": player.get("position"),
        "position_id": nint(player.get("position_id")),
        "price": player.get("current_price"),
        "image_url": player.get("image_url") or "",
        "fixtures": fixture_labels(fixture_rows, teams, horizon),
        "league_ownership_pct": lig["pct"],
        "league_owners": lig["owners"],
        "league_size": lig["size"],
        "target_cohort_ownership_pct": coh["pct"],
        "target_cohort_owners": coh["owners"],
        "target_cohort_size": coh["size"],
        "target_cohort_non_owner_count": coh["nonowners"],
        "global_ownership_pct": nfloat(player.get("selected_by_pct")),
        "strategy_score": round(score, 1),
        "projection_index": round(features["projection"] * 10, 1),
        "projection_source": "heuristic_projection",
        "relative_upside": tier_label(features["upside"]),
        "nedsiderisiko": tier_label(features["risk_penalty"]),
        "risk": tier_label(features["risk_penalty"]),
        "strategic_value": tier_label(clamp(score / 10.0, 0, 1)),
        "datagrunnlag": data_ground(player, fixture_rows),
        "facts": facts,
        "why": why_lines(facts),
        "news": news,
        "scores": {k: round(v, 3) for k, v in features.items()},
        "budget": budget,
        "club_limit_ok": ctx.squad_team_counts.get(nint(player.get("team_id")), 0) < 3,
    }


def pick_lists(ranked: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if not ranked:
        return {"recommended": [], "safe": [], "aggressive": [], "differentials": []}
    recommended = ranked[:1]
    safe = sorted(ranked, key=lambda r: (-r["scores"]["minutes"] - r["scores"]["projection"] + r["scores"]["risk_penalty"], -r["strategy_score"]))[:1]
    aggressive = sorted(ranked, key=lambda r: (-r["scores"]["upside"] - r["scores"]["target_leverage"], -r["strategy_score"]))[:1]
    diffs = [r for r in ranked if r["target_cohort_ownership_pct"] <= 25 and r["scores"]["projection"] >= 0.42][:1]
    if not diffs:
        diffs = aggressive
    def unique(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[int] = set()
        out = []
        for r in rows:
            if r["element"] in seen:
                continue
            seen.add(r["element"])
            out.append(r)
        return out
    return {
        "recommended": unique(recommended),
        "safe": unique(safe),
        "aggressive": unique(aggressive),
        "differentials": unique(diffs),
    }


def sell_candidates(
    catalog: dict[int, dict[str, Any]],
    ctx: StrategyContext,
    fixtures: list[dict[str, Any]],
    event_ids: list[int],
    provider: ProjectionProvider,
    teams: dict[int, str],
    horizon: int,
) -> list[dict[str, Any]]:
    out = []
    for pos, rows in ctx.squad_by_position.items():
        for row in rows:
            el = nint(row.get("element"))
            player = catalog.get(el)
            if not player:
                continue
            window = fixture_window(fixtures, nint(player.get("team_id")), event_ids)
            proj = provider.score(player, window, horizon)
            av, news = availability_score(player)
            bad = (1 - proj["projection"]) * 0.4 + (1 - proj["fixture"]) * 0.25 + (1 - proj["minutes"]) * 0.2 + (1 - av) * 0.15
            out.append({
                "element": el,
                "player": player.get("web_name"),
                "club": player.get("club"),
                "position": player.get("position"),
                "position_id": pos,
                "price": player.get("current_price"),
                "selling_price": ctx.selling_prices.get(el),
                "on_bench": bool(row.get("on_bench")),
                "team_id": nint(player.get("team_id")),
                "sell_score": round(10 * bad, 1),
                "why": [x for x in [
                    "Svak vurdering fremover" if proj["projection"] < 0.45 else "",
                    "Krevende kampprogram" if proj["fixture"] < 0.4 else "",
                    news or ("Usikker spilletid" if av < 0.8 else ""),
                ] if x][:3] or ["Lavest strategisk verdi i troppen"],
                "fixtures": fixture_labels(window, teams, horizon),
                "image_url": player.get("image_url") or "",
            })
    out.sort(key=lambda r: -r["sell_score"])
    return out[:5]


def budget_note(ctx: StrategyContext, buy_price: float, sell_row: dict[str, Any] | None) -> dict[str, Any]:
    if ctx.bank is None:
        return {"status": "unknown", "label": "Budsjett må bekreftes"}
    if sell_row and sell_row.get("selling_price") is None:
        return {"status": "unknown", "label": "Budsjett må bekreftes"}
    sale = nfloat(sell_row.get("selling_price")) if sell_row and sell_row.get("selling_price") is not None else 0.0
    room = (ctx.bank or 0) + sale
    if room + 0.05 >= buy_price:
        return {"status": "likely", "label": "Sannsynlig innenfor budsjett", "room": round(room, 1)}
    return {"status": "short", "label": "Budsjett må bekreftes", "room": round(room, 1)}


def transfer_pairs(buys: list[dict[str, Any]], sells: list[dict[str, Any]], ctx: StrategyContext) -> list[dict[str, Any]]:
    pairs = []
    for buy in buys[:4]:
        if not buy:
            continue
        buy_team = nint(buy.get("team_id"))
        for sell in sells:
            if sell["position_id"] != buy["position_id"]:
                continue
            count = ctx.squad_team_counts.get(buy_team, 0)
            if sell["team_id"] == buy_team:
                count = max(0, count - 1)
            if count >= 3:
                continue
            note = budget_note(ctx, nfloat(buy.get("price")), sell)
            pairs.append({
                "out": {"element": sell["element"], "player": sell["player"], "club": sell["club"]},
                "inn": {"element": buy["element"], "player": buy["player"], "club": buy["club"]},
                "budget": note,
                "why": (buy.get("why") or [])[:2] + (sell.get("why") or [])[:1],
            })
            if len(pairs) >= 3:
                return pairs
    return pairs


def strategy_summary(ctx: StrategyContext, strategy: str, risk: int) -> str:
    meta = STRATEGY_META.get(strategy, STRATEGY_META["balanced"])
    if strategy == "beat_rival" and ctx.rival_id:
        verb = "innhente" if ctx.chasing_rival else "holde unna"
        return f"Du skal {verb} én rival over {ctx.rounds_remaining} runder. Anbefalingene følger det."
    if strategy == "win_month":
        return f"Målgruppen er {ctx.cohort_label.lower()} i {ctx.month_name or 'måneden'}, ikke sesongtabellen."
    if strategy == "defend":
        return f"Du ligger på {ctx.live_rank}. plass. Prioritet er å ikke bli straffet av det {ctx.cohort_label.lower()} allerede eier."
    if strategy == "climb_or":
        return "OR-modus vekter minutter, vurdering og kampprogram. Lofthus-eierskap teller lite."
    if ctx.gap_to_top10 > 0 and strategy in {"rapid_lofthus", "win_lofthus", "balanced"}:
        return (
            f"Du ligger {ctx.gap_to_top10} poeng bak topp 10. "
            f"{ctx.cohort_label} er {len(ctx.cohort_entries)} managere. "
            f"{'Høy risikovilje peker mot spillere få av dem eier.' if risk >= 70 else 'Hold kvaliteten høy, og bruk leverage der det faktisk finnes.'}"
        )
    if ctx.gap_to_leader == 0:
        return f"Du leder Lofthus. {meta['blurb']}"
    return f"Du ligger {ctx.gap_to_leader} poeng bak ledelsen, {ctx.live_rank}. plass av {ctx.league_size}."


def rank_candidates(
    *,
    catalog: dict[int, dict[str, Any]],
    fixtures: list[dict[str, Any]],
    ctx: StrategyContext,
    strategy: str,
    risk: int,
    horizon: int,
    event_ids: list[int],
    position: str,
    provider: ProjectionProvider | None = None,
    teams: dict[int, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    provider = provider or HeuristicProjectionProvider()
    teams = teams or {}
    pos_id = POSITION_FILTER.get((position or "all").casefold())
    chase = clamp(ctx.gap_to_leader / max(ctx.rounds_remaining * 12.0, 1.0), 0, 1)
    weights = blend_weights(strategy, risk, chase_mix=chase)
    ranked: list[dict[str, Any]] = []
    for player in catalog.values():
        el = nint(player.get("element_id"))
        if el in ctx.squad_elements:
            continue
        if pos_id and nint(player.get("position_id")) != pos_id:
            continue
        if excluded_unavailable(player):
            continue
        window = fixture_window(fixtures, nint(player.get("team_id")), event_ids)
        proj = provider.score(player, window, horizon)
        feats = feature_vector(player, proj, ctx, strategy)
        if feats["availability"] < 0.2:
            continue
        score = strategy_score(feats, weights)
        ranked.append(serialize_player(player, score, feats, ctx, window, teams, horizon, strategy))
    ranked.sort(key=lambda r: (-r["strategy_score"], -r["projection_index"], r["player"] or ""))
    sells = sell_candidates(catalog, ctx, fixtures, event_ids, provider, teams, horizon)
    return ranked, sells


def why_not_notes(ranked: list[dict[str, Any]], ctx: StrategyContext, strategy: str) -> list[dict[str, Any]]:
    notes = []
    pool = sorted(ranked, key=lambda r: -r["projection_index"])[:8]
    for row in pool:
        if row["target_cohort_owners"] >= max(2, int(0.55 * (row["target_cohort_size"] or 1))) and strategy == "rapid_lofthus":
            notes.append({
                "element": row["element"],
                "player": row["player"],
                "line": (
                    f"{row['player']} er et sterkt FPL-valg, men strategisk verdi for å klatre raskt i Lofthus er mer "
                    f"begrenset fordi {row['target_cohort_owners']} av {row['target_cohort_size']} i målgruppen allerede eier ham."
                ),
            })
        if len(notes) >= 3:
            break
    return notes


def build_transfer_strategy(
    *,
    state: Any,
    bootstrap: dict,
    fixtures: list[dict[str, Any]] | None,
    entry_id: int,
    strategy: str = "balanced",
    risk: int = 50,
    horizon: int = 3,
    target: str = "",
    rival_id: int = 0,
    position: str = "all",
    provider: ProjectionProvider | None = None,
) -> dict[str, Any]:
    strategy = strategy if strategy in STRATEGY_META else "balanced"
    horizon = 1 if horizon not in {1, 3, 5} else horizon
    risk = int(clamp(nint(risk, 50), 0, 100))
    if not state or not state.manager(int(entry_id)):
        return {"ok": False, "error": "Velg deg selv i Lofthus før vi kan gi personlige råd."}
    provider = provider or HeuristicProjectionProvider()
    catalog = player_catalog(bootstrap)
    teams = {
        nint(t.get("id")): str(t.get("short_name") or t.get("name") or "")
        for t in bootstrap.get("teams", []) or []
        if nint(t.get("id"))
    }
    fx = list(fixtures or state.fixtures or [])
    ctx = build_context(state, bootstrap, int(entry_id), strategy, target, int(rival_id or 0))
    event_ids = horizon_event_ids(bootstrap, horizon)
    ranked, sells = rank_candidates(
        catalog=catalog,
        fixtures=fx,
        ctx=ctx,
        strategy=strategy,
        risk=risk,
        horizon=horizon,
        event_ids=event_ids,
        position=position,
        provider=provider,
        teams=teams,
    )
    lists = pick_lists(ranked)
    top_buy = lists["recommended"][0] if lists["recommended"] else None
    pairs = transfer_pairs([top_buy] + lists["aggressive"] + lists["differentials"] if top_buy else [], sells, ctx)
    compare = []
    if ranked:
        for row in ranked[:6]:
            scores = {}
            for key in ("climb_or", "rapid_lofthus", "defend"):
                scores[key] = round(strategy_score(row["scores"], blend_weights(key, 50)), 1)
            if max(scores.values()) - min(scores.values()) >= 0.6:
                compare.append({"element": row["element"], "player": row["player"], "scores": scores})
            if len(compare) >= 3:
                break
    me = state.manager(int(entry_id))
    return {
        "ok": True,
        "projection_source": provider.source,
        "strategy": {
            **STRATEGY_META[strategy],
            "risk": risk,
            "horizon": horizon,
            "target": target or "",
            "position": position or "all",
        },
        "manager": {
            "entry": me.entry,
            "manager": me.manager,
            "team": me.team,
            "rank": me.live_rank,
            "total": me.live_total_points,
            "bank": ctx.bank,
            "chip": ctx.chip,
        },
        "context": {
            "league_rank": ctx.live_rank,
            "league_size": ctx.league_size,
            "points_gap": ctx.gap_to_leader,
            "gap_to_top10": ctx.gap_to_top10,
            "rounds_remaining": ctx.rounds_remaining,
            "target_cohort": {
                "label": ctx.cohort_label,
                "entries": ctx.cohort_entries,
                "size": len(ctx.cohort_entries),
            },
            "month_name": ctx.month_name,
            "rival_id": ctx.rival_id,
            "chasing_rival": ctx.chasing_rival,
            "summary": strategy_summary(ctx, strategy, risk),
        },
        "recommendations": lists["recommended"],
        "safe": lists["safe"],
        "aggressive": lists["aggressive"],
        "differentials": lists["differentials"],
        "sell_candidates": sells,
        "pairs": pairs,
        "why_not": why_not_notes(ranked, ctx, strategy),
        "compare_modes": compare,
        "ranked": ranked[:12],
        "warnings": ctx.warnings
        + (["Vi har tynt kampprogram-grunnlag for denne horisonten."] if not fx else []),
    }
