from __future__ import annotations

import math
import os
from statistics import median
from typing import Any

from api.engine import get_engine
from lro_analysis import nfloat, nint
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


class DeepFPLProjectionProvider:
    """A transparent projection model using the full useful FPL bootstrap signal.

    This is deliberately not labelled as proprietary xPts. It combines role,
    expected output, actual output, minutes, set-piece responsibility, form,
    transfer momentum and opponent strength. Event-level tactical matchup data
    from an external provider can be layered on top later without changing the
    transfer-strategy contract.
    """

    source = "fpl_deep_v1"

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

        selected = max(0.5, nfloat(player.get("selected_by_pct"), 0.5))
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
            "evidence": evidence[:6],
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
                "global_ownership_pct": round(selected, 1),
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


def _enrich_rows(rows: list[dict[str, Any]], provider: DeepFPLProjectionProvider) -> None:
    for row in rows or []:
        element = nint(row.get("element"))
        detail = provider.details.get(element) or {}
        row["projection_source"] = provider.source
        row["confidence"] = detail.get("confidence", "lav")
        row["deep_stats"] = detail.get("stats", {})
        specific = list(detail.get("evidence") or [])
        generic = [str(line) for line in row.get("why") or []]
        row["why"] = (specific + generic)[:7]
        row["evidence"] = specific
        row["data_sources"] = [
            "Fantasy Premier League bootstrap",
            "Fantasy Premier League fixtures",
            "Lofthus Road Open live ownership",
        ]


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
    provider = DeepFPLProjectionProvider(snap.bootstrap)
    body = build_transfer_strategy(
        state=snap.state,
        bootstrap=snap.bootstrap,
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
    for key in ("recommendations", "safe", "aggressive", "differentials", "ranked"):
        _enrich_rows(body.get(key) or [], provider)
    body["projection_source"] = provider.source
    body["coverage"] = {
        "fpl_native": True,
        "league_context": True,
        "fixture_strength": True,
        "set_piece_role": True,
        "event_level_situational_matchups": False,
        "external_provider_configured": bool(os.getenv("SPORTMONKS_API_TOKEN", "").strip()),
        "note": "Situasjonsspesifikk motstanderanalyse krever en ekstern event-datakilde. Modellen markerer dette eksplisitt i stedet for å gjette.",
    }
    return body
