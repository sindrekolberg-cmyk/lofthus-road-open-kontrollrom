from __future__ import annotations

import streamlit as st

import lro_ui as ui
from lro_config import LeagueConfig
from lro_history import normalize_text
from lro_league import manager_options
from lro_live import LiveState
from lro_rival import auto_rivals, compare_managers
from lro_routes import manager_href, rival_href


def render(
    config: LeagueConfig,
    managers: list[dict],
    state: LiveState | None,
    me: int = 0,
    rival: int = 0,
) -> tuple[int, int]:
    ui.page_lead("Rivalradar", "LIVE DUELL")
    if not state or not state.manager_live:
        st.markdown('<div class="v8-empty">Rivalradar åpner når lagene er lastet.</div>', unsafe_allow_html=True)
        return me, rival

    options = manager_options(managers)
    ids = [entry for entry, _ in options]
    labels = dict(options)
    if me not in ids:
        me = ids[0] if ids else 0
    rivals = [x for x in ids if x != me]
    suggested = auto_rivals(state, me, limit=5)
    if rival not in rivals:
        rival = suggested[0] if suggested else (rivals[0] if rivals else 0)

    c1, c2 = st.columns(2)
    new_me = c1.selectbox("Meg", ids, index=ids.index(me) if me in ids else 0, format_func=lambda x: labels.get(x, str(x)), key="v800_rival_me") if ids else 0
    possible = [x for x in ids if x != int(new_me)]
    if rival not in possible:
        suggestions = auto_rivals(state, int(new_me), limit=5)
        rival = suggestions[0] if suggestions else (possible[0] if possible else 0)
    new_rival = c2.selectbox("Rival", possible, index=possible.index(rival) if rival in possible else 0, format_func=lambda x: labels.get(x, str(x)), key="v800_rival_other") if possible else 0
    me, rival = int(new_me or 0), int(new_rival or 0)

    st.markdown(
        f'<div style="display:flex;gap:.75rem;flex-wrap:wrap;margin:.2rem 0 .7rem">'
        f'<a target="_self" href="{rival_href(me,rival)}" style="font-size:.72rem;font-weight:900;text-decoration:none">Fast lenke til duellen</a>'
        f'<a target="_self" href="{manager_href(me,me=me)}" style="font-size:.72rem;font-weight:900;text-decoration:none">Se laget ditt</a>'
        f'</div>',
        unsafe_allow_html=True,
    )

    duel = compare_managers(state, me, rival)
    if not duel:
        st.markdown('<div class="v8-empty">Duellen kunne ikke beregnes.</div>', unsafe_allow_html=True)
        return me, rival

    ui.duel_header(duel.me, duel.rival, duel.live_gap)
    ui.mini_grid([
        (f"{duel.me.live_rank}. / {duel.rival.live_rank}.", "Plass"),
        (duel.common_players, "Like bidrag"),
        (f"{duel.me.players_remaining} / {duel.rival.players_remaining}", "Spillere igjen"),
    ])

    ui.section("Nå avgjøres duellen")
    ui.cheer_columns(duel.cheer_for, duel.hope_blank)

    rows = []
    for edge in duel.my_unique:
        rows.append({"side": duel.me.manager, "player": edge.player, "edge": f"+{edge.multiplier_edge}×", "swing": edge.live_swing, "status": edge.status.replace("not_started", "ikke startet").replace("finished", "ferdig")})
    for edge in duel.rival_unique:
        rows.append({"side": duel.rival.manager, "player": edge.player, "edge": f"{edge.multiplier_edge}×", "swing": edge.live_swing, "status": edge.status.replace("not_started", "ikke startet").replace("finished", "ferdig")})
    ui.section("Forskjellene")
    ui.simple_table(
        [("side", "Fordel"), ("player", "Spiller"), ("edge", "Effekt"), ("swing", "Live swing"), ("status", "Status")],
        rows,
        numeric={"swing"},
    )

    suggestions = [e for e in auto_rivals(state, me, limit=5) if e != rival]
    if suggestions:
        links = []
        by_entry = {m.entry: m for m in state.manager_live}
        for entry in suggestions:
            m = by_entry.get(entry)
            if m:
                links.append(f'<a target="_self" href="{rival_href(me,entry)}" style="text-decoration:none;font-size:.72rem;font-weight:850">{ui.esc(m.manager)}</a>')
        if links:
            ui.section("Andre rivaler")
            st.markdown('<div style="display:flex;gap:.9rem;flex-wrap:wrap">' + "".join(links) + '</div>', unsafe_allow_html=True)
    return me, rival
