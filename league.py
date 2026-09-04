from __future__ import annotations

import pandas as pd
import streamlit as st

import lro_ui as ui
from lro_analysis import nint
from lro_config import LeagueConfig
from lro_history import HistoryStore, normalize_text
from lro_league import effective_states, manager_options
from lro_live import LiveState
from lro_odds import build_preseason_odds
from lro_routes import league_href


def _season_rank_history(managers: list[dict], histories: dict[int, dict] | None) -> pd.DataFrame:
    histories = histories or {}
    names = {nint(m.get("entry")): str(m.get("canonical_name") or m.get("player_name") or m.get("entry")) for m in managers}
    rows=[]
    for entry,payload in histories.items():
        for r in payload.get("current",[]) or []:
            event=nint(r.get("event")); total=nint(r.get("total_points"))
            if event:
                rows.append({"entry":int(entry),"manager":names.get(int(entry),str(entry)),"event":event,"total":total})
    df=pd.DataFrame(rows)
    if df.empty:
        return df
    out=[]
    for event,block in df.groupby("event"):
        block=block.copy()
        block["rank"]=block["total"].rank(method="min",ascending=False).astype(int)
        out.extend(block.to_dict("records"))
    return pd.DataFrame(out).sort_values(["event","rank","manager"]).reset_index(drop=True)


def _render_compare(managers: list[dict], state: LiveState | None, preset: tuple[int,...], me: int) -> None:
    states=effective_states(managers,state)
    by_entry={m.entry:m for m in states}
    opts=manager_options(managers); ids=[x[0] for x in opts]; labels=dict(opts)
    default=[x for x in preset if x in ids]
    selected=st.multiselect("Managere",ids,default=default,max_selections=8,format_func=lambda x:labels.get(int(x),str(x)),key="v800_compare")
    if len(selected)<2:
        st.markdown('<div class="v8-empty">Velg minst to managere.</div>',unsafe_allow_html=True)
        return
    block=[by_entry[x] for x in selected if x in by_entry]
    if len(block)==2:
        a,b=block
        ui.duel_header(a,b,a.live_total_points-b.live_total_points)
        ui.mini_grid([
            (f"{a.live_rank}. / {b.live_rank}.","Plass"),
            (f"{a.live_gw_points} / {b.live_gw_points}","Denne GW"),
            (f"{a.players_remaining} / {b.players_remaining}","Spillere igjen"),
        ])
        ui.simple_table(
            [("side",""),("captain","Kaptein"),("month","Måneden"),("chip","Chip")],
            [
                {"side":a.manager,"captain":a.captain,"month":f"{a.month_points} p · {a.month_rank}.","chip":a.active_chip or "–"},
                {"side":b.manager,"captain":b.captain,"month":f"{b.month_points} p · {b.month_rank}.","chip":b.active_chip or "–"},
            ],
        )
    else:
        ui.simple_table(
            [("rank","#"),("manager","Manager"),("captain","Kaptein"),("gw","GW"),("total","Poeng")],
            [{"rank":m.live_rank,"manager":m.manager,"captain":m.captain,"gw":m.live_gw_points,"total":m.live_total_points} for m in sorted(block,key=lambda x:x.live_rank)],
            numeric={"rank","gw","total"},
        )


def _render_season(managers:list[dict],histories:dict[int,dict]|None,history:HistoryStore) -> None:
    history_df=_season_rank_history(managers,histories)
    if history_df.empty:
        st.markdown('<div class="v8-empty">Sesonghistorikken lastes i bakgrunnen.</div>',unsafe_allow_html=True)
        return
    current=history_df[history_df["event"]==history_df["event"].max()].sort_values(["rank","manager"])
    available=current["manager"].tolist()
    defaults=available[:min(6,len(available))]
    selected=st.multiselect("Vis i sesongløpet",available,default=defaults,max_selections=12,key="v800_season_managers")
    chart=history_df[history_df["manager"].isin(selected)].copy()
    if not chart.empty:
        spec={
            "mark":{"type":"line","point":True,"strokeWidth":2},
            "encoding":{
                "x":{"field":"event","type":"ordinal","title":"GW"},
                "y":{"field":"rank","type":"quantitative","title":"Plassering","scale":{"reverse":True,"zero":False}},
                "color":{"field":"manager","type":"nominal","title":"Manager"},
                "tooltip":[{"field":"manager","type":"nominal"},{"field":"event","type":"ordinal","title":"GW"},{"field":"rank","type":"quantitative","title":"Plass"}],
            },
            "data":{"values":chart[["manager","event","rank"]].to_dict("records")},
        }
        st.vega_lite_chart(spec,use_container_width=True)

    with st.expander("Odds før sesongstart"):
        if not histories:
            st.caption("Historikk lastes.")
        else:
            try:
                odds=build_preseason_odds(managers,histories,history)
            except Exception:
                odds=pd.DataFrame()
            if odds.empty:
                st.caption("Oddsdata er ikke tilgjengelig.")
            else:
                cols=[c for c in ["manager","winner_odds","top3_odds","average_rank","best_rank"] if c in odds.columns]
                labels={"manager":"Manager","winner_odds":"Vinner","top3_odds":"Topp 3","average_rank":"Snittrank","best_rank":"Beste rank"}
                data=[]
                for r in odds.head(63).to_dict("records"):
                    data.append({c:(f"{float(r.get(c)):.2f}" if c in {"winner_odds","top3_odds"} else r.get(c)) for c in cols})
                ui.simple_table([(c,labels.get(c,c)) for c in cols],data,numeric=set(cols)-{"manager"})


def render(
    config: LeagueConfig,
    history: HistoryStore,
    managers: list[dict],
    state: LiveState | None,
    histories: dict[int,dict] | None,
    view: str,
    me: int=0,
    compare: tuple[int,...]=(),
) -> None:
    ui.page_lead("Ligaen", "LIVE TABLE" if state and state.is_live else "TABELL")
    ui.subnav([
        ("Tabell",league_href("Tabell",me=me)),
        ("Måneden",league_href("Måneden",me=me)),
        ("Sammenlign",league_href("Sammenlign",me=me)),
        ("Sesongen",league_href("Sesongen",me=me)),
    ],view)
    states=effective_states(managers,state)
    if view=="Tabell":
        ui.league_table(states,me=me,live=bool(state and not state.is_finished))
        if state: ui.data_quality(state)
    elif view=="Måneden":
        name=state.month_name if state and state.month_name else "Måneden"
        ui.section(f"{name} · live" if state and not state.is_finished else name)
        if state:
            ui.month_table(state.month_ranking(),me=me)
        else:
            st.markdown('<div class="v8-empty">Månedstabellen lastes sammen med lagdataene.</div>',unsafe_allow_html=True)
    elif view=="Sammenlign":
        _render_compare(managers,state,compare,me)
    else:
        _render_season(managers,histories,history)
