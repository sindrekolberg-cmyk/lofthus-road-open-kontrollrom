from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

import lro_ui as ui
from lro_config import load_config
from lro_fpl import season_label
from lro_league import auto_monthly_rows
from lro_routes import parse_route
from lro_runtime import get_client, get_history_store, histories_async, live_state_async, load_shell, runtime_debug
from lro_pages import home, league, manager, rivalradar, history as history_page, player

APP_VERSION = "lofthus-road-open-v821-image-hotfix"
ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Lofthus Road Open",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)
ui.install_styles()

config = load_config(ROOT)
client = get_client()
history_store = get_history_store(str(config.data_dir), APP_VERSION)
route = parse_route(st.query_params)
bootstrap, managers, shell_errors = load_shell(config, client, history_store)
state_seed = live_state_async(config, managers, bootstrap, APP_VERSION, refresh_seconds=18) if bootstrap and managers else None
histories_seed = histories_async(managers, bootstrap) if managers and bootstrap else None

season = season_label(bootstrap) if bootstrap else config.season_fallback
status = "LIVE" if state_seed and state_seed.is_live else ""
updated = ""
if state_seed:
    try:
        updated = state_seed.fetched_at.astimezone(ZoneInfo("Europe/Oslo")).strftime("Oppdatert %H:%M")
    except Exception:
        updated = ""
ui.app_header(config.name, season, route.page, me=route.me, status=status, updated=updated)

# The first league-wide picks sweep is deliberately asynchronous. Once the first
# complete state arrives, promote it to a normal app rerun so non-live pages stop
# refreshing every five seconds.
refresh = "5s" if state_seed is None and bool(managers) else ("10s" if state_seed and state_seed.is_live else "45s" if state_seed and state_seed.event_status == "between_matches" else None)


def _render_page(state, histories):
    current = parse_route(st.query_params)
    me = current.me
    if current.page == "Hall of Fame":
        auto_rows = auto_monthly_rows(client, history_store, config.league_id, bootstrap) if bootstrap else []
        history_page.render(history_store, auto_rows, me=me)
        return

    if not managers:
        ui.page_lead("Lofthus Road Open", "MIDLERTIDIG UTE")
        st.markdown('<div class="v8-empty">Ligadata er ikke tilgjengelig akkurat nå. Historikken ligger fortsatt under Hall of Fame.</div>', unsafe_allow_html=True)
        return

    if current.page == "Forside":
        home.render(config, client, history_store, managers, bootstrap, state, histories, me=me)
    elif current.page == "Ligaen":
        league.render(config, history_store, managers, state, histories, current.view, me=me, compare=current.compare)
    elif current.page == "Manager":
        auto_rows = []
        manager.render(config, history_store, managers, state, histories, current.manager, me=me, auto_month_rows=auto_rows)
    elif current.page == "Rivalradar":
        rivalradar.render(config, managers, state, me=me, rival=current.rival)
    elif current.page == "Spiller":
        player.render(state, current.player, me=me)
    else:
        home.render(config, client, history_store, managers, bootstrap, state, histories, me=me)


@st.fragment(run_every=refresh)
def _product_body() -> None:
    state = live_state_async(config, managers, bootstrap, APP_VERSION, refresh_seconds=18) if bootstrap and managers else None
    histories = histories_async(managers, bootstrap) if managers and bootstrap else None
    if state_seed is None and state is not None and not st.session_state.get("_v800_state_promoted"):
        st.session_state["_v800_state_promoted"] = True
        st.rerun()
    if state_seed is not None and state is not None:
        # Promote match-status/event transitions to a full rerun so the shell,
        # cadence and league standings all move to the new state cleanly.
        if state.event_id != state_seed.event_id or state.is_live != state_seed.is_live or state.is_finished != state_seed.is_finished:
            st.rerun()
    _render_page(state, histories)


_product_body()

if route.debug:
    with st.expander("V821 debug", expanded=False):
        payload = {
            "version": APP_VERSION,
            "route": route.__dict__,
            "league_id": config.league_id,
            "managers": len(managers),
            "shell_errors": shell_errors,
            "runtime": runtime_debug(),
            "fpl": client.diagnostics(),
        }
        st.json(payload)
