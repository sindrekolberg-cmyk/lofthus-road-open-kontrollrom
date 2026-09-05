from __future__ import annotations

from typing import Any

import streamlit as st

import lro_ui as ui
from lro_analysis import nint
from lro_config import LeagueConfig
from lro_fpl import FPLClient
from lro_history import HistoryStore
from lro_league import effective_states, fixture_scoreline, manager_options
from lro_live import LiveState, manager_swing_for_player
from lro_newsroom import completed_round_summary, generate_candidates, merge_persistent_stories
from lro_routes import rival_href


def _identity(managers: list[dict], selected: int) -> int:
    opts = manager_options(managers)
    ids = [entry for entry, _ in opts]
    labels = dict(opts)
    selected = int(selected) if selected in ids else 0
    button = labels.get(selected, "Velg manager") if selected else "Velg manager"
    with st.popover(button, use_container_width=False):
        choice = st.selectbox(
            "Min manager",
            options=[0] + ids,
            index=([0] + ids).index(selected) if selected in ids else 0,
            format_func=lambda x: "Ingen valgt" if int(x) == 0 else labels.get(int(x), str(x)),
            key="v810_identity",
        )
        if int(choice or 0) != selected:
            try:
                if choice:
                    st.query_params["me"] = str(int(choice))
                elif "me" in st.query_params:
                    del st.query_params["me"]
            except Exception:
                pass
            st.rerun()
    return selected


def _previous(managers: list[dict], histories: dict[int, dict] | None, bootstrap: dict, history: HistoryStore) -> dict:
    finished = [nint(e.get("id")) for e in bootstrap.get("events", []) or [] if e.get("finished") and nint(e.get("id"))]
    return completed_round_summary(managers, histories, max(finished) if finished else 0, history)


def render(
    config: LeagueConfig,
    client: FPLClient,
    history: HistoryStore,
    managers: list[dict],
    bootstrap: dict,
    state: LiveState | None,
    histories: dict[int, dict] | None,
    me: int = 0,
) -> int:
    """V821 front page.

    Public surface = sports site. The deep analysis remains in the product, but
    the homepage only exposes the data that earns editorial space.
    """
    states = effective_states(managers, state)
    me = _identity(managers, int(me))

    previous = _previous(managers, histories, bootstrap, history)
    leader = states[0] if states else None
    winner = previous.get("gw_winner") or {}
    month = state.month_ranking() if state else []
    month_leader = month[0] if month and sum(x.month_points for x in month) > 0 else None

    # V821: no public dashboard strip above the lead story. The league leader
    # already owns the Top 5 rail, previous-GW/month context belongs in stories,
    # and a selected manager gets a personal strip lower on the page.

    if state:
        # The hero always has one dominant sporting subject. During live play we
        # prioritise a player currently on the pitch; between matches, the most
        # influential scorer from the active/last event remains the lead visual.
        candidates = [p for p in state.player_impacts if p.event_points or p.captain_count or p.triple_captain_count]
        if state.is_live:
            live_now = [p for p in candidates if p.fixture_status == "live"]
            standout = live_now[0] if live_now else (candidates[0] if candidates else None)
        else:
            standout = max(candidates, key=lambda p: (p.event_points, p.impact_score), default=None)
        impact_rows: list[dict[str, Any]] = []
        if standout:
            swings = manager_swing_for_player(state, standout.element)
            positive = [r for r in swings if float(r.get("swing") or 0) > 0][:3]
            negative = sorted(
                [r for r in swings if float(r.get("swing") or 0) < 0],
                key=lambda r: float(r.get("swing") or 0),
            )[:2]
            impact_rows = positive + negative
        ui.sports_front(state, impact_rows, fixture_scoreline(state, bootstrap), states[:5], me=me)
    else:
        ui.sports_section("Topp 5", "Sammenlagt")
        ui.top_five(states[:5], me=me, live=False)

    if state:
        candidates = generate_candidates(state, managers, bootstrap, history, histories)
        stories = merge_persistent_stories(candidates, st.session_state.get("v821_newsroom"), state, limit=3)
        st.session_state["v821_newsroom"] = [x.to_dict() for x in stories]
        ui.sports_section("Snakkiser", "Det viktigste fra ligaen")
        ui.sports_news(stories, me=me, state=state)
    else:
        ui.sports_section("Snakkiser")
        st.markdown('<div class="v8-empty">Redaksjonen våkner når lagdataene er klare.</div>', unsafe_allow_html=True)

    if state:
        mine = state.manager(me) if me else None
        if mine:
            ui.sports_section("Min Lofthus")
            rivals = [m for m in state.managers_by_rank() if m.entry != me]
            ahead = [m for m in rivals if m.live_rank < mine.live_rank]
            nearest = ahead[-1] if ahead else None
            move = mine.live_rank_change
            ui.personal_strip([
                (f"{mine.live_rank}.", "Sammenlagt"),
                (f"↑{move}" if move > 0 else f"↓{abs(move)}" if move < 0 else "–", "Livebevegelse"),
                (nearest.manager if nearest else "Leder", "Nærmest foran"),
            ])

        ui.sports_section("Spillerne alle snakker om", "Lofthus-eierskap")
        ui.sports_popular_players(state.player_impacts, me=me, limit=3)
        ui.analysis_invite(me=me)
        ui.data_quality(state)
    return me
