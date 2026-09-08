from __future__ import annotations

from collections import Counter
from typing import Any

from api.engine import AppEngine, get_engine
from api.league_intelligence_v2 import build_league_intelligence_v2
from api.league_journal import league_journal
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


def _target_managers(state: Any, entry_id: int, target_entries: list[int]) -> list[Any]:
    targets = [state.manager(int(entry)) for entry in target_entries]
    targets = [row for row in targets if row is not None and row.entry != int(entry_id)]
    if targets:
        return targets
    me = state.manager(int(entry_id))
    if not me:
        return []
    ranked = state.managers_by_rank()
    if me.live_rank == 1:
        return [row for row in ranked if row.entry != me.entry][:5]
    ahead = [row for row in ranked if row.live_rank < me.live_rank]
    return sorted(ahead, key=lambda row: row.live_rank, reverse=True)[:5]


def _reveal(state: Any, entry_id: int, target_entries: list[int]) -> dict[str, Any]:
    me = state.manager(int(entry_id))
    if not me:
        return {}
    targets = _target_managers(state, entry_id, target_entries)
    target_ids = {row.entry for row in targets}
    target_size = max(1, len(targets))

    captain_counts = Counter(
        str(row.original_captain or row.captain or "").replace(" (C)", "").replace(" (TC)", "")
        for row in targets
        if row.original_captain or row.captain
    )
    target_captains = [
        {"player": player, "count": count, "pct": round(100.0 * count / target_size, 1)}
        for player, count in captain_counts.most_common(8)
    ]

    picks = _pick_rows(state)
    own_rows = [row for row in picks if nint(row.get("entry")) == int(entry_id)]
    own_active = {nint(row.get("element")) for row in own_rows if nint(row.get("multiplier")) > 0}
    own_all = {nint(row.get("element")) for row in own_rows if nint(row.get("element"))}
    target_active: Counter[int] = Counter()
    player_names: dict[int, str] = {}
    for row in picks:
        element = nint(row.get("element"))
        if not element:
            continue
        player_names[element] = str(row.get("player") or f"Spiller {element}")
        if nint(row.get("entry")) in target_ids and nint(row.get("multiplier")) > 0:
            target_active[element] += 1

    my_differentials = [
        {
            "element": element,
            "player": player_names.get(element, f"Spiller {element}"),
            "target_owners": target_active.get(element, 0),
            "target_pct": round(100.0 * target_active.get(element, 0) / target_size, 1),
        }
        for element in own_active
        if target_active.get(element, 0) < max(1, (len(targets) + 1) // 2)
    ]
    my_differentials.sort(key=lambda row: (row["target_owners"], row["player"]))

    danger = [
        {
            "element": element,
            "player": player_names.get(element, f"Spiller {element}"),
            "target_owners": count,
            "target_pct": round(100.0 * count / target_size, 1),
        }
        for element, count in target_active.items()
        if element not in own_active
    ]
    danger.sort(key=lambda row: (-row["target_owners"], row["player"]))

    clone_scores: list[dict[str, Any]] = []
    for target in targets:
        theirs = {
            nint(row.get("element"))
            for row in picks
            if nint(row.get("entry")) == target.entry and nint(row.get("element"))
        }
        overlap = len(own_all & theirs)
        clone_scores.append(
            {
                "entry": target.entry,
                "manager": target.manager,
                "shared_players": overlap,
                "squad_similarity_pct": round(100.0 * overlap / 15.0, 1),
            }
        )
    clone_scores.sort(key=lambda row: (-row["shared_players"], row["manager"]))

    return {
        "my_captain": me.original_captain or me.captain,
        "my_chip": me.active_chip or "",
        "my_hits": nint(me.transfer_hits),
        "target_size": len(targets),
        "target_managers": [
            {
                "entry": row.entry,
                "manager": row.manager,
                "rank": row.live_rank,
                "captain": row.original_captain or row.captain,
                "chip": row.active_chip or "",
                "hits": nint(row.transfer_hits),
            }
            for row in targets
        ],
        "target_captains": target_captains,
        "chips": [
            {"entry": row.entry, "manager": row.manager, "chip": row.active_chip}
            for row in targets
            if str(row.active_chip or "").strip()
        ],
        "hits": [
            {"entry": row.entry, "manager": row.manager, "cost": nint(row.transfer_hits)}
            for row in targets
            if nint(row.transfer_hits) > 0
        ],
        "my_differentials": my_differentials[:8],
        "danger": danger[:8],
        "closest_clone": clone_scores[0] if clone_scores else None,
        "clone_scores": clone_scores[:5],
    }


def build_league_experience_v2(
    *,
    entry_id: int,
    goal: str = "auto",
    engine: AppEngine | None = None,
) -> dict[str, Any]:
    eng = engine or get_engine()
    body = build_league_intelligence_v2(entry_id=entry_id, goal=goal, engine=eng)
    if not body.get("ok"):
        return body
    snap = eng.snapshot()
    if not snap.state:
        return body

    target_entries = list((body.get("battle") or {}).get("target_entries") or [])
    phase = _phase(snap.state)
    body["phase"] = phase
    body["reveal"] = _reveal(snap.state, int(entry_id), target_entries)
    body["experience_version"] = "league-loop-v2"

    # Keep a compact season memory. The reveal row is first-write-wins, so the
    # first post-deadline view is preserved instead of being rewritten later.
    if phase in {"reveal", "live"}:
        league_journal.record(eng, snap.state, "reveal")
    if phase == "verdict":
        league_journal.record(eng, snap.state, "verdict")
    body["journal"] = league_journal.diagnostics()
    return body
