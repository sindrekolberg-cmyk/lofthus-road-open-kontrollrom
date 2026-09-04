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

/* V603 front-page scoreline: newspaper masthead strip, not a giant hero */
.v603-scoreline{display:grid;grid-template-columns:1.35fr 1fr 1fr;margin:.55rem 0 .7rem;border-top:3px solid var(--ink);border-bottom:1px solid var(--line);background:transparent}
.v603-score-item{min-width:0;padding:.68rem 1rem .7rem 0}
.v603-score-item + .v603-score-item{padding-left:1rem;border-left:1px solid var(--line)}
.v603-score-kicker{font-size:.63rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;color:var(--gold);margin-bottom:.22rem}
.v603-score-name{font-size:1.28rem;line-height:1.05;font-weight:950;letter-spacing:-.045em;color:var(--text);white-space:normal}
.v603-score-item.lead .v603-score-name{font-size:1.55rem}
.v603-score-meta{margin-top:.18rem;color:var(--muted);font-size:.76rem;font-weight:700}
.v603-front-section{margin:.7rem 0 .42rem;display:flex;align-items:end;justify-content:space-between;gap:1rem;border-bottom:2px solid var(--ink);padding-bottom:.38rem}
.v603-front-section-title{font-size:1.22rem;font-weight:950;letter-spacing:-.04em}
.v603-front-section-note{font-size:.73rem;color:var(--muted);font-weight:700}
.v603-popular .v500-row{padding:.72rem .1rem}
.v603-popular .v500-who{font-size:.94rem}
.v603-popular .v500-meta{font-size:.72rem}
.v603-popular .v500-num{font-size:.82rem}

/* editorial stories: one list, no dashboard cards */
.v500-story-list{border-top:1px solid var(--line);margin:.45rem 0 1.2rem}
.v500-story-line{display:grid;grid-template-columns:46px minmax(0,1fr);gap:.75rem;align-items:start;padding:.9rem .1rem;border-bottom:1px solid var(--line)}
.v500-story-line:hover{background:rgba(255,255,255,.34)}
.v500-story-n{font-size:1.42rem;line-height:1;font-weight:950;letter-spacing:-.06em;color:rgba(184,137,32,.8)}
.v500-story-text{font-weight:900;font-size:1rem;line-height:1.38;letter-spacing:-.02em}

/* My Lofthus: editorial strip rather than another card */
.v500-my{padding:.9rem 0 0;border-top:2px solid var(--ink);border-bottom:1px solid var(--line);margin:.55rem 0 1.1rem}
.v500-my-top{display:flex;justify-content:space-between;gap:1rem;align-items:baseline;padding:0 .05rem .75rem}
.v500-my-name{font-size:1.5rem;font-weight:950;letter-spacing:-.045em}
.v500-my-rank{font-size:2.1rem;font-weight:950;letter-spacing:-.07em;color:var(--ink)}
.v500-my-rank span{font-size:.7rem;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);margin-left:.3rem}
.v500-my-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--line)}
.v500-my-metric{padding:.72rem .8rem .72rem 0}
.v500-my-metric + .v500-my-metric{padding-left:.9rem;border-left:1px solid var(--line)}
.v500-my-metric strong{display:block;font-size:1.08rem}
.v500-my-metric span{font-size:.72rem;color:var(--muted);font-weight:700}
.v500-my-insights{margin:.1rem 0 0;padding:.72rem 0 .8rem 1.05rem;border-top:1px solid var(--line);color:#4e5969;font-size:.84rem;line-height:1.55}

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
.v500-who {font-weight:900; min-width:0; letter-spacing:-.015em;}.v500-row-link{color:inherit;text-decoration:none}.v500-row-link:hover{text-decoration:underline;text-decoration-color:var(--gold);text-underline-offset:3px}
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
.v500-live-kicker {font-size:.7rem; font-weight:950; letter-spacing:.09em; text-transform:uppercase; color:#ffb6ba; display:flex; gap:.5rem; align-items:center;}
.v500-live-dot {width:8px;height:8px;border-radius:50%;background:#ef3f4c;box-shadow:0 0 0 4px rgba(239,63,76,.14);animation:lro-live-blink 1.15s ease-in-out infinite;}
.v500-live-score {font-size:1.25rem; font-weight:950; margin:.45rem 0 .2rem;}.v500-live-sub {color:#b8c3d4;font-size:.8rem;}
@keyframes lro-live-blink{0%,100%{opacity:1;box-shadow:0 0 0 4px rgba(239,63,76,.13),0 0 0 0 rgba(239,63,76,.28)}50%{opacity:.45;box-shadow:0 0 0 4px rgba(239,63,76,.06),0 0 0 8px rgba(239,63,76,0)}}
@media (prefers-reduced-motion: reduce){.v500-live-dot{animation:none}}

/* V701 live centre: compact sports ticker, not another dashboard card */
.v701-livebar{position:relative;overflow:hidden;margin:.8rem 0 1.15rem;padding:.75rem 0 .68rem;border-top:1px solid rgba(239,63,76,.32);border-bottom:1px solid var(--line);}
.v701-livebar-head{display:flex;align-items:center;gap:.55rem;margin-bottom:.5rem}.v701-livebar-title{font-size:.72rem;font-weight:950;letter-spacing:.095em;text-transform:uppercase;color:#ef3f4c !important}.v701-livebar .v500-live-dot{background:#ef3f4c !important;box-shadow:0 0 0 4px rgba(239,63,76,.14),0 0 12px rgba(239,63,76,.35) !important;animation:lro-live-blink 1.05s ease-in-out infinite !important}.v701-livebar-gw{font-size:.7rem;color:var(--muted);font-weight:800;margin-left:auto}
.v701-fixtures{display:flex;gap:.7rem 1.25rem;flex-wrap:wrap;align-items:baseline}.v701-fixture{font-size:1.03rem;font-weight:950;letter-spacing:-.018em}.v701-fixture span{color:var(--red);font-size:.72rem;margin-left:.28rem;letter-spacing:0;font-weight:900}
.v701-live-label{font-size:.68rem;text-transform:uppercase;letter-spacing:.085em;color:var(--muted);font-weight:950;margin:.45rem 0 .1rem}
@media(max-width:700px){.v701-fixture{font-size:.94rem}.v701-livebar{margin-top:.6rem}}

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

/* V605 manager profile: denser, editorial, useful above the fold */
.v605-profile{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:17px;background:linear-gradient(125deg,rgba(255,255,255,.82),rgba(244,241,233,.68));box-shadow:0 10px 28px rgba(8,17,31,.04);padding:1.05rem 1.15rem .9rem}
.v605-profile:after{content:"";position:absolute;right:-55px;top:-85px;width:250px;height:250px;border:1px solid rgba(184,137,32,.11);border-radius:50%;box-shadow:0 0 0 44px rgba(184,137,32,.025);pointer-events:none}
.v605-profile-top{position:relative;z-index:1;display:flex;align-items:flex-end;justify-content:space-between;gap:1.2rem}
.v605-profile-name{font-size:clamp(1.7rem,3vw,2.5rem);font-weight:950;letter-spacing:-.055em;line-height:1}.v605-profile-team{font-size:.78rem;color:var(--muted);font-weight:700;margin-top:.35rem}
.v605-profile-stats{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,minmax(90px,1fr));border-top:1px solid var(--line);margin-top:.9rem;padding-top:.72rem}
.v605-profile-stat{padding:0 .85rem}.v605-profile-stat:first-child{padding-left:0}.v605-profile-stat+.v605-profile-stat{border-left:1px solid var(--line)}
.v605-profile-stat strong{display:block;font-size:1.18rem;font-weight:950;letter-spacing:-.035em;line-height:1.05}.v605-profile-stat span{display:block;color:var(--muted);font-size:.64rem;text-transform:uppercase;letter-spacing:.065em;font-weight:900;margin-top:.22rem}
.v605-honours{border-top:2px solid var(--gold);border-bottom:1px solid var(--line);padding:.65rem .1rem .72rem;margin:.15rem 0 .8rem}.v605-honours-title{font-size:.68rem;text-transform:uppercase;letter-spacing:.085em;color:var(--gold);font-weight:950;margin-bottom:.35rem}.v605-honours-line{font-size:1rem;font-weight:900;line-height:1.45}.v605-honours-empty{font-size:.78rem;color:var(--muted)}
.v605-sidebox{border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.5);padding:.9rem 1rem;margin:.15rem 0 1rem}.v605-sidebox-title{font-size:.7rem;text-transform:uppercase;letter-spacing:.085em;color:var(--muted);font-weight:950;margin-bottom:.6rem}.v605-sidegrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.62rem .9rem}.v605-side-stat strong{display:block;font-size:1.02rem;font-weight:950;letter-spacing:-.025em}.v605-side-stat span{display:block;font-size:.64rem;color:var(--muted);font-weight:800;margin-top:.08rem}.v605-history-list{border-top:1px solid var(--line);margin-top:.7rem;padding-top:.32rem}.v605-history-row{display:grid;grid-template-columns:64px minmax(0,1fr) auto;gap:.55rem;align-items:center;padding:.38rem 0;border-bottom:1px solid rgba(214,217,222,.7);font-size:.72rem}.v605-history-row:last-child{border-bottom:0}.v605-history-season{font-weight:900}.v605-history-points{color:var(--muted);font-weight:750}.v605-history-rank{font-weight:900;white-space:nowrap}
.v605-oddsgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.65rem;margin-top:.4rem}.v605-oddsitem{padding:.55rem 0;border-top:1px solid var(--line)}.v605-oddsitem strong{display:block;font-size:1.03rem;font-weight:950}.v605-oddsitem span{display:block;color:var(--muted);font-size:.65rem;font-weight:800;margin-top:.12rem}
.v605-compact-form .v500-row{padding:.62rem .15rem}.v605-compact-form .v500-meta{font-size:.7rem}.v605-manager-grid{align-items:start}

/* V605 player overview: top answers first, deep detail on demand */
.v605-overview-note{font-size:.74rem;color:var(--muted);font-weight:700;margin:.2rem 0 .45rem}.v605-mini-head{display:flex;justify-content:space-between;align-items:baseline;gap:.8rem;border-bottom:1px solid var(--line);padding-bottom:.38rem;margin-bottom:.1rem}.v605-mini-title{font-weight:950;font-size:1rem;letter-spacing:-.025em}.v605-mini-note{font-size:.68rem;color:var(--muted);font-weight:750}

/* recommendations */
.v500-rec {padding:1rem 0; border-bottom:1px solid var(--line)}.v500-rec-top {display:flex;justify-content:space-between;align-items:baseline;gap:1rem}.v500-rec-name {font-size:1.15rem;font-weight:950}.v500-rec-label {font-size:.72rem;font-weight:950;text-transform:uppercase;letter-spacing:.065em;color:var(--green)}.v500-rec-meta {font-size:.81rem;color:var(--muted);margin:.22rem 0 .45rem}.v500-reasons {margin:.35rem 0 0;padding-left:1.05rem;color:#4f5969;font-size:.84rem;line-height:1.5}

/* Hall of Fame: one continuous honours list */
.v500-hof-list{border-top:1px solid var(--line);margin-top:.65rem}
.v500-hof-row{position:relative;display:grid;grid-template-columns:64px minmax(0,1fr);gap:.9rem;align-items:center;padding:1rem .55rem;border-bottom:1px solid var(--line);overflow:hidden}
.v500-hof-row:hover{background:rgba(255,255,255,.4)}
.v500-hof-row.top1{background:linear-gradient(90deg,#0a1424 0%,#101d31 62%,rgba(16,29,49,.94) 100%);color:#fff;border-radius:10px;margin:.28rem 0;border-bottom-color:transparent;padding-left:.8rem;padding-right:.8rem}
.v500-hof-row.top2{background:linear-gradient(90deg,rgba(108,119,135,.10),transparent 72%)}
.v500-hof-row.top3{background:linear-gradient(90deg,rgba(146,95,58,.10),transparent 72%)}
.v500-hof-place{font-size:1.8rem;font-weight:950;letter-spacing:-.07em;color:rgba(18,24,36,.24)}
.v500-hof-row.top1 .v500-hof-place{color:var(--gold-soft)}
.v500-hof-row.top2 .v500-hof-place{color:#657080}.v500-hof-row.top3 .v500-hof-place{color:#925f3a}
.v500-hof-name{font-size:1.04rem;font-weight:950;letter-spacing:-.025em}.v500-hof-row.top1 .v500-hof-name{font-size:1.15rem;color:#fff}
.v500-hof-meta{font-size:.78rem;color:var(--muted);font-weight:650;margin-top:.18rem;line-height:1.4}.v500-hof-row.top1 .v500-hof-meta{color:#bdc7d6}

/* V604 manager squad: actual FPL-style formation, not an eleven-row receipt */
.v604-squad-wrap{margin:.3rem 0 .75rem}
.v604-pitch{position:relative;overflow:hidden;border-radius:18px;min-height:455px;padding:.9rem .85rem;background:linear-gradient(180deg,#173d31 0%,#12372c 52%,#0f3128 100%);border:1px solid rgba(255,255,255,.18);box-shadow:0 18px 42px rgba(8,17,31,.12);display:flex;flex-direction:column;justify-content:space-between;gap:.38rem}
.v604-pitch:before{content:"";position:absolute;inset:1rem;border:2px solid rgba(244,241,233,.28);border-radius:4px;pointer-events:none}
.v604-pitch:after{content:"";position:absolute;left:50%;top:1rem;bottom:1rem;width:2px;background:rgba(244,241,233,.22);transform:translateX(-50%);pointer-events:none}
.v604-center-circle{position:absolute;left:50%;top:50%;width:112px;height:112px;border:2px solid rgba(244,241,233,.22);border-radius:50%;transform:translate(-50%,-50%);pointer-events:none}
.v604-formation{position:absolute;right:1.45rem;top:1.2rem;color:rgba(255,255,255,.72);font-size:.7rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase;z-index:2}
.v604-line{position:relative;z-index:3;display:flex;justify-content:space-evenly;align-items:center;gap:.55rem;min-height:70px}
.v604-player{position:relative;width:min(150px,19%);min-width:96px;text-align:center;background:rgba(255,253,248,.94);border:1px solid rgba(255,255,255,.42);border-radius:11px;padding:.44rem .34rem .42rem;box-shadow:0 8px 18px rgba(4,14,11,.19)}
.v604-player-name{font-size:.84rem;font-weight:950;letter-spacing:-.025em;color:var(--ink);line-height:1.08;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.v604-player-meta{font-size:.66rem;font-weight:750;color:#687386;margin-top:.25rem;white-space:nowrap}
.v604-badge{position:absolute;top:-8px;right:-7px;min-width:24px;height:24px;padding:0 5px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:var(--ink);color:#fff;font-size:.62rem;font-weight:950;border:2px solid #f4f1e9}
.v604-badge.tc{background:#b63a34}.v604-badge.vc{background:#657084}
.v604-bench-label{font-size:.62rem;font-weight:950;letter-spacing:.11em;text-transform:uppercase;color:rgba(255,255,255,.68);margin:0 0 .28rem}
.v604-bench-shell{position:relative;z-index:4;margin-top:.12rem;padding:.5rem .55rem .45rem;background:rgba(5,18,15,.32);border-top:1px solid rgba(255,255,255,.18);border-radius:0 0 10px 10px}
.v604-bench{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.35rem}
.v604-bench-player{padding:.42rem .45rem;min-width:0;background:rgba(255,253,248,.91);border-radius:8px;text-align:center}.v604-bench-player + .v604-bench-player{border-left:0}
.v604-bench-name{font-size:.72rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink)}.v604-bench-meta{font-size:.59rem;color:#687386;font-weight:750;margin-top:.15rem;white-space:nowrap}
@media(max-width:760px){.v604-pitch{min-height:440px;padding:.9rem .35rem}.v604-line{gap:.2rem;min-height:76px}.v604-player{min-width:0;width:auto;flex:0 1 22%;padding:.43rem .22rem}.v604-player-name{font-size:.68rem}.v604-player-meta{font-size:.58rem}.v604-bench{grid-template-columns:repeat(2,minmax(0,1fr))}.v604-bench-player:nth-child(3),.v604-bench-player:nth-child(4){border-top:0}}

/* expander */
[data-testid="stExpander"] {border:1px solid var(--line) !important; border-radius:11px !important; background:rgba(255,255,255,.3) !important;}

@media(max-width:900px){.v603-scoreline{grid-template-columns:1fr 1fr}.v603-score-item.lead{grid-column:1/-1;border-bottom:1px solid var(--line)}.v603-score-item:nth-child(2){padding-left:0;border-left:0}.v500-hof-row{grid-template-columns:52px minmax(0,1fr)}}
@media(max-width:760px){
 .block-container{padding:.7rem .72rem 3rem !important}.v500-header{border-radius:14px;padding:1.1rem 1.05rem 1rem}.v500-brand{font-size:2.2rem}.v500-page-title{font-size:2.15rem}.v500-section{margin-top:1.55rem}.v603-scoreline{grid-template-columns:1fr;margin-top:.4rem}.v603-score-item,.v603-score-item + .v603-score-item{padding:.6rem .05rem;border-left:0;border-bottom:1px solid var(--line)}.v603-score-item:last-child{border-bottom:0}.v603-score-item.lead{grid-column:auto}.v603-score-item.lead .v603-score-name{font-size:1.3rem}.v603-score-name{font-size:1.05rem}.v500-story-list{display:block}.v500-my-metrics{grid-template-columns:1fr}.v500-stats{grid-template-columns:repeat(2,1fr)}.v500-stat:nth-child(3){border-left:0;padding-left:0;border-top:1px solid var(--line)}.v500-stat:nth-child(4){border-top:1px solid var(--line)}.v500-row{grid-template-columns:38px minmax(0,1fr) auto}.v500-table{min-width:520px}.v500-hide-mobile{display:none !important}.stButton > button{font-size:.77rem !important;padding:.45rem .15rem !important}.v500-my-top{align-items:flex-start}.v500-my-rank{font-size:1.8rem}.v605-profile-top{align-items:flex-start}.v605-profile-stats{grid-template-columns:repeat(2,1fr)}.v605-profile-stat{padding:.5rem .45rem}.v605-profile-stat:nth-child(3){border-left:0}.v605-profile-stat:nth-child(n+3){border-top:1px solid var(--line)}.v605-sidegrid,.v605-oddsgrid{grid-template-columns:1fr 1fr}
}

/* V700: personal newspaper front page + tighter profile/rival surfaces */
.v700-personal{margin:.55rem 0 .75rem;border-top:3px solid var(--ink);border-bottom:1px solid var(--line);padding:.78rem 0 .72rem;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:1.3rem;align-items:end}
.v700-personal-kicker{font-size:.63rem;text-transform:uppercase;letter-spacing:.11em;color:var(--gold);font-weight:950}.v700-personal-name{font-size:clamp(1.6rem,3vw,2.5rem);font-weight:950;letter-spacing:-.055em;line-height:.98;margin:.24rem 0 .26rem}.v700-personal-sub{color:var(--muted);font-size:.79rem;font-weight:750}
.v700-personal-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-left:1px solid var(--line)}.v700-personal-metric{padding:.18rem .8rem}.v700-personal-metric+.v700-personal-metric{border-left:1px solid var(--line)}.v700-personal-metric strong{display:block;font-size:1.12rem;font-weight:950}.v700-personal-metric span{display:block;color:var(--muted);font-size:.66rem;font-weight:800;margin-top:.12rem;line-height:1.25}.v700-personal-insight{grid-column:1/-1;border-top:1px solid var(--line);padding-top:.55rem;margin-top:.2rem;color:#4e5969;font-size:.78rem;font-weight:720}
.v700-identity-picker{margin:.5rem 0 .65rem;padding:.58rem 0;border-top:2px solid var(--ink);border-bottom:1px solid var(--line)}
.v700-career{border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.46);padding:.9rem 1rem;margin:.15rem 0 1rem}.v700-career-head{display:flex;justify-content:space-between;gap:.8rem;align-items:baseline;margin-bottom:.55rem}.v700-career-title{font-size:.72rem;text-transform:uppercase;letter-spacing:.085em;color:var(--muted);font-weight:950}.v700-live-badge{font-size:.64rem;color:var(--green);font-weight:950;text-transform:uppercase;letter-spacing:.065em}.v700-odds-note{font-size:.66rem;color:var(--muted);font-weight:750;line-height:1.35;margin-top:.4rem;padding-top:.4rem;border-top:1px solid var(--line)}
.v700-merits{display:flex;flex-wrap:wrap;gap:.4rem .8rem;border-top:2px solid var(--gold);border-bottom:1px solid var(--line);padding:.62rem 0 .66rem;margin:.15rem 0 .8rem}.v700-merit{font-size:.91rem;font-weight:900}.v700-merit strong{color:var(--gold);font-size:1.02rem;margin-right:.18rem}.v700-merit-empty{color:var(--muted);font-size:.78rem}
.v700-meta-links a{color:inherit;text-decoration:none;font-weight:800}.v700-meta-links a:hover{text-decoration:underline;text-decoration-color:var(--gold);text-underline-offset:2px}
.v700-rival-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin:.2rem 0 .6rem}.v700-rival-col{min-width:0}.v700-rival-title{font-size:.72rem;text-transform:uppercase;letter-spacing:.075em;color:var(--muted);font-weight:950;border-bottom:1px solid var(--line);padding-bottom:.35rem;margin-bottom:.05rem}
.v700-status{display:inline-block;margin-left:.25rem;font-size:.58rem;font-weight:950;color:var(--red);text-transform:uppercase;letter-spacing:.04em}
@media(max-width:900px){.v700-personal{grid-template-columns:1fr}.v700-personal-metrics{border-left:0;border-top:1px solid var(--line);padding-top:.55rem}.v700-rival-summary{grid-template-columns:1fr}}
@media(max-width:760px){.v700-personal-metrics{grid-template-columns:1fr}.v700-personal-metric,.v700-personal-metric+.v700-personal-metric{border-left:0;padding:.35rem 0;border-bottom:1px solid var(--line)}.v700-personal-metric:last-child{border-bottom:0}}

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


def home_scoreline(leader: str, leader_points: int, round_winner: str, round_points: int, month_manager: str, month_label: str) -> None:
    """Compact front-page scoreline. The tables and stories are the real front-page leads."""
    leader = leader or "–"
    round_winner = round_winner or "–"
    month_manager = month_manager or "–"
    st.markdown(
        f"""
        <div class='v603-scoreline'>
          <div class='v603-score-item lead'>
            <div class='v603-score-kicker'>Leder akkurat nå</div>
            <div class='v603-score-name'>{esc(leader)}</div>
            <div class='v603-score-meta'>{esc(leader_points)} poeng · leder Lofthus Road Open</div>
          </div>
          <div class='v603-score-item'>
            <div class='v603-score-kicker'>Forrige runde</div>
            <div class='v603-score-name'>{esc(round_winner)}</div>
            <div class='v603-score-meta'>{esc(round_points)} poeng</div>
          </div>
          <div class='v603-score-item'>
            <div class='v603-score-kicker'>{esc(month_label)}</div>
            <div class='v603-score-name'>{esc(month_manager)}</div>
            <div class='v603-score-meta'>Månedskampen</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def home_hero(leader: str, leader_points: int, round_winner: str, round_points: int, month_manager: str, month_label: str) -> None:
    # Backwards-compatible alias; V603 deliberately removes the oversized hero composition.
    home_scoreline(leader, leader_points, round_winner, round_points, month_manager, month_label)


def front_section(title: str, note: str = "") -> None:
    st.markdown(
        f"<div class='v603-front-section'><div class='v603-front-section-title'>{esc(title)}</div><div class='v603-front-section-note'>{esc(note)}</div></div>",
        unsafe_allow_html=True,
    )


def editorial_stories(items: list[str]) -> None:
    """Render Snakkiser as an editorial rundown, never as a card grid."""
    if not items:
        return
    bits = []
    for i, text in enumerate(items[:4], start=1):
        bits.append(
            f"<div class='v500-story-line'><div class='v500-story-n'>{i:02d}</div><div class='v500-story-text'>{esc(text)}</div></div>"
        )
    st.markdown("<div class='v500-story-list'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


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



def personal_home_lead(name: str, team: str, rank: int, points: int, metrics: list[tuple[Any, str]], insight: str = "") -> None:
    metric_html = "".join(
        f"<div class='v700-personal-metric'><strong>{esc(v)}</strong><span>{esc(l)}</span></div>" for v, l in metrics[:3]
    )
    insight_html = f"<div class='v700-personal-insight'>{esc(insight)}</div>" if insight else ""
    st.markdown(
        f"<div class='v700-personal'><div><div class='v700-personal-kicker'>Mitt Lofthus</div>"
        f"<div class='v700-personal-name'>{esc(name)}</div><div class='v700-personal-sub'>{esc(team)} · {esc(rank)}. plass · {esc(points)} poeng</div></div>"
        f"<div class='v700-personal-metrics'>{metric_html}</div>{insight_html}</div>",
        unsafe_allow_html=True,
    )


def career_odds_panel(stats: list[tuple[Any, str]], seasons: list[dict], pre_win: str, pre_top3: str, live_win: str, live_pct: str = "", live_note: str = "") -> None:
    stat_html = "".join(
        f"<div class='v605-side-stat'><strong>{esc(value)}</strong><span>{esc(label)}</span></div>" for value, label in stats[:4]
    )
    hist = []
    for r in seasons[:5]:
        hist.append(
            f"<div class='v605-history-row'><span class='v605-history-season'>{esc(r.get('season'))}</span>"
            f"<span class='v605-history-points'>{esc(r.get('points'))} poeng</span><span class='v605-history-rank'>{esc(r.get('rank'))}</span></div>"
        )
    history_html = "<div class='v605-history-list'>" + "".join(hist) + "</div>" if hist else ""
    odds = (
        "<div class='v605-oddsgrid'>"
        f"<div class='v605-oddsitem'><strong>{esc(pre_win)}</strong><span>Vinner · før sesongstart</span></div>"
        f"<div class='v605-oddsitem'><strong>{esc(pre_top3)}</strong><span>Topp 3 · før sesongstart</span></div>"
        f"<div class='v605-oddsitem'><strong>{esc(live_win)}</strong><span>Vinner · akkurat nå</span></div>"
        + (f"<div class='v605-oddsitem'><strong>{esc(live_pct)}</strong><span>Vinnersjanse akkurat nå</span></div>" if live_pct else "")
        + "</div>"
    )
    note = f"<div class='v700-odds-note'>{esc(live_note)}</div>" if live_note else ""
    st.markdown(
        "<div class='v700-career'><div class='v700-career-head'><div class='v700-career-title'>Karriere & odds</div><div class='v700-live-badge'>Live</div></div>"
        f"<div class='v605-sidegrid'>{stat_html}</div>{history_html}{odds}{note}</div>",
        unsafe_allow_html=True,
    )

def stat_strip(items: list[tuple[Any, str]]) -> None:
    bits = [f"<div class='v500-stat'><div class='v500-stat-value'>{esc(value)}</div><div class='v500-stat-label'>{esc(label)}</div></div>" for value, label in items]
    if bits:
        st.markdown("<div class='v500-stats'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def rows(items: list[dict]) -> None:
    bits = []
    for item in items:
        rank = esc(item.get("rank", "")); who = esc(item.get("who", "")); num = esc(item.get("num", ""))
        rank_class = esc(item.get("rank_class", "")); num_class = esc(item.get("num_class", ""))
        href = str(item.get("href") or "").strip()
        who_html = f"<a href='{esc(href)}' class='v500-row-link'>{who}</a>" if href else who
        meta = esc(item.get("meta", ""))
        links = item.get("meta_links") or []
        if links:
            link_bits = []
            for link in links:
                label = esc(link.get("label", ""))
                url = esc(link.get("href", ""))
                link_bits.append(f"<a href='{url}'>{label}</a>" if url else label)
            prefix = esc(item.get("meta_prefix", ""))
            meta = (prefix + (" " if prefix else "") + ", ".join(link_bits)).strip()
            meta = f"<span class='v700-meta-links'>{meta}</span>"
        else:
            meta = esc(item.get("meta", ""))
        bits.append(
            f"<div class='v500-row'><div class='v500-rank {rank_class}'>{rank}</div>"
            f"<div class='v500-who'>{who_html}<span class='v500-meta'>{meta}</span></div>"
            f"<div class='v500-num {num_class}'>{num}</div></div>"
        )
    if bits:
        st.markdown("<div class='v500-list'>" + "".join(bits) + "</div>", unsafe_allow_html=True)

def squad_formation(starters: pd.DataFrame, bench: pd.DataFrame, price_formatter) -> None:
    """Compact tactical pitch with XI and bench in the same visual surface."""
    if starters is None or starters.empty:
        st.caption("Startelleveren kunne ikke lastes.")
        return
    data = starters.copy()
    if "position_id" not in data.columns:
        data["position_id"] = 0
    if "squad_position" in data.columns:
        data = data.sort_values("squad_position")
    groups = {pid: data[data["position_id"] == pid].to_dict("records") for pid in (1, 2, 3, 4)}
    if sum(len(v) for v in groups.values()) != len(data):
        label_map = {"Keeper": 1, "Forsvar": 2, "Midtbane": 3, "Angrep": 4}
        groups = {pid: [] for pid in (1, 2, 3, 4)}
        for row in data.to_dict("records"):
            groups[label_map.get(str(row.get("position") or ""), 0) or 3].append(row)
    formation = f"{len(groups[2])}-{len(groups[3])}-{len(groups[4])}"
    active_chip = str(data.iloc[0].get("active_chip") or "") if not data.empty else ""

    def player_card(row: dict) -> str:
        badge = ""
        if row.get("is_captain"):
            label = "TC" if row.get("is_triple_captain") else "C"
            cls = " tc" if label == "TC" else ""
            badge = f"<span class='v604-badge{cls}'>{esc(label)}</span>"
        elif row.get("is_vice_captain"):
            badge = "<span class='v604-badge vc'>VC</span>"
        status = str(row.get("status") or "a")
        status_html = "<span class='v700-status'>status</span>" if status not in {"a", ""} else ""
        price = price_formatter(row.get("current_price"))
        points = int(row.get("event_points") or 0)
        return (
            "<div class='v604-player'>" + badge +
            f"<div class='v604-player-name'>{esc(row.get('player') or '')}{status_html}</div>"
            f"<div class='v604-player-meta'>{esc(price)} · {points} poeng</div></div>"
        )

    lines = []
    for pid in (4, 3, 2, 1):
        cards = "".join(player_card(r) for r in groups.get(pid, []))
        if cards:
            lines.append(f"<div class='v604-line'>{cards}</div>")
    pitch_open = (
        "<div class='v604-squad-wrap'><div class='v604-pitch'><div class='v604-center-circle'></div>"
        f"<div class='v604-formation'>Formasjon {esc(formation)}</div>" + "".join(lines)
    )
    bench_html = ""
    if bench is not None and not bench.empty:
        b = bench.sort_values("squad_position") if "squad_position" in bench.columns else bench
        items = []
        for row in b.to_dict("records"):
            label = ""
            if row.get("is_vice_captain"):
                label = " · VC"
            elif row.get("is_captain"):
                label = " · TC" if row.get("is_triple_captain") else " · C"
            items.append(
                f"<div class='v604-bench-player'><div class='v604-bench-name'>{esc(row.get('player') or '')}</div>"
                f"<div class='v604-bench-meta'>{esc(price_formatter(row.get('current_price')))} · {int(row.get('event_points') or 0)} poeng{esc(label)}</div></div>"
            )
        bench_total = int(pd.to_numeric(b.get("event_points", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if "event_points" in b.columns else 0
        chip_text = " · Bench Boost" if active_chip == "Bench Boost" else ""
        bench_html = f"<div class='v604-bench-shell'><div class='v604-bench-label'>Benk · {bench_total} poeng{chip_text}</div><div class='v604-bench'>" + "".join(items) + "</div></div>"
    st.markdown(pitch_open + bench_html + "</div></div>", unsafe_allow_html=True)

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


def live_scoreboard(scores: list[str], event_label: str = "") -> None:
    if not scores:
        return
    fixture_bits = []
    for score in scores:
        # A trailing minute marker is visually separated when present.
        text = str(score or "")
        if " · " in text:
            main, status = text.rsplit(" · ", 1)
            fixture_bits.append(f"<div class='v701-fixture'>{esc(main)} <span>{esc(status)}</span></div>")
        else:
            fixture_bits.append(f"<div class='v701-fixture'>{esc(text)}</div>")
    st.markdown(
        "<div class='v701-livebar'><div class='v701-livebar-head'>"
        "<span class='v500-live-dot'></span><div class='v701-livebar-title'>Live</div>"
        + (f"<div class='v701-livebar-gw'>{esc(event_label)}</div>" if event_label else "")
        + "</div><div class='v701-fixtures'>" + "".join(fixture_bits) + "</div></div>",
        unsafe_allow_html=True,
    )


def live_label(text: str) -> None:
    st.markdown(f"<div class='v701-live-label'>{esc(text)}</div>", unsafe_allow_html=True)


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


def manager_profile_header(name: str, team: str, stats: list[tuple[Any, str]]) -> None:
    stat_html = "".join(
        f"<div class='v605-profile-stat'><strong>{esc(value)}</strong><span>{esc(label)}</span></div>"
        for value, label in stats[:4]
    )
    st.markdown(
        f"<div class='v605-profile'><div class='v605-profile-top'><div><div class='v605-profile-name'>{esc(name)}</div><div class='v605-profile-team'>{esc(team)}</div></div></div>"
        f"<div class='v605-profile-stats'>{stat_html}</div></div>",
        unsafe_allow_html=True,
    )


def honours_panel(items: list[tuple[Any, str]]) -> None:
    parts = []
    for value, label in items:
        try:
            numeric = int(value)
        except Exception:
            numeric = 0
        if numeric <= 0:
            continue
        parts.append(f"<span class='v700-merit'><strong>{numeric}×</strong>{esc(label)}</span>")
    if parts:
        st.markdown("<div class='v700-merits'>" + "".join(parts) + "</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='v700-merits'><span class='v700-merit-empty'>Ingen registrerte Lofthus-meritter ennå.</span></div>", unsafe_allow_html=True)

def career_panel(stats: list[tuple[Any, str]], seasons: list[dict]) -> None:
    stat_html = "".join(
        f"<div class='v605-side-stat'><strong>{esc(value)}</strong><span>{esc(label)}</span></div>" for value, label in stats[:4]
    )
    rows = []
    for r in seasons[:5]:
        rows.append(
            f"<div class='v605-history-row'><span class='v605-history-season'>{esc(r.get('season'))}</span>"
            f"<span class='v605-history-points'>{esc(r.get('points'))} poeng</span>"
            f"<span class='v605-history-rank'>{esc(r.get('rank'))}</span></div>"
        )
    history_html = "<div class='v605-history-list'>" + "".join(rows) + "</div>" if rows else ""
    st.markdown(
        "<div class='v605-sidebox'><div class='v605-sidebox-title'>FPL-karriere</div>"
        f"<div class='v605-sidegrid'>{stat_html}</div>{history_html}</div>",
        unsafe_allow_html=True,
    )


def manager_odds_panel(pre_win: str, pre_top3: str, live_win: str, live_pct: str = "") -> None:
    st.markdown(
        "<div class='v605-sidebox'><div class='v605-sidebox-title'>Odds</div><div class='v605-oddsgrid'>"
        f"<div class='v605-oddsitem'><strong>{esc(pre_win)}</strong><span>Vinner · før sesongstart</span></div>"
        f"<div class='v605-oddsitem'><strong>{esc(pre_top3)}</strong><span>Topp 3 · før sesongstart</span></div>"
        f"<div class='v605-oddsitem'><strong>{esc(live_win)}</strong><span>Vinner · akkurat nå</span></div>"
        + (f"<div class='v605-oddsitem'><strong>{esc(live_pct)}</strong><span>Modellens vinnersjanse</span></div>" if live_pct else "")
        + "</div></div>",
        unsafe_allow_html=True,
    )


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
.wrap{width:100%;overflow-x:auto;border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:transparent}table{border-collapse:collapse;width:100%;min-width:900px}th{text-align:left;color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.075em;font-weight:900;padding:12px 10px;border-bottom:1px solid var(--line);cursor:pointer;user-select:none;background:transparent}td{padding:13px 10px;border-bottom:1px solid var(--line);vertical-align:middle;font-size:13.5px}tbody tr:last-child td{border-bottom:0}tbody tr{cursor:pointer}tbody tr:hover td,tbody tr:focus td{background:rgba(184,137,32,.055)}tbody tr:focus{outline:2px solid rgba(184,137,32,.45);outline-offset:-2px}.right{text-align:right;white-space:nowrap}.manager{font-weight:900}.manager-link{text-decoration:underline;text-decoration-color:transparent;text-underline-offset:3px}.team{font-weight:700}.chip{display:block;color:var(--muted);font-size:11.5px;font-weight:700;margin-top:2px}.captain{font-weight:900;white-space:nowrap}.vice{display:block;color:var(--muted);font-size:10.5px;font-weight:700;margin-top:2px}.rank{font-weight:900;color:var(--muted)}.rank.gold{color:#977013}.rank.silver{color:#657080}.rank.bronze{color:#925f3a}.up{color:var(--green);font-weight:900}.down{color:var(--red);font-weight:900}.sort{margin-left:5px;color:var(--gold)}
@media(hover:hover) and (pointer:fine){tbody tr:hover .manager-link{text-decoration-color:var(--gold)}}
@media(max-width:760px){table{min-width:760px}th,td{padding:10px 7px}.vice{display:none}}
</style></head><body><div class="wrap"><table><thead><tr><th data-k="rank" data-type="n">#</th><th data-k="manager">Manager</th><th data-k="team">Lag</th><th data-k="captain">Kaptein</th><th class="right" data-k="gw" data-type="n">GW</th><th class="right" data-k="points" data-type="n">Poeng</th><th class="right" data-k="move" data-type="n">+/-</th></tr></thead><tbody id="body"></tbody></table></div><script>
const rows=__ROWS__; let key='rank', dir=1; const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
function cmp(a,b){let av=a[key],bv=b[key];if(typeof av==='number'||typeof bv==='number'){av=(av===null||av===undefined)?1e15:Number(av);bv=(bv===null||bv===undefined)?1e15:Number(bv);return(av-bv)*dir}return String(av||'').localeCompare(String(bv||''),'nb')*dir}
function openManager(entry){if(!entry)return;const url=new URL(window.parent.location.href);url.searchParams.set('page','Ligaen');url.searchParams.set('manager',entry);url.searchParams.delete('league_view');window.parent.location.href=url.toString()}
function render(){const body=document.getElementById('body');body.innerHTML='';[...rows].sort(cmp).forEach(r=>{const tr=document.createElement('tr');tr.tabIndex=0;tr.dataset.entry=String(r.entry||'');tr.setAttribute('role','link');tr.setAttribute('aria-label','Åpne laget til '+String(r.manager||''));const rc=r.rank===1?'gold':r.rank===2?'silver':r.rank===3?'bronze':'';const mv=Number(r.move||0);const move=mv>0?'↑'+mv:mv<0?'↓'+Math.abs(mv):'–';const mc=mv>0?'up':mv<0?'down':'';const vice=r.vice?`<span class="vice">VC: ${esc(r.vice)}</span>`:'';tr.innerHTML=`<td><span class="rank ${rc}">${esc(r.rank??'')}</span></td><td class="manager"><span class="manager-link">${esc(r.manager)}</span></td><td><span class="team">${esc(r.team)}</span>${r.chip?`<span class="chip">${esc(r.chip)}</span>`:''}</td><td><span class="captain">${esc(r.captain||'–')}</span>${vice}</td><td class="right">${esc(r.gw)}</td><td class="right"><strong>${esc(r.points)}</strong></td><td class="right ${mc}">${move}</td>`;body.appendChild(tr)});document.querySelectorAll('th').forEach(th=>{th.querySelectorAll('.sort').forEach(x=>x.remove());if(th.dataset.k===key){const x=document.createElement('span');x.className='sort';x.textContent=dir===1?'▲':'▼';th.appendChild(x)}})}
document.querySelectorAll('th').forEach(th=>th.onclick=()=>{const k=th.dataset.k;if(key===k)dir*=-1;else{key=k;dir=(k==='manager'||k==='team'||k==='captain')?1:(k==='move'?-1:1)}render()});const body=document.getElementById('body');body.addEventListener('click',e=>{const tr=e.target.closest('tr[data-entry]');if(tr)openManager(tr.dataset.entry)});body.addEventListener('keydown',e=>{if(e.key!=='Enter'&&e.key!==' ')return;const tr=e.target.closest('tr[data-entry]');if(!tr)return;e.preventDefault();openManager(tr.dataset.entry)});render();
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
.board{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(260px,.7fr);gap:22px}.list,.detail{border-top:1px solid var(--line);border-bottom:1px solid var(--line);background:transparent;overflow:hidden}.list{max-height:520px;overflow-y:auto}.row{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:9px;align-items:center;padding:12px 13px;border-bottom:1px solid var(--line);cursor:pointer}.row:last-child{border-bottom:0}.row:hover,.row.active{background:rgba(184,137,32,.07)}.rank{font-size:11px;color:var(--muted);font-weight:900}.name{font-weight:900;font-size:14px}.meta{display:block;color:var(--muted);font-size:11.5px;font-weight:650;margin-top:2px}.count{font-weight:900;font-size:13px;white-space:nowrap}.detail{padding:16px 2px;min-height:250px;position:sticky;top:0;max-height:520px;overflow-y:auto}.eyebrow{text-transform:uppercase;letter-spacing:.085em;color:var(--gold);font-size:10px;font-weight:950}.dname{font-weight:950;font-size:25px;letter-spacing:-.045em;margin:5px 0 2px}.dmeta{font-size:12px;color:var(--muted);font-weight:650}.group{margin-top:17px;border-top:1px solid var(--line);padding-top:10px}.label{font-size:10px;text-transform:uppercase;letter-spacing:.07em;font-weight:900;color:var(--muted);margin-bottom:6px}.person{font-size:12.5px;font-weight:750;padding:5px 0}.tc{color:var(--red)}
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
    """One continuous Hall of Fame list; top three are accented in place."""
    if not rows_data:
        st.caption("Ingen historikk funnet.")
        return
    bits = []
    for i, row in enumerate(rows_data, start=1):
        cls = "top1" if i == 1 else "top2" if i == 2 else "top3" if i == 3 else ""
        bits.append(
            f"<div class='v500-hof-row {cls}'><div class='v500-hof-place'>{i:02d}</div>"
            f"<div><div class='v500-hof-name'>{esc(row.get('who'))}</div>"
            f"<div class='v500-hof-meta'>{esc(row.get('meta'))}</div></div></div>"
        )
    st.markdown("<div class='v500-hof-list'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


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
