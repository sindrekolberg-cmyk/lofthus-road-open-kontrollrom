from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

import lro_ui as ui
from lro_analysis import manager_squad, nint
from lro_config import LeagueConfig
from lro_history import HistoryStore
from lro_league import effective_states, form_rows, player_status_map, profile_story
from lro_live import LiveState
from lro_routes import league_href, rival_href


def _manager_state(managers: list[dict], state: LiveState | None, entry: int):
    rows = effective_states(managers, state)
    return next((m for m in rows if m.entry == int(entry)), None)


def _chips(history_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    out = []
    for chip in (history_payload or {}).get("chips", []) or []:
        event = nint(chip.get("event"))
        name = str(chip.get("name") or "")
        label = {
            "3xc": "Triple Captain",
            "bboost": "Bench Boost",
            "wildcard": "Wildcard",
            "freehit": "Free Hit",
        }.get(name, name or "Chip")
        out.append({"chip": label, "gw": f"GW{event}" if event else "–"})
    return out


def _career(history_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for r in (history_payload or {}).get("past", []) or []:
        rows.append({
            "season": r.get("season_name") or "",
            "points": nint(r.get("total_points")),
            "rank": f"{nint(r.get('rank')):,}".replace(",", " ") if nint(r.get("rank")) else "–",
        })
    return list(reversed(rows))


def render(
    config: LeagueConfig,
    history: HistoryStore,
    managers: list[dict],
    state: LiveState | None,
    histories: dict[int, dict] | None,
    entry: int,
    me: int = 0,
    auto_month_rows: list[dict] | None = None,
) -> None:
    m = _manager_state(managers, state, entry)
    if not m:
        ui.page_lead("Manager", "IKKE FUNNET")
        st.markdown('<div class="v8-empty">Manageren finnes ikke i ligaen.</div>', unsafe_allow_html=True)
        return

    st.markdown(
        f'<a target="_self" href="{league_href("Tabell", me=me)}" style="font-size:.72rem;font-weight:900;text-decoration:none">← Tilbake til tabellen</a>',
        unsafe_allow_html=True,
    )
    ui.manager_header(m)

    if state:
        ui.profile_story(profile_story(state, entry))
        squad = manager_squad(state.ownership, entry)
        ui.section("Laget", f"GW{state.event_id}" + (" · live" if not state.is_finished else ""))
        ui.squad_formation(squad, player_status_map(state), me=me)
        ui.mini_grid([
            (m.players_remaining, "Spillere igjen"),
            (f"{m.month_rank}." if m.month_rank else "–", state.month_name or "Måneden"),
            (f"£{m.team_value:.1f}m" if m.team_value else "–", "Lagverdi"),
        ])
        st.markdown(
            f'<div style="margin-top:.55rem"><a target="_self" href="{rival_href(me or entry)}" style="font-size:.73rem;font-weight:900;text-decoration:none">Åpne Rivalradar →</a></div>',
            unsafe_allow_html=True,
        )
    else:
        ui.section("Laget")
        st.markdown('<div class="v8-empty">Lagoppstillingen lastes i bakgrunnen.</div>', unsafe_allow_html=True)

    ui.section("Form")
    ui.form_strip(form_rows(managers, histories, entry, state, last_n=5))

    payload = (histories or {}).get(int(entry), {})
    st.markdown('<div id="historikk"></div>', unsafe_allow_html=True)
    with st.expander("Chips"):
        chips = _chips(payload)
        if chips:
            ui.simple_table([("chip", "Chip"), ("gw", "Brukt")], chips)
        else:
            st.caption("Ingen registrerte chips ennå.")

    with st.expander("Sesong og karriere"):
        current = (payload or {}).get("current", []) or []
        if current:
            latest = current[-1]
            ui.mini_grid([
                (f"{nint(latest.get('overall_rank')):,}".replace(",", " ") if nint(latest.get("overall_rank")) else "–", "OR"),
                (nint(latest.get("total_points")), "FPL-poeng"),
                (f"£{nint(latest.get('value'))/10:.1f}m" if nint(latest.get("value")) else "–", "Lagverdi"),
            ])
        career = _career(payload)
        if career:
            ui.simple_table(
                [("season", "Sesong"), ("points", "Poeng"), ("rank", "OR")],
                career,
                numeric={"points", "rank"},
            )

    with st.expander("Meritter"):
        merits = history.merits_for(m.manager, auto_month_rows or [])
        items = []
        labels = [
            ("league_gold", "Ligatitler"),
            ("league_silver", "Andreplasser"),
            ("league_bronze", "Tredjeplasser"),
            ("cup_gold", "Cupseire"),
            ("monthly_gold", "Månedsseire"),
        ]
        for key, label in labels:
            value = nint(merits.get(key))
            if value:
                items.append((value, label))
        if items:
            ui.mini_grid(items[:3])
            if len(items) > 3:
                ui.simple_table([("merit", "Meritt"), ("count", "Antall")], [{"merit": l, "count": v} for v, l in items[3:]], numeric={"count"})
        else:
            st.caption("Ingen registrerte Lofthus-meritter ennå.")
