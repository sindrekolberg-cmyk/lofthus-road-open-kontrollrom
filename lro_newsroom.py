from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from lro_analysis import nint
from lro_history import HistoryStore, normalize_text
from lro_live import LiveState


@dataclass(frozen=True)
class Story:
    key: str
    category: str
    headline: str
    meta: str
    importance: int
    freshness: int
    status: str
    confidence: int
    created_at: datetime
    expires_at: datetime
    source_event: int = 0
    manager_entry: int = 0
    player_element: int = 0
    supersedes: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["created_at"] = self.created_at.isoformat()
        out["expires_at"] = self.expires_at.isoformat()
        return out

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Story" | None:
        try:
            return cls(
                key=str(row.get("key") or ""),
                category=str(row.get("category") or ""),
                headline=str(row.get("headline") or ""),
                meta=str(row.get("meta") or ""),
                importance=int(row.get("importance") or 0),
                freshness=int(row.get("freshness") or 0),
                status=str(row.get("status") or ""),
                confidence=int(row.get("confidence") or 0),
                created_at=datetime.fromisoformat(str(row.get("created_at"))),
                expires_at=datetime.fromisoformat(str(row.get("expires_at"))),
                source_event=int(row.get("source_event") or 0),
                manager_entry=int(row.get("manager_entry") or 0),
                player_element=int(row.get("player_element") or 0),
                supersedes=str(row.get("supersedes") or ""),
            )
        except Exception:
            return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _story(
    key: str,
    category: str,
    headline: str,
    meta: str,
    importance: int,
    status: str,
    ttl_minutes: int,
    *,
    confidence: int = 100,
    source_event: int = 0,
    manager_entry: int = 0,
    player_element: int = 0,
    freshness: int = 100,
    supersedes: str = "",
) -> Story:
    now = _now()
    return Story(
        key=key,
        category=category,
        headline=headline,
        meta=meta,
        importance=max(0, min(100, int(importance))),
        freshness=max(0, min(100, int(freshness))),
        status=status,
        confidence=max(0, min(100, int(confidence))),
        created_at=now,
        expires_at=now + timedelta(minutes=max(1, int(ttl_minutes))),
        source_event=int(source_event),
        manager_entry=int(manager_entry),
        player_element=int(player_element),
        supersedes=supersedes,
    )


def completed_round_summary(managers: list[dict], histories: dict[int, dict] | None, event: int, history: HistoryStore) -> dict[str, Any]:
    """Reconstruct a finished LRO round from source-backed FPL entry history."""
    histories = histories or {}
    if not event or not histories:
        return {}
    names = {nint(m.get("entry")): history.canonical(str(m.get("player_name") or "")) for m in managers}
    teams = {nint(m.get("entry")): str(m.get("entry_name") or "") for m in managers}
    rows: list[dict[str, Any]] = []
    for entry, payload in histories.items():
        current = payload.get("current", []) or []
        row = next((r for r in current if nint(r.get("event")) == int(event)), None)
        if not row:
            continue
        points = nint(row.get("points"))
        total = nint(row.get("total_points"))
        rows.append({
            "entry": int(entry),
            "manager": names.get(int(entry), str(entry)),
            "team": teams.get(int(entry), ""),
            "gw": points,
            "total": total,
            "before": total - points,
        })
    if not rows:
        return {}
    after = {r["entry"]: 1 + sum(1 for x in rows if x["total"] > r["total"]) for r in rows}
    before = {r["entry"]: 1 + sum(1 for x in rows if x["before"] > r["before"]) for r in rows}
    for r in rows:
        r["rank"] = after[r["entry"]]
        r["last_rank"] = before[r["entry"]]
        r["move"] = before[r["entry"]] - after[r["entry"]]
    return {
        "event": int(event),
        "rows": rows,
        "gw_winner": sorted(rows, key=lambda r: (-r["gw"], r["rank"], normalize_text(r["manager"])))[0],
        "best_climber": sorted(rows, key=lambda r: (-r["move"], -r["gw"], normalize_text(r["manager"])))[0],
        "biggest_fall": sorted(rows, key=lambda r: (r["move"], -r["gw"], normalize_text(r["manager"])))[0],
    }


def _finished_event(bootstrap: dict) -> int:
    finished = [nint(e.get("id")) for e in bootstrap.get("events", []) or [] if e.get("finished") and nint(e.get("id"))]
    return max(finished) if finished else 0


def generate_candidates(
    state: LiveState,
    managers: list[dict],
    bootstrap: dict,
    history: HistoryStore,
    histories: dict[int, dict] | None = None,
) -> list[Story]:
    candidates: list[Story] = []

    # A live leader change is major news. The language explicitly remains provisional.
    top = state.top(1)
    if top:
        leader = top[0]
        if state.is_live and leader.previous_rank and leader.previous_rank != 1:
            candidates.append(_story(
                f"live-leader-{state.event_id}-{leader.entry}", "leader",
                f"{leader.manager} har tatt over tabelltoppen live",
                f"{leader.live_total_points} poeng · foreløpig opp {max(0, leader.live_rank_change)} plasser",
                97, "live", 45, source_event=state.event_id, manager_entry=leader.entry,
            ))

    # The player with the biggest real live effect. No unplayed zero can enter here.
    if state.is_live:
        live_impacts = [p for p in state.player_impacts if p.fixture_status == "live" and p.event_points != 0]
        if live_impacts:
            p = live_impacts[0]
            if p.event_points >= 8 or p.captain_count or p.triple_captain_count:
                imp = 94 if p.event_points >= 10 else 84
                caps = p.captain_count
                cap_text = f" · {caps} kaptein" if caps == 1 else f" · {caps} kapteiner" if caps else ""
                candidates.append(_story(
                    f"live-player-{state.event_id}-{p.element}", "live",
                    f"{p.player} herjer: {p.event_points} poeng live",
                    f"{p.ownership_count} eiere{cap_text}", imp, "live", 25,
                    source_event=state.event_id, player_element=p.element,
                ))

    # Extreme provisional movement is valid live, but the verb must stay provisional.
    if state.is_live and state.manager_live:
        mover = max(state.manager_live, key=lambda m: abs(m.live_rank_change))
        magnitude = abs(mover.live_rank_change)
        if magnitude >= 10:
            direction = f"opp {magnitude}" if mover.live_rank_change > 0 else f"ned {magnitude}"
            candidates.append(_story(
                f"live-move-{state.event_id}-{mover.entry}", "movement_live",
                f"{mover.manager} er foreløpig {direction} plasser",
                f"GW{state.event_id}: {mover.live_gw_points} poeng live", min(91, 72 + magnitude), "live", 35,
                source_event=state.event_id, manager_entry=mover.entry,
            ))

    # Triple Captain is only judged after the captain's fixture is finished.
    picks = state.ownership.get("picks", pd.DataFrame())
    if picks is not None and not picks.empty and "is_triple_captain" in picks.columns:
        tc = picks[picks["is_triple_captain"].astype(bool)]
        for row in tc.to_dict("records"):
            impact = state.player(nint(row.get("element")))
            if not impact or impact.fixture_status != "finished":
                continue
            raw_points = nint(row.get("event_points"))
            manager = str(row.get("manager") or "")
            if raw_points <= 2:
                importance = 98 if raw_points == 0 else 91
                headline = f"Triple Captain-smell for {manager}"
                meta = f"{row.get('player')} endte på {raw_points} poeng før trippelen"
            elif raw_points >= 12:
                importance = 88
                headline = f"Triple Captain-fulltreffer for {manager}"
                meta = f"{row.get('player')} leverte {raw_points} poeng før trippelen"
            else:
                continue
            candidates.append(_story(
                f"tc-{state.event_id}-{nint(row.get('entry'))}", "chip", headline, meta,
                importance, "settled", 24 * 60, source_event=state.event_id,
                manager_entry=nint(row.get("entry")), player_element=nint(row.get("element")),
            ))

    # The current monthly race matters after it has actual points.
    month = state.month_ranking()
    if state.month_name and month and sum(m.month_points for m in month) > 0:
        leader = month[0]
        candidates.append(_story(
            f"month-{state.month_name}-{leader.entry}", "month",
            f"{leader.manager} leder {state.month_name.lower()}{' live' if not state.is_finished else ''}",
            f"{leader.month_points} poeng denne måneden", 79 if state.is_live else 74,
            "live" if state.is_live else "settled", 180, manager_entry=leader.entry, source_event=state.event_id,
        ))

    # Finished-round facts can remain on the front page until a stronger story arrives.
    previous = completed_round_summary(managers, histories, _finished_event(bootstrap), history)
    if previous:
        fall = previous.get("biggest_fall") or {}
        climb = previous.get("best_climber") or {}
        fall_mag = abs(nint(fall.get("move"))) if nint(fall.get("move")) < 0 else 0
        climb_mag = max(0, nint(climb.get("move")))
        if max(fall_mag, climb_mag) >= 8:
            if fall_mag >= climb_mag:
                subject = fall
                headline = f"{fall.get('manager')} falt {fall_mag} plasser forrige runde"
                magnitude = fall_mag
            else:
                subject = climb
                headline = f"{climb.get('manager')} klatret {climb_mag} plasser forrige runde"
                magnitude = climb_mag
            candidates.append(_story(
                f"finished-move-{previous.get('event')}-{nint(subject.get('entry'))}", "movement",
                headline, f"GW{previous.get('event')}: {nint(subject.get('gw'))} poeng",
                min(96, 70 + magnitude), "settled", 36 * 60, source_event=nint(previous.get("event")),
                manager_entry=nint(subject.get("entry")), freshness=70,
            ))
        winner = previous.get("gw_winner") or {}
        if nint(winner.get("gw")):
            candidates.append(_story(
                f"round-winner-{previous.get('event')}-{nint(winner.get('entry'))}", "round",
                f"{winner.get('manager')} var best forrige runde",
                f"{nint(winner.get('gw'))} poeng i GW{previous.get('event')}", 68, "settled", 30 * 60,
                source_event=nint(previous.get("event")), manager_entry=nint(winner.get("entry")), freshness=65,
            ))

    # Ownership is a fallback story, never strong enough to push out genuine drama.
    if state.player_impacts:
        most_owned = max(state.player_impacts, key=lambda p: (p.ownership_count, p.captain_count, -p.element))
        loaded = max(1, nint(state.data_quality.get("loaded_managers"), state.league_size))
        without = max(0, loaded - most_owned.ownership_count)
        if most_owned.ownership_pct >= 75:
            candidates.append(_story(
                f"ownership-{state.event_id}-{most_owned.element}", "ownership",
                f"Bare {without} av {loaded} går uten {most_owned.player}",
                f"{most_owned.ownership_pct:.0f} % eierskap i Lofthus", 58, "context", 180,
                source_event=state.event_id, player_element=most_owned.element, freshness=55,
            ))

    # Deduplicate category + subject deterministically.
    best: dict[str, Story] = {}
    for story in candidates:
        old = best.get(story.key)
        if old is None or (story.importance, story.freshness) > (old.importance, old.freshness):
            best[story.key] = story
    return sorted(best.values(), key=lambda s: (-s.importance, -s.freshness, s.key))


def merge_persistent_stories(
    candidates: list[Story],
    previous_serialized: list[dict[str, Any]] | None,
    state: LiveState,
    limit: int = 4,
) -> list[Story]:
    """Newspaper hysteresis: strong stories survive ordinary low-value churn."""
    now = _now()
    pool: dict[str, Story] = {s.key: s for s in candidates}
    for raw in previous_serialized or []:
        old = Story.from_dict(raw)
        if not old or old.expires_at <= now:
            continue
        # A provisional live story dies when live play has stopped. Settled
        # stories can persist into the next page load as intended.
        if old.status == "live" and (not state.is_live or (old.source_event and old.source_event != state.event_id)):
            continue
        current = pool.get(old.key)
        if current is None:
            pool[old.key] = old
        elif old.importance > current.importance:
            pool[old.key] = old

    ordered = sorted(pool.values(), key=lambda s: (-s.importance, -s.freshness, s.created_at, s.key))
    # Avoid four versions of the same kind of story. One category slot is enough.
    result: list[Story] = []
    seen_categories: set[str] = set()
    for story in ordered:
        family = "movement" if story.category in {"movement", "movement_live"} else story.category
        if family in seen_categories:
            continue
        seen_categories.add(family)
        result.append(story)
        if len(result) >= max(1, int(limit)):
            break
    return result
