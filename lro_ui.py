from __future__ import annotations

import html
import json
import re
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


CSS = r"""
<style>
:root {
  --ink:#08111f;
  --ink-2:#0d1829;
  --navy:#132035;
  --paper:#f4f1e9;
  --paper-2:#ebe6dc;
  --surface:#fffdf8;
  --surface-strong:#ffffff;
  --line:#d6d9de;
  --line-dark:rgba(255,255,255,.14);
  --text:#121824;
  --muted:#687386;
  --gold:#b88920;
  --gold-soft:#d6b96d;
  --green:#167a52;
  --red:#b63a34;
  --blue:#2e6fae;
  --radius:14px;
  --radius-lg:22px;
  --shadow:0 18px 44px rgba(8,17,31,.09);
  --shadow-dark:0 26px 70px rgba(8,17,31,.23);
}
html,body,[data-testid="stAppViewContainer"] {background:var(--paper); color:var(--text); overflow-x:hidden;}
[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(circle at 5% 0%, rgba(184,137,32,.07), transparent 24rem),
    radial-gradient(circle at 100% 15%, rgba(19,32,53,.05), transparent 30rem),
    linear-gradient(180deg,#f7f4ed 0%,#f4f1e9 42%,#f2efe7 100%);
  position:relative;
}
[data-testid="stAppViewContainer"]::before{
  content:"";position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.36;
  background-image:
    linear-gradient(rgba(8,17,31,.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(8,17,31,.014) 1px, transparent 1px);
  background-size:48px 48px;
  mask-image:linear-gradient(to bottom,rgba(0,0,0,.65),transparent 62%);
}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {display:none;}
.block-container {max-width:1480px; padding:1.05rem 1.6rem 4rem !important; position:relative; z-index:1;}
#MainMenu, footer {visibility:hidden;}

/* typography */
h1,h2,h3,p {color:var(--text);}
h1,h2,h3 {letter-spacing:-.04em;}
.v500-brand {font-size:clamp(2.2rem,4.6vw,4.25rem); line-height:.9; font-weight:950; letter-spacing:-.065em; color:#fff; text-wrap:balance;}
.v500-season {margin-top:.72rem; color:#bcc8d8; font-size:.82rem; font-weight:850; letter-spacing:.085em; text-transform:uppercase;}
.v500-page-title {font-size:clamp(2rem,4vw,3.65rem); font-weight:950; letter-spacing:-.06em; line-height:.95; margin:.55rem 0 .45rem;}
.v500-page-sub {font-size:.98rem; color:var(--muted); max-width:760px; line-height:1.55;}
.v500-section {margin:2rem 0 .7rem; display:flex; align-items:end; justify-content:space-between; gap:1rem; border-bottom:1px solid var(--line); padding-bottom:.55rem;}
.v500-section-title {font-size:1.34rem; font-weight:900; letter-spacing:-.04em;}
.v500-section-note {font-size:.81rem; color:var(--muted);}

/* identity header */
.v500-header {
  position:relative; overflow:hidden; isolation:isolate;
  background:
    radial-gradient(circle at 82% -10%,rgba(214,185,109,.28),transparent 24rem),
    radial-gradient(circle at 12% 110%,rgba(46,111,174,.16),transparent 22rem),
    linear-gradient(115deg,#07101d 0%,#0c1728 56%,#111b2c 100%);
  border-radius:22px; padding:1.6rem 1.7rem 1.5rem; margin-bottom:.55rem; box-shadow:var(--shadow-dark);
  border:1px solid rgba(255,255,255,.08);
}
.v500-header::before{
  content:"";position:absolute;inset:-25% -5% auto auto;width:52%;height:170%;opacity:.45;z-index:-1;
  background:
    linear-gradient(106deg,transparent 0 35%,rgba(255,255,255,.05) 35% 36%,transparent 36% 100%),
    linear-gradient(74deg,transparent 0 55%,rgba(255,255,255,.035) 55% 56%,transparent 56% 100%);
  transform:rotate(-7deg);
}
.v500-header::after{
  content:"";position:absolute;right:-7%;bottom:-82px;width:54%;height:210px;border:1px solid rgba(255,255,255,.08);border-radius:50%;z-index:-1;
  box-shadow:0 0 0 46px rgba(255,255,255,.025),0 0 0 92px rgba(255,255,255,.018);
}
.v500-header-inner {display:flex; align-items:end; justify-content:space-between; gap:1rem;}

/* nav buttons are intentionally quiet */
div[data-testid="stHorizontalBlock"]:has(button[kind="primary"]), div[data-testid="stHorizontalBlock"]:has(button[kind="secondary"]) {gap:.2rem !important;}
.stButton > button {border:none !important; border-radius:0 !important; background:transparent !important; box-shadow:none !important; min-height:2.65rem; padding:.55rem .45rem .45rem !important; color:#657084 !important; font-weight:850 !important; font-size:.9rem !important; transition:color .16s ease, border-color .16s ease, background .16s ease !important; border-bottom:2px solid transparent !important;}
.stButton > button:hover {color:var(--text) !important; background:rgba(17,26,42,.035) !important;}
.stButton > button[kind="primary"] {color:var(--text) !important; border-bottom-color:var(--gold) !important;}
.stButton > button:focus {box-shadow:0 0 0 2px rgba(46,111,174,.18) !important;}

/* widgets */
[data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextInput input {background:rgba(255,255,255,.86) !important; border-color:var(--line) !important; border-radius:10px !important; box-shadow:none !important;}
[data-baseweb="tag"] {background:var(--ink) !important; color:#fff !important; border-radius:7px !important;}
label, .stSelectbox label, .stMultiSelect label {font-weight:800 !important; color:var(--text) !important;}
[data-testid="stPopover"] button{border:1px solid var(--line)!important;border-radius:10px!important;background:rgba(255,255,255,.55)!important;}

/* editorial hero */
.v500-home-hero{position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1.55fr) minmax(290px,.75fr);gap:0;background:var(--ink);border-radius:var(--radius-lg);margin:1rem 0 1.25rem;box-shadow:var(--shadow-dark);color:#fff;min-height:315px;border:1px solid rgba(255,255,255,.08)}
.v500-home-hero::before{content:"";position:absolute;inset:0;pointer-events:none;background:
 radial-gradient(circle at 77% 20%,rgba(214,185,109,.32),transparent 17rem),
 linear-gradient(110deg,transparent 0 53%,rgba(255,255,255,.035) 53% 54%,transparent 54% 100%),
 linear-gradient(70deg,transparent 0 68%,rgba(255,255,255,.03) 68% 69%,transparent 69% 100%)}
.v500-hero-main{position:relative;padding:2rem 2rem 1.9rem;display:flex;flex-direction:column;justify-content:flex-end;min-height:315px;border-right:1px solid var(--line-dark)}
.v500-kicker{font-size:.72rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase;color:var(--gold-soft);margin-bottom:.75rem}
.v500-hero-title{font-size:clamp(2.4rem,5.2vw,5.4rem);line-height:.86;font-weight:950;letter-spacing:-.07em;color:#fff;max-width:850px;text-wrap:balance}
.v500-hero-deck{margin-top:.8rem;color:#c2ccda;font-size:.94rem;line-height:1.45;max-width:710px}
.v500-hero-number{position:absolute;right:1rem;top:.35rem;font-size:clamp(5.5rem,12vw,10rem);font-weight:950;letter-spacing:-.08em;line-height:1;color:rgba(255,255,255,.055);user-select:none}
.v500-hero-side{position:relative;display:grid;grid-template-rows:1fr 1fr;background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.015))}
.v500-hero-mini{padding:1.45rem 1.45rem 1.25rem;display:flex;flex-direction:column;justify-content:flex-end}
.v500-hero-mini + .v500-hero-mini{border-top:1px solid var(--line-dark)}
.v500-mini-label{font-size:.69rem;font-weight:900;letter-spacing:.09em;text-transform:uppercase;color:#9daabe}
.v500-mini-value{font-size:1.55rem;font-weight:950;letter-spacing:-.045em;margin-top:.35rem;color:#fff}
.v500-mini-meta{font-size:.8rem;color:#b8c3d4;margin-top:.18rem}

/* story cards */
.v500-story-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin:.65rem 0 1.1rem}
.v500-story{position:relative;min-height:112px;padding:1rem 1.05rem 1rem 3.55rem;background:rgba(255,255,255,.58);border:1px solid rgba(214,217,222,.9);border-radius:13px;overflow:hidden}
.v500-story::before{content:attr(data-n);position:absolute;left:.9rem;top:.85rem;font-size:2rem;line-height:1;font-weight:950;letter-spacing:-.06em;color:rgba(184,137,32,.7)}
.v500-story-text{font-weight:900;font-size:1.02rem;line-height:1.32;letter-spacing:-.02em}
.v500-story-tag{font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:850;margin-bottom:.35rem}

/* my Lofthus */
.v500-my{position:relative;overflow:hidden;background:linear-gradient(135deg,#fffefa,#f2eee4);border:1px solid var(--line);border-radius:16px;padding:1.1rem 1.15rem;box-shadow:0 12px 30px rgba(8,17,31,.045)}
.v500-my::after{content:"";position:absolute;right:-50px;bottom:-80px;width:220px;height:220px;border-radius:50%;border:1px solid rgba(184,137,32,.16);box-shadow:0 0 0 35px rgba(184,137,32,.035),0 0 0 70px rgba(184,137,32,.02)}
.v500-my-top{position:relative;z-index:1;display:flex;justify-content:space-between;gap:1rem;align-items:baseline}
.v500-my-name{font-size:1.35rem;font-weight:950;letter-spacing:-.04em}
.v500-my-rank{font-size:2.35rem;font-weight:950;letter-spacing:-.07em;color:var(--ink)}
.v500-my-rank span{font-size:.72rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);margin-left:.3rem}
.v500-my-metrics{position:relative;z-index:1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.65rem;margin-top:.85rem}
.v500-my-metric{border-top:1px solid var(--line);padding-top:.65rem}
.v500-my-metric strong{display:block;font-size:1.05rem}
.v500-my-metric span{font-size:.72rem;color:var(--muted);font-weight:700}
.v500-my-insights{position:relative;z-index:1;margin:.75rem 0 0;padding-left:1.05rem;color:#4e5969;font-size:.84rem;line-height:1.55}

/* stat strip */
.v500-stats {display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); margin:1rem 0 1.25rem;}
.v500-stat {padding:.9rem 1rem .85rem 0; min-width:0;}
.v500-stat + .v500-stat {padding-left:1rem; border-left:1px solid var(--line);}
.v500-stat-value {font-weight:950; font-size:1.58rem; letter-spacing:-.05em; line-height:1;}
.v500-stat-label {margin-top:.35rem; color:var(--muted); font-size:.76rem; font-weight:750;}

/* sports lists */
.v500-list {border-top:1px solid var(--line);}
.v500-row {display:grid; grid-template-columns:52px minmax(0,1fr) auto; align-items:center; gap:.7rem; padding:.86rem .15rem; border-bottom:1px solid var(--line); transition:background .16s ease, transform .16s ease;}
.v500-row:hover {background:rgba(255,255,255,.46);}
.v500-rank {font-size:.8rem; color:var(--muted); font-weight:900;}
.v500-rank.gold {color:#977013;}.v500-rank.silver {color:#657080;}.v500-rank.bronze {color:#925f3a;}
.v500-who {font-weight:900; min-width:0; letter-spacing:-.015em;}
.v500-meta {display:block; color:var(--muted); font-size:.78rem; font-weight:650; margin-top:.12rem; white-space:normal;}
.v500-num {font-size:.94rem; font-weight:900; text-align:right; white-space:nowrap;}
.v500-num.up {color:var(--green);}.v500-num.down {color:var(--red);}

/* tables */
.v500-table-wrap {width:100%; overflow-x:auto; border:1px solid var(--line);border-radius:13px;background:rgba(255,255,255,.42);box-shadow:0 8px 24px rgba(8,17,31,.035)}
.v500-table {border-collapse:collapse; width:100%; min-width:620px;}
.v500-table th {text-align:left; color:var(--muted); font-size:.69rem; text-transform:uppercase; letter-spacing:.075em; font-weight:900; padding:.74rem .65rem; border-bottom:1px solid var(--line);background:rgba(8,17,31,.025)}
.v500-table td {padding:.82rem .65rem; border-bottom:1px solid var(--line); vertical-align:middle; font-size:.9rem;}
.v500-table tbody tr:last-child td{border-bottom:0}.v500-table tr:hover td {background:rgba(255,255,255,.58);}
.v500-table .right {text-align:right; white-space:nowrap;}.v500-table .strong {font-weight:900;}.v500-table .muted {color:var(--muted);}
.v500-cell-main {font-weight:800;}.v500-cell-meta {display:block;color:var(--muted);font-size:.74rem;font-weight:650;margin-top:.12rem;line-height:1.25;}

/* live */
.v500-live {position:relative;overflow:hidden;background:linear-gradient(120deg,#07151d,#0b1d29 60%,#132538); color:#fff; border-radius:15px; padding:1rem 1.15rem; margin:1rem 0 1.2rem;box-shadow:0 14px 32px rgba(8,17,31,.12)}
.v500-live::after{content:"";position:absolute;right:-60px;top:-100px;width:260px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(73,196,134,.12),transparent 65%)}
.v500-live-kicker {font-size:.7rem; font-weight:950; letter-spacing:.09em; text-transform:uppercase; color:#8cd6b4; display:flex; gap:.5rem; align-items:center;}
.v500-live-dot {width:7px;height:7px;border-radius:50%;background:#49c486;box-shadow:0 0 0 4px rgba(73,196,134,.12);}
.v500-live-score {font-size:1.25rem; font-weight:950; margin:.45rem 0 .2rem;}.v500-live-sub {color:#b8c3d4;font-size:.8rem;}

/* callouts */
.v500-callout {border-left:3px solid var(--gold); padding:.72rem .9rem; background:rgba(255,255,255,.48); margin:.7rem 0;border-radius:0 10px 10px 0;}
.v500-callout.green {border-left-color:var(--green);}.v500-callout.red {border-left-color:var(--red);}
.v500-callout strong {display:block; font-size:.88rem; margin-bottom:.15rem;}.v500-callout span {color:var(--muted); font-size:.84rem; line-height:1.45;}
.v500-alert {display:grid;grid-template-columns:4px 1fr;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:.7rem 0}.v500-alert-bar {background:var(--red)}.v500-alert-body {padding:.75rem .9rem}.v500-alert-title {font-size:.7rem;color:var(--red);font-weight:950;text-transform:uppercase;letter-spacing:.07em}.v500-alert-main {font-weight:950;margin-top:.15rem}

/* profile */
.v500-profile {position:relative;overflow:hidden;padding:1.2rem 1.25rem 1.1rem;border:1px solid var(--line);border-radius:16px;background:linear-gradient(135deg,rgba(255,255,255,.75),rgba(244,241,233,.65));box-shadow:0 10px 28px rgba(8,17,31,.04)}
.v500-profile::after{content:"";position:absolute;right:-55px;top:-75px;width:240px;height:240px;border:1px solid rgba(184,137,32,.12);border-radius:50%;box-shadow:0 0 0 42px rgba(184,137,32,.025)}
.v500-profile-name {position:relative;z-index:1;font-size:clamp(1.9rem,3.6vw,2.9rem); font-weight:950; letter-spacing:-.055em;}.v500-profile-team {position:relative;z-index:1;color:var(--muted); margin-top:.15rem;}
.v500-merits {display:flex;flex-wrap:wrap;gap:.55rem 1.4rem;padding:.68rem 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.v500-merit strong {font-size:1.1rem}.v500-merit span {color:var(--muted);font-size:.75rem;margin-left:.25rem}

/* recommendations */
.v500-rec {padding:1rem 0; border-bottom:1px solid var(--line)}.v500-rec-top {display:flex;justify-content:space-between;align-items:baseline;gap:1rem}.v500-rec-name {font-size:1.15rem;font-weight:950}.v500-rec-label {font-size:.72rem;font-weight:950;text-transform:uppercase;letter-spacing:.065em;color:var(--green)}.v500-rec-meta {font-size:.81rem;color:var(--muted);margin:.22rem 0 .45rem}.v500-reasons {margin:.35rem 0 0;padding-left:1.05rem;color:#4f5969;font-size:.84rem;line-height:1.5}

/* Hall of Fame */
.v500-hof-podium{display:grid;grid-template-columns:1.08fr 1fr 1fr;gap:.75rem;margin:.8rem 0 1rem}.v500-hof-card{position:relative;overflow:hidden;min-height:180px;border:1px solid var(--line);border-radius:15px;padding:1rem 1rem 1.05rem;background:rgba(255,255,255,.56)}.v500-hof-card.first{background:linear-gradient(145deg,#0a1424,#101d31);color:#fff;border-color:rgba(255,255,255,.08);box-shadow:var(--shadow-dark)}.v500-hof-card.first::after{content:"";position:absolute;right:-35px;bottom:-70px;width:210px;height:210px;border-radius:50%;background:radial-gradient(circle,rgba(214,185,109,.2),transparent 65%)}.v500-hof-place{font-size:3.4rem;font-weight:950;letter-spacing:-.08em;line-height:.9;color:rgba(18,24,36,.12)}.v500-hof-card.first .v500-hof-place{color:rgba(255,255,255,.13)}.v500-hof-name{font-size:1.2rem;font-weight:950;letter-spacing:-.035em;margin-top:2.35rem}.v500-hof-card.first .v500-hof-name{color:#fff}.v500-hof-meta{font-size:.78rem;color:var(--muted);font-weight:650;margin-top:.3rem;line-height:1.4}.v500-hof-card.first .v500-hof-meta{color:#b9c5d5}

/* expander */
[data-testid="stExpander"] {border:1px solid var(--line) !important; border-radius:11px !important; background:rgba(255,255,255,.3) !important;}

@media(max-width:900px){.v500-home-hero{grid-template-columns:1fr}.v500-hero-main{border-right:0;border-bottom:1px solid var(--line-dark)}.v500-hero-side{grid-template-columns:1fr 1fr;grid-template-rows:1fr}.v500-hero-mini + .v500-hero-mini{border-top:0;border-left:1px solid var(--line-dark)}.v500-hof-podium{grid-template-columns:1fr}.v500-hof-card{min-height:135px}.v500-hof-name{margin-top:1.25rem}}
@media(max-width:760px){
 .block-container{padding:.7rem .72rem 3rem !important}.v500-header{border-radius:14px;padding:1.1rem 1.05rem 1rem}.v500-brand{font-size:2.2rem}.v500-page-title{font-size:2.15rem}.v500-section{margin-top:1.55rem}.v500-home-hero{min-height:0}.v500-hero-main{min-height:245px;padding:1.25rem}.v500-hero-title{font-size:2.8rem}.v500-hero-side{grid-template-columns:1fr}.v500-hero-mini + .v500-hero-mini{border-left:0;border-top:1px solid var(--line-dark)}.v500-story-grid{grid-template-columns:1fr}.v500-my-metrics{grid-template-columns:1fr}.v500-stats{grid-template-columns:repeat(2,1fr)}.v500-stat:nth-child(3){border-left:0;padding-left:0;border-top:1px solid var(--line)}.v500-stat:nth-child(4){border-top:1px solid var(--line)}.v500-row{grid-template-columns:38px minmax(0,1fr) auto}.v500-table{min-width:520px}.v500-hide-mobile{display:none !important}.stButton > button{font-size:.77rem !important;padding:.45rem .15rem !important}.v500-my-top{align-items:flex-start}.v500-my-rank{font-size:1.8rem}
}
</style>
"""


def install_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def header(short_season: str) -> None:
    st.markdown(
        f"<div class='v500-header'><div class='v500-header-inner'><div>"
        f"<div class='v500-brand'>Lofthus Road Open</div>"
        f"<div class='v500-season'>Sesong {esc(short_season)}</div>"
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
            if st.button(option, key=f"{key}_{safe}", type="primary" if st.session_state[key] == option else "secondary", use_container_width=True):
                st.session_state[key] = option
                st.rerun()
    return str(st.session_state[key])


def page_title(title: str, sub: str = "") -> None:
    st.markdown(
        f"<div class='v500-page-title'>{esc(title)}</div>" + (f"<div class='v500-page-sub'>{esc(sub)}</div>" if sub else ""),
        unsafe_allow_html=True,
    )


def section(title: str, note: str = "") -> None:
    st.markdown(
        f"<div class='v500-section'><div class='v500-section-title'>{esc(title)}</div><div class='v500-section-note'>{esc(note)}</div></div>",
        unsafe_allow_html=True,
    )


def home_hero(leader: str, leader_points: int, round_winner: str, round_points: int, month_manager: str, month_label: str) -> None:
    leader = leader or "–"
    round_winner = round_winner or "–"
    month_manager = month_manager or "–"
    st.markdown(
        f"""
        <div class='v500-home-hero'>
          <div class='v500-hero-main'>
            <div class='v500-hero-number'>{esc(leader_points)}</div>
            <div class='v500-kicker'>Lofthus akkurat nå</div>
            <div class='v500-hero-title'>{esc(leader)}</div>
            <div class='v500-hero-deck'>{esc(leader_points)} poeng · leder Lofthus Road Open</div>
          </div>
          <div class='v500-hero-side'>
            <div class='v500-hero-mini'>
              <div class='v500-mini-label'>Siste runde</div>
              <div class='v500-mini-value'>{esc(round_winner)}</div>
              <div class='v500-mini-meta'>{esc(round_points)} poeng</div>
            </div>
            <div class='v500-hero-mini'>
              <div class='v500-mini-label'>{esc(month_label)}</div>
              <div class='v500-mini-value'>{esc(month_manager)}</div>
              <div class='v500-mini-meta'>Månedskampen</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def editorial_stories(items: list[str]) -> None:
    if not items:
        return
    bits = []
    for i, text in enumerate(items[:4], start=1):
        bits.append(
            f"<div class='v500-story' data-n='{i:02d}'><div class='v500-story-tag'>Snakkis</div><div class='v500-story-text'>{esc(text)}</div></div>"
        )
    st.markdown("<div class='v500-story-grid'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def my_lofthus_panel(name: str, rank: int, metrics: list[tuple[str, str]], insights: list[str]) -> None:
    metric_html = "".join(
        f"<div class='v500-my-metric'><strong>{esc(value)}</strong><span>{esc(label)}</span></div>" for value, label in metrics[:3]
    )
    insight_html = "".join(f"<li>{esc(text)}</li>" for text in insights[:4])
    st.markdown(
        f"<div class='v500-my'><div class='v500-my-top'><div class='v500-my-name'>{esc(name)}</div><div class='v500-my-rank'>{esc(rank)}.<span>plass</span></div></div>"
        f"<div class='v500-my-metrics'>{metric_html}</div>"
        + (f"<ul class='v500-my-insights'>{insight_html}</ul>" if insight_html else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def stat_strip(items: list[tuple[Any, str]]) -> None:
    bits = [f"<div class='v500-stat'><div class='v500-stat-value'>{esc(value)}</div><div class='v500-stat-label'>{esc(label)}</div></div>" for value, label in items]
    if bits:
        st.markdown("<div class='v500-stats'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def rows(items: list[dict]) -> None:
    bits = []
    for item in items:
        rank = esc(item.get("rank", "")); who = esc(item.get("who", "")); meta = esc(item.get("meta", "")); num = esc(item.get("num", ""))
        rank_class = esc(item.get("rank_class", "")); num_class = esc(item.get("num_class", ""))
        bits.append(
            f"<div class='v500-row'><div class='v500-rank {rank_class}'>{rank}</div>"
            f"<div class='v500-who'>{who}<span class='v500-meta'>{meta}</span></div>"
            f"<div class='v500-num {num_class}'>{num}</div></div>"
        )
    if bits:
        st.markdown("<div class='v500-list'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def inline_note(label: str, text: str) -> None:
    if not str(text or "").strip():
        return
    st.markdown(f"<div style='margin:.35rem 0 .9rem;color:var(--muted);font-size:.81rem'><strong style='color:var(--text)'>{esc(label)}</strong> · {esc(text)}</div>", unsafe_allow_html=True)


def html_table(headers: list[tuple[str, str]], data: list[dict], right: set[str] | None = None, hide_mobile: set[str] | None = None) -> None:
    right = right or set(); hide_mobile = hide_mobile or set(); th = []
    for key, label in headers:
        classes = (["right"] if key in right else []) + (["v500-hide-mobile"] if key in hide_mobile else [])
        th.append(f"<th class='{' '.join(classes)}'>{esc(label)}</th>")
    trs = []
    for row in data:
        cells = []
        for key, _ in headers:
            classes = (["right"] if key in right else []) + (["v500-hide-mobile"] if key in hide_mobile else [])
            value = row.get(key, "")
            if key in {"manager", "player", "name", "winner"}: classes.append("strong")
            if isinstance(value, dict) and ("main" in value or "sub" in value):
                rendered = f"<span class='v500-cell-main'>{esc(value.get('main',''))}</span>"
                if value.get("sub"): rendered += f"<span class='v500-cell-meta'>{esc(value.get('sub'))}</span>"
            else: rendered = esc(value)
            cells.append(f"<td class='{' '.join(classes)}'>{rendered}</td>")
        trs.append("<tr>" + "".join(cells) + "</tr>")
    st.markdown("<div class='v500-table-wrap'><table class='v500-table'><thead><tr>" + "".join(th) + "</tr></thead><tbody>" + "".join(trs) + "</tbody></table></div>", unsafe_allow_html=True)


def live_panel(score: str, sub: str = "") -> None:
    st.markdown(
        f"<div class='v500-live'><div class='v500-live-kicker'><span class='v500-live-dot'></span>Live</div><div class='v500-live-score'>{esc(score)}</div>"
        + (f"<div class='v500-live-sub'>{esc(sub)}</div>" if sub else "") + "</div>",
        unsafe_allow_html=True,
    )


def callout(title: str, text: str, tone: str = "") -> None:
    cls = tone if tone in {"green", "red"} else ""
    st.markdown(f"<div class='v500-callout {cls}'><strong>{esc(title)}</strong><span>{esc(text)}</span></div>", unsafe_allow_html=True)


def alert(title: str, main: str) -> None:
    st.markdown(f"<div class='v500-alert'><div class='v500-alert-bar'></div><div class='v500-alert-body'><div class='v500-alert-title'>{esc(title)}</div><div class='v500-alert-main'>{esc(main)}</div></div></div>", unsafe_allow_html=True)


def profile_header(name: str, team: str) -> None:
    st.markdown(f"<div class='v500-profile'><div class='v500-profile-name'>{esc(name)}</div><div class='v500-profile-team'>{esc(team)}</div></div>", unsafe_allow_html=True)


def merits(items: list[tuple[Any, str]]) -> None:
    bits = [f"<div class='v500-merit'><strong>{esc(value)}</strong><span>{esc(label)}</span></div>" for value, label in items]
    st.markdown("<div class='v500-merits'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def recommendation(name: str, label: str, meta: str, reasons: list[str]) -> None:
    reason_html = "".join(f"<li>{esc(r)}</li>" for r in reasons[:4])
    st.markdown(f"<div class='v500-rec'><div class='v500-rec-top'><div class='v500-rec-name'>{esc(name)}</div><div class='v500-rec-label'>{esc(label)}</div></div><div class='v500-rec-meta'>{esc(meta)}</div><ul class='v500-reasons'>{reason_html}</ul></div>", unsafe_allow_html=True)


def sortable_league_table(rows: list[dict]) -> None:
    payload = json.dumps(rows or [], ensure_ascii=False).replace("</", "<\\/")
    doc = r"""
<!doctype html><html><head><meta charset="utf-8"><style>
:root{--line:#d6d9de;--text:#121824;--muted:#687386;--gold:#b88920;--green:#167a52;--red:#b63a34}
*{box-sizing:border-box}body{margin:0;background:transparent;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--text)}
.wrap{width:100%;overflow-x:auto;border:1px solid var(--line);border-radius:13px;background:rgba(255,255,255,.42)}table{border-collapse:collapse;width:100%;min-width:720px}th{text-align:left;color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.075em;font-weight:900;padding:12px 10px;border-bottom:1px solid var(--line);cursor:pointer;user-select:none;background:rgba(8,17,31,.025)}td{padding:13px 10px;border-bottom:1px solid var(--line);vertical-align:middle;font-size:13.5px}tbody tr:last-child td{border-bottom:0}tr:hover td{background:rgba(255,255,255,.58)}.right{text-align:right;white-space:nowrap}.manager{font-weight:900}.team{font-weight:700}.chip{display:block;color:var(--muted);font-size:11.5px;font-weight:700;margin-top:2px}.rank{font-weight:900;color:var(--muted)}.rank.gold{color:#977013}.rank.silver{color:#657080}.rank.bronze{color:#925f3a}.up{color:var(--green);font-weight:900}.down{color:var(--red);font-weight:900}.sort{margin-left:5px;color:var(--gold)}
@media(max-width:760px){table{min-width:560px}th,td{padding:10px 7px}}
</style></head><body><div class="wrap"><table><thead><tr><th data-k="rank" data-type="n">#</th><th data-k="manager">Manager</th><th data-k="team">Lag</th><th class="right" data-k="gw" data-type="n">GW</th><th class="right" data-k="points" data-type="n">Poeng</th><th class="right" data-k="move" data-type="n">+/-</th></tr></thead><tbody id="body"></tbody></table></div><script>
const rows=__ROWS__; let key='rank', dir=1; const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function cmp(a,b){let av=a[key],bv=b[key];if(typeof av==='number'||typeof bv==='number'){av=(av===null||av===undefined)?1e15:Number(av);bv=(bv===null||bv===undefined)?1e15:Number(bv);return(av-bv)*dir}return String(av||'').localeCompare(String(bv||''),'nb')*dir}
function render(){const body=document.getElementById('body');body.innerHTML='';[...rows].sort(cmp).forEach(r=>{const tr=document.createElement('tr');const rc=r.rank===1?'gold':r.rank===2?'silver':r.rank===3?'bronze':'';const mv=Number(r.move||0);const move=mv>0?'↑'+mv:mv<0?'↓'+Math.abs(mv):'–';const mc=mv>0?'up':mv<0?'down':'';tr.innerHTML=`<td><span class="rank ${rc}">${esc(r.rank??'')}</span></td><td class="manager">${esc(r.manager)}</td><td><span class="team">${esc(r.team)}</span>${r.chip?`<span class="chip">${esc(r.chip)}</span>`:''}</td><td class="right">${esc(r.gw)}</td><td class="right"><strong>${esc(r.points)}</strong></td><td class="right ${mc}">${move}</td>`;body.appendChild(tr)});document.querySelectorAll('th').forEach(th=>{th.querySelectorAll('.sort').forEach(x=>x.remove());if(th.dataset.k===key){const x=document.createElement('span');x.className='sort';x.textContent=dir===1?'▲':'▼';th.appendChild(x)}})}
document.querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(key===k)dir*=-1;else{key=k;dir=(k==='manager'||k==='team')?1:(k==='move'?-1:1)}render()});render();
</script></body></html>
""".replace("__ROWS__", payload)
    height = min(3400, max(420, 58 + 48 * len(rows or [])))
    components.html(doc, height=height, scrolling=False)


def captain_board(rows: list[dict]) -> None:
    """Interactive captain list with a side detail panel on desktop."""
    if not rows:
        st.caption("Kapteinsdata er ikke tilgjengelig akkurat nå.")
        return
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    doc = r"""
<!doctype html><html><head><meta charset="utf-8"><style>
:root{--line:#d6d9de;--text:#121824;--muted:#687386;--gold:#b88920;--ink:#08111f;--red:#b63a34}
*{box-sizing:border-box}body{margin:0;background:transparent;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:var(--text)}
.board{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(260px,.7fr);gap:14px}.list,.detail{border:1px solid var(--line);border-radius:13px;background:rgba(255,255,255,.46);overflow:hidden}.list{max-height:520px;overflow-y:auto}.row{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:9px;align-items:center;padding:12px 13px;border-bottom:1px solid var(--line);cursor:pointer}.row:last-child{border-bottom:0}.row:hover,.row.active{background:rgba(184,137,32,.07)}.rank{font-size:11px;color:var(--muted);font-weight:900}.name{font-weight:900;font-size:14px}.meta{display:block;color:var(--muted);font-size:11.5px;font-weight:650;margin-top:2px}.count{font-weight:900;font-size:13px;white-space:nowrap}.detail{padding:16px;min-height:250px;position:sticky;top:0;max-height:520px;overflow-y:auto}.eyebrow{text-transform:uppercase;letter-spacing:.085em;color:var(--gold);font-size:10px;font-weight:950}.dname{font-weight:950;font-size:25px;letter-spacing:-.045em;margin:5px 0 2px}.dmeta{font-size:12px;color:var(--muted);font-weight:650}.group{margin-top:17px;border-top:1px solid var(--line);padding-top:10px}.label{font-size:10px;text-transform:uppercase;letter-spacing:.07em;font-weight:900;color:var(--muted);margin-bottom:6px}.person{font-size:12.5px;font-weight:750;padding:5px 0}.tc{color:var(--red)}
@media(max-width:760px){.board{grid-template-columns:1fr}.detail{position:static}.list{max-height:360px}}
</style></head><body><div class="board"><div class="list" id="list"></div><div class="detail" id="detail"></div></div><script>
const rows=__ROWS__;let selected=0;const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function countText(r){const b=[];if(r.regular)b.push(r.regular+' C');if(r.tc)b.push(r.tc+' TC');return b.join(' · ')}
function draw(){const list=document.getElementById('list');list.innerHTML='';rows.forEach((r,i)=>{const e=document.createElement('div');e.className='row'+(i===selected?' active':'');const preview=(r.people||[]).slice(0,4).map(p=>p.name+(p.tc?' (TC)':'')).join(', ')+(r.people&&r.people.length>4?' +'+(r.people.length-4):'');e.innerHTML=`<div class="rank">${i+1}</div><div><div class="name">${esc(r.player)}</div><span class="meta">${esc(preview)}</span></div><div class="count">${esc(countText(r))}</div>`;e.onclick=()=>{selected=i;draw()};list.appendChild(e)});drawDetail()}
function drawDetail(){const r=rows[selected]||{};const detail=document.getElementById('detail');const regular=(r.people||[]).filter(p=>!p.tc);const tc=(r.people||[]).filter(p=>p.tc);let html=`<div class="eyebrow">Full kapteinsoversikt</div><div class="dname">${esc(r.player||'')}</div><div class="dmeta">${esc(countText(r))}${r.points!==undefined?' · '+esc(r.points)+' spillerpoeng':''}</div>`;if(tc.length){html+=`<div class="group"><div class="label">Triple Captain</div>${tc.map(p=>`<div class="person tc">${esc(p.name)}</div>`).join('')}</div>`}if(regular.length){html+=`<div class="group"><div class="label">Kaptein</div>${regular.map(p=>`<div class="person">${esc(p.name)}</div>`).join('')}</div>`}detail.innerHTML=html}draw();
</script></body></html>
""".replace("__ROWS__", payload)
    components.html(doc, height=640, scrolling=False)


def hall_of_fame(rows_data: list[dict]) -> None:
    if not rows_data:
        st.caption("Ingen historikk funnet.")
        return
    top = rows_data[:3]
    cards = []
    for i, row in enumerate(top, start=1):
        cls = " first" if i == 1 else ""
        cards.append(f"<div class='v500-hof-card{cls}'><div class='v500-hof-place'>0{i}</div><div class='v500-hof-name'>{esc(row.get('who'))}</div><div class='v500-hof-meta'>{esc(row.get('meta'))}</div></div>")
    st.markdown("<div class='v500-hof-podium'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
    if len(rows_data) > 3:
        rows(rows_data[3:])


def odds_table(df: pd.DataFrame) -> None:
    if df is None or df.empty:
        st.caption("Før-sesongoddsen er ikke tilgjengelig akkurat nå.")
        return
    data = []
    for r in df.to_dict("records"):
        data.append({"rank": r.get("preseason_rank"), "manager": r.get("manager"), "winner": f"{float(r.get('winner_odds')):.2f}", "top3": f"{float(r.get('top3_odds')):.2f}"})
    html_table([("rank","#"),("manager","Manager"),("winner","Vinner"),("top3","Topp 3")], data, right={"winner","top3"})


def season_archive(df: pd.DataFrame, kind: str = "league") -> None:
    if df is None or df.empty:
        st.caption("Ingen historikk akkurat nå.")
        return
    items = []
    for r in df.to_dict("records"):
        if kind == "cup":
            meta = f"Finalist: {r.get('runner_up') or '–'}"
            who = r.get("winner") or "–"
        else:
            silver = r.get("runner_up") or "–"; bronze = r.get("third_place") or "–"
            meta = f"2. {silver} · 3. {bronze}"
            who = r.get("winner") or "–"
        items.append({"rank": r.get("season"), "who": who, "meta": meta, "num": "Vinner"})
    rows(items)


def dataframe_compact(df: pd.DataFrame, columns: list[str], labels: dict[str, str] | None = None) -> None:
    if df is None or df.empty:
        st.caption("Ingen data akkurat nå.")
        return
    work = df.copy()
    for col in columns:
        if col not in work.columns: work[col] = ""
    work = work[columns].fillna("")
    headers = [(col, (labels or {}).get(col, col)) for col in columns]
    html_table(headers, work.to_dict("records"))
