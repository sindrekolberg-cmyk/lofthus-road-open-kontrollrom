from __future__ import annotations

import pandas as pd
import streamlit as st

import lro_ui as ui
from lro_analysis import nfloat, nint, player_lookup
from lro_live import LiveState, manager_swing_for_player
from lro_routes import manager_href


def render(state: LiveState | None, element: int, me: int = 0) -> None:
    if not state:
        ui.page_lead("Spiller", "LOFTHUS")
        st.markdown('<div class="v8-empty">Spillerdata lastes i bakgrunnen.</div>', unsafe_allow_html=True)
        return
    impact = state.player(element)
    raw = player_lookup(state.ownership, element)
    if not impact and not raw:
        ui.page_lead("Spiller", "IKKE FUNNET")
        st.markdown('<div class="v8-empty">Spilleren finnes ikke i den aktive Lofthus-runden.</div>', unsafe_allow_html=True)
        return

    name = impact.player if impact else str((raw or {}).get("player") or f"Spiller {element}")
    club = impact.club if impact else str((raw or {}).get("club") or "")
    event_points = impact.event_points if impact else nint((raw or {}).get("event_points"))
    ownership_pct = impact.ownership_pct if impact else nfloat((raw or {}).get("ownership_pct"))
    captains = impact.captain_count if impact else nint((raw or {}).get("captain_count"))
    image_url = impact.image_url if impact else str((raw or {}).get("image_url") or "")
    status = impact.fixture_status if impact else ""
    ui.player_hero(name, club, image_url, event_points, f"{ownership_pct:.0f} %", captains, status)
    ui.mini_grid([
        (f"{impact.ownership_count}/{state.league_size}" if impact else nint((raw or {}).get("ownership_count")), "Eiere"),
        (f"{impact.effective_ownership_pct:.0f} %" if impact else f"{nfloat((raw or {}).get('effective_ownership_pct')):.0f} %", "Effektivt eierskap"),
        (impact.triple_captain_count if impact else nint((raw or {}).get("triple_captain_count")), "Triple Captain"),
    ])

    ui.section("Hvem profiterer mest?")
    swings = manager_swing_for_player(state, element)
    rows=[]
    for r in swings[:12]:
        rows.append({
            "manager": r.get("manager") or "",
            "multiplier": r.get("multiplier") or 0,
            "swing": f"{nfloat(r.get('swing')):+.1f}",
        })
    ui.simple_table([("manager","Manager"),("multiplier","Mult."),("swing","Effekt vs. feltet")], rows, numeric={"multiplier","swing"})

    if raw:
        owners = list(raw.get("owners") or [])
        captains = set(raw.get("captains") or [])
        if owners:
            ui.section("Eierne")
            names = []
            state_by_name = {m.manager: m for m in state.manager_live}
            for owner in owners:
                m = state_by_name.get(str(owner))
                if m:
                    label = f"{owner} (C)" if owner in captains else str(owner)
                    names.append(f'<a target="_self" href="{manager_href(m.entry,me=me)}" style="text-decoration:none;font-size:.72rem;font-weight:850">{ui.esc(label)}</a>')
            st.markdown('<div style="display:flex;gap:.8rem;flex-wrap:wrap">'+"".join(names)+'</div>', unsafe_allow_html=True)
