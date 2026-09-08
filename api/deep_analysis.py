from __future__ import annotations

import copy
import math
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median
from typing import Any

from api.engine import get_engine
from lro_analysis import manager_squad, nfloat, nint
from lro_transfer_strategy import build_transfer_strategy, clamp, fixture_quality


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _per90(value: float, minutes: float) -> float:
    return _safe_div(value * 90.0, minutes) if minutes > 0 else 0.0


def _norm(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return clamp((value - lo) / (hi - lo), 0.0, 1.0)


def _order(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if value in (None, ""):
        return 0
    return nint(value)


def _future_projection_bootstrap(bootstrap: dict[str, Any]) -> tuple[dict[str, Any], int | None]:
    """Make the transfer engine start at the next playable FPL event.

    The base engine historically starts its horizon at `current_event_id`. During
    a live or just-finished GW that can accidentally include a round whose
    deadline has already passed. Transfer advice must start with the next event.
    """
    out = copy.deepcopy(bootstrap or {})
    events = list(out.get("events") or [])
    if not events:
        return out, None

    next_event = next((e for e in events if e.get("is_next") and nint(e.get("id"))), None)
    if next_event is None:
        current_ids = [nint(e.get("id")) for e in events if e.get("is_current") and nint(e.get("id"))]
        finished_ids = [nint(e.get("id")) for e in events if e.get("finished") and nint(e.get("id"))]
        floor = max(current_ids or finished_ids or [0])
        future = [e for e in events if nint(e.get("id")) > floor]
        future.sort(key=lambda e: nint(e.get("id")))
        next_event = future[0] if future else next((e for e in events if e.get("is_current")), None)

    next_id = nint((next_event or {}).get("id")) or None
    if next_id:
        for event in events:
            event["is_current"] = nint(event.get("id")) == next_id
        out["events"] = events
    return out, next_id


class DeepFPLProjectionProvider:
    """Transparent projection model using the useful FPL bootstrap signal.

    It is intentionally not labelled as proprietary xPts. It combines expected
    output, actual output, minutes, role, set pieces, fixture strength, transfer
    momentum and league context. Event-level tactical matchup data can be layered
    on top when a licensed external feed is configured.
    """

    source = "fpl_deep_v2"

    def __init__(self, bootstrap: dict[str, Any]):
        self.bootstrap = bootstrap or {}
        self.details: dict[int, dict[str, Any]] = {}
        self.teams = {
            nint(team.get("id")): team
            for team in self.bootstrap.get("teams", []) or []
            if nint(team.get("id"))
        }
        defence_values: list[float] = []
        attack_values: list[float] = []
        for team in self.teams.values():
            defence_values.extend([
                nfloat(team.get("strength_defence_home")),
                nfloat(team.get("strength_defence_away")),
            ])
            attack_values.extend([
                nfloat(team.get("strength_attack_home")),
                nfloat(team.get("strength_attack_away")),
            ])
        defence_values = [x for x in defence_values if x > 0]
        attack_values = [x for x in attack_values if x > 0]
        self.def_lo = min(defence_values) if defence_values else 900.0
        self.def_hi = max(defence_values) if defence_values else 1500.0
        self.att_lo = min(attack_values) if attack_values else 900.0
        self.att_hi = max(attack_values) if attack_values else 1500.0
        self.def_median = median(defence_values) if defence_values else 1200.0

    def _fixture_profile(self, fixture_rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
        rows = list(fixture_rows or [])[: max(1, horizon)]
        if not rows:
            return {
                "fixture": 0.45,
                "attack_matchup": 0.5,
                "clean_sheet_matchup": 0.5,
                "weak_defences": 0,
                "fixture_count": 0,
            }
        weights = [1.0, 0.78, 0.61, 0.48, 0.38]
        attack_total = 0.0
        clean_total = 0.0
        weight_total = 0.0
        weak = 0
        for i, row in enumerate(rows):
            w = weights[i] if i < len(weights) else 0.3
            opp = self.teams.get(nint(row.get("opponent_id")), {})
            player_home = bool(row.get("home"))
            opp_def = nfloat(opp.get("strength_defence_away" if player_home else "strength_defence_home"), self.def_median)
            opp_att = nfloat(opp.get("strength_attack_away" if player_home else "strength_attack_home"), (self.att_lo + self.att_hi) / 2.0)
            defence_weakness = 1.0 - _norm(opp_def, self.def_lo, self.def_hi)
            attack_weakness = 1.0 - _norm(opp_att, self.att_lo, self.att_hi)
            attack_total += w * defence_weakness
            clean_total += w * attack_weakness
            weight_total += w
            if opp_def and opp_def <= self.def_median:
                weak += 1
        fdr = fixture_quality(rows, horizon)
        attack_matchup = attack_total / weight_total if weight_total else 0.5
        clean_matchup = clean_total / weight_total if weight_total else 0.5
        return {
            "fixture": clamp(0.48 * fdr + 0.52 * attack_matchup, 0.0, 1.0),
            "attack_matchup": clamp(attack_matchup, 0.0, 1.0),
            "clean_sheet_matchup": clamp(clean_matchup, 0.0, 1.0),
            "weak_defences": weak,
            "fixture_count": len(rows),
        }

    def score(self, player: dict[str, Any], fixture_rows: list[dict[str, Any]], horizon: int) -> dict[str, Any]:
        raw = player.get("raw") if isinstance(player.get("raw"), dict) else {}
        element = nint(player.get("element_id") or player.get("id"))
        position = nint(player.get("position_id"))
        minutes = nfloat(player.get("minutes"))
        starts = nfloat(player.get("starts"))
        appearances = max(starts, minutes / 80.0, 1.0)
        start_rate = clamp(starts / appearances if starts else minutes / max(appearances * 80.0, 1.0), 0.0, 1.0)
        minutes_rate = clamp(minutes / max(appearances * 90.0, 1.0), 0.0, 1.0)
        minutes_score = clamp(0.68 * start_rate + 0.32 * minutes_rate, 0.0, 1.0)

        xg90 = nfloat(raw.get("expected_goals_per_90"), _per90(nfloat(player.get("xg")), minutes))
        xa90 = nfloat(raw.get("expected_assists_per_90"), _per90(nfloat(player.get("xa")), minutes))
        xgi90 = nfloat(raw.get("expected_goal_involvements_per_90"), xg90 + xa90)
        gi90 = _per90(nfloat(player.get("goals_scored")) + nfloat(player.get("assists")), minutes)
        ppg = nfloat(player.get("points_per_game"))
        form = nfloat(player.get("form"))
        threat = nfloat(player.get("threat"))
        creativity = nfloat(player.get("creativity"))
        influence = nfloat(player.get("influence"))
        ict = nfloat(player.get("ict_index"))
        total_points = nfloat(player.get("total_points"))

        xgi_signal = clamp(xgi90 / 0.85, 0.0, 1.0)
        output_signal = clamp(gi90 / 0.85, 0.0, 1.0)
        ppg_signal = clamp(ppg / 8.0, 0.0, 1.0)
        form_signal = clamp(form / 9.0, 0.0, 1.0)
        threat_signal = clamp(threat / 500.0, 0.0, 1.0)
        creativity_signal = clamp(creativity / 500.0, 0.0, 1.0)
        influence_signal = clamp(influence / 500.0, 0.0, 1.0)
        ict_signal = clamp(ict / 300.0, 0.0, 1.0)
        season_signal = clamp(_safe_div(total_points, max(1.0, appearances)) / 8.0, 0.0, 1.0)

        penalties = _order(raw, "penalties_order")
        direct_fk = _order(raw, "direct_freekicks_order")
        corners_fk = _order(raw, "corners_and_indirect_freekicks_order")
        set_piece_score = 0.0
        if penalties == 1:
            set_piece_score += 0.22
        elif penalties == 2:
            set_piece_score += 0.10
        if direct_fk == 1:
            set_piece_score += 0.08
        elif direct_fk == 2:
            set_piece_score += 0.04
        if corners_fk == 1:
            set_piece_score += 0.10
        elif corners_fk == 2:
            set_piece_score += 0.05
        set_piece_score = clamp(set_piece_score, 0.0, 0.35)

        transfers_in = nfloat(player.get("transfers_in_event"))
        transfers_out = nfloat(player.get("transfers_out_event"))
        momentum_raw = math.tanh((transfers_in - transfers_out) / 200000.0)
        momentum = clamp(0.5 + 0.5 * momentum_raw, 0.0, 1.0)

        fx = self._fixture_profile(fixture_rows, horizon)
        attacking_role = clamp(
            0.31 * xgi_signal
            + 0.13 * output_signal
            + 0.12 * ppg_signal
            + 0.10 * form_signal
            + 0.10 * threat_signal
            + 0.08 * creativity_signal
            + 0.06 * influence_signal
            + 0.05 * ict_signal
            + 0.05 * season_signal
            + set_piece_score,
            0.0,
            1.0,
        )

        if position == 1:
            saves90 = _per90(nfloat(player.get("saves")), minutes)
            keeper_skill = clamp(0.58 * fx["clean_sheet_matchup"] + 0.22 * clamp(saves90 / 5.0, 0.0, 1.0) + 0.20 * ppg_signal, 0.0, 1.0)
            projection = clamp(0.49 * keeper_skill + 0.31 * minutes_score + 0.20 * fx["fixture"], 0.0, 1.0)
        elif position == 2:
            projection = clamp(0.38 * attacking_role + 0.25 * fx["clean_sheet_matchup"] + 0.22 * minutes_score + 0.12 * fx["fixture"] + 0.03 * momentum, 0.0, 1.0)
        else:
            projection = clamp(0.54 * attacking_role + 0.22 * fx["fixture"] + 0.18 * minutes_score + 0.06 * momentum, 0.0, 1.0)

        evidence: list[str] = []
        if minutes >= 90:
            evidence.append(f"{xgi90:.2f} xGI per 90 over {int(minutes)} minutter")
        evidence.append(f"Form {form:.1f} og {ppg:.1f} poeng per kamp")
        if starts > 0:
            evidence.append(f"{int(starts)} starter, beregnet spilletidssikkerhet {round(minutes_score * 100):d} %")
        if penalties == 1:
            evidence.append("Førstevalg på straffer")
        elif corners_fk == 1 or direct_fk == 1:
            evidence.append("Førstevalg på minst én dødballtype")
        if fx["fixture_count"]:
            evidence.append(f"{fx['weak_defences']} av de neste {fx['fixture_count']} motstanderne har defensiv FPL-rating på eller under ligamedianen")
        if transfers_in or transfers_out:
            net = int(transfers_in - transfers_out)
            evidence.append(f"Netto transfers denne runden: {net:+d}")

        confidence = "høy" if minutes >= 540 and starts >= 6 and fx["fixture_count"] >= min(3, horizon) else "middels" if minutes >= 180 else "lav"
        self.details[element] = {
            "confidence": confidence,
            "evidence": evidence[:7],
            "stats": {
                "xg_per90": round(xg90, 3),
                "xa_per90": round(xa90, 3),
                "xgi_per90": round(xgi90, 3),
                "goal_involvements_per90": round(gi90, 3),
                "form": round(form, 2),
                "points_per_game": round(ppg, 2),
                "minutes": int(minutes),
                "starts": int(starts),
                "threat": round(threat, 1),
                "creativity": round(creativity, 1),
                "influence": round(influence, 1),
                "ict": round(ict, 1),
                "global_ownership_pct": round(nfloat(player.get("selected_by_pct")), 1),
                "next_fixture_count": fx["fixture_count"],
                "weaker_defence_fixtures": fx["weak_defences"],
                "attack_matchup": round(fx["attack_matchup"], 3),
                "clean_sheet_matchup": round(fx["clean_sheet_matchup"], 3),
                "penalties_order": penalties or None,
                "direct_freekicks_order": direct_fk or None,
                "corners_indirect_freekicks_order": corners_fk or None,
            },
        }
        return {
            "source": self.source,
            "projection": projection,
            "minutes": minutes_score,
            "form": form_signal,
            "fixture": fx["fixture"],
            "index_10": round(projection * 10.0, 1),
        }


def _recent_summary(payload: dict[str, Any], position_id: int) -> dict[str, Any]:
    history = list((payload or {}).get("history") or [])
    if not history:
        return {}
    history.sort(key=lambda row: (nint(row.get("round")), str(row.get("kickoff_time") or "")))
    rows = history[-5:]
    minutes = sum(nfloat(row.get("minutes")) for row in rows)
    apps = len(rows)
    xg = sum(nfloat(row.get("expected_goals")) for row in rows)
    xa = sum(nfloat(row.get("expected_assists")) for row in rows)
    xgi = sum(nfloat(row.get("expected_goal_involvements"), nfloat(row.get("expected_goals")) + nfloat(row.get("expected_assists"))) for row in rows)
    points = sum(nfloat(row.get("total_points")) for row in rows)
    goals = sum(nfloat(row.get("goals_scored")) for row in rows)
    assists = sum(nfloat(row.get("assists")) for row in rows)
    bonus = sum(nfloat(row.get("bonus")) for row in rows)
    clean_sheets = sum(nfloat(row.get("clean_sheets")) for row in rows)
    saves = sum(nfloat(row.get("saves")) for row in rows)
    xgc = sum(nfloat(row.get("expected_goals_conceded")) for row in rows)

    xgi90 = _per90(xgi, minutes)
    gi90 = _per90(goals + assists, minutes)
    ppg = _safe_div(points, apps)
    avg_minutes = _safe_div(minutes, apps)
    clean_rate = _safe_div(clean_sheets, apps)
    saves90 = _per90(saves, minutes)
    xgc90 = _per90(xgc, minutes)

    minutes_signal = clamp(avg_minutes / 90.0, 0.0, 1.0)
    points_signal = clamp(ppg / 8.0, 0.0, 1.0)
    xgi_signal = clamp(xgi90 / 0.85, 0.0, 1.0)
    bonus_signal = clamp(_safe_div(bonus, apps) / 2.0, 0.0, 1.0)
    if position_id == 1:
        recent_score = 10.0 * clamp(0.38 * points_signal + 0.28 * minutes_signal + 0.20 * clamp(saves90 / 5.0, 0.0, 1.0) + 0.14 * clean_rate, 0.0, 1.0)
    elif position_id == 2:
        defensive_signal = clamp(0.55 * clean_rate + 0.45 * (1.0 - clamp(xgc90 / 2.0, 0.0, 1.0)), 0.0, 1.0)
        recent_score = 10.0 * clamp(0.29 * xgi_signal + 0.27 * points_signal + 0.23 * minutes_signal + 0.16 * defensive_signal + 0.05 * bonus_signal, 0.0, 1.0)
    else:
        recent_score = 10.0 * clamp(0.45 * xgi_signal + 0.26 * points_signal + 0.19 * minutes_signal + 0.06 * clamp(gi90 / 0.85, 0.0, 1.0) + 0.04 * bonus_signal, 0.0, 1.0)

    return {
        "matches": apps,
        "minutes": int(minutes),
        "avg_minutes": round(avg_minutes, 1),
        "xg_per90": round(_per90(xg, minutes), 3),
        "xa_per90": round(_per90(xa, minutes), 3),
        "xgi_per90": round(xgi90, 3),
        "goal_involvements_per90": round(gi90, 3),
        "points_per_match": round(ppg, 2),
        "clean_sheet_rate": round(clean_rate, 3),
        "saves_per90": round(saves90, 2),
        "expected_goals_conceded_per90": round(xgc90, 3),
        "score_10": round(recent_score, 2),
    }


def _fetch_recent_summaries(client: Any, rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    elements = [nint(row.get("element")) for row in rows if nint(row.get("element"))]
    elements = list(dict.fromkeys(elements))[:12]
    if not elements:
        return {}

    out: dict[int, dict[str, Any]] = {}

    def fetch(element: int) -> tuple[int, dict[str, Any]]:
        payload = client.get_json(f"/element-summary/{element}/", ttl=600, stale_if_error=7200)
        return element, payload if isinstance(payload, dict) else {}

    with ThreadPoolExecutor(max_workers=min(6, len(elements))) as pool:
        futures = {pool.submit(fetch, element): element for element in elements}
        for future in as_completed(futures):
            element = futures[future]
            try:
                _, payload = future.result()
                out[element] = payload
            except Exception:
                out[element] = {}
    return out


def _rerank_with_recent(rows: list[dict[str, Any]], recent_payloads: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        recent = _recent_summary(recent_payloads.get(nint(row.get("element"))) or {}, nint(row.get("position_id")))
        if recent:
            sample = min(5, nint(recent.get("matches")))
            weight = min(0.18, 0.035 * sample)
            old = nfloat(row.get("strategy_score"))
            row["strategy_score"] = round((1.0 - weight) * old + weight * nfloat(recent.get("score_10")), 1)
            row.setdefault("deep_stats", {})["recent_5"] = recent
            evidence = list(row.get("evidence") or [])
            evidence.insert(
                0,
                f"Siste {sample} kamper: {nfloat(recent.get('xgi_per90')):.2f} xGI/90, {nfloat(recent.get('points_per_match')):.1f} poeng per kamp og {nfloat(recent.get('avg_minutes')):.0f} min i snitt",
            )
            row["evidence"] = evidence[:8]
            row["why"] = (evidence + [str(line) for line in row.get("why") or []])[:8]
        out.append(row)
    out.sort(key=lambda row: (-nfloat(row.get("strategy_score")), -nfloat(row.get("projection_index")), str(row.get("player") or "")))
    return out


def _squad_rows(state: Any, entry_id: int) -> list[dict[str, Any]]:
    squad = manager_squad(state.ownership, int(entry_id))
    if squad is None or getattr(squad, "empty", True):
        return []
    return list(squad.to_dict("records"))


def _transfer_feasibility(candidate: dict[str, Any], squad: list[dict[str, Any]], bank: float | None) -> dict[str, Any]:
    buy_team = nint(candidate.get("team_id"))
    position = nint(candidate.get("position_id"))
    buy_price = nfloat(candidate.get("price"), 999.0)
    club_counts = Counter(nint(row.get("team_id")) for row in squad if nint(row.get("team_id")))
    same_position = [row for row in squad if nint(row.get("position_id")) == position]
    legal: list[dict[str, Any]] = []
    budget_unknown = False

    for outgoing in same_position:
        out_team = nint(outgoing.get("team_id"))
        post_count = club_counts.get(buy_team, 0) + 1 - (1 if out_team == buy_team else 0)
        if post_count > 3:
            continue
        selling = outgoing.get("selling_price")
        if bank is None or selling in (None, ""):
            budget_unknown = True
            legal.append(outgoing)
            continue
        if nfloat(bank) + nfloat(selling) + 0.05 >= buy_price:
            legal.append(outgoing)

    if not legal:
        return {
            "legal": False,
            "budget_verified": not budget_unknown,
            "out_candidates": [],
            "reason": "Ingen lovlig ett-bytte-løsning med dagens klubbgrense og budsjett.",
        }

    return {
        "legal": True,
        "budget_verified": not budget_unknown,
        "out_candidates": [
            {
                "element": nint(row.get("element")),
                "player": str(row.get("player") or ""),
                "selling_price": row.get("selling_price"),
            }
            for row in legal[:4]
        ],
        "reason": "Minst én lovlig ett-bytte-løsning er funnet." if not budget_unknown else "Klubbgrensen er kontrollert. Budsjettet må bekreftes for minst ett mulig bytte.",
    }


def _enrich_rows(rows: list[dict[str, Any]], provider: DeepFPLProjectionProvider) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for source in rows or []:
        row = dict(source)
        element = nint(row.get("element"))
        detail = provider.details.get(element) or {}
        row["projection_source"] = provider.source
        row["confidence"] = detail.get("confidence", "lav")
        row["deep_stats"] = detail.get("stats", {})
        specific = list(detail.get("evidence") or [])
        generic = [str(line) for line in row.get("why") or []]
        row["why"] = (specific + generic)[:8]
        row["evidence"] = specific
        row["data_sources"] = [
            "Fantasy Premier League bootstrap",
            "Fantasy Premier League fixtures",
            "Fantasy Premier League element history",
            "Lofthus Road Open live ownership",
        ]
        out.append(row)
    return out


def build_deep_transfer_analysis(
    *,
    entry_id: int,
    strategy: str,
    risk: int,
    horizon: int,
    target: str = "",
    rival_id: int = 0,
    position: str = "all",
) -> dict[str, Any]:
    eng = get_engine()
    snap = eng.snapshot()
    if not snap.state:
        return {"ok": False, "error": "Live-data er ikke klare ennå."}
    try:
        fixtures = list(eng.client.fixtures() or [])
    except Exception:
        fixtures = list(snap.state.fixtures or [])

    projection_bootstrap, first_event_id = _future_projection_bootstrap(snap.bootstrap)
    provider = DeepFPLProjectionProvider(snap.bootstrap)
    body = build_transfer_strategy(
        state=snap.state,
        bootstrap=projection_bootstrap,
        fixtures=fixtures,
        entry_id=int(entry_id),
        strategy=strategy,
        risk=int(risk),
        horizon=int(horizon),
        target=target,
        rival_id=int(rival_id or 0),
        position=position,
        provider=provider,
    )
    if not body.get("ok"):
        return body

    base_ranked = _enrich_rows(list(body.get("ranked") or []), provider)
    recent_payloads = _fetch_recent_summaries(eng.client, base_ranked)
    ranked = _rerank_with_recent(base_ranked, recent_payloads)

    squad = _squad_rows(snap.state, int(entry_id))
    bank_raw = (body.get("manager") or {}).get("bank")
    bank = None if bank_raw in (None, "") else nfloat(bank_raw)
    legal_ranked: list[dict[str, Any]] = []
    for row in ranked:
        feasibility = _transfer_feasibility(row, squad, bank)
        row["transfer_feasibility"] = feasibility
        if feasibility.get("legal"):
            legal_ranked.append(row)

    body["ranked"] = legal_ranked[:12]
    body["recommendations"] = legal_ranked[:5]

    for key in ("safe", "aggressive", "differentials"):
        enriched = _enrich_rows(list(body.get(key) or []), provider)
        kept = []
        for row in enriched:
            feasibility = _transfer_feasibility(row, squad, bank)
            row["transfer_feasibility"] = feasibility
            if feasibility.get("legal"):
                kept.append(row)
        body[key] = kept[:3]

    body["projection_source"] = provider.source
    body["analysis_horizon"] = {
        "matches": int(horizon),
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
        "external_provider_configured": bool(os.getenv("SPORTMONKS_API_TOKEN", "").strip()),
        "note": "Situasjonsspesifikk motstanderanalyse krever en ekstern event-datakilde. Modellen markerer dette eksplisitt i stedet for å gjette.",
    }
    return body
