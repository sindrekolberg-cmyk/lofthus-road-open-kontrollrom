from __future__ import annotations

import pandas as pd
import streamlit as st

import lro_ui as ui
from lro_history import HistoryStore


def _overall_rows(history: HistoryStore) -> list[dict]:
    df = history.overall_results()
    if df.empty:
        return []
    rows=[]
    for r in df.to_dict("records"):
        rows.append({
            "season": r.get("season") or "",
            "winner": r.get("winner") or "–",
            "runner": r.get("runner_up") or "–",
            "third": r.get("third_place") or "–",
        })
    return list(reversed(rows))


def render(history: HistoryStore, auto_month_rows: list[dict] | None = None, me: int = 0) -> None:
    ui.page_lead("Hall of Fame", "LOFTHUS-HISTORIEN")
    auto_month_rows = auto_month_rows or []
    tabs = st.tabs(["Hall of Fame", "Mestere", "Månedsvinnere", "Rekorder"])

    with tabs[0]:
        hof = history.hall_of_fame(auto_month_rows)
        if hof.empty:
            st.markdown('<div class="v8-empty">Historikkfilene er ikke tilgjengelige.</div>', unsafe_allow_html=True)
        else:
            rows=[]
            for r in hof.head(40).to_dict("records"):
                rows.append({
                    "rank": int(r.get("rank") or 0),
                    "manager": r.get("display_name") or "",
                    "league": int(r.get("league_gold") or 0),
                    "cup": int(r.get("cup_gold") or 0),
                    "month": int(r.get("monthly_gold") or 0),
                    "silver": int(r.get("silver") or 0),
                    "bronze": int(r.get("bronze") or 0),
                })
            ui.simple_table(
                [("rank", "#"), ("manager", "Manager"), ("league", "Liga"), ("cup", "Cup"), ("month", "Måned"), ("silver", "Sølv"), ("bronze", "Bronse")],
                rows,
                numeric={"rank","league","cup","month","silver","bronze"},
            )

    with tabs[1]:
        rows = _overall_rows(history)
        if rows:
            ui.simple_table(
                [("season", "Sesong"), ("winner", "Vinner"), ("runner", "Nr. 2"), ("third", "Nr. 3")],
                rows,
            )
        else:
            st.markdown('<div class="v8-empty">Sesongarkivet er tomt.</div>', unsafe_allow_html=True)
        cups = history.cup_results()
        if not cups.empty:
            ui.section("Cupvinnere")
            ui.simple_table(
                [("season", "Sesong"), ("winner", "Vinner"), ("runner_up", "Finalist")],
                list(reversed(cups[["season","winner","runner_up"]].to_dict("records"))),
            )

    with tabs[2]:
        cal = history.monthly_calendar(auto_month_rows)
        if cal.empty:
            st.markdown('<div class="v8-empty">Månedsarkivet er ikke tilgjengelig.</div>', unsafe_allow_html=True)
        else:
            seasons = sorted(cal["season"].dropna().astype(str).unique().tolist(), reverse=True)
            selected = st.selectbox("Sesong", ["Alle"] + seasons, key="v800_hof_month_season")
            block = cal if selected == "Alle" else cal[cal["season"] == selected]
            ui.simple_table(
                [("season", "Sesong"), ("month", "Måned"), ("winner", "Vinner"), ("runner_up", "Nr. 2"), ("third", "Nr. 3")],
                block.rename(columns={"runner_up":"runner_up"}).to_dict("records"),
            )

    with tabs[3]:
        hof = history.hall_of_fame(auto_month_rows)
        if hof.empty:
            st.markdown('<div class="v8-empty">Ingen rekorder å vise.</div>', unsafe_allow_html=True)
        else:
            def leader(metric: str):
                row = hof.sort_values([metric,"display_name"], ascending=[False,True]).iloc[0]
                return row.get("display_name"), int(row.get(metric) or 0)
            champ, champ_n = leader("league_gold")
            month, month_n = leader("monthly_gold")
            podium, podium_n = leader("podiums")
            ui.mini_grid([
                (f"{champ} · {champ_n}", "Flest ligatitler"),
                (f"{month} · {month_n}", "Flest månedsseire"),
                (f"{podium} · {podium_n}", "Flest pallplasser"),
            ])
