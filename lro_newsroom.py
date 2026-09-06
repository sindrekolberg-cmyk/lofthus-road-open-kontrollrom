from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from lro_analysis import nint
from lro_history import HistoryStore, normalize_text
from lro_live import LiveState
from lro_status import story_is_current_gw


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
    source_fixture: int = 0
    manager_entry: int = 0
    player_element: int = 0
    supersedes: str = ""
    updated_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["created_at"] = self.created_at.isoformat()
        out["expires_at"] = self.expires_at.isoformat()
        updated = self.updated_at or self.created_at
        out["updated_at"] = updated.isoformat()
        out["source_gw"] = int(self.source_event or 0)
        return out

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Story" | None:
        try:
            created = datetime.fromisoformat(str(row.get("created_at")))
            updated_raw = row.get("updated_at")
            updated = datetime.fromisoformat(str(updated_raw)) if updated_raw else created
            return cls(
                key=str(row.get("key") or ""),
                category=str(row.get("category") or ""),
                headline=str(row.get("headline") or ""),
                meta=str(row.get("meta") or ""),
                importance=int(row.get("importance") or 0),
                freshness=int(row.get("freshness") or 0),
                status=str(row.get("status") or ""),
                confidence=int(row.get("confidence") or 0),
                created_at=created,
                expires_at=datetime.fromisoformat(str(row.get("expires_at"))),
                source_event=int(row.get("source_event") or row.get("source_gw") or 0),
                source_fixture=int(row.get("source_fixture") or 0),
                manager_entry=int(row.get("manager_entry") or 0),
                player_element=int(row.get("player_element") or 0),
                supersedes=str(row.get("supersedes") or ""),
                updated_at=updated,
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
    source_fixture: int = 0,
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
        source_fixture=int(source_fixture),
        manager_entry=int(manager_entry),
        player_element=int(player_element),
        supersedes=supersedes,
        updated_at=now,
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


def desk_score(story: Story, event_id: int) -> tuple:
    """Prefer this GW's live pulse over leftover previous-round drama."""
    current = story_is_current_gw(story.source_event, event_id)
    tier = {
        "live": 10,
        "leader": 9,
        "captain": 8,
        "chip": 7,
        "differential": 6,
        "autosub": 6,
        "bench": 6,
        "unique": 6,
        "month": 4,
        "movement": 2,
        "round": 1,
        "ownership": 0,
        "context": 0,
    }.get(story.category, 3)
    if story.category == "live" and story.status != "live":
        tier = min(tier, 5)
    importance = story.importance
    freshness = story.freshness
    if not current:
        tier = min(tier, 2)
        importance = min(importance, 42)
        freshness = min(freshness, 28)
    return (tier, importance, freshness, -len(story.key))


def generate_candidates(
    state: LiveState,
    managers: list[dict],
    bootstrap: dict,
    history: HistoryStore,
    histories: dict[int, dict] | None = None,
) -> list[Story]:
    candidates: list[Story] = []
    picks = state.ownership.get("picks", pd.DataFrame())

    # A live leader change is major news. The language explicitly remains provisional.
    top = state.top(1)
    if top:
        leader = top[0]
        if state.is_live and leader.previous_rank and leader.previous_rank != 1:
            candidates.append(_story(
                f"live-leader-{state.event_id}-{leader.entry}", "leader",
                f"{leader.manager} leder live",
                f"{leader.live_total_points} poeng · foreløpig opp {max(0, leader.live_rank_change)} plasser",
                97, "live", 45, source_event=state.event_id, manager_entry=leader.entry,
            ))

    this_round = not state.is_finished

    # The player with the biggest real live/this-round effect. No unplayed zero can enter here.
    if this_round:
        live_impacts = [
            p for p in state.player_impacts
            if p.fixture_status in {"live", "pause", "finished"} and p.event_points != 0
        ]
        if live_impacts:
            playing = [p for p in live_impacts if p.fixture_status in {"live", "pause"}]
            p = playing[0] if playing else live_impacts[0]
            if p.event_points >= 8 or p.captain_count or p.triple_captain_count:
                imp = 94 if p.event_points >= 10 else 84
                caps = p.captain_count
                cap_text = f" · {caps} kaptein" if caps == 1 else f" · {caps} kapteiner" if caps else ""
                verb = "herjer" if p.fixture_status in {"live", "pause"} else "leverte"
                candidates.append(_story(
                    f"live-player-{state.event_id}-{p.element}", "live",
                    f"{p.player} {verb}: {p.event_points} poeng",
                    f"{p.ownership_count} eiere{cap_text}", imp, "live" if p.fixture_status in {"live", "pause"} else "settled", 25,
                    source_event=state.event_id, player_element=p.element,
                ))

        diffs = [
            p for p in live_impacts
            if p.ownership_pct <= 15 and p.event_points >= 8
        ]
        if diffs:
            p = diffs[0]
            candidates.append(_story(
                f"diff-{state.event_id}-{p.element}", "differential",
                f"{p.player} er runden sin differensial: {p.event_points} poeng",
                f"Bare {p.ownership_pct:.0f} % eierskap i Lofthus", 86, "live" if state.is_live else "settled", 40,
                source_event=state.event_id, player_element=p.element,
            ))
        uniques = [p for p in live_impacts if p.ownership_count == 1 and p.event_points >= 10]
        if uniques:
            p = uniques[0]
            owner_name = ""
            if picks is not None and not picks.empty:
                block = picks[picks["element"].map(nint) == p.element]
                if not block.empty:
                    owner_name = str(block.iloc[0].get("manager") or "")
            candidates.append(_story(
                f"unique-{state.event_id}-{p.element}", "unique",
                f"{p.player} er unik i Lofthus: {p.event_points} poeng",
                f"{owner_name or 'Én manager'} er eneste eier".strip(),
                85, "live" if p.fixture_status in {"live", "pause"} else "settled", 40,
                source_event=state.event_id, player_element=p.element,
            ))

    candidates.extend(_decision_stories(state, this_round))

    if this_round and picks is not None and not picks.empty:
        if "is_captain" in picks.columns:
            caps = picks[picks["is_captain"].astype(bool)]
            worst = None
            for row in caps.to_dict("records"):
                impact = state.player(nint(row.get("element")))
                if not impact or impact.fixture_status != "finished":
                    continue
                pts = nint(row.get("event_points"))
                if pts > 2:
                    continue
                if worst is None or pts < nint(worst.get("event_points")):
                    worst = row
                    worst["_impact"] = impact
            if worst is not None:
                impact = worst["_impact"]
                tc = nint(worst.get("multiplier")) >= 3 or bool(worst.get("is_triple_captain"))
                if not tc:
                    candidates.append(_story(
                        f"capfail-{state.event_id}-{nint(worst.get('entry'))}", "captain",
                        f"Kapteinsmell for {worst.get('manager')}",
                        f"{impact.player} endte på {nint(worst.get('event_points'))} poeng",
                        82, "settled", 12 * 60,
                        source_event=state.event_id, manager_entry=nint(worst.get("entry")),
                        player_element=impact.element,
                    ))
            best_cap = None
            for row in caps.to_dict("records"):
                impact = state.player(nint(row.get("element")))
                if not impact or impact.fixture_status != "finished":
                    continue
                pts = nint(row.get("event_points"))
                if pts < 12:
                    continue
                if best_cap is None or pts > nint(best_cap.get("event_points")):
                    best_cap = row
                    best_cap["_impact"] = impact
            if best_cap is not None:
                impact = best_cap["_impact"]
                tc = nint(best_cap.get("multiplier")) >= 3 or bool(best_cap.get("is_triple_captain"))
                if not tc:
                    candidates.append(_story(
                        f"caphit-{state.event_id}-{nint(best_cap.get('entry'))}", "captain",
                        f"Kapteinen leverte for {best_cap.get('manager')}",
                        f"{impact.player} endte på {nint(best_cap.get('event_points'))} poeng",
                        80, "settled", 12 * 60,
                        source_event=state.event_id, manager_entry=nint(best_cap.get("entry")),
                        player_element=impact.element,
                    ))
        if "autosub_in" in picks.columns:
            subs = picks[picks["autosub_in"].astype(bool)]
            if not subs.empty:
                best = max(subs.to_dict("records"), key=lambda r: nint(r.get("gw_contribution")))
                if nint(best.get("gw_contribution")) >= 4:
                    replaced = str(best.get("replaced_player") or "benken")
                    candidates.append(_story(
                        f"autosub-{state.event_id}-{nint(best.get('entry'))}", "autosub",
                        f"{best.get('player')} inn for {replaced}",
                        f"{best.get('manager')} henter {nint(best.get('gw_contribution'))} poeng fra benken",
                        80, "live" if state.is_live else "settled", 90,
                        source_event=state.event_id, manager_entry=nint(best.get("entry")),
                        player_element=nint(best.get("element")),
                    ))

    # Triple Captain is only judged after the captain's fixture is finished.
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

    # Previous-round ordinary movement stays out of the homepage while this GW is open.
    previous = completed_round_summary(managers, histories, _finished_event(bootstrap), history)
    if previous and state.is_finished and nint(previous.get("event")) == int(state.event_id):
        fall = previous.get("biggest_fall") or {}
        climb = previous.get("best_climber") or {}
        fall_mag = abs(nint(fall.get("move"))) if nint(fall.get("move")) < 0 else 0
        climb_mag = max(0, nint(climb.get("move")))
        if max(fall_mag, climb_mag) >= 12:
            if fall_mag >= climb_mag:
                subject = fall
                headline = f"{fall.get('manager')} falt {fall_mag} plasser"
                magnitude = fall_mag
            else:
                subject = climb
                headline = f"{climb.get('manager')} klatret {climb_mag} plasser"
                magnitude = climb_mag
            candidates.append(_story(
                f"finished-move-{previous.get('event')}-{nint(subject.get('entry'))}", "movement",
                headline, f"GW{previous.get('event')}: {nint(subject.get('gw'))} poeng",
                min(78, 60 + magnitude // 2), "settled", 8 * 60, source_event=nint(previous.get("event")),
                manager_entry=nint(subject.get("entry")), freshness=40,
            ))

    best: dict[str, Story] = {}
    for story in candidates:
        old = best.get(story.key)
        if old is None or desk_score(story, state.event_id) > desk_score(old, state.event_id):
            best[story.key] = story
    return sorted(best.values(), key=lambda s: desk_score(s, state.event_id), reverse=True)


def _decision_stories(state: LiveState, this_round: bool) -> list[Story]:
    """Snakkiser about decisions/drama. Pure rank movement belongs in Største utslag."""
    if not this_round:
        return []
    out: list[Story] = []
    picks = state.ownership.get("picks", pd.DataFrame())
    live_by_entry = {m.entry: m for m in state.manager_live}
    if picks is None or picks.empty:
        return out
    if "is_captain" in picks.columns:
        caps = picks[picks["is_captain"].astype(bool)]
        by_el: dict[int, list[dict[str, Any]]] = {}
        for cap_row in caps.to_dict("records"):
            by_el.setdefault(nint(cap_row.get("element")), []).append(cap_row)
        for element, rows in by_el.items():
            impact = state.player(element)
            if not impact or impact.event_points < 8:
                continue
            if impact.fixture_status not in {"live", "pause", "finished"}:
                continue
            top20 = [
                cap_row for cap_row in rows
                if live_by_entry.get(nint(cap_row.get("entry"))) and live_by_entry[nint(cap_row.get("entry"))].live_rank <= 20
            ]
            if len(top20) != 1:
                continue
            cap_row = top20[0]
            mgr = live_by_entry[nint(cap_row.get("entry"))]
            climb = max(0, mgr.live_rank_change)
            if climb >= 8:
                headline = f"{impact.player}-gambleren flyr"
                meta = (
                    f"{mgr.manager} er eneste {impact.player}-kaptein i topp 20 "
                    f"og går {climb} plasser opp"
                )
            else:
                headline = f"Eneste {impact.player}-kaptein i topp 20"
                meta = f"{mgr.manager} tok {impact.player} · {impact.event_points} poeng"
            out.append(_story(
                f"capgamble-{state.event_id}-{mgr.entry}", "captain",
                headline, meta, 93 if climb >= 8 else 84,
                "live" if impact.fixture_status in {"live", "pause"} else "settled", 40,
                source_event=state.event_id, manager_entry=mgr.entry, player_element=impact.element,
            ))
    if "multiplier" in picks.columns:
        for entry, group in picks.groupby(picks["entry"].map(nint)):
            bench_mask = group["multiplier"].map(nint) == 0
            if "on_bench" in group.columns:
                bench_mask = bench_mask | group["on_bench"].astype(bool)
            bench = group[bench_mask]
            pts = 0
            best_name = ""
            best_pts = -1
            for bench_row in bench.to_dict("records"):
                value = nint(bench_row.get("gw_contribution") or bench_row.get("event_points"))
                pts += value
                if value > best_pts:
                    best_pts = value
                    best_name = str(bench_row.get("player") or "")
            if pts < 10:
                continue
            mgr = live_by_entry.get(int(entry))
            manager_name = mgr.manager if mgr else str(group.iloc[0].get("manager") or "")
            out.append(_story(
                f"bench-{state.event_id}-{int(entry)}", "bench",
                f"{pts} poeng fra benken",
                f"{manager_name} · {best_name}" if best_name else manager_name,
                81, "live" if state.is_live else "settled", 60,
                source_event=state.event_id, manager_entry=int(entry),
            ))
    for mgr in state.manager_live:
        chip = str(mgr.active_chip or "")
        if chip in {"Free Hit", "Wildcard", "Bench Boost"} and mgr.live_gw_points >= 55 and mgr.live_rank_change >= 5:
            out.append(_story(
                f"chipplay-{state.event_id}-{mgr.entry}", "chip",
                f"{mgr.manager} kjører {chip}",
                f"{mgr.live_gw_points} poeng · {mgr.live_rank_change} plasser opp",
                87, "live" if state.is_live else "settled", 90,
                source_event=state.event_id, manager_entry=mgr.entry,
            ))
    return out


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
        if old.source_event and old.source_event != state.event_id:
            continue
        current = pool.get(old.key)
        if current is None:
            pool[old.key] = old
        elif desk_score(old, state.event_id) > desk_score(current, state.event_id):
            pool[old.key] = old

    ordered = sorted(pool.values(), key=lambda s: desk_score(s, state.event_id), reverse=True)
    result: list[Story] = []
    seen_once: set[str] = set()
    for story in ordered:
        family = story.category
        if family in {"leader", "month", "round", "movement"}:
            if family in seen_once:
                continue
            seen_once.add(family)
        if family in {"captain", "chip"} and story.manager_entry and story.player_element:
            arm = f"armband:{story.manager_entry}:{story.player_element}"
            if arm in seen_once:
                continue
            seen_once.add(arm)
        result.append(story)
        if len(result) >= max(1, int(limit)):
            break
    return result


_HOMEPAGE_MAJOR = {"live", "leader", "chip", "captain", "differential", "autosub", "bench", "unique", "month"}


def homepage_feed(stories: list[Any], event_id: int, limit: int = 5) -> list[Any]:
    """Homepage Snakkiser: current, strong stories only. Never pad with leftovers."""
    out: list[Any] = []
    seen_armband: set[str] = set()
    for story in stories:
        if isinstance(story, dict):
            category = str(story.get("category") or "")
            source = int(story.get("source_event") or 0)
            importance = int(story.get("importance") or 0)
        else:
            category = str(getattr(story, "category", "") or "")
            source = int(getattr(story, "source_event", 0) or 0)
            importance = int(getattr(story, "importance", 0) or 0)
        if not story_is_current_gw(source, event_id) and category != "month":
            continue
        if category not in _HOMEPAGE_MAJOR:
            continue
        if importance < 72:
            continue
        entry = int(story.get("manager_entry") or 0) if isinstance(story, dict) else int(getattr(story, "manager_entry", 0) or 0)
        player = int(story.get("player_element") or 0) if isinstance(story, dict) else int(getattr(story, "player_element", 0) or 0)
        if category in {"captain", "chip"} and entry and player:
            arm = f"{entry}:{player}"
            if arm in seen_armband:
                continue
            seen_armband.add(arm)
        out.append(story)
        if len(out) >= max(1, int(limit)):
            break
    return out
