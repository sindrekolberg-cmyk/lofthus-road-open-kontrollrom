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
    states = effective_states(managers, state)
    me = _identity(managers, int(me))

    previous = _previous(managers, histories, bootstrap, history)
    leader = states[0] if states else None
    winner = previous.get("gw_winner") or {}
    month = state.month_ranking() if state else []
    month_leader = month[0] if month and sum(x.month_points for x in month) > 0 else None

    if not me:
        items = []
        if leader:
            items.append(("Leder", leader.manager, f"{leader.live_total_points} poeng"))
        if winner:
            items.append(("Forrige GW", str(winner.get("manager") or "–"), f"{nint(winner.get('gw'))} poeng"))
        if month_leader and state:
            items.append((state.month_name or "Måneden", month_leader.manager, f"{month_leader.month_points} poeng"))
        if items:
            ui.status_strip(items[:3])
    elif state:
        mine = state.manager(me)
        if mine:
            ahead = next((m for m in state.managers_by_rank() if m.live_rank == mine.live_rank - 1), None)
            gap = (ahead.live_total_points - mine.live_total_points + 1) if ahead else 0
            ui.status_strip([
                ("Din plass", f"{mine.live_rank}.", f"{mine.live_gw_points} GW" + (" · live" if state.is_live else "")),
                ("Neste rival", ahead.manager if ahead else "Du leder", f"{gap} poeng" if ahead else ""),
                (state.month_name or "Måneden", f"{mine.month_rank}." if mine.month_rank else "–", f"{mine.month_points} poeng"),
            ])

    if state and state.is_live:
        live_players = [p for p in state.player_impacts if p.fixture_status == "live" and (p.event_points or p.captain_count or p.triple_captain_count)]
        standout = live_players[0] if live_players else None
        impact_rows: list[dict[str, Any]] = []
        if standout:
            swings = manager_swing_for_player(state, standout.element)
            positive = [r for r in swings if float(r.get("swing") or 0) > 0][:3]
            negative = [r for r in reversed(swings) if float(r.get("swing") or 0) < 0][:2]
            impact_rows = positive + negative
        ui.home_matchday(state, impact_rows, fixture_scoreline(state, bootstrap), states[:5], me=me)
    else:
        ui.section("Topp 5", "Sammenlagt")
        ui.top_five(states[:5], me=me, live=False)

    if state:
        candidates = generate_candidates(state, managers, bootstrap, history, histories)
        stories = merge_persistent_stories(candidates, st.session_state.get("v810_newsroom"), state, limit=4)
        st.session_state["v810_newsroom"] = [x.to_dict() for x in stories]
        ui.section("Snakkiser")
        ui.story_list(stories, me=me, state=state)
    else:
        ui.section("Snakkiser")
        st.markdown('<div class="v8-empty">Live-redaksjonen våkner når lagdataene er klare.</div>', unsafe_allow_html=True)

    if state:
        mine = state.manager(me) if me else None
        if mine:
            left, right = st.columns([1, 1], gap="large")
            with left:
                ui.section("Min Lofthus")
                rivals = [m for m in state.managers_by_rank() if m.entry != me]
                ahead = [m for m in rivals if m.live_rank < mine.live_rank]
                nearest = ahead[-1] if ahead else None
                move = mine.live_rank_change
                ui.mini_grid([
                    (f"{mine.live_rank}.", "Sammenlagt"),
                    (f"↑{move}" if move > 0 else f"↓{abs(move)}" if move < 0 else "–", "Livebevegelse"),
                    (nearest.manager if nearest else "Leder", "Nærmest foran"),
                ])
                if nearest:
                    st.markdown(f'<div style="margin-top:.5rem"><a target="_self" href="{rival_href(me, nearest.entry)}" style="font-size:.73rem;font-weight:900;text-decoration:none">Åpne duellen →</a></div>', unsafe_allow_html=True)
            with right:
                ui.section("Mest populære")
                ui.popular_players(state.player_impacts, me=me, limit=3)
        else:
            ui.section("Mest populære")
            ui.popular_players(state.player_impacts, me=me, limit=3)
        ui.data_quality(state)
    return me
