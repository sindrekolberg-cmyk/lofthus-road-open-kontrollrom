from __future__ import annotations

import html
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from lro_analysis import nfloat, nint
from lro_live import LiveState, ManagerLiveState, PlayerImpact
from lro_routes import compare_href, href, league_href, manager_href, player_href, rival_href


CSS = r"""
<style>
:root{
  --bg:#f3f0e8;--paper:#fffdf8;--paper2:#f8f5ee;--ink:#091522;--muted:#6b7480;--line:#d9d5cc;
  --navy:#071829;--navy2:#0f2841;--gold:#c79a35;--gold2:#e7c56f;--green:#087b54;--red:#bd3b38;
  --blue:#0a5da8;--soft:#ece8de;--radius:16px;--shadow:0 20px 55px rgba(8,20,34,.11);
  --font:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
*{box-sizing:border-box}html,body,[data-testid="stAppViewContainer"]{background:var(--bg);color:var(--ink);font-family:var(--font)}
[data-testid="stHeader"]{background:transparent;height:0}.block-container{max-width:1380px;padding:.75rem 1.1rem 3.2rem!important}
[data-testid="stSidebar"],#MainMenu,footer{display:none!important}.element-container{min-width:0}a{color:inherit}

/* product shell */
.v8-shell{background:var(--navy);color:#fff;border-radius:20px;padding:1rem 1.25rem .76rem;margin-bottom:.65rem;box-shadow:var(--shadow);overflow:hidden;position:relative}
.v8-shell:after{content:"";position:absolute;width:300px;height:300px;border-radius:50%;right:-120px;top:-170px;background:radial-gradient(circle,rgba(199,154,53,.20),rgba(199,154,53,0) 68%);pointer-events:none}
.v8-shell-top{display:flex;justify-content:space-between;gap:1rem;align-items:flex-end;position:relative;z-index:1}.v8-brand{font-size:clamp(1.8rem,3.2vw,2.8rem);font-weight:950;letter-spacing:-.055em;line-height:.95}.v8-season{font-size:.62rem;color:#aebbd0;font-weight:900;letter-spacing:.12em;text-transform:uppercase;margin-top:.34rem}
.v8-live-status{font-size:.67rem;color:#d9e0e9;font-weight:800;text-align:right}.v8-live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#f05b58;margin-right:.38rem;vertical-align:1px;box-shadow:0 0 0 4px rgba(240,91,88,.10)}
.v8-shell-nav{display:flex;gap:.18rem;flex-wrap:wrap;margin-top:.72rem;padding-top:.58rem;border-top:1px solid rgba(255,255,255,.11);position:relative;z-index:1}.v8-shell-nav a{color:#bfc9d7!important;text-decoration:none!important;font-size:.74rem;font-weight:850;padding:.36rem .56rem;border-radius:8px}.v8-shell-nav a:hover,.v8-shell-nav a.active{background:rgba(255,255,255,.10);color:#fff!important}

/* native controls, made quieter */
.stButton>button,.stDownloadButton>button{border-radius:10px!important;box-shadow:none!important;font-weight:850!important;border-color:var(--line)!important}
.stSelectbox label,.stMultiSelect label{font-size:.68rem!important;font-weight:850!important;color:var(--muted)!important}.stSelectbox,.stMultiSelect{margin-bottom:.15rem}
div[data-testid="stExpander"]{border:1px solid var(--line)!important;border-radius:14px!important;background:rgba(255,255,255,.34)!important;overflow:hidden}
div[data-testid="stPopover"] button{border-radius:999px!important;border:1px solid #d7d2c8!important;background:rgba(255,255,255,.72)!important;color:var(--ink)!important;font-weight:850!important;padding:.38rem .72rem!important;min-height:38px!important;box-shadow:none!important}
div[data-baseweb="tab-list"]{gap:.15rem;border-bottom:1px solid var(--line)}button[data-baseweb="tab"]{font-size:.7rem!important;font-weight:850!important;color:var(--muted)!important;padding:.42rem .58rem!important}button[data-baseweb="tab"][aria-selected="true"]{color:var(--ink)!important}div[data-baseweb="tab-highlight"]{background:var(--gold)!important}

/* headers + navigation */
.v8-page{display:flex;justify-content:space-between;gap:1rem;align-items:flex-end;margin:.9rem 0 .72rem}.v8-page h1{font-size:clamp(2rem,3.8vw,3.35rem);line-height:.92;letter-spacing:-.06em;margin:0;font-weight:950}.v8-kicker{font-size:.61rem;color:var(--gold);text-transform:uppercase;letter-spacing:.12em;font-weight:950;margin-bottom:.28rem}.v8-page-meta{font-size:.72rem;color:var(--muted);font-weight:760;text-align:right}
.v8-subnav{display:flex;gap:.18rem;flex-wrap:wrap;margin:.05rem 0 .95rem}.v8-subnav a{font-size:.7rem;font-weight:850;color:var(--muted)!important;text-decoration:none!important;padding:.38rem .58rem;border-radius:999px;border:1px solid transparent}.v8-subnav a:hover,.v8-subnav a.active{background:var(--paper);border-color:var(--line);color:var(--ink)!important}
.v8-section{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin:1.55rem 0 .58rem}.v8-section strong{font-size:1.18rem;letter-spacing:-.035em}.v8-section span{font-size:.68rem;color:var(--muted);font-weight:760}.v8-muted{color:var(--muted);font-size:.73rem;font-weight:700}.v8-empty{background:rgba(255,255,255,.42);border:1px solid var(--line);border-radius:14px;padding:.85rem 1rem;color:var(--muted);font-size:.76rem}

/* compact scoreboard strip */
.v8-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:rgba(255,255,255,.42);border:1px solid var(--line);border-radius:14px;margin:.35rem 0 .8rem;overflow:hidden}.v8-strip-item{padding:.62rem .78rem .58rem;min-width:0}.v8-strip-item+.v8-strip-item{border-left:1px solid var(--line)}.v8-strip-label{font-size:.55rem;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);font-weight:950}.v8-strip-value{font-size:.98rem;font-weight:950;letter-spacing:-.025em;margin-top:.13rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v8-strip-sub{font-size:.62rem;color:var(--muted);margin-top:.09rem;font-weight:720}

/* manager menu */
details.v8-manager{position:relative;display:inline-block;max-width:100%}details.v8-manager>summary{list-style:none;cursor:pointer;font-weight:900;color:inherit;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}details.v8-manager>summary::-webkit-details-marker{display:none}details.v8-manager>summary:hover{color:var(--blue);text-decoration:underline;text-underline-offset:3px}details.v8-manager[open]>summary{color:var(--blue)}
.v8-menu{position:absolute;z-index:80;left:0;top:calc(100% + 7px);min-width:188px;background:#fff;border:1px solid #ced3d8;border-radius:12px;box-shadow:0 18px 40px rgba(8,17,31,.18);padding:.34rem}.v8-menu a{display:block;text-decoration:none!important;padding:.46rem .54rem;border-radius:8px;font-size:.7rem;font-weight:830;color:var(--ink)!important}.v8-menu a:hover{background:#eef2f5}

/* front page matchday: sports site first */
.v81-frontgrid{display:grid;grid-template-columns:minmax(0,1.72fr) minmax(320px,.78fr);gap:.85rem;align-items:stretch;margin:.35rem 0 1rem}
.v81-hero{position:relative;min-height:350px;border-radius:20px;overflow:hidden;background:linear-gradient(112deg,#071829 0%,#0b2340 56%,#173b5a 100%);color:#fff;box-shadow:var(--shadow);isolation:isolate}
.v81-hero:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 76% 20%,rgba(231,197,111,.18),transparent 28%),linear-gradient(90deg,rgba(7,24,41,.98) 0%,rgba(7,24,41,.94) 47%,rgba(7,24,41,.28) 78%,rgba(7,24,41,.12) 100%);z-index:1}
.v81-hero-body{position:relative;z-index:3;padding:1.15rem 1.25rem 1rem;max-width:68%}.v81-hero-kicker{display:flex;gap:.6rem;align-items:center;font-size:.61rem;font-weight:950;letter-spacing:.12em;text-transform:uppercase;color:#f6b9b6}.v81-hero-score{color:#c5d0de;font-weight:800;letter-spacing:.03em}.v81-hero-name{font-size:clamp(2.7rem,6vw,5.2rem);font-weight:950;letter-spacing:-.075em;line-height:.82;margin:.72rem 0 .46rem}.v81-hero-name a{color:#fff!important;text-decoration:none!important}.v81-hero-deck{font-size:.78rem;color:#d5deea;font-weight:760;line-height:1.45}.v81-hero-statline{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.65rem}.v81-hero-stat{background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.10);border-radius:999px;padding:.28rem .52rem;font-size:.63rem;font-weight:860;color:#eef3f8}
.v81-hero-playerimg{position:absolute;z-index:2;right:-1%;bottom:-4%;height:94%;width:46%;object-fit:contain;object-position:right bottom;filter:drop-shadow(-14px 18px 28px rgba(0,0,0,.24))}.v81-hero-noimg{position:absolute;z-index:0;right:1.2rem;bottom:-2rem;font-size:13rem;font-weight:950;color:rgba(255,255,255,.035);letter-spacing:-.12em}
.v81-impactbox{position:absolute;z-index:4;left:1.25rem;right:1.25rem;bottom:1rem;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.34rem}.v81-impact{background:rgba(4,14,26,.66);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.11);border-radius:10px;padding:.45rem .5rem;min-width:0}.v81-impact-name{font-size:.62rem;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v81-impact-name a{color:#fff!important;text-decoration:none!important}.v81-impact-value{font-size:.85rem;font-weight:950;color:#6fe0ad;margin-top:.08rem}.v81-impact.neg .v81-impact-value{color:#ff9994}

.v81-toprail{background:var(--paper);border:1px solid var(--line);border-radius:20px;box-shadow:0 12px 34px rgba(8,20,34,.065);padding:.85rem .9rem .7rem;overflow:visible}.v81-railhead{display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding-bottom:.55rem;border-bottom:1px solid var(--line)}.v81-railtitle{font-size:.72rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.v81-raillive{font-size:.55rem;color:var(--red);font-weight:950;text-transform:uppercase;letter-spacing:.08em}.v81-rail-leader{padding:.75rem 0 .65rem}.v81-rail-rank{font-size:.55rem;color:var(--gold);font-weight:950;text-transform:uppercase;letter-spacing:.11em}.v81-rail-name details.v8-manager>summary{font-size:1.22rem;letter-spacing:-.035em}.v81-rail-team{font-size:.62rem;color:var(--muted);font-weight:720;margin-top:.08rem}.v81-rail-score{display:flex;justify-content:space-between;gap:.8rem;align-items:flex-end;margin-top:.42rem}.v81-rail-score strong{font-size:1.55rem;letter-spacing:-.05em}.v81-rail-score span{font-size:.61rem;color:var(--muted);font-weight:850}.v81-rail-row{display:grid;grid-template-columns:26px minmax(0,1fr) auto;gap:.45rem;align-items:center;padding:.48rem 0;border-top:1px solid var(--line)}.v81-rail-pos{font-size:.7rem;color:var(--muted);font-weight:950}.v81-rail-row details.v8-manager>summary{font-size:.76rem}.v81-rail-meta{font-size:.57rem;color:var(--muted);font-weight:720;margin-top:.05rem}.v81-rail-total{font-size:.82rem;font-weight:950;text-align:right}.v81-move{font-size:.57rem;font-weight:900;margin-left:.2rem}.v81-up{color:var(--green)}.v81-down{color:var(--red)}

/* non-live top five */
.v8-top5{display:grid;grid-template-columns:1.15fr .85fr .85fr;gap:.55rem;margin:.15rem 0 1rem}.v8-top-lead,.v8-top-row{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:.75rem .8rem;min-width:0}.v8-top-lead{grid-row:span 2}.v8-top-rank{font-size:.61rem;color:var(--gold);font-weight:950;text-transform:uppercase;letter-spacing:.1em}.v8-top-name details.v8-manager>summary{font-size:1.08rem;letter-spacing:-.03em;margin-top:.28rem}.v8-top-lead .v8-top-name details.v8-manager>summary{font-size:1.55rem}.v8-top-meta{font-size:.62rem;color:var(--muted);font-weight:720;margin-top:.14rem}.v8-top-points{font-size:1.55rem;font-weight:950;letter-spacing:-.05em;margin-top:.7rem}.v8-top-points small{font-size:.6rem;color:var(--muted);letter-spacing:0;margin-left:.3rem}.v8-top-row .v8-top-points{font-size:1.05rem;margin-top:.36rem}

/* visual newsroom */
.v81-newsgrid{display:grid;grid-template-columns:1.35fr 1fr 1fr;grid-auto-rows:minmax(148px,auto);gap:.65rem}.v81-story{position:relative;background:var(--paper);border:1px solid var(--line);border-radius:16px;overflow:hidden;min-height:148px;padding:.82rem .9rem;display:flex;flex-direction:column;justify-content:flex-end}.v81-story:first-child{grid-row:span 2;min-height:310px;background:var(--navy);color:#fff;padding:1rem 1.05rem}.v81-story:first-child:before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(7,24,41,.03),rgba(7,24,41,.92) 72%);z-index:1}.v81-story-img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:85% 5%;background:linear-gradient(135deg,#102a43,#1f4b6c);filter:saturate(.96)}.v81-story:not(:first-child) .v81-story-img{left:auto;right:-7%;top:7%;bottom:auto;width:52%;height:94%;object-fit:contain;object-position:right bottom;background:transparent;opacity:.92;filter:drop-shadow(-6px 10px 12px rgba(0,0,0,.10))}.v81-story:not(:first-child) .v81-story-content{max-width:68%}.v81-story-content{position:relative;z-index:2}.v81-story-kicker{font-size:.55rem;text-transform:uppercase;letter-spacing:.1em;font-weight:950;color:var(--gold)}.v81-story:first-child .v81-story-kicker{color:#f1d791}.v81-story-head{font-size:.95rem;font-weight:920;line-height:1.08;letter-spacing:-.025em;margin-top:.26rem}.v81-story:first-child .v81-story-head{font-size:clamp(1.45rem,2.6vw,2.2rem);max-width:85%}.v81-story-head a{text-decoration:none!important;color:inherit!important}.v81-story-meta{font-size:.64rem;color:var(--muted);font-weight:710;line-height:1.35;margin-top:.28rem}.v81-story:first-child .v81-story-meta{color:#c8d2df;max-width:80%}.v81-story-number{position:absolute;right:.7rem;top:.4rem;font-size:3rem;font-weight:950;color:rgba(9,21,34,.035);letter-spacing:-.08em}.v81-story:first-child .v81-story-number{color:rgba(255,255,255,.055);font-size:6rem}

/* visual player cards */
.v81-playercards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.55rem}.v81-playercard{position:relative;min-height:128px;background:var(--paper);border:1px solid var(--line);border-radius:16px;overflow:hidden;padding:.72rem .75rem;display:flex;align-items:flex-end}.v81-playercard img{position:absolute;right:-7px;bottom:-6px;height:118px;width:105px;object-fit:contain;filter:drop-shadow(-7px 10px 12px rgba(0,0,0,.12));opacity:.98}.v81-playercard-copy{position:relative;z-index:2;max-width:68%}.v81-playercard-name{font-size:.95rem;font-weight:950;letter-spacing:-.03em}.v81-playercard-name a{text-decoration:none!important}.v81-playercard-club{font-size:.55rem;color:var(--muted);font-weight:850;text-transform:uppercase;letter-spacing:.08em;margin-top:.05rem}.v81-playercard-stat{font-size:1.15rem;font-weight:950;margin-top:.38rem}.v81-playercard-meta{font-size:.58rem;color:var(--muted);font-weight:720;margin-top:.05rem}

/* league table */
.v8-league{background:var(--paper);border:1px solid var(--line);border-radius:16px;overflow:visible}.v8-league-head,.v8-league-row{display:grid;grid-template-columns:44px minmax(210px,1.7fr) minmax(150px,1.25fr) minmax(115px,.9fr) 64px 82px 64px;gap:.6rem;align-items:center}.v8-league-head{font-size:.56rem;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:950;padding:.55rem .72rem;border-bottom:1px solid var(--line)}.v8-league-row{padding:.58rem .72rem;border-bottom:1px solid var(--line);font-size:.74rem;min-height:52px}.v8-league-row:last-child{border-bottom:0}.v8-league-row:hover{background:#f8f7f2}.v8-rank{color:var(--muted);font-weight:950}.v8-team{font-weight:730;color:#3f4854}.v8-cap{font-weight:860}.v8-num{text-align:right;font-weight:950;font-variant-numeric:tabular-nums}.v8-manager-sub{display:none;color:var(--muted);font-size:.61rem;font-weight:700;margin-top:.08rem}.v8-chip{display:inline-block;margin-left:.28rem;color:var(--red);font-size:.54rem;font-weight:950;text-transform:uppercase;letter-spacing:.05em}

/* manager profile */
.v8-profile{background:var(--paper);border:1px solid var(--line);border-radius:18px;padding:.92rem 1rem .84rem;margin:.28rem 0 .72rem;box-shadow:0 10px 28px rgba(8,20,34,.04)}.v8-profile-grid{display:grid;grid-template-columns:minmax(0,1.45fr) repeat(3,minmax(92px,.45fr));gap:1rem;align-items:end}.v8-profile-name{font-size:clamp(1.9rem,3.7vw,3.1rem);font-weight:950;letter-spacing:-.06em;line-height:.92}.v8-profile-team{font-size:.72rem;color:var(--muted);font-weight:760;margin-top:.3rem}.v8-profile-stat strong{font-size:1.38rem;font-weight:950;display:block;letter-spacing:-.04em}.v8-profile-stat span{font-size:.55rem;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.08em}.v8-profile-story{font-size:.78rem;font-weight:800;background:#eceff1;border-left:3px solid var(--navy2);border-radius:0 10px 10px 0;padding:.52rem .7rem;margin:.15rem 0 .72rem}

/* pitch with player faces */
.v8-pitch{position:relative;overflow:hidden;background:linear-gradient(180deg,#1b704a,#0d5939);border-radius:18px;padding:1rem .7rem .72rem;color:#fff;box-shadow:inset 0 0 0 1px rgba(255,255,255,.13),0 14px 34px rgba(9,45,30,.12)}.v8-pitch:before{content:"";position:absolute;inset:7% 4%;border:1px solid rgba(255,255,255,.22);border-radius:5px;pointer-events:none}.v8-pitch:after{content:"";position:absolute;left:50%;top:7%;bottom:21%;border-left:1px solid rgba(255,255,255,.18);pointer-events:none}.v8-line{position:relative;z-index:2;display:flex;justify-content:space-evenly;gap:.36rem;min-height:116px;align-items:flex-end}.v8-player{width:min(150px,22%);min-width:88px;background:rgba(255,253,248,.97);color:var(--ink);border-radius:12px;padding:.26rem .32rem .42rem;text-align:center;box-shadow:0 9px 20px rgba(0,0,0,.16);overflow:hidden}.v8-player-img{height:54px;width:66px;object-fit:contain;display:block;margin:-.14rem auto -.05rem}.v8-player-name{font-size:.68rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v8-player-meta{font-size:.54rem;color:var(--muted);font-weight:760;margin-top:.11rem}.v8-player.live{box-shadow:0 0 0 2px #f2cf74,0 9px 20px rgba(0,0,0,.16)}.v8-player.finished{opacity:.88}.v8-badge{display:inline-block;background:var(--navy);color:#fff;border-radius:99px;padding:.06rem .26rem;font-size:.48rem;font-weight:950;margin-left:.1rem}.v8-badge.tc{background:var(--red)}.v8-badge.vc{background:#6b7280}.v8-bench{margin-top:.65rem;border-top:1px solid rgba(255,255,255,.28);padding-top:.5rem;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.34rem;position:relative;z-index:2}.v8-bench .v8-player{width:auto;min-width:0}.v8-bench .v8-player-img{height:42px}

/* player profile hero */
.v81-playerhero{position:relative;min-height:285px;border-radius:20px;background:linear-gradient(120deg,#071829,#153b5e);color:#fff;overflow:hidden;margin:.35rem 0 .9rem;box-shadow:var(--shadow)}.v81-playerhero:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(7,24,41,.98),rgba(7,24,41,.76) 55%,rgba(7,24,41,.12));z-index:1}.v81-playerhero-copy{position:relative;z-index:3;padding:1.15rem 1.2rem;max-width:65%}.v81-playerhero-club{font-size:.6rem;color:#e6c979;text-transform:uppercase;letter-spacing:.12em;font-weight:950}.v81-playerhero-name{font-size:clamp(2.5rem,5vw,4.5rem);font-weight:950;letter-spacing:-.07em;line-height:.86;margin:.55rem 0 .8rem}.v81-playerhero-stats{display:flex;gap:1.1rem;flex-wrap:wrap}.v81-playerhero-stat strong{display:block;font-size:1.4rem;letter-spacing:-.04em}.v81-playerhero-stat span{font-size:.55rem;text-transform:uppercase;letter-spacing:.08em;color:#bfcadb;font-weight:900}.v81-playerhero img{position:absolute;z-index:2;right:2%;bottom:-5%;height:100%;width:42%;object-fit:contain;filter:drop-shadow(-12px 18px 22px rgba(0,0,0,.25))}

/* form, stats, rivalry, generic tables */
.v8-form{display:flex;gap:.45rem;overflow-x:auto}.v8-form-item{min-width:112px;background:var(--paper);border:1px solid var(--line);border-radius:13px;padding:.56rem .62rem}.v8-form-gw{font-size:.55rem;color:var(--muted);font-weight:950;text-transform:uppercase;letter-spacing:.07em}.v8-form-points{font-size:1.18rem;font-weight:950;margin:.08rem 0}.v8-form-rank{font-size:.58rem;color:var(--muted);font-weight:730}.v8-mini-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.48rem}.v8-mini{background:var(--paper);border:1px solid var(--line);border-radius:13px;padding:.56rem .65rem}.v8-mini strong{display:block;font-size:1.05rem;font-weight:950;letter-spacing:-.025em}.v8-mini span{font-size:.58rem;color:var(--muted);font-weight:780}
.v8-duel{background:var(--paper);border:1px solid var(--line);border-radius:17px;display:grid;grid-template-columns:1fr auto 1fr;gap:1rem;align-items:end;padding:.82rem .9rem}.v8-duel-side:last-child{text-align:right}.v8-duel-name{font-size:1.2rem;font-weight:950;letter-spacing:-.04em}.v8-duel-points{font-size:1.85rem;font-weight:950;letter-spacing:-.06em}.v8-duel-meta{font-size:.63rem;color:var(--muted);font-weight:730}.v8-vs{font-size:.57rem;color:var(--muted);font-weight:950;text-transform:uppercase;letter-spacing:.1em;padding-bottom:.45rem}.v8-cheer{display:grid;grid-template-columns:1fr 1fr;gap:.65rem}.v8-cheer-col{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:.55rem .65rem}.v8-cheer-title{font-size:.58rem;text-transform:uppercase;letter-spacing:.1em;font-weight:950;padding:.15rem 0 .35rem}.v8-edge{display:flex;justify-content:space-between;gap:.6rem;border-top:1px solid var(--line);padding:.4rem 0;font-size:.72rem}.v8-edge strong{font-weight:900}.v8-edge span{font-weight:950;color:var(--green)}.v8-cheer-col.bad .v8-edge span{color:var(--red)}
.v8-table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--paper)}.v8-table{width:100%;border-collapse:collapse;font-size:.72rem}.v8-table th{text-align:left;color:var(--muted);font-size:.54rem;text-transform:uppercase;letter-spacing:.08em;padding:.48rem .52rem;border-bottom:1px solid var(--line)}.v8-table td{padding:.5rem .52rem;border-bottom:1px solid var(--line);font-weight:710}.v8-table tr:last-child td{border-bottom:0}.v8-table td.num,.v8-table th.num{text-align:right;font-weight:900}.v8-hof-name{font-weight:950}.v8-medal{font-weight:950;color:var(--gold)}

@media(max-width:980px){
  .v81-frontgrid{grid-template-columns:1fr}.v81-toprail{padding:.75rem .85rem}.v81-rail-leader{display:grid;grid-template-columns:1fr auto;gap:.5rem}.v81-rail-score{grid-column:2;grid-row:1/3;align-self:center}.v81-newsgrid{grid-template-columns:1.2fr 1fr}.v81-story:first-child{grid-row:span 2}.v81-story:nth-child(4){grid-column:1/-1}.v8-profile-grid{grid-template-columns:minmax(0,1.4fr) repeat(3,minmax(78px,.45fr))}
}
@media(max-width:760px){
  .block-container{padding:.55rem .55rem 2.5rem!important}.v8-shell{border-radius:15px;padding:.82rem .78rem .65rem}.v8-shell-top{align-items:flex-start}.v8-live-status{display:none}.v8-shell-nav{gap:.04rem}.v8-shell-nav a{font-size:.68rem;padding:.34rem .42rem}.v8-page{align-items:flex-start}.v8-page-meta{display:none}
  .v8-strip{grid-template-columns:repeat(3,minmax(0,1fr));border-radius:12px}.v8-strip-item{padding:.5rem .48rem}.v8-strip-item+.v8-strip-item{border-left:1px solid var(--line)}.v8-strip-value{font-size:.8rem}.v8-strip-sub{font-size:.54rem}.v8-strip-label{font-size:.48rem}
  .v81-hero{min-height:410px}.v81-hero-body{max-width:100%;padding:.9rem .85rem}.v81-hero-name{font-size:3.15rem;max-width:72%}.v81-hero-playerimg{height:64%;width:58%;right:-7%;bottom:12%}.v81-impactbox{left:.75rem;right:.75rem;bottom:.72rem;grid-template-columns:repeat(2,minmax(0,1fr))}.v81-impact:nth-child(n+5){display:none}.v81-impact{padding:.38rem .42rem}.v81-hero-deck{max-width:70%}
  .v81-newsgrid{grid-template-columns:1fr;grid-auto-rows:auto}.v81-story:first-child{grid-row:auto;min-height:260px}.v81-story:first-child .v81-story-head{max-width:90%}.v81-story:nth-child(4){grid-column:auto}
  .v81-playercards{grid-template-columns:1fr}.v81-playercard{min-height:112px}.v81-playercard img{height:105px}
  .v8-top5{grid-template-columns:1fr 1fr}.v8-top-lead{grid-column:1/-1;grid-row:auto}.v8-top-row:last-child{grid-column:1/-1}
  .v8-league-head{display:none}.v8-league-row{grid-template-columns:34px minmax(0,1fr) auto;gap:.42rem;padding:.56rem .58rem}.v8-league-row>.v8-team,.v8-league-row>.v8-cap,.v8-league-row>.v8-gw,.v8-league-row>.v8-move-cell{display:none}.v8-league-row>.v8-total{grid-column:3}.v8-manager-sub{display:block}.v8-league-row details.v8-manager>summary{font-size:.8rem}.v8-menu{position:fixed;left:.75rem;right:.75rem;top:auto;bottom:.75rem;min-width:0;max-width:none}
  .v8-profile-grid{grid-template-columns:1fr 1fr}.v8-profile-main{grid-column:1/-1}.v8-profile-stat:nth-child(4){display:none}.v8-pitch{padding:.65rem .18rem}.v8-line{gap:.12rem;min-height:104px}.v8-player{min-width:0;width:24%;padding:.2rem .12rem .32rem}.v8-player-img{height:45px;width:55px}.v8-player-name{font-size:.58rem}.v8-player-meta{font-size:.47rem}.v8-bench{grid-template-columns:repeat(2,minmax(0,1fr))}.v8-duel{grid-template-columns:1fr 30px 1fr;gap:.4rem}.v8-duel-name{font-size:.9rem}.v8-duel-points{font-size:1.3rem}.v8-cheer{grid-template-columns:1fr}.v8-mini-grid{grid-template-columns:1fr 1fr}.v8-mini:last-child:nth-child(odd){grid-column:1/-1}
  .v81-playerhero{min-height:320px}.v81-playerhero-copy{max-width:76%;padding:.9rem}.v81-playerhero-name{font-size:2.8rem}.v81-playerhero img{width:52%;height:72%;right:-7%}.v81-playerhero-stats{gap:.65rem}.v81-playerhero-stat strong{font-size:1.05rem}
  .v8-table{min-width:540px}.v8-table-wrap{overflow-x:auto}
}
@media(max-width:420px){
  .v8-strip{grid-template-columns:1fr}.v8-strip-item+.v8-strip-item{border-left:0;border-top:1px solid var(--line)}.v81-hero-name{font-size:2.7rem}.v81-hero-playerimg{opacity:.83}.v81-hero-deck{max-width:85%}.v81-impactbox{grid-template-columns:1fr 1fr}.v8-top5{grid-template-columns:1fr}.v8-top-row:last-child{grid-column:auto}.v8-mini-grid{grid-template-columns:1fr}.v8-mini:last-child:nth-child(odd){grid-column:auto}
}
</style>
"""


CSS_V820 = r"""
<style>
/* V820 SPORTSFRONT
   The homepage is intentionally treated as an editorial sports front, not a
   dashboard. Secondary analysis still uses the compact V8 primitives below. */
:root{
  --v820-bg:#f4f1e9;--v820-ink:#0a1724;--v820-navy:#061a2c;--v820-navy2:#0b2d4a;
  --v820-paper:#fffdf8;--v820-line:#d9d4ca;--v820-muted:#727d89;--v820-gold:#b98e31;
  --v820-green:#07855b;--v820-red:#c74440;--v820-soft:#ece7dc;
}
html,body,[data-testid="stAppViewContainer"]{background:var(--v820-bg)!important}
.block-container{max-width:1420px!important;padding:.72rem 1.25rem 3.4rem!important}

/* tighter masthead: identity without eating the first screen */
.v8-shell{border-radius:17px!important;padding:.92rem 1.15rem .68rem!important;margin-bottom:.55rem!important;box-shadow:0 13px 34px rgba(6,20,34,.10)!important;background:var(--v820-navy)!important}
.v8-brand{font-size:clamp(1.75rem,3vw,2.55rem)!important;letter-spacing:-.06em!important}
.v8-season{font-size:.56rem!important;margin-top:.3rem!important}.v8-shell-nav{margin-top:.62rem!important;padding-top:.52rem!important}
.v8-shell-nav a{font-size:.69rem!important;padding:.32rem .5rem!important}

/* small editorial ticker replaces three dashboard cards */
.v820-ticker{display:flex;align-items:center;justify-content:flex-end;gap:.78rem;min-height:32px;margin:.08rem 0 .54rem;font-size:.66rem;color:var(--v820-muted);font-weight:720;white-space:nowrap;overflow:hidden}
.v820-ticker-item{min-width:0;overflow:hidden;text-overflow:ellipsis}.v820-ticker-label{font-size:.48rem;text-transform:uppercase;letter-spacing:.11em;font-weight:950;color:#89929b;margin-right:.28rem}.v820-ticker b{color:var(--v820-ink);font-weight:950}.v820-ticker-sep{color:#c3bdb2}

/* true sports front: image-led lead story + standings rail */
.v820-front{display:grid;grid-template-columns:minmax(0,1.78fr) minmax(330px,.72fr);gap:1rem;align-items:stretch;margin:.28rem 0 1.1rem}
.v820-hero{position:relative;height:455px;overflow:hidden;border-radius:20px;background:linear-gradient(128deg,var(--v820-navy) 0%,#0b2d4b 58%,#1c5474 100%);color:#fff;isolation:isolate;box-shadow:0 20px 48px rgba(6,20,34,.14)}
.v820-hero:before{content:"";position:absolute;inset:0;z-index:1;background:radial-gradient(circle at 78% 12%,rgba(232,196,99,.16),transparent 28%),linear-gradient(90deg,rgba(6,26,44,.99) 0%,rgba(6,26,44,.96) 39%,rgba(6,26,44,.58) 62%,rgba(6,26,44,.12) 100%)}
.v820-hero-img{position:absolute;z-index:1;right:1.5%;bottom:-4%;height:99%;width:51%;object-fit:contain;object-position:right bottom;filter:drop-shadow(-16px 18px 30px rgba(0,0,0,.25))}
.v820-hero-noimg{position:absolute;right:2%;bottom:-3%;z-index:0;font-size:13rem;font-weight:950;color:rgba(255,255,255,.035);letter-spacing:-.12em}
.v820-hero-copy{position:relative;z-index:3;width:61%;padding:1.45rem 1.55rem 1rem}.v820-kicker{font-size:.56rem;font-weight:950;letter-spacing:.14em;text-transform:uppercase;color:#ffb1ae}.v820-scoreline{color:#b7c4d1;margin-left:.7rem;letter-spacing:.03em}
.v820-headline{font-size:clamp(2.65rem,5.1vw,4.8rem);font-weight:950;letter-spacing:-.075em;line-height:.86;margin:1.12rem 0 .7rem}.v820-headline a{color:#fff!important;text-decoration:none!important}
.v820-deck{font-size:clamp(.92rem,1.4vw,1.12rem);font-weight:800;line-height:1.3;color:#eef3f7;max-width:540px}.v820-subdeck{font-size:.69rem;color:#b8c5d1;font-weight:720;margin-top:.48rem}
.v820-hero-foot{position:absolute;z-index:4;left:1.55rem;right:1.55rem;bottom:1.25rem;border-top:1px solid rgba(255,255,255,.18);padding-top:.78rem;display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:1rem}
.v820-foot-label{font-size:.48rem;text-transform:uppercase;letter-spacing:.12em;font-weight:950;color:#9fb0c1}.v820-foot-main{font-size:.76rem;font-weight:900;margin-top:.18rem}.v820-foot-main strong{font-size:1.35rem;letter-spacing:-.04em;margin-left:.25rem;color:#78e2b2}.v820-foot-row{font-size:.67rem;font-weight:850;margin-top:.18rem}.v820-good{color:#78e2b2}.v820-bad{color:#ff9b96}

/* standings is a newspaper rail, not another rounded dashboard card */
.v820-rail{background:var(--v820-paper);border-top:4px solid var(--v820-ink);border-bottom:1px solid var(--v820-line);padding:.92rem 1rem .4rem;overflow:visible}
.v820-railhead{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--v820-line);padding-bottom:.62rem}.v820-railtitle{font-size:.58rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase}.v820-raillive{font-size:.5rem;font-weight:950;letter-spacing:.1em;text-transform:uppercase;color:var(--v820-red)}
.v820-leader{padding:1rem 0 .9rem;border-bottom:1px solid var(--v820-line)}.v820-place{font-size:.48rem;color:var(--v820-gold);font-weight:950;text-transform:uppercase;letter-spacing:.12em}.v820-leader-name details.v8-manager>summary{font-size:1.28rem!important;letter-spacing:-.04em!important}.v820-team{font-size:.59rem;color:var(--v820-muted);font-weight:720;margin-top:.1rem}
.v820-leader-score{font-size:2.25rem;font-weight:950;letter-spacing:-.065em;margin-top:.5rem}.v820-leader-score small{font-size:.54rem;color:var(--v820-muted);font-weight:800;letter-spacing:0;margin-left:.35rem}
.v820-rrow{display:grid;grid-template-columns:24px minmax(0,1fr) auto;gap:.42rem;align-items:center;padding:.63rem 0;border-bottom:1px solid #e4dfd6}.v820-rrow:last-child{border-bottom:0}.v820-pos{font-size:.59rem;color:#6e7883;font-weight:900}.v820-rname details.v8-manager>summary{font-size:.72rem!important}.v820-rmeta{font-size:.49rem;color:var(--v820-muted);font-weight:730;margin-top:.1rem}.v820-rpoints{font-size:.88rem;font-weight:950}.v820-up{color:var(--v820-green)!important}.v820-down{color:var(--v820-red)!important}

/* section headings are editorial markers, not card labels */
.v820-section{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin:1.7rem 0 .62rem}.v820-section strong{font-size:1.08rem;font-weight:950;letter-spacing:-.035em}.v820-section span{font-size:.58rem;color:var(--v820-muted);font-weight:740}

/* newsroom: one visual lead + two different secondary treatments */
.v820-news{display:grid;grid-template-columns:1.18fr .82fr;gap:1rem}.v820-leadstory{position:relative;min-height:345px;background:var(--v820-paper);border:1px solid var(--v820-line);overflow:hidden;border-radius:18px}.v820-leadstory.hasimg:before{content:"";position:absolute;inset:0;z-index:2;background:linear-gradient(90deg,rgba(6,26,44,.96) 0%,rgba(6,26,44,.88) 44%,rgba(6,26,44,.18) 100%)}.v820-story-img{position:absolute;right:0;bottom:-4%;width:56%;height:100%;object-fit:contain;object-position:right bottom;background:linear-gradient(135deg,#102b45,#1b506e)}
.v820-leadstory.hasimg .v820-story-copy{color:#fff;max-width:58%;z-index:3}.v820-leadstory.hasimg .v820-story-meta{color:#c6d1dc}.v820-leadstory.hasimg .v820-story-tag{color:#f0d48a}
.v820-story-graphic{position:absolute;left:0;top:0;bottom:0;width:43%;display:flex;align-items:center;justify-content:center;flex-direction:column;background:var(--v820-navy);color:#fff}.v820-story-arrow{font-size:3.6rem;line-height:.8;font-weight:950;color:#ff8f8a}.v820-story-number{font-size:6.5rem;line-height:.82;font-weight:950;letter-spacing:-.08em}.v820-story-month{font-size:3.2rem;line-height:.9;font-weight:950;letter-spacing:-.06em;text-align:center;padding:.6rem}.v820-story-trophy{font-size:4.5rem;line-height:1}
.v820-story-copy{position:absolute;left:47%;right:4.5%;bottom:1.35rem;z-index:3}.v820-story-tag{font-size:.5rem;text-transform:uppercase;letter-spacing:.12em;font-weight:950;color:var(--v820-gold)}.v820-story-head{font-size:clamp(1.45rem,2.5vw,2.1rem);font-weight:950;line-height:1.02;letter-spacing:-.045em;margin-top:.38rem}.v820-story-head a{text-decoration:none!important;color:inherit!important}.v820-story-meta{font-size:.62rem;color:var(--v820-muted);font-weight:720;margin-top:.55rem;line-height:1.35}
.v820-news-side{display:grid;grid-template-rows:1fr 1fr;gap:1rem}.v820-smallstory{position:relative;min-height:164px;background:var(--v820-paper);border:1px solid var(--v820-line);border-radius:18px;overflow:hidden;padding:1rem;display:flex;align-items:flex-end}.v820-smallstory.dark{background:#0a2943;color:#fff;border-color:#0a2943}.v820-smallstory img{position:absolute;right:-4%;bottom:-8%;height:96%;width:47%;object-fit:contain;object-position:right bottom;filter:drop-shadow(-6px 10px 14px rgba(0,0,0,.15))}.v820-small-copy{position:relative;z-index:2;max-width:64%}.v820-small-head{font-size:1.04rem;font-weight:950;line-height:1.05;letter-spacing:-.035em;margin-top:.3rem}.v820-small-head a{color:inherit!important;text-decoration:none!important}.v820-small-meta{font-size:.58rem;color:var(--v820-muted);font-weight:720;margin-top:.38rem}.v820-smallstory.dark .v820-small-meta{color:#bcc9d5}.v820-smallstory.dark .v820-story-tag{color:#efd38a}

/* player strip is image-first */
.v820-players{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.v820-player{position:relative;min-height:205px;background:var(--v820-paper);border:1px solid var(--v820-line);border-radius:18px;overflow:hidden;padding:1rem 1.05rem}.v820-player:after{content:"";position:absolute;width:155px;height:155px;border-radius:50%;right:-35px;bottom:-55px;background:#eee9de;z-index:0}.v820-player img{position:absolute;z-index:2;right:-1%;bottom:-4%;height:96%;width:50%;object-fit:contain;object-position:right bottom;filter:drop-shadow(-7px 11px 15px rgba(0,0,0,.12))}.v820-player-copy{position:relative;z-index:3;max-width:58%}.v820-player-club{font-size:.48rem;color:var(--v820-muted);font-weight:900;letter-spacing:.11em;text-transform:uppercase}.v820-player-name{font-size:1.18rem;font-weight:950;letter-spacing:-.045em;margin-top:.12rem}.v820-player-name a{text-decoration:none!important}.v820-player-pct{font-size:2.2rem;font-weight:950;letter-spacing:-.065em;margin-top:1.2rem}.v820-player-meta{font-size:.56rem;color:var(--v820-muted);font-weight:720;margin-top:.08rem}

/* personal widget is intentionally quiet */
.v820-personal{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:2px solid var(--v820-ink);border-bottom:1px solid var(--v820-line);background:rgba(255,255,255,.25)}.v820-personal-item{padding:.65rem .75rem}.v820-personal-item+.v820-personal-item{border-left:1px solid var(--v820-line)}.v820-personal-value{font-size:1rem;font-weight:950;letter-spacing:-.03em}.v820-personal-label{font-size:.49rem;color:var(--v820-muted);font-weight:900;text-transform:uppercase;letter-spacing:.1em;margin-top:.08rem}

/* analysis is a destination, not homepage clutter */
.v820-analysis-invite{margin-top:1.75rem;background:var(--v820-navy);color:#fff;border-radius:17px;padding:1rem 1.1rem;display:flex;align-items:center;justify-content:space-between;gap:1rem}.v820-analysis-invite strong{font-size:1.05rem;letter-spacing:-.035em}.v820-analysis-invite span{display:block;color:#afbdca;font-size:.59rem;font-weight:700;margin-top:.14rem}.v820-analysis-invite a{color:#fff!important;text-decoration:none!important;border:1px solid rgba(255,255,255,.18);padding:.48rem .68rem;border-radius:999px;font-size:.61rem;font-weight:900;white-space:nowrap}

@media(max-width:980px){
  .v820-front{grid-template-columns:1fr}.v820-hero{height:440px}.v820-rail{border-radius:14px}.v820-news{grid-template-columns:1fr}.v820-leadstory{min-height:320px}.v820-players{grid-template-columns:repeat(3,minmax(0,1fr))}.v820-ticker{justify-content:flex-start}
}
@media(max-width:760px){
  .block-container{padding:.5rem .55rem 2.5rem!important}.v8-shell{border-radius:14px!important}.v820-ticker{font-size:.58rem;gap:.44rem;overflow-x:auto;justify-content:flex-start}.v820-ticker-item{overflow:visible;text-overflow:clip}.v820-ticker-sep{display:none}
  .v820-hero{height:510px;border-radius:17px}.v820-hero-copy{width:88%;padding:1rem}.v820-headline{font-size:2.75rem;max-width:82%;margin-top:.8rem}.v820-deck{font-size:.86rem;max-width:72%}.v820-subdeck{max-width:70%}.v820-hero-img{height:67%;width:61%;right:-8%;bottom:12%}.v820-hero-foot{left:1rem;right:1rem;bottom:.9rem;grid-template-columns:1fr 1fr;gap:.6rem}.v820-hero-foot>div:first-child{grid-column:1/-1}.v820-foot-main strong{font-size:1.1rem}
  .v820-news-side{grid-template-rows:auto}.v820-smallstory{min-height:150px}.v820-players{grid-template-columns:1fr}.v820-player{min-height:155px}.v820-player img{height:145px;width:46%}.v820-player-pct{margin-top:.65rem;font-size:1.8rem}.v820-personal{grid-template-columns:1fr 1fr}.v820-personal-item:nth-child(3){grid-column:1/-1;border-left:0;border-top:1px solid var(--v820-line)}.v820-analysis-invite{align-items:flex-start;flex-direction:column}
}
@media(max-width:430px){
  .v820-headline{font-size:2.35rem;max-width:92%}.v820-deck{max-width:85%}.v820-hero-img{opacity:.88;width:68%;right:-14%}.v820-story-graphic{width:38%}.v820-story-copy{left:42%;right:4%}.v820-story-number{font-size:5rem}.v820-small-copy{max-width:70%}
}
</style>
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def install_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(CSS_V820, unsafe_allow_html=True)


def _initials(name: str) -> str:
    parts = [x for x in str(name or "").replace("-", " ").split() if x]
    return "".join(x[0] for x in parts[:2]).upper() or "LRO"


def _img(url: str, cls: str = "", eager: bool = False) -> str:
    if not url:
        return ""
    loading = "eager" if eager else "lazy"
    class_attr = f' class="{esc(cls)}"' if cls else ""
    return f'<img{class_attr} src="{esc(url)}" alt="" loading="{loading}" decoding="async">'


def _manager_menu(entry: int, name: str, team: str, me: int = 0, captain: str = "") -> str:
    links = [
        ("Se laget", manager_href(entry, me=me)),
        ("Sammenlign", compare_href([entry] if not me or me == entry else [me, entry], me=me)),
        ("Rivalradar", rival_href(me or entry, 0 if me == entry else entry)),
        ("Historikk", manager_href(entry, me=me) + "#historikk"),
    ]
    menu = "".join(f'<a target="_self" href="{esc(url)}">{esc(label)}</a>' for label, url in links)
    return (
        f'<details class="v8-manager"><summary>{esc(name)}</summary>'
        f'<div class="v8-menu"><div style="padding:.34rem .52rem .25rem;font-size:.60rem;color:#687386;font-weight:760">{esc(team)}'
        + (f" · {esc(captain)}" if captain else "")
        + f"</div>{menu}</div></details>"
    )


def app_header(league_name: str, season: str, page: str, me: int = 0, status: str = "", updated: str = "") -> None:
    nav = [
        ("Forside", href("Forside", me=me)),
        ("Ligaen", league_href("Tabell", me=me)),
        ("Hall of Fame", href("Hall of Fame", me=me)),
        ("Analyse", rival_href(me or 0)),
    ]
    active_page = "Ligaen" if page in {"Manager", "Spiller"} else ("Analyse" if page == "Rivalradar" else page)
    nav_html = "".join(f'<a target="_self" class="{"active" if label == active_page else ""}" href="{esc(url)}">{esc(label)}</a>' for label, url in nav)
    status_html = ""
    if status or updated:
        dot = '<span class="v8-live-dot"></span>' if status.casefold() == "live" else ""
        txt = " · ".join(x for x in [status, updated] if x)
        status_html = f'<div class="v8-live-status">{dot}{esc(txt)}</div>'
    st.markdown(
        f'<div class="v8-shell"><div class="v8-shell-top"><div><div class="v8-brand">{esc(league_name)}</div><div class="v8-season">Sesong {esc(season)}</div></div>{status_html}</div><div class="v8-shell-nav">{nav_html}</div></div>',
        unsafe_allow_html=True,
    )


def page_lead(title: str, kicker: str = "", meta: str = "") -> None:
    st.markdown(
        f'<div class="v8-page"><div>{f"<div class=\'v8-kicker\'>{esc(kicker)}</div>" if kicker else ""}<h1>{esc(title)}</h1></div>{f"<div class=\'v8-page-meta\'>{esc(meta)}</div>" if meta else ""}</div>',
        unsafe_allow_html=True,
    )


def section(title: str, meta: str = "") -> None:
    st.markdown(f'<div class="v8-section"><strong>{esc(title)}</strong><span>{esc(meta)}</span></div>', unsafe_allow_html=True)


def status_strip(items: list[tuple[str, str, str]]) -> None:
    html_items = "".join(
        f'<div class="v8-strip-item"><div class="v8-strip-label">{esc(label)}</div><div class="v8-strip-value">{esc(value)}</div><div class="v8-strip-sub">{esc(sub)}</div></div>'
        for label, value, sub in items[:3]
    )
    st.markdown(f'<div class="v8-strip">{html_items}</div>', unsafe_allow_html=True)


def _rail_html(rows: list[ManagerLiveState], me: int = 0, live: bool = False) -> str:
    if not rows:
        return '<div class="v81-toprail"><div class="v8-muted">Tabellen lastes.</div></div>'
    leader = rows[0]
    cap = leader.captain if leader.captain != "–" else ""
    leader_menu = _manager_menu(leader.entry, leader.manager, leader.team, me=me, captain=cap)
    move = leader.live_rank_change
    move_txt = f'↑{move}' if move > 0 else f'↓{abs(move)}' if move < 0 else '–'
    move_cls = 'v81-up' if move > 0 else 'v81-down' if move < 0 else ''
    body = [
        '<div class="v81-toprail">',
        f'<div class="v81-railhead"><div class="v81-railtitle">Toppen</div><div class="v81-raillive">{"Live" if live else "Sammenlagt"}</div></div>',
        f'<div class="v81-rail-leader"><div><div class="v81-rail-rank">1. plass</div><div class="v81-rail-name">{leader_menu}</div><div class="v81-rail-team">{esc(leader.team)}' + (f' · {esc(cap)}' if cap else '') + f' <span class="v81-move {move_cls}">{move_txt}</span></div></div><div class="v81-rail-score"><strong>{leader.live_total_points}</strong><span>{leader.live_gw_points} GW</span></div></div>'
    ]
    for m in rows[1:5]:
        cap = m.captain if m.captain != "–" else ""
        menu = _manager_menu(m.entry, m.manager, m.team, me=me, captain=cap)
        move = m.live_rank_change
        move_txt = f'↑{move}' if move > 0 else f'↓{abs(move)}' if move < 0 else '–'
        move_cls = 'v81-up' if move > 0 else 'v81-down' if move < 0 else ''
        body.append(
            f'<div class="v81-rail-row"><div class="v81-rail-pos">{m.live_rank}</div><div>{menu}<div class="v81-rail-meta">{esc(cap or m.team)} <span class="v81-move {move_cls}">{move_txt}</span></div></div><div class="v81-rail-total">{m.live_total_points}</div></div>'
        )
    body.append('</div>')
    return ''.join(body)


def home_matchday(state: LiveState, beneficiary_rows: list[dict[str, Any]], scoreline: str, top_rows: list[ManagerLiveState], me: int = 0) -> None:
    live_players = [p for p in state.player_impacts if p.fixture_status == "live" and (p.event_points or p.captain_count or p.triple_captain_count)]
    p = live_players[0] if live_players else (state.player_impacts[0] if state.player_impacts else None)
    if p:
        name = f'<a target="_self" href="{esc(player_href(p.element, me=me))}">{esc(p.player)}</a>'
        cap_label = f"{p.captain_count} kaptein" if p.captain_count == 1 else f"{p.captain_count} kapteiner"
        stat_bits = [f"{p.event_points} poeng", f"{p.ownership_count} eiere"]
        if p.captain_count:
            stat_bits.append(cap_label)
        if p.triple_captain_count:
            stat_bits.append(f"{p.triple_captain_count} TC")
        deck = " · ".join(stat_bits)
        hero_img = _img(p.image_url, "v81-hero-playerimg", eager=True)
        no_img = '' if hero_img else f'<div class="v81-hero-noimg">{esc(_initials(p.player))}</div>'
    else:
        name = f"GW{state.event_id}"
        deck = "Lofthus oppdateres mens kampene pågår."
        hero_img = ""
        no_img = '<div class="v81-hero-noimg">LRO</div>'
    impacts = []
    for r in beneficiary_rows[:5]:
        swing = nfloat(r.get("swing"))
        cls = "neg" if swing < 0 else ""
        impacts.append(
            f'<div class="v81-impact {cls}"><div class="v81-impact-name"><a target="_self" href="{esc(manager_href(nint(r.get("entry")), me=me))}">{esc(r.get("manager"))}</a></div><div class="v81-impact-value">{swing:+.1f}</div></div>'
        )
    impacts_html = ''.join(impacts) if impacts else '<div class="v81-impact"><div class="v81-impact-name">Lagpåvirkning</div><div class="v81-impact-value">laster</div></div>'
    max_swing = max((abs(nfloat(r.get("swing"))) for r in beneficiary_rows), default=0.0)
    hero_stats = (
        f'<div class="v81-hero-statline"><span class="v81-hero-stat">EO {p.effective_ownership_pct:.0f} %</span><span class="v81-hero-stat">Største swing {max_swing:.1f}</span></div>'
        if p else '<div class="v81-hero-statline"><span class="v81-hero-stat">Live</span></div>'
    )
    hero = (
        f'<div class="v81-hero">{hero_img}{no_img}<div class="v81-hero-body">'
        f'<div class="v81-hero-kicker"><span><span class="v8-live-dot"></span>LIVE · GW{state.event_id}</span><span class="v81-hero-score">{esc(scoreline)}</span></div>'
        f'<div class="v81-hero-name">{name}</div><div class="v81-hero-deck">{esc(deck)}</div>{hero_stats}</div>'
        f'<div class="v81-impactbox">{impacts_html}</div></div>'
    )
    rail = _rail_html(top_rows[:5], me=me, live=True)
    st.markdown(f'<div class="v81-frontgrid">{hero}{rail}</div>', unsafe_allow_html=True)


def live_centre(state: LiveState, beneficiary_rows: list[dict[str, Any]], scoreline: str = "", me: int = 0) -> None:
    """Kept for secondary pages/backwards compatibility; the front page uses home_matchday."""
    home_matchday(state, beneficiary_rows, scoreline, state.top(5), me=me)


def top_five(rows: list[ManagerLiveState], me: int = 0, live: bool = False) -> None:
    if not rows:
        st.markdown('<div class="v8-empty">Tabellen lastes inn.</div>', unsafe_allow_html=True)
        return
    def row_html(m: ManagerLiveState, lead: bool = False) -> str:
        move = m.live_rank_change
        move_html = f'<span class="v81-move {"v81-up" if move>0 else "v81-down" if move<0 else ""}">{"↑"+str(move) if move>0 else "↓"+str(abs(move)) if move<0 else "–"}</span>'
        cap = m.captain if m.captain != "–" else ""
        manager = _manager_menu(m.entry, m.manager, m.team, me=me, captain=cap)
        cls = "v8-top-lead" if lead else "v8-top-row"
        return f'<div class="{cls}"><div class="v8-top-rank">{"Leder" if lead else str(m.live_rank)+". plass"}</div><div class="v8-top-name">{manager}<div class="v8-top-meta">{esc(m.team)}' + (f' · {esc(cap)}' if cap else '') + f' {move_html}</div></div><div class="v8-top-points">{m.live_total_points}<small>{m.live_gw_points} GW{" · live" if live else ""}</small></div></div>'
    html_rows = row_html(rows[0], True) + "".join(row_html(m, False) for m in rows[1:5])
    st.markdown(f'<div class="v8-top5">{html_rows}</div>', unsafe_allow_html=True)


def story_list(stories: Iterable[Any], me: int = 0, state: LiveState | None = None) -> None:
    data = list(stories)
    if not data:
        st.markdown('<div class="v8-empty">Ingen sak slår gjennom nyhetsterskelen akkurat nå.</div>', unsafe_allow_html=True)
        return
    cards = []
    for i, story in enumerate(data[:4], start=1):
        manager_entry = nint(getattr(story, "manager_entry", 0))
        player_element = nint(getattr(story, "player_element", 0))
        headline = esc(getattr(story, "headline", ""))
        if manager_entry:
            headline = f'<a target="_self" href="{esc(manager_href(manager_entry, me=me))}">{headline}</a>'
        elif player_element:
            headline = f'<a target="_self" href="{esc(player_href(player_element, me=me))}">{headline}</a>'
        image = ""
        if state and player_element:
            impact = state.player(player_element)
            if impact and impact.image_url:
                image = _img(impact.image_url, "v81-story-img", eager=(i == 1))
        raw_status = str(getattr(story, "status", "") or "Snakkis").casefold()
        status = {"live": "LIVE", "settled": "Ferdig", "provisional": "LIVE", "context": "Analyse"}.get(raw_status, raw_status.title() or "Snakkis")
        cards.append(
            f'<article class="v81-story">{image}<div class="v81-story-number">0{i}</div><div class="v81-story-content"><div class="v81-story-kicker">{esc(status)}</div><div class="v81-story-head">{headline}</div><div class="v81-story-meta">{esc(getattr(story,"meta",""))}</div></div></article>'
        )
    st.markdown(f'<div class="v81-newsgrid">{"".join(cards)}</div>', unsafe_allow_html=True)


def popular_players(players: list[PlayerImpact], me: int = 0, limit: int = 3) -> None:
    top = sorted(players, key=lambda p: (-p.ownership_count, -p.captain_count, p.player))[:limit]
    if not top:
        st.markdown('<div class="v8-empty">Eierskap lastes inn.</div>', unsafe_allow_html=True)
        return
    cards = []
    for p in top:
        cards.append(
            f'<div class="v81-playercard">{_img(p.image_url, eager=False) if p.image_url else ""}<div class="v81-playercard-copy"><div class="v81-playercard-name"><a target="_self" href="{esc(player_href(p.element, me=me))}">{esc(p.player)}</a></div><div class="v81-playercard-club">{esc(p.club)}</div><div class="v81-playercard-stat">{p.ownership_pct:.0f} %</div><div class="v81-playercard-meta">{p.ownership_count} eiere · {p.captain_count} C</div></div></div>'
        )
    st.markdown(f'<div class="v81-playercards">{"".join(cards)}</div>', unsafe_allow_html=True)


def league_table(rows: list[ManagerLiveState], me: int = 0, live: bool = False) -> None:
    head = '<div class="v8-league-head"><div>#</div><div>Manager</div><div>Lag</div><div>Kaptein</div><div style="text-align:right">GW</div><div style="text-align:right">Poeng</div><div style="text-align:right">+/-</div></div>'
    body = []
    for m in rows:
        move = m.live_rank_change
        move_text = f"↑{move}" if move > 0 else f"↓{abs(move)}" if move < 0 else "–"
        move_cls = "v81-up" if move > 0 else "v81-down" if move < 0 else ""
        cap = m.captain if m.captain != "–" else "–"
        chip = f'<span class="v8-chip">{esc(m.active_chip)}</span>' if m.active_chip and m.active_chip not in {"Triple Captain"} else ""
        manager = _manager_menu(m.entry, m.manager, m.team, me=me, captain=cap)
        mobile_sub = f'<div class="v8-manager-sub">{esc(m.team)} · {esc(cap)} · {m.live_gw_points} GW · <span class="{move_cls}">{move_text}</span></div>'
        body.append(
            f'<div class="v8-league-row"><div class="v8-rank">{m.live_rank}</div><div>{manager}{mobile_sub}</div><div class="v8-team">{esc(m.team)}{chip}</div><div class="v8-cap">{esc(cap)}</div><div class="v8-num v8-gw">{m.live_gw_points}</div><div class="v8-num v8-total">{m.live_total_points}</div><div class="v8-num v8-move-cell {move_cls}">{move_text}</div></div>'
        )
    st.markdown(f'<div class="v8-league">{head}{"".join(body)}</div>', unsafe_allow_html=True)


def month_table(rows: list[ManagerLiveState], me: int = 0, limit: int | None = None) -> None:
    block = rows[:limit] if limit else rows
    data = "".join(
        f'<tr><td class="num">{m.month_rank}</td><td>{_manager_menu(m.entry,m.manager,m.team,me=me,captain=m.captain if m.captain!="–" else "")}</td><td>{esc(m.team)}</td><td class="num">{m.month_points}</td></tr>' for m in block
    )
    st.markdown(f'<div class="v8-table-wrap"><table class="v8-table"><thead><tr><th class="num">#</th><th>Manager</th><th>Lag</th><th class="num">Poeng</th></tr></thead><tbody>{data}</tbody></table></div>', unsafe_allow_html=True)


def manager_header(m: ManagerLiveState) -> None:
    move = m.live_rank_change
    move_txt = f"↑ {move} live" if move > 0 else f"↓ {abs(move)} live" if move < 0 else "samme plass"
    st.markdown(
        f'<div class="v8-profile"><div class="v8-profile-grid"><div class="v8-profile-main"><div class="v8-profile-name">{esc(m.manager)}</div><div class="v8-profile-team">{esc(m.team)} · {esc(m.captain)} · {esc(move_txt)}</div></div><div class="v8-profile-stat"><strong>{m.live_rank}.</strong><span>Plass</span></div><div class="v8-profile-stat"><strong>{m.live_total_points}</strong><span>Poeng</span></div><div class="v8-profile-stat"><strong>{m.live_gw_points}</strong><span>Denne GW</span></div></div></div>',
        unsafe_allow_html=True,
    )


def player_hero(name: str, club: str, image_url: str, event_points: int, ownership: str, captains: int, status: str = "") -> None:
    status_label = status.replace("not_started", "Ikke startet").replace("finished", "Ferdig").replace("live", "LIVE")
    img = _img(image_url, eager=True) if image_url else ""
    st.markdown(
        f'<div class="v81-playerhero">{img}<div class="v81-playerhero-copy"><div class="v81-playerhero-club">{esc(club or "Lofthus")}{" · "+esc(status_label) if status_label else ""}</div><div class="v81-playerhero-name">{esc(name)}</div><div class="v81-playerhero-stats"><div class="v81-playerhero-stat"><strong>{event_points}</strong><span>GW-poeng</span></div><div class="v81-playerhero-stat"><strong>{esc(ownership)}</strong><span>LRO-eierskap</span></div><div class="v81-playerhero-stat"><strong>{captains}</strong><span>Kapteiner</span></div></div></div></div>',
        unsafe_allow_html=True,
    )


def profile_story(text: str) -> None:
    if text:
        st.markdown(f'<div class="v8-profile-story">{esc(text)}</div>', unsafe_allow_html=True)


def squad_formation(squad: pd.DataFrame, status_map: dict[int, str] | None = None, me: int = 0) -> None:
    if squad is None or squad.empty:
        st.markdown('<div class="v8-empty">Troppen kunne ikke lastes.</div>', unsafe_allow_html=True)
        return
    status_map = status_map or {}
    starters = squad[~squad["on_bench"].astype(bool)].copy()
    bench = squad[squad["on_bench"].astype(bool)].copy()
    def player_html(r: dict) -> str:
        status = status_map.get(nint(r.get("element")), "")
        badge = ""
        if bool(r.get("is_captain")):
            badge = '<span class="v8-badge tc">TC</span>' if bool(r.get("is_triple_captain")) or nint(r.get("multiplier")) >= 3 else '<span class="v8-badge">C</span>'
        elif bool(r.get("is_vice_captain")):
            badge = '<span class="v8-badge vc">VC</span>'
        raw = nint(r.get("event_points"))
        meta = f"{raw} p" + (f" ×{nint(r.get('multiplier'))}" if nint(r.get("multiplier")) > 1 else "")
        image = _img(str(r.get("image_url") or ""), "v8-player-img")
        return f'<div class="v8-player {esc(status)}">{image}<div class="v8-player-name"><a target="_self" href="{esc(player_href(nint(r.get("element")), me=me))}" style="color:inherit;text-decoration:none">{esc(r.get("player"))}</a>{badge}</div><div class="v8-player-meta">{esc(meta)} · {esc(status.replace("not_started","ikke startet").replace("finished","ferdig").replace("live","live"))}</div></div>'
    lines = []
    for pos in [1,2,3,4]:
        block = starters[starters["position_id"].map(nint) == pos]
        if not block.empty:
            lines.append('<div class="v8-line">' + ''.join(player_html(r) for r in block.sort_values("squad_position").to_dict("records")) + '</div>')
    bench_html = '<div class="v8-bench">' + ''.join(player_html(r) for r in bench.sort_values("squad_position").to_dict("records")) + '</div>' if not bench.empty else ""
    st.markdown(f'<div class="v8-pitch">{"".join(lines)}{bench_html}</div>', unsafe_allow_html=True)


def form_strip(rows: list[dict[str, Any]]) -> None:
    html_rows = "".join(
        f'<div class="v8-form-item"><div class="v8-form-gw">GW{nint(r.get("event"))}{" · live" if r.get("is_live") else ""}</div><div class="v8-form-points">{nint(r.get("points"))}</div><div class="v8-form-rank">{nint(r.get("round_rank"))}. i GW · {nint(r.get("league_rank"))}. totalt</div></div>'
        for r in rows
    )
    st.markdown(f'<div class="v8-form">{html_rows}</div>' if html_rows else '<div class="v8-empty">Formdata er ikke tilgjengelig.</div>', unsafe_allow_html=True)


def mini_grid(items: list[tuple[Any, str]]) -> None:
    html_items = "".join(f'<div class="v8-mini"><strong>{esc(value)}</strong><span>{esc(label)}</span></div>' for value, label in items[:3])
    st.markdown(f'<div class="v8-mini-grid">{html_items}</div>', unsafe_allow_html=True)


def duel_header(me: ManagerLiveState, rival: ManagerLiveState, gap: int) -> None:
    st.markdown(
        f'<div class="v8-duel"><div class="v8-duel-side"><div class="v8-duel-name">{esc(me.manager)}</div><div class="v8-duel-points">{me.live_total_points}</div><div class="v8-duel-meta">{me.live_gw_points} GW · {me.players_remaining} igjen · {esc(me.captain)}</div></div><div class="v8-vs">{abs(gap)} p</div><div class="v8-duel-side"><div class="v8-duel-name">{esc(rival.manager)}</div><div class="v8-duel-points">{rival.live_total_points}</div><div class="v8-duel-meta">{rival.live_gw_points} GW · {rival.players_remaining} igjen · {esc(rival.captain)}</div></div></div>',
        unsafe_allow_html=True,
    )


def cheer_columns(cheer: Iterable[Any], blank: Iterable[Any]) -> None:
    def rows(items: Iterable[Any]) -> str:
        data = list(items)
        if not data:
            return '<div class="v8-muted" style="padding:.45rem 0">Ingen klare utslag akkurat nå.</div>'
        return "".join(f'<div class="v8-edge"><strong>{esc(x.player)}</strong><span>{x.multiplier_edge:+d}×</span></div>' for x in data[:6])
    st.markdown(f'<div class="v8-cheer"><div class="v8-cheer-col"><div class="v8-cheer-title">Heia på</div>{rows(cheer)}</div><div class="v8-cheer-col bad"><div class="v8-cheer-title">Håp på blank</div>{rows(blank)}</div></div>', unsafe_allow_html=True)


def simple_table(headers: list[tuple[str, str]], rows: list[dict[str, Any]], numeric: set[str] | None = None) -> None:
    numeric = numeric or set()
    th = "".join(f'<th class="{"num" if key in numeric else ""}">{esc(label)}</th>' for key,label in headers)
    tr = []
    for row in rows:
        cells = "".join(f'<td class="{"num" if key in numeric else ""}">{esc(row.get(key,""))}</td>' for key,_ in headers)
        tr.append(f"<tr>{cells}</tr>")
    st.markdown(f'<div class="v8-table-wrap"><table class="v8-table"><thead><tr>{th}</tr></thead><tbody>{"".join(tr)}</tbody></table></div>', unsafe_allow_html=True)


def data_quality(state: LiveState | None) -> None:
    if state is None:
        return
    loaded = nint(state.data_quality.get("loaded_managers"))
    total = nint(state.data_quality.get("league_size"))
    if total and loaded < total:
        st.caption(f"Live-data: {loaded}/{total} lag klare. Resten fylles inn fortløpende.")


def subnav(items: list[tuple[str, str]], active: str) -> None:
    links = ''.join(
        f'<a target="_self" class="{"active" if label == active else ""}" href="{esc(url)}">{esc(label)}</a>'
        for label, url in items
    )
    st.markdown(f'<div class="v8-subnav">{links}</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# V820 sportsfront primitives
# ---------------------------------------------------------------------------

def home_ticker(items: list[tuple[str, str, str]]) -> None:
    """One quiet line of context. Deliberately not three dashboard cards."""
    bits = []
    for label, value, sub in items[:3]:
        tail = f" {esc(sub)}" if sub else ""
        bits.append(
            f'<div class="v820-ticker-item"><span class="v820-ticker-label">{esc(label)}</span>'
            f'<b>{esc(value)}</b>{tail}</div>'
        )
    if not bits:
        return
    st.markdown(
        '<div class="v820-ticker">' + '<span class="v820-ticker-sep">•</span>'.join(bits) + '</div>',
        unsafe_allow_html=True,
    )


def sports_section(title: str, meta: str = "") -> None:
    st.markdown(
        f'<div class="v820-section"><strong>{esc(title)}</strong><span>{esc(meta)}</span></div>',
        unsafe_allow_html=True,
    )


def _img_v820(url: str, cls: str = "", eager: bool = False) -> str:
    """Current PL cut-out with a same-CDN fallback size.

    The current player asset tree is `premierleague25`. A handful of 500px cuts
    can lag behind the smaller version, so an inline fallback avoids another
    giant empty hero without adding app-side HTTP proxying.
    """
    if not url:
        return ""
    loading = "eager" if eager else "lazy"
    class_attr = f' class="{esc(cls)}"' if cls else ""
    fallback = url.replace('/500x500/', '/250x250/') if '/500x500/' in url else ""
    onerror = f' onerror="this.onerror=null;this.src=\'{esc(fallback)}\';"' if fallback and fallback != url else ""
    return f'<img{class_attr} src="{esc(url)}" alt="" loading="{loading}" decoding="async"{onerror}>'


def _v820_rail_html(rows: list[ManagerLiveState], me: int = 0, live: bool = False) -> str:
    if not rows:
        return '<aside class="v820-rail"><div class="v8-muted">Tabellen lastes.</div></aside>'
    leader = rows[0]
    cap = leader.captain if leader.captain != "–" else ""
    leader_menu = _manager_menu(leader.entry, leader.manager, leader.team, me=me, captain=cap)
    move = leader.live_rank_change
    move_txt = f'↑{move}' if move > 0 else f'↓{abs(move)}' if move < 0 else '–'
    move_cls = 'v820-up' if move > 0 else 'v820-down' if move < 0 else ''
    out = [
        '<aside class="v820-rail">',
        f'<div class="v820-railhead"><div class="v820-railtitle">Topp 5</div><div class="v820-raillive">{"Live" if live else "Sammenlagt"}</div></div>',
        '<div class="v820-leader">',
        '<div class="v820-place">1. plass</div>',
        f'<div class="v820-leader-name">{leader_menu}</div>',
        f'<div class="v820-team">{esc(leader.team)}' + (f' · {esc(cap)}' if cap else '') + f' · <span class="{move_cls}">{move_txt}</span></div>',
        f'<div class="v820-leader-score">{leader.live_total_points}<small>{leader.live_gw_points} GW</small></div>',
        '</div>',
    ]
    for m in rows[1:5]:
        cap = m.captain if m.captain != "–" else ""
        menu = _manager_menu(m.entry, m.manager, m.team, me=me, captain=cap)
        move = m.live_rank_change
        move_txt = f'↑{move}' if move > 0 else f'↓{abs(move)}' if move < 0 else '–'
        move_cls = 'v820-up' if move > 0 else 'v820-down' if move < 0 else ''
        out.append(
            f'<div class="v820-rrow"><div class="v820-pos">{m.live_rank}</div>'
            f'<div class="v820-rname">{menu}<div class="v820-rmeta">{esc(cap or m.team)} · <span class="{move_cls}">{move_txt}</span></div></div>'
            f'<div class="v820-rpoints">{m.live_total_points}</div></div>'
        )
    out.append('</aside>')
    return ''.join(out)


def _sports_headline(player: PlayerImpact, live: bool) -> str:
    name = player.player.upper()
    if live:
        if player.event_points >= 12:
            return f"{name} SETTER FYR PÅ LOFTHUS"
        if player.event_points >= 8:
            return f"{name} DRIVER LIVE-RUNDEN"
        return f"{name} PÅVIRKER HELE LIGAEN"
    if player.event_points >= 12:
        return f"{name} BLE RUNDENS STORE SPILLER"
    return f"{name} PREGET SISTE RUNDE"


def sports_front(
    state: LiveState,
    beneficiary_rows: list[dict[str, Any]],
    scoreline: str,
    top_rows: list[ManagerLiveState],
    me: int = 0,
) -> None:
    """Image-led matchday front. This is the public face of V820."""
    candidates = [p for p in state.player_impacts if p.event_points or p.captain_count or p.triple_captain_count]
    if state.is_live:
        live_now = [p for p in candidates if p.fixture_status == "live"]
        p = live_now[0] if live_now else (candidates[0] if candidates else None)
    else:
        p = max(candidates, key=lambda x: (x.event_points, x.impact_score), default=None)

    if p:
        player_link = f'<a target="_self" href="{esc(player_href(p.element, me=me))}">{esc(_sports_headline(p, state.is_live))}</a>'
        cap_word = "kaptein" if p.captain_count == 1 else "kapteiner"
        ownership_line = f"{p.ownership_count} av {max(1,state.league_size)} eier {esc(p.player)}"
        if p.captain_count:
            ownership_line += f" · {p.captain_count} {cap_word}"
        positive = [r for r in beneficiary_rows if float(r.get("swing") or 0) > 0]
        negative = [r for r in beneficiary_rows if float(r.get("swing") or 0) < 0]
        biggest = positive[0] if positive else None
        if biggest:
            deck = f"{p.event_points} poeng. {biggest.get('manager')} får den største gevinsten i ligaen."
        else:
            deck = f"{p.event_points} poeng og en tydelig effekt på Lofthus-tabellen."
        image = _img_v820(p.image_url, "v820-hero-img", eager=True)
        fallback = '' if image else f'<div class="v820-hero-noimg">{esc(_initials(p.player))}</div>'
    else:
        player_link = f"GW{state.event_id}"
        deck = "Lofthus følger kampene mens tabellen flytter på seg."
        ownership_line = ""
        image = ""
        fallback = '<div class="v820-hero-noimg">LRO</div>'
        positive, negative = [], []

    phase = "LIVE" if state.is_live else "SISTE GW"
    score = scoreline or ("Kampene pågår" if state.is_live else "Runden er oppdatert")
    foot = []
    if p and positive:
        r = positive[0]
        foot.append(
            f'<div><div class="v820-foot-label">Største vinner</div><div class="v820-foot-main">{esc(r.get("manager"))}<strong>+{float(r.get("swing") or 0):.1f}</strong></div></div>'
        )
    else:
        foot.append('<div><div class="v820-foot-label">Ligaeffekt</div><div class="v820-foot-main">Oppdateres fortløpende</div></div>')
    other_pos = positive[1:3]
    foot.append(
        '<div><div class="v820-foot-label">Andre vinnere</div>' +
        ''.join(f'<div class="v820-foot-row v820-good">{esc(r.get("manager"))} +{float(r.get("swing") or 0):.1f}</div>' for r in other_pos) +
        ('<div class="v820-foot-row">Ingen store utslag</div>' if not other_pos else '') + '</div>'
    )
    foot.append(
        '<div><div class="v820-foot-label">Rammes hardest</div>' +
        ''.join(f'<div class="v820-foot-row v820-bad">{esc(r.get("manager"))} {float(r.get("swing") or 0):.1f}</div>' for r in negative[:2]) +
        ('<div class="v820-foot-row">Ingen store utslag</div>' if not negative else '') + '</div>'
    )

    hero = (
        f'<section class="v820-hero">{image}{fallback}<div class="v820-hero-copy">'
        f'<div class="v820-kicker"><span class="v8-live-dot"></span>{phase} · GW{state.event_id}<span class="v820-scoreline">{esc(score)}</span></div>'
        f'<div class="v820-headline">{player_link}</div><div class="v820-deck">{esc(deck)}</div>'
        f'<div class="v820-subdeck">{ownership_line}</div></div><div class="v820-hero-foot">{"".join(foot)}</div></section>'
    )
    st.markdown(
        f'<div class="v820-front">{hero}{_v820_rail_html(top_rows[:5], me=me, live=state.is_live)}</div>',
        unsafe_allow_html=True,
    )


def _movement_graphic(headline: str) -> str:
    import re
    match = re.search(r"(\d+)\s+plasser", headline or "", re.I)
    magnitude = match.group(1) if match else ""
    low = (headline or "").casefold()
    arrow = "↓" if any(x in low for x in ("falt", "ned", "raste")) else "↑"
    if not magnitude:
        magnitude = "!"
    return f'<div class="v820-story-graphic"><div class="v820-story-arrow">{arrow}</div><div class="v820-story-number">{esc(magnitude)}</div></div>'


def _story_visual(story: Any, state: LiveState | None, lead: bool) -> tuple[str, str]:
    category = str(getattr(story, "category", "") or "")
    player_element = nint(getattr(story, "player_element", 0))
    if state and player_element:
        impact = state.player(player_element)
        if impact and impact.image_url:
            return _img_v820(impact.image_url, "v820-story-img", eager=lead), "hasimg"
    if category in {"movement", "movement_live"}:
        return _movement_graphic(str(getattr(story, "headline", ""))), "graphic"
    if category == "month":
        month = (state.month_name if state else "Måned") or "Måned"
        short = month[:3].upper()
        return f'<div class="v820-story-graphic"><div class="v820-story-month">{esc(short)}</div></div>', "graphic"
    if category == "round":
        return '<div class="v820-story-graphic"><div class="v820-story-trophy">🏆</div></div>', "graphic"
    if category == "leader":
        return '<div class="v820-story-graphic"><div class="v820-story-number">1</div></div>', "graphic"
    return '<div class="v820-story-graphic"><div class="v820-story-number">LRO</div></div>', "graphic"


def sports_news(stories: Iterable[Any], me: int = 0, state: LiveState | None = None) -> None:
    data = list(stories)[:3]
    if not data:
        st.markdown('<div class="v8-empty">Ingen stor nok historie akkurat nå.</div>', unsafe_allow_html=True)
        return

    def headline_html(story: Any) -> str:
        headline = esc(getattr(story, "headline", ""))
        manager_entry = nint(getattr(story, "manager_entry", 0))
        player_element = nint(getattr(story, "player_element", 0))
        if manager_entry:
            return f'<a target="_self" href="{esc(manager_href(manager_entry, me=me))}">{headline}</a>'
        if player_element:
            return f'<a target="_self" href="{esc(player_href(player_element, me=me))}">{headline}</a>'
        return headline

    def status_label(story: Any) -> str:
        raw = str(getattr(story, "status", "") or "").casefold()
        return {"live": "LIVE", "settled": "FERDIG", "provisional": "LIVE", "context": "ANALYSE"}.get(raw, raw.upper() or "SNAKKIS")

    lead = data[0]
    visual, kind = _story_visual(lead, state, True)
    lead_cls = "v820-leadstory hasimg" if kind == "hasimg" else "v820-leadstory"
    lead_html = (
        f'<article class="{lead_cls}">{visual}<div class="v820-story-copy">'
        f'<div class="v820-story-tag">{esc(status_label(lead))}</div><div class="v820-story-head">{headline_html(lead)}</div>'
        f'<div class="v820-story-meta">{esc(getattr(lead,"meta",""))}</div></div></article>'
    )
    side_cards = []
    for story in data[1:3]:
        player_element = nint(getattr(story, "player_element", 0))
        image = ""
        if state and player_element:
            impact = state.player(player_element)
            if impact and impact.image_url:
                image = _img_v820(impact.image_url, eager=False)
        dark = " dark" if image else ""
        side_cards.append(
            f'<article class="v820-smallstory{dark}">{image}<div class="v820-small-copy">'
            f'<div class="v820-story-tag">{esc(status_label(story))}</div><div class="v820-small-head">{headline_html(story)}</div>'
            f'<div class="v820-small-meta">{esc(getattr(story,"meta",""))}</div></div></article>'
        )
    if len(side_cards) == 1:
        side_cards.append('<article class="v820-smallstory"><div class="v820-small-copy"><div class="v820-story-tag">LOFTHUS</div><div class="v820-small-head">Neste historie dukker opp når noe faktisk skjer</div><div class="v820-small-meta">Kvalitet foran fyllstoff.</div></div></article>')
    st.markdown(
        f'<div class="v820-news">{lead_html}<div class="v820-news-side">{"".join(side_cards)}</div></div>',
        unsafe_allow_html=True,
    )


def sports_popular_players(players: list[PlayerImpact], me: int = 0, limit: int = 3) -> None:
    top = sorted(players, key=lambda p: (-p.ownership_count, -p.captain_count, p.player))[:limit]
    if not top:
        st.markdown('<div class="v8-empty">Spillerdata lastes.</div>', unsafe_allow_html=True)
        return
    cards = []
    for p in top:
        image = _img_v820(p.image_url, eager=False) if p.image_url else ""
        cap = f" · {p.captain_count} C" if p.captain_count else ""
        cards.append(
            f'<article class="v820-player">{image}<div class="v820-player-copy"><div class="v820-player-club">{esc(p.club)}</div>'
            f'<div class="v820-player-name"><a target="_self" href="{esc(player_href(p.element, me=me))}">{esc(p.player)}</a></div>'
            f'<div class="v820-player-pct">{p.ownership_pct:.0f}%</div><div class="v820-player-meta">{p.ownership_count} eiere{cap}</div></div></article>'
        )
    st.markdown(f'<div class="v820-players">{"".join(cards)}</div>', unsafe_allow_html=True)


def personal_strip(items: list[tuple[Any, str]]) -> None:
    blocks = ''.join(
        f'<div class="v820-personal-item"><div class="v820-personal-value">{esc(value)}</div><div class="v820-personal-label">{esc(label)}</div></div>'
        for value, label in items[:3]
    )
    st.markdown(f'<div class="v820-personal">{blocks}</div>', unsafe_allow_html=True)


def analysis_invite(me: int = 0) -> None:
    url = rival_href(me or 0)
    st.markdown(
        f'<div class="v820-analysis-invite"><div><strong>Vil du dypere?</strong><span>Rivalradar, EO, chips, sammenligning og spilleranalyse ligger ett nivå ned.</span></div>'
        f'<a target="_self" href="{esc(url)}">Åpne analyse →</a></div>',
        unsafe_allow_html=True,
    )
