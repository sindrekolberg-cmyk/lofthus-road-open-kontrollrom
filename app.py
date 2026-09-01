from __future__ import annotations

from pathlib import Path
import time
from typing import Any

import pandas as pd
import streamlit as st

from lro_analysis import (
    build_ownership,
    canonical_managers,
    manager_form_from_histories,
    manager_squad,
    nfloat,
    nint,
    rival_analysis,
    round_movements,
    stories,
)
from lro_fpl import (
    DEFAULT_LEAGUE_ID,
    FPLClient,
    current_event_id,
    current_month_phase,
    finished_event_ids,
    month_phases,
    player_catalog,
    season_label,
    short_season_label,
)
from lro_history import HistoryStore, normalize_text
from lro_odds import compare_group_odds, decimal_odds_from_pct, simulate_group
import lro_ui as ui

APP_VERSION = "lofthus-road-open-v400-rebuild"
DATA_DIR = Path(__file__).resolve().parent / "data"

st.set_page_config(page_title="Lofthus Road Open", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")
ui.install_styles()


@st.cache_resource
def get_client() -> FPLClient:
    return FPLClient()


@st.cache_resource
def get_history_store() -> HistoryStore:
    return HistoryStore(DATA_DIR)


client = get_client()
history_store = get_history_store()


def fmt_price(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return "–"
        price = float(value)
        if price <= 0 or price > 25:
            return "–"
        return f"£{price:.1f}"
    except Exception:
        return "–"


def fmt_pct(value: Any) -> str:
    return f"{max(0.0, min(100.0, nfloat(value))):.0f}%"


def manager_map(managers: list[dict]) -> dict[int, dict]:
    return {nint(m.get("entry")): m for m in managers if nint(m.get("entry"))}


def manager_name(m: dict) -> str:
    return history_store.canonical(str(m.get("player_name") or "Ukjent manager"))


def manager_options(managers: list[dict]) -> list[tuple[int, str]]:
    out = [(nint(m.get("entry")), manager_name(m)) for m in managers if nint(m.get("entry"))]
    return sorted(out, key=lambda x: normalize_text(x[1]))


def selected_ownership(managers: list[dict], entries: list[int] | None = None) -> dict:
    bootstrap = client.bootstrap()
    event = current_event_id(bootstrap)
    key_entries = tuple(sorted(int(x) for x in (entries or [nint(m.get("entry")) for m in managers]) if int(x) > 0))
    cache_key = f"v400_ownership_{event}_{','.join(map(str, key_entries))}"
    stamp_key = f"{cache_key}_built_at"
    # Picks themselves are cached in FPLClient, but live event points move during a
    # match. Rebuild the derived ownership object roughly once a minute so live
    # points do not freeze for an entire browser session.
    stale = time.time() - float(st.session_state.get(stamp_key, 0.0)) > 75
    if cache_key not in st.session_state or stale:
        st.session_state[cache_key] = build_ownership(
            client,
            managers,
            history_store,
            event_id=event,
            only_entries=list(key_entries),
            max_workers=8 if len(key_entries) > 8 else 6,
        )
        st.session_state[stamp_key] = time.time()
    return st.session_state[cache_key]


def histories_for(entries: list[int]) -> tuple[dict[int, dict], dict[int, str]]:
    ids = tuple(sorted(set(int(x) for x in entries if int(x) > 0)))
    cache_key = f"v400_histories_{','.join(map(str, ids))}"
    if cache_key not in st.session_state:
        st.session_state[cache_key] = client.histories_many(ids, max_workers=8)
    return st.session_state[cache_key]


def auto_monthly_rows(bootstrap: dict) -> list[dict]:
    season = season_label(bootstrap)
    max_finished = max(finished_event_ids(bootstrap) or [0])
    rows = []
    for phase in month_phases(bootstrap):
        if phase["stop_event"] <= 0 or phase["stop_event"] > max_finished:
            continue
        try:
            standings = client.league_phase_standings(DEFAULT_LEAGUE_ID, phase["id"])
        except Exception:
            continue
        if not standings:
            continue
        standings = sorted(
            standings,
            key=lambda r: (nint(r.get("rank"), 10**9), -nint(r.get("total")), normalize_text(str(r.get("player_name") or ""))),
        )
        for place, row in enumerate(standings[:3], start=1):
            rows.append({
                "season": season,
                "month": phase["name"],
                "place": place,
                "manager": history_store.canonical(str(row.get("player_name") or "Ukjent manager")),
                "status": "Automatisk",
                "source": f"FPL phase {phase['id']}",
            })
    return rows


def current_month_table(managers: list[dict], bootstrap: dict) -> tuple[dict | None, pd.DataFrame]:
    phase = current_month_phase(bootstrap)
    if not phase:
        return None, pd.DataFrame()
    try:
        standings = client.league_phase_standings(DEFAULT_LEAGUE_ID, phase["id"])
    except Exception:
        standings = []
    rows = []
    for r in standings:
        rows.append({
            "rank": nint(r.get("rank")),
            "entry": nint(r.get("entry")),
            "manager": history_store.canonical(str(r.get("player_name") or "Ukjent manager")),
            "team": str(r.get("entry_name") or ""),
            "points": nint(r.get("total")),
        })
    df = pd.DataFrame(rows)
    # On the first day(s) of a month FPL can still expose the old/current GW. A zero
    # month should be visibly live, but not invent a sporting order.
    if df.empty or ("points" in df.columns and int(pd.to_numeric(df["points"], errors="coerce").fillna(0).sum()) == 0):
        alpha = sorted(
            [{"entry": nint(m.get("entry")), "manager": manager_name(m), "team": str(m.get("entry_name") or ""), "points": 0} for m in managers],
            key=lambda x: normalize_text(x["manager"]),
        )
        df = pd.DataFrame([{**r, "rank": i + 1} for i, r in enumerate(alpha)])
    else:
        df = df.sort_values(["rank", "manager"]).reset_index(drop=True)
    return phase, df


def current_month_points_map(managers: list[dict], bootstrap: dict) -> dict[int, float]:
    _, df = current_month_table(managers, bootstrap)
    if df.empty:
        return {}
    return {nint(r.get("entry")): nfloat(r.get("points")) for r in df.to_dict("records") if nint(r.get("entry"))}


def data_quality_note(ownership: dict) -> None:
    loaded = nint(ownership.get("loaded_managers"))
    total = nint(ownership.get("league_size"))
    if total and loaded < total:
        st.caption(f"Lagdata tilgjengelig for {loaded} av {total}.")


def active_fixtures(bootstrap: dict) -> tuple[list[dict], dict[int, str]]:
    event = current_event_id(bootstrap)
    if not event:
        return [], {}
    fixtures = client.fixtures(event)
    teams = {nint(t.get("id")): str(t.get("short_name") or t.get("name") or "?") for t in bootstrap.get("teams", []) or []}
    active = [f for f in fixtures if f.get("started") and not f.get("finished")]
    return active, teams


def fixture_score(f: dict, teams: dict[int, str]) -> str:
    home = teams.get(nint(f.get("team_h")), "?")
    away = teams.get(nint(f.get("team_a")), "?")
    hs = f.get("team_h_score")
    aas = f.get("team_a_score")
    minute = nint(f.get("minutes"))
    base = f"{home} {nint(hs)}–{nint(aas)} {away}"
    return f"{base} · {minute}'" if minute else base


def render_live(managers: list[dict], bootstrap: dict, compact: bool = False) -> bool:
    active, teams = active_fixtures(bootstrap)
    if not active:
        return False
    event = current_event_id(bootstrap)
    ui.live_panel("  |  ".join(fixture_score(f, teams) for f in active), f"GW{event}")
    ownership = selected_ownership(managers)
    players = ownership.get("players", pd.DataFrame())
    if players.empty:
        return True
    active_teams = {nint(f.get(k)) for f in active for k in ("team_h", "team_a")}
    live = players[players["team_id"].isin(active_teams)].copy()
    if live.empty:
        return True
    live["importance"] = (
        pd.to_numeric(live["triple_captain_count"], errors="coerce").fillna(0) * 100
        + pd.to_numeric(live["captain_count"], errors="coerce").fillna(0) * 8
        + pd.to_numeric(live["ownership_count"], errors="coerce").fillna(0)
        + pd.to_numeric(live["event_points"], errors="coerce").fillna(0) * 2
    )
    live = live.sort_values("importance", ascending=False).head(5 if compact else 10)
    ui.rows([
        {
            "rank": "TC" if nint(r.get("triple_captain_count")) else "C" if nint(r.get("captain_count")) else "",
            "who": r.get("player"),
            "meta": f"{nint(r.get('ownership_count'))}/{nint(ownership.get('loaded_managers'))} eiere"
            + (f" · {nint(r.get('captain_count'))} C" if nint(r.get("captain_count")) else "")
            + (f" · {nint(r.get('triple_captain_count'))} TC" if nint(r.get("triple_captain_count")) else ""),
            "num": f"{nint(r.get('event_points'))} p",
        }
        for r in live.to_dict("records")
    ])
    for r in live.to_dict("records"):
        if nint(r.get("triple_captain_count")):
            names = ", ".join(r.get("triple_captains") or [])
            ui.alert("Triple Captain", f"{names}: {r.get('player')}")
    data_quality_note(ownership)
    return True


def render_month(managers: list[dict], bootstrap: dict, top: int = 5) -> None:
    phase, df = current_month_table(managers, bootstrap)
    if phase is None:
        st.caption("Månedstabellen er ikke tilgjengelig akkurat nå.")
        return
    ui.section(f"{phase['name']} · live")
    zero = df.empty or int(pd.to_numeric(df.get("points", 0), errors="coerce").fillna(0).sum()) == 0
    ui.rows([
        {
            "rank": nint(r.get("rank")),
            "rank_class": "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else "",
            "who": r.get("manager"),
            "meta": r.get("team"),
            "num": f"{nint(r.get('points'))} p",
        }
        for i, r in enumerate(df.head(top).to_dict("records"))
    ])
    if zero:
        st.caption(f"Ingen {phase['name'].casefold()}poeng ennå.")


def render_home(managers: list[dict], bootstrap: dict) -> None:
    live = render_live(managers, bootstrap, compact=True)
    move = round_movements(managers, history_store)
    if not live:
        leader = move.get("leader", {})
        winner = move.get("gw_winner", {})
        phase, month_df = current_month_table(managers, bootstrap)
        month_leader = month_df.iloc[0].to_dict() if not month_df.empty else {}
        ui.stat_strip([
            (leader.get("manager", "–"), "Ligaleder"),
            (f"{winner.get('manager', '–')} · {winner.get('gw', 0)} p", "Siste runde"),
            (month_leader.get("manager", "–"), f"{phase['name']}" if phase else "Måneden"),
        ])

    ui.section("Snakkiser")
    ownership = None
    if live:
        ownership = selected_ownership(managers)
    story_items = stories(managers, ownership, history_store)
    if not story_items:
        story_items = ["Ligaen er i gang. Flere snakkiser kommer når rundene begynner å sette seg."]
    ui.rows([{"rank": i + 1, "who": text, "meta": "", "num": ""} for i, text in enumerate(story_items[:4])])

    ui.section("Topp 5")
    top = sorted(managers, key=lambda m: (nint(m.get("rank"), 10**9), -nint(m.get("total"))))[:5]
    ui.rows([
        {
            "rank": nint(m.get("rank")),
            "rank_class": "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else "",
            "who": manager_name(m),
            "meta": str(m.get("entry_name") or ""),
            "num": f"{nint(m.get('total'))} p",
        }
        for i, m in enumerate(top)
    ])
    render_month(managers, bootstrap, top=3)


def render_captains(ownership: dict) -> None:
    players = ownership.get("players", pd.DataFrame())
    if players.empty:
        st.caption("Kapteinsdata er ikke tilgjengelig akkurat nå.")
        return
    caps = players[players["captain_count"] > 0].sort_values(["captain_count", "player"], ascending=[False, True])
    cap_items = []
    for i, r in enumerate(caps.head(10).to_dict("records")):
        names = list(r.get("captains") or [])
        shown = ", ".join(names[:4])
        if len(names) > 4:
            shown += f" +{len(names) - 4}"
        cap_items.append({
            "rank": i + 1,
            "who": r.get("player"),
            "meta": shown,
            "num": f"{nint(r.get('captain_count'))} C" + (f" · {nint(r.get('triple_captain_count'))} TC" if nint(r.get("triple_captain_count")) else ""),
        })
    ui.rows(cap_items)
    triples = caps[caps["triple_captain_count"] > 0]
    for r in triples.to_dict("records"):
        ui.alert("Triple Captain", f"{', '.join(r.get('triple_captains') or [])}: {r.get('player')}")


def render_popular(ownership: dict) -> None:
    players = ownership.get("players", pd.DataFrame())
    if players.empty:
        st.caption("Eierskapsdata mangler.")
        return
    total = nint(ownership.get("loaded_managers"))
    ui.rows([
        {
            "rank": i + 1,
            "who": r.get("player"),
            "meta": f"{r.get('club')} · {r.get('position')} · {fmt_price(r.get('current_price'))}",
            "num": f"{nint(r.get('ownership_count'))}/{total} · {fmt_pct(r.get('ownership_pct'))}",
        }
        for i, r in enumerate(players.sort_values("ownership_count", ascending=False).head(10).to_dict("records"))
    ])


def render_player_profile(player: dict, ownership: dict, bootstrap: dict) -> None:
    total = nint(ownership.get("loaded_managers"))
    ui.profile_header(str(player.get("player") or ""), f"{player.get('club')} · {player.get('position')} · {fmt_price(player.get('current_price'))}")
    ui.stat_strip([
        (f"{nint(player.get('ownership_count'))}/{total}", "Eier"),
        (nint(player.get("captain_count")), "Kapteiner"),
        (nint(player.get("triple_captain_count")), "Triple Captain"),
        (nint(player.get("bench_count")), "På benken"),
        (f"{nint(player.get('event_points'))} p", "Denne GW"),
    ])
    captains = player.get("captains") or []
    triples = set(player.get("triple_captains") or [])
    if captains:
        ui.section("Kaptein hos")
        ui.rows([
            {"rank": "TC" if name in triples else "C", "who": name, "meta": "Triple Captain" if name in triples else "Kaptein", "num": ""}
            for name in captains[:8]
        ])
        if len(captains) > 8:
            with st.expander(f"Se alle {len(captains)} kapteiner"):
                st.write(" · ".join(captains))
    owners = player.get("owners") or []
    if owners:
        with st.expander(f"Se alle {len(owners)} eiere"):
            st.write(" · ".join(owners))
    benched = player.get("benched_by") or []
    if benched:
        ui.callout("På benken", ", ".join(benched))
    regular = nint(player.get("ownership_count")) - nint(player.get("captain_count"))
    without = max(0, total - nint(player.get("ownership_count")))
    sentence = f"{nint(player.get('triple_captain_count'))} får trippel, {max(0, nint(player.get('captain_count')) - nint(player.get('triple_captain_count')))} får dobbelt, {max(0, regular)} får vanlige poeng og {without} har ham ikke."
    ui.callout(f"Hvis {player.get('player')} leverer", sentence, "green")


def render_player_search(ownership: dict, key: str) -> None:
    players = ownership.get("players", pd.DataFrame())
    if players.empty:
        return
    query = st.text_input("Søk etter spiller", placeholder="Skriv et spillernavn …", key=key)
    if not query.strip():
        return
    norm = normalize_text(query)
    candidates = players[
        players.apply(lambda r: norm in normalize_text(f"{r.get('player','')} {r.get('full_name','')} {r.get('club','')}"), axis=1)
    ].copy()
    if candidates.empty:
        st.caption("Fant ingen spiller.")
        return
    candidates = candidates.sort_values(["ownership_count", "player"], ascending=[False, True]).head(8)
    if len(candidates) > 1:
        choices = candidates["element"].astype(int).tolist()
        label_map = {nint(r["element"]): f"{r['player']} · {r['club']}" for r in candidates.to_dict("records")}
        element = st.selectbox("Treff", choices, format_func=lambda x: label_map.get(int(x), str(x)), key=f"{key}_choice")
        row = candidates[candidates["element"] == int(element)].iloc[0].to_dict()
    else:
        row = candidates.iloc[0].to_dict()
    render_player_profile(row, ownership, client.bootstrap())


def render_season(managers: list[dict], bootstrap: dict) -> None:
    ui.page_title("Sesong", "Live, kapteiner og spillerne som faktisk flytter ligaen.")
    render_live(managers, bootstrap)
    with st.spinner("Henter Lofthus-lag …"):
        ownership = selected_ownership(managers)
    data_quality_note(ownership)
    ui.section("Hvem har cappet hvem?")
    render_captains(ownership)
    c1, c2 = st.columns([0.9, 1.1], gap="large")
    with c1:
        ui.section("Mest eide")
        render_popular(ownership)
    with c2:
        ui.section("Finn spiller")
        render_player_search(ownership, "v400_player_search")
    ui.section("Differensialer")
    players = ownership.get("players", pd.DataFrame())
    if not players.empty:
        current = current_event_id(bootstrap) or 1
        # Small ownership + actual output/minutes: avoids a cemetery of bench fodder.
        dif = players[(players["ownership_count"].between(1, 6)) & ((players["season_points"] >= max(6, current * 3)) | (players["event_points"] >= 4))]
        dif = dif.sort_values(["event_points", "season_points", "ownership_count"], ascending=[False, False, True]).head(8)
        ui.rows([{"rank": i + 1, "who": r.get("player"), "meta": f"{r.get('club')} · {r.get('position')}", "num": f"{nint(r.get('ownership_count'))} eiere"} for i, r in enumerate(dif.to_dict("records"))])
    render_month(managers, bootstrap, top=5)
    ui.section("Rundebevegelser")
    mv = round_movements(managers, history_store)
    bits = []
    if mv.get("gw_winner"):
        r = mv["gw_winner"]; bits.append({"rank": "GW", "who": r["manager"], "meta": "Rundens beste", "num": f"{r['gw']} p"})
    if mv.get("best_climber"):
        r = mv["best_climber"]; bits.append({"rank": "↑", "who": r["manager"], "meta": "Største klatring", "num": f"+{r['move']}" if r["move"] >= 0 else str(r["move"]), "num_class": "up"})
    if mv.get("biggest_fall"):
        r = mv["biggest_fall"]; bits.append({"rank": "↓", "who": r["manager"], "meta": "Største fall", "num": str(r["move"]), "num_class": "down"})
    ui.rows(bits)
    with st.expander("Sesongutvikling"):
        st.caption("Velg manager under Ligaen for detaljert form. Full 63-linjers graf er bevisst ikke standardvisningen.")


def render_league_table(managers: list[dict]) -> None:
    data = []
    for m in sorted(managers, key=lambda x: (nint(x.get("rank"), 10**9), -nint(x.get("total")))):
        rank = nint(m.get("rank"))
        last = nint(m.get("last_rank"), rank)
        move = last - rank
        data.append({
            "rank": rank,
            "manager": manager_name(m),
            "team": str(m.get("entry_name") or ""),
            "gw": nint(m.get("event_total")),
            "points": nint(m.get("total")),
            "move": f"↑{move}" if move > 0 else f"↓{abs(move)}" if move < 0 else "–",
        })
    ui.html_table(
        [("rank", "#"), ("manager", "Manager"), ("team", "Lag"), ("gw", "GW"), ("points", "Poeng"), ("move", "+/−")],
        data,
        right={"rank", "gw", "points", "move"},
        hide_mobile={"team", "gw", "move"},
    )


def render_form(managers: list[dict], entry: int) -> None:
    with st.spinner("Henter form …"):
        histories, errors = histories_for([nint(m.get("entry")) for m in managers])
    form = manager_form_from_histories(managers, histories, int(entry), 5)
    if form.empty:
        own = histories.get(int(entry), {}).get("current", []) or []
        if own:
            own = own[-5:]
            ui.rows([{"rank": f"GW{nint(r.get('event'))}", "who": f"{nint(r.get('points'))} poeng", "meta": f"FPL-rank {nint(r.get('overall_rank')):,}".replace(",", " "), "num": ""} for r in own])
        else:
            st.caption("Formdata er ikke tilgjengelig.")
        return
    ui.rows([
        {
            "rank": f"GW{nint(r.get('event'))}",
            "who": f"{nint(r.get('points'))} poeng",
            "meta": f"{nint(r.get('round_rank'))}. beste i Lofthus",
            "num": f"{nint(r.get('league_rank'))}. sammenlagt",
        }
        for r in form.to_dict("records")
    ])


def render_merits(name: str, auto_rows: list[dict]) -> None:
    m = history_store.merits_for(name, auto_rows)
    if not m:
        st.caption("Ingen registrerte meritter.")
        return
    best = history_store.best_finish(name)
    ui.merits([
        (nint(m.get("league_gold")), "ligagull"),
        (nint(m.get("league_silver")), "seriesølv"),
        (nint(m.get("league_bronze")), "seriebronse"),
        (nint(m.get("cup_gold")), "cupgull"),
        (nint(m.get("monthly_gold")), "månedsseire"),
        (nint(m.get("monthly_podiums")), "månedspaller"),
        (f"{best}." if best else "–", "beste sluttplass"),
    ])


def render_squad(entry: int, managers: list[dict], bootstrap: dict) -> tuple[dict, pd.DataFrame]:
    ownership = selected_ownership(managers, [entry])
    squad = manager_squad(ownership, entry)
    if squad.empty:
        st.caption("Troppen kunne ikke lastes.")
        return ownership, squad
    ui.section("Troppen")
    starters = squad[~squad["on_bench"]]
    bench = squad[squad["on_bench"]]
    def meta(r: dict) -> str:
        bits = [str(r.get("position") or "Ukjent"), fmt_price(r.get("current_price"))]
        if r.get("is_captain"):
            bits.append("TC" if r.get("is_triple_captain") else "C")
        elif r.get("is_vice_captain"):
            bits.append("VC")
        return " · ".join(bits)
    ui.rows([{"rank": "", "who": r.get("player"), "meta": meta(r), "num": f"{nint(r.get('event_points'))} p"} for r in starters.to_dict("records")])
    if not bench.empty:
        st.caption("Benk")
        ui.rows([{"rank": "", "who": r.get("player"), "meta": meta(r) + " · Benk", "num": f"{nint(r.get('event_points'))} p"} for r in bench.to_dict("records")])
    return ownership, squad


def render_manager_profile(entry: int, managers: list[dict], bootstrap: dict, auto_rows: list[dict]) -> None:
    mmap = manager_map(managers)
    m = mmap.get(int(entry))
    if not m:
        return
    name = manager_name(m)
    phase, month_df = current_month_table(managers, bootstrap)
    month_row = month_df[month_df["entry"] == int(entry)] if not month_df.empty else pd.DataFrame()
    month_rank = nint(month_row.iloc[0].get("rank")) if not month_row.empty else 0
    ui.profile_header(name, str(m.get("entry_name") or ""))
    ui.stat_strip([
        (f"{nint(m.get('rank'))}.", "Plass"),
        (nint(m.get("total")), "Poeng"),
        (nint(m.get("event_total")), "Denne GW"),
        (f"{month_rank}." if month_rank else "–", phase["name"] if phase else "Måneden"),
    ])
    ui.section("Form")
    render_form(managers, entry)
    ui.section("Meritter")
    render_merits(name, auto_rows)
    ownership, squad = render_squad(entry, managers, bootstrap)
    if not squad.empty:
        event_row = ownership.get("manager_events", pd.DataFrame())
        if not event_row.empty:
            e = event_row.iloc[0]
            chip = str(e.get("active_chip") or "")
            ui.stat_strip([
                (fmt_price(e.get("team_value")), "Lagverdi"),
                (fmt_price(e.get("bank")), "I banken"),
                (chip or "Ingen", "Chip denne GW"),
                (nint(e.get("points_on_bench")), "Benkepoeng"),
            ])
    ui.section("Analyse")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Åpne i Rivalradar", key=f"rr_from_{entry}", use_container_width=True):
            st.session_state["v400_my_manager"] = int(entry)
            st.session_state["v400_main_page"] = "Rivalradar"
            st.rerun()
    with c2:
        show_odds = st.toggle("Vis modellens anslag", key=f"odds_manager_{entry}")
    if show_odds:
        with st.spinner("Beregner anslag …"):
            histories, _ = histories_for([nint(x.get("entry")) for x in managers])
            result = simulate_group(managers, histories, current_event_id(bootstrap) or 1, history_store, simulations=3500)
        row = result[result["entry"] == int(entry)]
        if not row.empty:
            r = row.iloc[0]
            ui.stat_strip([
                (fmt_pct(r.get("win_pct")), "Ligagull"),
                (fmt_pct(r.get("top3_pct")), "Topp 3"),
                (f"{nfloat(r.get('strength')):.0f}/100", "Modellstyrke"),
            ])
            st.caption("Modellens anslag. Historikk veier mindre jo lenger sesongen går.")


def render_compare(managers: list[dict], bootstrap: dict) -> None:
    opts = manager_options(managers)
    ids = [x[0] for x in opts]
    labels = dict(opts)
    selected = st.multiselect("Velg 2–8 managere", ids, max_selections=8, format_func=lambda x: labels.get(int(x), str(x)), key="v400_compare_entries")
    if len(selected) < 2:
        st.caption("Velg minst to managere.")
        return
    selected_managers = [m for m in managers if nint(m.get("entry")) in selected]
    ownership = selected_ownership(managers, selected)
    events = ownership.get("manager_events", pd.DataFrame())
    basis = ui.nav(["Ligaen", "Denne måneden", "Denne GW"], "v400_compare_basis", "Ligaen")
    ui.section("Slik står de")
    if basis == "Denne måneden":
        phase, month_df = current_month_table(managers, bootstrap)
        block = month_df[month_df["entry"].isin(selected)].sort_values(["points", "manager"], ascending=[False, True]) if not month_df.empty else pd.DataFrame()
        ui.rows([
            {"rank": i + 1, "who": r.get("manager"), "meta": f"{phase['name'] if phase else 'Måneden'} · {r.get('team','')}", "num": f"{nint(r.get('points'))} p"}
            for i, r in enumerate(block.to_dict("records"))
        ])
    elif basis == "Denne GW" and not events.empty:
        block = events.sort_values(["gw_points", "manager"], ascending=[False, True])
        ui.rows([
            {"rank": i + 1, "who": r.get("manager"), "meta": r.get("team",""), "num": f"{nint(r.get('gw_points'))} p"}
            for i, r in enumerate(block.to_dict("records"))
        ])
    else:
        ui.rows([
            {"rank": nint(m.get("rank")), "who": manager_name(m), "meta": str(m.get("entry_name") or ""), "num": f"{nint(m.get('total'))} p"}
            for m in sorted(selected_managers, key=lambda x: nint(x.get("rank"), 999999))
        ])
    picks = ownership.get("picks", pd.DataFrame())
    if not picks.empty:
        ui.section("Kapteiner")
        cap_rows = picks[picks["is_captain"]]
        ui.rows([{"rank": "TC" if r.get("is_triple_captain") else "C", "who": r.get("manager"), "meta": r.get("player"), "num": f"{nint(r.get('event_points'))} p"} for r in cap_rows.to_dict("records")])
        sets = {entry: set(block["element"].astype(int).tolist()) for entry, block in picks.groupby("entry")}
        common_ids = set.intersection(*sets.values()) if sets else set()
        catalog = player_catalog(bootstrap)
        ui.section("Felles")
        if common_ids:
            ui.rows([{"rank": "", "who": catalog.get(pid, {}).get("web_name", str(pid)), "meta": catalog.get(pid, {}).get("club", ""), "num": ""} for pid in sorted(common_ids, key=lambda x: catalog.get(x, {}).get("web_name", ""))])
        ui.section("Der de skiller seg")
        for entry in selected:
            mine = sets.get(int(entry), set()) - common_ids
            name = labels.get(int(entry), str(entry))
            names = [catalog.get(pid, {}).get("web_name", str(pid)) for pid in mine]
            ui.callout(name, ", ".join(sorted(names, key=normalize_text)) or "Ingen forskjeller")
    show_odds = st.toggle("Vis odds for denne gruppen", key="v400_compare_odds")
    if show_odds:
        with st.spinner("Beregner gruppen …"):
            histories, _ = histories_for(selected)
            phase, month_df = current_month_table(managers, bootstrap)
            current = current_event_id(bootstrap) or 1
            if basis == "Denne måneden":
                month_scores = {nint(r.get("entry")): nfloat(r.get("points")) for r in month_df.to_dict("records")} if not month_df.empty else {}
                period_events = max(1, phase["stop_event"] - current) if phase else 3
                title = f"{phase['name'] if phase else 'Måneden'} · modellens anslag"
            elif basis == "Denne GW":
                month_scores = {nint(r.get("entry")): nfloat(r.get("gw_points")) for r in events.to_dict("records")} if not events.empty else {}
                period_events = 1
                title = "Denne GW · modellens anslag"
            else:
                month_scores = {nint(m.get("entry")): nfloat(m.get("total")) for m in selected_managers}
                period_events = max(1, 38 - current)
                title = "Ligaen · modellens anslag"
            odds = compare_group_odds(selected_managers, histories, current, history_store, period_events=period_events, month_scores=month_scores)
        ui.section(title)
        ui.rows([{"rank": i + 1, "who": r.get("manager"), "meta": f"Odds {decimal_odds_from_pct(r.get('win_pct'))}", "num": fmt_pct(r.get("win_pct"))} for i, r in enumerate(odds.to_dict("records"))])


def render_league(managers: list[dict], bootstrap: dict, auto_rows: list[dict]) -> None:
    ui.page_title("Ligaen")
    view = ui.nav(["Tabell", "Manager", "Sammenlign"], "v400_league_view", "Tabell")
    if view == "Tabell":
        render_league_table(managers)
    elif view == "Manager":
        opts = manager_options(managers); ids = [x[0] for x in opts]; labels = dict(opts)
        entry = st.selectbox("Finn manager", ids, format_func=lambda x: labels.get(int(x), str(x)), key="v400_manager_select")
        render_manager_profile(int(entry), managers, bootstrap, auto_rows)
    else:
        render_compare(managers, bootstrap)


def render_candidate_list(df: pd.DataFrame, title: str, rival_n: int, limit: int = 6) -> None:
    ui.section(title)
    if df is None or df.empty:
        st.caption("Ingen sterke treff akkurat nå.")
        return
    ui.rows([
        {
            "rank": i + 1,
            "who": r.get("web_name"),
            "meta": f"{r.get('club')} · {r.get('position')} · {fmt_price(r.get('current_price'))} · {r.get('outlook_label')} · FPL {nfloat(r.get('selected_by_pct')):.0f}%",
            "num": f"{nint(r.get('rival_count'))}/{rival_n} rivaler",
        }
        for i, r in enumerate(df.head(limit).to_dict("records"))
    ])


def render_rivalradar(managers: list[dict], bootstrap: dict) -> None:
    ui.page_title("Rivalradar", "Velg hvem du vil slå. Resten skal verktøyet gjøre for deg.")
    opts = manager_options(managers); ids = [x[0] for x in opts]; labels = dict(opts)
    default_me = st.session_state.get("v400_my_manager")
    if default_me not in ids:
        default_me = ids[0] if ids else None
    me = st.selectbox("Min manager", ids, index=ids.index(default_me) if default_me in ids else 0, format_func=lambda x: labels.get(int(x), str(x)), key="v400_my_manager")
    rival_choices = [x for x in ids if int(x) != int(me)]
    rivals = st.multiselect("Rivaler", rival_choices, max_selections=8, format_func=lambda x: labels.get(int(x), str(x)), key="v400_rivals")
    c1, c2, c3 = st.columns(3)
    with c1:
        period = st.selectbox("Periode", ["Neste GW", "Neste 3 GW", "Neste 5 GW", "Resten av måneden", "Sesongen"], index=1, key="v400_period")
    with c2:
        goal = st.selectbox("Mål", ["Slå disse managerne", "Vinn måneden", "Kom topp 3", "Ta igjen manageren foran", "Forsvar ledelsen", "Vinn ligaen"], key="v400_goal")
    with c3:
        risk = st.selectbox("Risiko", ["Trygt", "Balansert", "Aggressivt"], index=1, key="v400_risk")
    if not rivals:
        st.caption("Velg minst én rival.")
        return
    run = st.button("Analyser rivalene", type="primary", use_container_width=True, key="v400_run_rivals")
    signature = (int(me), tuple(sorted(int(x) for x in rivals)), period, goal, risk)
    if run or st.session_state.get("v400_rival_signature") != signature:
        if not run:
            st.caption("Trykk «Analyser rivalene» når du er klar.")
            return
        names = ", ".join(labels.get(int(x), str(x)) for x in rivals)
        with st.spinner(f"Analyserer {labels.get(int(me), me)} mot {names} …"):
            result = rival_analysis(client, managers, history_store, int(me), [int(x) for x in rivals], period, risk, goal)
        st.session_state["v400_rival_signature"] = signature
        st.session_state["v400_rival_result"] = result
    result = st.session_state.get("v400_rival_result")
    if not result or result.get("error"):
        if result and result.get("error"):
            st.warning(result["error"])
        return
    ownership = result["ownership"]
    data_quality_note(ownership)
    rival_n = nint(result.get("rival_n"), len(rivals))
    strategy_context = str(result.get("strategy_context") or "neutral")
    ui.callout(
        "Spill situasjonen",
        str(result.get("strategy_text") or ""),
        "green" if strategy_context == "defend" else "red" if strategy_context == "chase" else "",
    )
    render_candidate_list(result.get("they_have_i_lack"), "De har · du mangler", rival_n)
    render_candidate_list(result.get("i_have_they_lack"), "Du har · de mangler", rival_n)
    render_candidate_list(result.get("nobody_has"), "Muligheter ingen av dere har", rival_n)

    ui.section("Trekk å vurdere")
    suggestions = result.get("suggestions", pd.DataFrame())
    if suggestions is None or suggestions.empty:
        st.caption("Fant ingen tydelige én-for-én-trekk som passer budsjett og posisjon.")
    else:
        for i, r in enumerate(suggestions.head(5).to_dict("records")):
            if i == 0:
                label = "Beste treff"
            elif risk == "Trygt":
                label = "Tryggere"
            elif risk == "Aggressivt":
                label = "Offensivt"
            else:
                label = "Alternativ"
            meta = f"{r['out_player']} → {r['in_player']} · {fmt_price(r['in_price'])} · {r['outlook_label']} · budsjett etter {fmt_price(r['budget_after'])}"
            ui.recommendation(r["in_player"], label, meta, r.get("reasons") or [])
        if not bool(suggestions.iloc[0].get("selling_price_exact")):
            st.caption("Minst ett forslag bruker estimert salgspris fordi FPL ikke leverte managerens eksakte salgspris i picks-dataene.")

    ui.section("Kaptein")
    caps = result.get("captains", pd.DataFrame())
    if caps is not None and not caps.empty:
        labels_cap = ["Beste valg", "Tryggere alternativ", "Mer offensivt"]
        ui.rows([
            {"rank": i + 1, "who": r.get("web_name"), "meta": labels_cap[i] if i < len(labels_cap) else "Alternativ", "num": f"{nint(r.get('outlook_expected_low'))}–{nint(r.get('outlook_expected_high'))} p"}
            for i, r in enumerate(caps.to_dict("records"))
        ])

    with st.expander("Hva om?"):
        if suggestions is None or suggestions.empty:
            st.caption("Ingen transfer å simulere.")
        else:
            choices = list(range(min(5, len(suggestions))))
            idx = st.selectbox("Trekk", choices, format_func=lambda i: f"{suggestions.iloc[i]['out_player']} → {suggestions.iloc[i]['in_player']}", key="v400_whatif")
            r = suggestions.iloc[int(idx)].to_dict()
            ui.stat_strip([
                (fmt_price(r.get("budget_after")), "Budsjett etter"),
                (f"{nint(r.get('rival_count'))}/{rival_n}", "Rivaler med spilleren"),
                (f"{nint(r.get('expected_low'))}–{nint(r.get('expected_high'))}", "Forventet område"),
            ])
            st.caption("Scenarioet viser strukturen i trekket. Det er et anslag, ikke en spådom.")

    show_odds = st.toggle("Vis odds for rivalgruppen", key="v400_rival_odds")
    if show_odds:
        selected = [int(me)] + [int(x) for x in rivals]
        selected_managers = [m for m in managers if nint(m.get("entry")) in selected]
        with st.spinner("Beregner gruppen …"):
            histories, _ = histories_for(selected)
            month_scores = current_month_points_map(managers, bootstrap) if goal == "Vinn måneden" else None
            events_n = max(1, len(result.get("event_ids") or [1]))
            odds = compare_group_odds(selected_managers, histories, current_event_id(bootstrap) or 1, history_store, period_events=events_n, month_scores=month_scores)
        ui.section("Modellens anslag")
        ui.rows([{"rank": i + 1, "who": r.get("manager"), "meta": f"Odds {decimal_odds_from_pct(r.get('win_pct'))}", "num": fmt_pct(r.get("win_pct"))} for i, r in enumerate(odds.to_dict("records"))])
        st.caption("Anslaget kombinerer inneværende sesong med historikk. Historikken tones ned gjennom sesongen.")


def render_history(auto_rows: list[dict]) -> None:
    ui.page_title("Historikk")
    view = ui.nav(["Hall of Fame", "Månedsvinnere", "Sesonger", "Rekorder"], "v400_history_view", "Hall of Fame")
    if view == "Hall of Fame":
        hof = history_store.hall_of_fame(auto_rows)
        if hof.empty:
            st.caption("Ingen historikk funnet.")
            return
        ui.rows([
            {
                "rank": nint(r.get("rank")),
                "rank_class": "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else "",
                "who": r.get("display_name"),
                "meta": f"{nint(r.get('podiums'))} pallplasser",
                "num": f"{nint(r.get('gold'))} gull · {nint(r.get('silver'))} sølv · {nint(r.get('bronze'))} bronse",
            }
            for i, r in enumerate(hof.head(40).to_dict("records"))
        ])
        st.caption("Hall of Fame rangeres etter gull, deretter sølv og bronse. Gull summerer ligagull, cupgull og månedsseire.")
    elif view == "Månedsvinnere":
        medals = history_store.monthly_medals(auto_rows)
        ui.rows([
            {"rank": nint(r.get("rank")), "who": r.get("manager"), "meta": f"{nint(r.get('podiums'))} pallplasser", "num": f"{nint(r.get('gold'))} gull · {nint(r.get('silver'))} sølv · {nint(r.get('bronze'))} bronse"}
            for r in medals.head(40).to_dict("records")
        ])
        with st.expander("Måned for måned"):
            cal = history_store.monthly_calendar(auto_rows)
            ui.dataframe_compact(cal, ["season", "month", "winner", "runner_up", "third"], {"season": "Sesong", "month": "Måned", "winner": "Gull", "runner_up": "Sølv", "third": "Bronse"})
    elif view == "Sesonger":
        ui.section("Sammenlagt")
        overall = history_store.overall_results()
        ui.dataframe_compact(overall, ["season", "winner", "runner_up", "third_place"], {"season": "Sesong", "winner": "Gull", "runner_up": "Sølv", "third_place": "Bronse"})
        ui.section("Cup")
        cup = history_store.cup_results()
        ui.dataframe_compact(cup, ["season", "winner", "runner_up"], {"season": "Sesong", "winner": "Vinner", "runner_up": "Finalist"})
    else:
        hof = history_store.hall_of_fame(auto_rows)
        if hof.empty:
            st.caption("Ingen rekorddata.")
            return
        league = hof.sort_values(["league_gold", "league_silver", "display_name"], ascending=[False, False, True]).iloc[0]
        cup = hof.sort_values(["cup_gold", "cup_silver", "display_name"], ascending=[False, False, True]).iloc[0]
        month = hof.sort_values(["monthly_gold", "monthly_silver", "display_name"], ascending=[False, False, True]).iloc[0]
        podium = hof.sort_values(["podiums", "gold", "display_name"], ascending=[False, False, True]).iloc[0]
        ui.rows([
            {"rank": "L", "who": league["display_name"], "meta": "Flest ligatitler", "num": nint(league["league_gold"])},
            {"rank": "C", "who": cup["display_name"], "meta": "Flest cupgull", "num": nint(cup["cup_gold"])},
            {"rank": "M", "who": month["display_name"], "meta": "Flest månedsseire", "num": nint(month["monthly_gold"])},
            {"rank": "P", "who": podium["display_name"], "meta": "Flest pallplasser", "num": nint(podium["podiums"])},
        ])


def health_check(managers: list[dict], bootstrap: dict) -> list[str]:
    issues = []
    entries = [nint(m.get("entry")) for m in managers if nint(m.get("entry"))]
    if len(managers) != 63:
        issues.append(f"Forventet 63 managere, fant {len(managers)}.")
    if len(entries) != len(set(entries)):
        issues.append("Duplikate entry-ID-er i ligadata.")
    catalog = player_catalog(bootstrap)
    invalid_prices = [p for p in catalog.values() if p["current_price"] <= 0 or p["current_price"] > 25]
    if invalid_prices:
        issues.append(f"{len(invalid_prices)} spillere har mistenkelig pris.")
    return issues


def load_app_data() -> tuple[dict, list[dict], list[str]]:
    errors = []
    try:
        bootstrap = client.bootstrap()
    except Exception as exc:
        return {}, [], [str(exc)]
    try:
        _, managers, debug = client.league_managers(DEFAULT_LEAGUE_ID)
        managers = canonical_managers(managers, history_store)
        errors.extend(debug.get("errors", []))
    except Exception as exc:
        managers = []
        errors.append(str(exc))
    return bootstrap, managers, errors


bootstrap, managers, load_errors = load_app_data()
ui.header(short_season_label(bootstrap) if bootstrap else "26/27")
main_page = ui.nav(["Forside", "Sesong", "Ligaen", "Rivalradar", "Historikk"], "v400_main_page", "Forside")

if not bootstrap or not managers:
    st.warning("FPL-data er midlertidig utilgjengelig.")
    if load_errors:
        st.caption("Historikken kan fortsatt fungere når datafilene ligger i repoet.")
    if main_page == "Historikk":
        render_history([])
else:
    auto_rows = auto_monthly_rows(bootstrap)
    if main_page == "Forside":
        render_home(managers, bootstrap)
    elif main_page == "Sesong":
        render_season(managers, bootstrap)
    elif main_page == "Ligaen":
        render_league(managers, bootstrap, auto_rows)
    elif main_page == "Rivalradar":
        render_rivalradar(managers, bootstrap)
    elif main_page == "Historikk":
        render_history(auto_rows)

# Hidden developer health data: no sidebar, no normal UI noise.
if st.query_params.get("debug") == "1" and bootstrap:
    with st.expander("V400 debug"):
        st.code(APP_VERSION)
        issues = health_check(managers, bootstrap)
        st.write(issues or ["Ingen kjente health-check-avvik."])
