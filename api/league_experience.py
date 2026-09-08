from __future__ import annotations

from collections import Counter
from typing import Any

from api.engine import get_engine
from api.league_intelligence import build_league_intelligence
from lro_analysis import nint


def _pick_rows(state: Any) -> list[dict[str, Any]]:
    picks = (state.ownership or {}).get("picks")
    if picks is None:
        return []
    if hasattr(picks, "to_dict"):
        return [] if getattr(picks, "empty", True) else list(picks.to_dict("records"))
    return list(picks or [])


def _phase(state: Any) -> str:
    if state.is_finished:
        return "verdict"
    if state.is_live:
        return "live"
    if state.event_status == "between_matches":
        any_started = any(
            bool(row.get("started"))
            or bool(row.get("finished"))
            or bool(row.get("finished_provisional"))
            or nint(row.get("minutes")) > 0
            for row in (state.fixtures or [])
        )
        return "live" if any_started else "reveal"
    return "plan"


def _reveal(state: Any, entry_id: int, target_entries: list[int]) -> dict[str, Any]:
    me = state.manager(int(entry_id))
    if not me:
        return {}
    targets = [state.manager(int(entry)) for entry in target_entries]
    targets = [row for row in targets if row]
    if not targets:
        ranked = state.managers_by_rank()
        targets = [row for row in ranked if row.entry != int(entry_id)][:5]

    captain_counts = Counter(str(row.captain or "").replace(" (C)", "").replace(" (TC)", "") for row in targets if row.captain)
    target_captains = [
        {"player": player, "count": count, "pct": round(100.0 * count / max(1, len(targets)), 1)}
        for player, count in captain_counts.most_common(6)
    ]

    chips = [
        {"entry": row.entry, "manager": row.manager, "chip": row.active_chip}
        for row in targets
        if str(row.active_chip or "").strip()
    ]
    hit_rows = [
        {"entry": row.entry, "manager": row.manager, "cost": nint(row.transfer_hits)}
        for row in targets
        if nint(row.transfer_hits) > 0
    ]

    picks = _pick_rows(state)
    own_active = {
        nint(row.get("element"))
        for row in picks
        if nint(row.get("entry")) == int(entry_id) and nint(row.get("multiplier")) > 0
    }
    target_active: Counter[int] = Counter()
    player_names: dict[int, str] = {}
    for row in picks:
        element = nint(row.get("element"))
        if not element:
            continue
        player_names[element] = str(row.get("player") or "")
        if nint(row.get("entry")) in {target.entry for target in targets} and nint(row.get("multiplier")) > 0:
            target_active[element] += 1

    my_differentials = [
        {
            "element": element,
            "player": player_names.get(element, f"Spiller {element}"),
            "target_owners": target_active.get(element, 0),
            "target_pct": round(100.0 * target_active.get(element, 0) / max(1, len(targets)), 1),
        }
        for element in own_active
        if target_active.get(element, 0) < max(1, len(targets) // 2)
    ]
    my_differentials.sort(key=lambda row: (row["target_owners"], row["player"]))

    danger = [
        {
            "element": element,
            "player": player_names.get(element, f"Spiller {element}"),
            "target_owners": count,
            "target_pct": round(100.0 * count / max(1, len(targets)), 1),
        }
        for element, count in target_active.items()
        if element not in own_active
    ]
    danger.sort(key=lambda row: (-row["target_owners"], row["player"]))

    return {
        "my_captain": me.captain,
        "my_chip": me.active_chip or "",
        "my_hits": nint(me.transfer_hits),
        "target_size": len(targets),
        "target_managers": [
            {
                "entry": row.entry,
                "manager": row.manager,
                "rank": row.live_rank,
                "captain": row.captain,
                "chip": row.active_chip or "",
                "hits": nint(row.transfer_hits),
            }
            for row in targets
        ],
        "target_captains": target_captains,
        "chips": chips,
        "hits": hit_rows,
        "my_differentials": my_differentials[:6],
        "danger": danger[:6],
    }


def build_league_experience(entry_id: int, goal: str = "auto") -> dict[str, Any]:
    body = build_league_intelligence(entry_id=entry_id, goal=goal)
    if not body.get("ok"):
        return body

    eng = get_engine()
    snap = eng.snapshot()
    if not snap.state:
        return body

    state = snap.state
    target_entries = list((body.get("battle") or {}).get("target_entries") or [])
    body["phase"] = _phase(state)
    body["reveal"] = _reveal(state, int(entry_id), target_entries)
    return body
