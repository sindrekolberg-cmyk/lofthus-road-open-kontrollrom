from __future__ import annotations

from pathlib import Path
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any

import pandas as pd
import streamlit as st

from lro_analysis import (
    build_ownership,
    canonical_managers,
    chip_label,
    manager_form_from_histories,
    manager_squad,
    nfloat,
    nint,
    rival_analysis,
    refresh_ownership_live,
    round_movements,
)
from lro_fpl import (
    DEFAULT_LEAGUE_ID,
    FPLClient,
    current_event_id,
    current_month_phase,
    finished_event_ids,
    month_phases,
    player_catalog,
    season_label,
    short_season_label,
)
try:
    from lro_history import HistoryStore, hall_of_fame_sort_key, normalize_text
except ImportError:
    # Backward-compatible deploy guard: an older cached/deployed lro_history.py
    # may not yet export hall_of_fame_sort_key. The app must still boot.
    from lro_history import HistoryStore, normalize_text

    def hall_of_fame_sort_key(row: dict) -> tuple:
        def num(key: str) -> int:
            try:
                return int(float(row.get(key) or 0))
            except Exception:
                return 0

        league_gold = num("league_gold")
        other_gold = num("cup_gold") + num("monthly_gold")
        total_silver = num("league_silver") + num("cup_silver") + num("monthly_silver")
        total_bronze = num("league_bronze") + num("monthly_bronze")
        return (
            -league_gold,
            -other_gold,
            -total_silver,
            -total_bronze,
            normalize_text(row.get("display_name") or ""),
        )
from lro_archive import SnapshotStore
from lro_odds import build_live_market, build_preseason_odds, compare_group_odds, decimal_odds_from_pct, simulate_group
import lro_ui as ui

APP_VERSION = "lofthus-road-open-v705-live-manager-form"
DATA_DIR = Path(__file__).resolve().parent / "data"
PRESEASON_ODDS_FILE = DATA_DIR / "preseason_odds_2026_27.csv"

st.set_page_config(page_title="Lofthus Road Open", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")
ui.install_styles()


@st.cache_resource
def get_client() -> FPLClient:
    return FPLClient()


@st.cache_resource
def get_history_store(version: str) -> HistoryStore:
    # Version is part of the cache key so deploys never keep an old HistoryStore object.
    return HistoryStore(DATA_DIR)


client = get_client()
history_store = get_history_store(APP_VERSION)
snapshot_store = SnapshotStore(DATA_DIR / "snapshots")


@st.cache_resource
def get_home_background_pool() -> ThreadPoolExecutor:
    # One coordinator job is enough. build_ownership itself fans out the FPL calls.
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="lro-home")


@st.cache_resource
def get_home_background_jobs() -> dict:
    return {"lock": threading.RLock(), "jobs": {}}


def _build_home_ownership_background(managers: list[dict], event_id: int) -> dict:
    # Use a separate client in the worker so the visible app never waits on the
    # 63-manager ownership sweep. Shorter timeouts also stop a few bad FPL calls
    # from holding the entire background job hostage.
    bg_client = FPLClient(timeout=9)
    bg_history = HistoryStore(DATA_DIR)
    return build_ownership(
        bg_client,
        managers,
        bg_history,
        event_id=int(event_id),
        only_entries=None,
        max_workers=10,
    )


def home_ownership_async(managers: list[dict], bootstrap: dict) -> dict | None:
    event_id = current_event_id(bootstrap)
    if not event_id:
        return None
    entries = tuple(sorted(nint(m.get("entry")) for m in managers if nint(m.get("entry"))))
    key = ("ownership", int(event_id), entries)
    state = get_home_background_jobs()
    with state["lock"]:
        future = state["jobs"].get(key)
        if future is None:
            future = get_home_background_pool().submit(_build_home_ownership_background, [dict(m) for m in managers], int(event_id))
            state["jobs"][key] = future
    if not future.done():
        return None
    try:
        return future.result()
    except Exception:
        # Drop a failed job so a later rerun can try again, while the page itself
        # remains fully usable.
        with state["lock"]:
            state["jobs"].pop(key, None)
        return None


def _build_home_histories_background(managers: list[dict]) -> dict[int, dict]:
    """Fetch current-season histories without blocking the front page.

    This lets the newsroom reconstruct the *previous completed* Lofthus round
    instead of mistaking live table movement for a finished result.
    """
    bg_client = FPLClient(timeout=9)
    entries = [nint(m.get("entry")) for m in managers if nint(m.get("entry"))]
    values, _ = bg_client.histories_many(entries, max_workers=10)
    return values


def home_histories_async(managers: list[dict]) -> dict[int, dict] | None:
    entries = tuple(sorted(nint(m.get("entry")) for m in managers if nint(m.get("entry"))))
    if not entries:
        return None
    key = ("histories", entries)
    state = get_home_background_jobs()
    with state["lock"]:
        future = state["jobs"].get(key)
        if future is None:
            future = get_home_background_pool().submit(_build_home_histories_background, [dict(m) for m in managers])
            state["jobs"][key] = future
    if not future.done():
        return None
    try:
        return future.result()
    except Exception:
        with state["lock"]:
            state["jobs"].pop(key, None)
        return None


def fmt_price(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return "–"
        price = float(value)
        if price <= 0 or price > 25:
            return "–"
        return f"£{price:.1f}"
    except Exception:
        return "–"


def fmt_pct(value: Any) -> str:
    return f"{max(0.0, min(100.0, nfloat(value))):.0f}%"


def manager_map(managers: list[dict]) -> dict[int, dict]:
    return {nint(m.get("entry")): m for m in managers if nint(m.get("entry"))}


def manager_name(m: dict) -> str:
    return history_store.canonical(str(m.get("player_name") or "Ukjent manager"))


def manager_options(managers: list[dict]) -> list[tuple[int, str]]:
    out = [(nint(m.get("entry")), manager_name(m)) for m in managers if nint(m.get("entry"))]
    return sorted(out, key=lambda x: normalize_text(x[1]))



def manager_href(entry: int) -> str:
    return f"?page=Ligaen&league_view=Manager&manager={int(entry)}"


def owner_links(names: list[str], managers: list[dict], limit: int = 3) -> list[dict]:
    by_key = {history_store.key(manager_name(m)): nint(m.get("entry")) for m in managers if nint(m.get("entry"))}
    out = []
    for name in names[:limit]:
        entry = by_key.get(history_store.key(name), 0)
        out.append({"label": name, "href": manager_href(entry) if entry else ""})
    if len(names) > limit:
        out.append({"label": f"+{len(names)-limit}", "href": ""})
    return out


def _preseason_market(managers: list[dict], histories: dict[int, dict]) -> pd.DataFrame:
    odds = pd.DataFrame()
    if PRESEASON_ODDS_FILE.exists():
        try:
            odds = pd.read_csv(PRESEASON_ODDS_FILE)
        except Exception:
            odds = pd.DataFrame()
    if odds.empty:
        try:
            odds = build_preseason_odds(managers, histories, history_store)
        except Exception:
            odds = pd.DataFrame()
    return odds


def my_manager_id(managers: list[dict]) -> int:
    ids = {nint(m.get("entry")) for m in managers if nint(m.get("entry"))}
    candidates = [st.session_state.get("v500_my_manager"), st.session_state.get("v400_my_manager")]
    try:
        candidates.insert(0, st.query_params.get("me"))
    except Exception:
        pass
    for value in candidates:
        entry = nint(value)
        if entry in ids:
            return entry
    return 0

def selected_ownership(managers: list[dict], entries: list[int] | None = None) -> dict:
    bootstrap = client.bootstrap()
    event = current_event_id(bootstrap)
    key_entries = tuple(sorted(int(x) for x in (entries or [nint(m.get("entry")) for m in managers]) if int(x) > 0))
    cache_key = f"v400_ownership_{event}_{','.join(map(str, key_entries))}"
    stamp_key = f"{cache_key}_built_at"
    # Picks themselves are cached in FPLClient, but live event points move during a
    # match. Rebuild the derived ownership object roughly once a minute so live
    # points do not freeze for an entire browser session.
    stale = time.time() - float(st.session_state.get(stamp_key, 0.0)) > 75
    if cache_key not in st.session_state or stale:
        st.session_state[cache_key] = build_ownership(
            client,
            managers,
            history_store,
            event_id=event,
            only_entries=list(key_entries),
            max_workers=8 if len(key_entries) > 8 else 6,
        )
        st.session_state[stamp_key] = time.time()
    ownership = st.session_state[cache_key]
    # A full-league load after a completed GW is enough to build a repo-friendly
    # archive snapshot. Failure to write must never break the live app.
    if len(key_entries) >= len(managers) and current_event_finished(bootstrap):
        archive_completed_round(managers, bootstrap, ownership)
    return ownership


def histories_for(entries: list[int]) -> tuple[dict[int, dict], dict[int, str]]:
    ids = tuple(sorted(set(int(x) for x in entries if int(x) > 0)))
    cache_key = f"v400_histories_{','.join(map(str, ids))}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = client.histories_many(ids, max_workers=8)
    return st.session_state[cache_key]


def auto_monthly_rows(bootstrap: dict) -> list[dict]:
    season = season_label(bootstrap)
    max_finished = max(finished_event_ids(bootstrap) or [0])
    rows = []
    for phase in month_phases(bootstrap):
        if phase["stop_event"] <= 0 or phase["stop_event"] > max_finished:
            continue
        try:
            standings = client.league_phase_standings(DEFAULT_LEAGUE_ID, phase["id"])
        except Exception:
            continue
        if not standings:
            continue
        standings = sorted(
            standings,
            key=lambda r: (nint(r.get("rank"), 10**9), -nint(r.get("total")), normalize_text(str(r.get("player_name") or ""))),
        )
        for place, row in enumerate(standings[:3], start=1):
            rows.append({
                "season": season,
                "month": phase["name"],
                "place": place,
                "manager": history_store.canonical(str(row.get("player_name") or "Ukjent manager")),
                "status": "Automatisk",
                "source": f"FPL phase {phase['id']}",
            })
    return rows


def current_month_table(managers: list[dict], bootstrap: dict) -> tuple[dict | None, pd.DataFrame]:
    phase = current_month_phase(bootstrap)
    if not phase:
        return None, pd.DataFrame()
    try:
        standings = client.league_phase_standings(DEFAULT_LEAGUE_ID, phase["id"])
    except Exception:
        standings = []
    rows = []
    for r in standings:
        rows.append({
            "rank": nint(r.get("rank")),
            "entry": nint(r.get("entry")),
            "manager": history_store.canonical(str(r.get("player_name") or "Ukjent manager")),
            "team": str(r.get("entry_name") or ""),
            "points": nint(r.get("total")),
        })
    df = pd.DataFrame(rows)
    # On the first day(s) of a month FPL can still expose the old/current GW. A zero
    # month should be visibly live, but not invent a sporting order.
    if df.empty or ("points" in df.columns and int(pd.to_numeric(df["points"], errors="coerce").fillna(0).sum()) == 0):
        alpha = sorted(
            [{"entry": nint(m.get("entry")), "manager": manager_name(m), "team": str(m.get("entry_name") or ""), "points": 0} for m in managers],
            key=lambda x: normalize_text(x["manager"]),
        )
        df = pd.DataFrame([{**r, "rank": i + 1} for i, r in enumerate(alpha)])
    else:
        df = df.sort_values(["rank", "manager"]).reset_index(drop=True)
    return phase, df


def display_month_table(managers: list[dict], bootstrap: dict) -> tuple[dict | None, pd.DataFrame, bool]:
    """Month table for presentation.

    If a new calendar month has started but FPL has not awarded any points in
    that monthly phase yet, keep showing the previous completed month. This
    avoids an alphabetical 0-point table on the front page while preserving the
    real current-month zeroes for calculations such as Rivalradar.
    """
    phase, df = current_month_table(managers, bootstrap)
    if phase is None:
        return None, pd.DataFrame(), False

    points_sum = int(pd.to_numeric(df.get("points", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not df.empty else 0
    if points_sum > 0:
        return phase, df, True

    max_finished = max(finished_event_ids(bootstrap) or [0])
    phases = month_phases(bootstrap)
    previous = [
        p for p in phases
        if nint(p.get("id")) != nint(phase.get("id"))
        and nint(p.get("stop_event")) > 0
        and nint(p.get("stop_event")) <= max_finished
        and nint(p.get("stop_event")) < nint(phase.get("start_event"), 10**9)
    ]
    if not previous:
        return phase, df, False

    previous_phase = sorted(previous, key=lambda p: nint(p.get("stop_event")), reverse=True)[0]
    try:
        standings = client.league_phase_standings(DEFAULT_LEAGUE_ID, previous_phase["id"])
    except Exception:
        standings = []
    rows = [
        {
            "rank": nint(r.get("rank")),
            "entry": nint(r.get("entry")),
            "manager": history_store.canonical(str(r.get("player_name") or "Ukjent manager")),
            "team": str(r.get("entry_name") or ""),
            "points": nint(r.get("total")),
        }
        for r in standings
    ]
    previous_df = pd.DataFrame(rows)
    if previous_df.empty:
        return phase, df, False
    previous_df = previous_df.sort_values(["rank", "manager"]).reset_index(drop=True)
    return previous_phase, previous_df, False


def current_month_points_map(managers: list[dict], bootstrap: dict) -> dict[int, float]:
    _, df = current_month_table(managers, bootstrap)
    if df.empty:
        return {}
    return {nint(r.get("entry")): nfloat(r.get("points")) for r in df.to_dict("records") if nint(r.get("entry"))}


def current_month_live_table(managers: list[dict], bootstrap: dict, ownership: dict | None) -> tuple[dict | None, pd.DataFrame, bool]:
    """Return the current calendar-month table including an unfinished GW live.

    FPL's league phase table commonly stays at the last completed round while the
    normal league table moves live. We therefore add the current event's *live*
    manager points only while that event is unfinished. This is what lets the
    September race appear immediately on the first September matchday.
    """
    phase, base = current_month_table(managers, bootstrap)
    if phase is None:
        return None, pd.DataFrame(), False
    event = current_event_id(bootstrap) or 0
    if not event or current_event_finished(bootstrap):
        return phase, base, False
    if not (nint(phase.get("start_event")) <= int(event) <= nint(phase.get("stop_event"))):
        return phase, base, False
    ownership = ownership or {}
    if nint(ownership.get("loaded_managers")) < len(managers):
        return phase, base, False
    events = ownership.get("manager_events", pd.DataFrame())
    if events is None or events.empty or "live_gw_points" not in events.columns:
        return phase, base, False

    base_points = {nint(r.get("entry")): nint(r.get("points")) for r in base.to_dict("records")} if not base.empty else {}
    live_points = {nint(r.get("entry")): nint(r.get("live_gw_points")) for r in events.to_dict("records") if nint(r.get("entry"))}
    rows = []
    for m in managers:
        entry = nint(m.get("entry"))
        if not entry:
            continue
        rows.append({
            "entry": entry,
            "manager": manager_name(m),
            "team": str(m.get("entry_name") or ""),
            "points": nint(base_points.get(entry)) + nint(live_points.get(entry)),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return phase, base, False
    df["rank"] = df["points"].rank(method="min", ascending=False).astype(int)
    df = df.sort_values(["rank", "manager"], ascending=[True, True]).reset_index(drop=True)
    return phase, df, bool(int(pd.to_numeric(df["points"], errors="coerce").fillna(0).sum()) > 0)


def _previous_completed_event(bootstrap: dict) -> int:
    finished = sorted(finished_event_ids(bootstrap))
    if not finished:
        return 0
    current = current_event_id(bootstrap) or 0
    if current and not current_event_finished(bootstrap):
        older = [e for e in finished if e < current]
        return max(older or [0])
    return max(finished)


def _completed_round_from_snapshot(bootstrap: dict, event: int) -> dict:
    if not event:
        return {}
    payload = snapshot_store.read(season_label(bootstrap), int(event))
    table = payload.get("table", []) if isinstance(payload, dict) else []
    rows = []
    for r in table or []:
        rank = nint(r.get("rank"), 999999); last = nint(r.get("last_rank"), rank)
        if rank >= 999999:
            continue
        rows.append({
            "entry": nint(r.get("entry")), "manager": str(r.get("manager") or ""),
            "rank": rank, "last_rank": last, "move": last - rank,
            "gw": nint(r.get("gw_points")), "total": nint(r.get("total_points")),
        })
    if not rows:
        return {}
    return {
        "best_climber": max(rows, key=lambda x: (x["move"], x["gw"])),
        "biggest_fall": min(rows, key=lambda x: (x["move"], -x["gw"])),
        "gw_winner": max(rows, key=lambda x: (x["gw"], -x["rank"])),
        "rows": rows,
    }


def _completed_round_from_histories(managers: list[dict], histories: dict[int, dict] | None, event: int) -> dict:
    if not histories or event <= 0:
        return {}
    names = {nint(m.get("entry")): manager_name(m) for m in managers}
    totals_now: dict[int, int] = {}; totals_prev: dict[int, int] = {}; gw_points: dict[int, int] = {}
    for entry, payload in histories.items():
        by_event = {nint(r.get("event")): r for r in (payload.get("current", []) or []) if nint(r.get("event"))}
        now = by_event.get(int(event)); prev = by_event.get(int(event) - 1)
        if not now:
            continue
        totals_now[int(entry)] = nint(now.get("total_points"))
        totals_prev[int(entry)] = nint(prev.get("total_points")) if prev else 0
        gw_points[int(entry)] = nint(now.get("points"))
    if not totals_now:
        return {}
    now_df = pd.DataFrame([{"entry": e, "total": t} for e, t in totals_now.items()])
    prev_df = pd.DataFrame([{"entry": e, "total": totals_prev.get(e, 0)} for e in totals_now])
    now_df["rank"] = now_df["total"].rank(method="min", ascending=False).astype(int)
    prev_df["last_rank"] = prev_df["total"].rank(method="min", ascending=False).astype(int)
    ranks = now_df.merge(prev_df[["entry", "last_rank"]], on="entry", how="left")
    rows = []
    for r in ranks.to_dict("records"):
        entry = nint(r.get("entry")); rank = nint(r.get("rank")); last = nint(r.get("last_rank"), rank)
        rows.append({"entry": entry, "manager": names.get(entry, str(entry)), "rank": rank, "last_rank": last, "move": last-rank, "gw": gw_points.get(entry, 0), "total": totals_now.get(entry, 0)})
    return {
        "best_climber": max(rows, key=lambda x: (x["move"], x["gw"])),
        "biggest_fall": min(rows, key=lambda x: (x["move"], -x["gw"])),
        "gw_winner": max(rows, key=lambda x: (x["gw"], -x["rank"])),
        "rows": rows,
    }


def previous_completed_round(managers: list[dict], bootstrap: dict, histories: dict[int, dict] | None = None) -> dict:
    event = _previous_completed_event(bootstrap)
    snap = _completed_round_from_snapshot(bootstrap, event)
    if snap:
        return {**snap, "event": event}
    hist = _completed_round_from_histories(managers, histories, event)
    return {**hist, "event": event} if hist else {}


def _team_fixture_states(bootstrap: dict) -> dict[int, dict]:
    event = current_event_id(bootstrap) or 0
    if not event:
        return {}
    try:
        fixtures = client.fixtures(int(event))
    except Exception:
        fixtures = []
    out: dict[int, dict] = {}
    for f in fixtures:
        state = {"started": bool(f.get("started")), "finished": bool(f.get("finished")), "minutes": nint(f.get("minutes"))}
        for key in ("team_h", "team_a"):
            tid = nint(f.get(key))
            if tid:
                out[tid] = state
    return out


def front_stories(managers: list[dict], bootstrap: dict, ownership: dict | None, histories: dict[int, dict] | None) -> list[str]:
    """Act like a sports desk: publish the strongest four *valid* stories.

    Unplayed captain chips are not failures, and live table movement is not a
    completed-round fact. When a headline is suppressed, the next-best candidate
    takes its place rather than leaving a hole.
    """
    candidates: list[tuple[int, str, str]] = []
    ownership = ownership or {}
    team_state = _team_fixture_states(bootstrap)

    # Settled chip outcome only. Zero before kickoff is not news.
    picks = ownership.get("picks", pd.DataFrame())
    if picks is not None and not picks.empty:
        tc = picks[picks.get("is_triple_captain", False).astype(bool)].copy() if "is_triple_captain" in picks.columns else pd.DataFrame()
        settled = []
        for row in tc.to_dict("records") if not tc.empty else []:
            state = team_state.get(nint(row.get("team_id")), {})
            if not state.get("finished"):
                continue
            settled.append(row)
        if settled:
            settled.sort(key=lambda r: (nint(r.get("event_points")), normalize_text(str(r.get("manager") or ""))))
            row = settled[0]; pts = nint(row.get("event_points"))
            text = f"{row.get('manager')} brukte Triple Captain på {row.get('player')} – og fikk {pts} poeng."
            score = 100 if pts == 0 else 88 if pts >= 15 else 72
            candidates.append((score, "chip", text))

    # The previous *completed* GW movement stays news until something genuinely bigger replaces it.
    previous = previous_completed_round(managers, bootstrap, histories)
    climber = previous.get("best_climber") or {}; faller = previous.get("biggest_fall") or {}
    c_move = nint(climber.get("move")); f_move = nint(faller.get("move"))
    if max(c_move, abs(f_move)) >= 8:
        if abs(f_move) >= c_move:
            mag = abs(f_move); text = f"{faller.get('manager')} falt {mag} plasser forrige runde."
        else:
            mag = c_move; text = f"{climber.get('manager')} klatret {mag} plasser forrige runde."
        candidates.append((min(98, 68 + mag), "movement", text))

    # Previous round winner, never a live half-round winner.
    gw_winner = previous.get("gw_winner") or {}
    if gw_winner and nint(gw_winner.get("gw")):
        candidates.append((66, "round", f"{gw_winner.get('manager')} var best forrige runde med {nint(gw_winner.get('gw'))} poeng."))

    players = ownership.get("players", pd.DataFrame())
    active, _ = active_fixtures(bootstrap)
    active_teams = {nint(f.get(k)) for f in active for k in ("team_h", "team_a")}
    if players is not None and not players.empty:
        # A genuine live explosion can be front-page news, unlike an unplayed zero.
        if active_teams:
            live = players[players["team_id"].isin(active_teams)].copy()
            if not live.empty:
                live["event_points"] = pd.to_numeric(live.get("event_points", 0), errors="coerce").fillna(0)
                best = live.sort_values(["event_points", "ownership_count"], ascending=[False, False]).iloc[0].to_dict()
                if nint(best.get("event_points")) >= 10:
                    candidates.append((92, "live", f"{best.get('player')} herjer: {nint(best.get('event_points'))} poeng live – {nint(best.get('ownership_count'))} Lofthus-eiere profiterer."))

        top = players.sort_values(["ownership_count", "player"], ascending=[False, True]).iloc[0]
        loaded = nint(ownership.get("loaded_managers")); without = max(0, loaded - nint(top.get("ownership_count")))
        if loaded:
            pct = nint(top.get("ownership_count")) / max(1, loaded)
            score = 74 if pct >= .85 else 58
            candidates.append((score, "ownership", f"Bare {without} av {loaded} går uten {top.get('player')}."))

    # Live monthly race is more interesting than an old August winner once the new month has points.
    phase, month_live, is_live = current_month_live_table(managers, bootstrap, ownership)
    if phase and is_live and not month_live.empty:
        lead = month_live.iloc[0].to_dict()
        candidates.append((78, "month", f"{lead.get('manager')} leder {str(phase.get('name') or 'måned').lower()} live med {nint(lead.get('points'))} poeng."))

    move_now = round_movements(managers, history_store)
    leader = move_now.get("leader") or {}
    if leader:
        candidates.append((48, "leader", f"{leader.get('manager')} leder ligaen med {nint(leader.get('total'))} poeng."))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    out: list[str] = []; seen: set[str] = set()
    for _, category, text in candidates:
        if category in seen or not text or text in out:
            continue
        seen.add(category); out.append(text)
        if len(out) >= 4:
            break
    return out


def data_quality_note(ownership: dict) -> None:
    loaded = nint(ownership.get("loaded_managers"))
    total = nint(ownership.get("league_size"))
    if total and loaded < total:
        st.caption(f"Lagdata tilgjengelig for {loaded} av {total}.")


def active_fixtures(bootstrap: dict) -> tuple[list[dict], dict[int, str]]:
    event = current_event_id(bootstrap)
    if not event:
        return [], {}
    try:
        fixtures = client.fixtures(event)
    except Exception:
        return [], {}
    teams = {nint(t.get("id")): str(t.get("short_name") or t.get("name") or "?") for t in bootstrap.get("teams", []) or []}
    active = [f for f in fixtures if f.get("started") and not f.get("finished")]
    return active, teams


def current_event_finished(bootstrap: dict) -> bool:
    event_id = current_event_id(bootstrap)
    if not event_id:
        return True
    for event in bootstrap.get("events", []) or []:
        if nint(event.get("id")) == int(event_id):
            return bool(event.get("finished")) or bool(event.get("data_checked"))
    return False


def archive_completed_round(managers: list[dict], bootstrap: dict, ownership: dict) -> None:
    """Best-effort snapshot. The UI keeps working even on a read-only filesystem."""
    event = current_event_id(bootstrap)
    if not event or not current_event_finished(bootstrap):
        return
    if nint(ownership.get("loaded_managers")) < len(managers):
        return
    try:
        phase, month_df = current_month_table(managers, bootstrap)
        payload = snapshot_store.make_payload(
            season=season_label(bootstrap),
            event=int(event),
            managers=managers,
            ownership=ownership,
            month_name=str((phase or {}).get("name") or ""),
            month_table=month_df.to_dict("records") if not month_df.empty else [],
        )
        snapshot_store.write(payload, replace=False)
        if int(event) >= 38:
            snapshot_store.freeze_season_final(payload)
    except Exception:
        return


def fixture_score(f: dict, teams: dict[int, str]) -> str:
    home = teams.get(nint(f.get("team_h")), "?")
    away = teams.get(nint(f.get("team_a")), "?")
    hs = f.get("team_h_score")
    aas = f.get("team_a_score")
    minute = nint(f.get("minutes"))
    base = f"{home} {nint(hs)}–{nint(aas)} {away}"
    return f"{base} · {minute}'" if minute else f"{base} · LIVE"


def _live_player_meta(row: dict, ownership: dict) -> str:
    bits = []
    goals = nint(row.get("live_goals"))
    assists = nint(row.get("live_assists"))
    bonus = nint(row.get("live_bonus"))
    if goals:
        bits.append(f"{goals} mål")
    if assists:
        bits.append(f"{assists} assist" if assists == 1 else f"{assists} assists")
    if bonus:
        bits.append(f"{bonus} bonus")
    owners = list(row.get("owners") or [])
    if owners:
        shown = ", ".join(owners[:3])
        if len(owners) > 3:
            shown += f" +{len(owners) - 3}"
        bits.append(f"Eies av {shown}")
    captain_count = nint(row.get("captain_count"))
    tc_names = list(row.get("triple_captains") or [])
    if captain_count:
        bits.append(f"{captain_count} kaptein" if captain_count == 1 else f"{captain_count} kapteiner")
    if tc_names:
        bits.append("TC: " + ", ".join(tc_names[:2]) + (f" +{len(tc_names)-2}" if len(tc_names) > 2 else ""))
    return " · ".join(bits)


def _live_manager_rows(ownership: dict, managers: list[dict], top: int = 5) -> list[dict]:
    events = ownership.get("manager_events", pd.DataFrame())
    if events is None or events.empty or "live_gw_points" not in events.columns:
        return []
    table = events.copy()
    table["live_gw_points"] = pd.to_numeric(table["live_gw_points"], errors="coerce").fillna(0).astype(int)
    table = table.sort_values(["live_gw_points", "manager"], ascending=[False, True]).reset_index(drop=True)
    table["live_rank"] = range(1, len(table) + 1)
    chosen = table.head(top).copy()
    me = my_manager_id(managers)
    if me and me not in set(chosen["entry"].astype(int).tolist()):
        mine = table[table["entry"].astype(int) == int(me)]
        if not mine.empty:
            chosen = pd.concat([chosen.head(max(0, top - 1)), mine.head(1)], ignore_index=True)
    rows = []
    for r in chosen.to_dict("records"):
        chip = str(r.get("active_chip") or "").strip()
        meta = str(r.get("team") or "")
        if chip:
            meta += (" · " if meta else "") + chip
        rows.append({
            "rank": nint(r.get("live_rank")),
            "who": str(r.get("manager") or ""),
            "meta": meta,
            "num": f"{nint(r.get('live_gw_points'))} poeng",
            "href": manager_href(nint(r.get("entry"))) if nint(r.get("entry")) else "",
        })
    return rows


def _live_beneficiary_rows(ownership: dict, player_row: dict, top: int = 5) -> list[dict]:
    """Managers receiving actual live points from the standout player."""
    picks = ownership.get("picks", pd.DataFrame())
    events = ownership.get("manager_events", pd.DataFrame())
    if picks is None or picks.empty:
        return []
    element = nint(player_row.get("element"))
    if not element:
        return []
    block = picks[picks["element"].astype(int) == int(element)].copy()
    if block.empty:
        return []
    # multiplier=0 means the player is stranded on the bench and is not currently
    # helping that manager. Bench Boost has already been normalised to x1.
    block["gw_contribution"] = pd.to_numeric(block.get("gw_contribution", 0), errors="coerce").fillna(0).astype(int)
    block = block[block["gw_contribution"] > 0].copy()
    if block.empty:
        return []
    live_totals = {}
    if events is not None and not events.empty and "live_gw_points" in events.columns:
        live_totals = {nint(r.get("entry")): nint(r.get("live_gw_points")) for r in events.to_dict("records")}
    block["live_total"] = block["entry"].map(lambda x: live_totals.get(nint(x), 0))
    block = block.sort_values(["gw_contribution", "live_total", "manager"], ascending=[False, False, True]).head(top)
    rows = []
    for r in block.to_dict("records"):
        role = "TC" if bool(r.get("is_triple_captain")) else "C" if bool(r.get("is_captain")) else ""
        meta = str(r.get("team") or "")
        if role:
            meta += (" · " if meta else "") + role
        rows.append({
            "rank": role,
            "who": str(r.get("manager") or ""),
            "meta": meta,
            "num": f"+{nint(r.get('gw_contribution'))} fra {player_row.get('player')}",
            "href": manager_href(nint(r.get("entry"))) if nint(r.get("entry")) else "",
        })
    return rows


def render_live(
    managers: list[dict],
    bootstrap: dict,
    compact: bool = False,
    ownership: dict | None = None,
    allow_blocking_ownership: bool = True,
) -> bool:
    """Render a compact live newsroom: score, impact, month race and GW race."""
    active, teams = active_fixtures(bootstrap)
    if not active:
        return False
    event = current_event_id(bootstrap)
    ui.live_scoreboard([fixture_score(f, teams) for f in active], f"GW{event}")

    base = ownership
    if base is None and allow_blocking_ownership:
        base = selected_ownership(managers)
    if not base:
        st.caption("Henter Lofthus-poengene i bakgrunnen …")
        return True

    try:
        fresh = refresh_ownership_live(base, client.event_live(int(event))) if event else base
    except Exception:
        fresh = base

    players = fresh.get("players", pd.DataFrame())
    active_teams = {nint(f.get(k)) for f in active for k in ("team_h", "team_a")}
    live_players = players[players["team_id"].isin(active_teams)].copy() if players is not None and not players.empty else pd.DataFrame()
    if not live_players.empty:
        for col in ["event_points", "captain_count", "triple_captain_count", "ownership_count", "live_goals", "live_assists", "live_bonus"]:
            if col not in live_players.columns:
                live_players[col] = 0
        live_players["importance"] = (
            pd.to_numeric(live_players["event_points"], errors="coerce").fillna(0) * 7
            + pd.to_numeric(live_players["live_goals"], errors="coerce").fillna(0) * 6
            + pd.to_numeric(live_players["live_assists"], errors="coerce").fillna(0) * 4
            + pd.to_numeric(live_players["triple_captain_count"], errors="coerce").fillna(0) * 12
            + pd.to_numeric(live_players["captain_count"], errors="coerce").fillna(0) * 4
            + pd.to_numeric(live_players["ownership_count"], errors="coerce").fillna(0)
        )
        live_players = live_players.sort_values(["importance", "event_points", "player"], ascending=[False, False, True]).reset_index(drop=True)

    standout = live_players.iloc[0].to_dict() if not live_players.empty else {}
    beneficiary_rows = _live_beneficiary_rows(fresh, standout, top=5 if compact else 8) if standout else []
    manager_rows = _live_manager_rows(fresh, managers, top=5 if compact else 8)
    phase, month_df, month_live = current_month_live_table(managers, bootstrap, fresh)

    # Newspaper logic: one live strip, then three small columns. The point is to
    # answer 'what is happening and who benefits?' without creating another long page.
    c1, c2, c3 = st.columns([1.2, 1, 1], gap="large")
    with c1:
        title = f"Hvem profiterer på {standout.get('player')}?" if standout else "Hvem profiterer?"
        ui.live_label(title)
        if standout:
            owners = nint(standout.get("ownership_count")); caps = nint(standout.get("captain_count")); pts = nint(standout.get("event_points"))
            st.caption(f"{pts} poeng live · {owners} eiere" + (f" · {caps} kaptein" if caps == 1 else f" · {caps} kapteiner" if caps > 1 else ""))
        if beneficiary_rows:
            ui.rows(beneficiary_rows)
        elif standout:
            st.caption("Ingen får tellende poeng fra spilleren akkurat nå.")
        else:
            st.caption("Ingen Lofthus-spiller har rukket å gjøre utslag ennå.")
    with c2:
        month_title = f"{phase.get('name')} · live" if phase and month_live else "Månedskampen"
        ui.live_label(month_title)
        if phase and month_live and not month_df.empty:
            ui.rows([{
                "rank": nint(r.get("rank")), "who": str(r.get("manager") or ""), "meta": str(r.get("team") or ""),
                "num": f"{nint(r.get('points'))} poeng",
                "href": manager_href(nint(r.get("entry"))) if nint(r.get("entry")) else "",
            } for r in month_df.head(5 if compact else 8).to_dict("records")])
        else:
            st.caption("Live månedstabell kommer når hele ligaens lagdata er klare.")
    with c3:
        ui.live_label(f"GW{event} · live")
        if manager_rows:
            ui.rows(manager_rows)
        else:
            st.caption("Live managerpoeng kommer så snart lagdataene er klare.")

    if not compact and not live_players.empty:
        ui.live_label("Andre spillere på banen")
        ui.rows([{
            "rank": "TC" if nint(r.get("triple_captain_count")) else "C" if nint(r.get("captain_count")) else "",
            "who": str(r.get("player") or ""), "meta": _live_player_meta(r, fresh),
            "num": f"{nint(r.get('event_points'))} poeng",
        } for r in live_players.head(8).to_dict("records")])
    data_quality_note(fresh)
    return True


@st.fragment(run_every="30s")
def render_home_live_fragment(managers: list[dict], bootstrap: dict) -> None:
    """Auto-updating live strip without rerunning the rest of the front page."""
    ownership = home_ownership_async(managers, bootstrap)
    render_live(
        managers,
        bootstrap,
        compact=True,
        ownership=ownership,
        allow_blocking_ownership=False,
    )


@st.fragment(run_every="60s")
def render_home_news_fragment(managers: list[dict], bootstrap: dict) -> None:
    """Refresh the newspaper desk without moving the rest of the page."""
    ownership = home_ownership_async(managers, bootstrap)
    histories = home_histories_async(managers)
    if ownership and current_event_id(bootstrap) and not current_event_finished(bootstrap):
        try:
            ownership = refresh_ownership_live(ownership, client.event_live(int(current_event_id(bootstrap))))
        except Exception:
            pass
    news, popular = st.columns([1.7, 0.8], gap="large")
    with news:
        ui.front_section("Snakkiser", "De største sakene akkurat nå")
        story_items = front_stories(managers, bootstrap, ownership, histories)
        if not story_items:
            story_items = ["Ligaen er i gang. Vi publiserer først når det faktisk har skjedd noe."]
        ui.editorial_stories(story_items[:4])
    with popular:
        ui.front_section("Mest populære", "Topp 3 i Lofthus")
        if ownership is None:
            st.caption("Henter eierskap i bakgrunnen …")
        else:
            render_popular(ownership, top=3)


def _fresh_home_ownership(managers: list[dict], bootstrap: dict) -> dict | None:
    ownership = home_ownership_async(managers, bootstrap)
    event = current_event_id(bootstrap) or 0
    if ownership and event and not current_event_finished(bootstrap):
        try:
            return refresh_ownership_live(ownership, client.event_live(int(event)))
        except Exception:
            return ownership
    return ownership


@st.fragment(run_every="30s")
def render_home_scoreline_fragment(managers: list[dict], bootstrap: dict) -> None:
    """Keep the compact headline strip honest during a live round."""
    ownership = _fresh_home_ownership(managers, bootstrap)
    histories = home_histories_async(managers)
    move = round_movements(managers, history_store)
    leader = move.get("leader", {})
    previous = previous_completed_round(managers, bootstrap, histories)
    winner = previous.get("gw_winner") or (move.get("gw_winner", {}) if current_event_finished(bootstrap) else {})

    live_phase, live_month_df, live_month = current_month_live_table(managers, bootstrap, ownership)
    if live_phase and live_month:
        display_phase, month_df, month_is_live = live_phase, live_month_df, True
    else:
        display_phase, month_df, month_is_live = display_month_table(managers, bootstrap)
    month_leader = month_df.iloc[0].to_dict() if not month_df.empty else {}
    if display_phase:
        month_name = str(display_phase.get("name") or "måneden").lower()
        month_label = f"Leder {month_name} måned" if month_is_live else f"Vinner av {month_name} måned"
    else:
        month_label = "Månedskampen"
    ui.home_scoreline(
        str(leader.get("manager") or "–"),
        nint(leader.get("points"), nint(leader.get("total"))),
        str(winner.get("manager") or "–"),
        nint(winner.get("gw")),
        str(month_leader.get("manager") or "–"),
        month_label,
    )


@st.fragment(run_every="30s")
def render_home_tables_fragment(managers: list[dict], bootstrap: dict) -> None:
    """Keep the front page lean: one league table, not another two-column dashboard.

    The current-month leader still lives in the headline/status layer above, so the
    September race remains visible without burning an entire front-page column.
    """
    ui.front_section("Topp 5", "Sammenlagt")
    top = sorted(managers, key=lambda m: (nint(m.get("rank"), 10**9), -nint(m.get("total"))))[:5]
    ui.rows([{
        "rank": nint(m.get("rank")),
        "rank_class": "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else "",
        "who": manager_name(m),
        "meta": str(m.get("entry_name") or ""),
        "num": f"{nint(m.get('total'))} poeng",
        "href": manager_href(nint(m.get("entry"))) if nint(m.get("entry")) else "",
    } for i, m in enumerate(top)])


def render_month(
    managers: list[dict],
    bootstrap: dict,
    top: int = 5,
    front: bool = False,
    ownership: dict | None = None,
    prefer_live: bool = False,
) -> None:
    if prefer_live and ownership:
        phase, df, is_current_live = current_month_live_table(managers, bootstrap, ownership)
        if not is_current_live:
            phase, df, is_current_live = display_month_table(managers, bootstrap)
    else:
        phase, df, is_current_live = display_month_table(managers, bootstrap)
    if phase is None:
        st.caption("Månedstabellen er ikke tilgjengelig akkurat nå.")
        return
    title = f"{phase['name']} · live" if is_current_live else phase["name"]
    (ui.front_section if front else ui.section)(title)
    ui.rows([
        {
            "rank": nint(r.get("rank")),
            "rank_class": "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else "",
            "who": r.get("manager"),
            "meta": r.get("team"),
            "num": f"{nint(r.get('points'))} poeng",
            "href": f"?page=Ligaen&league_view=Manager&manager={nint(r.get('entry'))}" if nint(r.get('entry')) else "",
        }
        for i, r in enumerate(df.head(top).to_dict("records"))
    ])


def _manager_neighborhood(managers: list[dict], entry: int, radius: int = 2) -> list[dict]:
    ordered = sorted(managers, key=lambda m: (nint(m.get("rank"), 10**9), -nint(m.get("total"))))
    idx = next((i for i, m in enumerate(ordered) if nint(m.get("entry")) == int(entry)), None)
    if idx is None:
        return []
    lo = max(0, idx - radius)
    hi = min(len(ordered), idx + radius + 1)
    return [m for m in ordered[lo:hi] if nint(m.get("entry")) != int(entry)]


def suggested_rival_entries(managers: list[dict], bootstrap: dict, entry: int, limit: int = 5) -> list[int]:
    """Managers who matter now: three ahead, two behind, plus nearby month rivals."""
    ordered = sorted(managers, key=lambda m: (nint(m.get("rank"), 10**9), -nint(m.get("total"))))
    idx = next((i for i, m in enumerate(ordered) if nint(m.get("entry")) == int(entry)), None)
    if idx is None:
        return []
    picks: list[int] = []
    ahead = list(reversed(ordered[max(0, idx - 3):idx]))
    behind = ordered[idx + 1:idx + 3]
    for m in ahead + behind:
        eid = nint(m.get("entry"))
        if eid and eid != int(entry) and eid not in picks:
            picks.append(eid)

    # Month neighbours matter when the monthly race has real points. Do not let a
    # zero-point alphabetical table manufacture rivals.
    try:
        _, month_df = current_month_table(managers, bootstrap)
        if not month_df.empty and int(pd.to_numeric(month_df["points"], errors="coerce").fillna(0).sum()) > 0:
            month_ordered = month_df.sort_values(["rank", "manager"]).reset_index(drop=True)
            hit = month_ordered.index[month_ordered["entry"] == int(entry)].tolist()
            if hit:
                mi = int(hit[0])
                for r in month_ordered.iloc[max(0, mi - 2):mi + 3].to_dict("records"):
                    eid = nint(r.get("entry"))
                    if eid and eid != int(entry) and eid not in picks:
                        picks.append(eid)
    except Exception:
        pass
    return picks[:limit]


def render_my_lofthus(managers: list[dict], bootstrap: dict, ownership: dict) -> int:
    opts = manager_options(managers)
    ids = [x[0] for x in opts]
    labels = dict(opts)
    if not ids:
        return 0
    if st.session_state.get("v500_my_manager") is not None and nint(st.session_state.get("v500_my_manager")) not in ids:
        st.session_state.pop("v500_my_manager", None)
    remembered = my_manager_id(managers)
    index = ids.index(remembered) if remembered in ids else None
    if not remembered:
        st.markdown("<div class='v700-identity-picker'>", unsafe_allow_html=True)
        selected = st.selectbox(
            "Gjør forsiden personlig",
            ids,
            index=index,
            placeholder="Hvem er du i Lofthus?",
            format_func=lambda x: labels.get(int(x), str(x)),
            key="v500_my_manager",
        )
        st.markdown("</div>", unsafe_allow_html=True)
        if selected is None:
            return 0
        remembered = int(selected)
    else:
        st.session_state["v500_my_manager"] = int(remembered)

    selected = int(remembered)
    st.session_state["v400_my_manager"] = selected
    try:
        st.query_params["me"] = str(selected)
    except Exception:
        pass
    me = manager_map(managers).get(selected)
    if not me:
        return 0

    ordered = sorted(managers, key=lambda m: (nint(m.get("rank"), 10**9), -nint(m.get("total"))))
    my_rank = nint(me.get("rank")); my_points = nint(me.get("total"))
    above = next((m for m in ordered if nint(m.get("rank")) == my_rank - 1), None)
    below = next((m for m in ordered if nint(m.get("rank")) == my_rank + 1), None)
    fifth = next((m for m in ordered if nint(m.get("rank")) == 5), ordered[min(4, len(ordered)-1)] if ordered else None)
    gap_top5 = max(0, nint(fifth.get("total")) - my_points + 1) if fifth and my_rank > 5 else 0
    gap_above = max(0, nint(above.get("total")) - my_points + 1) if above else 0
    movement = nint(me.get("last_rank"), my_rank) - my_rank

    live_phase, live_month_df, live_month = current_month_live_table(managers, bootstrap, ownership)
    if live_phase and live_month:
        phase, month_df = live_phase, live_month_df
        month_name = f"{str(phase.get('name') or 'Måneden')} · live"
    else:
        phase, month_df, _ = display_month_table(managers, bootstrap)
        month_name = str(phase.get("name") or "Måneden") if phase else "Måneden"
    month_hit = month_df[month_df["entry"] == selected] if not month_df.empty else pd.DataFrame()
    month_rank = nint(month_hit.iloc[0].get("rank")) if not month_hit.empty else 0

    if above:
        gap_metric = (gap_above, f"poeng til {manager_name(above)}")
    else:
        gap_metric = ("–", "ingen foran")
    top_metric = ("Inne", "topp 5") if my_rank <= 5 else (gap_top5, "poeng til topp 5")
    month_metric = (f"{month_rank}." if month_rank else "–", month_name)
    motion = f"↑ {movement} plasser forrige runde" if movement > 0 else f"↓ {abs(movement)} plasser forrige runde" if movement < 0 else "Samme plass som før forrige runde"
    chase = f"{manager_name(above)} er nærmest foran" if above else "Du leder ligaen"
    if below:
        chase += f" · {manager_name(below)} følger bak"
    player_angle = ""
    picks = ownership.get("picks", pd.DataFrame()) if ownership else pd.DataFrame()
    players = ownership.get("players", pd.DataFrame()) if ownership else pd.DataFrame()
    if not picks.empty and selected in set(pd.to_numeric(picks.get("entry"), errors="coerce").dropna().astype(int).tolist()):
        mine = picks[picks["entry"] == selected]
        cap = mine[mine["is_captain"]]
        if not cap.empty:
            crow = cap.iloc[0]
            player_angle = f"Din kaptein er {crow.get('player')}"
        if above is not None and not players.empty:
            rival_entry = nint(above.get("entry"))
            rival = picks[picks["entry"] == rival_entry]
            if not rival.empty:
                mine_ids = set(mine[~mine["on_bench"]]["element"].astype(int).tolist())
                rival_ids = set(rival[~rival["on_bench"]]["element"].astype(int).tolist())
                pmap = {nint(r.get("element")): r for r in players.to_dict("records")}
                mine_only = sorted(mine_ids - rival_ids, key=lambda pid: -nint(pmap.get(pid, {}).get("season_points")))
                if mine_only:
                    pname = pmap.get(mine_only[0], {}).get("player")
                    if pname:
                        player_angle += (" · " if player_angle else "") + f"{pname} skiller deg fra {manager_name(above)}"
    insight = f"{motion} · {chase}" + (f" · {player_angle}" if player_angle else "")
    ui.personal_home_lead(manager_name(me), str(me.get("entry_name") or ""), my_rank, my_points, [gap_metric, top_metric, month_metric], insight)
    return selected

def render_home(managers: list[dict], bootstrap: dict) -> None:
    """Personal newspaper front page: breaking live, tables, then the news desk."""
    # Kick off both expensive league-wide jobs immediately, but never make the
    # visible front page wait for them.
    ownership = home_ownership_async(managers, bootstrap)
    home_histories_async(managers)
    selected = render_my_lofthus(managers, bootstrap, ownership or {})

    # Without a personal identity, the compact headline strip is itself live-aware.
    # It therefore switches from an August winner to a September live leader as
    # soon as the first September points exist.
    if not selected:
        render_home_scoreline_fragment(managers, bootstrap)

    # LIVE is breaking news, so it belongs high on the front page. It only exists
    # while a Premier League match is actually in progress.
    render_home_live_fragment(managers, bootstrap)

    # The two structural lead tables refresh independently. The monthly table
    # turns into the new month's LIVE race immediately, instead of clinging to August.
    render_home_tables_fragment(managers, bootstrap)

    render_home_news_fragment(managers, bootstrap)

    # Personal rival strip: only when the owner is known, and only a few names.
    if selected:
        suggested = suggested_rival_entries(managers, bootstrap, selected, limit=4)
        mmap = manager_map(managers); me = mmap.get(selected, {})
        if suggested:
            ui.front_section("Dine nærmeste rivaler", "Automatisk valgt fra tabellen og månedskampen")
            rows_data = []
            my_points = nint(me.get("total"))
            for eid in suggested[:4]:
                rival = mmap.get(eid)
                if not rival:
                    continue
                diff = nint(rival.get("total")) - my_points
                relation = f"{abs(diff)} poeng foran deg" if diff > 0 else f"{abs(diff)} poeng bak deg" if diff < 0 else "likt med deg"
                rows_data.append({"rank": f"{nint(rival.get('rank'))}.", "who": manager_name(rival), "meta": str(rival.get("entry_name") or ""), "num": relation, "href": manager_href(eid)})
            ui.rows(rows_data)
            if st.button("Analyser disse i Rivalradar", key="v700_home_rivals", use_container_width=True):
                st.session_state["v400_my_manager"] = selected
                st.session_state["v400_rivals"] = suggested[:4]
                st.session_state["v700_rivals"] = suggested[:4]
                st.session_state["v700_rivals_owner"] = selected
                st.session_state["v400_main_page"] = "Rivalradar"
                st.session_state["v406_rival_view"] = "Rivaler"
                st.rerun()


def captain_board_rows(ownership: dict) -> list[dict]:
    players = ownership.get("players", pd.DataFrame())
    if players.empty:
        return []
    caps = players[players["captain_count"] > 0].sort_values(["captain_count", "triple_captain_count", "player"], ascending=[False, False, True])
    board_rows = []
    for r in caps.to_dict("records"):
        triples = set(r.get("triple_captains") or [])
        people = [{"name": name, "tc": name in triples} for name in (r.get("captains") or [])]
        board_rows.append({
            "player": r.get("player"),
            "regular": max(0, nint(r.get("captain_count")) - nint(r.get("triple_captain_count"))),
            "tc": nint(r.get("triple_captain_count")),
            "points": nint(r.get("event_points")),
            "people": people,
        })
    return board_rows


def render_captains(ownership: dict) -> None:
    rows = captain_board_rows(ownership)
    if not rows:
        st.caption("Kapteinsdata er ikke tilgjengelig akkurat nå.")
        return
    ui.captain_board(rows)

def render_popular(ownership: dict, top: int = 10) -> None:
    players = ownership.get("players", pd.DataFrame())
    if players.empty:
        st.caption("Eierskapsdata mangler.")
        return
    total = nint(ownership.get("loaded_managers"))
    ui.rows([
        {
            "rank": i + 1,
            "who": r.get("player"),
            "meta": f"{r.get('club')} · {r.get('position')} · {fmt_price(r.get('current_price'))}",
            "num": f"{nint(r.get('ownership_count'))}/{total} · {fmt_pct(r.get('ownership_pct'))}",
        }
        for i, r in enumerate(players.sort_values(["ownership_count", "player"], ascending=[False, True]).head(top).to_dict("records"))
    ])


def render_player_profile(player: dict, ownership: dict, bootstrap: dict) -> None:
    total = nint(ownership.get("loaded_managers"))
    ui.profile_header(str(player.get("player") or ""), f"{player.get('club')} · {player.get('position')} · {fmt_price(player.get('current_price'))}")
    ui.stat_strip([
        (f"{nint(player.get('ownership_count'))}/{total}", "Lofthus-eiere"),
        (f"{nfloat(player.get('fpl_ownership_pct')):.1f}%", "FPL-eierskap"),
        (nint(player.get("captain_count")), "Kapteiner"),
        (nint(player.get("triple_captain_count")), "Triple Captain"),
        (nint(player.get("bench_count")), "På benken"),
        (f"{nint(player.get('event_points'))} poeng", "Denne GW"),
    ])
    captains = player.get("captains") or []
    triples = set(player.get("triple_captains") or [])
    if captains:
        ui.section("Kaptein hos")
        ui.rows([
            {"rank": "TC" if name in triples else "C", "who": name, "meta": "Triple Captain" if name in triples else "Kaptein", "num": ""}
            for name in captains[:8]
        ])
        if len(captains) > 8:
            with st.expander(f"Se alle {len(captains)} kapteiner"):
                st.write(" · ".join(captains))
    owners = player.get("owners") or []
    if owners:
        with st.expander(f"Se alle {len(owners)} eiere"):
            st.write(" · ".join(owners))
    benched = player.get("benched_by") or []
    if benched:
        ui.callout("På benken", ", ".join(benched))
    regular = nint(player.get("ownership_count")) - nint(player.get("captain_count"))
    without = max(0, total - nint(player.get("ownership_count")))
    sentence = f"{nint(player.get('triple_captain_count'))} får trippel, {max(0, nint(player.get('captain_count')) - nint(player.get('triple_captain_count')))} får dobbelt, {max(0, regular)} får vanlige poeng og {without} har ham ikke."
    ui.callout(f"Hvis {player.get('player')} leverer", sentence, "green")


def render_player_search(ownership: dict, key: str) -> None:
    players = ownership.get("players", pd.DataFrame())
    if players.empty:
        return
    query = st.text_input("Søk etter spiller", placeholder="Skriv et spillernavn …", key=key)
    if not query.strip():
        return
    norm = normalize_text(query)
    candidates = players[
        players.apply(lambda r: norm in normalize_text(f"{r.get('player','')} {r.get('full_name','')} {r.get('club','')}"), axis=1)
    ].copy()
    if candidates.empty:
        st.caption("Fant ingen spiller.")
        return
    candidates = candidates.sort_values(["ownership_count", "player"], ascending=[False, True]).head(8)
    if len(candidates) > 1:
        choices = candidates["element"].astype(int).tolist()
        label_map = {nint(r["element"]): f"{r['player']} · {r['club']}" for r in candidates.to_dict("records")}
        element = st.selectbox("Treff", choices, format_func=lambda x: label_map.get(int(x), str(x)), key=f"{key}_choice")
        row = candidates[candidates["element"] == int(element)].iloc[0].to_dict()
    else:
        row = candidates.iloc[0].to_dict()
    render_player_profile(row, ownership, client.bootstrap())


def render_season(managers: list[dict], bootstrap: dict, embedded: bool = False) -> None:
    if not embedded:
        ui.page_title("Spilleroversikt", "Finn svaret raskt. Detaljene ligger ett klikk unna.")
    render_live(managers, bootstrap, compact=True)
    with st.spinner("Henter Lofthus-lag …"):
        ownership = selected_ownership(managers)
    data_quality_note(ownership)
    ui.section("Finn spiller")
    render_player_search(ownership, "v700_player_search")
    players = ownership.get("players", pd.DataFrame())
    cap_rows = captain_board_rows(ownership)
    c1, c2, c3 = st.columns([1.1, 1, 1], gap="large")
    with c1:
        st.markdown("<div class='v605-mini-head'><div class='v605-mini-title'>Kapteiner</div><div class='v605-mini-note'>Topp 5</div></div>", unsafe_allow_html=True)
        mini = []
        for i, r in enumerate(cap_rows[:5], start=1):
            bits = []
            if nint(r.get("regular")): bits.append(f"{nint(r.get('regular'))} C")
            if nint(r.get("tc")): bits.append(f"{nint(r.get('tc'))} TC")
            people = [p.get("name") for p in (r.get("people") or []) if p.get("name")]
            mini.append({"rank": i, "who": r.get("player"), "meta": ", ".join(people[:2]) + (f" +{len(people)-2}" if len(people) > 2 else ""), "num": " · ".join(bits)})
        ui.rows(mini)
    with c2:
        st.markdown("<div class='v605-mini-head'><div class='v605-mini-title'>Mest eide</div><div class='v605-mini-note'>Topp 5</div></div>", unsafe_allow_html=True)
        render_popular(ownership, top=5)
    with c3:
        st.markdown("<div class='v605-mini-head'><div class='v605-mini-title'>Differensialer</div><div class='v605-mini-note'>Lavt eid · leverer</div></div>", unsafe_allow_html=True)
        if not players.empty:
            current = current_event_id(bootstrap) or 1
            dif = players[(players["ownership_count"].between(1, 6)) & ((players["season_points"] >= max(6, current * 3)) | (players["event_points"] >= 4))]
            dif = dif.sort_values(["event_points", "season_points", "ownership_count"], ascending=[False, False, True]).head(5)
            rows_data = []
            for i, r in enumerate(dif.to_dict("records"), start=1):
                owners = [str(name) for name in (r.get("owners") or []) if str(name).strip()]
                form = nfloat(r.get("form"))
                why = f"{nint(r.get('event_points'))} poeng denne GW · {nint(r.get('season_points'))} totalt"
                if form > 0:
                    why += f" · form {form:.1f}"
                count = nint(r.get("ownership_count"))
                rows_data.append({
                    "rank": i, "who": r.get("player"),
                    "meta_prefix": f"{r.get('club')} · {r.get('position')} · {why} · Eies av:",
                    "meta_links": owner_links(owners, managers, limit=3),
                    "num": f"{count} eier" if count == 1 else f"{count} eiere",
                })
            ui.rows(rows_data)
        else:
            st.caption("Ingen spillerdata akkurat nå.")
    with st.expander("Full kapteinsoversikt"):
        ui.captain_board(cap_rows)
    st.caption("Månedstabell og rundebevegelser ligger på forsiden og i Ligaen. Spilleroversikt holder seg til spillerne.")

def current_league_table_meta(managers: list[dict], bootstrap: dict) -> dict[int, dict]:
    """Fetch captain + chip once for the league table and cache the result.

    This deliberately shares one picks_many sweep. Previously the table only knew
    about chips, even though the same FPL payload already contained captaincy.
    """
    event_id = current_event_id(bootstrap)
    if not event_id:
        return {}
    entries = tuple(sorted(nint(m.get("entry")) for m in managers if nint(m.get("entry"))))
    cache_key = f"v704_league_meta_{event_id}_{','.join(map(str, entries))}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    payloads, _ = client.picks_many(entries, int(event_id), max_workers=10)
    catalog = player_catalog(bootstrap)
    out: dict[int, dict] = {}
    for entry, payload in payloads.items():
        picks = payload.get("picks", []) or []
        active_chip = chip_label(payload.get("active_chip"))
        captain_pick = next((p for p in picks if p.get("is_captain")), None)
        captain = "–"
        captain_short = ""
        if captain_pick:
            player = catalog.get(nint(captain_pick.get("element")), {}).get("web_name")
            if player:
                is_tc = active_chip == "Triple Captain" or nint(captain_pick.get("multiplier")) >= 3
                captain_short = str(player)
                captain = f"{player} ({'TC' if is_tc else 'C'})"
        out[int(entry)] = {
            "captain": captain,
            "captain_name": captain_short,
            "chip": active_chip,
        }
    st.session_state[cache_key] = out
    return out


def _league_open_manager(entry: int) -> None:
    entry = int(entry)
    st.session_state["v405_league_view"] = "Manager"
    st.session_state["v400_manager_select"] = entry
    try:
        st.query_params["page"] = "Ligaen"
        st.query_params["league_view"] = "Manager"
        st.query_params["manager"] = str(entry)
    except Exception:
        pass


def _league_compare_manager(entry: int) -> None:
    entry = int(entry)
    selected = [nint(x) for x in (st.session_state.get("v400_compare_entries") or []) if nint(x)]
    if entry not in selected:
        selected.insert(0, entry)
    st.session_state["v400_compare_entries"] = selected[:8]
    st.session_state["v405_league_view"] = "Sammenlign"
    try:
        st.query_params["page"] = "Ligaen"
        st.query_params["league_view"] = "Sammenlign"
        st.query_params.pop("manager", None)
    except Exception:
        pass


def render_league_table(managers: list[dict], bootstrap: dict) -> None:
    """Native Streamlit league table with a real click menu on every manager.

    The old iframe table looked clickable, but its cross-frame URL navigation was
    brittle. A native popover makes the manager name itself the menu trigger and
    guarantees that "Se laget" actually reaches the manager profile.
    """
    try:
        with st.spinner("Henter kapteiner …"):
            meta_by_entry = current_league_table_meta(managers, bootstrap)
    except Exception:
        meta_by_entry = {}

    event_id = current_event_id(bootstrap) or 0
    if event_id and not current_event_finished(bootstrap):
        st.caption(f"GW{event_id} pågår · poeng og tabellendringer er live.")

    st.markdown(
        """
        <style>
        div[data-testid="stPopover"] > div > button {
            background: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            padding: 0 !important;
            min-height: 1.7rem !important;
            color: #005aa6 !important;
            font-weight: 900 !important;
            justify-content: flex-start !important;
            text-decoration: underline !important;
            text-underline-offset: 3px !important;
        }
        div[data-testid="stPopover"] > div > button:hover {
            color: #003f76 !important;
            background: transparent !important;
        }
        .v704-lh {color:#687386;font-size:.69rem;text-transform:uppercase;letter-spacing:.075em;font-weight:900;padding:.25rem 0 .45rem}
        .v704-cell {font-size:.91rem;font-weight:750;padding:.18rem 0;line-height:1.25}
        .v704-team {font-size:.91rem;font-weight:800;line-height:1.2}
        .v704-sub {color:#687386;font-size:.76rem;font-weight:700;line-height:1.2;margin-top:.12rem}
        .v704-num {font-size:.91rem;font-weight:900;text-align:right;padding:.18rem 0;white-space:nowrap}
        .v704-rank {font-size:.91rem;font-weight:900;color:#687386;padding:.18rem 0}
        .v704-up {color:#167a52}.v704-down {color:#b63a34}
        .v704-divider {border-top:1px solid #d6d9de;margin:.42rem 0 .34rem}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # # / manager / team / captain / GW / points / movement
    widths = [0.55, 2.35, 2.65, 1.75, 0.75, 0.9, 0.7]
    headers = ["#", "Manager", "Lag", "Kaptein", "GW", "Poeng", "+/-"]
    hcols = st.columns(widths, gap="small")
    for i, (col, label) in enumerate(zip(hcols, headers)):
        align = "text-align:right" if i >= 4 else ""
        col.markdown(f"<div class='v704-lh' style='{align}'>{label}</div>", unsafe_allow_html=True)
    st.markdown("<div class='v704-divider'></div>", unsafe_allow_html=True)

    ordered = sorted(managers, key=lambda m: (nint(m.get("rank"), 10**9), -nint(m.get("total")), normalize_text(manager_name(m))))
    for m in ordered:
        rank = nint(m.get("rank"), 10**9)
        last = nint(m.get("last_rank"), rank)
        move = last - rank if rank < 10**9 else 0
        entry = nint(m.get("entry"))
        team_name = str(m.get("entry_name") or "").strip()
        meta = meta_by_entry.get(entry, {})
        captain = str(meta.get("captain") or "–")
        chip = str(meta.get("chip") or "").strip()

        cols = st.columns(widths, gap="small")
        cols[0].markdown(f"<div class='v704-rank'>{rank if rank < 10**9 else '–'}</div>", unsafe_allow_html=True)
        with cols[1]:
            with st.popover(manager_name(m)):
                st.markdown(f"**{manager_name(m)}**")
                st.caption(team_name or "Uten lagnavn")
                st.caption(f"{rank if rank < 10**9 else '–'}. plass · {nint(m.get('total'))} poeng · Kaptein: {captain}")
                st.button("Se laget", key=f"v704_open_{entry}", use_container_width=True, on_click=_league_open_manager, args=(entry,))
                st.button("Sammenlign", key=f"v704_compare_{entry}", use_container_width=True, on_click=_league_compare_manager, args=(entry,))
        team_sub = f"<div class='v704-sub'>{chip}</div>" if chip else ""
        cols[2].markdown(f"<div class='v704-team'>{ui.esc(team_name)}</div>{team_sub}", unsafe_allow_html=True)
        cols[3].markdown(f"<div class='v704-cell'>{ui.esc(captain)}</div>", unsafe_allow_html=True)
        cols[4].markdown(f"<div class='v704-num'>{nint(m.get('event_total'))}</div>", unsafe_allow_html=True)
        cols[5].markdown(f"<div class='v704-num'>{nint(m.get('total'))}</div>", unsafe_allow_html=True)
        move_text = f"↑{move}" if move > 0 else f"↓{abs(move)}" if move < 0 else "–"
        move_cls = "v704-up" if move > 0 else "v704-down" if move < 0 else ""
        cols[6].markdown(f"<div class='v704-num {move_cls}'>{move_text}</div>", unsafe_allow_html=True)
        st.markdown("<div class='v704-divider'></div>", unsafe_allow_html=True)

def render_form(managers: list[dict], entry: int, bootstrap: dict | None = None) -> tuple[dict, dict[int, dict]]:
    """Render recent form, using the live LRO score for an active GW.

    FPL's ``entry/{id}/history`` endpoint is not a live endpoint. During an
    active gameweek it can contain a current-GW row with 0/stale points even
    while the league table already has the manager's live score. The profile
    header therefore looked correct while the Form section claimed 0 points.

    Past GWs still come from entry history. Only the active GW is overlaid with
    the same live manager values used by the league table/profile header.
    """
    with st.spinner("Henter form …"):
        histories, errors = histories_for([nint(m.get("entry")) for m in managers])
    entry_history = histories.get(int(entry), {}) or {}
    form = manager_form_from_histories(managers, histories, int(entry), 5)

    current = current_event_id(bootstrap or {}) if bootstrap else None
    event_meta = next(
        (e for e in (bootstrap or {}).get("events", []) or [] if nint(e.get("id")) == nint(current)),
        None,
    )
    is_live = bool(event_meta and event_meta.get("is_current") and not event_meta.get("finished"))

    if is_live and current:
        selected = next((m for m in managers if nint(m.get("entry")) == int(entry)), None)
        if selected is not None:
            live_points = nint(selected.get("event_total"))
            live_total = nint(selected.get("total"))
            live_league_rank = nint(selected.get("rank"))
            # FPL ranking semantics: tied scores share the best applicable rank.
            live_round_rank = 1 + sum(
                1 for m in managers if nint(m.get("event_total")) > live_points
            )
            live_row = {
                "entry": int(entry),
                "manager": manager_name(selected),
                "event": int(current),
                "points": live_points,
                "total_points": live_total,
                "overall_rank": 0,
                "round_rank": live_round_rank,
                "league_rank": live_league_rank,
                "is_live": True,
            }
            if form.empty:
                form = pd.DataFrame([live_row])
            else:
                form = form[form["event"].map(nint) != int(current)].copy()
                form = pd.concat([form, pd.DataFrame([live_row])], ignore_index=True)
            form = form.sort_values("event").tail(5).reset_index(drop=True)

    if form.empty:
        own = entry_history.get("current", []) or []
        if own:
            own = own[-5:]
            ui.rows([{"rank": f"GW{nint(r.get('event'))}", "who": f"{nint(r.get('points'))} poeng", "meta": f"FPL-rank {nint(r.get('overall_rank')):,}".replace(",", " "), "num": ""} for r in own])
        else:
            st.caption("Formdata er ikke tilgjengelig.")
        return entry_history, histories

    rows = []
    for r in form.to_dict("records"):
        live_suffix = " · live" if bool(r.get("is_live")) else ""
        rows.append({
            "rank": f"GW{nint(r.get('event'))}",
            "who": f"{nint(r.get('points'))} poeng",
            "meta": f"{nint(r.get('round_rank'))}. beste i Lofthus{live_suffix}",
            "num": f"{nint(r.get('league_rank'))}. sammenlagt{live_suffix}",
        })
    ui.rows(rows)
    return entry_history, histories


def render_chip_history(entry_history: dict) -> None:
    chips = entry_history.get("chips", []) or []
    items = []
    for row in chips:
        label = chip_label(row.get("name"))
        event = nint(row.get("event"))
        if label:
            items.append(f"{label} GW{event}" if event else label)
    if items:
        ui.inline_note("Chips brukt", " · ".join(items))


def manager_merit_items(name: str, auto_rows: list[dict]) -> list[tuple[int, str]]:
    m = history_store.merits_for(name, auto_rows) or {}
    league_gold = nint(m.get("league_gold"))
    monthly_wins = nint(m.get("monthly_gold"))
    return [
        (league_gold, "sesongtittel" if league_gold == 1 else "sesongtitler"),
        (nint(m.get("league_silver")), "seriesølv"),
        (nint(m.get("league_bronze")), "seriebronse"),
        (nint(m.get("cup_gold")), "cupgull"),
        (monthly_wins, "månedsseier" if monthly_wins == 1 else "månedsseire"),
    ]


def render_merits(name: str, auto_rows: list[dict]) -> None:
    ui.honours_panel(manager_merit_items(name, auto_rows))

def _rank_text(value: Any) -> str:
    rank = nint(value)
    if rank <= 0:
        return "–"
    return f"#{rank:,}".replace(",", " ")


def career_summary(entry_history: dict) -> tuple[list[tuple[Any, str]], list[dict]]:
    past = entry_history.get("past", []) or []
    valid = [r for r in past if nint(r.get("rank")) > 0 or nint(r.get("total_points")) > 0]
    ranks = [nint(r.get("rank")) for r in valid if nint(r.get("rank")) > 0]
    points = [nint(r.get("total_points")) for r in valid if nint(r.get("total_points")) > 0]
    stats = [
        (_rank_text(min(ranks)) if ranks else "–", "Beste overall"),
        (f"{max(points):,}".replace(",", " ") if points else "–", "Høyeste poengsum"),
        (len(valid), "Tidligere sesonger"),
        (sum(1 for r in ranks if r <= 100_000), "Topp 100k"),
    ]
    seasons = []
    for r in reversed(valid[-5:]):
        seasons.append({
            "season": str(r.get("season_name") or ""),
            "points": f"{nint(r.get('total_points')):,}".replace(",", " "),
            "rank": _rank_text(r.get("rank")),
        })
    return stats, seasons


def preseason_odds_for_manager(managers: list[dict], histories: dict[int, dict], entry: int) -> tuple[str, str]:
    odds = pd.DataFrame()
    if PRESEASON_ODDS_FILE.exists():
        try:
            odds = pd.read_csv(PRESEASON_ODDS_FILE)
        except Exception:
            odds = pd.DataFrame()
    if odds.empty:
        try:
            odds = build_preseason_odds(managers, histories, history_store)
        except Exception:
            odds = pd.DataFrame()
    if odds.empty:
        return "–", "–"
    row = pd.DataFrame()
    if "entry" in odds.columns:
        row = odds[pd.to_numeric(odds["entry"], errors="coerce").fillna(0).astype(int) == int(entry)]
    if row.empty and "manager" in odds.columns:
        target_manager = manager_map(managers).get(int(entry))
        target = history_store.key(manager_name(target_manager)) if target_manager else ""
        if target:
            row = odds[odds["manager"].map(history_store.key) == target]
    if row.empty:
        return "–", "–"
    r = row.iloc[0]
    def f(v):
        try:
            return f"{float(v):.2f}"
        except Exception:
            return "–"
    return f(r.get("winner_odds")), f(r.get("top3_odds"))


def live_odds_for_manager(managers: list[dict], histories: dict[int, dict], bootstrap: dict, entry: int) -> tuple[str, str, str]:
    event = current_event_id(bootstrap) or 0
    signature = tuple((nint(m.get("entry")), nint(m.get("rank")), nint(m.get("total"))) for m in sorted(managers, key=lambda x: nint(x.get("entry"))))
    key = f"v700_live_market_{event}_{hash(signature)}"
    if key not in st.session_state:
        try:
            pre = _preseason_market(managers, histories)
            st.session_state[key] = build_live_market(managers, histories, event, history_store, preseason=pre)
        except Exception:
            st.session_state[key] = pd.DataFrame()
    result = st.session_state.get(key, pd.DataFrame())
    if result is None or result.empty:
        return "–", "", ""
    row = result[result["entry"] == int(entry)]
    if row.empty:
        return "–", "", ""
    r = row.iloc[0]
    pct = nfloat(r.get("win_pct"))
    return f"{nfloat(r.get('winner_odds')):.2f}", f"{pct:.1f}%", str(r.get("note") or "")

def render_squad(entry: int, managers: list[dict], bootstrap: dict) -> tuple[dict, pd.DataFrame]:
    ownership = selected_ownership(managers, [entry])
    squad = manager_squad(ownership, entry)
    if squad.empty:
        st.caption("Troppen kunne ikke lastes.")
        return ownership, squad
    ui.section("Troppen")
    starters = squad[~squad["on_bench"]].copy()
    bench = squad[squad["on_bench"]].copy()
    ui.squad_formation(starters, bench, fmt_price)
    return ownership, squad


def render_manager_profile(entry: int, managers: list[dict], bootstrap: dict, auto_rows: list[dict]) -> None:
    mmap = manager_map(managers)
    m = mmap.get(int(entry))
    if not m:
        return
    name = manager_name(m)
    phase, month_df, month_live = display_month_table(managers, bootstrap)
    month_row = month_df[month_df["entry"] == int(entry)] if not month_df.empty else pd.DataFrame()
    month_rank = nint(month_row.iloc[0].get("rank")) if not month_row.empty else 0

    ui.manager_profile_header(
        name,
        str(m.get("entry_name") or ""),
        [
            (f"{nint(m.get('rank'))}.", "Plass"),
            (nint(m.get("total")), "Poeng"),
            (nint(m.get("event_total")), "Denne GW"),
            (f"{month_rank}." if month_rank else "–", phase["name"] if phase else "Måneden"),
        ],
    )

    # Magazine layout: the pitch starts under form in the main column while
    # career/odds lives in the sidebar. No giant dead zone between form and squad.
    left, right = st.columns([2.15, 0.85], gap="large")
    with left:
        render_merits(name, auto_rows)
        ui.section("Form")
        entry_history, histories = render_form(managers, entry, bootstrap)
        render_chip_history(entry_history)
        render_squad(entry, managers, bootstrap)
    with right:
        stats, season_rows = career_summary(entry_history)
        pre_win, pre_top3 = preseason_odds_for_manager(managers, histories, entry)
        live_win, live_pct, live_note = live_odds_for_manager(managers, histories, bootstrap, entry)
        ui.career_odds_panel(stats, season_rows, pre_win, pre_top3, live_win, live_pct, live_note)
        if st.button("Åpne i Rivalradar", key=f"rr_from_{entry}", use_container_width=True):
            st.session_state["v400_my_manager"] = int(entry)
            st.session_state["v500_my_manager"] = int(entry)
            try:
                st.query_params["me"] = str(int(entry))
            except Exception:
                pass
            st.session_state["v400_main_page"] = "Rivalradar"
            st.rerun()

def render_compare(managers: list[dict], bootstrap: dict) -> None:
    opts = manager_options(managers)
    ids = [x[0] for x in opts]
    labels = dict(opts)
    selected = st.multiselect("Velg 2–8 managere", ids, max_selections=8, format_func=lambda x: labels.get(int(x), str(x)), key="v400_compare_entries")
    if len(selected) < 2:
        st.caption("Velg minst to managere.")
        return
    selected_managers = [m for m in managers if nint(m.get("entry")) in selected]
    ownership = selected_ownership(managers, selected)
    events = ownership.get("manager_events", pd.DataFrame())
    basis = ui.nav(["Ligaen", "Denne måneden", "Denne GW"], "v400_compare_basis", "Ligaen")
    ui.section("Slik står de")
    if basis == "Denne måneden":
        phase, month_df = current_month_table(managers, bootstrap)
        block = month_df[month_df["entry"].isin(selected)].sort_values(["points", "manager"], ascending=[False, True]) if not month_df.empty else pd.DataFrame()
        ui.rows([
            {"rank": i + 1, "who": r.get("manager"), "meta": f"{phase['name'] if phase else 'Måneden'} · {r.get('team','')}", "num": f"{nint(r.get('points'))} poeng"}
            for i, r in enumerate(block.to_dict("records"))
        ])
    elif basis == "Denne GW" and not events.empty:
        block = events.sort_values(["gw_points", "manager"], ascending=[False, True])
        compare_rows = []
        for i, r in enumerate(block.to_dict("records")):
            meta = str(r.get("team") or "")
            if str(r.get("active_chip") or ""):
                meta += f" · {r.get('active_chip')}"
            compare_rows.append({"rank": i + 1, "who": r.get("manager"), "meta": meta, "num": f"{nint(r.get('gw_points'))} poeng"})
        ui.rows(compare_rows)
    else:
        ui.rows([
            {"rank": nint(m.get("rank")), "who": manager_name(m), "meta": str(m.get("entry_name") or ""), "num": f"{nint(m.get('total'))} poeng"}
            for m in sorted(selected_managers, key=lambda x: nint(x.get("rank"), 999999))
        ])
    picks = ownership.get("picks", pd.DataFrame())
    if not picks.empty:
        ui.section("Kapteiner")
        cap_rows = picks[picks["is_captain"]]
        ui.rows([{"rank": "TC" if r.get("is_triple_captain") else "C", "who": r.get("manager"), "meta": r.get("player"), "num": f"{nint(r.get('event_points'))} poeng"} for r in cap_rows.to_dict("records")])
        sets = {entry: set(block["element"].astype(int).tolist()) for entry, block in picks.groupby("entry")}
        common_ids = set.intersection(*sets.values()) if sets else set()
        catalog = player_catalog(bootstrap)
        ui.section("Felles")
        if common_ids:
            ui.rows([{"rank": "", "who": catalog.get(pid, {}).get("web_name", str(pid)), "meta": catalog.get(pid, {}).get("club", ""), "num": ""} for pid in sorted(common_ids, key=lambda x: catalog.get(x, {}).get("web_name", ""))])
        ui.section("Der de skiller seg")
        for entry in selected:
            mine = sets.get(int(entry), set()) - common_ids
            name = labels.get(int(entry), str(entry))
            names = [catalog.get(pid, {}).get("web_name", str(pid)) for pid in mine]
            ui.callout(name, ", ".join(sorted(names, key=normalize_text)) or "Ingen forskjeller")
    show_odds = st.toggle("Vis odds for denne gruppen", key="v400_compare_odds")
    if show_odds:
        with st.spinner("Beregner gruppen …"):
            histories, _ = histories_for(selected)
            phase, month_df = current_month_table(managers, bootstrap)
            current = current_event_id(bootstrap) or 1
            if basis == "Denne måneden":
                month_scores = {nint(r.get("entry")): nfloat(r.get("points")) for r in month_df.to_dict("records")} if not month_df.empty else {}
                period_events = max(1, phase["stop_event"] - current) if phase else 3
                title = f"{phase['name'] if phase else 'Måneden'} · modellens anslag"
            elif basis == "Denne GW":
                month_scores = {nint(r.get("entry")): nfloat(r.get("gw_points")) for r in events.to_dict("records")} if not events.empty else {}
                period_events = 1
                title = "Denne GW · modellens anslag"
            else:
                month_scores = {nint(m.get("entry")): nfloat(m.get("total")) for m in selected_managers}
                period_events = max(1, 38 - current)
                title = "Ligaen · modellens anslag"
            odds = compare_group_odds(selected_managers, histories, current, history_store, period_events=period_events, month_scores=month_scores)
        ui.section(title)
        ui.rows([{"rank": i + 1, "who": r.get("manager"), "meta": f"Odds {decimal_odds_from_pct(r.get('win_pct'))}", "num": fmt_pct(r.get("win_pct"))} for i, r in enumerate(odds.to_dict("records"))])


def render_league(managers: list[dict], bootstrap: dict, auto_rows: list[dict]) -> None:
    ui.page_title("Ligaen", "Tabellen, managerne og oddsen som lå der før sesongstart.")
    view = ui.nav(["Tabell", "Manager", "Sammenlign", "Odds før sesongstart"], "v405_league_view", "Tabell")
    if view == "Tabell":
        render_league_table(managers, bootstrap)
    elif view == "Manager":
        opts = manager_options(managers); ids = [x[0] for x in opts]; labels = dict(opts)
        if st.session_state.get("v400_manager_select") not in ids:
            st.session_state.pop("v400_manager_select", None)
        entry = st.selectbox("Finn manager", ids, format_func=lambda x: labels.get(int(x), str(x)), key="v400_manager_select")
        render_manager_profile(int(entry), managers, bootstrap, auto_rows)
    elif view == "Sammenlign":
        render_compare(managers, bootstrap)
    else:
        ui.section("Odds før sesongstart")
        render_preseason_odds(managers)


def render_candidate_list(df: pd.DataFrame, title: str, rival_n: int, mode: str, limit: int = 3) -> None:
    ui.section(title)
    if df is None or df.empty:
        st.caption("Ingen tydelige treff akkurat nå.")
        return
    items = []
    for i, r in enumerate(df.head(limit).to_dict("records")):
        rival_count = nint(r.get("rival_count")); owners = list(r.get("rival_owners") or []); missing = list(r.get("rival_missing") or [])
        if mode == "cover":
            names = owners; prefix = "Har:"
            num = ", ".join(names[:2]) + (f" +{len(names)-2}" if len(names) > 2 else "") if names else "Ingen"
        elif mode == "keep":
            names = missing; prefix = "Mangler hos:"
            num = ", ".join(names[:2]) + (f" +{len(names)-2}" if len(names) > 2 else "") if names else "Ingen"
        else:
            names = owners; prefix = "Har:"
            num = "Ingen rivaler" if not names else ", ".join(names[:2]) + (f" +{len(names)-2}" if len(names) > 2 else "")
        items.append({
            "rank": i + 1,
            "who": r.get("web_name"),
            "meta": f"{r.get('club')} · {r.get('position')} · {fmt_price(r.get('current_price'))} · {r.get('outlook_label')} · {prefix} {', '.join(names) if names else 'ingen'}",
            "num": num,
        })
    ui.rows(items)

def render_rival_matchup(managers: list[dict], bootstrap: dict) -> None:
    opts = manager_options(managers); ids = [x[0] for x in opts]; labels = dict(opts)
    default_me = my_manager_id(managers) or st.session_state.get("v400_my_manager")
    if default_me not in ids:
        default_me = ids[0] if ids else None
    me = st.selectbox("Min manager", ids, index=ids.index(default_me) if default_me in ids else 0, format_func=lambda x: labels.get(int(x), str(x)), key="v400_my_manager")
    suggested = suggested_rival_entries(managers, bootstrap, int(me), limit=5) if me else []
    if "v400_rivals" not in st.session_state:
        st.session_state["v400_rivals"] = suggested
    valid_rivals = {x for x in ids if x != me}
    if st.session_state.get("v700_rivals_owner") != int(me) or any(x not in valid_rivals for x in st.session_state.get("v700_rivals", [])):
        st.session_state["v700_rivals"] = [x for x in st.session_state.get("v400_rivals", suggested) if x in valid_rivals][:8]
        if not st.session_state["v700_rivals"]:
            st.session_state["v700_rivals"] = suggested[:5]
        st.session_state["v700_rivals_owner"] = int(me)
    rivals = st.multiselect("Rivaler", [x for x in ids if x != me], max_selections=8, format_func=lambda x: labels.get(int(x), str(x)), key="v700_rivals")
    st.session_state["v400_rivals"] = rivals
    c1, c2, c3 = st.columns(3)
    with c1: period = st.selectbox("Periode", ["Neste GW", "Neste 3 GW", "Neste 5 GW", "Resten av måneden", "Sesongen"], index=1, key="v400_period")
    with c2: goal = st.selectbox("Mål", ["Slå disse managerne", "Vinn måneden", "Kom topp 3", "Ta igjen manageren foran", "Forsvar ledelsen", "Vinn ligaen"], key="v400_goal")
    with c3: risk = st.selectbox("Risiko", ["Trygt", "Balansert", "Aggressivt"], index=1, key="v400_risk")
    if not rivals:
        st.caption("Velg minst én rival.")
        return
    run = st.button("Analyser rivalene", type="primary", use_container_width=True, key="v400_run_rivals")
    signature = (int(me), tuple(sorted(int(x) for x in rivals)), period, goal, risk)
    if run:
        names = ", ".join(labels.get(int(x), str(x)) for x in rivals)
        with st.spinner(f"Analyserer {labels.get(int(me), me)} mot {names} …"):
            result = rival_analysis(client, managers, history_store, int(me), [int(x) for x in rivals], period, risk, goal)
        st.session_state["v400_rival_signature"] = signature
        st.session_state["v400_rival_result"] = result
    elif st.session_state.get("v400_rival_signature") != signature:
        st.caption("Trykk «Analyser rivalene» når du er klar.")
        return
    result = st.session_state.get("v400_rival_result")
    if not result or result.get("error"):
        if result and result.get("error"): st.warning(result["error"])
        return
    ownership = result["ownership"]; data_quality_note(ownership)
    rival_n = nint(result.get("rival_n"), len(rivals)); strategy_context = str(result.get("strategy_context") or "neutral")
    ui.callout("Din situasjon", str(result.get("strategy_text") or ""), "green" if strategy_context == "defend" else "red" if strategy_context == "chase" else "")

    overview_tab, transfer_tab, captain_tab = st.tabs(["Oversikt", "Trekk", "Kaptein"])
    with overview_tab:
        cols = st.columns(3, gap="large")
        with cols[0]: render_candidate_list(result.get("they_have_i_lack"), "Dekk deg", rival_n, "cover", limit=3)
        with cols[1]: render_candidate_list(result.get("i_have_they_lack"), "Behold", rival_n, "keep", limit=3)
        with cols[2]: render_candidate_list(result.get("nobody_has"), "Hent", rival_n, "attack", limit=3)

    suggestions = result.get("suggestions", pd.DataFrame())
    with transfer_tab:
        ui.section("Trekk å vurdere")
        if suggestions is None or suggestions.empty:
            st.caption("Fant ingen tydelige én-for-én-trekk som passer budsjett og posisjon.")
        else:
            for i, r in enumerate(suggestions.head(3).to_dict("records")):
                label = "Beste treff" if i == 0 else "Tryggere" if risk == "Trygt" else "Offensivt" if risk == "Aggressivt" else "Alternativ"
                meta = f"{r['out_player']} ({fmt_price(r.get('selling_price'))}) → {r['in_player']} ({fmt_price(r.get('in_price'))}) · {fmt_price(r.get('budget_after'))} igjen"
                ui.recommendation(r["in_player"], label, meta, r.get("reasons") or [])
            if not bool(suggestions.iloc[0].get("selling_price_exact")):
                st.caption("Minst ett forslag bruker estimert salgspris fordi FPL ikke leverte eksakt salgspris.")
        with st.expander("Hva om?"):
            if suggestions is None or suggestions.empty:
                st.caption("Ingen transfer å simulere.")
            else:
                choices = list(range(min(3, len(suggestions))))
                idx = st.selectbox("Trekk", choices, format_func=lambda i: f"{suggestions.iloc[i]['out_player']} → {suggestions.iloc[i]['in_player']}", key="v700_whatif")
                r = suggestions.iloc[int(idx)].to_dict()
                ui.stat_strip([(fmt_price(r.get("budget_after")), "Budsjett etter"), (f"{nint(r.get('rival_count'))}/{rival_n}", "Rivaler med spilleren"), (f"{nint(r.get('expected_low'))}–{nint(r.get('expected_high'))}", "Forventet område")])
                st.caption("Anslag, ikke fasit.")

    with captain_tab:
        caps = result.get("captains", pd.DataFrame())
        ui.section("Kaptein")
        if caps is None or caps.empty:
            st.caption("Ingen tydelig kapteinanbefaling akkurat nå.")
        else:
            cap_items = []
            labels_cap = ["Beste valg", "Tryggere alternativ", "Mer offensivt"]
            for i, r in enumerate(caps.to_dict("records")):
                base = labels_cap[i] if i < len(labels_cap) else "Alternativ"
                names = list(r.get("rival_captain_names") or [])
                if names:
                    base += " · Kaptein hos " + ", ".join(names[:3]) + (f" +{len(names)-3}" if len(names) > 3 else "")
                cap_items.append({"rank": i + 1, "who": r.get("web_name"), "meta": base, "num": f"{nint(r.get('outlook_expected_low'))}–{nint(r.get('outlook_expected_high'))} poeng"})
            ui.rows(cap_items)
        with st.expander("Modellens anslag"):
            selected = [int(me)] + [int(x) for x in rivals]
            selected_managers = [m for m in managers if nint(m.get("entry")) in selected]
            histories, _ = histories_for(selected)
            month_scores = current_month_points_map(managers, bootstrap) if goal == "Vinn måneden" else None
            events_n = max(1, len(result.get("event_ids") or [1]))
            odds = compare_group_odds(selected_managers, histories, current_event_id(bootstrap) or 1, history_store, period_events=events_n, month_scores=month_scores)
            ui.rows([{"rank": i + 1, "who": r.get("manager"), "meta": f"Odds {decimal_odds_from_pct(r.get('win_pct'))}", "num": fmt_pct(r.get("win_pct"))} for i, r in enumerate(odds.to_dict("records"))])

def champion_season_history(managers: list[dict]) -> pd.DataFrame:
    """Build verified score/rank rows for every recorded LRO league champion.

    Current managers come from FPL Previous Seasons. Former managers are included
    only when we have explicit source-backed alumni data. This avoids pretending a
    random old FPL season was necessarily played in Lofthus.
    """
    overall = history_store.overall_results()
    if overall.empty:
        return pd.DataFrame()

    alumni_loader = getattr(history_store, "alumni_season_history", None)
    if callable(alumni_loader):
        try:
            alumni = alumni_loader()
        except Exception:
            alumni = pd.DataFrame()
    else:
        alumni = pd.DataFrame()

    # Defensive fallback for Nordmo. Keeping these verified rows in app.py means
    # Mesterrekorder still works even if Streamlit briefly serves an older cached
    # HistoryStore object during a deploy.
    if alumni.empty:
        alumni = pd.DataFrame([
            {"manager": "Øyvind Nordmo Sivertsen", "season": "2020/21", "total_points": 2515, "overall_rank": 4759, "source": "FPL Previous Seasons"},
            {"manager": "Øyvind Nordmo Sivertsen", "season": "2021/22", "total_points": 2599, "overall_rank": 19100, "source": "FPL Previous Seasons"},
            {"manager": "Øyvind Nordmo Sivertsen", "season": "2022/23", "total_points": 2429, "overall_rank": 477228, "source": "FPL Previous Seasons"},
            {"manager": "Øyvind Nordmo Sivertsen", "season": "2023/24", "total_points": 2557, "overall_rank": 17663, "source": "FPL Previous Seasons"},
            {"manager": "Øyvind Nordmo Sivertsen", "season": "2024/25", "total_points": 2488, "overall_rank": 158118, "source": "FPL Previous Seasons"},
            {"manager": "Øyvind Nordmo Sivertsen", "season": "2025/26", "total_points": 2244, "overall_rank": 496413, "source": "FPL Previous Seasons"},
        ])
    current_by_name = {history_store.key(manager_name(m)): m for m in managers}
    current_winner_entries: list[int] = []
    for row in overall.to_dict("records"):
        winner = history_store.canonical(str(row.get("winner") or ""))
        m = current_by_name.get(history_store.key(winner))
        if m and nint(m.get("entry")):
            current_winner_entries.append(nint(m.get("entry")))
    histories, _ = histories_for(current_winner_entries) if current_winner_entries else ({}, {})

    rows = []
    for row in overall.to_dict("records"):
        season = str(row.get("season") or "")
        winner = history_store.canonical(str(row.get("winner") or ""))
        points = None
        overall_rank = None
        source = ""

        if not alumni.empty:
            hit = alumni[(alumni["manager"].map(history_store.key) == history_store.key(winner)) & (alumni["season"] == season)]
            if not hit.empty:
                r = hit.iloc[0]
                points = nint(r.get("total_points"))
                overall_rank = nint(r.get("overall_rank"))
                source = str(r.get("source") or "")

        if points is None:
            m = current_by_name.get(history_store.key(winner))
            entry = nint(m.get("entry")) if m else 0
            hist = histories.get(entry, {}) if entry else {}
            past = hist.get("past", []) or []
            hit = next((r for r in past if str(r.get("season_name") or "") == season), None)
            if hit:
                points = nint(hit.get("total_points"))
                overall_rank = nint(hit.get("rank"))
                source = "FPL Previous Seasons"

        rows.append({
            "season": season,
            "manager": winner,
            "total_points": points,
            "overall_rank": overall_rank,
            "source": source,
        })
    return pd.DataFrame(rows)


def render_preseason_odds(managers: list[dict]) -> None:
    """Show an immutable pre-season market when a frozen CSV exists.

    On the first run without a snapshot we reconstruct it strictly from pre-2026/27
    history, then write a best-effort CSV without ever overwriting it. Committing
    that file to data/ turns the market into a permanent historical artifact.
    """
    errors: dict[int, str] = {}
    odds = pd.DataFrame()
    if PRESEASON_ODDS_FILE.exists():
        try:
            odds = pd.read_csv(PRESEASON_ODDS_FILE)
        except Exception:
            odds = pd.DataFrame()
    if odds.empty:
        entries = [nint(m.get("entry")) for m in managers if nint(m.get("entry"))]
        with st.spinner("Henter før-sesonghistorikken …"):
            histories, errors = histories_for(entries)
            odds = build_preseason_odds(managers, histories, history_store)
        if not odds.empty and not PRESEASON_ODDS_FILE.exists():
            try:
                PRESEASON_ODDS_FILE.parent.mkdir(parents=True, exist_ok=True)
                odds.to_csv(PRESEASON_ODDS_FILE, index=False)
            except Exception:
                pass
    if odds.empty:
        st.caption("Før-sesongoddsen er ikke tilgjengelig akkurat nå.")
        return
    ui.odds_table(odds)
    if errors:
        st.caption("Noen historikkprofiler manglet under rekonstruksjonen av før-sesongmarkedet.")
    st.caption("Historisk før-sesongmarked. 2026/27-poeng endrer ikke oddsen.")


def render_rivalradar(managers: list[dict], bootstrap: dict) -> None:
    ui.page_title("Rivalradar", "Finn forskjellene som faktisk kan avgjøre duellen.")
    view = ui.nav(["Rivaler", "Spilleroversikt"], "v406_rival_view", "Rivaler")
    if view == "Rivaler":
        render_rival_matchup(managers, bootstrap)
    else:
        render_season(managers, bootstrap, embedded=True)

def render_history(auto_rows: list[dict], managers: list[dict] | None = None) -> None:
    managers = managers or []
    ui.page_title("Hall of Fame", "Mestere, månedskonger og rekordene som har formet Lofthus.")
    view = ui.nav(["Rangering", "Månedskonger", "Sesonger", "Rekorder"], "v404_hof_view", "Rangering")
    if view == "Rangering":
        hof = history_store.hall_of_fame(auto_rows)
        if hof.empty:
            st.caption("Ingen historikk funnet.")
            return

        # V404: enforce the Hall of Fame hierarchy again at render time as a
        # defensive guard. A season championship is the top honour in LRO.
        # Two league titles MUST rank above one league title regardless of cups,
        # monthly wins or total podiums. This also protects the UI if an older
        # lro_history.py is accidentally left in a deployment.
        # Numeric tuple sort, deliberately independent of pandas dtypes.
        # LRO rule: season titles are the supreme honour. Once managers have the
        # same number of league titles, use an Olympic-style hierarchy for the
        # remaining honours: other golds first, then silver, then bronze.
        hof_records = sorted(hof.to_dict("records"), key=hall_of_fame_sort_key)

        hall_rows = []
        for i, r in enumerate(hof_records[:40]):
            merits = []
            league_gold = nint(r.get("league_gold"))
            monthly_gold = nint(r.get("monthly_gold"))
            cup_gold = nint(r.get("cup_gold"))
            if league_gold:
                merits.append(f"{league_gold} sesongtittel" if league_gold == 1 else f"{league_gold} sesongtitler")
            if cup_gold:
                merits.append(f"{cup_gold} cupgull")
            if monthly_gold:
                merits.append(f"{monthly_gold} månedsseier" if monthly_gold == 1 else f"{monthly_gold} månedsseire")
            if not merits:
                # Ranking may still be earned through silver/bronze, but the
                # aggregate 'pallplasser' label is deliberately not shown here.
                if nint(r.get("league_silver")):
                    merits.append(f"{nint(r.get('league_silver'))} sølv sammenlagt")
                elif nint(r.get("league_bronze")):
                    merits.append(f"{nint(r.get('league_bronze'))} bronse sammenlagt")
                elif nint(r.get("monthly_silver")):
                    merits.append(f"{nint(r.get('monthly_silver'))} månedssølv")
                elif nint(r.get("monthly_bronze")):
                    merits.append(f"{nint(r.get('monthly_bronze'))} månedsbronse")
            hall_rows.append({
                "rank": i + 1,
                "rank_class": "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else "",
                "who": r.get("display_name"),
                "meta": " · ".join(merits),
                "num": "",
            })
        ui.hall_of_fame(hall_rows)
        st.caption("Sesongtitler står over alt annet. Ved likt antall sesongtitler rangeres øvrige gull først, deretter sølv og bronse.")
    elif view == "Månedskonger":
        medals = history_store.monthly_medals(auto_rows)
        ui.rows([
            {"rank": nint(r.get("rank")), "who": r.get("manager"), "meta": f"{nint(r.get('podiums'))} pallplasser", "num": f"{nint(r.get('gold'))} gull · {nint(r.get('silver'))} sølv · {nint(r.get('bronze'))} bronse"}
            for r in medals.head(40).to_dict("records")
        ])
        with st.expander("Måned for måned"):
            cal = history_store.monthly_calendar(auto_rows)
            ui.dataframe_compact(cal, ["season", "month", "winner", "runner_up", "third"], {"season": "Sesong", "month": "Måned", "winner": "Gull", "runner_up": "Sølv", "third": "Bronse"})
    elif view == "Sesonger":
        ui.section("Sammenlagt")
        overall = history_store.overall_results()
        ui.season_archive(overall, "league")
        ui.section("Cup")
        cup = history_store.cup_results()
        ui.season_archive(cup, "cup")
    else:
        hof = history_store.hall_of_fame(auto_rows)
        if hof.empty:
            st.caption("Ingen rekorddata.")
            return
        league = hof.sort_values(["league_gold", "league_silver", "display_name"], ascending=[False, False, True]).iloc[0]
        cup = hof.sort_values(["cup_gold", "cup_silver", "display_name"], ascending=[False, False, True]).iloc[0]
        month = hof.sort_values(["monthly_gold", "monthly_silver", "display_name"], ascending=[False, False, True]).iloc[0]
        podium = hof.sort_values(["podiums", "league_gold", "cup_gold", "monthly_gold", "display_name"], ascending=[False, False, False, False, True]).iloc[0]
        ui.rows([
            {"rank": "L", "who": league["display_name"], "meta": "Flest ligatitler", "num": nint(league["league_gold"])},
            {"rank": "C", "who": cup["display_name"], "meta": "Flest cupgull", "num": nint(cup["cup_gold"])},
            {"rank": "M", "who": month["display_name"], "meta": "Flest månedsseire", "num": nint(month["monthly_gold"])},
            {"rank": "P", "who": podium["display_name"], "meta": "Flest pallplasser", "num": nint(podium["podiums"])},
        ])

        ui.section("Mesterrekorder")
        try:
            champions = champion_season_history(managers)
        except Exception:
            champions = pd.DataFrame()
        known = champions.dropna(subset=["total_points", "overall_rank"]).copy() if not champions.empty else pd.DataFrame()
        if known.empty:
            st.caption("Mesterpoengene kunne ikke lastes akkurat nå.")
        else:
            high = known.sort_values(["total_points", "overall_rank"], ascending=[False, True]).iloc[0]
            low = known.sort_values(["total_points", "overall_rank"], ascending=[True, True]).iloc[0]
            best_or = known.sort_values(["overall_rank", "total_points"], ascending=[True, False]).iloc[0]
            ui.rows([
                {"rank": "P", "who": high["manager"], "meta": f"Høyeste poengsum som Lofthus-mester · {high['season']}", "num": f"{nint(high['total_points'])} poeng"},
                {"rank": "OR", "who": best_or["manager"], "meta": f"Beste FPL-plassering som Lofthus-mester · {best_or['season']}", "num": f"{nint(best_or['overall_rank']):,}".replace(",", " ")},
                {"rank": "L", "who": low["manager"], "meta": f"Laveste poengsum som ga ligagull · {low['season']}", "num": f"{nint(low['total_points'])} poeng"},
            ])
            with st.expander("Alle mestersesongene"):
                view = known[["season", "manager", "total_points", "overall_rank"]].copy()
                view.columns = ["Sesong", "Mester", "Poeng", "FPL-plassering"]
                st.dataframe(view, hide_index=True, use_container_width=True)
            missing = champions[champions["total_points"].isna()] if not champions.empty else pd.DataFrame()
            if not missing.empty:
                st.caption(f"Mangler fortsatt FPL-poeng for {len(missing)} registrert mestersesong(er).")
            else:
                st.caption("Mesterrekordene dekker alle registrerte ligavinnere siden Lofthus startet i 2020/21.")


def health_check(managers: list[dict], bootstrap: dict) -> list[str]:
    issues = []
    entries = [nint(m.get("entry")) for m in managers if nint(m.get("entry"))]
    if len(managers) != 63:
        issues.append(f"Forventet 63 managere, fant {len(managers)}.")
    if len(entries) != len(set(entries)):
        issues.append("Duplikate entry-ID-er i ligadata.")
    canonical_names = [history_store.key(manager_name(m)) for m in managers]
    if len(canonical_names) != len(set(canonical_names)):
        issues.append("Duplikate manageridentiteter etter aliasing.")
    catalog = player_catalog(bootstrap)
    invalid_prices = [p for p in catalog.values() if p["current_price"] <= 0 or p["current_price"] > 25]
    if invalid_prices:
        issues.append(f"{len(invalid_prices)} spillere har mistenkelig pris.")
    return issues


def load_app_data() -> tuple[dict, list[dict], list[str]]:
    errors = []
    try:
        bootstrap = client.bootstrap()
    except Exception as exc:
        return {}, [], [str(exc)]
    try:
        _, managers, debug = client.league_managers(DEFAULT_LEAGUE_ID)
        managers = canonical_managers(managers, history_store)
        errors.extend(debug.get("errors", []))
    except Exception as exc:
        managers = []
        errors.append(str(exc))
    return bootstrap, managers, errors


bootstrap, managers, load_errors = load_app_data()

# Deep-link bridge used by custom sports tables. This makes manager names behave
# like navigation without introducing another visible button or control.
try:
    requested_page = st.query_params.get("page")
    requested_view = st.query_params.get("league_view")
    requested_manager = st.query_params.get("manager")
    requested_me = st.query_params.get("me")
    deep_link_signature = f"{requested_page}|{requested_view}|{requested_manager}|{requested_me}"
    if st.session_state.get("_v600_consumed_deeplink") != deep_link_signature:
        if requested_page in {"Forside", "Ligaen", "Rivalradar", "Hall of Fame"}:
            st.session_state["v400_main_page"] = requested_page
        if requested_view in {"Tabell", "Manager", "Sammenlign", "Odds før sesongstart"}:
            st.session_state["v405_league_view"] = requested_view
        if requested_manager and str(requested_manager).isdigit():
            st.session_state["v400_manager_select"] = int(requested_manager)
        if requested_me and str(requested_me).isdigit():
            st.session_state["v500_my_manager"] = int(requested_me)
            st.session_state["v400_my_manager"] = int(requested_me)
        st.session_state["_v600_consumed_deeplink"] = deep_link_signature
except Exception:
    pass

ui.header(short_season_label(bootstrap) if bootstrap else "26/27")
main_page = ui.nav(["Forside", "Ligaen", "Rivalradar", "Hall of Fame"], "v400_main_page", "Forside")

if not bootstrap or not managers:
    st.warning("FPL-data er midlertidig utilgjengelig.")
    if load_errors:
        st.caption("Historikken kan fortsatt fungere når datafilene ligger i repoet.")
    if main_page == "Hall of Fame":
        render_history([], [])
else:
    auto_rows = auto_monthly_rows(bootstrap)
    if main_page == "Forside":
        render_home(managers, bootstrap)
    elif main_page == "Ligaen":
        render_league(managers, bootstrap, auto_rows)
    elif main_page == "Rivalradar":
        render_rivalradar(managers, bootstrap)
    elif main_page == "Hall of Fame":
        render_history(auto_rows, managers)

# Hidden developer health data: no sidebar, no normal UI noise.
if st.query_params.get("debug") == "1" and bootstrap:
    with st.expander("V704 debug"):
        st.code(APP_VERSION)
        issues = health_check(managers, bootstrap)
        st.write(issues or ["Ingen kjente health-check-avvik."])
        st.caption(f"Arkivsnapshots i data/snapshots: {len(snapshot_store.list_snapshots())}")
