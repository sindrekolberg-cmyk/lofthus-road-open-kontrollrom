from __future__ import annotations

import html
import re
from typing import Any

import pandas as pd
import streamlit as st


CSS = r"""
<style>
:root {
  --ink:#0b1220;
  --navy:#111a2a;
  --navy-2:#182235;
  --paper:#f5f3ee;
  --surface:#fffefa;
  --soft:#eceff3;
  --line:#d9dde3;
  --text:#121824;
  --muted:#6c7687;
  --gold:#b98a1f;
  --green:#167a52;
  --red:#b63a34;
  --blue:#2e6fae;
  --radius:12px;
  --shadow:0 16px 42px rgba(11,18,32,.08);
}
html,body,[data-testid="stAppViewContainer"] {background:var(--paper); color:var(--text); overflow-x:hidden;}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {display:none;}
.block-container {max-width:1440px; padding:1.25rem 1.55rem 4rem !important;}
#MainMenu, footer {visibility:hidden;}

/* typography */
h1,h2,h3,p {color:var(--text);}
h1,h2,h3 {letter-spacing:-.035em;}
.v400-brand {font-size:clamp(2rem,4vw,3.3rem); line-height:.95; font-weight:900; letter-spacing:-.055em; color:#fff;}
.v400-season {margin-top:.55rem; color:#b9c4d5; font-size:.92rem; font-weight:750; letter-spacing:.02em;}
.v400-page-title {font-size:clamp(2rem,4vw,3.4rem); font-weight:900; letter-spacing:-.055em; line-height:1; margin:.35rem 0 .45rem;}
.v400-page-sub {font-size:1rem; color:var(--muted); max-width:760px; line-height:1.55;}
.v400-section {margin:2.1rem 0 .7rem; display:flex; align-items:end; justify-content:space-between; gap:1rem; border-bottom:1px solid var(--line); padding-bottom:.55rem;}
.v400-section-title {font-size:1.32rem; font-weight:850; letter-spacing:-.035em;}
.v400-section-note {font-size:.83rem; color:var(--muted);}

/* header */
.v400-header {background:var(--ink); border-radius:16px; padding:1.35rem 1.55rem 1.25rem; margin-bottom:.55rem; box-shadow:var(--shadow);}
.v400-header-inner {display:flex; align-items:end; justify-content:space-between; gap:1rem;}

/* nav buttons styled as flat text */
div[data-testid="stHorizontalBlock"]:has(button[kind="primary"]), div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) {gap:.15rem !important;}
.stButton > button {border:none !important; border-radius:0 !important; background:transparent !important; box-shadow:none !important; min-height:2.65rem; padding:.55rem .4rem .45rem !important; color:#667184 !important; font-weight:800 !important; font-size:.92rem !important; transition:color .16s ease, border-color .16s ease, background .16s ease !important; border-bottom:2px solid transparent !important;}
.stButton > button:hover {color:var(--text) !important; background:rgba(17,26,42,.035) !important;}
.stButton > button[kind="primary"] {color:var(--text) !important; border-bottom-color:var(--gold) !important;}
.stButton > button:focus {box-shadow:0 0 0 2px rgba(46,111,174,.22) !important;}

/* widgets */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextInput input {background:#fff !important; border-color:var(--line) !important; border-radius:10px !important; box-shadow:none !important;}
[data-baseweb="tag"] {background:var(--ink) !important; color:#fff !important; border-radius:7px !important;}
label, .stSelectbox label, .stMultiSelect label {font-weight:750 !important; color:var(--text) !important;}

/* stat strip */
.v400-stats {display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); margin:1rem 0 1.25rem;}
.v400-stat {padding:.9rem 1rem .85rem 0; min-width:0;}
.v400-stat + .v400-stat {padding-left:1rem; border-left:1px solid var(--line);}
.v400-stat-value {font-weight:900; font-size:1.55rem; letter-spacing:-.045em; line-height:1;}
.v400-stat-label {margin-top:.35rem; color:var(--muted); font-size:.78rem; font-weight:700;}

/* sports lists */
.v400-list {border-top:1px solid var(--line);}
.v400-row {display:grid; grid-template-columns:52px minmax(0,1fr) auto; align-items:center; gap:.7rem; padding:.85rem .15rem; border-bottom:1px solid var(--line); transition:background .16s ease;}
.v400-row:hover {background:rgba(255,255,255,.45);}
.v400-rank {font-size:.82rem; color:var(--muted); font-weight:850;}
.v400-rank.gold {color:#977013;}
.v400-rank.silver {color:#657080;}
.v400-rank.bronze {color:#925f3a;}
.v400-who {font-weight:850; min-width:0;}
.v400-meta {display:block; color:var(--muted); font-size:.80rem; font-weight:600; margin-top:.12rem; white-space:normal;}
.v400-num {font-size:.95rem; font-weight:850; text-align:right; white-space:nowrap;}
.v400-num.up {color:var(--green);}
.v400-num.down {color:var(--red);}

/* tables */
.v400-table-wrap {width:100%; overflow-x:auto; border-top:1px solid var(--line);}
.v400-table {border-collapse:collapse; width:100%; min-width:620px;}
.v400-table th {text-align:left; color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.07em; font-weight:800; padding:.72rem .55rem; border-bottom:1px solid var(--line);}
.v400-table td {padding:.78rem .55rem; border-bottom:1px solid var(--line); vertical-align:middle; font-size:.92rem;}
.v400-table tr:hover td {background:rgba(255,255,255,.5);}
.v400-table .right {text-align:right; white-space:nowrap;}
.v400-table .strong {font-weight:850;}
.v400-table .muted {color:var(--muted);}

/* live */
.v400-live {background:var(--ink); color:#fff; border-radius:14px; padding:1rem 1.15rem; margin:1rem 0 1.2rem;}
.v400-live-kicker {font-size:.72rem; font-weight:900; letter-spacing:.08em; text-transform:uppercase; color:#8cd6b4; display:flex; gap:.5rem; align-items:center;}
.v400-live-dot {width:7px;height:7px;border-radius:50%;background:#49c486;box-shadow:0 0 0 4px rgba(73,196,134,.12);}
.v400-live-score {font-size:1.25rem; font-weight:900; margin:.45rem 0 .2rem;}
.v400-live-sub {color:#b8c3d4;font-size:.82rem;}

/* callouts */
.v400-callout {border-left:3px solid var(--gold); padding:.7rem .9rem; background:rgba(255,255,255,.42); margin:.7rem 0;}
.v400-callout.green {border-left-color:var(--green);}
.v400-callout.red {border-left-color:var(--red);}
.v400-callout strong {display:block; font-size:.88rem; margin-bottom:.15rem;}
.v400-callout span {color:var(--muted); font-size:.86rem; line-height:1.45;}
.v400-alert {display:grid;grid-template-columns:4px 1fr;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:.7rem 0;}
.v400-alert-bar {background:var(--red);}
.v400-alert-body {padding:.75rem .9rem;}
.v400-alert-title {font-size:.72rem;color:var(--red);font-weight:900;text-transform:uppercase;letter-spacing:.07em;}
.v400-alert-main {font-weight:900;margin-top:.15rem;}

/* profile */
.v400-profile {padding:1rem 0 .8rem; border-bottom:1px solid var(--line);}
.v400-profile-name {font-size:clamp(1.8rem,3.5vw,2.7rem); font-weight:900; letter-spacing:-.05em;}
.v400-profile-team {color:var(--muted); margin-top:.15rem;}
.v400-merits {display:flex;flex-wrap:wrap;gap:.55rem 1.4rem;padding:.65rem 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);}
.v400-merit strong {font-size:1.1rem;}
.v400-merit span {color:var(--muted);font-size:.76rem;margin-left:.25rem;}

/* recommendation */
.v400-rec {padding:1rem 0; border-bottom:1px solid var(--line);}
.v400-rec-top {display:flex;justify-content:space-between;align-items:baseline;gap:1rem;}
.v400-rec-name {font-size:1.15rem;font-weight:900;}
.v400-rec-label {font-size:.75rem;font-weight:900;text-transform:uppercase;letter-spacing:.06em;color:var(--green);}
.v400-rec-meta {font-size:.83rem;color:var(--muted);margin:.22rem 0 .45rem;}
.v400-reasons {margin:.35rem 0 0;padding-left:1.05rem;color:#4f5969;font-size:.85rem;line-height:1.5;}

/* expander */
[data-testid="stExpander"] {border:1px solid var(--line) !important; border-radius:10px !important; background:rgba(255,255,255,.25) !important;}

@media(max-width:760px){
 .block-container{padding:.75rem .75rem 3rem !important;}
 .v400-header{border-radius:12px;padding:1rem 1rem .95rem;}
 .v400-brand{font-size:2rem;}
 .v400-page-title{font-size:2rem;}
 .v400-section{margin-top:1.55rem;}
 .v400-stats{grid-template-columns:repeat(2,1fr);}
 .v400-stat:nth-child(3){border-left:0;padding-left:0;border-top:1px solid var(--line);}
 .v400-stat:nth-child(4){border-top:1px solid var(--line);}
 .v400-row{grid-template-columns:38px minmax(0,1fr) auto;}
 .v400-table{min-width:520px;}
 .v400-hide-mobile{display:none !important;}
 .stButton > button{font-size:.78rem !important;padding:.45rem .15rem !important;}
}
</style>
"""


def install_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def header(short_season: str) -> None:
    st.markdown(
        f"<div class='v400-header'><div class='v400-header-inner'><div>"
        f"<div class='v400-brand'>Lofthus Road Open</div>"
        f"<div class='v400-season'>Sesong {esc(short_season)}</div>"
        f"</div></div></div>",
        unsafe_allow_html=True,
    )


def nav(options: list[str], key: str, default: str) -> str:
    if key not in st.session_state or st.session_state.get(key) not in options:
        st.session_state[key] = default
    cols = st.columns(len(options), gap="small")
    for option, col in zip(options, cols):
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", option).strip("_").lower()
        with col:
            if st.button(
                option,
                key=f"{key}_{safe}",
                type="primary" if st.session_state[key] == option else "secondary",
                use_container_width=True,
            ):
                st.session_state[key] = option
                st.rerun()
    return str(st.session_state[key])


def page_title(title: str, sub: str = "") -> None:
    st.markdown(
        f"<div class='v400-page-title'>{esc(title)}</div>"
        + (f"<div class='v400-page-sub'>{esc(sub)}</div>" if sub else ""),
        unsafe_allow_html=True,
    )


def section(title: str, note: str = "") -> None:
    st.markdown(
        f"<div class='v400-section'><div class='v400-section-title'>{esc(title)}</div>"
        f"<div class='v400-section-note'>{esc(note)}</div></div>",
        unsafe_allow_html=True,
    )


def stat_strip(items: list[tuple[Any, str]]) -> None:
    bits = []
    for value, label in items:
        bits.append(f"<div class='v400-stat'><div class='v400-stat-value'>{esc(value)}</div><div class='v400-stat-label'>{esc(label)}</div></div>")
    if bits:
        st.markdown("<div class='v400-stats'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def rows(items: list[dict]) -> None:
    bits = []
    for item in items:
        rank = esc(item.get("rank", ""))
        who = esc(item.get("who", ""))
        meta = esc(item.get("meta", ""))
        num = esc(item.get("num", ""))
        rank_class = esc(item.get("rank_class", ""))
        num_class = esc(item.get("num_class", ""))
        bits.append(
            f"<div class='v400-row'><div class='v400-rank {rank_class}'>{rank}</div>"
            f"<div class='v400-who'>{who}<span class='v400-meta'>{meta}</span></div>"
            f"<div class='v400-num {num_class}'>{num}</div></div>"
        )
    if bits:
        st.markdown("<div class='v400-list'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def html_table(headers: list[tuple[str, str]], data: list[dict], right: set[str] | None = None, hide_mobile: set[str] | None = None) -> None:
    right = right or set()
    hide_mobile = hide_mobile or set()
    th = []
    for key, label in headers:
        classes = []
        if key in right:
            classes.append("right")
        if key in hide_mobile:
            classes.append("v400-hide-mobile")
        th.append(f"<th class='{' '.join(classes)}'>{esc(label)}</th>")
    trs = []
    for row in data:
        cells = []
        for key, _ in headers:
            classes = []
            if key in right:
                classes.append("right")
            if key in hide_mobile:
                classes.append("v400-hide-mobile")
            value = row.get(key, "")
            if key in {"manager", "player", "name"}:
                classes.append("strong")
            cells.append(f"<td class='{' '.join(classes)}'>{esc(value)}</td>")
        trs.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown(
        "<div class='v400-table-wrap'><table class='v400-table'><thead><tr>"
        + "".join(th)
        + "</tr></thead><tbody>"
        + "".join(trs)
        + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


def live_panel(score: str, sub: str = "") -> None:
    st.markdown(
        f"<div class='v400-live'><div class='v400-live-kicker'><span class='v400-live-dot'></span>Live</div>"
        f"<div class='v400-live-score'>{esc(score)}</div>"
        + (f"<div class='v400-live-sub'>{esc(sub)}</div>" if sub else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def callout(title: str, text: str, tone: str = "") -> None:
    cls = tone if tone in {"green", "red"} else ""
    st.markdown(
        f"<div class='v400-callout {cls}'><strong>{esc(title)}</strong><span>{esc(text)}</span></div>",
        unsafe_allow_html=True,
    )


def alert(title: str, main: str) -> None:
    st.markdown(
        f"<div class='v400-alert'><div class='v400-alert-bar'></div><div class='v400-alert-body'>"
        f"<div class='v400-alert-title'>{esc(title)}</div><div class='v400-alert-main'>{esc(main)}</div></div></div>",
        unsafe_allow_html=True,
    )


def profile_header(name: str, team: str) -> None:
    st.markdown(
        f"<div class='v400-profile'><div class='v400-profile-name'>{esc(name)}</div>"
        f"<div class='v400-profile-team'>{esc(team)}</div></div>",
        unsafe_allow_html=True,
    )


def merits(items: list[tuple[Any, str]]) -> None:
    bits = []
    for value, label in items:
        bits.append(f"<div class='v400-merit'><strong>{esc(value)}</strong><span>{esc(label)}</span></div>")
    st.markdown("<div class='v400-merits'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def recommendation(name: str, label: str, meta: str, reasons: list[str]) -> None:
    reason_html = "".join(f"<li>{esc(r)}</li>" for r in reasons[:4])
    st.markdown(
        f"<div class='v400-rec'><div class='v400-rec-top'><div class='v400-rec-name'>{esc(name)}</div>"
        f"<div class='v400-rec-label'>{esc(label)}</div></div>"
        f"<div class='v400-rec-meta'>{esc(meta)}</div>"
        f"<ul class='v400-reasons'>{reason_html}</ul></div>",
        unsafe_allow_html=True,
    )


def dataframe_compact(df: pd.DataFrame, columns: list[str], labels: dict[str, str] | None = None) -> None:
    if df is None or df.empty:
        st.caption("Ingen data akkurat nå.")
        return
    work = df.copy()
    for col in columns:
        if col not in work.columns:
            work[col] = ""
    work = work[columns].fillna("")
    if labels:
        work = work.rename(columns=labels)
    st.dataframe(work, hide_index=True, use_container_width=True)
