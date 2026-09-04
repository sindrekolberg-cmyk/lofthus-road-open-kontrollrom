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
  --bg:#f4f2ec;--paper:#fbfaf6;--ink:#0b1420;--muted:#687386;--line:#d8d7d1;
  --navy:#0b1728;--navy2:#12223a;--gold:#b88920;--green:#167a52;--red:#b53b36;
  --blue:#215f9a;--soft:#ebe8df;--radius:10px;--font:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg);color:var(--ink);font-family:var(--font)}
[data-testid="stHeader"]{background:transparent;height:0}.block-container{max-width:1320px;padding:1rem 1.35rem 3.5rem!important}
[data-testid="stSidebar"],#MainMenu,footer{display:none!important}
a{color:inherit}.element-container{min-width:0}

/* shell */
.v8-shell{background:var(--navy);color:#fff;border-radius:14px;padding:1rem 1.15rem .82rem;margin-bottom:.85rem;box-shadow:0 18px 45px rgba(11,23,40,.13)}
.v8-shell-top{display:flex;justify-content:space-between;gap:1rem;align-items:flex-end}.v8-brand{font-size:clamp(1.75rem,3.4vw,3rem);font-weight:950;letter-spacing:-.06em;line-height:.92}.v8-season{font-size:.68rem;color:#b9c4d3;font-weight:850;letter-spacing:.11em;text-transform:uppercase;margin-top:.38rem}
.v8-live-status{font-size:.7rem;color:#d7dfeb;font-weight:780;text-align:right}.v8-live-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#ef5b57;margin-right:.35rem;vertical-align:1px}.v8-shell-nav{display:flex;gap:.2rem;flex-wrap:wrap;margin-top:.82rem;padding-top:.62rem;border-top:1px solid rgba(255,255,255,.13)}
.v8-shell-nav a{color:#c8d1de!important;text-decoration:none!important;font-size:.77rem;font-weight:850;padding:.4rem .62rem;border-radius:7px}.v8-shell-nav a:hover,.v8-shell-nav a.active{background:rgba(255,255,255,.10);color:#fff!important}
.v8-subnav{display:flex;gap:.12rem;flex-wrap:wrap;border-bottom:1px solid var(--line);margin:.1rem 0 .8rem;padding-bottom:.42rem}.v8-subnav a{font-size:.72rem;font-weight:850;color:var(--muted)!important;text-decoration:none!important;padding:.33rem .5rem;border-radius:6px}.v8-subnav a:hover,.v8-subnav a.active{background:#e7e5de;color:var(--ink)!important}

/* type + rhythm */
.v8-page{display:flex;justify-content:space-between;gap:1rem;align-items:flex-end;margin:.75rem 0 .65rem}.v8-page h1{font-size:clamp(1.9rem,3.7vw,3.2rem);line-height:.95;letter-spacing:-.06em;margin:0;font-weight:950}.v8-kicker{font-size:.65rem;color:var(--gold);text-transform:uppercase;letter-spacing:.11em;font-weight:950;margin-bottom:.25rem}.v8-page-meta{font-size:.74rem;color:var(--muted);font-weight:760;text-align:right}
.v8-section{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;border-bottom:1px solid var(--line);padding-bottom:.42rem;margin:1.35rem 0 .45rem}.v8-section strong{font-size:1.12rem;letter-spacing:-.03em}.v8-section span{font-size:.7rem;color:var(--muted);font-weight:760}.v8-muted{color:var(--muted);font-size:.75rem;font-weight:700}.v8-empty{border-top:2px solid var(--ink);border-bottom:1px solid var(--line);padding:.8rem 0;color:var(--muted);font-size:.78rem}

/* status strip */
.v8-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:2px solid var(--ink);border-bottom:1px solid var(--line);margin:.35rem 0 .75rem}.v8-strip-item{padding:.58rem .7rem .56rem;min-width:0}.v8-strip-item+.v8-strip-item{border-left:1px solid var(--line)}.v8-strip-label{font-size:.61rem;text-transform:uppercase;letter-spacing:.085em;color:var(--muted);font-weight:900}.v8-strip-value{font-size:1.04rem;font-weight:950;letter-spacing:-.025em;margin-top:.12rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v8-strip-sub{font-size:.66rem;color:var(--muted);margin-top:.08rem;font-weight:700}

/* live */
.v8-live{border-top:4px solid var(--red);border-bottom:1px solid var(--line);padding:.65rem 0 .72rem;margin:.3rem 0 .9rem}.v8-live-head{display:flex;align-items:center;justify-content:space-between;gap:1rem}.v8-live-title{font-size:.68rem;letter-spacing:.12em;text-transform:uppercase;font-weight:950;color:var(--red)}.v8-scoreline{font-size:.73rem;color:var(--muted);font-weight:780;text-align:right}.v8-live-grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:1.4rem;margin-top:.55rem}.v8-live-player{font-size:clamp(1.7rem,3.6vw,3.1rem);font-weight:950;letter-spacing:-.06em;line-height:.92}.v8-live-player small{display:block;font-size:.72rem;letter-spacing:0;color:var(--muted);font-weight:750;margin-top:.38rem}.v8-impact-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.6rem;padding:.34rem 0;border-bottom:1px solid var(--line);font-size:.76rem}.v8-impact-row:last-child{border-bottom:0}.v8-impact-row strong{font-weight:900}.v8-impact-row span{color:var(--green);font-weight:950}.v8-impact-row.neg span{color:var(--red)}

/* manager menu: native HTML, no iframe, no JS */
details.v8-manager{position:relative;display:inline-block;max-width:100%}details.v8-manager>summary{list-style:none;cursor:pointer;font-weight:900;color:var(--ink);text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}details.v8-manager>summary::-webkit-details-marker{display:none}details.v8-manager>summary:hover{color:var(--blue);text-decoration:underline;text-underline-offset:3px}details.v8-manager[open]>summary{color:var(--blue)}
.v8-menu{position:absolute;z-index:30;left:0;top:calc(100% + 6px);min-width:175px;background:#fff;border:1px solid #cfd3d9;border-radius:9px;box-shadow:0 14px 34px rgba(8,17,31,.18);padding:.32rem}.v8-menu a{display:block;text-decoration:none!important;padding:.45rem .52rem;border-radius:6px;font-size:.72rem;font-weight:820;color:var(--ink)!important}.v8-menu a:hover{background:#eef2f6}

/* Top five is the structural front-page hero */
.v8-top5{border-top:3px solid var(--ink);border-bottom:1px solid var(--line);margin:.15rem 0 .8rem}.v8-top-lead{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:.8rem;align-items:center;padding:.72rem .1rem .68rem}.v8-top-rank{font-size:2rem;color:var(--gold);font-weight:950;letter-spacing:-.06em}.v8-top-name details.v8-manager>summary{font-size:clamp(1.25rem,2.5vw,1.75rem);letter-spacing:-.045em}.v8-top-meta{font-size:.7rem;color:var(--muted);font-weight:740;margin-top:.1rem}.v8-top-points{text-align:right;font-size:1.55rem;font-weight:950;letter-spacing:-.05em}.v8-top-points small{display:block;font-size:.63rem;color:var(--muted);letter-spacing:.02em;margin-top:.08rem}.v8-top-row{display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:.8rem;align-items:center;border-top:1px solid var(--line);padding:.5rem .1rem}.v8-top-row .v8-top-rank{font-size:.9rem;color:var(--muted)}.v8-top-row:nth-child(2) .v8-top-rank,.v8-top-row:nth-child(3) .v8-top-rank{color:var(--gold)}.v8-top-row .v8-top-points{font-size:.98rem}.v8-move{font-size:.67rem;font-weight:900;margin-left:.28rem}.v8-up{color:var(--green)}.v8-down{color:var(--red)}

/* newsroom */
.v8-news{border-top:2px solid var(--ink)}.v8-story{display:grid;grid-template-columns:46px minmax(0,1fr) auto;gap:.7rem;padding:.58rem .05rem;border-bottom:1px solid var(--line);align-items:start}.v8-story-score{font-size:.68rem;color:var(--gold);font-weight:950;padding-top:.08rem}.v8-story-head{font-size:.92rem;font-weight:900;line-height:1.15;letter-spacing:-.02em}.v8-story-meta{font-size:.68rem;color:var(--muted);font-weight:700;margin-top:.14rem}.v8-story-tag{font-size:.57rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:900;padding-top:.13rem}

/* league table */
.v8-league{border-top:3px solid var(--ink);margin-top:.2rem}.v8-league-head,.v8-league-row{display:grid;grid-template-columns:44px minmax(210px,1.7fr) minmax(150px,1.25fr) minmax(115px,.9fr) 64px 82px 64px;gap:.6rem;align-items:center}.v8-league-head{font-size:.6rem;text-transform:uppercase;letter-spacing:.075em;color:var(--muted);font-weight:950;padding:.48rem .06rem;border-bottom:1px solid var(--line)}.v8-league-row{padding:.5rem .06rem;border-bottom:1px solid var(--line);font-size:.76rem;min-height:48px}.v8-league-row:hover{background:rgba(255,255,255,.38)}.v8-rank{color:var(--muted);font-weight:950}.v8-team{font-weight:760}.v8-cap{font-weight:880}.v8-num{text-align:right;font-weight:950;font-variant-numeric:tabular-nums}.v8-manager-sub{display:none;color:var(--muted);font-size:.64rem;font-weight:700;margin-top:.08rem}.v8-chip{display:inline-block;margin-left:.28rem;color:var(--red);font-size:.57rem;font-weight:950;text-transform:uppercase;letter-spacing:.05em}

/* profile */
.v8-profile{border-top:4px solid var(--ink);border-bottom:1px solid var(--line);padding:.7rem 0 .65rem;margin:.25rem 0 .65rem}.v8-profile-grid{display:grid;grid-template-columns:minmax(0,1.4fr) repeat(3,minmax(100px,.55fr));gap:1rem;align-items:end}.v8-profile-name{font-size:clamp(1.8rem,3.8vw,3.2rem);font-weight:950;letter-spacing:-.06em;line-height:.92}.v8-profile-team{font-size:.75rem;color:var(--muted);font-weight:760;margin-top:.28rem}.v8-profile-stat strong{font-size:1.35rem;font-weight:950;display:block;letter-spacing:-.04em}.v8-profile-stat span{font-size:.61rem;color:var(--muted);font-weight:850;text-transform:uppercase;letter-spacing:.06em}.v8-profile-story{font-size:.82rem;font-weight:850;border-bottom:1px solid var(--line);padding:.52rem 0 .62rem;margin-bottom:.5rem}

/* pitch */
.v8-pitch{position:relative;overflow:hidden;background:linear-gradient(180deg,#146140,#0e5236);border-radius:10px;padding:.8rem .55rem .65rem;color:#fff;box-shadow:inset 0 0 0 1px rgba(255,255,255,.14)}.v8-pitch:before{content:"";position:absolute;inset:8% 5%;border:1px solid rgba(255,255,255,.2);border-radius:3px;pointer-events:none}.v8-pitch:after{content:"";position:absolute;left:50%;top:8%;bottom:8%;border-left:1px solid rgba(255,255,255,.17);pointer-events:none}.v8-line{position:relative;z-index:2;display:flex;justify-content:space-evenly;gap:.35rem;min-height:72px;align-items:center}.v8-player{width:min(145px,22%);min-width:84px;background:rgba(251,250,246,.96);color:var(--ink);border-radius:8px;padding:.38rem .3rem;text-align:center;box-shadow:0 7px 15px rgba(0,0,0,.14)}.v8-player-name{font-size:.73rem;font-weight:950;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.v8-player-meta{font-size:.59rem;color:var(--muted);font-weight:760;margin-top:.12rem}.v8-player.live{box-shadow:0 0 0 2px #f0c45c,0 7px 15px rgba(0,0,0,.14)}.v8-player.finished{opacity:.86}.v8-badge{display:inline-block;background:var(--navy);color:#fff;border-radius:99px;padding:.07rem .28rem;font-size:.52rem;font-weight:950;margin-left:.12rem}.v8-badge.tc{background:var(--red)}.v8-badge.vc{background:#6b7280}.v8-bench{margin-top:.45rem;border-top:1px solid rgba(255,255,255,.25);padding-top:.38rem;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.28rem;position:relative;z-index:2}.v8-bench .v8-player{width:auto;min-width:0}

/* form + small stats */
.v8-form{display:flex;gap:.18rem;border-top:2px solid var(--ink);border-bottom:1px solid var(--line);overflow-x:auto}.v8-form-item{min-width:92px;padding:.5rem .55rem}.v8-form-item+.v8-form-item{border-left:1px solid var(--line)}.v8-form-gw{font-size:.6rem;color:var(--muted);font-weight:900;text-transform:uppercase}.v8-form-points{font-size:1.1rem;font-weight:950;margin:.08rem 0}.v8-form-rank{font-size:.61rem;color:var(--muted);font-weight:730}
.v8-mini-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:2px solid var(--ink);border-bottom:1px solid var(--line)}.v8-mini{padding:.52rem .6rem}.v8-mini+.v8-mini{border-left:1px solid var(--line)}.v8-mini strong{display:block;font-size:1.05rem;font-weight:950}.v8-mini span{font-size:.62rem;color:var(--muted);font-weight:780}

/* rival */
.v8-duel{border-top:4px solid var(--ink);border-bottom:1px solid var(--line);display:grid;grid-template-columns:1fr auto 1fr;gap:1rem;align-items:end;padding:.7rem 0}.v8-duel-side:last-child{text-align:right}.v8-duel-name{font-size:1.25rem;font-weight:950;letter-spacing:-.04em}.v8-duel-points{font-size:1.8rem;font-weight:950;letter-spacing:-.06em}.v8-duel-meta{font-size:.67rem;color:var(--muted);font-weight:730}.v8-vs{font-size:.62rem;color:var(--muted);font-weight:950;text-transform:uppercase;letter-spacing:.1em;padding-bottom:.45rem}.v8-cheer{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}.v8-cheer-col{border-top:2px solid var(--ink)}.v8-cheer-title{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;font-weight:950;padding:.45rem 0}.v8-edge{display:flex;justify-content:space-between;gap:.6rem;border-top:1px solid var(--line);padding:.38rem 0;font-size:.74rem}.v8-edge strong{font-weight:900}.v8-edge span{font-weight:950;color:var(--green)}.v8-cheer-col.bad .v8-edge span{color:var(--red)}

/* generic compact table / hall */
.v8-table{width:100%;border-collapse:collapse;border-top:2px solid var(--ink);font-size:.74rem}.v8-table th{text-align:left;color:var(--muted);font-size:.58rem;text-transform:uppercase;letter-spacing:.07em;padding:.4rem .35rem;border-bottom:1px solid var(--line)}.v8-table td{padding:.45rem .35rem;border-bottom:1px solid var(--line);font-weight:720}.v8-table td.num,.v8-table th.num{text-align:right;font-weight:900}.v8-hof-name{font-weight:950}.v8-medal{font-weight:950;color:var(--gold)}

/* native streamlit controls: quieter */
.stButton>button,.stDownloadButton>button{border-radius:8px!important;box-shadow:none!important;font-weight:820!important}.stSelectbox label,.stMultiSelect label{font-size:.7rem!important;font-weight:850!important;color:var(--muted)!important}.stSelectbox,.stMultiSelect{margin-bottom:.25rem}div[data-testid="stExpander"]{border:1px solid var(--line)!important;border-radius:9px!important;background:rgba(255,255,255,.25)!important}

@media(max-width:760px){
 .block-container{padding:.65rem .7rem 2.5rem!important}.v8-shell{border-radius:10px;padding:.85rem .8rem .68rem}.v8-shell-top{align-items:flex-start}.v8-live-status{display:none}.v8-shell-nav{gap:.06rem}.v8-shell-nav a{font-size:.7rem;padding:.36rem .43rem}.v8-page{align-items:flex-start}.v8-page-meta{display:none}
 .v8-strip{grid-template-columns:1fr}.v8-strip-item+.v8-strip-item{border-left:0;border-top:1px solid var(--line)}.v8-live-grid{grid-template-columns:1fr;gap:.6rem}.v8-top-lead,.v8-top-row{grid-template-columns:38px minmax(0,1fr) auto;gap:.45rem}.v8-top-rank{font-size:1.45rem}.v8-top-points{font-size:1.15rem}.v8-story{grid-template-columns:34px minmax(0,1fr)}.v8-story-tag{display:none}
 .v8-league-head{display:none}.v8-league-row{grid-template-columns:34px minmax(0,1fr) auto;gap:.45rem;padding:.55rem .05rem}.v8-league-row>.v8-team,.v8-league-row>.v8-cap,.v8-league-row>.v8-gw,.v8-league-row>.v8-move-cell{display:none}.v8-league-row>.v8-total{grid-column:3}.v8-manager-sub{display:block}.v8-league-row details.v8-manager>summary{font-size:.83rem}.v8-menu{position:fixed;left:1rem;right:1rem;top:auto;bottom:1rem;min-width:0;max-width:none}
 .v8-profile-grid{grid-template-columns:1fr 1fr}.v8-profile-main{grid-column:1/-1}.v8-profile-stat:nth-child(4){display:none}.v8-pitch{padding:.65rem .22rem}.v8-line{gap:.15rem;min-height:75px}.v8-player{min-width:0;width:23%;padding:.34rem .15rem}.v8-player-name{font-size:.63rem}.v8-player-meta{font-size:.52rem}.v8-bench{grid-template-columns:repeat(2,minmax(0,1fr))}.v8-duel{grid-template-columns:1fr 32px 1fr;gap:.45rem}.v8-duel-name{font-size:.95rem}.v8-duel-points{font-size:1.35rem}.v8-cheer{grid-template-columns:1fr}.v8-mini-grid{grid-template-columns:1fr}.v8-mini+.v8-mini{border-left:0;border-top:1px solid var(--line)}
 .v8-table-wrap{overflow-x:auto}.v8-table{min-width:560px}
}
</style>
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def install_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _manager_menu(entry: int, name: str, team: str, me: int = 0, captain: str = "") -> str:
    links = [
        ("Se laget", manager_href(entry, me=me)),
        ("Sammenlign", compare_href([entry] if not me or me == entry else [me, entry], me=me)),
        ("Rivalradar", rival_href(me or entry, 0 if me == entry else entry)),
        ("Historikk", manager_href(entry, me=me) + "#historikk"),
    ]
    menu = "".join(f'<a href="{esc(url)}">{esc(label)}</a>' for label, url in links)
    return (
        f'<details class="v8-manager"><summary>{esc(name)}</summary>'
        f'<div class="v8-menu"><div style="padding:.34rem .52rem .25rem;font-size:.62rem;color:#687386;font-weight:760">{esc(team)}'
        + (f" · {esc(captain)}" if captain else "")
        + f"</div>{menu}</div></details>"
    )


def app_header(league_name: str, season: str, page: str, me: int = 0, status: str = "", updated: str = "") -> None:
    nav = [
        ("Forside", href("Forside", me=me)),
        ("Ligaen", league_href("Tabell", me=me)),
        ("Rivalradar", rival_href(me or 0)),
        ("Hall of Fame", href("Hall of Fame", me=me)),
    ]
    active_page = "Ligaen" if page in {"Manager", "Spiller"} else page
    nav_html = "".join(f'<a class="{"active" if label == active_page else ""}" href="{esc(url)}">{esc(label)}</a>' for label, url in nav)
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


def live_centre(state: LiveState, beneficiary_rows: list[dict[str, Any]], scoreline: str = "", me: int = 0) -> None:
    live_players = [p for p in state.player_impacts if p.fixture_status == "live" and (p.event_points or p.captain_count or p.triple_captain_count)]
    p = live_players[0] if live_players else None
    if p:
        cap = f" · {p.captain_count} kaptein" if p.captain_count == 1 else f" · {p.captain_count} kapteiner" if p.captain_count else ""
        lead = f'<a href="{esc(player_href(p.element, me=me))}" style="color:inherit;text-decoration:none">{esc(p.player)}</a><small>{p.event_points} poeng · {p.ownership_count} eiere{esc(cap)}</small>'
    else:
        lead = f'GW{state.event_id}<small>Ingen Lofthus-spiller har gjort et stort utslag ennå</small>'
    impacts = "".join(
        f'<div class="v8-impact-row {"neg" if nfloat(r.get("swing")) < 0 else ""}"><strong><a href="{esc(manager_href(nint(r.get("entry")), me=me))}" style="text-decoration:none">{esc(r.get("manager"))}</a></strong><span>{nfloat(r.get("swing")):+.1f}</span></div>'
        for r in beneficiary_rows[:5]
    ) or '<div class="v8-muted">Lagpåvirkning kommer når picks er klare.</div>'
    st.markdown(
        f'<div class="v8-live"><div class="v8-live-head"><div class="v8-live-title"><span class="v8-live-dot"></span>LIVE · GW{state.event_id}</div><div class="v8-scoreline">{esc(scoreline)}</div></div><div class="v8-live-grid"><div class="v8-live-player">{lead}</div><div>{impacts}</div></div></div>',
        unsafe_allow_html=True,
    )


def top_five(rows: list[ManagerLiveState], me: int = 0, live: bool = False) -> None:
    if not rows:
        st.markdown('<div class="v8-empty">Tabellen lastes inn.</div>', unsafe_allow_html=True)
        return
    def row_html(m: ManagerLiveState, lead: bool = False) -> str:
        move = m.live_rank_change
        move_html = f'<span class="v8-move {"v8-up" if move>0 else "v8-down" if move<0 else ""}">{"↑"+str(move) if move>0 else "↓"+str(abs(move)) if move<0 else "–"}</span>'
        cap = m.captain if m.captain != "–" else ""
        manager = _manager_menu(m.entry, m.manager, m.team, me=me, captain=cap)
        cls = "v8-top-lead" if lead else "v8-top-row"
        return f'<div class="{cls}"><div class="v8-top-rank">{m.live_rank}</div><div class="v8-top-name">{manager}<div class="v8-top-meta">{esc(m.team)}' + (f' · {esc(cap)}' if cap else '') + f' {move_html}</div></div><div class="v8-top-points">{m.live_total_points}<small>{m.live_gw_points} GW{" · live" if live else ""}</small></div></div>'
    html_rows = row_html(rows[0], True) + "".join(row_html(m, False) for m in rows[1:5])
    st.markdown(f'<div class="v8-top5">{html_rows}</div>', unsafe_allow_html=True)


def story_list(stories: Iterable[Any], me: int = 0) -> None:
    items = []
    for story in stories:
        manager_entry = nint(getattr(story, "manager_entry", 0))
        player_element = nint(getattr(story, "player_element", 0))
        headline = esc(getattr(story, "headline", ""))
        if manager_entry:
            headline = f'<a href="{esc(manager_href(manager_entry, me=me))}" style="text-decoration:none">{headline}</a>'
        elif player_element:
            headline = f'<a href="{esc(player_href(player_element, me=me))}" style="text-decoration:none">{headline}</a>'
        items.append(
            f'<div class="v8-story"><div class="v8-story-score">{nint(getattr(story,"importance",0))}</div><div><div class="v8-story-head">{headline}</div><div class="v8-story-meta">{esc(getattr(story,"meta",""))}</div></div><div class="v8-story-tag">{esc(getattr(story,"status",""))}</div></div>'
        )
    st.markdown(f'<div class="v8-news">{"".join(items)}</div>' if items else '<div class="v8-empty">Ingen sak slår gjennom nyhetsterskelen akkurat nå.</div>', unsafe_allow_html=True)


def popular_players(players: list[PlayerImpact], me: int = 0, limit: int = 3) -> None:
    top = sorted(players, key=lambda p: (-p.ownership_count, -p.captain_count, p.player))[:limit]
    if not top:
        st.markdown('<div class="v8-empty">Eierskap lastes inn.</div>', unsafe_allow_html=True)
        return
    rows = "".join(
        f'<tr><td><a href="{esc(player_href(p.element, me=me))}" style="text-decoration:none;font-weight:900">{esc(p.player)}</a></td><td class="num">{p.ownership_count}</td><td class="num">{p.ownership_pct:.0f} %</td></tr>' for p in top
    )
    st.markdown(f'<table class="v8-table"><thead><tr><th>Spiller</th><th class="num">Eiere</th><th class="num">LRO</th></tr></thead><tbody>{rows}</tbody></table>', unsafe_allow_html=True)


def league_table(rows: list[ManagerLiveState], me: int = 0, live: bool = False) -> None:
    head = '<div class="v8-league-head"><div>#</div><div>Manager</div><div>Lag</div><div>Kaptein</div><div style="text-align:right">GW</div><div style="text-align:right">Poeng</div><div style="text-align:right">+/-</div></div>'
    body = []
    for m in rows:
        move = m.live_rank_change
        move_text = f"↑{move}" if move > 0 else f"↓{abs(move)}" if move < 0 else "–"
        move_cls = "v8-up" if move > 0 else "v8-down" if move < 0 else ""
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
        points = nint(r.get("event_points")) * max(0, nint(r.get("multiplier")))
        raw = nint(r.get("event_points"))
        meta = f"{raw} p" + (f" ×{nint(r.get('multiplier'))}" if nint(r.get("multiplier")) > 1 else "")
        return f'<div class="v8-player {esc(status)}"><div class="v8-player-name"><a href="{esc(player_href(nint(r.get("element")), me=me))}" style="color:inherit;text-decoration:none">{esc(r.get("player"))}</a>{badge}</div><div class="v8-player-meta">{esc(meta)} · {esc(status.replace("not_started","ikke startet").replace("finished","ferdig").replace("live","live"))}</div></div>'
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
    def rows(items: Iterable[Any], bad: bool = False) -> str:
        data = list(items)
        if not data:
            return '<div class="v8-muted" style="padding:.45rem 0">Ingen klare utslag akkurat nå.</div>'
        return "".join(f'<div class="v8-edge"><strong>{esc(x.player)}</strong><span>{x.multiplier_edge:+d}×</span></div>' for x in data[:6])
    st.markdown(f'<div class="v8-cheer"><div class="v8-cheer-col"><div class="v8-cheer-title">Heia på</div>{rows(cheer)}</div><div class="v8-cheer-col bad"><div class="v8-cheer-title">Håp på blank</div>{rows(blank,True)}</div></div>', unsafe_allow_html=True)


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
        st.caption("Live-lagdata lastes i bakgrunnen.")
        return
    loaded = nint(state.data_quality.get("loaded_managers"))
    total = nint(state.data_quality.get("league_size"))
    if total and loaded < total:
        st.caption(f"Lagdata: {loaded}/{total}. Tabellen vises mens resten lastes.")

def subnav(items: list[tuple[str, str]], active: str) -> None:
    links = ''.join(
        f'<a class="{"active" if label == active else ""}" href="{esc(url)}">{esc(label)}</a>'
        for label, url in items
    )
    st.markdown(f'<div class="v8-subnav">{links}</div>', unsafe_allow_html=True)
