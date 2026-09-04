from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from lro_analysis import nint
from lro_history import normalize_text
from lro_live import LiveState, ManagerLiveState


@dataclass(frozen=True)
class RivalPlayerEdge:
    element: int
    player: str
    my_multiplier: int
    rival_multiplier: int
    multiplier_edge: int
    event_points: int
    live_swing: int
    status: str


@dataclass(frozen=True)
class RivalDuel:
    me: ManagerLiveState
    rival: ManagerLiveState
    live_gap: int
    common_players: int
    my_unique: tuple[RivalPlayerEdge, ...]
    rival_unique: tuple[RivalPlayerEdge, ...]
    cheer_for: tuple[RivalPlayerEdge, ...]
    hope_blank: tuple[RivalPlayerEdge, ...]


def _pick_map(state: LiveState, entry: int) -> dict[int, dict[str, Any]]:
    picks = state.ownership.get("picks", pd.DataFrame())
    if picks is None or picks.empty:
        return {}
    block = picks[picks["entry"].map(nint) == int(entry)]
    out: dict[int, dict[str, Any]] = {}
    for r in block.to_dict("records"):
        # Only players currently contributing to the manager's score matter in
        # the head-to-head. Bench Boost is already represented by multiplier 1.
        element = nint(r.get("element"))
        if element:
            out[element] = r
    return out


def compare_managers(state: LiveState, my_entry: int, rival_entry: int) -> RivalDuel | None:
    me = state.manager(int(my_entry))
    rival = state.manager(int(rival_entry))
    if not me or not rival or me.entry == rival.entry:
        return None
    mine = _pick_map(state, me.entry)
    theirs = _pick_map(state, rival.entry)
    elements = sorted(set(mine) | set(theirs))
    edges: list[RivalPlayerEdge] = []
    common = 0
    for element in elements:
        a = mine.get(element, {})
        b = theirs.get(element, {})
        am = max(0, nint(a.get("multiplier")))
        bm = max(0, nint(b.get("multiplier")))
        if am == bm and am > 0:
            common += 1
            continue
        impact = state.player(element)
        player = str((a or b).get("player") or (impact.player if impact else f"Spiller {element}"))
        points = int(impact.event_points if impact else nint((a or b).get("event_points")))
        status = impact.fixture_status if impact else "not_started"
        edge = am - bm
        edges.append(RivalPlayerEdge(
            element=element,
            player=player,
            my_multiplier=am,
            rival_multiplier=bm,
            multiplier_edge=edge,
            event_points=points,
            live_swing=edge * points,
            status=status,
        ))
    my_unique = tuple(sorted((e for e in edges if e.multiplier_edge > 0), key=lambda e: (-abs(e.multiplier_edge), normalize_text(e.player))))
    rival_unique = tuple(sorted((e for e in edges if e.multiplier_edge < 0), key=lambda e: (-abs(e.multiplier_edge), normalize_text(e.player))))
    # Players still capable of changing the duel are the useful cheer/blank lists.
    cheer = tuple(e for e in my_unique if e.status != "finished")
    blank = tuple(e for e in rival_unique if e.status != "finished")
    return RivalDuel(
        me=me,
        rival=rival,
        live_gap=me.live_total_points - rival.live_total_points,
        common_players=common,
        my_unique=my_unique,
        rival_unique=rival_unique,
        cheer_for=cheer,
        hope_blank=blank,
    )


def auto_rivals(state: LiveState, entry: int, limit: int = 5) -> list[int]:
    me = state.manager(int(entry))
    if not me:
        return []
    ordered = state.managers_by_rank()
    index = next((i for i, m in enumerate(ordered) if m.entry == me.entry), None)
    if index is None:
        return []
    candidates: list[int] = []
    # Most useful order: immediate manager ahead, next two ahead, then two behind.
    for offset in (-1, -2, -3, 1, 2):
        i = index + offset
        if 0 <= i < len(ordered):
            eid = ordered[i].entry
            if eid != me.entry and eid not in candidates:
                candidates.append(eid)
    # A nearby month rival may matter even if league position is different.
    month = state.month_ranking()
    mi = next((i for i, m in enumerate(month) if m.entry == me.entry), None)
    if mi is not None:
        for offset in (-1, 1):
            i = mi + offset
            if 0 <= i < len(month):
                eid = month[i].entry
                if eid != me.entry and eid not in candidates:
                    candidates.append(eid)
    return candidates[: max(0, int(limit))]
