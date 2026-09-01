
import math
import re
import unicodedata
import json
import html
from difflib import SequenceMatcher
from typing import Any
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import numpy as np
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    import pydeck as pdk
except ImportError:
    pdk = None


BASE_URL = "https://fantasy.premierleague.com/api"
DEFAULT_LEAGUE_ID = 25220
APP_VERSION = "lofthus-road-open-v300-competitive-update"

HEADERS = {"User-Agent": "Mozilla/5.0 Lofthus Road Open Kontrollrom"}

st.set_page_config(page_title="Lofthus Road Open", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

if st.session_state.get("_app_version") != APP_VERSION:
    st.session_state.clear()
    st.session_state["_app_version"] = APP_VERSION

st.markdown(
    """
    <style>
        :root {
            --lro-bg: #0b1220;
            --lro-card: #111827;
            --lro-card-soft: #f8fafc;
            --lro-border: #e5e7eb;
            --lro-gold: #fbbf24;
            --lro-red: #b91c1c;
            --lro-muted: #6b7280;
        }

        .block-container {padding-top: 1.6rem; padding-bottom: 3rem;}

        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            padding: 14px 16px;
            border-radius: 16px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
        }

        .lro-hero {
            position: relative;
            overflow: hidden;
            background:
                linear-gradient(90deg, rgba(8, 18, 36, 0.96) 0%, rgba(8, 31, 22, 0.90) 44%, rgba(83, 19, 19, 0.90) 100%),
                repeating-linear-gradient(90deg, rgba(255,255,255,0.055) 0 2px, transparent 2px 74px),
                linear-gradient(135deg, #075f37 0%, #0f7a42 46%, #0b3d2a 100%);
            border-radius: 24px;
            padding: 28px 32px;
            color: white;
            margin-bottom: 18px;
            box-shadow: 0 18px 46px rgba(15, 23, 42, 0.25);
            border: 1px solid rgba(255, 255, 255, 0.12);
        }
        .lro-hero:before {
            content: "";
            position: absolute;
            right: -12px;
            top: 14px;
            width: min(42vw, 460px);
            height: 165px;
            border: 2px solid rgba(255,255,255,0.20);
            border-radius: 22px;
            transform: rotate(-7deg);
            background:
                radial-gradient(circle at 50% 50%, transparent 0 38px, rgba(255,255,255,0.22) 39px 41px, transparent 42px),
                linear-gradient(90deg, transparent 0 49%, rgba(255,255,255,0.20) 49% 51%, transparent 51% 100%),
                linear-gradient(90deg, rgba(255,255,255,0.14) 0 11%, transparent 11% 89%, rgba(255,255,255,0.14) 89% 100%);
            opacity: 0.95;
            pointer-events: none;
        }
        .lro-hero:after {
            content: "●";
            position: absolute;
            right: 118px;
            bottom: 42px;
            width: 54px;
            height: 54px;
            border-radius: 999px;
            display: grid;
            place-items: center;
            background: radial-gradient(circle, #ffffff 0 36%, #111827 37% 43%, #ffffff 44% 100%);
            color: transparent;
            opacity: 0.18;
            box-shadow: 0 0 42px rgba(255,255,255,0.22);
        }

        .lro-hero h1 {
            position: relative;
            z-index: 1;
            font-size: clamp(2.15rem, 4vw, 3.6rem);
            line-height: 0.98;
            margin: 0;
            color: white;
            letter-spacing: -0.055em;
        }

        .lro-beta {
            position: relative;
            z-index: 1;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 7px 11px;
            border-radius: 999px;
            background: rgba(251, 191, 36, 0.14);
            color: #fde68a;
            border: 1px solid rgba(251, 191, 36, 0.32);
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 14px;
        }

        .lro-card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 14px;
            margin: 14px 0 24px 0;
        }

        .lro-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 18px 18px 16px 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        }

        .lro-card.dark {
            background: linear-gradient(135deg, #111827 0%, #1f2937 100%);
            color: white;
            border-color: rgba(255,255,255,0.12);
        }

        .lro-card-label {
            color: #6b7280;
            font-size: 0.82rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 8px;
        }
        .lro-card.dark .lro-card-label {color: #d1d5db;}

        .lro-card-value {
            font-size: 1.3rem;
            line-height: 1.12;
            font-weight: 850;
            letter-spacing: -0.025em;
            word-break: normal;
        }

        .lro-card-caption {
            margin-top: 8px;
            color: #6b7280;
            font-size: 0.92rem;
        }
        .lro-card.dark .lro-card-caption {color: #e5e7eb;}

        .lro-note {
            border-radius: 18px;
            padding: 16px 18px;
            margin: 12px 0 18px 0;
            border: 1px solid #e5e7eb;
            background: #f8fafc;
        }
        .lro-note strong {display:block; margin-bottom: 4px;}
        .lro-note.gold {background: #fffbeb; border-color: #fde68a;}
        .lro-note.red {background: #fef2f2; border-color: #fecaca;}
        .lro-note.dark {background: #111827; border-color: #1f2937; color:white;}
        .lro-note.dark span {color:#e5e7eb;}

        .small-muted {color: #6b7280; font-size: 0.92rem;}



        .league-help {
            color: #6b7280;
            font-size: 0.92rem;
            margin: 6px 0 12px 0;
        }

        .city-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
            margin-top: 12px;
        }

        .city-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 14px 16px;
            margin-bottom: 10px;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.04);
        }
        .city-title {font-weight: 850; font-size: 1.04rem; margin-bottom: 4px;}
        .city-people {color: #374151; line-height: 1.45;}


        .lro-page-nav {
            margin: 2px 0 18px 0;
        }
        .section-kicker {
            color: #991b1b;
            font-weight: 850;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.78rem;
            margin-bottom: 4px;
        }
        .clean-section {
            margin-top: 14px;
            margin-bottom: 18px;
        }

        /* Stable navigation. Avoids Streamlit tabs/radio dots and renders only the selected page. */
        .stButton > button {
            border-radius: 999px;
            border: 1px solid #d1d5db;
            font-weight: 750;
            padding: 0.45rem 0.75rem;
        }
        .stButton > button[kind="primary"] {
            background: #111827;
            border-color: #111827;
            color: white;
        }

        .lro-section-title {
            margin: 18px 0 10px 0;
            padding: 10px 14px;
            border-radius: 14px;
            background: linear-gradient(90deg, #111827 0%, #7f1d1d 100%);
            color: white;
            font-weight: 850;
            letter-spacing: -0.01em;
        }
        .lro-section-title span {
            display:block;
            color:#fde68a;
            font-size:0.78rem;
            text-transform:uppercase;
            letter-spacing:0.08em;
            margin-bottom:2px;
        }



        /* v37: tighter dashboard layout and safer mobile behavior */
        html, body, [data-testid="stAppViewContainer"] { overflow-x: hidden; }
        .block-container {
            max-width: 100% !important;
            padding-left: clamp(0.75rem, 2.2vw, 2.6rem) !important;
            padding-right: clamp(0.75rem, 2.2vw, 2.6rem) !important;
        }
        h1, h2, h3 { letter-spacing: -0.035em; }
        .lro-note { padding: 13px 15px; margin: 10px 0 14px 0; }
        .lro-card { padding: 14px 15px; border-radius: 15px; }
        .lro-card-value { font-size: 1.12rem; }

        @media (max-width: 760px) {
            .block-container {padding-left: 0.65rem !important; padding-right: 0.65rem !important;}
            .lro-hero {padding: 20px 18px; border-radius: 18px; margin-bottom: 12px;}
            .lro-hero:before, .lro-hero:after {opacity: 0.12;}
            .lro-hero h1 {font-size: 2.05rem; line-height: 1.02;}
            .lro-beta {font-size: 0.68rem; padding: 6px 9px;}
            .lro-card-grid {grid-template-columns: 1fr; gap: 9px; margin-bottom: 14px;}
            .lro-card {padding: 12px 13px;}
            .lro-note {font-size: 0.88rem;}
            .stButton > button {font-size: 0.82rem; padding: 0.35rem 0.45rem;}
        }

        .lro-premium-line {
            margin-top: 14px;
            position: relative;
            z-index: 1;
            color: rgba(255,255,255,0.86);
            font-size: 1.05rem;
            font-weight: 650;
        }

        .lro-club-mark {
            display:inline-flex;
            align-items:center;
            gap:8px;
            padding:6px 12px;
            border-radius:999px;
            background:rgba(255,255,255,0.12);
            border:1px solid rgba(255,255,255,0.18);
            margin-top:12px;
            font-size:0.82rem;
            font-weight:800;
            letter-spacing:0.08em;
            text-transform:uppercase;
        }

    </style>
    <div class="lro-hero">
        <div class="lro-beta">SESONG 2026/27</div>
        <h1>Lofthus Road Open</h1>
        <div class="lro-premium-line">Fantasy Football Club</div>
        <div class="lro-club-mark">LRO · SIDEN 2014</div>
    </div>
    """,
    unsafe_allow_html=True,
)
# V202 renders its own product header below.

with st.sidebar:
    st.header("Lofthus Road Open")
    st.caption(f"Liga-ID: {DEFAULT_LEAGUE_ID}")
    if st.session_state.get("last_updated"):
        st.caption(f"Sist hentet: {st.session_state['last_updated']}")
    if st.button("Oppdater fra FPL nå"):
        st.session_state["_refresh_fpl_now"] = True
        st.rerun()
    st.markdown("---")
    st.caption("Lofthus Road Open")
    st.caption("Build: V300 · The Competitive Update")


# -----------------------------
# Grunnfunksjoner
# -----------------------------

@st.cache_data(ttl=300)
def get_json(path: str) -> Any:
    url = f"{BASE_URL}{path}"
    response = requests.get(url, timeout=30, headers=HEADERS)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=3600)
def get_entry_history(entry_id: int) -> dict:
    return get_json(f"/entry/{entry_id}/history/")


@st.cache_data(ttl=300)
def get_bootstrap_static() -> dict:
    """FPL master data: events, players and clubs."""
    return get_json("/bootstrap-static/")


@st.cache_data(ttl=300)
def get_entry_event_picks(entry_id: int, event_id: int) -> dict:
    """Public squad/line-up for one manager after the gameweek deadline."""
    return get_json(f"/entry/{int(entry_id)}/event/{int(event_id)}/picks/")


def normalize_text(value: str) -> str:
    value = str(value or "").lower().strip()

    replacements = {
        "æ": "ae",
        "ø": "o",
        "å": "a",
        "ä": "a",
        "ö": "o",
        "ü": "u",
        "é": "e",
        "è": "e",
        "á": "a",
        "à": "a",
        "í": "i",
        "ó": "o",
        "ò": "o",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def format_rank(rank: int | float | None) -> str:
    if rank is None or pd.isna(rank):
        return ""

    try:
        rank = int(float(rank))
    except (ValueError, TypeError):
        return ""

    return f"{rank:,}".replace(",", " ")


def format_odds(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""

    value = max(float(value), 1.10)
    return f"{value:.2f}"


def display_table(
    df: pd.DataFrame,
    columns: list[str],
    labels: dict[str, str],
    column_config: dict | None = None,
):
    existing = [column for column in columns if column in df.columns]
    display_df = df[existing].rename(columns={column: labels.get(column, column) for column in existing})

    translated_config = {}

    if column_config:
        for source_column, config in column_config.items():
            if source_column in existing:
                translated_name = labels.get(source_column, source_column)
                translated_config[translated_name] = config

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config=translated_config,
    )


def render_static_table_component(
    df: pd.DataFrame,
    columns: list[str],
    labels: dict[str, str],
    wide_columns: set[str] | None = None,
    height: int = 520,
):
    """Render a clean wide table where long text wraps instead of disappearing."""
    if df.empty:
        st.caption("Ingen data å vise.")
        return

    wide_columns = wide_columns or set()
    existing = [column for column in columns if column in df.columns]
    header_cells = []
    for column in existing:
        cls = "wide" if column in wide_columns else ""
        header_cells.append(f'<th class="{cls}">{html.escape(labels.get(column, column))}</th>')

    body_rows = []
    for _, row in df[existing].iterrows():
        cells = []
        for column in existing:
            value = "" if pd.isna(row.get(column)) else str(row.get(column))
            safe_value = html.escape(value).replace(" | ", "<br>")
            cls = "wide" if column in wide_columns else ""
            cells.append(f'<td class="{cls}">{safe_value}</td>')
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    component_html = f"""
    <div class="static-table-wrap">
      <style>
        .static-table-wrap {{
          width: 100%;
          max-width: 100%;
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          border-radius: 12px;
        }}
        table.static-table {{
          border-collapse: collapse;
          width: 100%;
          min-width: 880px;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          overflow: hidden;
        }}
        .static-table th {{
          background: #0f172a;
          color: #ffffff;
          text-align: left;
          font-size: 10.5px;
          letter-spacing: .055em;
          text-transform: uppercase;
          padding: 7px 9px;
          white-space: nowrap;
        }}
        .static-table td {{
          padding: 7px 9px;
          border-bottom: 1px solid #eef2f7;
          vertical-align: top;
          color: #111827;
          font-size: 12.4px;
          line-height: 1.35;
          white-space: nowrap;
        }}
        .static-table td.wide, .static-table th.wide {{
          min-width: 520px;
          max-width: 980px;
          white-space: normal;
          overflow-wrap: anywhere;
        }}
        .static-table tr:nth-child(even) td {{ background: #f8fafc; }}
        @media (max-width: 760px) {{
          table.static-table {{ min-width: 760px; }}
          .static-table th {{ font-size: 9.5px; padding: 6px 7px; }}
          .static-table td {{ font-size: 11.2px; padding: 6px 7px; }}
          .static-table td.wide, .static-table th.wide {{ min-width: 360px; }}
        }}
      </style>
      <table class="static-table">
        <thead><tr>{''.join(header_cells)}</tr></thead>
        <tbody>{''.join(body_rows)}</tbody>
      </table>
    </div>
    """
    components.html(component_html, height=height, scrolling=True)


def csv_bytes(df: pd.DataFrame, columns: list[str], labels: dict[str, str]) -> bytes:
    existing = [column for column in columns if column in df.columns]
    display_df = df[existing].rename(columns={column: labels.get(column, column) for column in existing})
    return display_df.to_csv(index=False).encode("utf-8")


def lro_note(title: str, text: str, tone: str = ""):
    tone_class = f" {tone}" if tone else ""
    st.markdown(
        f'''
        <div class="lro-note{tone_class}">
            <strong>{title}</strong>
            <span>{text}</span>
        </div>
        ''',
        unsafe_allow_html=True,
    )


def lro_cards(cards: list[dict]):
    """Render cards with native Streamlit components.

    This avoids raw HTML leaking into the page if Streamlit/Markdown parsing
    gets fussy about multi-card HTML blocks.
    """
    if not cards:
        return

    cols = st.columns(len(cards))

    for col, card in zip(cols, cards):
        with col:
            with st.container(border=True):
                label = str(card.get("label", ""))
                value = str(card.get("value", ""))
                caption = str(card.get("caption", ""))

                if label:
                    st.caption(label.upper())
                if value:
                    st.markdown(f"**{value}**")
                if caption:
                    st.caption(caption)




# -----------------------------
# v60 design helpers
# -----------------------------

def v60_section(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="lro-section-title">
            <span>{subtitle}</span>
            {title}
        </div>
        """,
        unsafe_allow_html=True,
    )


def v60_stat_cards(summary_df):
    if summary_df is None or summary_df.empty:
        return
    leader = summary_df.iloc[0]
    cards = [
        {
            "label": "Serieledelse",
            "value": str(leader.get("player_name", "")),
            "caption": str(leader.get("entry_name", "")),
        }
    ]
    if len(summary_df) > 1:
        cards.append({
            "label": "Utfordrer",
            "value": str(summary_df.iloc[1].get("player_name", "")),
            "caption": "2. plass",
        })
    lro_cards(cards)




# ============================================================
# FERRARI EDITION V100 - CLUBHOUSE COMPONENTS
# ============================================================

def ferrari_story_card(title, body, emoji="🏟️"):
    st.markdown(
        f"""
        <div class="lro-card">
            <div class="lro-card-label">{emoji} {title}</div>
            <div class="lro-card-value">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ferrari_home_intro():
    st.markdown(
        """
        <div class="lro-section-title">
            <span>LIVE FRA LIGAEN</span>
            Kampdag på Lofthus Road
        </div>
        """,
        unsafe_allow_html=True,
    )


def ferrari_empty_state(title, text):
    st.markdown(
        f"""
        <div class="lro-note dark">
            <strong>{title}</strong>
            <span>{text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )




# ============================================================
# FERRARI PASS 2 - MATCHDAY EXPERIENCE
# ============================================================

def ferrari_matchday_block():
    st.markdown(
        """
        <div class="lro-section-title">
            <span>LOFTHUS ROAD OPEN</span>
            Matchday
        </div>
        """,
        unsafe_allow_html=True,
    )


def ferrari_rank_card(place, manager, team, points, trend=""):
    medal = ""
    if str(place) == "1":
        medal = "🥇"
    elif str(place) == "2":
        medal = "🥈"
    elif str(place) == "3":
        medal = "🥉"

    st.markdown(
        f"""
        <div class="lro-card">
            <div class="lro-card-label">{medal} Plass {place}</div>
            <div class="lro-card-value">{manager}</div>
            <div class="lro-card-caption">
                {team}<br>
                {points} poeng {trend}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ferrari_story_engine(summary_df):
    if summary_df is None or summary_df.empty:
        return

    top = summary_df.iloc[0]

    st.markdown(
        """
        <div class="lro-section-title">
            <span>DAGENS OVERSKRIFTER</span>
            Ligaens historier
        </div>
        """,
        unsafe_allow_html=True,
    )

    ferrari_story_card(
        "Serieleder",
        f"{top.get('manager', 'Ukjent')} topper ligaen"
    )

    if "form" in summary_df.columns:
        best_form = summary_df.iloc[0]
        ferrari_story_card(
            "Heteste manager",
            f"{best_form.get('manager', 'Ukjent')} er i flyt"
        )


def ferrari_profile_header(name):
    st.markdown(
        f"""
        <div class="lro-hero">
            <div class="lro-beta">MANAGERPROFILE</div>
            <h1>{name}</h1>
            <div class="lro-premium-line">
                Lofthus Road Open-legende under utvikling
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )




# ============================================================
# FERRARI PASS 3 - CLUBHOUSE FRONT PAGE ENGINE
# ============================================================

def ferrari_stat_card(title, value, subtitle="", icon="⚽"):
    st.markdown(
        f"""
        <div class="lro-card">
            <div class="lro-card-label">{icon} {title}</div>
            <div class="lro-card-value">{value}</div>
            <div class="lro-card-caption">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ferrari_headline(title, text, icon="🔥"):
    st.markdown(
        f"""
        <div class="lro-note dark">
            <strong>{icon} {title}</strong>
            <span>{text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ferrari_clubhouse_frontpage(summary_df):
    if summary_df is None or summary_df.empty:
        ferrari_empty_state("Ingen livedata", "Ligaen har ikke nok data enda.")
        return

    leader = summary_df.iloc[0]

    v60_section("Kampdag på Lofthus Road", "LIVE LIGA")

    lro_cards([
        {
            "label": "Serieledelse",
            "value": str(leader.get("player_name", "")),
            "caption": f"{leader.get('total', '')} poeng"
        },
        {
            "label": "Lag",
            "value": str(leader.get("entry_name", "")),
            "caption": "Tabelltopp"
        },
        {
            "label": "Status",
            "value": "🔥 I flyt",
            "caption": "Sesongen lever"
        }
    ])

    v60_section("Ukens overskrifter", "LIGAENS DRAMA")

    ferrari_headline(
        "Seriepress",
        f"{leader.get('player_name', 'Ukjent')} leder ligaen akkurat nå."
    )

    if len(summary_df) > 1:
        challenger = summary_df.iloc[1]
        ferrari_headline(
            "Nærmeste utfordrer",
            f"{challenger.get('player_name', 'Ukjent')} jakter bakfra.",
            "⚔️"
        )

    v60_section("Topp 5 i ligaen", "LIVE TABELL")

    for idx, row in summary_df.head(5).iterrows():
        ferrari_rank_card(
            idx + 1,
            row.get("player_name", ""),
            row.get("entry_name", ""),
            row.get("total", ""),
            ""
        )


# -----------------------------
# Datafiler
# -----------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"


def clean_cell(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def read_csv_file(filename: str, columns: list[str]) -> pd.DataFrame:
    path = DATA_DIR / filename

    if not path.exists():
        return pd.DataFrame(columns=columns)

    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)

    for column in columns:
        if column not in df.columns:
            df[column] = ""

    df = df[columns].copy()

    for column in columns:
        df[column] = df[column].map(clean_cell)

    return df


def records_from_csv(filename: str, columns: list[str], required: str | None = None) -> list[dict]:
    df = read_csv_file(filename, columns)

    if required and required in df.columns:
        df = df[df[required].astype(str).str.strip() != ""]

    return df.to_dict("records")


HOF_OVERALL = records_from_csv(
    "overall_results.csv",
    ["season", "winner", "runner_up", "third_place", "note", "status", "source"],
    required="winner",
)

HOF_CUP = records_from_csv(
    "cup_results.csv",
    ["season", "winner", "runner_up", "note", "status", "source"],
    required="winner",
)

HOF_RANDOM = records_from_csv(
    "random_results.csv",
    ["season", "winner", "placement", "note", "status", "source"],
    required="winner",
)


def load_monthly_podiums() -> list[dict]:
    df = read_csv_file(
        "monthly_podiums.csv",
        ["season", "month", "place", "manager", "status", "source"],
    )

    if df.empty:
        return []

    df = df[(df["season"] != "") & (df["month"] != "") & (df["manager"] != "")]
    df["place"] = pd.to_numeric(df["place"], errors="coerce").fillna(0).astype(int)
    df = df[df["place"] > 0]

    return df.to_dict("records")


MONTHLY_PODIUMS = load_monthly_podiums()


def load_official_monthly_titles() -> dict:
    df = read_csv_file(
        "official_monthly_titles.csv",
        ["manager", "monthly_titles", "status", "source"],
    )

    out = {}

    for _, row in df.iterrows():
        manager = clean_cell(row.get("manager"))

        if not manager:
            continue

        try:
            out[manager] = int(float(row.get("monthly_titles") or 0))
        except (TypeError, ValueError):
            out[manager] = 0

    return out


OFFICIAL_MONTHLY_TITLES_RAW = load_official_monthly_titles()


def load_aliases() -> dict:
    df = read_csv_file("aliases.csv", ["canonical_name", "alias"])
    out: dict[str, list[str]] = {}

    for _, row in df.iterrows():
        canonical = clean_cell(row.get("canonical_name"))
        alias = clean_cell(row.get("alias"))

        if not canonical or not alias:
            continue

        out.setdefault(canonical, [])

        if alias not in out[canonical]:
            out[canonical].append(alias)

    return out


HOF_ALIASES = load_aliases()

# Ekstra alias som gjør at FPL-navn, korte navn og lokale navn peker mot samme person.
# Disse ligger også fint å flytte permanent til data/aliases.csv, men ligger her som trygg fallback
# for at kart og meritter ikke skal bomme hvis CSV-en ikke er oppdatert ennå.
FALLBACK_ALIASES = {
    "Adrian Auke": ["Adrian Auke", "Adrian Tangen Auke"],
    "Kevin Jørgensen": ["Kevin Jørgensen", "Kevin Andre Dybfest Jørgensen", "Kevin André Dybfest Jørgensen"],
    "Mattias Pettersen": ["Mattias Pettersen", "Matias Pettersen", "Matias Leander Pettersen"],
    "Oskar Brun": ["Oskar Brun", "Oskar Kristensen Brun"],
    "Kristoffer W Pettersen": ["Kristoffer W Pettersen", "Kristoffer Wollvik Pettersen"],
    "Mats Arntzen": ["Mats Arntzen", "Mats Øyvind Jacobsen Arntzen"],
    "Mikael Eliassen": ["Mikael Eliassen", "Mikael Andre Eliassen", "Mikael André Eliassen"],
    "Remi Kristiansen": ["Remi Kristiansen", "Remi Andre Kristiansen", "Remi André Kristiansen"],
    "Andreas Løkås": ["Andreas Løkås", "Andreas Nikolai Løkås"],
    "Anders Hole": ["Anders Hole"],
    "Øyvind Nordmo Sivertsen": ["Nordmo Sivertsen", "Øyvind Nordmo", "Øyvind Nordmo Sivertsen"],
}

for canonical, aliases in FALLBACK_ALIASES.items():
    HOF_ALIASES.setdefault(canonical, [])
    for alias in aliases:
        if alias not in HOF_ALIASES[canonical]:
            HOF_ALIASES[canonical].append(alias)


TAG_SORT = {
    "Tittelkandidat": 1,
    "Outsider": 2,
    "Dark horse": 3,
    "Stabil traver": 4,
    "Usikkert kort": 5,
    "Rookie": 6,
}


def canonical_hof_name(name: str) -> str:
    norm = normalize_text(name)

    for canonical, aliases in HOF_ALIASES.items():
        if norm == normalize_text(canonical):
            return canonical

        for alias in aliases:
            if norm == normalize_text(alias):
                return canonical

    return name


def hof_key(name: str) -> str:
    return normalize_text(canonical_hof_name(name))


def build_official_monthly_map() -> dict:
    out = {}

    for name, count in OFFICIAL_MONTHLY_TITLES_RAW.items():
        out[hof_key(name)] = int(count)

    return out


def merit_phrase(count: int, singular: str, plural: str | None = None) -> str:
    count = int(count or 0)
    if count <= 0:
        return ""
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural or singular}"


def merit_text(row: dict) -> str:
    parts = []

    items = [
        (row.get("overall_count", 0), "sammenlagt-seier", "sammenlagt-seire"),
        (row.get("overall_runner_up_count", 0), "sammenlagt-sølv", "sammenlagt-sølv"),
        (row.get("overall_third_count", 0), "sammenlagt-bronse", "sammenlagt-bronse"),
        (row.get("cup_count", 0), "cupgull", "cupgull"),
        (row.get("cup_runner_up_count", 0), "cupsølv", "cupsølv"),
        (row.get("monthly_titles", 0), "månedsseier", "månedsseire"),
        (row.get("monthly_silver", 0), "månedssølv", "månedssølv"),
        (row.get("monthly_bronze", 0), "månedsbronse", "månedsbronse"),
        (row.get("random_count", 0), "random-treff", "random-treff"),
    ]

    for count, singular, plural in items:
        phrase = merit_phrase(int(count or 0), singular, plural)
        if phrase:
            parts.append(phrase)

    return ", ".join(parts)


def build_monthly_podium_df() -> pd.DataFrame:
    df = pd.DataFrame(MONTHLY_PODIUMS)

    if df.empty:
        return df

    df["manager"] = df["manager"].apply(canonical_hof_name)
    df["points"] = df["place"].map({1: 6, 2: 2, 3: 1}).fillna(0).astype(int)

    month_order = {
        "August": 1,
        "September": 2,
        "Oktober": 3,
        "November": 4,
        "Desember": 5,
        "Januar": 6,
        "Februar": 7,
        "Mars": 8,
        "April": 9,
        "Mai": 10,
    }

    df["month_order"] = df["month"].map(month_order).fillna(99)
    return df.sort_values(["season", "month_order", "place", "manager"]).reset_index(drop=True)


def build_monthly_medal_table(season_filter: str | None = None) -> pd.DataFrame:
    df = build_monthly_podium_df()

    if df.empty:
        return df

    if season_filter and season_filter != "Alle":
        df = df[df["season"] == season_filter]

    grouped = (
        df.groupby("manager")
        .agg(
            gold=("place", lambda s: int((s == 1).sum())),
            silver=("place", lambda s: int((s == 2).sum())),
            bronze=("place", lambda s: int((s == 3).sum())),
            month_points=("points", "sum"),
            podiums=("place", "count"),
        )
        .reset_index()
    )

    grouped = grouped.sort_values(
        ["month_points", "gold", "silver", "bronze", "manager"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)

    grouped.insert(0, "monthly_rank", range(1, len(grouped) + 1))
    return grouped


def build_monthly_calendar_table(season_filter: str | None = None) -> pd.DataFrame:
    df = build_monthly_podium_df()

    if df.empty:
        return df

    if season_filter and season_filter != "Alle":
        df = df[df["season"] == season_filter]

    grouped = (
        df.groupby(["season", "month_order", "month", "place"])["manager"]
        .apply(lambda values: ", ".join(values))
        .reset_index()
    )

    pivot = grouped.pivot_table(
        index=["season", "month_order", "month"],
        columns="place",
        values="manager",
        aggfunc="first",
    ).reset_index()

    for place in [1, 2, 3]:
        if place not in pivot.columns:
            pivot[place] = ""

    pivot = pivot.rename(columns={
        "season": "season",
        "month": "month",
        1: "winner",
        2: "second_place",
        3: "third_place",
    })

    pivot = pivot.sort_values(["season", "month_order"]).reset_index(drop=True)
    return pivot[["season", "month", "winner", "second_place", "third_place"]]


def build_month_specialist_table() -> pd.DataFrame:
    df = build_monthly_podium_df()

    if df.empty:
        return df

    grouped = (
        df.groupby(["month_order", "month", "manager"])
        .agg(
            month_points=("points", "sum"),
            gold=("place", lambda series: int((series == 1).sum())),
            silver=("place", lambda series: int((series == 2).sum())),
            bronze=("place", lambda series: int((series == 3).sum())),
            podiums=("place", "count"),
        )
        .reset_index()
    )

    rows = []

    for month, month_df in grouped.groupby("month"):
        month_df = month_df.sort_values(
            ["month_points", "gold", "silver", "bronze", "manager"],
            ascending=[False, False, False, False, True],
        ).reset_index(drop=True)

        best_points = int(month_df.iloc[0]["month_points"])
        leaders = month_df[month_df["month_points"] == best_points].copy()

        leader_names = ", ".join(leaders["manager"].tolist())
        gold_total = int(leaders["gold"].sum())
        silver_total = int(leaders["silver"].sum())
        bronze_total = int(leaders["bronze"].sum())
        podium_total = int(leaders["podiums"].sum())

        if len(leaders) > 1:
            comment = "Delt månedskonge"
        else:
            second_points = int(month_df.iloc[1]["month_points"]) if len(month_df) > 1 else 0
            if best_points - second_points >= 4:
                comment = "Tydelig månedskonge"
            else:
                comment = "Knapp ledelse"

        rows.append({
            "month_order": int(month_df.iloc[0]["month_order"]),
            "month": month,
            "king": leader_names,
            "leaders_count": int(len(leaders)),
            "king_points": best_points,
            "gold": gold_total,
            "silver": silver_total,
            "bronze": bronze_total,
            "podiums": podium_total,
            "month_merits": f"{gold_total} gull, {silver_total} sølv, {bronze_total} bronse",
            "comment": comment,
        })

    return pd.DataFrame(rows).sort_values("month_order").reset_index(drop=True)


def build_month_winner_history_table() -> pd.DataFrame:
    df = build_monthly_podium_df()

    if df.empty:
        return df

    winners = df[df["place"].astype(int) == 1].copy()
    if winners.empty:
        return pd.DataFrame(columns=["month", "winners_history"])

    rows = []
    for (month_order, month), month_df in winners.groupby(["month_order", "month"]):
        month_df = month_df.sort_values(["season", "manager"])
        history_parts = []
        for season, season_df in month_df.groupby("season"):
            names = ", ".join(season_df["manager"].tolist())
            history_parts.append(f"{season}: {names}")
        rows.append({
            "month_order": int(month_order),
            "month": month,
            "winners_history": " | ".join(history_parts),
        })

    return pd.DataFrame(rows).sort_values("month_order").reset_index(drop=True)


def build_hof_people() -> pd.DataFrame:
    people = {}

    def ensure_person(name: str):
        if not name:
            return None

        canonical = canonical_hof_name(name)
        key = hof_key(canonical)

        if key not in people:
            people[key] = {
                "key": key,
                "display_name": canonical,
                "overall_count": 0,
                "overall_runner_up_count": 0,
                "overall_third_count": 0,
                "overall_seasons": [],
                "overall_runner_up_seasons": [],
                "overall_third_seasons": [],
                "cup_count": 0,
                "cup_runner_up_count": 0,
                "cup_seasons": [],
                "cup_runner_up_seasons": [],
                "random_count": 0,
                "random_notes": [],
                "monthly_gold_detail": 0,
                "monthly_silver": 0,
                "monthly_bronze": 0,
                "monthly_podiums": 0,
                "monthly_points": 0,
            }

        return people[key]

    for row in HOF_OVERALL:
        winner = ensure_person(row.get("winner"))
        if winner:
            winner["overall_count"] += 1
            note = f"{row['season']}" if not row.get("note") else f"{row['season']} ({row['note']})"
            winner["overall_seasons"].append(note)

        runner = ensure_person(row.get("runner_up"))
        if runner:
            runner["overall_runner_up_count"] += 1
            runner["overall_runner_up_seasons"].append(row["season"])

        third = ensure_person(row.get("third_place"))
        if third:
            third["overall_third_count"] += 1
            third["overall_third_seasons"].append(row["season"])

    for row in HOF_CUP:
        winner = ensure_person(row.get("winner"))
        if winner:
            winner["cup_count"] += 1
            winner["cup_seasons"].append(row["season"])

        runner = ensure_person(row.get("runner_up"))
        if runner:
            runner["cup_runner_up_count"] += 1
            runner["cup_runner_up_seasons"].append(row["season"])

    for row in HOF_RANDOM:
        person = ensure_person(row.get("winner"))
        if person:
            person["random_count"] += 1
            person["random_notes"].append(f"{row['season']} – {row['placement']}")

    monthly_df = build_monthly_podium_df()

    if not monthly_df.empty:
        for _, row in monthly_df.iterrows():
            person = ensure_person(row["manager"])

            if person:
                if int(row["place"]) == 1:
                    person["monthly_gold_detail"] += 1
                elif int(row["place"]) == 2:
                    person["monthly_silver"] += 1
                elif int(row["place"]) == 3:
                    person["monthly_bronze"] += 1

                person["monthly_podiums"] += 1
                person["monthly_points"] += int(row["points"])

    official_monthly = build_official_monthly_map()

    for raw_name in OFFICIAL_MONTHLY_TITLES_RAW:
        ensure_person(raw_name)

    rows = []

    for person in people.values():
        official_titles = official_monthly.get(person["key"], None)
        detail_titles = int(person["monthly_gold_detail"])

        if official_titles is not None:
            monthly_titles = int(official_titles)
        else:
            monthly_titles = detail_titles

        total_titles = (
            int(person["overall_count"])
            + int(person["cup_count"])
            + int(person["random_count"])
            + monthly_titles
        )

        hof_score = (
            int(person["overall_count"]) * 60
            + int(person["overall_runner_up_count"]) * 30
            + int(person["overall_third_count"]) * 16
            + int(person["cup_count"]) * 20
            + int(person["cup_runner_up_count"]) * 8
            + int(person["random_count"]) * 4
            + monthly_titles * 6
            + int(person["monthly_silver"]) * 2
            + int(person["monthly_bronze"]) * 1
        )

        out = {
            "key": person["key"],
            "display_name": person["display_name"],
            "overall_count": int(person["overall_count"]),
            "overall_runner_up_count": int(person["overall_runner_up_count"]),
            "overall_third_count": int(person["overall_third_count"]),
            "overall_seasons": ", ".join(person["overall_seasons"]),
            "overall_runner_up_seasons": ", ".join(person["overall_runner_up_seasons"]),
            "overall_third_seasons": ", ".join(person["overall_third_seasons"]),
            "cup_count": int(person["cup_count"]),
            "cup_runner_up_count": int(person["cup_runner_up_count"]),
            "cup_seasons": ", ".join(person["cup_seasons"]),
            "cup_runner_up_seasons": ", ".join(person["cup_runner_up_seasons"]),
            "random_count": int(person["random_count"]),
            "random_notes": ", ".join(person["random_notes"]),
            "monthly_titles": int(monthly_titles),
            "monthly_silver": int(person["monthly_silver"]),
            "monthly_bronze": int(person["monthly_bronze"]),
            "monthly_podiums": int(person["monthly_podiums"]),
            "monthly_points": int(person["monthly_points"]),
            "total_titles": int(total_titles),
            "hof_score": int(hof_score),
        }

        out["merits"] = merit_text(out)
        rows.append(out)

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.sort_values(
            [
                "hof_score",
                "overall_count",
                "overall_runner_up_count",
                "cup_count",
                "monthly_titles",
                "display_name",
            ],
            ascending=[False, False, False, False, False, True],
        ).reset_index(drop=True)

        df.insert(0, "hof_rank", range(1, len(df) + 1))

    return df


def enrich_summary_with_hof(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return summary_df

    hof_df = build_hof_people()

    if hof_df.empty:
        summary_df["monthly_titles"] = 0
        summary_df["merits"] = ""
        summary_df["hof_score"] = 0
        return summary_df

    hof_index = hof_df.set_index("key")

    hof_columns = [
        "monthly_titles",
        "monthly_silver",
        "monthly_bronze",
        "overall_count",
        "overall_runner_up_count",
        "overall_third_count",
        "cup_count",
        "cup_runner_up_count",
        "random_count",
        "hof_score",
    ]

    collected = {column: [] for column in hof_columns}
    merits = []

    for _, row in summary_df.iterrows():
        key = hof_key(row["manager"])

        if key in hof_index.index:
            hof_row = hof_index.loc[key]
            merits.append(hof_row["merits"])
            for column in hof_columns:
                collected[column].append(int(hof_row.get(column, 0) or 0))
        else:
            merits.append("")
            for column in hof_columns:
                collected[column].append(0)

    summary_df = summary_df.copy()
    for column, values in collected.items():
        summary_df[column] = values
    summary_df["merits"] = merits

    return summary_df


# -----------------------------
# Henting av liga
# -----------------------------

def normalize_manager_row(row: dict, source: str) -> dict:
    entry = row.get("entry") or row.get("entry_id") or row.get("id")

    entry_name = (
        row.get("entry_name")
        or row.get("name")
        or row.get("team_name")
        or "Ukjent lag"
    )

    player_name = (
        row.get("player_name")
        or row.get("player")
        or row.get("manager_name")
        or "Ukjent manager"
    )

    first_name = row.get("player_first_name")
    last_name = row.get("player_last_name")

    if player_name == "Ukjent manager" and (first_name or last_name):
        player_name = f"{first_name or ''} {last_name or ''}".strip()

    return {
        "source": source,
        "entry": entry,
        "player_name": player_name,
        "entry_name": entry_name,
        "rank": row.get("rank"),
        "last_rank": row.get("last_rank"),
        "event_total": row.get("event_total"),
        "total": row.get("total"),
        "joined_time": row.get("joined_time"),
        "search_text": normalize_text(f"{player_name} {entry_name} {entry}"),
        "raw": row,
    }


@st.cache_data(ttl=300)
def get_league_managers(league_id: int) -> tuple[dict | None, list[dict], dict]:
    league_info = None
    managers_by_entry = {}

    debug = {
        "league_id": league_id,
        "standings_pages": 0,
        "new_entries_pages": 0,
        "standings_count": 0,
        "new_entries_count": 0,
        "total_unique_managers": 0,
        "errors": [],
    }

    page = 1

    while page <= 100:
        path = (
            f"/leagues-classic/{league_id}/standings/"
            f"?page_standings={page}&page_new_entries=1"
        )

        try:
            data = get_json(path)
        except requests.exceptions.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                debug["errors"].append(f"Tabell ga 404 for liga-ID {league_id}")
                break
            raise error

        league_info = data.get("league") or league_info
        standings = data.get("standings", {}) or {}
        results = standings.get("results", []) or []

        debug["standings_pages"] += 1
        debug["standings_count"] += len(results)

        for row in results:
            manager = normalize_manager_row(row, "tabell")
            entry = manager.get("entry")

            if entry:
                managers_by_entry[entry] = manager

        if not standings.get("has_next"):
            break

        page += 1

    page = 1

    while page <= 100:
        path = (
            f"/leagues-classic/{league_id}/standings/"
            f"?page_standings=1&page_new_entries={page}"
        )

        try:
            data = get_json(path)
        except requests.exceptions.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                debug["errors"].append(f"Påmeldte ga 404 for liga-ID {league_id}")
                break
            raise error

        league_info = data.get("league") or league_info
        new_entries = data.get("new_entries", {}) or {}
        results = new_entries.get("results", []) or []

        debug["new_entries_pages"] += 1
        debug["new_entries_count"] += len(results)

        for row in results:
            manager = normalize_manager_row(row, "påmeldt")
            entry = manager.get("entry")

            if entry and entry not in managers_by_entry:
                managers_by_entry[entry] = manager

        if not new_entries.get("has_next"):
            break

        page += 1

    managers = list(managers_by_entry.values())
    debug["total_unique_managers"] = len(managers)

    return league_info, managers, debug


# -----------------------------
# Historikkmodell
# -----------------------------

def rank_score(rank: int | float | None) -> float:
    if rank is None or pd.isna(rank):
        return 0

    try:
        rank = float(rank)
    except ValueError:
        return 0

    if rank <= 0:
        return 0

    score = 100 - 10 * math.log10(rank)
    return max(0, min(100, score))


def safe_mean(values: list[float]) -> float:
    values = [value for value in values if value is not None and not pd.isna(value)]

    if not values:
        return 0

    return sum(values) / len(values)


def tier_from_score(score: float) -> str:
    if score >= 60:
        return "Elite"
    if score >= 55:
        return "Meget sterk"
    if score >= 50:
        return "Sterk"
    if score >= 45:
        return "Solid"
    if score >= 40:
        return "Midtable"
    return "Rookie"


def trend_string(seasons: list[dict], limit: int = 3) -> str:
    seasons = seasons[-limit:]
    parts = []
    previous_rank = None

    for season in seasons:
        season_name = str(season.get("season_name", ""))
        rank = season.get("rank")

        if previous_rank is None:
            arrow = "⚪"
        elif rank < previous_rank:
            arrow = "🟢"
        elif rank > previous_rank:
            arrow = "🔴"
        else:
            arrow = "⚪"

        parts.append(f"{season_name}: {format_rank(rank)} {arrow}")
        previous_rank = rank

    return "  →  ".join(parts)


def manager_tag(row: dict) -> str:
    seasons = int(row.get("seasons") or 0)
    total_rating = float(row.get("total_rating") or 0)

    best_rank = row.get("best_rank_num")
    last_rank = row.get("last_season_rank_num")
    avg3 = row.get("avg_rank_last_3_num")
    avg5 = row.get("avg_rank_last_5_num")

    top_100k = int(row.get("top_100k_seasons") or 0)
    top_500k = int(row.get("top_500k_seasons") or 0)

    last_2_good = int(row.get("last_2_good_seasons") or 0)
    weak_before_last_2 = bool(row.get("weak_before_last_2") or False)

    if seasons <= 2:
        return "Rookie"

    if total_rating >= 56 or (
        avg3 is not None
        and avg3 <= 350_000
        and top_100k >= 2
    ):
        return "Tittelkandidat"

    if top_100k >= 3 or top_500k >= 6:
        return "Outsider"

    if (
        best_rank is not None
        and best_rank <= 100_000
        and (
            avg3 is None
            or avg3 >= 750_000
            or last_rank is None
            or last_rank >= 1_000_000
        )
    ):
        return "Dark horse"

    if last_2_good >= 2 and weak_before_last_2:
        return "Dark horse"

    if total_rating < 42:
        return "Usikkert kort"

    if last_rank is not None and last_rank > 2_000_000:
        return "Usikkert kort"

    if avg3 is not None and avg3 > 1_700_000:
        return "Usikkert kort"

    if seasons >= 5 and avg5 is not None and avg5 <= 1_500_000:
        return "Stabil traver"

    return "Usikkert kort"


def build_summary_row(manager: dict, history: dict) -> dict:
    past = history.get("past", []) or []
    seasons = []

    for season in past:
        rank = season.get("rank")
        total_points = season.get("total_points")
        season_name = season.get("season_name")

        if rank is None:
            continue

        seasons.append({
            "season_name": season_name,
            "rank": int(rank),
            "total_points": int(total_points) if total_points is not None else None,
            "score": rank_score(rank),
        })

    seasons = sorted(seasons, key=lambda x: x["season_name"] or "")

    last_2 = seasons[-2:]
    last_3 = seasons[-3:]
    last_5 = seasons[-5:]

    ranks = [season["rank"] for season in seasons]
    ranks_last_3 = [season["rank"] for season in last_3]
    ranks_last_5 = [season["rank"] for season in last_5]

    best_rank_num = min(ranks) if ranks else None
    best_seasons = [season for season in seasons if season["rank"] == best_rank_num] if best_rank_num else []
    best_season = best_seasons[0]["season_name"] if best_seasons else None

    last_season = seasons[-1] if seasons else None
    last_season_rank_num = last_season["rank"] if last_season else None

    avg_rank_last_3_num = round(safe_mean(ranks_last_3)) if ranks_last_3 else None
    avg_rank_last_5_num = round(safe_mean(ranks_last_5)) if ranks_last_5 else None

    scores_last_2 = [season["score"] for season in last_2]
    scores_last_3 = [season["score"] for season in last_3]
    scores_last_5 = [season["score"] for season in last_5]

    consistency_last_5 = 0

    if last_5:
        consistency_last_5 = 100 * sum(
            1 for season in last_5 if season["rank"] <= 500_000
        ) / len(last_5)

    best_score = rank_score(best_rank_num)
    recent_score = safe_mean(scores_last_2)
    last_3_score = safe_mean(scores_last_3)
    last_5_score = safe_mean(scores_last_5)
    consistency_score = consistency_last_5

    top_100k_seasons = sum(1 for rank in ranks if rank <= 100_000)
    top_500k_seasons = sum(1 for rank in ranks if rank <= 500_000)

    top_100k_rate = top_100k_seasons / len(seasons) * 100 if seasons else 0
    top_500k_rate = top_500k_seasons / len(seasons) * 100 if seasons else 0

    last_2_good_seasons = sum(1 for season in last_2 if season["rank"] <= 500_000)
    before_last_2 = seasons[:-2]

    weak_before_last_2 = (
        len(before_last_2) >= 2
        and sum(1 for season in before_last_2 if season["rank"] <= 500_000) == 0
    )

    total_rating = (
        0.45 * last_3_score
        + 0.15 * recent_score
        + 0.15 * last_5_score
        + 0.10 * best_score
        + 0.07 * consistency_score
        + 0.05 * top_100k_rate
        + 0.03 * top_500k_rate
    )

    row = {
        "manager": manager.get("player_name"),
        "team": manager.get("entry_name"),
        "entry": manager.get("entry"),
        "search_text": normalize_text(
            f"{manager.get('player_name')} {manager.get('entry_name')} {manager.get('entry')}"
        ),
        "seasons": len(seasons),
        "last_season": last_season["season_name"] if last_season else None,
        "last_season_rank_num": last_season_rank_num,
        "last_season_rank": format_rank(last_season_rank_num),
        "last_season_points": last_season["total_points"] if last_season else None,
        "best_rank_num": best_rank_num,
        "best_rank": format_rank(best_rank_num),
        "best_season": best_season,
        "avg_rank_last_3_num": avg_rank_last_3_num,
        "avg_rank_last_3": format_rank(avg_rank_last_3_num),
        "avg_rank_last_5_num": avg_rank_last_5_num,
        "avg_rank_last_5": format_rank(avg_rank_last_5_num),
        "last_3_ranks": " / ".join(format_rank(season["rank"]) for season in last_3),
        "trend": trend_string(seasons, limit=3),
        "top_100k_seasons": top_100k_seasons,
        "top_500k_seasons": top_500k_seasons,
        "last_2_good_seasons": last_2_good_seasons,
        "weak_before_last_2": weak_before_last_2,
        "best_score": round(best_score, 1),
        "recent_score": round(recent_score, 1),
        "last_3_score": round(last_3_score, 1),
        "last_5_score": round(last_5_score, 1),
        "consistency_score": round(consistency_score, 1),
        "total_rating": round(total_rating, 1),
        "tier": tier_from_score(total_rating),
    }

    row["tag"] = manager_tag(row)
    row["tag_sort"] = TAG_SORT.get(row["tag"], 99)
    return row


def build_history_tables(managers: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    season_rows = []
    errors = []

    if not managers:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    progress = st.progress(0)
    status = st.empty()

    for i, manager in enumerate(managers):
        entry_id = manager.get("entry")
        name = manager.get("player_name", "Ukjent manager")

        status.write(f"Henter historikk for {name} ({i + 1}/{len(managers)})")

        try:
            history = get_entry_history(int(entry_id))
            summary_rows.append(build_summary_row(manager, history))

            for season in history.get("past", []) or []:
                season_rows.append({
                    "manager": manager.get("player_name"),
                    "team": manager.get("entry_name"),
                    "entry": entry_id,
                    "season_name": season.get("season_name"),
                    "total_points": season.get("total_points"),
                    "rank_num": season.get("rank"),
                    "rank": format_rank(season.get("rank")),
                })

        except Exception as error:
            errors.append({
                "manager": name,
                "team": manager.get("entry_name"),
                "entry": entry_id,
                "error": str(error),
            })

        progress.progress((i + 1) / len(managers))

    progress.empty()
    status.empty()

    summary_df = pd.DataFrame(summary_rows)
    seasons_df = pd.DataFrame(season_rows)
    errors_df = pd.DataFrame(errors)

    if not summary_df.empty:
        summary_df = enrich_summary_with_hof(summary_df)
        summary_df["peak_sort"] = summary_df["best_rank_num"].fillna(999_999_999)

        summary_df = summary_df.sort_values(
            ["peak_sort", "total_rating"],
            ascending=[True, False],
        ).reset_index(drop=True)

    if not seasons_df.empty:
        seasons_df = seasons_df.sort_values(["manager", "season_name"]).reset_index(drop=True)

    return summary_df, seasons_df, errors_df


# -----------------------------
# Oddsmodell
# -----------------------------

def plackett_luce_top3_probs(probs: list[float]) -> list[float]:
    """Exact top-3 probabilities for a Plackett-Luce field."""
    n = len(probs)
    out = [0.0 for _ in probs]

    for i in range(n):
        out[i] += probs[i]

    for first in range(n):
        p_first = probs[first]
        rest_after_first = 1.0 - p_first
        if rest_after_first <= 0:
            continue
        for i in range(n):
            if i == first:
                continue
            out[i] += p_first * probs[i] / rest_after_first

    for first in range(n):
        p_first = probs[first]
        rest_after_first = 1.0 - p_first
        if rest_after_first <= 0:
            continue
        for second in range(n):
            if second == first:
                continue
            p_second = p_first * probs[second] / rest_after_first
            rest_after_second = rest_after_first - probs[second]
            if rest_after_second <= 0:
                continue
            for i in range(n):
                if i == first or i == second:
                    continue
                out[i] += p_second * probs[i] / rest_after_second

    return [min(max(value, 0.0), 0.98) for value in out]



def recommended_stake_by_odds(odds: float | None, market: str = "winner") -> int:
    """Social stake limits for the internal Lofthus Road Open odds game.

    The limits keep big longshot payouts fun, but stop anyone from placing
    ruinous stakes on 50.00+ prices.
    """
    if odds is None or pd.isna(odds):
        return 0

    odds = float(odds)

    if market == "top3":
        if odds <= 2.99:
            return 150
        if odds <= 5.99:
            return 100
        if odds <= 11.99:
            return 50
        if odds <= 24.99:
            return 25
        return 10

    # Winner market.
    if odds <= 5.99:
        return 200
    if odds <= 9.99:
        return 150
    if odds <= 19.99:
        return 75
    if odds <= 39.99:
        return 50
    if odds <= 79.99:
        return 20
    if odds <= 149.99:
        return 10
    return 5


def build_preseason_odds(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Lofthus Road Open bookmaker-ish preseason market.

    This is intentionally NOT a pure fair-probability model. The goal is a
    playable internal market:
    - the known elite should be protected hard, with the favourite around 3-ish;
    - the field still spreads naturally down the list;
    - top-3 prices must not collapse into 1.14 nonsense;
    - odds are for internal fun, not a hard financial model.
    """
    if summary_df.empty:
        return pd.DataFrame()

    df = summary_df.copy()

    def series_num(column: str, default: float = 0.0) -> pd.Series:
        if column not in df.columns:
            return pd.Series([default] * len(df), index=df.index, dtype="float")
        return pd.to_numeric(df[column], errors="coerce").fillna(default).astype(float)

    total_rating = series_num("total_rating")
    last_3_score = series_num("last_3_score")
    last_5_score = series_num("last_5_score")
    recent_score = series_num("recent_score")
    best_score = series_num("best_score")
    consistency_score = series_num("consistency_score")
    hof_score = series_num("hof_score")
    monthly_titles = series_num("monthly_titles")
    overall_titles = series_num("overall_count")
    overall_silver = series_num("overall_runner_up_count")
    overall_bronze = series_num("overall_third_count")
    cup_gold = series_num("cup_count")
    cup_silver = series_num("cup_runner_up_count")
    seasons = series_num("seasons")
    top_100k = series_num("top_100k_seasons")
    top_500k = series_num("top_500k_seasons")
    last_rank = series_num("last_season_rank_num", 9_999_999)
    avg3_rank = series_num("avg_rank_last_3_num", 9_999_999)

    # Betting strength. Recent FPL years drive the model, but elite peak,
    # consistency and LRO track record still matter.
    market_score = (
        0.30 * total_rating
        + 0.30 * last_3_score
        + 0.12 * recent_score
        + 0.10 * last_5_score
        + 0.08 * best_score
        + 0.06 * consistency_score
        + 0.04 * top_100k.clip(0, 6) * 6
    )

    # Lofthus Road Open-respect bonus. We deliberately avoid monthly silver/bronze
    # here, because that part of the old data is incomplete. Full-season medals,
    # cupgull and official monthly wins can move the price a little; FPL-history
    # still drives the odds.
    market_score += overall_titles.clip(0, 3) * 0.75
    market_score += overall_silver.clip(0, 3) * 0.32
    market_score += overall_bronze.clip(0, 3) * 0.16
    market_score += cup_gold.clip(0, 4) * 0.24
    market_score += cup_silver.clip(0, 4) * 0.10
    market_score += monthly_titles.clip(0, 6) * 0.10
    market_score += top_500k.clip(0, 12) * 0.06

    # Human bookmaker-style adjustments.
    market_score = market_score.where(seasons > 2, market_score - 2.2)
    market_score = market_score.where(last_rank <= 2_000_000, market_score - 1.4)
    market_score = market_score.where(avg3_rank <= 1_700_000, market_score - 1.4)
    market_score = market_score.where(avg3_rank <= 2_500_000, market_score - 1.0)

    df["market_score"] = market_score.round(2)

    max_score = float(market_score.max()) if len(market_score) else 0.0

    # Start from a score-based price ladder, not a fully normalised probability
    # model. This gives the right bookmaker-feel for a social market.
    base_favourite_odds = 3.25
    spread = 8.8
    df["odds_float"] = base_favourite_odds * ((max_score - market_score) / spread).apply(math.exp)

    # Extra protection on obvious elite profiles. We would rather be a bit short
    # on the proven best players than give away 5-6 odds before the field is full.
    elite_mask = (
        (avg3_rank <= 350_000)
        | (top_100k >= 4)
        | (((overall_titles * 2 + overall_silver + cup_gold) >= 2) & (top_500k >= 5))
    )
    df.loc[elite_mask, "odds_float"] *= 0.88

    # Dark horses can still be tempting, but don't make weak recent form too cheap.
    df.loc[avg3_rank > 1_500_000, "odds_float"] *= 1.18
    df.loc[last_rank > 2_500_000, "odds_float"] *= 1.12
    df.loc[seasons <= 2, "odds_float"] *= 1.18

    # Guardrails. Known elite starts around 3, longshots are allowed to drift.
    df["odds_float"] = df["odds_float"].clip(lower=3.00, upper=251.00)

    # Keep the very top compact. If there are several genuinely strong managers,
    # they should not all drift to 10+ before the season starts.
    df = df.sort_values("odds_float", ascending=True).reset_index(drop=True)
    top_caps = {0: 3.25, 1: 4.00, 2: 4.75, 3: 5.75, 4: 7.25}
    for idx, cap in top_caps.items():
        if idx < len(df) and float(df.loc[idx, "odds_float"]) > cap:
            df.loc[idx, "odds_float"] = cap

    # Avoid a completely flat top: later rows must be at least marginally longer.
    for idx in range(1, len(df)):
        min_allowed = float(df.loc[idx - 1, "odds_float"]) + 0.10
        if float(df.loc[idx, "odds_float"]) < min_allowed:
            df.loc[idx, "odds_float"] = min_allowed

    # Top-3 odds derived from vinnerodds, but softened for a 37-62-player FPL field.
    # This is a practical market relation: strong favourites can be 1.70-ish,
    # but no one should be 1.14 before GW1.
    win_odds = pd.to_numeric(df["odds_float"], errors="coerce").fillna(251.0)
    top3_odds = []
    for odd in win_odds:
        odd = float(odd)
        implied = 1 / max(odd, 1.01)
        # Multiplying implied win chance gives a rough top-3 chance. The factor
        # slowly falls as odds rise, preventing silly low top-3 prices on outsiders.
        factor = 2.25 if odd <= 5 else 2.05 if odd <= 10 else 1.85 if odd <= 25 else 1.65
        top3_prob = implied * factor
        top3_prob = min(max(top3_prob, 0.006), 0.56)
        # Tiny margin, then guardrails.
        top3_odds.append(min(max(1 / (top3_prob * 1.04), 1.70), 151.00))

    df["top3_odds_float"] = pd.Series(top3_odds, index=df.index)

    # Final display columns.
    df["odds"] = df["odds_float"].apply(format_odds)
    df["top3_odds"] = df["top3_odds_float"].apply(format_odds)
    df["winner_max_stake"] = df["odds_float"].apply(lambda value: recommended_stake_by_odds(value, "winner"))
    df["top3_max_stake"] = df["top3_odds_float"].apply(lambda value: recommended_stake_by_odds(value, "top3"))
    df["winner_max_payout"] = (df["winner_max_stake"] * df["odds_float"]).round(0).astype(int)
    df["top3_max_payout"] = (df["top3_max_stake"] * df["top3_odds_float"]).round(0).astype(int)

    df = df.sort_values("odds_float", ascending=True).reset_index(drop=True)
    df.insert(0, "odds_rank", range(1, len(df) + 1))

    return df

# -----------------------------
# Navnesøk
# -----------------------------

def smart_match(summary_df: pd.DataFrame, query: str) -> tuple[pd.Series | None, float]:
    if summary_df.empty:
        return None, 0

    query_norm = normalize_text(query)
    query_tokens = [token for token in query_norm.split() if len(token) > 1]

    if not query_tokens:
        return None, 0

    candidates = summary_df.copy()

    if "search_text" not in candidates.columns:
        candidates["search_text"] = (
            candidates["manager"].astype(str)
            + " "
            + candidates["team"].astype(str)
            + " "
            + candidates["entry"].astype(str)
        ).apply(normalize_text)

    scored = []

    for index, row in candidates.iterrows():
        manager_norm = normalize_text(row.get("manager", ""))
        team_norm = normalize_text(row.get("team", ""))
        text = row.get("search_text", "")
        text_tokens = set(text.split())

        score = 0.0

        if query_norm == manager_norm:
            score = 100.0
        elif query_norm == team_norm:
            score = 98.0
        elif query_norm in text:
            score = 94.0
        elif all(token in text_tokens for token in query_tokens):
            score = 90.0
        elif len(query_tokens) >= 3 and sum(token in text_tokens for token in query_tokens) >= len(query_tokens) - 1:
            score = 88.0
        elif len(query_tokens) == 1 and query_tokens[0] in text_tokens:
            score = 82.0
        else:
            fuzzy = max(
                SequenceMatcher(None, query_norm, manager_norm).ratio(),
                SequenceMatcher(None, query_norm, team_norm).ratio(),
            ) * 100

            if fuzzy >= 90:
                score = fuzzy

        if score > 0:
            scored.append((score, index))

    if not scored:
        return None, 0

    scored = sorted(scored, reverse=True, key=lambda item: item[0])
    best_score, best_index = scored[0]

    threshold = 88 if len(query_tokens) > 1 else 78

    if best_score < threshold:
        return None, round(best_score, 1)

    return candidates.loc[best_index], round(best_score, 1)


# -----------------------------
# H2H
# -----------------------------

def num(row: pd.Series, key: str, default: float = 999_999_999) -> float:
    value = row.get(key, default)

    if value is None or pd.isna(value):
        return default

    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def compact_profile(row: pd.Series) -> str:
    return (
        f"beste {row['best_rank']}, "
        f"snitt siste 3 {row['avg_rank_last_3']}, "
        f"{int(row['top_100k_seasons'])} topp 100k"
    )


def reason_bits(a: pd.Series, b: pd.Series, max_items: int = 1) -> str:
    bits = []

    if num(a, "avg_rank_last_3_num") < num(b, "avg_rank_last_3_num"):
        bits.append("bedre siste tre sesonger")

    if num(a, "last_season_rank_num") < num(b, "last_season_rank_num"):
        bits.append("bedre sist sesong")

    if num(a, "best_rank_num") < num(b, "best_rank_num"):
        bits.append("høyere toppnivå")

    if int(a.get("top_100k_seasons") or 0) > int(b.get("top_100k_seasons") or 0):
        bits.append("flere topp 100k")

    if not bits:
        bits.append("sterkere profil")

    return ", ".join(bits[:max_items])


def h2h_reason(player: pd.Series, opponent: pd.Series) -> str:
    if float(player["total_rating"]) >= float(opponent["total_rating"]):
        return f"Favoritt: {reason_bits(player, opponent)}."

    return f"Underdog: {opponent['manager']} har {reason_bits(opponent, player)}."


def group_reason(player: pd.Series, ordered_players: list[pd.Series], index: int) -> str:
    total = len(ordered_players)

    if index == 0:
        next_player = ordered_players[1]
        return f"Favoritt: {reason_bits(player, next_player)}."

    if index == total - 1:
        previous_player = ordered_players[index - 1]
        return f"Svakest i feltet: {previous_player['manager']} har {reason_bits(previous_player, player)}."

    above = ordered_players[index - 1]
    below = ordered_players[index + 1]
    return f"Bak {above['manager']}, foran {below['manager']}."


def h2h_odds(a: pd.Series, b: pd.Series) -> tuple[float, float]:
    diff = float(a["total_rating"]) - float(b["total_rating"])
    raw_a = 1 / (1 + math.exp(-diff / 6.0))

    p_a = 0.25 * 0.50 + 0.75 * raw_a
    p_b = 1 - p_a

    margin = 1.06

    odds_a = 1 / (p_a * margin)
    odds_b = 1 / (p_b * margin)

    return min(max(odds_a, 1.18), 4.25), min(max(odds_b, 1.18), 4.25)


def group_odds(players: list[pd.Series]) -> list[dict]:
    scores = [float(player["total_rating"]) for player in players]
    max_score = max(scores)

    temperature = 6.5

    weights = [math.exp((score - max_score) / temperature) for score in scores]
    total_weight = sum(weights)
    skill_probs = [weight / total_weight for weight in weights]

    n = len(players)
    equal_prob = 1 / n

    random_blend = 0.35
    margin = 1.08

    raw_rows = []

    for player, skill_prob in zip(players, skill_probs):
        probability = random_blend * equal_prob + (1 - random_blend) * skill_prob
        odds = min(max(1 / (probability * margin), 1.25), 12.00)

        raw_rows.append({
            "player": player,
            "odds_float": odds,
        })

    raw_rows = sorted(raw_rows, key=lambda row: row["odds_float"])
    ordered_players = [row["player"] for row in raw_rows]

    rows = []

    for index, item in enumerate(raw_rows):
        player = item["player"]
        odds = item["odds_float"]

        rows.append({
            "Rangering": index + 1,
            "Manager": player["manager"],
            "Lagnavn": player["team"],
            "Odds": format_odds(odds),
            "Beste plassering": player["best_rank"],
            "Snitt siste 3": player["avg_rank_last_3"],
            "Utvikling": player["trend"],
            "Begrunnelse": group_reason(player, ordered_players, index),
            "Profil": compact_profile(player),
        })

    return rows


def analyze_markets(summary_df: pd.DataFrame, text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    market_rows = []
    missing_rows = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        names = [
            part.strip()
            for part in re.split(r"\s+vs\s+", line, flags=re.IGNORECASE)
            if part.strip()
        ]

        if len(names) < 2:
            continue

        matched = []

        for name in names:
            row, score = smart_match(summary_df, name)

            if row is None:
                missing_rows.append({
                    "Søk": name,
                    "Status": "Ikke funnet / ikke påmeldt",
                })
            else:
                matched.append(row)

        if len(matched) != len(names):
            continue

        if len(matched) == 2:
            a, b = matched
            odds_a, odds_b = h2h_odds(a, b)

            h2h_rows = []

            for player, opponent, odds in [(a, b, odds_a), (b, a, odds_b)]:
                h2h_rows.append({
                    "Rangering": None,
                    "Manager": player["manager"],
                    "Lagnavn": player["team"],
                    "Odds": format_odds(odds),
                    "Beste plassering": player["best_rank"],
                    "Snitt siste 3": player["avg_rank_last_3"],
                    "Utvikling": player["trend"],
                    "Begrunnelse": h2h_reason(player, opponent),
                    "Profil": compact_profile(player),
                    "odds_float": odds,
                })

            h2h_rows = sorted(h2h_rows, key=lambda row: row["odds_float"])

            for index, row in enumerate(h2h_rows):
                row["Rangering"] = index + 1
                row.pop("odds_float", None)
                market_rows.append(row)

        else:
            market_rows.extend(group_odds(matched))

    return pd.DataFrame(market_rows), pd.DataFrame(missing_rows)




# -----------------------------
# Visning og sesongradar
# -----------------------------

TIER_SORT = {
    "Elite": 1,
    "Meget sterk": 2,
    "Sterk": 3,
    "Solid": 4,
    "Midtable": 5,
    "Rookie": 6,
}


def add_sortable_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Usynlige sorteringsprefikser: gir riktig sortering ved kolonneklikk uten synlige 01/02-tall.
    invisible_prefixes = {
        1: "\u200b",
        2: "\u200c",
        3: "\u200d",
        4: "\u2060",
        5: "\u2061",
        6: "\u2062",
        99: "\uffff",
    }

    def tag_value(value: str) -> str:
        if not value or pd.isna(value):
            return ""
        return f"{invisible_prefixes.get(TAG_SORT.get(str(value), 99), '')}{value}"

    def tier_value(value: str) -> str:
        if not value or pd.isna(value):
            return ""
        return f"{invisible_prefixes.get(TIER_SORT.get(str(value), 99), '')}{value}"

    if "tag" in df.columns:
        df["tag_display"] = df["tag"].apply(tag_value)

    if "tier" in df.columns:
        df["tier_display"] = df["tier"].apply(tier_value)

    return df


def clean_invisible(value: Any) -> str:
    return str(value or "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\u2060", "").replace("\u2061", "").replace("\u2062", "").replace("\uffff", "")


def medal_for_position(position: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(int(position), "")


def add_podium_column(df: pd.DataFrame, column_name: str = "podium") -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    df[column_name] = [medal_for_position(index + 1) for index in range(len(df))]
    return df


def add_medal_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)
    df["gold_col"] = ["🥇" if index == 0 else "" for index in range(len(df))]
    df["silver_col"] = ["🥈" if index == 1 else "" for index in range(len(df))]
    df["bronze_col"] = ["🥉" if index == 2 else "" for index in range(len(df))]
    return df


def format_rank_with_season(rank: int | float | None, season: str | None = None) -> str:
    formatted = format_rank(rank)
    if not formatted:
        return ""
    if season:
        return f"{formatted} ({season})"
    return formatted


def make_numeric_display(df: pd.DataFrame, source: str, target: str) -> pd.DataFrame:
    df = df.copy()
    df[target] = pd.to_numeric(df.get(source), errors="coerce")
    df.loc[df[target] >= 999_999_999, target] = pd.NA
    return df




def form_curve_badge(delta: Any, big_threshold: int = 5) -> tuple[str, int]:
    if delta is None or pd.isna(delta):
        return "⚪ ━", 0

    try:
        delta_int = int(delta)
    except (TypeError, ValueError):
        return "⚪ ━", 0

    if delta_int >= big_threshold:
        return f"🟢 ↑ {delta_int}", 2
    if delta_int > 0:
        return f"🔵 ↗ {delta_int}", 1
    if delta_int <= -big_threshold:
        return f"🔴 ↓ {abs(delta_int)}", -2
    if delta_int < 0:
        return f"🟡 ↘ {abs(delta_int)}", -1
    return "⚪ ━", 0


def render_league_table_component(table_df: pd.DataFrame, has_live_table: bool):
    rows = []
    n = max(len(table_df), 1)
    big_threshold = max(5, round(n * 0.15))

    for fallback_index, row in table_df.reset_index(drop=True).iterrows():
        form_text, form_sort = form_curve_badge(row.get("form_delta"), big_threshold)
        rows.append({
            "rank": clean_cell(row.get("rank_display")),
            "rankValue": None if pd.isna(row.get("rank_num")) else float(row.get("rank_num")),
            "fallbackPosition": int(fallback_index + 1),
            "manager": clean_cell(row.get("player_name")),
            "team": clean_cell(row.get("entry_name")),
            "eventPoints": None if pd.isna(row.get("event_total_num")) else int(row.get("event_total_num")),
            "totalPoints": None if pd.isna(row.get("total_num")) else int(row.get("total_num")),
            "form": form_text,
            "formSort": form_sort,
        })

    rows_json = json.dumps(rows, ensure_ascii=False)
    default_sort = "rankValue" if has_live_table else "manager"
    default_dir = "asc"

    component_html = f'''
    <div id="lro-league-table" class="lro-table-wrap">
      <div class="lro-table-note">Trykk på kolonneoverskriftene for å sortere.</div>
      <table class="lro-table">
        <thead>
          <tr>
            <th data-key="rankValue" class="sortable">Plassering</th>
            <th data-key="manager" class="sortable">Manager</th>
            <th data-key="team" class="sortable">Lagnavn</th>
            <th data-key="eventPoints" class="sortable">Rundepoeng</th>
            <th data-key="totalPoints" class="sortable">Poeng totalt</th>
            <th data-key="formSort" class="sortable">Formkurve</th>
          </tr>
        </thead>
        <tbody id="lro-table-body"></tbody>
      </table>
    </div>
    <style>
      .lro-table-wrap {{font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; width:100%; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:12px;}}
      .lro-table-note {{font-size: 13px; color: #64748b; margin: 0 0 10px 0;}}
      .lro-table {{border-collapse: collapse; width: 100%; min-width: 820px; font-size: 12.6px; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; background:white;}}
      .lro-table th {{text-align: left; background: #0f172a; color: #ffffff; padding: 7px 8px; border-bottom: 1px solid #0f172a; cursor: pointer; user-select: none; white-space: nowrap; font-size:10.5px; text-transform:uppercase; letter-spacing:.055em;}}
      .lro-table td {{padding: 7px 8px; border-bottom: 1px solid #eef2f7; color: #0f172a; vertical-align: top; line-height:1.35;}}
      .lro-table tr:hover td {{background: #f1f5f9;}}
      .rank-cell {{font-weight: 850; white-space: nowrap;}}
      .sort-mark {{margin-left: 6px; font-size: 11px; color: #b91c1c;}}
      .lro-table tr:nth-child(even) td {{background:#f8fafc;}}
      .rank-number {{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        min-width:28px;
        height:28px;
        border-radius:999px;
        background:#eef2f7;
        color:#111827;
        font-weight:900;
        font-variant-numeric:tabular-nums;
      }}
      @media (max-width: 760px) {{
        .lro-table-wrap, .lro-history-wrap, .lro-hof-wrap {{overflow-x:auto; max-width:100%;}}
        .lro-table {{min-width: 780px; font-size: 11.2px;}}
        .lro-table th {{font-size: 9.4px; padding: 6px 7px;}}
        .lro-table td {{padding: 6px 7px;}}
        .merits-cell {{max-width: 360px;}}
      }}

    </style>
    <script>
      const rows = {rows_json};
      let sortKey = '{default_sort}';
      let sortDir = '{default_dir}';
      const tbody = document.getElementById('lro-table-body');

      function esc(value) {{
        if (value === null || value === undefined) return '';
        return String(value).replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));
      }}

      function fmtNum(value) {{
        if (value === null || value === undefined || Number.isNaN(value)) return '';
        return Number(value).toLocaleString('nb-NO');
      }}

      function compareRows(a, b) {{
        const numericKeys = new Set(["rankValue", "eventPoints", "totalPoints", "formSort"]);
        let av = a[sortKey];
        let bv = b[sortKey];
        if (numericKeys.has(sortKey)) {{
          const aMissing = av === null || av === undefined || Number.isNaN(av);
          const bMissing = bv === null || bv === undefined || Number.isNaN(bv);
          if (aMissing && bMissing) return String(a.manager).localeCompare(String(b.manager), 'nb');
          if (aMissing) return 1;
          if (bMissing) return -1;
          return sortDir === 'asc' ? av - bv : bv - av;
        }}
        av = String(av || '').toLowerCase();
        bv = String(bv || '').toLowerCase();
        return sortDir === 'asc' ? av.localeCompare(bv, 'nb') : bv.localeCompare(av, 'nb');
      }}

      function rankCell(row, index) {{
        const rawRank = row.rankValue !== null && row.rankValue !== undefined && !Number.isNaN(row.rankValue)
          ? Number(row.rankValue)
          : Number(row.fallbackPosition || (index + 1));
        const place = Math.max(1, Math.round(rawRank));
        if (place === 1) return '<span class="rank-cell">🥇</span>';
        if (place === 2) return '<span class="rank-cell">🥈</span>';
        if (place === 3) return '<span class="rank-cell">🥉</span>';
        return `<span class="rank-cell rank-number">${{place}}</span>`;
      }}

      function render() {{
        const sorted = [...rows].sort(compareRows);
        tbody.innerHTML = '';
        sorted.forEach((row, index) => {{
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${{rankCell(row, index)}}</td>
            <td><strong>${{esc(row.manager)}}</strong></td>
            <td>${{esc(row.team)}}</td>
            <td>${{fmtNum(row.eventPoints)}}</td>
            <td>${{fmtNum(row.totalPoints)}}</td>
            <td>${{esc(row.form)}}</td>
          `;
          tbody.appendChild(tr);
        }});
        document.querySelectorAll('th.sortable').forEach(th => {{
          const key = th.getAttribute('data-key');
          th.querySelectorAll('.sort-mark').forEach(s => s.remove());
          if (key === sortKey) {{
            const span = document.createElement('span');
            span.className = 'sort-mark';
            span.textContent = sortDir === 'asc' ? '▲' : '▼';
            th.appendChild(span);
          }}
        }});
      }}

      document.querySelectorAll('th.sortable').forEach(th => {{
        th.addEventListener('click', () => {{
          const key = th.getAttribute('data-key');
          if (sortKey === key) {{
            sortDir = sortDir === 'asc' ? 'desc' : 'asc';
          }} else {{
            sortKey = key;
            sortDir = (key === 'eventPoints' || key === 'totalPoints' || key === 'formSort') ? 'desc' : 'asc';
          }}
          render();
        }});
      }});
      render();
    </script>
    '''
    components.html(component_html, height=860, scrolling=True)




def render_odds_table_component(odds_view: pd.DataFrame):
    rows = []
    for _, row in odds_view.reset_index(drop=True).iterrows():
        rows.append({
            "rank": None if pd.isna(row.get("odds_rank")) else int(row.get("odds_rank")),
            "manager": clean_cell(row.get("manager")),
            "team": clean_cell(row.get("team")),
            "winOdds": None if pd.isna(row.get("odds_float")) else float(row.get("odds_float")),
            "top3Odds": None if pd.isna(row.get("top3_odds_float")) else float(row.get("top3_odds_float")),
            "avg3": None if pd.isna(row.get("avg_rank_last_3_num")) else float(row.get("avg_rank_last_3_num")),
            "bestRank": None if pd.isna(row.get("best_rank_num")) else float(row.get("best_rank_num")),
        })

    rows_json = json.dumps(rows, ensure_ascii=False)
    component_html = f"""
    <div class="lro-table-wrap">
      <div class="lro-table-note">Trykk på kolonneoverskriftene for å sortere.</div>
      <table class="lro-table lro-odds-table">
        <thead>
          <tr>
            <th data-key="rank" class="sortable">Odds-rangering</th>
            <th data-key="manager" class="sortable">Manager</th>
            <th data-key="team" class="sortable">Lagnavn</th>
            <th data-key="winOdds" class="sortable">Odds - vinner</th>
            <th data-key="top3Odds" class="sortable">Odds - topp 3</th>
            <th data-key="avg3" class="sortable">Snitt siste tre sesonger</th>
            <th data-key="bestRank" class="sortable">Beste FPL-plassering</th>
          </tr>
        </thead>
        <tbody id="lro-odds-body"></tbody>
      </table>
    </div>
    <style>
      .lro-table-wrap {{font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; width:100%; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:12px;}}
      .lro-table-note {{font-size: 13px; color: #64748b; margin: 0 0 10px 0;}}
      .lro-table {{border-collapse: collapse; width: 100%; min-width: 900px; font-size: 12.5px; border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden; background:white;}}
      .lro-table th {{text-align: left; background: #0f172a; color: #ffffff; padding: 7px 8px; border-bottom: 1px solid #0f172a; cursor: pointer; user-select: none; white-space: nowrap; font-size:10.5px; text-transform:uppercase; letter-spacing:.055em;}}
      .lro-table td {{padding: 7px 8px; border-bottom: 1px solid #eef2f7; color: #0f172a; vertical-align: top; line-height:1.35;}}
      .lro-table tr:hover td {{background: #f1f5f9;}}
      .lro-table td.col-win {{background: #fff7ed; font-weight: 850;}}
      .lro-table td.col-top3 {{background: #eff6ff; font-weight: 850;}}
      .sort-mark {{margin-left: 6px; font-size: 11px; color: #b91c1c;}}
      .lro-table tr:nth-child(even) td {{background:#f8fafc;}}
      @media (max-width: 760px) {{
        .lro-table-wrap, .lro-history-wrap, .lro-hof-wrap {{overflow-x:auto; max-width:100%;}}
        .lro-table {{min-width: 780px; font-size: 11.2px;}}
        .lro-table th {{font-size: 9.4px; padding: 6px 7px;}}
        .lro-table td {{padding: 6px 7px;}}
        .merits-cell {{max-width: 360px;}}
      }}

    </style>
    <script>
      const oddsRows = {rows_json};
      let sortKey = 'rank';
      let sortDir = 'asc';
      const tbody = document.getElementById('lro-odds-body');
      function esc(value) {{ if (value === null || value === undefined) return ''; return String(value).replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m])); }}
      function fmtNum(value) {{ if (value === null || value === undefined || Number.isNaN(value)) return ''; return Number(value).toLocaleString('nb-NO'); }}
      function fmtOdds(value) {{ if (value === null || value === undefined || Number.isNaN(value)) return ''; return Number(value).toFixed(2); }}
      function compareRows(a,b) {{
        const numericKeys = new Set(['rank','winOdds','top3Odds','avg3','bestRank']);
        let av = a[sortKey]; let bv = b[sortKey];
        if (numericKeys.has(sortKey)) {{
          const am = av === null || av === undefined || Number.isNaN(av);
          const bm = bv === null || bv === undefined || Number.isNaN(bv);
          if (am && bm) return String(a.manager).localeCompare(String(b.manager), 'nb');
          if (am) return 1; if (bm) return -1;
          const diff = sortDir === 'asc' ? av - bv : bv - av;
          if (diff !== 0) return diff;
          return String(a.manager).localeCompare(String(b.manager), 'nb');
        }}
        av = String(av || '').toLowerCase(); bv = String(bv || '').toLowerCase();
        return sortDir === 'asc' ? av.localeCompare(bv, 'nb') : bv.localeCompare(av, 'nb');
      }}
      function render() {{
        const sorted = [...oddsRows].sort(compareRows); tbody.innerHTML = '';
        sorted.forEach(row => {{
          const tr = document.createElement('tr');
          tr.innerHTML = `<td><strong>${{fmtNum(row.rank)}}</strong></td><td><strong>${{esc(row.manager)}}</strong></td><td>${{esc(row.team)}}</td><td class="col-win">${{fmtOdds(row.winOdds)}}</td><td class="col-top3">${{fmtOdds(row.top3Odds)}}</td><td>${{fmtNum(row.avg3)}}</td><td>${{fmtNum(row.bestRank)}}</td>`;
          tbody.appendChild(tr);
        }});
        document.querySelectorAll('.lro-odds-table th.sortable').forEach(th => {{
          const key = th.getAttribute('data-key'); th.querySelectorAll('.sort-mark').forEach(s => s.remove());
          if (key === sortKey) {{ const span = document.createElement('span'); span.className = 'sort-mark'; span.textContent = sortDir === 'asc' ? '▲' : '▼'; th.appendChild(span); }}
        }});
      }}
      document.querySelectorAll('.lro-odds-table th.sortable').forEach(th => {{ th.addEventListener('click', () => {{ const key = th.getAttribute('data-key'); if (sortKey === key) {{ sortDir = sortDir === 'asc' ? 'desc' : 'asc'; }} else {{ sortKey = key; sortDir = (key === 'manager' || key === 'team') ? 'asc' : 'asc'; }} render(); }}); }});
      render();
    </script>
    """
    components.html(component_html, height=780, scrolling=True)


def render_history_table_component(summary: pd.DataFrame, seasons_df: pd.DataFrame):
    rows = []
    history_by_entry: dict[str, list[dict]] = {}

    for _, season in seasons_df.copy().iterrows():
        entry = str(season.get("entry", ""))
        if not entry:
            continue
        points_value = pd.to_numeric(season.get("total_points"), errors="coerce")
        rank_value = pd.to_numeric(season.get("rank_num"), errors="coerce")
        history_by_entry.setdefault(entry, []).append({
            "season": clean_cell(season.get("season_name")),
            "points": None if pd.isna(points_value) else int(points_value),
            "rank": None if pd.isna(rank_value) else int(rank_value),
        })

    for entry, values in history_by_entry.items():
        values.sort(key=lambda item: item.get("season") or "", reverse=True)

    summary = summary.copy().reset_index(drop=True)

    for index, row in summary.iterrows():
        merit_rank = int(row.get("merit_rank") or index + 1)
        rank_label = f"{medal_for_position(merit_rank)} {merit_rank}".strip()
        best_rank = None if pd.isna(row.get("best_rank_num")) else int(row.get("best_rank_num"))
        last_rank = None if pd.isna(row.get("last_season_rank_num")) else int(row.get("last_season_rank_num"))
        avg3 = None if pd.isna(row.get("avg_rank_last_3_num")) else int(row.get("avg_rank_last_3_num"))
        rows.append({
            "entry": str(row.get("entry", "")),
            "rankLabel": rank_label,
            "meritRank": merit_rank,
            "manager": clean_cell(row.get("manager")),
            "team": clean_cell(row.get("team")),
            "seasons": None if pd.isna(row.get("seasons")) else int(row.get("seasons")),
            "lastRank": last_rank,
            "bestRank": best_rank,
            "bestSeason": clean_cell(row.get("best_season")),
            "avg3": avg3,
            "hofScore": None if pd.isna(row.get("hof_score")) else int(row.get("hof_score")),
            "merits": clean_cell(row.get("merits")),
        })

    rows_json = json.dumps(rows, ensure_ascii=False)
    histories_json = json.dumps(history_by_entry, ensure_ascii=False)

    component_html = f'''
    <div class="lro-table-wrap lro-history-wrap">
      <div class="lro-table-note">Trykk på kolonneoverskriftene for å sortere. Trykk på en manager for full FPL-historikk.</div>
      <table class="lro-table lro-history-table">
        <thead><tr>
          <th data-key="meritRank" class="sortable">#</th>
          <th data-key="manager" class="sortable">Manager</th>
          <th data-key="team" class="sortable">Lagnavn</th>
          <th data-key="seasons" class="sortable">Sesonger spilt</th>
          <th data-key="lastRank" class="sortable">Plassering forrige sesong</th>
          <th data-key="bestRank" class="sortable">Beste FPL-plassering gjennom tidene</th>
          <th data-key="avg3" class="sortable">Snitt siste tre sesonger</th>
          <th data-key="hofScore" class="sortable">Merittpoeng</th>
          <th data-key="merits" class="sortable">Meritter</th>
        </tr></thead>
        <tbody id="lro-history-body"></tbody>
      </table>
    </div>
    <style>
      .lro-history-wrap {{font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; width:100%; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:12px;}}
      .lro-table-note {{font-size:13px;color:#64748b;margin:0 0 10px 0;}}
      .lro-table {{border-collapse:collapse;width:100%;min-width:980px;font-size:12.5px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:white;}}
      .lro-table th {{text-align:left;background:#0f172a;color:#ffffff;padding:7px 8px;border-bottom:1px solid #0f172a;cursor:pointer;user-select:none;white-space:nowrap;font-size:10.5px;text-transform:uppercase;letter-spacing:.055em;}}
      .lro-table td {{padding:7px 8px;border-bottom:1px solid #eef2f7;color:#0f172a;vertical-align:top;line-height:1.35;}}
      .lro-table tr:hover td {{background:#f8fafc;}}
      .lro-table td.col-last,
      .lro-table td.col-best,
      .lro-table td.col-avg,
      .lro-table td.col-merit {{font-weight:750;}}
      .lro-table td.col-merit {{font-weight:850;}}
      .manager-link {{font-weight:850;color:#7f1d1d;cursor:pointer;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;}}
      .history-detail {{background:#f8fafc!important;color:#0f172a!important;padding:16px!important;border-top:1px solid #e5e7eb;border-bottom:1px solid #e5e7eb;}}
      .history-detail strong {{display:block;color:#0f172a!important;font-size:15px;margin-bottom:10px;}}
      .history-detail table {{width:100%;border-collapse:collapse;margin-top:8px;background:white;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;}}
      .history-detail th {{background:#f1f5f9!important;color:#334155!important;font-weight:800;border-bottom:1px solid #e5e7eb;padding:8px 10px;text-align:left;}}
      .history-detail td {{background:white!important;color:#0f172a!important;border-bottom:1px solid #eef2f7;padding:8px 10px;text-align:left;}}
      .history-detail tr:hover td {{background:#f8fafc!important;}}
      .sort-mark {{margin-left:6px;font-size:11px;color:#b91c1c;}}
      .lro-table tr:nth-child(even) td {{background:#f8fafc;}}
      @media (max-width: 760px) {{
        .lro-table-wrap, .lro-history-wrap, .lro-hof-wrap {{overflow-x:auto; max-width:100%;}}
        .lro-table {{min-width: 780px; font-size: 11.2px;}}
        .lro-table th {{font-size: 9.4px; padding: 6px 7px;}}
        .lro-table td {{padding: 6px 7px;}}
        .merits-cell {{max-width: 360px;}}
      }}

      .merits-cell {{max-width:620px;line-height:1.35;}}
    </style>
    <script>
      const historyRows = {rows_json};
      const histories = {histories_json};
      let sortKey = 'hofScore';
      let sortDir = 'desc';
      let activeEntry = null;
      const tbody = document.getElementById('lro-history-body');
      function esc(value) {{ if (value === null || value === undefined) return ''; return String(value).replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m])); }}
      function fmtNum(value) {{ if (value === null || value === undefined || Number.isNaN(value)) return ''; return Number(value).toLocaleString('nb-NO'); }}
      function fmtBest(row) {{ const base = fmtNum(row.bestRank); if (!base) return ''; return row.bestSeason ? `${{base}} (${{esc(row.bestSeason)}})` : base; }}
      function compareRows(a,b) {{
        const numericKeys = new Set(['meritRank','seasons','lastRank','bestRank','avg3','hofScore']);
        let av=a[sortKey]; let bv=b[sortKey];
        if (numericKeys.has(sortKey)) {{
          const am=av===null||av===undefined||Number.isNaN(av); const bm=bv===null||bv===undefined||Number.isNaN(bv);
          if(am&&bm) return String(a.manager).localeCompare(String(b.manager),'nb');
          if(am) return 1; if(bm) return -1;
          const diff=sortDir==='asc'?av-bv:bv-av;
          if(diff!==0) return diff;
          return String(a.manager).localeCompare(String(b.manager),'nb');
        }}
        av=String(av||'').toLowerCase(); bv=String(bv||'').toLowerCase();
        return sortDir==='asc'?av.localeCompare(bv,'nb'):bv.localeCompare(av,'nb');
      }}
      function detailRow(row) {{
        const data=histories[row.entry]||[];
        const rows=data.map(item=>`<tr><td>${{esc(item.season)}}</td><td>${{fmtNum(item.points)}}</td><td>${{fmtNum(item.rank)}}</td></tr>`).join('');
        const empty=data.length?'':'<div>Fant ikke tidligere sesonger.</div>';
        return `<tr><td colspan="9" class="history-detail"><strong>Full FPL-historikk: ${{esc(row.manager)}}</strong>${{empty}}<table><thead><tr><th>Sesong</th><th>Poeng</th><th>FPL-plassering</th></tr></thead><tbody>${{rows}}</tbody></table></td></tr>`;
      }}
      function render() {{
        const sorted=[...historyRows].sort(compareRows); tbody.innerHTML='';
        sorted.forEach(row=>{{
          const tr=document.createElement('tr');
          tr.innerHTML=`<td><strong>${{esc(row.rankLabel)}}</strong></td><td><span class="manager-link" data-entry="${{esc(row.entry)}}">${{esc(row.manager)}}</span></td><td>${{esc(row.team)}}</td><td>${{fmtNum(row.seasons)}}</td><td class="col-last">${{fmtNum(row.lastRank)}}</td><td class="col-best">${{fmtBest(row)}}</td><td class="col-avg">${{fmtNum(row.avg3)}}</td><td class="col-merit">${{fmtNum(row.hofScore)}}</td><td class="merits-cell">${{esc(row.merits)}}</td>`;
          tbody.appendChild(tr);
          if(activeEntry===row.entry) tbody.insertAdjacentHTML('beforeend', detailRow(row));
        }});
        document.querySelectorAll('.manager-link').forEach(el=>{{el.addEventListener('click',()=>{{const entry=el.getAttribute('data-entry'); activeEntry=activeEntry===entry?null:entry; render();}});}});
        document.querySelectorAll('.lro-history-table th.sortable').forEach(th=>{{const key=th.getAttribute('data-key'); th.querySelectorAll('.sort-mark').forEach(s=>s.remove()); if(key===sortKey){{const span=document.createElement('span'); span.className='sort-mark'; span.textContent=sortDir==='asc'?'▲':'▼'; th.appendChild(span);}}}});
      }}
      document.querySelectorAll('.lro-history-table th.sortable').forEach(th=>{{th.addEventListener('click',()=>{{const key=th.getAttribute('data-key'); if(sortKey===key){{sortDir=sortDir==='asc'?'desc':'asc';}} else {{sortKey=key; sortDir=(key==='manager'||key==='team'||key==='merits')?'asc':(key==='hofScore'?'desc':'asc');}} render();}});}});
      render();
    </script>
    '''
    components.html(component_html, height=1060, scrolling=True)


def render_hof_table_component(hof_df: pd.DataFrame):
    rows=[]
    for index,row in hof_df.reset_index(drop=True).iterrows():
        rank=int(index+1)
        rows.append({
            "rank": rank,
            "rankLabel": f"{medal_for_position(rank)} {rank}".strip(),
            "manager": clean_cell(row.get("display_name")),
            "hofScore": int(row.get("hof_score") or 0),
            "overall": int(row.get("overall_count") or 0),
            "cupGold": int(row.get("cup_count") or 0),
            "cupSilver": int(row.get("cup_runner_up_count") or 0),
            "monthly": int(row.get("monthly_titles") or 0),
            "merits": clean_cell(row.get("merits")),
        })
    rows_json=json.dumps(rows, ensure_ascii=False)
    component_html=f'''
    <div class="lro-table-wrap lro-hof-wrap">
      <table class="lro-table lro-hof-table">
        <thead><tr><th data-key="rank" class="sortable">#</th><th data-key="manager" class="sortable">Manager</th><th data-key="hofScore" class="sortable">Merittpoeng</th><th data-key="overall" class="sortable">Sammenlagtseiere</th><th data-key="cupGold" class="sortable">Cupgull</th><th data-key="cupSilver" class="sortable">Cupsølv</th><th data-key="monthly" class="sortable">Månedsseiere</th><th data-key="merits" class="sortable">Meritter</th></tr></thead>
        <tbody id="lro-hof-body"></tbody>
      </table>
    </div>
    <style>
      .lro-hof-wrap {{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; width:100%; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:12px;}}
      .lro-table {{border-collapse:collapse;width:100%;min-width:980px;font-size:12.5px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:white;}}
      .lro-table th {{text-align:left;background:#0f172a;color:#ffffff;padding:7px 8px;border-bottom:1px solid #0f172a;cursor:pointer;white-space:nowrap;font-size:10.5px;text-transform:uppercase;letter-spacing:.055em;}}
      .lro-table td {{padding:7px 8px;border-bottom:1px solid #eef2f7;color:#0f172a;vertical-align:top;line-height:1.35;}}
      .lro-table tr:hover td {{background:#f1f5f9;}}
      .lro-table td.col-merit {{font-weight:900;}}
      .manager-strong {{font-weight:850;}}
      .merits-cell {{max-width:560px;line-height:1.35;}}
      .sort-mark {{margin-left:6px;font-size:11px;color:#b91c1c;}}
      .lro-table tr:nth-child(even) td {{background:#f8fafc;}}
      @media (max-width: 760px) {{
        .lro-table-wrap, .lro-history-wrap, .lro-hof-wrap {{overflow-x:auto; max-width:100%;}}
        .lro-table {{min-width: 780px; font-size: 11.2px;}}
        .lro-table th {{font-size: 9.4px; padding: 6px 7px;}}
        .lro-table td {{padding: 6px 7px;}}
        .merits-cell {{max-width: 360px;}}
      }}

    </style>
    <script>
      const hofRows={rows_json}; let sortKey='hofScore'; let sortDir='desc'; const tbody=document.getElementById('lro-hof-body');
      function esc(value) {{ if(value===null||value===undefined) return ''; return String(value).replace(/[&<>"']/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m])); }}
      function fmtNum(value) {{ if(value===null||value===undefined||Number.isNaN(value)) return ''; return Number(value).toLocaleString('nb-NO'); }}
      function compareRows(a,b) {{ const numericKeys=new Set(['rank','hofScore','overall','cupGold','cupSilver','monthly']); let av=a[sortKey],bv=b[sortKey]; if(numericKeys.has(sortKey)){{const diff=sortDir==='asc'?av-bv:bv-av; if(diff!==0)return diff; return String(a.manager).localeCompare(String(b.manager),'nb');}} av=String(av||'').toLowerCase(); bv=String(bv||'').toLowerCase(); return sortDir==='asc'?av.localeCompare(bv,'nb'):bv.localeCompare(av,'nb'); }}
      function render(){{const sorted=[...hofRows].sort(compareRows); tbody.innerHTML=''; sorted.forEach(row=>{{const tr=document.createElement('tr'); tr.innerHTML=`<td><strong>${{esc(row.rankLabel)}}</strong></td><td class="manager-strong">${{esc(row.manager)}}</td><td class="col-merit">${{fmtNum(row.hofScore)}}</td><td>${{fmtNum(row.overall)}}</td><td>${{fmtNum(row.cupGold)}}</td><td>${{fmtNum(row.cupSilver)}}</td><td>${{fmtNum(row.monthly)}}</td><td class="merits-cell">${{esc(row.merits)}}</td>`; tbody.appendChild(tr);}}); document.querySelectorAll('.lro-hof-table th.sortable').forEach(th=>{{const key=th.getAttribute('data-key'); th.querySelectorAll('.sort-mark').forEach(s=>s.remove()); if(key===sortKey){{const span=document.createElement('span'); span.className='sort-mark'; span.textContent=sortDir==='asc'?'▲':'▼'; th.appendChild(span);}}}});}}
      document.querySelectorAll('.lro-hof-table th.sortable').forEach(th=>{{th.addEventListener('click',()=>{{const key=th.getAttribute('data-key'); if(sortKey===key){{sortDir=sortDir==='asc'?'desc':'asc';}} else {{sortKey=key; sortDir=(key==='manager'||key==='merits')?'asc':'desc';}} render();}});}});
      render();
    </script>
    '''
    components.html(component_html, height=720, scrolling=True)

def render_city_cards(place_df: pd.DataFrame):
    """Render place cards with native Streamlit elements.

    This deliberately avoids feeding a large indented HTML string to st.markdown,
    because Markdown can interpret indented HTML as a code block in some cases.
    """
    ordered = place_df.sort_values(["Antall", "By"], ascending=[False, True]).reset_index(drop=True)

    if ordered.empty:
        return

    cols = st.columns(3)

    for index, row in ordered.iterrows():
        count = int(row.get("Antall", 0))
        label = "manager" if count == 1 else "managere"
        people = str(row.get("Deltakere", ""))

        with cols[index % 3]:
            with st.container(border=True):
                st.markdown(f"**{row.get('By', '')} · {count} {label}**")
                st.write(people)



def fmt_int(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
        return f"{int(float(value)):,}".replace(",", " ")
    except Exception:
        return ""


def fmt_kr(value: Any) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
        return f"{int(float(value))} kr"
    except Exception:
        return ""


def pick_first(df: pd.DataFrame, sort_column: str, ascending: bool = True) -> pd.Series | None:
    if df is None or df.empty or sort_column not in df.columns:
        return None
    temp = df.copy()
    temp[sort_column] = pd.to_numeric(temp[sort_column], errors="coerce")
    temp = temp.dropna(subset=[sort_column])
    if temp.empty:
        return None
    return temp.sort_values(sort_column, ascending=ascending).iloc[0]


def render_manager_profile(summary: pd.DataFrame, seasons_df: pd.DataFrame):
    if summary.empty:
        return

    ordered = summary.sort_values(["hof_score", "manager"], ascending=[False, True]).reset_index(drop=True)
    names = ordered["manager"].fillna("Ukjent").tolist()

    selected_name = st.selectbox(
        "Velg managerprofil",
        names,
        key="history_profile_picker_v31",
        help="Velg en manager for å se FPL-historikk og Lofthus Road Open-meritter samlet.",
    )

    selected = ordered[ordered["manager"] == selected_name].iloc[0]
    selected_rank = int(ordered.index[ordered["manager"] == selected_name][0]) + 1

    st.markdown('<div class="section-kicker">Managerprofil</div>', unsafe_allow_html=True)
    st.subheader(selected.get("manager", "Manager"))

    lro_cards([
        {
            "label": "Meritt-rangering",
            "value": f"{medal_for_position(selected_rank)} {selected_rank}. plass".strip(),
            "caption": f"{fmt_int(selected.get('hof_score'))} merittpoeng",
        },
        {
            "label": "Beste FPL-plassering",
            "value": format_rank_with_season(selected.get("best_rank_num"), selected.get("best_season")),
            "caption": "All-time peak",
        },
        {
            "label": "Forrige sesong",
            "value": format_rank(selected.get("last_season_rank_num")),
            "caption": "FPL-plassering forrige sesong",
        },
        {
            "label": "Snitt siste tre sesonger",
            "value": format_rank(selected.get("avg_rank_last_3_num")),
            "caption": f"{int(selected.get('seasons') or 0)} sesonger spilt totalt",
        },
    ])

    merits = clean_cell(selected.get("merits"))
    if merits:
        st.markdown("**Lofthus Road Open-meritter**")
        st.write(merits)
    else:
        st.caption("Ingen Lofthus Road Open-meritter registrert på denne manageren ennå.")

    entry = selected.get("entry")
    manager_history = seasons_df[seasons_df["entry"].astype(str) == str(entry)].copy() if "entry" in seasons_df.columns else pd.DataFrame()

    st.markdown("**Full FPL-historikk**")
    if not manager_history.empty:
        manager_history["rank_num"] = pd.to_numeric(manager_history["rank_num"], errors="coerce")
        manager_history["total_points_num"] = pd.to_numeric(manager_history["total_points"], errors="coerce")
        manager_history = manager_history.sort_values("season_name", ascending=False)
        history_view = manager_history[["season_name", "total_points_num", "rank_num"]].rename(columns={
            "season_name": "Sesong",
            "total_points_num": "Poeng",
            "rank_num": "FPL-plassering",
        })
        st.dataframe(
            history_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Poeng": st.column_config.NumberColumn("Poeng", format="%d"),
                "FPL-plassering": st.column_config.NumberColumn("FPL-plassering", format="%d"),
            },
        )
    else:
        st.caption("Fant ikke tidligere sesonger for denne manageren.")


def build_history_overview(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    overview = summary.copy().sort_values(["hof_score", "manager"], ascending=[False, True], na_position="last").reset_index(drop=True)
    overview["Rangering"] = [f"{medal_for_position(i + 1)} {i + 1}".strip() for i in range(len(overview))]
    overview["Manager"] = overview["manager"]
    overview["Lagnavn"] = overview["team"]
    overview["Sesonger spilt"] = pd.to_numeric(overview["seasons"], errors="coerce")
    overview["Plassering forrige sesong"] = pd.to_numeric(overview["last_season_rank_num"], errors="coerce")
    overview["Beste FPL-plassering gjennom tidene"] = pd.to_numeric(overview["best_rank_num"], errors="coerce")
    overview["Beste sesong"] = overview["best_season"]
    overview["Snitt siste tre sesonger"] = pd.to_numeric(overview["avg_rank_last_3_num"], errors="coerce")
    overview["Merittpoeng"] = pd.to_numeric(overview["hof_score"], errors="coerce")
    overview["Meritter"] = overview["merits"].fillna("")

    return overview[[
        "Rangering",
        "Manager",
        "Lagnavn",
        "Sesonger spilt",
        "Plassering forrige sesong",
        "Beste FPL-plassering gjennom tidene",
        "Beste sesong",
        "Snitt siste tre sesonger",
        "Merittpoeng",
        "Meritter",
    ]]


def render_history_overview_table(summary: pd.DataFrame):
    overview = build_history_overview(summary)
    if overview.empty:
        st.caption("Ingen historikk å vise ennå.")
        return

    st.dataframe(
        overview,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rangering": st.column_config.TextColumn("Rangering", width="small"),
            "Manager": st.column_config.TextColumn("Manager", width="medium"),
            "Lagnavn": st.column_config.TextColumn("Lagnavn", width="medium"),
            "Sesonger spilt": st.column_config.NumberColumn("Sesonger spilt", format="%d"),
            "Plassering forrige sesong": st.column_config.NumberColumn("Plassering forrige sesong", format="%d"),
            "Beste FPL-plassering gjennom tidene": st.column_config.NumberColumn("Beste FPL-plassering gjennom tidene", format="%d"),
            "Snitt siste tre sesonger": st.column_config.NumberColumn("Snitt siste tre sesonger", format="%d"),
            "Merittpoeng": st.column_config.NumberColumn("Merittpoeng", format="%d"),
            "Meritter": st.column_config.TextColumn("Meritter", width="large"),
        },
    )

def render_odds_cards(df: pd.DataFrame, title: str, empty_text: str):
    """Render selected odds section as compact table, not metric cards."""
    st.subheader(title)
    if df.empty:
        st.caption(empty_text)
        return

    render_odds_table_component(df)


def render_month_king_cards(month_specialists: pd.DataFrame):
    if month_specialists.empty:
        return

    cols_per_row = 5
    for start in range(0, len(month_specialists), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, (_, row) in zip(cols, month_specialists.iloc[start:start + cols_per_row].iterrows()):
            with col:
                with st.container(border=True):
                    month = str(row.get("month", ""))
                    leaders_count = int(row.get("leaders_count") or 1)
                    st.caption(month.upper())
                    if leaders_count > 1:
                        st.markdown("**Delt månedskonge**")
                        st.caption(f"{leaders_count} på topp")
                    else:
                        st.markdown(f"**{row.get('king', '')}**")


def nav_choice(label: str, options: list[str], key: str, default: str | None = None) -> str:
    """Stable button navigation without radio dots or segmented-control indicators."""
    if not options:
        return ""

    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = default or options[0]

    if label:
        st.caption(label)

    cols = st.columns(len(options))
    for option, col in zip(options, cols):
        safe = re.sub(r"[^a-zA-Z0-9_]+", "_", option).strip("_").lower()
        with col:
            if st.button(
                option,
                key=f"{key}_btn_{safe}",
                type="primary" if st.session_state[key] == option else "secondary",
                use_container_width=True,
            ):
                st.session_state[key] = option
                st.rerun()

    return st.session_state[key]


def render_prediction_table_component(odds_df: pd.DataFrame):
    if odds_df.empty:
        st.caption("Fant ikke nok historikk til å lage tabelltips.")
        return

    rows = []
    for index, row in odds_df.reset_index(drop=True).iterrows():
        best_rank = pd.to_numeric(row.get("best_rank_num"), errors="coerce")
        last_rank = pd.to_numeric(row.get("last_season_rank_num"), errors="coerce")
        avg3 = pd.to_numeric(row.get("avg_rank_last_3_num"), errors="coerce")
        rows.append({
            "tip": int(index + 1),
            "manager": clean_cell(row.get("manager")),
            "lastRank": None if pd.isna(last_rank) else int(last_rank),
            "avg3": None if pd.isna(avg3) else int(avg3),
            "bestRank": None if pd.isna(best_rank) else int(best_rank),
            "bestSeason": clean_cell(row.get("best_season")),
        })

    rows_json = json.dumps(rows, ensure_ascii=False)
    component_html = """
    <div class="lro-table-wrap lro-prediction-wrap">
      <div class="lro-table-note">Modellens tabelltips før sesongstart. Trykk på kolonneoverskriftene for å sortere.</div>
      <table class="lro-table lro-prediction-table">
        <thead><tr>
          <th data-key="tip" class="sortable">Tips</th>
          <th data-key="manager" class="sortable">Manager</th>
          <th data-key="lastRank" class="sortable">Plassering forrige sesong</th>
          <th data-key="avg3" class="sortable">Snitt siste tre sesonger</th>
          <th data-key="bestRank" class="sortable">Beste FPL-plassering</th>
        </tr></thead>
        <tbody id="lro-prediction-body"></tbody>
      </table>
    </div>
    <style>
      .lro-prediction-wrap {font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; width:100%; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:12px;}
      .lro-table-note {font-size:13px;color:#64748b;margin:0 0 10px 0;}
      .lro-table {border-collapse:collapse;width:100%;min-width:720px;font-size:12.5px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:white;}
      .lro-table th {text-align:left;background:#0f172a;color:#ffffff;padding:7px 8px;border-bottom:1px solid #0f172a;cursor:pointer;user-select:none;white-space:nowrap;font-size:10.5px;text-transform:uppercase;letter-spacing:.055em;}
      .lro-table td {padding:7px 8px;border-bottom:1px solid #eef2f7;color:#0f172a;vertical-align:top;line-height:1.35;}
      .lro-table tr:hover td {background:#f1f5f9;}
      .tip-cell {font-weight:900;white-space:nowrap;}
      .sort-mark {margin-left:6px;font-size:11px;color:#b91c1c;}
      .lro-table tr:nth-child(even) td {background:#f8fafc;}
      @media (max-width: 760px) {
        .lro-prediction-wrap {overflow-x:auto; max-width:100%;}
        .lro-table {min-width: 680px; font-size: 11.2px;}
        .lro-table th {font-size: 9.4px; padding: 6px 7px;}
        .lro-table td {padding: 6px 7px;}
      }
    </style>
    <script>
      const predictionRows = __ROWS__;
      let sortKey = 'tip';
      let sortDir = 'asc';
      const tbody = document.getElementById('lro-prediction-body');
      function esc(value) { if (value === null || value === undefined) return ''; return String(value).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
      function fmtNum(value) { if (value === null || value === undefined || Number.isNaN(value)) return ''; return Number(value).toLocaleString('nb-NO'); }
      function medal(index) { return index === 0 ? '🥇 ' : index === 1 ? '🥈 ' : index === 2 ? '🥉 ' : ''; }
      function fmtBest(row) { const base = fmtNum(row.bestRank); if (!base) return ''; return row.bestSeason ? `${base} (${esc(row.bestSeason)})` : base; }
      function compareRows(a,b) {
        const numericKeys = new Set(['tip','lastRank','avg3','bestRank']);
        let av=a[sortKey]; let bv=b[sortKey];
        if (numericKeys.has(sortKey)) {
          const am=av===null||av===undefined||Number.isNaN(av); const bm=bv===null||bv===undefined||Number.isNaN(bv);
          if(am&&bm) return String(a.manager).localeCompare(String(b.manager),'nb');
          if(am) return 1; if(bm) return -1;
          const diff=sortDir==='asc'?av-bv:bv-av;
          if(diff!==0) return diff;
          return String(a.manager).localeCompare(String(b.manager),'nb');
        }
        av=String(av||'').toLowerCase(); bv=String(bv||'').toLowerCase();
        return sortDir==='asc'?av.localeCompare(bv,'nb'):bv.localeCompare(av,'nb');
      }
      function render() {
        const sorted=[...predictionRows].sort(compareRows); tbody.innerHTML='';
        sorted.forEach((row,index)=>{
          const tr=document.createElement('tr');
          tr.innerHTML=`<td><span class="tip-cell">${medal(index)}${fmtNum(row.tip)}</span></td><td><strong>${esc(row.manager)}</strong></td><td>${fmtNum(row.lastRank)}</td><td>${fmtNum(row.avg3)}</td><td>${fmtBest(row)}</td>`;
          tbody.appendChild(tr);
        });
        document.querySelectorAll('.lro-prediction-table th.sortable').forEach(th=>{const key=th.getAttribute('data-key'); th.querySelectorAll('.sort-mark').forEach(s=>s.remove()); if(key===sortKey){const span=document.createElement('span'); span.className='sort-mark'; span.textContent=sortDir==='asc'?'▲':'▼'; th.appendChild(span);}});
      }
      document.querySelectorAll('.lro-prediction-table th.sortable').forEach(th=>{th.addEventListener('click',()=>{const key=th.getAttribute('data-key'); if(sortKey===key){sortDir=sortDir==='asc'?'desc':'asc';} else {sortKey=key; sortDir=(key==='manager')?'asc':'asc';} render();});});
      render();
    </script>
    """.replace("__ROWS__", rows_json)
    components.html(component_html, height=620, scrolling=True)

def render_preseason_radar_preview():
    st.info("Sesongradaren våkner når ligaen får live plasseringer og runde-data fra FPL.")
    lro_cards([
        {"label": "Kommer", "value": "Største klatrere", "caption": "Hvem flyr oppover tabellen"},
        {"label": "Kommer", "value": "Største fall", "caption": "Hvem faller mest"},
        {"label": "Kommer", "value": "Form siste tre runder", "caption": "Hvem har momentum"},
        {"label": "Kommer", "value": "Mot oddsen", "caption": "Over- og underprestasjon"},
    ])

def build_season_radar_tables(managers: list[dict], summary_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if not managers:
        return {}

    df = pd.DataFrame(managers).copy()

    df["rank_num"] = pd.to_numeric(df.get("rank"), errors="coerce")
    df["last_rank_num"] = pd.to_numeric(df.get("last_rank"), errors="coerce")
    df["event_total_num"] = pd.to_numeric(df.get("event_total"), errors="coerce")
    df["total_num"] = pd.to_numeric(df.get("total"), errors="coerce")
    df["form_delta"] = df["last_rank_num"] - df["rank_num"]

    if not summary_df.empty:
        odds_df = build_preseason_odds(summary_df)
        odds_lookup = odds_df[["entry", "odds", "odds_float", "odds_rank"]].copy()
        df = df.merge(odds_lookup, on="entry", how="left")
    else:
        df["odds"] = pd.NA
        df["odds_float"] = pd.NA
        df["odds_rank"] = pd.NA

    df["rank_display"] = df["rank_num"].apply(format_rank)
    df["form_curve"] = df["form_delta"].apply(
        lambda delta: "" if pd.isna(delta) else (f"🟢 ▲ {int(delta)}" if delta > 0 else (f"🔴 ▼ {abs(int(delta))}" if delta < 0 else "⚪ 0"))
    )

    base_cols = ["player_name", "entry_name", "rank_num", "rank_display", "form_curve", "event_total_num", "total_num", "odds", "odds_rank"]

    climbers = df[df["form_delta"] > 0].sort_values("form_delta", ascending=False)[base_cols].head(10)
    fallers = df[df["form_delta"] < 0].sort_values("form_delta", ascending=True)[base_cols].head(10)

    over = pd.DataFrame()
    under = pd.DataFrame()

    if df["rank_num"].notna().any() and df["odds_rank"].notna().any():
        df["performance_vs_odds"] = pd.to_numeric(df["odds_rank"], errors="coerce") - df["rank_num"]
        over = df[df["performance_vs_odds"] > 0].sort_values("performance_vs_odds", ascending=False)[base_cols + ["performance_vs_odds"]].head(10)
        under = df[df["performance_vs_odds"] < 0].sort_values("performance_vs_odds", ascending=True)[base_cols + ["performance_vs_odds"]].head(10)

    form_rows = []

    for _, row in df.iterrows():
        entry = row.get("entry")
        if pd.isna(entry):
            continue

        try:
            history = get_entry_history(int(entry))
            current = history.get("current", []) or []
        except Exception:
            current = []

        last_events = [gw for gw in current if gw.get("points") is not None][-3:]

        if not last_events:
            continue

        points = [int(gw.get("points") or 0) for gw in last_events]
        events = [str(gw.get("event")) for gw in last_events]

        form_rows.append({
            "player_name": row.get("player_name"),
            "entry_name": row.get("entry_name"),
            "last_three_points": sum(points),
            "last_three_avg": round(sum(points) / len(points), 1),
            "last_three_detail": " / ".join(f"GW{event}: {point}" for event, point in zip(events, points)),
            "rank_num": row.get("rank_num"),
        })

    form_df = pd.DataFrame(form_rows)

    if not form_df.empty:
        form_df = form_df.sort_values(["last_three_points", "rank_num"], ascending=[False, True]).head(10)

    return {
        "climbers": climbers,
        "fallers": fallers,
        "form_three": form_df,
        "over": over,
        "under": under,
    }


def build_round_by_round_league_history(managers: list[dict]) -> pd.DataFrame:
    """Reconstruct LRO positions after every played FPL gameweek.

    FPL exposes each manager's current-season history with gameweek points and
    cumulative points. Ranking the cumulative totals inside this league gives us
    the Lofthus Road Open table round by round without storing snapshots.
    """
    rows = []

    for manager in managers or []:
        entry = manager.get("entry")
        if not entry:
            continue

        try:
            history = get_entry_history(int(entry))
            current = history.get("current", []) or []
        except Exception:
            current = []

        player_name = str(manager.get("player_name") or "Ukjent manager")
        entry_name = str(manager.get("entry_name") or "Ukjent lag")

        for gw in current:
            event = gw.get("event")
            total_points = gw.get("total_points")
            round_points = gw.get("points")

            if event is None or total_points is None:
                continue

            try:
                event = int(event)
                total_points = int(total_points)
                round_points = int(round_points or 0)
            except (TypeError, ValueError):
                continue

            if event <= 0:
                continue

            rows.append({
                "event": event,
                "entry": int(entry),
                "player_name": player_name,
                "entry_name": entry_name,
                "manager_label": player_name,
                "round_points": round_points,
                "total_points": total_points,
            })

    history_df = pd.DataFrame(rows)
    if history_df.empty:
        return pd.DataFrame(columns=[
            "event", "entry", "player_name", "entry_name", "manager_label",
            "round_points", "total_points", "league_rank",
        ])

    # Two people can share a display name. Keep their lines separate by adding
    # the team name only when it is actually needed.
    duplicate_names = history_df.groupby("player_name")["entry"].nunique()
    duplicate_names = set(duplicate_names[duplicate_names > 1].index)
    if duplicate_names:
        mask = history_df["player_name"].isin(duplicate_names)
        history_df.loc[mask, "manager_label"] = (
            history_df.loc[mask, "player_name"]
            + " · "
            + history_df.loc[mask, "entry_name"]
        )

    # Ranking by cumulative points reconstructs the mini-league table. Ties get
    # the same displayed place rather than a made-up tie-breaker.
    history_df["league_rank"] = (
        history_df.groupby("event")["total_points"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    return history_df.sort_values(
        ["event", "league_rank", "player_name"],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def build_demo_round_by_round_history(managers: list[dict], rounds: int = 8) -> pd.DataFrame:
    """Create deterministic, explicitly fictional gameweeks for preview use."""
    clean_managers = []
    for manager in managers or []:
        entry = manager.get("entry")
        if not entry:
            continue
        clean_managers.append({
            "entry": int(entry),
            "player_name": str(manager.get("player_name") or "Ukjent manager"),
            "entry_name": str(manager.get("entry_name") or "Ukjent lag"),
        })

    if not clean_managers:
        return pd.DataFrame(columns=[
            "event", "entry", "player_name", "entry_name", "manager_label",
            "round_points", "total_points", "league_rank",
        ])

    # Stable ordering plus arithmetic pseudo-variation. No random module, so the
    # same league always gets the same demo after every refresh.
    clean_managers = sorted(
        clean_managers,
        key=lambda item: (item["entry"] % 997, normalize_text(item["player_name"])),
    )
    cumulative = {item["entry"]: 0 for item in clean_managers}
    rows = []

    for event in range(1, rounds + 1):
        event_rows = []
        for idx, manager in enumerate(clean_managers):
            entry = manager["entry"]
            seed = (entry * 37 + event * 71 + idx * 19) % 43
            round_points = 43 + seed
            if (entry + event) % 7 == 0:
                round_points += 13
            if (entry + event * 3) % 11 == 0:
                round_points -= 9
            round_points = max(28, min(102, round_points))
            cumulative[entry] += round_points

            event_rows.append({
                "event": event,
                "entry": entry,
                "player_name": manager["player_name"],
                "entry_name": manager["entry_name"],
                "manager_label": manager["player_name"],
                "round_points": round_points,
                "total_points": cumulative[entry],
            })

        event_df = pd.DataFrame(event_rows)
        event_df["league_rank"] = (
            event_df["total_points"]
            .rank(method="first", ascending=False)
            .astype(int)
        )
        rows.extend(event_df.to_dict("records"))

    history_df = pd.DataFrame(rows)

    duplicate_names = history_df.groupby("player_name")["entry"].nunique()
    duplicate_names = set(duplicate_names[duplicate_names > 1].index)
    if duplicate_names:
        mask = history_df["player_name"].isin(duplicate_names)
        history_df.loc[mask, "manager_label"] = (
            history_df.loc[mask, "player_name"]
            + " · "
            + history_df.loc[mask, "entry_name"]
        )

    return history_df.sort_values(
        ["event", "league_rank", "player_name"],
        ascending=[True, True, True],
    ).reset_index(drop=True)


def build_round_by_round_summary(history_df: pd.DataFrame) -> pd.DataFrame:
    if history_df is None or history_df.empty:
        return pd.DataFrame()

    rows = []
    for manager_label, manager_df in history_df.groupby("manager_label", sort=False):
        manager_df = manager_df.sort_values("event").reset_index(drop=True)
        first = manager_df.iloc[0]
        last = manager_df.iloc[-1]
        start_rank = int(first["league_rank"])
        current_rank = int(last["league_rank"])
        best_rank = int(manager_df["league_rank"].min())
        worst_rank = int(manager_df["league_rank"].max())
        movement = start_rank - current_rank

        if movement > 0:
            movement_text = f"🟢 +{movement}"
        elif movement < 0:
            movement_text = f"🔴 {movement}"
        else:
            movement_text = "⚪ 0"

        biggest_jump = 0
        biggest_jump_event = None
        biggest_jump_direction = 0
        previous_rank = None
        for _, row in manager_df.iterrows():
            rank = int(row["league_rank"])
            if previous_rank is not None:
                delta = previous_rank - rank
                if abs(delta) > abs(biggest_jump):
                    biggest_jump = delta
                    biggest_jump_direction = delta
                    biggest_jump_event = int(row["event"])
            previous_rank = rank

        if biggest_jump_event is None or biggest_jump == 0:
            biggest_jump_text = "⚪ 0"
        elif biggest_jump_direction > 0:
            biggest_jump_text = f"🟢 +{biggest_jump} (GW{biggest_jump_event})"
        else:
            biggest_jump_text = f"🔴 {biggest_jump} (GW{biggest_jump_event})"

        rows.append({
            "manager_label": manager_label,
            "entry_name": last["entry_name"],
            "start_rank": start_rank,
            "current_rank": current_rank,
            "best_rank": best_rank,
            "worst_rank": worst_rank,
            "movement": movement,
            "movement_text": movement_text,
            "biggest_jump": int(biggest_jump),
            "biggest_jump_text": biggest_jump_text,
            "round_points": int(last.get("round_points", 0) or 0),
            "total_points": int(last["total_points"]),
        })

    return pd.DataFrame(rows).sort_values(
        ["current_rank", "total_points", "manager_label"],
        ascending=[True, False, True],
    ).reset_index(drop=True)


def render_round_by_round_league_history(managers: list[dict]):
    history_df = build_round_by_round_league_history(managers)
    is_demo = history_df.empty

    if is_demo:
        history_df = build_demo_round_by_round_history(managers, rounds=8)
        if history_df.empty:
            st.info("Sesongløpet våkner så snart ligaen har managere å vise.")
            return

    latest_event = int(history_df["event"].max())
    summary = build_round_by_round_summary(history_df)
    league_size = int(summary.shape[0])

    if is_demo:
        st.warning("DEMO · Fiktive plasseringer. Ekte manager- og lagnavn, men oppdiktede GW1–GW8-resultater. Dette forsvinner automatisk når FPL har ekte rundedata.")
    else:
        st.markdown(
            f'''<div style="display:flex;gap:10px;align-items:center;justify-content:space-between;background:linear-gradient(135deg,#052e2b,#0f172a 70%);color:white;border-radius:16px;padding:13px 16px;margin:2px 0 14px 0;border:1px solid rgba(255,255,255,.10)">
            <div><div style="font-size:.7rem;color:#fde68a;font-weight:900;letter-spacing:.08em">LIVE SESONG 2026/27</div><div style="font-size:1.08rem;font-weight:900;margin-top:3px">Sesongløpet etter GW{latest_event}</div></div>
            <div style="font-size:.78rem;color:#cbd5e1">{league_size} managere</div></div>''', unsafe_allow_html=True)

    leader = summary.iloc[0] if not summary.empty else None
    biggest_climber = summary.sort_values(["movement", "current_rank"], ascending=[False, True]).iloc[0] if not summary.empty else None
    biggest_faller = summary.sort_values(["movement", "current_rank"], ascending=[True, True]).iloc[0] if not summary.empty else None
    biggest_jump = summary.assign(_jump_abs=summary["biggest_jump"].abs()).sort_values(["_jump_abs", "current_rank"], ascending=[False, True]).iloc[0] if not summary.empty else None
    radar_metric_strip([
        {"label": "Ligaleder", "value": str(leader["manager_label"]) if leader is not None else "–", "caption": f"{int(leader['total_points'])} poeng" if leader is not None else ""},
        {"label": "Mest opp", "value": str(biggest_climber["manager_label"]) if biggest_climber is not None else "–", "caption": str(biggest_climber["movement_text"]) if biggest_climber is not None else ""},
        {"label": "Mest ned", "value": str(biggest_faller["manager_label"]) if biggest_faller is not None else "–", "caption": str(biggest_faller["movement_text"]) if biggest_faller is not None else ""},
        {"label": "Villeste GW-hopp", "value": str(biggest_jump["manager_label"]) if biggest_jump is not None else "–", "caption": str(biggest_jump["biggest_jump_text"]) if biggest_jump is not None else ""},
    ])

    st.markdown("### Plassering runde for runde")
    st.caption("1. plass ligger øverst. Standardvisningen holder grafen lesbar; hele ligaen er fortsatt ett klikk unna.")

    available = summary["manager_label"].tolist()
    race_mode = st.selectbox(
        "Vis i grafen",
        ["Topp 5", "Topp 10", "Hele ligaen", "Velg selv"],
        index=0,
        key="race_mode_v110",
    )

    if race_mode == "Topp 5":
        selected = available[:5]
    elif race_mode == "Topp 10":
        selected = available[:10]
    elif race_mode == "Hele ligaen":
        selected = available
    else:
        selected = st.multiselect(
            "Managere",
            options=available,
            default=available[: min(5, len(available))],
            key="season_race_custom_v110",
        )

    if not selected:
        st.caption("Velg minst én manager.")
    else:
        chart_df = history_df[history_df["manager_label"].isin(selected)].copy()
        chart_df = chart_df.rename(columns={
            "event": "Runde", "league_rank": "Plassering", "manager_label": "Manager",
            "entry_name": "Lag", "round_points": "Rundepoeng", "total_points": "Poeng totalt",
        })

        selected_max = int(chart_df["Plassering"].max()) if not chart_df.empty else league_size
        max_rank = max(2, min(league_size, selected_max + 2)) if race_mode != "Hele ligaen" else max(2, league_size)
        many_lines = len(selected) > 10
        chart_spec = {
            "width": "container",
            "height": 430 if not many_lines else 500,
            "mark": {
                "type": "line",
                "point": False if many_lines else {"filled": True, "size": 54},
                "strokeWidth": 1.5 if many_lines else 3.0,
                "opacity": 0.72 if many_lines else 0.95,
            },
            "encoding": {
                "x": {"field": "Runde", "type": "quantitative", "title": "Gameweek", "axis": {"tickMinStep": 1, "format": "d", "grid": False}},
                "y": {"field": "Plassering", "type": "quantitative", "title": "Plassering", "scale": {"reverse": True, "domain": [1, max_rank], "zero": False}, "axis": {"tickMinStep": 1, "format": "d"}},
                "color": {"field": "Manager", "type": "nominal", "title": "Manager", "legend": None if many_lines else {"orient": "bottom", "columns": 3, "labelLimit": 190, "symbolStrokeWidth": 3}},
                "detail": {"field": "Manager", "type": "nominal"},
                "tooltip": [
                    {"field": "Manager", "type": "nominal", "title": "Manager"},
                    {"field": "Lag", "type": "nominal", "title": "Lag"},
                    {"field": "Runde", "type": "quantitative", "title": "GW", "format": "d"},
                    {"field": "Plassering", "type": "quantitative", "title": "Plass", "format": "d"},
                    {"field": "Rundepoeng", "type": "quantitative", "title": "GW-poeng", "format": "d"},
                    {"field": "Poeng totalt", "type": "quantitative", "title": "Totalt", "format": "d"},
                ],
            },
            "config": {"view": {"stroke": None}, "axis": {"labelFontSize": 11, "titleFontSize": 12}, "legend": {"labelFontSize": 10, "titleFontSize": 11}},
        }
        st.vega_lite_chart(chart_df, chart_spec, use_container_width=True)
        if many_lines:
            st.caption("Hele ligaen vises uten legend/punkter for å unngå full spagettikatastrofe. Hold over linjene for detaljer.")

    compact = summary.copy()
    compact["trend"] = compact["movement"].apply(movement_text)
    st.markdown(f"### Topp 10 etter GW{latest_event}")
    display_table(
        compact.head(10),
        ["current_rank", "manager_label", "round_points", "total_points", "trend"],
        {"current_rank": "#", "manager_label": "Manager", "round_points": "GW", "total_points": "Totalt", "trend": "Fra GW1"},
    )
    with st.expander("Se full utviklingstabell"):
        display_table(
            compact,
            ["current_rank", "manager_label", "entry_name", "round_points", "total_points", "trend", "best_rank", "worst_rank", "biggest_jump_text"],
            {"current_rank": "#", "manager_label": "Manager", "entry_name": "Lag", "round_points": "GW", "total_points": "Totalt", "trend": "Fra GW1", "best_rank": "Beste", "worst_rank": "Laveste", "biggest_jump_text": "Største hopp"},
        )


# ============================================================
# V112 - SPILLERE, KAPTEINER OG LIVE-SWINGS
# ============================================================

POSITION_LABELS = {1: "Keeper", 2: "Forsvar", 3: "Midtbane", 4: "Angrep"}
POSITION_SHORT = {1: "K", 2: "F", 3: "M", 4: "A"}


@st.cache_data(ttl=180)
def get_event_live(event_id: int) -> dict:
    """Live poeng for alle spillere i én FPL-runde."""
    return get_json(f"/event/{int(event_id)}/live/")


@st.cache_data(ttl=60)
def get_event_fixtures(event_id: int) -> list[dict]:
    """Kamper i én FPL-runde. Kort cache fordi dette brukes som live-kampmotor."""
    payload = get_json(f"/fixtures/?event={int(event_id)}")
    return payload if isinstance(payload, list) else []


def _live_stats_map(event_id: int) -> dict[int, dict]:
    try:
        payload = get_event_live(int(event_id))
    except Exception:
        return {}
    out = {}
    for row in payload.get("elements", []) or []:
        try:
            element_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        stats = row.get("stats") or {}
        out[element_id] = {
            "points": int(stats.get("total_points") or 0),
            "minutes": int(stats.get("minutes") or 0),
        }
    return out


def build_live_fixture_context(event_id: int) -> dict:
    """Finn kampene som faktisk pågår, pluss neste kamp hvis ingen er live."""
    try:
        bootstrap = get_bootstrap_static()
        fixtures = get_event_fixtures(int(event_id))
    except Exception as error:
        return {"active": [], "next": None, "teams": {}, "error": str(error)}

    teams = {
        int(t.get("id")): str(t.get("short_name") or t.get("name") or t.get("id"))
        for t in (bootstrap.get("teams", []) or []) if t.get("id") is not None
    }
    active = []
    upcoming = []
    for fixture in fixtures:
        started = bool(fixture.get("started"))
        finished = bool(fixture.get("finished"))
        if started and not finished:
            active.append(fixture)
        elif not started:
            upcoming.append(fixture)

    def kickoff_value(f):
        value = f.get("kickoff_time")
        try:
            return pd.Timestamp(value) if value else pd.Timestamp.max.tz_localize("UTC")
        except Exception:
            return pd.Timestamp.max.tz_localize("UTC")

    upcoming = sorted(upcoming, key=kickoff_value)
    return {"active": active, "next": upcoming[0] if upcoming else None, "teams": teams, "error": ""}


def _fixture_label(fixture: dict, teams: dict[int, str]) -> str:
    home = teams.get(int(fixture.get("team_h") or 0), "?")
    away = teams.get(int(fixture.get("team_a") or 0), "?")
    hs = fixture.get("team_h_score")
    aas = fixture.get("team_a_score")
    minutes = int(fixture.get("minutes") or 0)
    score = f"{home} {hs if hs is not None else 0}–{aas if aas is not None else 0} {away}"
    return f"{score} · {minutes}'" if minutes else score


def _next_fixture_label(fixture: dict | None, teams: dict[int, str]) -> str:
    if not fixture:
        return "Ingen flere kamper i runden"
    home = teams.get(int(fixture.get("team_h") or 0), "?")
    away = teams.get(int(fixture.get("team_a") or 0), "?")
    kickoff = fixture.get("kickoff_time")
    when = ""
    if kickoff:
        try:
            ts = pd.Timestamp(kickoff)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            ts = ts.tz_convert("Europe/Oslo")
            when = ts.strftime("%H:%M")
        except Exception:
            when = ""
    return f"{home}–{away}" + (f" · {when}" if when else "")


def render_home_live_snapshot(managers: list[dict]):
    event_id = current_fpl_event_id()
    if event_id is None:
        with st.container(border=True):
            st.caption("LIVE AKKURAT NÅ")
            st.markdown("**Venter på aktiv GW**")
        return
    context = build_live_fixture_context(int(event_id))
    active = context.get("active", [])
    teams = context.get("teams", {})
    with st.container(border=True):
        st.caption("LIVE AKKURAT NÅ")
        if not active:
            st.markdown("**Ingen kamp pågår**")
            st.caption(f"Neste: {_next_fixture_label(context.get('next'), teams)}")
            return
        labels = [_fixture_label(f, teams) for f in active]
        st.markdown("**" + " · ".join(labels) + "**")
        try:
            ownership = build_league_ownership(managers, int(event_id))
            players_df = ownership.get("players", pd.DataFrame()).copy()
            active_ids = set()
            for f in active:
                active_ids.add(int(f.get("team_h") or 0))
                active_ids.add(int(f.get("team_a") or 0))
            if not players_df.empty and "team_id" in players_df.columns:
                live = players_df[players_df["team_id"].isin(active_ids)].sort_values(
                    ["triple_captain_count", "captain_count", "ownership_count"], ascending=[False, False, False]
                ).head(4)
                if not live.empty:
                    bits = []
                    for r in live.itertuples():
                        tag = f"{r.player}: {int(r.ownership_count)} eiere"
                        if int(r.triple_captain_count):
                            tag += f" · TC {getattr(r, 'triple_captains_text', '')}"
                        elif int(r.captain_count):
                            tag += f" · {int(r.captain_count)} C"
                        bits.append(tag)
                    st.caption(" | ".join(bits))
        except Exception:
            st.caption("Live-spillerdata oppdateres fortløpende.")


def render_live_match_centre(managers: list[dict], ownership: dict | None = None):
    """Kompakt livefelt: kamper nå + LRO-spillere som betyr mest i de kampene."""
    event_id = current_fpl_event_id()
    if event_id is None:
        return
    context = build_live_fixture_context(int(event_id))
    active = context.get("active", [])
    teams = context.get("teams", {})

    st.markdown("## Live akkurat nå")
    if not active:
        with st.container(border=True):
            st.caption(f"GW{event_id} · INGEN KAMP PÅGÅR")
            st.markdown(f"**Neste: {_next_fixture_label(context.get('next'), teams)}**")
            st.caption("Når en kamp starter, dukker de viktigste Lofthus-spillerne og kapteinsvalgene opp her automatisk.")
        return

    if ownership is None:
        with st.spinner("Leser Lofthus-lag for livebildet …"):
            ownership = build_league_ownership(managers, int(event_id))
    players_df = ownership.get("players", pd.DataFrame()).copy()

    active_team_ids = set()
    match_by_team = {}
    match_labels = []
    for fixture in active:
        label = _fixture_label(fixture, teams)
        match_labels.append(label)
        for key in ("team_h", "team_a"):
            try:
                tid = int(fixture.get(key) or 0)
            except (TypeError, ValueError):
                continue
            active_team_ids.add(tid)
            match_by_team[tid] = label

    joined_matches = " &nbsp; | &nbsp; ".join(html.escape(x) for x in match_labels)
    st.markdown(
        f'''<div style="background:linear-gradient(110deg,#071525,#064e3b 58%,#511b1b);color:white;border-radius:18px;padding:16px 18px;margin:4px 0 14px 0">
        <div style="font-size:.72rem;color:#fde68a;font-weight:900;letter-spacing:.09em;text-transform:uppercase">GW{event_id} · LIVE</div>
        <div style="font-size:1.15rem;font-weight:900;margin-top:4px">{joined_matches}</div>
        <div style="font-size:.84rem;color:#d1fae5;margin-top:5px">Her ser du spillerne som kan flytte Lofthus akkurat nå.</div>
        </div>''',
        unsafe_allow_html=True,
    )

    if players_df.empty or "team_id" not in players_df.columns:
        st.caption("Kampene er live, men spillerdata kunne ikke kobles akkurat nå.")
        return

    live_players = players_df[players_df["team_id"].isin(active_team_ids)].copy()
    if live_players.empty:
        st.caption("Ingen Lofthus-eide spillere fra lagene i aksjon ble funnet.")
        return
    live_players["kamp"] = live_players["team_id"].map(match_by_team)
    live_players = live_players.sort_values(
        ["triple_captain_count", "captain_count", "ownership_count", "event_points"],
        ascending=[False, False, False, False],
    )

    tc = live_players[live_players["triple_captain_count"] > 0]
    if not tc.empty:
        alarms = []
        for r in tc.itertuples():
            names = str(getattr(r, "triple_captains_text", "") or "")
            alarms.append(f"{r.player}: {names}")
        lro_note("🚨 Triple captain live", " · ".join(alarms), "gold")

    display_table(
        live_players.head(12),
        ["player", "club", "event_points", "ownership_count", "captain_count", "triple_captain_count", "captains_text"],
        {"player": "Spiller", "club": "Klubb", "event_points": "GW", "ownership_count": "Eiere", "captain_count": "C", "triple_captain_count": "TC", "captains_text": "Hvem har bindet"},
    )


def current_fpl_event_id() -> int | None:
    """Runden som er relevant for picks akkurat nå."""
    try:
        data = get_bootstrap_static()
    except Exception:
        return None

    events = data.get("events", []) or []
    current = [event for event in events if event.get("is_current")]
    if current:
        try:
            return int(current[0].get("id"))
        except (TypeError, ValueError):
            pass

    finished = []
    for event in events:
        if event.get("finished"):
            try:
                finished.append(int(event.get("id")))
            except (TypeError, ValueError):
                pass
    return max(finished) if finished else None


def _live_points_map(event_id: int) -> dict[int, int]:
    try:
        payload = get_event_live(int(event_id))
    except Exception:
        return {}
    out = {}
    for row in payload.get("elements", []) or []:
        try:
            out[int(row.get("id"))] = int((row.get("stats") or {}).get("total_points") or 0)
        except (TypeError, ValueError):
            continue
    return out


def build_league_ownership(managers: list[dict], event_id: int | None = None) -> dict:
    """Samle alle LRO-lag for én GW, inkludert kapteiner, chips og livebidrag."""
    empty_players = pd.DataFrame(columns=[
        "element", "player", "full_name", "club", "team_id", "position", "position_id",
        "ownership_count", "ownership_pct", "started_count", "bench_count",
        "captain_count", "captain_pct", "triple_captain_count", "vice_count",
        "effective_ownership_count", "effective_ownership_pct", "event_points",
        "season_points", "live_minutes", "owners_text", "captains_text", "triple_captains_text",
    ])
    empty_picks = pd.DataFrame(columns=[
        "entry", "manager", "team", "rank", "element", "player", "full_name",
        "club", "team_id", "position", "position_id", "squad_position", "multiplier",
        "is_captain", "is_vice_captain", "on_bench", "event_points",
        "season_points", "live_minutes", "gw_contribution",
    ])
    empty_events = pd.DataFrame(columns=[
        "entry", "manager", "team", "rank", "active_chip", "gw_points",
        "total_points", "event_transfers", "event_transfers_cost", "points_on_bench", "bank", "value",
    ])

    if not managers:
        return {"event": event_id, "players": empty_players, "picks": empty_picks,
                "manager_events": empty_events, "loaded_managers": 0,
                "league_size": 0, "errors": []}

    try:
        bootstrap = get_bootstrap_static()
    except Exception as error:
        return {"event": event_id, "players": empty_players, "picks": empty_picks,
                "manager_events": empty_events, "loaded_managers": 0,
                "league_size": len(managers), "errors": [str(error)]}

    if event_id is None:
        event_id = current_fpl_event_id()
    if event_id is None:
        return {"event": None, "players": empty_players, "picks": empty_picks,
                "manager_events": empty_events, "loaded_managers": 0,
                "league_size": len(managers), "errors": ["Fant ingen aktiv eller ferdig FPL-runde."]}

    teams = {
        int(row.get("id")): str(row.get("short_name") or row.get("name") or "")
        for row in (bootstrap.get("teams", []) or []) if row.get("id") is not None
    }
    elements = {}
    for row in bootstrap.get("elements", []) or []:
        try:
            element_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        position_id = int(row.get("element_type") or 0)
        elements[element_id] = {
            "player": str(row.get("web_name") or row.get("second_name") or row.get("first_name") or element_id),
            "full_name": f"{row.get('first_name') or ''} {row.get('second_name') or ''}".strip(),
            "club": teams.get(int(row.get("team") or 0), ""),
            "team_id": int(row.get("team") or 0),
            "position_id": position_id,
            "position": POSITION_LABELS.get(position_id, "Ukjent"),
            "season_points": int(row.get("total_points") or 0),
        }

    live_stats = _live_stats_map(int(event_id))
    pick_rows = []
    manager_event_rows = []
    errors = []
    loaded_entries = set()

    def _fetch_one(manager: dict):
        entry = manager.get("entry")
        if not entry:
            return manager, None, "Mangler entry-ID"
        try:
            entry = int(entry)
            return manager, get_entry_event_picks(entry, int(event_id)), None
        except Exception as error:
            return manager, None, str(error)

    fetched = []
    # 63 offentlige lag er nok til at sekvensielle kall merkes. Hold worker-antallet
    # moderat, både for FPL og for Streamlit Cloud.
    with ThreadPoolExecutor(max_workers=min(12, max(1, len(managers)))) as pool:
        futures = [pool.submit(_fetch_one, manager) for manager in managers if manager.get("entry")]
        for future in as_completed(futures):
            fetched.append(future.result())

    # Stabil rekkefølge gjør både testing og UI forutsigbart.
    fetched.sort(key=lambda item: normalize_text(str((item[0] or {}).get("player_name") or "")))

    for manager, payload, fetch_error in fetched:
        entry = int(manager.get("entry"))
        if fetch_error or payload is None:
            errors.append({
                "manager": str(manager.get("player_name") or "Ukjent manager"),
                "entry": entry,
                "error": fetch_error or "Ukjent feil",
            })
            continue
        picks = payload.get("picks", []) or []
        if not picks:
            errors.append({
                "manager": str(manager.get("player_name") or "Ukjent manager"),
                "entry": entry,
                "error": "Ingen picks tilgjengelig",
            })
            continue

        loaded_entries.add(entry)
        manager_name = canonical_hof_name(str(manager.get("player_name") or "Ukjent manager"))
        team_name = str(manager.get("entry_name") or "Ukjent lag")
        rank_value = pd.to_numeric(manager.get("rank"), errors="coerce")
        entry_history = payload.get("entry_history") or {}
        manager_event_rows.append({
            "entry": entry,
            "manager": manager_name,
            "team": team_name,
            "rank": rank_value,
            "active_chip": str(payload.get("active_chip") or ""),
            "gw_points": int(entry_history.get("points") or manager.get("event_total") or 0),
            "total_points": int(entry_history.get("total_points") or manager.get("total") or 0),
            "event_transfers": int(entry_history.get("event_transfers") or 0),
            "event_transfers_cost": int(entry_history.get("event_transfers_cost") or 0),
            "points_on_bench": int(entry_history.get("points_on_bench") or 0),
            "bank": int(entry_history.get("bank") or 0),
            "value": int(entry_history.get("value") or 0),
        })

        for pick in picks:
            try:
                element = int(pick.get("element"))
                squad_position = int(pick.get("position") or 0)
                multiplier = int(pick.get("multiplier") or 0)
            except (TypeError, ValueError):
                continue
            meta = elements.get(element, {
                "player": f"Spiller {element}", "full_name": "", "club": "", "team_id": 0,
                "position_id": 0, "position": "Ukjent", "season_points": 0,
            })
            element_live = live_stats.get(element, {})
            event_points = int(element_live.get("points", 0) or 0)
            live_minutes = int(element_live.get("minutes", 0) or 0)
            pick_rows.append({
                "entry": entry,
                "manager": manager_name,
                "team": team_name,
                "rank": rank_value,
                "element": element,
                "player": meta["player"],
                "full_name": meta.get("full_name", ""),
                "club": meta["club"],
                "team_id": int(meta.get("team_id", 0) or 0),
                "position_id": meta["position_id"],
                "position": meta["position"],
                "squad_position": squad_position,
                "multiplier": multiplier,
                "is_captain": bool(pick.get("is_captain")),
                "is_vice_captain": bool(pick.get("is_vice_captain")),
                "on_bench": squad_position > 11,
                "event_points": event_points,
                "season_points": meta["season_points"],
                "live_minutes": live_minutes,
                "gw_contribution": event_points * multiplier,
            })

    picks_df = pd.DataFrame(pick_rows)
    manager_events_df = pd.DataFrame(manager_event_rows)
    loaded_count = len(loaded_entries)
    if picks_df.empty:
        return {"event": int(event_id), "players": empty_players, "picks": empty_picks,
                "manager_events": manager_events_df, "loaded_managers": loaded_count,
                "league_size": len(managers), "errors": errors}

    player_rows = []
    for element, player_df in picks_df.groupby("element", sort=False):
        first = player_df.iloc[0]
        owners = player_df.sort_values(["manager", "team"])
        captains = owners[owners["is_captain"]]
        triple_captains = captains[captains["multiplier"] >= 3]
        owner_count = int(owners["entry"].nunique())
        eo_count = int(owners["multiplier"].clip(lower=0).sum())
        player_rows.append({
            "element": int(element),
            "player": first["player"],
            "full_name": first.get("full_name", ""),
            "club": first["club"],
            "team_id": int(first.get("team_id", 0) or 0),
            "position": first["position"],
            "position_id": int(first["position_id"]),
            "ownership_count": owner_count,
            "ownership_pct": round(owner_count / loaded_count * 100, 1) if loaded_count else 0.0,
            "started_count": int((~owners["on_bench"]).sum()),
            "bench_count": int(owners["on_bench"].sum()),
            "captain_count": int(owners["is_captain"].sum()),
            "captain_pct": round(int(owners["is_captain"].sum()) / loaded_count * 100, 1) if loaded_count else 0.0,
            "triple_captain_count": int(((owners["is_captain"]) & (owners["multiplier"] >= 3)).sum()),
            "vice_count": int(owners["is_vice_captain"].sum()),
            "effective_ownership_count": eo_count,
            "effective_ownership_pct": round(eo_count / loaded_count * 100, 1) if loaded_count else 0.0,
            "event_points": int(first.get("event_points", 0) or 0),
            "season_points": int(first.get("season_points", 0) or 0),
            "live_minutes": int(first.get("live_minutes", 0) or 0),
            "owners_text": " · ".join(owners["manager"].astype(str).tolist()),
            "captains_text": " · ".join(captains["manager"].astype(str).tolist()),
            "triple_captains_text": " · ".join(triple_captains["manager"].astype(str).tolist()),
        })

    players_df = pd.DataFrame(player_rows).sort_values(
        ["ownership_count", "captain_count", "season_points", "player"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    players_df.insert(0, "ownership_rank", range(1, len(players_df) + 1))

    return {
        "event": int(event_id),
        "players": players_df,
        "picks": picks_df,
        "manager_events": manager_events_df,
        "loaded_managers": loaded_count,
        "league_size": len(managers),
        "errors": errors,
    }


def build_template_xi(players_df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if players_df is None or players_df.empty:
        return pd.DataFrame(), ""

    candidates = players_df.copy().sort_values(
        ["ownership_count", "captain_count", "season_points"], ascending=[False, False, False]
    )
    selected = []
    selected_ids = set()
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    minimums = {1: 1, 2: 3, 3: 2, 4: 1}
    maximums = {1: 1, 2: 5, 3: 5, 4: 3}

    for pos, minimum in minimums.items():
        pool = candidates[candidates["position_id"] == pos].head(minimum)
        for _, row in pool.iterrows():
            selected.append(row.to_dict())
            selected_ids.add(int(row["element"]))
            counts[pos] += 1

    for _, row in candidates.iterrows():
        if len(selected) >= 11:
            break
        element = int(row["element"])
        pos = int(row["position_id"])
        if element in selected_ids or pos not in maximums:
            continue
        if counts[pos] >= maximums[pos]:
            continue
        selected.append(row.to_dict())
        selected_ids.add(element)
        counts[pos] += 1

    template = pd.DataFrame(selected)
    if template.empty:
        return template, ""
    template = template.sort_values(["position_id", "ownership_count"], ascending=[True, False]).reset_index(drop=True)
    formation = f"{counts[2]}-{counts[3]}-{counts[4]}"
    return template, formation


def build_template_squad(players_df: pd.DataFrame) -> set[int]:
    """15-manns template for å måle hvor likt hvert lag er kollektivet."""
    if players_df is None or players_df.empty:
        return set()
    quotas = {1: 2, 2: 5, 3: 5, 4: 3}
    selected = set()
    for pos_id, count in quotas.items():
        pool = players_df[players_df["position_id"] == pos_id].sort_values(
            ["ownership_count", "captain_count", "season_points"], ascending=[False, False, False]
        ).head(count)
        selected.update(pool["element"].astype(int).tolist())
    return selected


def build_manager_style_table(ownership: dict) -> pd.DataFrame:
    picks_df = ownership.get("picks", pd.DataFrame())
    players_df = ownership.get("players", pd.DataFrame())
    events_df = ownership.get("manager_events", pd.DataFrame())
    if picks_df.empty or players_df.empty:
        return pd.DataFrame()

    lookup = players_df.set_index("element")
    template_ids = build_template_squad(players_df)
    event_lookup = events_df.set_index("entry") if not events_df.empty else pd.DataFrame()
    rows = []
    for entry, group in picks_df.groupby("entry"):
        ids = set(group["element"].astype(int).tolist())
        own_pcts = [float(lookup.loc[e, "ownership_pct"]) for e in ids if e in lookup.index]
        diff_count = sum(int(lookup.loc[e, "ownership_count"]) <= 3 for e in ids if e in lookup.index)
        overlap = len(ids & template_ids)
        first = group.iloc[0]
        event_row = event_lookup.loc[entry] if not event_lookup.empty and entry in event_lookup.index else None
        rows.append({
            "entry": int(entry),
            "manager": str(first["manager"]),
            "team": str(first["team"]),
            "rank": first.get("rank"),
            "template_overlap": overlap,
            "template_pct": round(overlap / 15 * 100, 1),
            "avg_ownership_pct": round(sum(own_pcts) / len(own_pcts), 1) if own_pcts else 0.0,
            "differential_count": int(diff_count),
            "gw_points": int(event_row.get("gw_points", 0)) if event_row is not None else 0,
            "bench_points": int(event_row.get("points_on_bench", 0)) if event_row is not None else int(group[group["on_bench"]]["event_points"].sum()),
            "active_chip": str(event_row.get("active_chip", "")) if event_row is not None else "",
        })
    return pd.DataFrame(rows).sort_values(["rank", "manager"], na_position="last").reset_index(drop=True)


def build_ownership_changes(current: dict, previous: dict) -> dict:
    cur_players = current.get("players", pd.DataFrame())
    prev_players = previous.get("players", pd.DataFrame())
    cur_picks = current.get("picks", pd.DataFrame())
    prev_picks = previous.get("picks", pd.DataFrame())
    empty = pd.DataFrame()
    if cur_players.empty or prev_players.empty or cur_picks.empty or prev_picks.empty:
        return {"players": empty, "moves": empty}

    prev_base = prev_players[["element", "ownership_count", "captain_count"]].rename(columns={
        "ownership_count": "previous_ownership", "captain_count": "previous_captains"
    })
    changes = cur_players.merge(prev_base, on="element", how="outer")
    for col in ["ownership_count", "captain_count", "previous_ownership", "previous_captains"]:
        changes[col] = pd.to_numeric(changes.get(col), errors="coerce").fillna(0).astype(int)
    changes["ownership_delta"] = changes["ownership_count"] - changes["previous_ownership"]
    changes["captain_delta"] = changes["captain_count"] - changes["previous_captains"]

    meta = {}
    for source in [cur_players, prev_players]:
        for _, row in source.iterrows():
            meta[int(row["element"])] = {
                "player": row.get("player", ""), "club": row.get("club", ""), "position": row.get("position", "")
            }
    if "player" not in changes.columns:
        changes["player"] = changes["element"].map(lambda e: meta.get(int(e), {}).get("player", str(e)))
    else:
        changes["player"] = changes.apply(
            lambda r: meta.get(int(r["element"]), {}).get("player", "") if pd.isna(r.get("player")) or str(r.get("player") or "").strip() == "" else r.get("player"),
            axis=1,
        )
    move_rows = []
    all_entries = sorted(set(cur_picks["entry"].astype(int)) & set(prev_picks["entry"].astype(int)))
    for entry in all_entries:
        cg = cur_picks[cur_picks["entry"] == entry]
        pg = prev_picks[prev_picks["entry"] == entry]
        cur_ids = set(cg["element"].astype(int))
        prev_ids = set(pg["element"].astype(int))
        manager = str(cg.iloc[0]["manager"]) if not cg.empty else str(pg.iloc[0]["manager"])
        for element in cur_ids - prev_ids:
            move_rows.append({"element": element, "player": meta.get(element, {}).get("player", str(element)), "manager": manager, "move": "Inn"})
        for element in prev_ids - cur_ids:
            move_rows.append({"element": element, "player": meta.get(element, {}).get("player", str(element)), "manager": manager, "move": "Ut"})
    moves = pd.DataFrame(move_rows)
    return {"players": changes, "moves": moves}


def radar_metric_strip(cards: list[dict]):
    if not cards:
        return
    blocks = []
    for card in cards[:4]:
        eyebrow = html.escape(str(card.get("label", "")))
        value = html.escape(str(card.get("value", "–")))
        caption = html.escape(str(card.get("caption", "")))
        blocks.append(f'<div class="radar-kpi"><div class="radar-kpi-label">{eyebrow}</div><div class="radar-kpi-value">{value}</div><div class="radar-kpi-caption">{caption}</div></div>')
    st.markdown(
        f'''<style>
        .radar-kpis{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:8px 0 18px 0}}
        .radar-kpi{{background:#ffffff;border:1px solid #e5e7eb;border-radius:15px;padding:13px 14px;color:#111827;min-height:94px;box-shadow:0 5px 16px rgba(15,23,42,.045)}}
        .radar-kpi-label{{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:#7f1d1d;font-weight:850}}
        .radar-kpi-value{{font-size:1rem;font-weight:900;margin-top:6px;line-height:1.12;overflow-wrap:anywhere}}
        .radar-kpi-caption{{font-size:.78rem;color:#667085;margin-top:6px}}
        @media(max-width:900px){{.radar-kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
        @media(max-width:560px){{.radar-kpis{{grid-template-columns:1fr}}}}
        </style><div class="radar-kpis">{''.join(blocks)}</div>''',
        unsafe_allow_html=True,
    )


def movement_text(delta: Any) -> str:
    if delta is None or pd.isna(delta):
        return "━ 0"
    delta = int(delta)
    if delta > 0:
        return f"↑ +{delta}"
    if delta < 0:
        return f"↓ {delta}"
    return "━ 0"


def render_radar_overview(managers: list[dict], radar: dict[str, pd.DataFrame]):
    df = pd.DataFrame(managers or []).copy()
    if df.empty:
        st.info("Ingen ligadata å vise ennå.")
        return

    df["rank_num"] = pd.to_numeric(df.get("rank"), errors="coerce")
    df["last_rank_num"] = pd.to_numeric(df.get("last_rank"), errors="coerce")
    df["event_total_num"] = pd.to_numeric(df.get("event_total"), errors="coerce")
    df["total_num"] = pd.to_numeric(df.get("total"), errors="coerce")
    df["form_delta"] = df["last_rank_num"] - df["rank_num"]
    live = df["rank_num"].notna().any()

    if live:
        current = df.sort_values(["rank_num", "total_num", "player_name"], ascending=[True, False, True]).copy()
        leader = current.iloc[0]
        round_king = df.sort_values(["event_total_num", "rank_num"], ascending=[False, True], na_position="last").iloc[0]
        climber = radar.get("climbers", pd.DataFrame())
        form = radar.get("form_three", pd.DataFrame())
        cards = [
            {"label": "Ligaleder", "value": leader.get("player_name", "–"), "caption": f"{int(leader.get('total_num') or 0)} poeng"},
            {"label": "Rundens beste", "value": round_king.get("player_name", "–"), "caption": f"{int(round_king.get('event_total_num') or 0)} poeng denne GW"},
            {"label": "Største klatrer", "value": climber.iloc[0].get("player_name", "–") if not climber.empty else "–", "caption": climber.iloc[0].get("form_curve", "Ingen bevegelse") if not climber.empty else "Ingen bevegelse"},
            {"label": "Formkonge", "value": form.iloc[0].get("player_name", "–") if not form.empty else "–", "caption": f"{int(form.iloc[0].get('last_three_points') or 0)} p siste tre" if not form.empty else "Venter på flere runder"},
        ]
        radar_metric_strip(cards)
    else:
        st.info("Live-radaren venter på første tellende FPL-tabell. Sesongløpet bruker demo til ekte plasseringer finnes.")


def _role_label(row: pd.Series) -> str:
    if bool(row.get("is_captain")):
        return "TC" if int(row.get("multiplier") or 0) >= 3 else "C"
    if bool(row.get("is_vice_captain")):
        return "VC"
    if bool(row.get("on_bench")):
        return "Benk"
    return "Start"


def _short_manager_list(values, max_names: int = 3) -> str:
    names = [str(v).strip() for v in list(values) if str(v).strip()]
    if not names:
        return "Ingen"
    if len(names) <= max_names:
        return " · ".join(names)
    return " · ".join(names[:max_names]) + f" · +{len(names) - max_names} til"


def render_player_profile(selected_row: pd.Series, ownership: dict):
    """Forklar ett spillervalg som et menneske faktisk ville gjort det i sofaen."""
    picks_df = ownership["picks"]
    loaded = int(ownership["loaded_managers"] or 0)
    selected_id = int(selected_row["element"])
    player_name = str(selected_row.get("player") or "Spilleren")
    club = str(selected_row.get("club") or "")

    owners = picks_df[picks_df["element"] == selected_id].copy().sort_values(["multiplier", "manager"], ascending=[False, True])
    owners["rolle"] = owners.apply(_role_label, axis=1)
    captains = owners[owners["is_captain"]]
    triple_captains = captains[captains["multiplier"] >= 3]
    normal_captains = captains[captains["multiplier"] < 3]
    starters = owners[(~owners["on_bench"]) & (~owners["is_captain"])]
    benched = owners[owners["on_bench"]]

    owner_count = int(selected_row.get("ownership_count") or len(owners))
    captain_count = int(selected_row.get("captain_count") or len(captains))
    tc_count = int(selected_row.get("triple_captain_count") or len(triple_captains))
    without_count = max(0, loaded - owner_count)

    st.markdown(f"### {player_name}" + (f" · {club}" if club else ""))
    radar_metric_strip([
        {"label": "Eies av", "value": f"{owner_count} av {loaded}", "caption": f"{float(selected_row.get('ownership_pct') or 0):.1f}% av ligaen"},
        {"label": "Kaptein hos", "value": str(captain_count), "caption": "inkludert Triple Captain"},
        {"label": "Triple Captain", "value": str(tc_count), "caption": "får trippel uttelling"},
        {"label": "Har ham ikke", "value": str(without_count), "caption": "får ingen poeng fra spilleren"},
    ])

    st.markdown(f"#### Hvis {player_name} leverer")
    sentence_bits = []
    if tc_count:
        sentence_bits.append(f"**{tc_count}** får trippel uttelling")
    if len(normal_captains):
        sentence_bits.append(f"**{len(normal_captains)}** får dobbel uttelling")
    if len(starters):
        sentence_bits.append(f"**{len(starters)}** får vanlige poeng")
    if len(benched):
        sentence_bits.append(f"**{len(benched)}** har ham på benken")
    if without_count:
        sentence_bits.append(f"**{without_count}** har ham ikke")
    if sentence_bits:
        st.write(", ".join(sentence_bits[:-1]) + ((" og " + sentence_bits[-1]) if len(sentence_bits) > 1 else sentence_bits[-1]) + ".")

    if not triple_captains.empty:
        lro_note("🚨 TRIPLE CAPTAIN", _short_manager_list(triple_captains["manager"], 5), "gold")

    with st.container(border=True):
        st.markdown("**© Hvem har gitt ham kapteinsbindet?**")
        if normal_captains.empty:
            st.caption("Ingen har vanlig kaptein på spilleren denne runden.")
        else:
            st.write(_short_manager_list(normal_captains["manager"], 5))
            if len(normal_captains) > 5:
                with st.expander(f"Se alle {len(normal_captains)} vanlige kapteiner"):
                    for name in normal_captains["manager"].tolist():
                        st.write(f"• {name}")

    quick = st.columns(3, gap="medium")
    with quick[0]:
        with st.container(border=True):
            st.caption("STARTER UTEN BIND")
            st.markdown(f"**{len(starters)} managere**")
    with quick[1]:
        with st.container(border=True):
            st.caption("PÅ BENKEN")
            st.markdown(f"**{len(benched)} managere**")
    with quick[2]:
        with st.container(border=True):
            st.caption("UTEN SPILLEREN")
            st.markdown(f"**{without_count} managere**")

    with st.expander(f"Se alle som eier {player_name} ({owner_count})"):
        if owners.empty:
            st.caption("Ingen eiere registrert.")
        else:
            roles = owners[["manager", "rolle"]].copy()
            display_table(roles, ["manager", "rolle"], {"manager": "Manager", "rolle": "Bruk"})

    with st.expander("Hva betyr tallene?"):
        st.write("Kaptein gir dobbel uttelling. Triple Captain gir trippel. Vanlige startere får spillerens vanlige poeng, mens en spiller på benken normalt ikke teller med mindre han blir autosubbet inn.")
        st.caption(f"Effektivt eierskap (EO) er {float(selected_row.get('effective_ownership_pct') or 0):.1f} %. Det er et nerdetall som også tar hensyn til kapteinsdobling og Triple Captain, og derfor ligger det her nede i stedet for å late som alle trenger det til frokost.")

def v200_chip_label(value: Any) -> str:
    """Vis FPLs interne chipkoder med navn folk faktisk bruker."""
    raw = str(value or "").strip()
    if not raw:
        return "Ingen"
    key = raw.lower().replace("-", "_").replace(" ", "_")
    labels = {
        "bboost": "Bench Boost",
        "bbost": "Bench Boost",
        "bench_boost": "Bench Boost",
        "3xc": "Triple Captain",
        "triple_captain": "Triple Captain",
        "freehit": "Free Hit",
        "free_hit": "Free Hit",
        "wildcard": "Wildcard",
        "wildcard1": "Wildcard",
        "wildcard2": "Wildcard",
    }
    return labels.get(key, raw.replace("_", " ").strip().title())


def render_manager_profile(selected_entry: int, ownership: dict, managers: list[dict]):
    picks_df = ownership["picks"]
    players_df = ownership["players"]
    events_df = ownership["manager_events"]
    style_df = build_manager_style_table(ownership)
    group = picks_df[picks_df["entry"] == int(selected_entry)].copy()
    if group.empty:
        st.caption("Fant ikke picks for manageren i denne runden.")
        return

    row = style_df[style_df["entry"] == int(selected_entry)]
    style = row.iloc[0] if not row.empty else None
    event_row = events_df[events_df["entry"] == int(selected_entry)]
    event = event_row.iloc[0] if not event_row.empty else None
    manager_name = str(group.iloc[0]["manager"])
    team_name = str(group.iloc[0]["team"])
    rank = style.get("rank") if style is not None else None
    rank_text = str(int(rank)) if rank is not None and not pd.isna(rank) else "–"

    radar_metric_strip([
        {"label": "Plass", "value": rank_text, "caption": team_name},
        {"label": "GW-poeng", "value": str(int(style.get("gw_points", 0))) if style is not None else "–", "caption": f"Benk: {int(style.get('bench_points', 0)) if style is not None else 0} p"},
        {"label": "Template", "value": f"{float(style.get('template_pct', 0)):.0f}%" if style is not None else "–", "caption": f"{int(style.get('template_overlap', 0)) if style is not None else 0}/15 fra LRO-template"},
        {"label": "Differensialer", "value": str(int(style.get("differential_count", 0))) if style is not None else "–", "caption": v200_chip_label(event.get("active_chip")) if event is not None else "Ingen"},
    ])

    lookup = players_df.set_index("element")
    group["ownership_pct"] = group["element"].map(lambda e: float(lookup.loc[e, "ownership_pct"]) if e in lookup.index else 0.0)
    group["eo_pct"] = group["element"].map(lambda e: float(lookup.loc[e, "effective_ownership_pct"]) if e in lookup.index else 0.0)
    group["rolle"] = group.apply(_role_label, axis=1)
    group = group.sort_values(["squad_position", "position_id"])
    with st.expander(f"Se troppen til {manager_name}"):
        display_table(
            group,
            ["rolle", "player", "club", "event_points", "gw_contribution", "ownership_pct", "eo_pct"],
            {"rolle": "Rolle", "player": "Spiller", "club": "Klubb", "event_points": "GW", "gw_contribution": "Bidrag", "ownership_pct": "Eid %", "eo_pct": "EO %"},
        )

    selected_ids = set(group["element"].astype(int))
    missing = players_df[~players_df["element"].isin(selected_ids)].head(10).copy()
    if not missing.empty:
        st.caption("POPULÆRE SPILLERE MANAGEREN GÅR UTEN")
        display_table(missing.head(6), ["player", "ownership_count", "ownership_pct", "captain_count"], {"player": "Spiller", "ownership_count": "Eiere", "ownership_pct": "%", "captain_count": "Kapteiner"})

    manager_df = pd.DataFrame(managers or []).copy()
    manager_df["rank_num"] = pd.to_numeric(manager_df.get("rank"), errors="coerce")
    selected_rank = pd.to_numeric(group.iloc[0].get("rank"), errors="coerce")
    if pd.notna(selected_rank):
        rivals = manager_df[(manager_df["entry"].astype(str) != str(selected_entry)) & manager_df["rank_num"].notna()].copy()
        rivals["distance"] = (rivals["rank_num"] - float(selected_rank)).abs()
        rivals = rivals.sort_values(["distance", "rank_num"]).head(4)
        rival_entries = set(pd.to_numeric(rivals["entry"], errors="coerce").dropna().astype(int))
        rival_picks = picks_df[picks_df["entry"].isin(rival_entries) & ~picks_df["element"].isin(selected_ids)].copy()
        if not rival_picks.empty:
            threat_rows = []
            for element, threat in rival_picks.groupby("element"):
                first = threat.iloc[0]
                threat_rows.append({
                    "player": first["player"],
                    "rivals": int(threat["entry"].nunique()),
                    "captains": int(threat["is_captain"].sum()),
                    "event_points": int(first.get("event_points", 0)),
                    "managers": ", ".join(threat.sort_values(["is_captain", "manager"], ascending=[False, True])["manager"].tolist()),
                })
            threats = pd.DataFrame(threat_rows).sort_values(["captains", "rivals", "event_points"], ascending=[False, False, False]).head(8)
            st.caption("HVEM MÅ JEG FRYKTE? · NÆRMESTE RIVALER")
            display_table(threats, ["player", "rivals", "captains", "event_points", "managers"], {"player": "Spiller du mangler", "rivals": "Rivaler", "captains": "C", "event_points": "GW", "managers": "Hvem har ham"})

    try:
        history = get_entry_history(int(selected_entry))
        recent = (history.get("current", []) or [])[-3:]
        if len(recent) >= 3:
            transfers = sum(int(r.get("event_transfers") or 0) for r in recent)
            if transfers == 0:
                st.caption("Aktivitetssignal: Ingen transfers de siste tre registrerte rundene.")
            else:
                st.caption(f"Aktivitetssignal: {transfers} transfer(s) de siste tre rundene.")
    except Exception:
        pass


def render_head_to_head(ownership: dict):
    picks_df = ownership["picks"]
    events_df = ownership["manager_events"]
    if picks_df.empty:
        return
    managers_options = picks_df[["entry", "manager"]].drop_duplicates().sort_values("manager")
    options = [(int(r.entry), str(r.manager)) for r in managers_options.itertuples()]
    if len(options) < 2:
        return
    labels = {entry: name for entry, name in options}
    c1, c2 = st.columns(2)
    with c1:
        left = st.selectbox("Manager A", [e for e, _ in options], format_func=lambda e: labels[e], index=0, key="h2h_left_v112")
    with c2:
        right_default = 1 if len(options) > 1 else 0
        right = st.selectbox("Manager B", [e for e, _ in options], format_func=lambda e: labels[e], index=right_default, key="h2h_right_v112")
    if left == right:
        st.caption("Velg to ulike managere.")
        return

    lg = picks_df[picks_df["entry"] == left]
    rg = picks_df[picks_df["entry"] == right]
    left_ids = set(lg["element"].astype(int))
    right_ids = set(rg["element"].astype(int))
    shared = len(left_ids & right_ids)
    left_event = events_df[events_df["entry"] == left]
    right_event = events_df[events_df["entry"] == right]
    lp = int(left_event.iloc[0]["gw_points"]) if not left_event.empty else 0
    rp = int(right_event.iloc[0]["gw_points"]) if not right_event.empty else 0
    radar_metric_strip([
        {"label": "Like spillere", "value": str(shared), "caption": f"{15-shared} forskjeller i troppene"},
        {"label": labels[left], "value": str(lp), "caption": "GW-poeng"},
        {"label": labels[right], "value": str(rp), "caption": "GW-poeng"},
        {"label": "Swing", "value": f"{abs(lp-rp)} p", "caption": "Forskjell denne runden"},
    ])

    union = (left_ids | right_ids) - (left_ids & right_ids)
    swing_rows = []
    for element in union:
        lr = lg[lg["element"] == element]
        rr = rg[rg["element"] == element]
        source = lr if not lr.empty else rr
        if source.empty:
            continue
        first = source.iloc[0]
        lmult = int(lr.iloc[0]["multiplier"]) if not lr.empty else 0
        rmult = int(rr.iloc[0]["multiplier"]) if not rr.empty else 0
        points = int(first.get("event_points", 0))
        swing_rows.append({
            "player": first["player"],
            labels[left]: lmult,
            labels[right]: rmult,
            "gw_points": points,
            "swing": points * (lmult - rmult),
        })
    swing_df = pd.DataFrame(swing_rows)
    if not swing_df.empty:
        swing_df["abs_swing"] = swing_df["swing"].abs()
        swing_df = swing_df.sort_values(["abs_swing", "player"], ascending=[False, True]).drop(columns=["abs_swing"])
        display_table(swing_df.head(12), ["player", labels[left], labels[right], "gw_points", "swing"], {"player": "Forskjellsspiller", labels[left]: labels[left], labels[right]: labels[right], "gw_points": "GW", "swing": "Poengsving"})


def render_ownership_trends(managers: list[dict], ownership: dict):
    event_id = int(ownership.get("event") or 0)
    if event_id <= 1:
        st.caption("Trenger minst to runder før vi kan vise kjøp, salg og kapteinsendringer.")
        return
    with st.spinner(f"Sammenligner GW{event_id} med GW{event_id-1} …"):
        previous = build_league_ownership(managers, event_id - 1)
    changes = build_ownership_changes(ownership, previous)
    player_changes = changes["players"]
    moves = changes["moves"]
    if player_changes.empty:
        st.caption("Fant ikke nok data fra forrige runde.")
        return

    incoming = player_changes.sort_values(["ownership_delta", "captain_delta"], ascending=[False, False]).head(8)
    outgoing = player_changes.sort_values(["ownership_delta", "captain_delta"], ascending=[True, True]).head(8)
    cap_changes = player_changes.reindex(player_changes["captain_delta"].abs().sort_values(ascending=False).index).head(8)
    a, b = st.columns(2)
    with a:
        st.markdown("**Mest kjøpt i Lofthus**")
        display_table(incoming, ["player", "ownership_count", "ownership_delta"], {"player": "Spiller", "ownership_count": "Nå", "ownership_delta": "Endring"})
    with b:
        st.markdown("**Mest solgt i Lofthus**")
        display_table(outgoing, ["player", "ownership_count", "ownership_delta"], {"player": "Spiller", "ownership_count": "Nå", "ownership_delta": "Endring"})
    st.markdown("**Kapteinsmarkedet**")
    display_table(cap_changes, ["player", "captain_count", "captain_delta"], {"player": "Spiller", "captain_count": "C nå", "captain_delta": "Endring"})

    if not moves.empty:
        with st.expander("Se hvem som kjøpte og solgte"):
            grouped = moves.groupby(["player", "move"])["manager"].apply(lambda s: ", ".join(sorted(set(s)))).reset_index()
            display_table(grouped, ["move", "player", "manager"], {"move": "Retning", "player": "Spiller", "manager": "Managere"})


def render_gw_stories(ownership: dict, managers: list[dict]):
    players_df = ownership["players"]
    events_df = ownership["manager_events"]
    if players_df.empty or events_df.empty:
        return
    round_winner = events_df.sort_values(["gw_points", "rank"], ascending=[False, True], na_position="last").iloc[0]
    bench_pain = events_df.sort_values(["points_on_bench", "gw_points"], ascending=[False, False]).iloc[0]
    diff = players_df[(players_df["ownership_count"] >= 1) & (players_df["ownership_count"] <= 3)].sort_values(["event_points", "ownership_count"], ascending=[False, True])
    diff_row = diff.iloc[0] if not diff.empty else None
    chip_users = events_df[events_df["active_chip"].astype(str).str.strip() != ""]
    style_df = build_manager_style_table(ownership)
    unique_manager = None
    if not style_df.empty:
        unique_manager = style_df.sort_values(["template_pct", "differential_count"], ascending=[True, False]).iloc[0]

    radar_metric_strip([
        {"label": "GW-vinner", "value": round_winner["manager"], "caption": f"{int(round_winner['gw_points'])} poeng"},
        {"label": "Benkefadesen", "value": bench_pain["manager"], "caption": f"{int(bench_pain['points_on_bench'])} poeng på benk"},
        {"label": "Differensialtreff", "value": diff_row["player"] if diff_row is not None else "–", "caption": f"{int(diff_row['event_points'])} p · {int(diff_row['ownership_count'])} eiere" if diff_row is not None else "Ingen tydelig ennå"},
        {"label": "Mest egenrådig", "value": unique_manager["manager"] if unique_manager is not None else "–", "caption": f"{float(unique_manager['template_pct']):.0f}% template" if unique_manager is not None else "Ikke nok data"},
    ])

    winner_entry = int(round_winner["entry"])
    winner_picks = ownership["picks"][ownership["picks"]["entry"] == winner_entry].copy()
    if not winner_picks.empty:
        lookup = players_df.set_index("element")
        winner_picks["ownership_pct"] = winner_picks["element"].map(lambda e: float(lookup.loc[e, "ownership_pct"]) if e in lookup.index else 0.0)
        winner_picks["rolle"] = winner_picks.apply(_role_label, axis=1)
        key_choices = winner_picks[(winner_picks["gw_contribution"] > 0)].sort_values(
            ["gw_contribution", "ownership_pct"], ascending=[False, True]
        ).head(6)
        with st.expander(f"Hvorfor vant {round_winner['manager']} GW-en?"):
            display_table(key_choices, ["rolle", "player", "event_points", "gw_contribution", "ownership_pct"], {"rolle": "Rolle", "player": "Nøkkelspiller", "event_points": "GW", "gw_contribution": "Bidrag", "ownership_pct": "Eid %"})

    captain_score = players_df[players_df["captain_count"] > 0].copy().sort_values(["event_points", "captain_count"], ascending=[False, False])
    if not captain_score.empty:
        with st.expander("Kapteinsfasiten denne GW-en"):
            display_table(captain_score.head(15), ["player", "captain_count", "event_points", "effective_ownership_pct", "captains_text"], {"player": "Kaptein", "captain_count": "Antall C", "event_points": "GW", "effective_ownership_pct": "EO %", "captains_text": "Hvem"})

    if not chip_users.empty:
        with st.expander("Chips i spill"):
            chip_view = chip_users.copy()
            chip_view["chip_label"] = chip_view["active_chip"].map(v200_chip_label)
            display_table(chip_view.sort_values(["chip_label", "manager"]), ["manager", "team", "chip_label", "gw_points"], {"manager": "Manager", "team": "Lag", "chip_label": "Chip", "gw_points": "GW"})

    quiet_rows = []
    for manager in managers:
        try:
            entry = int(manager.get("entry"))
            history = get_entry_history(entry)
            recent = (history.get("current", []) or [])[-3:]
            if len(recent) >= 3 and sum(int(r.get("event_transfers") or 0) for r in recent) == 0:
                quiet_rows.append({"manager": manager.get("player_name", ""), "team": manager.get("entry_name", "")})
        except Exception:
            continue
    if quiet_rows:
        with st.expander("Aktivitetssignal · lag uten transfers siste tre GW"):
            st.caption("Dette er ikke automatisk et dødt lag, bare et signal om at det ikke er registrert transfers i de tre siste rundene.")
            display_table(pd.DataFrame(quiet_rows), ["manager", "team"], {"manager": "Manager", "team": "Lag"})


def render_ownership_dashboard(managers: list[dict], ownership: dict | None = None):
    event_id = current_fpl_event_id()
    if event_id is None:
        st.info("Spiller- og kapteinsradaren våkner når FPL har en aktiv eller ferdig gameweek.")
        return None

    if ownership is None:
        with st.spinner(f"Leser {len(managers)} Lofthus-lag i GW{event_id} …"):
            ownership = build_league_ownership(managers, event_id)

    players_df = ownership["players"]
    picks_df = ownership["picks"]
    events_df = ownership["manager_events"]
    loaded = int(ownership["loaded_managers"])
    league_size = int(ownership["league_size"])

    if players_df.empty:
        st.warning("Fant ingen offentlige picks for denne runden ennå.")
        return ownership

    st.markdown("## Spillere & kapteiner")
    st.caption("Kapteinsvalg først. Deretter de mest populære spillerne. Alt annet er sekundært.")

    captained = players_df[players_df["captain_count"] > 0].copy().sort_values(
        ["triple_captain_count", "captain_count", "effective_ownership_pct", "ownership_count"],
        ascending=[False, False, False, False],
    )
    most_owned = players_df.sort_values(["ownership_count", "captain_count"], ascending=[False, False]).iloc[0]
    most_captained = captained.iloc[0] if not captained.empty else None
    tc_total = int(players_df["triple_captain_count"].sum())

    cards = [
        {"label": "Mest eid", "value": most_owned["player"], "caption": f"{int(most_owned['ownership_count'])}/{loaded} · {float(most_owned['ownership_pct']):.1f}%"},
        {"label": "Mest cappet", "value": most_captained["player"] if most_captained is not None else "–", "caption": f"{int(most_captained['captain_count'])} managere" if most_captained is not None else "Ingen"},
        {"label": "Triple captain", "value": str(tc_total), "caption": "aktive TC-valg denne GW"},
    ]
    radar_metric_strip(cards)

    if not captained.empty:
        tc_rows = captained[captained["triple_captain_count"] > 0]
        if not tc_rows.empty:
            alerts = []
            for r in tc_rows.itertuples():
                names = str(getattr(r, "triple_captains_text", "") or "")
                alerts.append(f"{r.player}: {names}")
            lro_note("🚨 Triple captain", " · ".join(alerts), "gold")

        st.markdown("### Hvem har cappet hvem?")
        display_table(
            captained,
            ["player", "club", "captain_count", "triple_captain_count", "event_points", "effective_ownership_pct", "captains_text"],
            {"player": "Spiller", "club": "Klubb", "captain_count": "C", "triple_captain_count": "TC", "event_points": "GW", "effective_ownership_pct": "EO %", "captains_text": "Hvem"},
        )

        st.markdown("### Finn et kapteinsvalg")
        cap_options = captained["element"].astype(int).tolist()
        cap_labels = {
            int(r.element): f"{r.player} · {r.club} · {int(r.captain_count)} C" + (f" · {int(r.triple_captain_count)} TC" if int(r.triple_captain_count) else "")
            for r in captained.itertuples()
        }
        selected_id = st.selectbox(
            "Cappet spiller",
            cap_options,
            format_func=lambda e: cap_labels.get(int(e), str(e)),
            index=0,
            key="captain_search_v113",
            label_visibility="collapsed",
        )
        selected_row = players_df[players_df["element"] == int(selected_id)].iloc[0]
        render_player_profile(selected_row, ownership)
    else:
        st.caption("Fant ingen kapteinsvalg ennå.")

    st.markdown("### Mest populære spillere")
    popular = players_df.sort_values(["ownership_count", "captain_count", "season_points"], ascending=[False, False, False]).head(15).copy()
    display_table(
        popular,
        ["player", "club", "ownership_count", "ownership_pct", "started_count", "bench_count", "captain_count", "event_points"],
        {"player": "Spiller", "club": "Klubb", "ownership_count": "Eiere", "ownership_pct": "%", "started_count": "Start", "bench_count": "Benk", "captain_count": "C", "event_points": "GW"},
    )

    with st.expander("Managerblikk · se tropp, template-score og hvem du må frykte"):
        manager_options = picks_df[["entry", "manager"]].drop_duplicates().sort_values("manager")
        manager_ids = manager_options["entry"].astype(int).tolist()
        manager_labels = dict(zip(manager_options["entry"].astype(int), manager_options["manager"].astype(str)))
        if manager_ids:
            selected_manager = st.selectbox("Manager", manager_ids, format_func=lambda e: manager_labels.get(int(e), str(e)), key="manager_profile_v113", label_visibility="collapsed")
            render_manager_profile(int(selected_manager), ownership, managers)

    with st.expander("Mer liveanalyse · template, differensialer, endringer og dueller"):
        st.markdown("### Lofthus-template")
        template, formation = build_template_xi(players_df)
        if not template.empty:
            st.caption(f"Mest populære lovlige XI · {formation}")
            for pos_id in [1, 2, 3, 4]:
                group = template[template["position_id"] == pos_id]
                if group.empty:
                    continue
                names = " · ".join(f"{r.player} ({int(r.ownership_count)}/{loaded})" for r in group.itertuples())
                st.markdown(f"**{POSITION_LABELS[pos_id]}:** {names}")

        st.markdown("### Differensialradar")
        differential = players_df[(players_df["ownership_count"] >= 1) & (players_df["ownership_count"] <= 3)].copy()
        differential = differential.sort_values(["event_points", "season_points", "ownership_count"], ascending=[False, False, True]).head(20)
        if differential.empty:
            st.caption("Ingen spillere med 1–3 eiere akkurat nå.")
        else:
            display_table(differential, ["player", "ownership_count", "event_points", "season_points", "owners_text"], {"player": "Spiller", "ownership_count": "Eiere", "event_points": "GW", "season_points": "Sesong", "owners_text": "Hvem"})

        st.markdown("### Endringer fra forrige GW")
        render_ownership_trends(managers, ownership)

        st.markdown("### Manager mot manager")
        render_head_to_head(ownership)

        st.markdown("### Rundens historier")
        render_gw_stories(ownership, managers)

    if loaded < league_size:
        st.warning(f"Picks er lest fra {loaded} av {league_size} lag. {league_size-loaded} lag kunne ikke leses akkurat nå, så prosentene gjelder lagene som faktisk svarte fra FPL.")
    return ownership


# -----------------------------
# Norgeskart
# -----------------------------


def build_place_data(active_manager_names: list[str] | None = None) -> pd.DataFrame:
    df = read_csv_file("places.csv", ["manager", "place", "lat", "lon"])

    if df.empty:
        return pd.DataFrame(columns=["By", "lat", "lon", "Antall", "Deltakere", "Label", "radius"])

    df = df[(df["manager"] != "") & (df["place"] != "")].copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])

    if active_manager_names:
        active_keys = {hof_key(name) for name in active_manager_names if str(name).strip()}
        df["_manager_key"] = df["manager"].map(hof_key)
        df = df[df["_manager_key"].isin(active_keys)].copy()

    rows = []

    for (place, lat, lon), place_df in df.groupby(["place", "lat", "lon"], dropna=False):
        people = sorted(place_df["manager"].dropna().astype(str).unique().tolist())
        count = len(people)
        people_text = ", ".join(people)
        rows.append({
            "By": place,
            "lat": float(lat),
            "lon": float(lon),
            "Antall": count,
            "Deltakere": people_text,
            "Label": f"{place} ({count})",
            "radius": 5_200,
        })

    return pd.DataFrame(rows)


# -----------------------------
# Session helpers
# -----------------------------

def ensure_managers_loaded(league_id: int):
    if "managers" not in st.session_state or st.session_state.get("loaded_league_id") != league_id:
        league_info, managers, debug = get_league_managers(league_id)

        st.session_state["league_info"] = league_info
        st.session_state["managers"] = managers
        st.session_state["debug"] = debug
        st.session_state["loaded_league_id"] = league_id
        st.session_state["last_updated"] = datetime.now().strftime("%d.%m %H:%M")


def ensure_history_loaded(league_id: int):
    ensure_managers_loaded(league_id)

    if "summary_df" not in st.session_state or st.session_state.get("history_league_id") != league_id:
        summary_df, seasons_df, errors_df = build_history_tables(st.session_state["managers"])

        st.session_state["summary_df"] = summary_df
        st.session_state["seasons_df"] = seasons_df
        st.session_state["errors_df"] = errors_df
        st.session_state["history_league_id"] = league_id


def clear_loaded_fpl_state():
    for key in [
        "league_info",
        "managers",
        "debug",
        "loaded_league_id",
        "summary_df",
        "seasons_df",
        "errors_df",
        "history_league_id",
        "last_updated",
    ]:
        st.session_state.pop(key, None)


def handle_refresh_and_autoload():
    """Load just the lightweight league list on first visit.

    Full manager history is heavier and is therefore loaded only when a page
    actually needs it. This keeps the public app snappier on first open.
    """
    if st.session_state.pop("_refresh_fpl_now", False):
        for cached_func in [get_json, get_entry_history, get_bootstrap_static, get_entry_event_picks, get_league_managers]:
            try:
                cached_func.clear()
            except Exception:
                pass
        clear_loaded_fpl_state()
        st.session_state.pop("_autoload_failed", None)

    if "managers" not in st.session_state and not st.session_state.get("_autoload_failed"):
        with st.spinner("Henter Lofthus-data fra FPL ..."):
            try:
                ensure_managers_loaded(DEFAULT_LEAGUE_ID)
                st.session_state["_autoload_failed"] = False
            except Exception as error:
                st.session_state["_autoload_failed"] = True
                st.error(f"Klarte ikke å hente FPL-data akkurat nå: {error}")
                st.caption("Prøv Oppdater fra FPL nå i venstremenyen om litt.")


def ensure_history_for_page():
    if "summary_df" not in st.session_state or st.session_state.get("history_league_id") != DEFAULT_LEAGUE_ID:
        with st.spinner("Henter FPL-historikk ..."):
            ensure_history_loaded(DEFAULT_LEAGUE_ID)


handle_refresh_and_autoload()



# -----------------------------
# Labels
# -----------------------------

LIGATABELL_LABELS = {
    "rank_display": "Plassering",
    "player_name": "Manager",
    "entry_name": "Lagnavn",
    "event_total_num": "Rundepoeng",
    "total_num": "Poeng totalt",
    "form_curve": "Formkurve",
    "form_delta": "Endring i plassering",
    "odds_before": "Odds - vinner",
    "top3_odds": "Odds - topp 3",
    "top3_odds_float": "Odds - topp 3",
}

HISTORY_LABELS = {
    "podium": "",
    "best_rank_with_season": "Beste FPL-plassering gjennom tidene",
    "manager": "Manager",
    "team": "Lagnavn",
    "seasons": "Sesonger spilt",
    "last_season_rank_display": "Plassering forrige sesong",
    "best_rank_numeric": "Beste FPL-plassering gjennom tidene",
    "best_season": "Beste sesong",
    "avg_rank_last_3_display": "Snitt siste tre sesonger",
    "trend": "Utvikling siste tre sesonger",
    "monthly_titles": "Månedstitler",
    "hof_score": "Merittpoeng",
    "merits": "Meritter",
    "top_100k_seasons": "Topp 100k",
    "top_500k_seasons": "Topp 500k",
    "tier_display": "Nivå",
}

SEASON_LABELS = {
    "manager": "Manager",
    "team": "Lagnavn",
    "season_name": "Sesong",
    "total_points": "Poeng",
    "rank": "Plassering",
}

ERROR_LABELS = {
    "manager": "Manager",
    "team": "Lagnavn",
    "entry": "Entry-ID",
    "error": "Feil",
}

HOF_LABELS = {
    "podium": "",
    "hof_rank": "Hall of Fame-rangering",
    "display_name": "Manager",
    "hof_score": "Merittpoeng",
    "overall_count": "Sammenlagtseiere",
    "overall_runner_up_count": "2. plasser",
    "overall_third_count": "3. plasser",
    "cup_count": "Cupgull",
    "cup_runner_up_count": "Cupsølv",
    "monthly_titles": "Månedsseiere",
    "monthly_silver": "Månedssølv",
    "monthly_bronze": "Månedsbronse",
    "monthly_podiums": "Månedspodier",
    "monthly_points": "Månedspoeng",
    "random_count": "Random",
    "merits": "Meritter",
    "overall_seasons": "Sammenlagt-gull",
    "overall_runner_up_seasons": "Sammenlagt-sølv",
    "overall_third_seasons": "Sammenlagt-bronse",
    "cup_seasons": "Cupgull-sesonger",
    "cup_runner_up_seasons": "Cupsølv-sesonger",
}

MONTHLY_MEDAL_LABELS = {
    "monthly_rank": "Månedsrangering",
    "manager": "Manager",
    "month_points": "Månedspoeng",
    "gold": "1. plass",
    "silver": "2. plass",
    "bronze": "3. plass",
    "podiums": "Pallplasser",
}

MONTHLY_PODIUM_LABELS = {
    "season": "Sesong",
    "month": "Måned",
    "place": "Plass",
    "manager": "Manager",
    "points": "Poeng",
}

MONTHLY_CALENDAR_LABELS = {
    "season": "Sesong",
    "month": "Måned",
    "winner": "1. plass",
    "second_place": "2. plass",
    "third_place": "3. plass",
}

MONTH_SPECIALIST_LABELS = {
    "month": "Måned",
    "king": "Månedskonge(r)",
    "gold": "1. plass",
    "silver": "2. plass",
    "bronze": "3. plass",
    "podiums": "Pallplasser",
    "winners_history": "Vinnere gjennom tidene",
}

MONTH_WINNER_HISTORY_LABELS = {
    "month": "Måned",
    "winners_history": "Vinnere gjennom tidene",
}

OVERALL_LABELS = {
    "season": "Sesong",
    "winner": "Vinner",
    "runner_up": "2. plass",
    "third_place": "3. plass",
    "note": "Notat",
}

CUP_LABELS = {
    "season": "Sesong",
    "winner": "Cupvinner",
    "runner_up": "Finalist",
}

RANDOM_LABELS = {
    "season": "Sesong",
    "winner": "Vinner",
    "placement": "Plassering",
}

RADAR_LABELS = {
    "player_name": "Manager",
    "entry_name": "Lagnavn",
    "rank_num": "Plassering",
    "rank_display": "Plassering",
    "form_curve": "Formkurve",
    "event_total_num": "Rundepoeng",
    "total_num": "Poeng",
    "odds": "Odds - vinner",
    "top3_odds": "Odds - topp 3",
    "odds_rank": "Odds-rangering",
    "performance_vs_odds": "Avvik mot odds",
    "last_three_points": "Poeng siste tre runder",
    "last_three_avg": "Snitt siste tre runder",
    "last_three_detail": "Siste tre runder",
}

NUMERIC_CONFIG = {
    "odds_before": st.column_config.NumberColumn("Odds - vinner", format="%.2f"),
    "best_rank_numeric": st.column_config.NumberColumn("Beste FPL-plassering gjennom tidene", format="%d"),
    "last_season_rank_display": st.column_config.TextColumn("Plassering forrige sesong", width="medium"),
    "avg_rank_last_3_display": st.column_config.TextColumn("Snitt siste tre sesonger", width="medium"),
    "event_total_num": st.column_config.NumberColumn("Rundepoeng", format="%d"),
    "total_num": st.column_config.NumberColumn("Poeng", format="%d"),
    "rank_num": st.column_config.NumberColumn("Plassering", format="%d"),
    "odds": st.column_config.NumberColumn("Odds - vinner", format="%.2f"),
    "top3_odds_float": st.column_config.NumberColumn("Odds - topp 3", format="%.2f"),
    "odds_rank": st.column_config.NumberColumn("Odds-rangering", format="%d"),
    "performance_vs_odds": st.column_config.NumberColumn("Avvik mot odds", format="%d"),
    "last_three_points": st.column_config.NumberColumn("Poeng siste tre runder", format="%d"),
    "last_three_avg": st.column_config.NumberColumn("Snitt siste tre runder", format="%.1f"),
}



# -----------------------------
# V106 Clubhouse-forside
# -----------------------------

def render_home_top5(live_df: pd.DataFrame):
    if live_df is None or live_df.empty:
        st.caption("Tabellen våkner når første tellende runde er registrert.")
        return

    rows = []
    for _, row in live_df.head(5).iterrows():
        rank = int(row.get("rank_num")) if not pd.isna(row.get("rank_num")) else "–"
        manager = html.escape(clean_cell(row.get("player_name")) or "Ukjent")
        team = html.escape(clean_cell(row.get("entry_name")))
        total = "–" if pd.isna(row.get("total_num")) else str(int(row.get("total_num")))
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))
        rows.append(
            f'<div class="home-table-row"><div class="home-rank">{medal}</div>'
            f'<div class="home-person"><strong>{manager}</strong><span>{team}</span></div>'
            f'<div class="home-points">{total}<span>poeng</span></div></div>'
        )

    st.markdown(
        """
        <style>
        .home-table{background:#fff;border:1px solid #e5e7eb;border-radius:18px;overflow:hidden;box-shadow:0 8px 24px rgba(15,23,42,.05)}
        .home-table-row{display:grid;grid-template-columns:48px minmax(0,1fr) 88px;gap:10px;align-items:center;padding:12px 14px;border-bottom:1px solid #eef2f7}
        .home-table-row:last-child{border-bottom:0}
        .home-rank{font-weight:900;color:#0f172a;font-size:1rem}
        .home-person{min-width:0}.home-person strong{display:block;color:#111827;font-size:.96rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.home-person span{display:block;color:#667085;font-size:.78rem;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .home-points{text-align:right;font-size:1.05rem;font-weight:900;color:#111827}.home-points span{display:block;font-size:.68rem;font-weight:700;color:#98a2b3;text-transform:uppercase;letter-spacing:.06em}
        @media(max-width:600px){.home-table-row{grid-template-columns:38px minmax(0,1fr) 68px;padding:10px 11px}.home-person strong{font-size:.9rem}.home-points{font-size:.95rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="home-table">' + ''.join(rows) + '</div>', unsafe_allow_html=True)


def render_clubhouse_home(managers: list[dict]):
    # V110: editorial front page with one clear hierarchy and no duplicate navigation.
    managers = managers or []
    df = pd.DataFrame(managers).copy() if managers else pd.DataFrame()

    if not df.empty:
        for column in ["rank", "last_rank", "event_total", "total"]:
            if column not in df.columns:
                df[column] = pd.NA
        df["rank_num"] = pd.to_numeric(df["rank"], errors="coerce")
        df["last_rank_num"] = pd.to_numeric(df["last_rank"], errors="coerce")
        df["event_total_num"] = pd.to_numeric(df["event_total"], errors="coerce")
        df["total_num"] = pd.to_numeric(df["total"], errors="coerce")
        df["form_delta"] = df["last_rank_num"] - df["rank_num"]

    has_live = bool(not df.empty and df["rank_num"].notna().any())
    participant_count = len(df)
    event_id = current_fpl_event_id()

    if has_live:
        live_df = df.sort_values(["rank_num", "total_num", "player_name"], ascending=[True, False, True], na_position="last").copy()
        leader = live_df.iloc[0]
        round_king = df.sort_values(["event_total_num", "rank_num"], ascending=[False, True], na_position="last").iloc[0]
        movers = df.dropna(subset=["rank_num", "last_rank_num"]).copy()
        if not movers.empty:
            movers["delta"] = movers["last_rank_num"] - movers["rank_num"]
            climbers = movers[movers["delta"] > 0].sort_values(["delta", "rank_num"], ascending=[False, True])
        else:
            climbers = pd.DataFrame()
        leader_name = clean_cell(leader.get("player_name")) or "Ukjent"
        leader_team = clean_cell(leader.get("entry_name"))
        leader_points = 0 if pd.isna(leader.get("total_num")) else int(leader.get("total_num"))
        round_name = clean_cell(round_king.get("player_name")) or "Ukjent"
        round_points = 0 if pd.isna(round_king.get("event_total_num")) else int(round_king.get("event_total_num"))
        climber_name = clean_cell(climbers.iloc[0].get("player_name")) if not climbers.empty else "Ingen stor bevegelse"
        climber_delta = int(climbers.iloc[0].get("delta")) if not climbers.empty else 0
        gw_label = f"GW{event_id}" if event_id else "LIVE"
    else:
        live_df = pd.DataFrame()
        leader_name = "Sesongen venter"
        leader_team = "Første tellende tabell kommer automatisk"
        leader_points = 0
        round_name = "–"
        round_points = 0
        climber_name = "–"
        climber_delta = 0
        gw_label = "FØR LIVE"

    if has_live:
        leader_line = f"Serieledelse · {html.escape(leader_team)} · {leader_points} poeng"
        round_line = f"{round_points} poeng"
    else:
        leader_line = html.escape(leader_team)
        round_line = "Venter på live-runde"

    st.markdown(
        f'''
        <style>
        .home-scoreboard{{background:linear-gradient(115deg,#071525 0%,#063d2e 56%,#511b1b 100%);border:1px solid rgba(255,255,255,.1);border-radius:22px;color:white;padding:22px 24px;margin:6px 0 20px 0;box-shadow:0 14px 34px rgba(15,23,42,.14)}}
        .home-score-kicker{{font-size:.72rem;color:#fde68a;font-weight:900;letter-spacing:.1em;text-transform:uppercase}}
        .home-score-grid{{display:grid;grid-template-columns:minmax(0,1.5fr) repeat(2,minmax(150px,.65fr));gap:18px;align-items:end;margin-top:10px}}
        .home-score-leader{{font-size:clamp(1.55rem,3vw,2.5rem);font-weight:950;line-height:1.02;letter-spacing:-.045em}}
        .home-score-sub{{font-size:.88rem;color:#cbd5e1;margin-top:7px}}
        .home-score-stat{{border-left:1px solid rgba(255,255,255,.18);padding-left:18px}}
        .home-score-stat span{{display:block;color:#cbd5e1;font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;font-weight:800}}
        .home-score-stat strong{{display:block;font-size:1.2rem;margin-top:5px}}
        @media(max-width:800px){{.home-score-grid{{grid-template-columns:1fr;gap:12px}}.home-score-stat{{border-left:0;border-top:1px solid rgba(255,255,255,.14);padding:12px 0 0 0}}}}
        </style>
        <div class="home-scoreboard">
          <div class="home-score-kicker">{gw_label} · LOFTHUS ROAD OPEN</div>
          <div class="home-score-grid">
            <div><div class="home-score-leader">{html.escape(leader_name)}</div><div class="home-score-sub">{leader_line}</div></div>
            <div class="home-score-stat"><span>Påmeldte</span><strong>{participant_count}</strong></div>
            <div class="home-score-stat"><span>Rundens beste</span><strong>{html.escape(round_name) if has_live else '–'}</strong><div class="home-score-sub">{round_line}</div></div>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.42, 1], gap="large")
    with left:
        st.markdown("### Topp 5")
        st.caption("Ligaen akkurat nå. Full tabell finner du under Ligatabell.")
        render_home_top5(live_df)

    with right:
        st.markdown("### Klubbpuls")
        if has_live:
            with st.container(border=True):
                st.caption("STØRSTE KLATRER")
                st.markdown(f"**{climber_name}**")
                st.caption(f"Opp {climber_delta} plasser denne runden" if climber_delta else "Ingen tydelig klatrer ennå")
            render_home_live_snapshot(managers)
        else:
            render_home_live_snapshot(managers)
            with st.container(border=True):
                st.caption("FØR SESONG")
                st.markdown("**Odds og tabelltips er klare**")
                st.caption("Historikken ligger urørt og tilgjengelig i hovedmenyen.")



# ============================================================
# V115 - FOLKELIG KAPTEINSRADAR, RYDDIG LIVEVISNING OG KALENDERMÅNED
# ============================================================

CURRENT_SEASON_FALLBACK_PODIUMS = [
    {"season": "2026/27", "month": "August", "place": 1, "manager": "Vegard Røstby", "status": "Bekreftet", "source": "LRO bekreftet august 2026"},
    {"season": "2026/27", "month": "August", "place": 2, "manager": "Edward Stenlund", "status": "Bekreftet", "source": "LRO bekreftet august 2026"},
    {"season": "2026/27", "month": "August", "place": 3, "manager": "Kristoffer W Pettersen", "status": "Bekreftet", "source": "LRO bekreftet august 2026"},
]

MONTH_NAME_NO = {
    "august": "August", "september": "September", "october": "Oktober", "oktober": "Oktober",
    "november": "November", "december": "Desember", "desember": "Desember",
    "january": "Januar", "januar": "Januar", "february": "Februar", "februar": "Februar",
    "march": "Mars", "mars": "Mars", "april": "April", "may": "Mai", "mai": "Mai",
}


def _season_label_from_bootstrap(bootstrap: dict | None = None) -> str:
    try:
        bootstrap = bootstrap or get_bootstrap_static()
        first = next((e for e in (bootstrap.get("events", []) or []) if e.get("deadline_time")), None)
        if first:
            year = int(str(first.get("deadline_time"))[:4])
            return f"{year}/{str(year + 1)[-2:]}"
    except Exception:
        pass
    return "2026/27"


def _finished_event_ids(bootstrap: dict | None = None) -> list[int]:
    try:
        bootstrap = bootstrap or get_bootstrap_static()
    except Exception:
        return []
    out = []
    for event in bootstrap.get("events", []) or []:
        if event.get("finished"):
            try:
                out.append(int(event.get("id")))
            except (TypeError, ValueError):
                pass
    return sorted(set(out))


def _event_finished(event_id: int) -> bool:
    try:
        for event in get_bootstrap_static().get("events", []) or []:
            if int(event.get("id") or 0) == int(event_id):
                return bool(event.get("finished"))
    except Exception:
        pass
    return False


@st.cache_data(ttl=900)
def get_league_phase_standings(league_id: int, phase_id: int) -> list[dict]:
    """Hent hele LRO-tabellen for én FPL-fase (måned)."""
    rows = []
    page = 1
    while page <= 100:
        payload = get_json(f"/leagues-classic/{int(league_id)}/standings/?page_standings={page}&page_new_entries=1&phase={int(phase_id)}")
        standings = payload.get("standings", {}) or {}
        rows.extend(standings.get("results", []) or [])
        if not standings.get("has_next"):
            break
        page += 1
    return rows


def _month_phases(bootstrap: dict | None = None) -> list[dict]:
    try:
        bootstrap = bootstrap or get_bootstrap_static()
    except Exception:
        return []
    phases = []
    for phase in bootstrap.get("phases", []) or []:
        no_name = MONTH_NAME_NO.get(normalize_text(str(phase.get("name") or "")))
        if not no_name:
            continue
        try:
            phases.append({
                "id": int(phase.get("id")), "name": no_name,
                "start_event": int(phase.get("start_event") or 0),
                "stop_event": int(phase.get("stop_event") or 0),
            })
        except (TypeError, ValueError):
            continue
    return phases


def _static_month_keys() -> set[tuple[str, str, int]]:
    keys = set()
    for row in MONTHLY_PODIUMS:
        try:
            keys.add((str(row.get("season") or ""), str(row.get("month") or ""), int(row.get("place") or 0)))
        except Exception:
            pass
    return keys


@st.cache_data(ttl=900)
def get_auto_monthly_podiums(league_id: int = DEFAULT_LEAGUE_ID) -> list[dict]:
    """Automatisk pall for ferdige FPL-måneder. August 2026 har bekreftet fallback."""
    fallback = [dict(row) for row in CURRENT_SEASON_FALLBACK_PODIUMS]
    try:
        bootstrap = get_bootstrap_static()
        season = _season_label_from_bootstrap(bootstrap)
        finished = _finished_event_ids(bootstrap)
        max_finished = max(finished) if finished else 0
        auto_rows, auto_months = [], set()
        for phase in _month_phases(bootstrap):
            if int(phase["stop_event"]) <= 0 or int(phase["stop_event"]) > max_finished:
                continue
            try:
                standings = get_league_phase_standings(int(league_id), int(phase["id"]))
            except Exception:
                continue
            if not standings:
                continue
            standings = sorted(standings, key=lambda r: (int(r.get("rank") or 10**9), -int(r.get("total") or 0), normalize_text(str(r.get("player_name") or ""))))
            for place, row in enumerate(standings[:3], start=1):
                manager = normalize_manager_row(row, "måned").get("player_name") or "Ukjent manager"
                auto_rows.append({
                    "season": season, "month": phase["name"], "place": place,
                    "manager": canonical_hof_name(str(manager)), "status": "Automatisk",
                    "source": f"FPL phase {phase['id']}",
                })
            auto_months.add((season, phase["name"]))
        for row in fallback:
            if (row["season"], row["month"]) not in auto_months:
                auto_rows.append(row)
        return auto_rows
    except Exception:
        return fallback


def build_monthly_podium_df() -> pd.DataFrame:
    """Historiske CSV-data + automatisk inneværende sesong, uten dobbeltføring."""
    rows = [dict(row) for row in MONTHLY_PODIUMS]
    static_keys = _static_month_keys()
    for row in get_auto_monthly_podiums(DEFAULT_LEAGUE_ID):
        try:
            key = (str(row.get("season") or ""), str(row.get("month") or ""), int(row.get("place") or 0))
        except Exception:
            continue
        if key not in static_keys:
            rows.append(dict(row))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ["season", "month", "manager", "status", "source"]:
        if col not in df.columns:
            df[col] = ""
    df["manager"] = df["manager"].apply(canonical_hof_name)
    df["place"] = pd.to_numeric(df.get("place"), errors="coerce").fillna(0).astype(int)
    df = df[df["place"].between(1, 3)].copy()
    df["points"] = df["place"].map({1: 6, 2: 2, 3: 1}).fillna(0).astype(int)
    month_order = {"August": 1, "September": 2, "Oktober": 3, "November": 4, "Desember": 5, "Januar": 6, "Februar": 7, "Mars": 8, "April": 9, "Mai": 10}
    df["month_order"] = df["month"].map(month_order).fillna(99)
    df = df.drop_duplicates(subset=["season", "month", "place"], keep="last")
    return df.sort_values(["season", "month_order", "place", "manager"]).reset_index(drop=True)


def build_official_monthly_map() -> dict:
    """Historisk offisiell count + auto-gull som ikke allerede ligger i CSV-en."""
    out = {hof_key(name): int(count) for name, count in OFFICIAL_MONTHLY_TITLES_RAW.items()}
    static_keys = _static_month_keys()
    for row in get_auto_monthly_podiums(DEFAULT_LEAGUE_ID):
        try:
            key = (str(row.get("season") or ""), str(row.get("month") or ""), int(row.get("place") or 0))
        except Exception:
            continue
        if int(row.get("place") or 0) == 1 and key not in static_keys:
            k = hof_key(str(row.get("manager") or ""))
            out[k] = int(out.get(k, 0)) + 1
    return out


def current_month_phase(bootstrap: dict | None = None, event_id: int | None = None) -> dict | None:
    """Finn måneden som skal vises nå. Kalenderen vinner over gammel aktiv GW.

    FPL kan stå igjen på forrige gameweek noen dager inn i en ny måned. Da skal
    Lofthus likevel vise f.eks. «September · live», ikke late som august fortsetter.
    """
    try:
        bootstrap = bootstrap or get_bootstrap_static()
    except Exception:
        return None
    phases = _month_phases(bootstrap)
    if not phases:
        return None

    norwegian_months = {
        1: "Januar", 2: "Februar", 3: "Mars", 4: "April", 5: "Mai", 6: "Juni",
        7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
    }
    calendar_month = norwegian_months.get(datetime.now().month)
    for phase in phases:
        if phase.get("name") == calendar_month:
            return phase

    event_id = int(event_id or current_fpl_event_id() or 0)
    for phase in phases:
        if int(phase["start_event"]) <= event_id <= int(phase["stop_event"]):
            return phase
    latest = max(_finished_event_ids(bootstrap) or [0])
    for phase in reversed(phases):
        if int(phase["stop_event"]) <= latest:
            return phase
    return phases[0]

def get_current_month_table(league_id: int = DEFAULT_LEAGUE_ID) -> tuple[dict | None, pd.DataFrame]:
    try:
        bootstrap = get_bootstrap_static()
        phase = current_month_phase(bootstrap)
        if not phase:
            return None, pd.DataFrame()
        rows = get_league_phase_standings(int(league_id), int(phase["id"]))
        data = []
        for row in rows:
            m = normalize_manager_row(row, "måned")
            data.append({
                "rank": int(row.get("rank") or 0),
                "manager": canonical_hof_name(str(m.get("player_name") or "Ukjent manager")),
                "team": str(m.get("entry_name") or ""), "points": int(row.get("total") or 0),
            })
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values(["rank", "manager"]).reset_index(drop=True)
        return phase, df
    except Exception:
        return None, pd.DataFrame()


RUNTIME_DIR = Path(".lro_runtime")
SNAPSHOT_DIR = RUNTIME_DIR / "snapshots"


def _snapshot_path(event_id: int) -> Path:
    return SNAPSHOT_DIR / f"gw_{int(event_id):02d}.json"


def _frame_records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    try:
        return json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))
    except Exception:
        safe = df.astype(object).where(pd.notna(df), None)
        return safe.to_dict("records")


def persist_ownership_snapshot(ownership: dict) -> None:
    """Best-effort rundeminne. Historiske GW kan også rekonstrueres direkte fra FPL."""
    event_id = int(ownership.get("event") or 0)
    if event_id <= 0 or not _event_finished(event_id):
        return
    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "event": event_id, "saved_at": datetime.now().isoformat(timespec="seconds"),
            "league_size": int(ownership.get("league_size") or 0),
            "loaded_managers": int(ownership.get("loaded_managers") or 0),
            "players": _frame_records(ownership.get("players", pd.DataFrame())),
            "picks": _frame_records(ownership.get("picks", pd.DataFrame())),
            "manager_events": _frame_records(ownership.get("manager_events", pd.DataFrame())),
        }
        _snapshot_path(event_id).write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    except Exception:
        pass


def load_ownership_snapshot(event_id: int) -> dict | None:
    path = _snapshot_path(event_id)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "event": int(payload.get("event") or event_id),
            "players": pd.DataFrame(payload.get("players", []) or []),
            "picks": pd.DataFrame(payload.get("picks", []) or []),
            "manager_events": pd.DataFrame(payload.get("manager_events", []) or []),
            "loaded_managers": int(payload.get("loaded_managers") or 0),
            "league_size": int(payload.get("league_size") or 0), "errors": [],
        }
    except Exception:
        return None


def ownership_for_event(managers: list[dict], event_id: int) -> dict:
    snapshot = load_ownership_snapshot(int(event_id))
    if snapshot is not None and not snapshot.get("picks", pd.DataFrame()).empty:
        return snapshot
    ownership = build_league_ownership(managers, int(event_id))
    persist_ownership_snapshot(ownership)
    return ownership


def persist_season_archive(managers: list[dict]) -> Path | None:
    """Oppdater et kompakt sesongarkiv ved hvert besøk."""
    if not managers:
        return None
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        bootstrap = get_bootstrap_static()
        season = _season_label_from_bootstrap(bootstrap)
        finished = _finished_event_ids(bootstrap)
        events = bootstrap.get("events", []) or []
        table = []
        for m in managers:
            rank_num = pd.to_numeric(m.get("rank"), errors="coerce")
            points_num = pd.to_numeric(m.get("total"), errors="coerce")
            table.append({
                "entry": int(m.get("entry") or 0), "manager": canonical_hof_name(str(m.get("player_name") or "")),
                "team": str(m.get("entry_name") or ""),
                "rank": None if pd.isna(rank_num) else int(rank_num), "points": None if pd.isna(points_num) else int(points_num),
            })
        monthly = build_monthly_podium_df()
        if not monthly.empty:
            monthly = monthly[monthly["season"] == season]
        # Første besøk etter en ferdig GW lagrer automatisk rundebildet lokalt.
        # Hvis et gammelt snapshot mangler, kan det fortsatt rekonstrueres fra FPLs historiske picks.
        if finished:
            latest_finished = max(finished)
            if not _snapshot_path(latest_finished).exists():
                try:
                    persist_ownership_snapshot(build_league_ownership(managers, latest_finished))
                except Exception:
                    pass
        snapshot_files = sorted(SNAPSHOT_DIR.glob("gw_*.json")) if SNAPSHOT_DIR.exists() else []
        cup_current = [row for row in HOF_CUP if str(row.get("season") or "") == season]
        payload = {
            "season": season, "generated_at": datetime.now().isoformat(timespec="seconds"),
            "season_finished": bool(events) and len(finished) == len(events),
            "latest_finished_gw": max(finished) if finished else 0, "league_id": DEFAULT_LEAGUE_ID,
            "final_or_live_table": sorted(table, key=lambda r: (r["rank"] is None, r["rank"] or 10**9, r["manager"])),
            "monthly_podiums": _frame_records(monthly),
            "cup_result": cup_current,
            "saved_gw_snapshots": [f.name for f in snapshot_files],
        }
        path = RUNTIME_DIR / f"lofthus_road_open_{season.replace('/', '_')}_archive.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path
    except Exception:
        return None


def render_month_snapshot(compact: bool = False):
    phase, month_df = get_current_month_table(DEFAULT_LEAGUE_ID)
    if phase is None:
        return
    season = _season_label_from_bootstrap()
    month = phase["name"]
    finished = set(_finished_event_ids())
    phase_gws = set(range(int(phase["start_event"]), int(phase["stop_event"]) + 1))
    phase_done = bool(phase_gws) and phase_gws.issubset(finished)
    with st.container(border=True):
        st.caption("MÅNEDSKAMPEN")
        st.markdown(f"**{month} · {'ferdig' if phase_done else 'live'}**")
        if phase_done:
            podium = build_monthly_podium_df()
            podium = podium[(podium["season"] == season) & (podium["month"] == month)].sort_values("place")
            if not podium.empty:
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                for row in podium.head(3).itertuples():
                    st.write(f"{medals.get(int(row.place), str(row.place))} {row.manager}")
                return

        max_points = 0
        if not month_df.empty:
            max_points = int(pd.to_numeric(month_df["points"], errors="coerce").fillna(0).max())
        if max_points > 0:
            display_table(month_df.head(3), ["rank", "manager", "points"], {"rank": "#", "manager": "Manager", "points": "Måned"})
            return

        # Ny måned, ingen tellende poeng ennå: vis en faktisk live-tabell på 0 poeng.
        zero_df = month_df[["manager"]].drop_duplicates().copy() if not month_df.empty else pd.DataFrame()
        if zero_df.empty:
            try:
                _, managers, _ = get_league_managers(DEFAULT_LEAGUE_ID)
                zero_df = pd.DataFrame({"manager": [canonical_hof_name(str(m.get("player_name") or "")) for m in managers]})
            except Exception:
                zero_df = pd.DataFrame()
        if not zero_df.empty:
            zero_df = zero_df[zero_df["manager"].astype(str).str.strip() != ""].drop_duplicates().sort_values("manager").head(3).reset_index(drop=True)
            zero_df["rank"] = range(1, len(zero_df) + 1)
            zero_df["points"] = 0
            display_table(zero_df, ["rank", "manager", "points"], {"rank": "#", "manager": "Manager", "points": "September" if month == "September" else "Poeng"})
            st.caption(f"Ingen {month.lower()}poeng registrert ennå. Rekkefølgen er alfabetisk fram til første tellende poeng.")
        else:
            st.caption(f"Ingen {month.lower()}poeng registrert ennå.")

def _captain_tag(row: pd.Series) -> str:
    tc, c = int(row.get("triple_captain_count") or 0), int(row.get("captain_count") or 0)
    if tc:
        return f"🚨 {tc} TC · {c} C"
    return f"© {c} C" if c else ""


def render_live_match_centre(managers: list[dict], ownership: dict | None = None):
    """Live-kampkontroll: hva skjer, hvem betyr noe, og hvem har bindet."""
    event_id = current_fpl_event_id()
    if event_id is None:
        return
    context = build_live_fixture_context(int(event_id))
    active, teams = context.get("active", []), context.get("teams", {})
    st.markdown("## Live akkurat nå")
    if ownership is None:
        ownership = ownership_for_event(managers, int(event_id))
    players_df = ownership.get("players", pd.DataFrame()).copy()
    league_df = pd.DataFrame(managers or []).copy()
    cards = []
    if not league_df.empty:
        league_df["rank_num"] = pd.to_numeric(league_df.get("rank"), errors="coerce")
        league_df["event_num"] = pd.to_numeric(league_df.get("event_total"), errors="coerce")
        league_df["total_num"] = pd.to_numeric(league_df.get("total"), errors="coerce")
        ranked = league_df.dropna(subset=["rank_num"]).sort_values(["rank_num", "total_num"], ascending=[True, False])
        if not ranked.empty:
            r = ranked.iloc[0]
            cards.append({"label": "Ligaleder", "value": r.get("player_name", "–"), "caption": f"{int(r.get('total_num') or 0)} poeng"})
        rounders = league_df.dropna(subset=["event_num"]).sort_values(["event_num", "rank_num"], ascending=[False, True])
        if not rounders.empty:
            r = rounders.iloc[0]
            cards.append({"label": f"GW{event_id} best", "value": r.get("player_name", "–"), "caption": f"{int(r.get('event_num') or 0)} poeng"})
    if not players_df.empty:
        capped = players_df[players_df["captain_count"] > 0].sort_values(["captain_count", "triple_captain_count", "ownership_count", "player"], ascending=[False, False, False, True])
        if not capped.empty:
            r = capped.iloc[0]
            cards.append({"label": "Mest cappet", "value": r["player"], "caption": f"{int(r['captain_count'])} kapteiner"})
    radar_metric_strip(cards[:4])

    if not active:
        with st.container(border=True):
            st.caption(f"GW{event_id} · INGEN KAMP PÅGÅR")
            st.markdown(f"**Neste: {_next_fixture_label(context.get('next'), teams)}**")
            if not players_df.empty:
                cap = players_df[players_df["captain_count"] > 0].sort_values(["captain_count", "triple_captain_count", "ownership_count"], ascending=[False, False, False]).head(4)
                if not cap.empty:
                    st.caption("Mest populære kapteiner: " + " · ".join(f"{r.player} ({int(r.captain_count)})" for r in cap.itertuples()))
        return

    active_ids, labels = set(), []
    for fixture in active:
        labels.append(_fixture_label(fixture, teams))
        active_ids.update({int(fixture.get("team_h") or 0), int(fixture.get("team_a") or 0)})
    matches_html = " &nbsp; | &nbsp; ".join(html.escape(x) for x in labels)
    st.markdown(
        f"<div style='background:linear-gradient(110deg,#071525,#064e3b 58%,#511b1b);color:white;border-radius:18px;padding:16px 18px;margin:4px 0 14px 0'><div style='font-size:.72rem;color:#fde68a;font-weight:900;letter-spacing:.09em'>GW{event_id} · LIVE</div><div style='font-size:1.12rem;font-weight:900;margin-top:4px'>{matches_html}</div><div style='font-size:.84rem;color:#d1fae5;margin-top:5px'>Her ser du spillerne i kamp som betyr mest for Lofthus-ligaen akkurat nå.</div></div>",
        unsafe_allow_html=True,
    )
    if players_df.empty:
        st.caption("Kampene er live, men laguttakene kunne ikke kobles akkurat nå.")
        return
    live = players_df[players_df["team_id"].isin(active_ids)].copy()
    if live.empty:
        st.caption("Ingen Lofthus-eide spillere er i aksjon i disse kampene.")
        return
    live = live.sort_values(["captain_count", "triple_captain_count", "ownership_count", "event_points"], ascending=[False, False, False, False])
    tc = live[live["triple_captain_count"] > 0]
    if not tc.empty:
        lro_note("🚨 Triple Captain i aksjon", " · ".join(f"{r.player}: {getattr(r, 'triple_captains_text', '')}" for r in tc.itertuples()), "gold")
    live["kapteiner_kort"] = live["captains_text"].fillna("").apply(lambda x: _short_manager_list(str(x).split(" · ") if x else [], 2))
    display_table(
        live.head(10),
        ["player", "club", "event_points", "ownership_count", "captain_count", "triple_captain_count", "kapteiner_kort"],
        {"player": "Spiller", "club": "Klubb", "event_points": "GW-poeng", "ownership_count": "Eies av", "captain_count": "Kaptein", "triple_captain_count": "TC", "kapteiner_kort": "Hvem"},
    )

def render_ownership_trends(managers: list[dict], ownership: dict):
    event_id = int(ownership.get("event") or 0)
    if event_id <= 1:
        st.caption("Trenger minst to runder før vi kan vise kjøp, salg og kapteinsendringer.")
        return
    with st.spinner(f"Sammenligner GW{event_id} med GW{event_id-1} …"):
        previous = ownership_for_event(managers, event_id - 1)
    changes = build_ownership_changes(ownership, previous)
    player_changes, moves = changes["players"], changes["moves"]
    if player_changes.empty:
        st.caption("Fant ikke nok data fra forrige runde.")
        return
    incoming = player_changes.sort_values(["ownership_delta", "captain_delta"], ascending=[False, False]).head(6)
    outgoing = player_changes.sort_values(["ownership_delta", "captain_delta"], ascending=[True, True]).head(6)
    cap_changes = player_changes.reindex(player_changes["captain_delta"].abs().sort_values(ascending=False).index).head(6)
    a, b = st.columns(2)
    with a:
        st.markdown("**Mest kjøpt**")
        display_table(incoming, ["player", "ownership_count", "ownership_delta"], {"player": "Spiller", "ownership_count": "Nå", "ownership_delta": "±"})
    with b:
        st.markdown("**Mest solgt**")
        display_table(outgoing, ["player", "ownership_count", "ownership_delta"], {"player": "Spiller", "ownership_count": "Nå", "ownership_delta": "±"})
    st.markdown("**Kapteinsendringer**")
    display_table(cap_changes, ["player", "captain_count", "captain_delta"], {"player": "Spiller", "captain_count": "C nå", "captain_delta": "±"})
    if not moves.empty:
        with st.expander("Hvem kjøpte og solgte?"):
            grouped = moves.groupby(["player", "move"])["manager"].apply(lambda x: ", ".join(sorted(set(x)))).reset_index()
            display_table(grouped, ["move", "player", "manager"], {"move": "", "player": "Spiller", "manager": "Managere"})


def render_ownership_dashboard(managers: list[dict], ownership: dict | None = None):
    """Kapteinsradar først. Navnelister bare når de faktisk hjelper."""
    event_id = current_fpl_event_id()
    if event_id is None:
        st.info("Spiller- og kapteinsradaren våkner når FPL har en aktiv eller ferdig gameweek.")
        return None
    if ownership is None:
        with st.spinner(f"Leser {len(managers)} Lofthus-lag i GW{event_id} …"):
            ownership = ownership_for_event(managers, int(event_id))
    persist_ownership_snapshot(ownership)
    players_df, picks_df = ownership.get("players", pd.DataFrame()), ownership.get("picks", pd.DataFrame())
    loaded, league_size = int(ownership.get("loaded_managers") or 0), int(ownership.get("league_size") or 0)
    if players_df.empty:
        st.warning("Fant ingen offentlige laguttak for denne runden ennå.")
        return ownership

    st.markdown("## Spillere & kapteiner")
    st.caption("Hvem er mest populær? Hvem har bindet? Og hvem har gjort noe sprekt? Det skal være mulig å finne på noen sekunder.")

    captained = players_df[players_df["captain_count"] > 0].copy().sort_values(
        ["captain_count", "triple_captain_count", "ownership_count", "player"],
        ascending=[False, False, False, True],
    )
    tc_rows = captained[captained["triple_captain_count"] > 0]
    most_owned = players_df.sort_values(["ownership_count", "captain_count", "player"], ascending=[False, False, True]).iloc[0]
    most_captained = captained.iloc[0] if not captained.empty else None

    radar_metric_strip([
        {"label": "Mest eid", "value": most_owned["player"], "caption": f"{int(most_owned['ownership_count'])} av {loaded}"},
        {"label": "Mest cappet", "value": most_captained["player"] if most_captained is not None else "–", "caption": f"{int(most_captained['captain_count'])} kapteiner" if most_captained is not None else "Ingen"},
        {"label": "Triple Captain", "value": str(int(players_df["triple_captain_count"].sum())), "caption": "TC-valg denne runden"},
        {"label": "Lag lest", "value": f"{loaded}/{league_size}", "caption": "grunnlag for tallene"},
    ])

    if not tc_rows.empty:
        lro_note("🚨 TRIPLE CAPTAIN", " · ".join(f"{r.player}: {getattr(r, 'triple_captains_text', '')}" for r in tc_rows.itertuples()), "gold")

    st.markdown("### Hvem har cappet hvem?")
    if not captained.empty:
        cap_view = captained.copy()
        cap_view["hvem_kort"] = cap_view["captains_text"].fillna("").apply(lambda x: _short_manager_list(str(x).split(" · ") if x else [], 3))
        display_table(
            cap_view.head(8),
            ["player", "captain_count", "triple_captain_count", "event_points", "hvem_kort"],
            {"player": "Spiller", "captain_count": "Kapteiner", "triple_captain_count": "TC", "event_points": "GW-poeng", "hvem_kort": "Hvem"},
        )
        if len(cap_view) > 8:
            with st.expander(f"Se alle {len(cap_view)} spillere som er cappet"):
                display_table(
                    cap_view.iloc[8:],
                    ["player", "captain_count", "triple_captain_count", "hvem_kort"],
                    {"player": "Spiller", "captain_count": "Kapteiner", "triple_captain_count": "TC", "hvem_kort": "Hvem"},
                )

        st.markdown("### Finn et kapteinsvalg")
        cap_options = captained["element"].astype(int).tolist()
        labels = {}
        for r in captained.itertuples():
            tc_text = f" · {int(r.triple_captain_count)} TC" if int(r.triple_captain_count) else ""
            labels[int(r.element)] = f"{r.player} · {int(r.captain_count)} kapteiner{tc_text}"
        selected_id = st.selectbox(
            "Kapteinsspiller", cap_options,
            format_func=lambda e: labels.get(int(e), str(e)),
            index=0, key="captain_search_v115",
            help="Lista inneholder bare spillere som faktisk er cappet denne runden.",
            label_visibility="collapsed",
        )
        render_player_profile(players_df[players_df["element"] == int(selected_id)].iloc[0], ownership)
    else:
        st.caption("Ingen kapteinsvalg tilgjengelig ennå.")

    st.markdown("### Mest populære spillere")
    popular = players_df.sort_values(["ownership_count", "captain_count", "season_points", "player"], ascending=[False, False, False, True]).head(10).copy()
    display_table(
        popular,
        ["player", "club", "ownership_count", "ownership_pct", "captain_count", "event_points"],
        {"player": "Spiller", "club": "Klubb", "ownership_count": "Eies av", "ownership_pct": "%", "captain_count": "Kaptein", "event_points": "GW-poeng"},
    )

    with st.expander("Mer statistikk · manager, transfers, template og dueller"):
        st.markdown("### Managerblikk")
        manager_options = picks_df[["entry", "manager"]].drop_duplicates().sort_values("manager") if not picks_df.empty else pd.DataFrame()
        if not manager_options.empty:
            ids = manager_options["entry"].astype(int).tolist()
            names = dict(zip(manager_options["entry"].astype(int), manager_options["manager"].astype(str)))
            selected_manager = st.selectbox("Manager", ids, format_func=lambda e: names.get(int(e), str(e)), key="manager_profile_v115", label_visibility="collapsed")
            render_manager_profile(int(selected_manager), ownership, managers)
        st.markdown("### Endringer fra forrige GW")
        render_ownership_trends(managers, ownership)
        st.markdown("### Manager mot manager")
        render_head_to_head(ownership)
        st.markdown("### Rundens historier")
        render_gw_stories(ownership, managers)
        st.markdown("### Lofthus-template")
        template, formation = build_template_xi(players_df)
        if not template.empty:
            st.caption(f"Mest populære lovlige XI · {formation}")
            for pos_id in [1, 2, 3, 4]:
                group = template[template["position_id"] == pos_id]
                if not group.empty:
                    st.write(f"**{POSITION_LABELS[pos_id]}:** " + " · ".join(f"{r.player} ({int(r.ownership_count)}/{loaded})" for r in group.itertuples()))
    if loaded < league_size:
        st.warning(f"Laguttak er lest fra {loaded} av {league_size} lag. Prosentene gjelder lagene FPL faktisk svarte for.")
    return ownership

def render_home_live_snapshot(managers: list[dict]):
    event_id = current_fpl_event_id()
    if event_id is None:
        with st.container(border=True): st.caption("LIVE AKKURAT NÅ"); st.markdown("**Venter på aktiv GW**")
        return
    context = build_live_fixture_context(int(event_id)); active, teams = context.get("active", []), context.get("teams", {})
    with st.container(border=True):
        st.caption("LIVE AKKURAT NÅ")
        if not active:
            st.markdown("**Ingen kamp pågår**"); st.caption(f"Neste: {_next_fixture_label(context.get('next'), teams)}"); return
        st.markdown("**" + " · ".join(_fixture_label(f, teams) for f in active) + "**")
        try:
            ownership = ownership_for_event(managers, int(event_id)); players_df = ownership.get("players", pd.DataFrame())
            ids = {int(f.get(k) or 0) for f in active for k in ("team_h", "team_a")}
            live = players_df[players_df["team_id"].isin(ids)].sort_values(["triple_captain_count", "captain_count", "ownership_count"], ascending=[False, False, False]).head(5)
            bits = []
            for r in live.itertuples():
                text = f"{r.player} · {int(r.ownership_count)} eiere"
                if int(r.triple_captain_count): text += f" · 🚨 TC: {getattr(r, 'triple_captains_text', '')}"
                elif int(r.captain_count): text += f" · {int(r.captain_count)} C"
                bits.append(text)
            if bits: st.caption(" | ".join(bits))
        except Exception:
            pass


def render_clubhouse_home(managers: list[dict]):
    """Forsiden har én jobb: status nå, live, måned og topp 5."""
    managers = managers or []
    df = pd.DataFrame(managers).copy() if managers else pd.DataFrame()
    if not df.empty:
        for column in ["rank", "last_rank", "event_total", "total"]:
            if column not in df.columns: df[column] = pd.NA
        df["rank_num"] = pd.to_numeric(df["rank"], errors="coerce"); df["event_total_num"] = pd.to_numeric(df["event_total"], errors="coerce"); df["total_num"] = pd.to_numeric(df["total"], errors="coerce")
    has_live = bool(not df.empty and df["rank_num"].notna().any())
    event_id = current_fpl_event_id()
    if has_live:
        live_df = df.sort_values(["rank_num", "total_num", "player_name"], ascending=[True, False, True], na_position="last")
        leader = live_df.iloc[0]; gwbest = df.sort_values(["event_total_num", "rank_num"], ascending=[False, True], na_position="last").iloc[0]
        leader_name, leader_team, leader_points = str(leader.get("player_name") or "–"), str(leader.get("entry_name") or ""), int(leader.get("total_num") or 0)
        gw_name, gw_points = str(gwbest.get("player_name") or "–"), int(gwbest.get("event_total_num") or 0)
    else:
        live_df = pd.DataFrame(); leader_name, leader_team, leader_points, gw_name, gw_points = "Sesongen venter", "", 0, "–", 0
    gw_label = "GW" + str(event_id) if event_id else "FØR LIVE"
    leader_sub = html.escape(leader_team) + (f" · {leader_points} poeng" if has_live else "")
    gw_sub = f"{gw_points} poeng" if has_live else "–"
    st.markdown(
        """<style>
        .home-scoreboard{background:linear-gradient(115deg,#071525 0%,#063d2e 56%,#511b1b 100%);border:1px solid rgba(255,255,255,.1);border-radius:22px;color:white;padding:22px 24px;margin:6px 0 20px 0;box-shadow:0 14px 34px rgba(15,23,42,.14)}
        .home-score-kicker{font-size:.72rem;color:#fde68a;font-weight:900;letter-spacing:.1em;text-transform:uppercase}
        .home-score-grid{display:grid;grid-template-columns:minmax(0,1.5fr) repeat(2,minmax(150px,.65fr));gap:18px;align-items:end;margin-top:10px}
        .home-score-leader{font-size:clamp(1.55rem,3vw,2.5rem);font-weight:950;line-height:1.02;letter-spacing:-.045em}
        .home-score-sub{font-size:.88rem;color:#cbd5e1;margin-top:7px}
        .home-score-stat{border-left:1px solid rgba(255,255,255,.18);padding-left:18px}
        .home-score-stat span{display:block;color:#cbd5e1;font-size:.72rem;text-transform:uppercase;letter-spacing:.07em;font-weight:800}
        .home-score-stat strong{display:block;font-size:1.2rem;margin-top:5px}
        @media(max-width:800px){.home-score-grid{grid-template-columns:1fr;gap:12px}.home-score-stat{border-left:0;border-top:1px solid rgba(255,255,255,.14);padding:12px 0 0 0}}
        </style>""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='home-scoreboard'><div class='home-score-kicker'>{gw_label} · LOFTHUS ROAD OPEN</div><div class='home-score-grid'><div><div class='home-score-leader'>{html.escape(leader_name)}</div><div class='home-score-sub'>{leader_sub}</div></div><div class='home-score-stat'><span>Påmeldte</span><strong>{len(managers)}</strong></div><div class='home-score-stat'><span>Rundens beste</span><strong>{html.escape(gw_name)}</strong><div class='home-score-sub'>{gw_sub}</div></div></div></div>",
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.35, 1], gap="large")
    with left:
        st.markdown("### Topp 5"); render_home_top5(live_df)
    with right:
        render_home_live_snapshot(managers); render_month_snapshot(compact=True)


if st.session_state.get("managers"):
    persist_season_archive(st.session_state.get("managers", []))




# ============================================================
# LRO V300 · THE COMPETITIVE UPDATE
# Sportsprodukt + live kontrollrom + Rivalradar.
# ============================================================

st.markdown(
    """
    <style>
    :root {
      --v300-ink:#07131F;
      --v300-navy:#0D1C2A;
      --v300-deep:#122536;
      --v300-paper:#F4F1EA;
      --v300-white:#FFFFFF;
      --v300-soft:#ECE9E2;
      --v300-line:#D9D6CE;
      --v300-text:#111820;
      --v300-muted:#65717D;
      --v300-gold:#D49A1F;
      --v300-gold-soft:#F4E7C5;
      --v300-green:#0E7C66;
      --v300-green-soft:#E4F3EF;
      --v300-red:#C84C43;
      --v300-red-soft:#F7E8E6;
      --v300-blue:#315F84;
      --v300-radius:10px;
      --v300-radius-lg:15px;
      --v300-shadow:0 12px 34px rgba(7,19,31,.08);
    }

    #MainMenu, footer {visibility:hidden !important;}
    [data-testid="stHeader"] {background:transparent !important;height:0 !important;}
    [data-testid="stToolbar"], [data-testid="stDecoration"] {display:none !important;}
    html, body, [data-testid="stAppViewContainer"], .stApp {
      background:var(--v300-paper) !important;
      color:var(--v300-text) !important;
      overflow-x:hidden;
    }
    .block-container {
      max-width:1360px !important;
      padding:1rem clamp(.8rem,2.8vw,2.25rem) 4rem !important;
    }
    section[data-testid="stSidebar"] {background:var(--v300-ink) !important;border-right:1px solid rgba(255,255,255,.08);}
    section[data-testid="stSidebar"] * {color:#EAF0F5;}

    h1,h2,h3,h4,p,div,span,label,button,input,textarea {
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
    }
    h1,h2,h3 {letter-spacing:-.035em;color:var(--v300-text);}
    [data-testid="stCaptionContainer"] {color:var(--v300-muted) !important;}

    .v300-shell {margin-bottom:18px;}
    .v300-header {
      background:var(--v300-ink);
      color:#fff;
      border-radius:var(--v300-radius-lg) var(--v300-radius-lg) 0 0;
      padding:18px 22px 17px;
      border-bottom:1px solid rgba(255,255,255,.08);
    }
    .v300-header-inner {display:flex;align-items:flex-end;justify-content:space-between;gap:24px;}
    .v300-brand {font-size:clamp(1.45rem,2.5vw,2.1rem);font-weight:900;letter-spacing:-.052em;line-height:.98;color:#fff;}
    .v300-brand-sub {margin-top:6px;color:#9EACBA;font-size:.73rem;letter-spacing:.11em;text-transform:uppercase;font-weight:760;}
    .v300-head-status {display:flex;gap:20px;align-items:flex-end;text-align:right;}
    .v300-head-item-label {font-size:.6rem;color:#738394;text-transform:uppercase;letter-spacing:.1em;font-weight:850;}
    .v300-head-item-value {font-size:.86rem;color:#fff;font-weight:780;margin-top:3px;white-space:nowrap;}
    .v300-dot {display:inline-block;width:7px;height:7px;border-radius:50%;background:#33B894;margin-right:6px;box-shadow:0 0 0 3px rgba(51,184,148,.13);}

    .v300-page-head {display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin:8px 0 19px;}
    .v300-page-title {font-size:clamp(1.72rem,3vw,2.45rem);font-weight:900;letter-spacing:-.055em;line-height:1;}
    .v300-page-sub {font-size:.9rem;color:var(--v300-muted);margin-top:6px;max-width:760px;}
    .v300-section {display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin:26px 0 8px;padding-bottom:7px;border-bottom:1px solid var(--v300-line);}
    .v300-section-title {font-size:1.08rem;font-weight:860;letter-spacing:-.025em;}
    .v300-section-note {font-size:.76rem;color:var(--v300-muted);text-align:right;}

    .v300-statbar {display:flex;border-top:1px solid var(--v300-line);border-bottom:1px solid var(--v300-line);margin:8px 0 18px;overflow:auto;}
    .v300-stat {min-width:110px;flex:1 1 130px;padding:11px 14px;border-right:1px solid var(--v300-line);}
    .v300-stat:last-child {border-right:0;}
    .v300-stat-value {font-size:1.08rem;font-weight:900;letter-spacing:-.03em;white-space:nowrap;}
    .v300-stat-label {font-size:.61rem;color:var(--v300-muted);text-transform:uppercase;letter-spacing:.085em;font-weight:820;margin-top:3px;white-space:nowrap;}

    .v300-list {border-top:1px solid var(--v300-line);margin:4px 0 17px;}
    .v300-row {display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:12px;align-items:center;padding:10px 2px;border-bottom:1px solid var(--v300-line);transition:background 160ms ease,padding 160ms ease;}
    .v300-row:hover {background:rgba(255,255,255,.44);padding-left:7px;padding-right:7px;}
    .v300-rank {font-size:.73rem;color:var(--v300-muted);font-weight:850;font-variant-numeric:tabular-nums;}
    .v300-who {font-size:.92rem;font-weight:790;min-width:0;}
    .v300-meta {display:block;color:var(--v300-muted);font-size:.74rem;font-weight:500;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .v300-num {font-size:.86rem;font-weight:860;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;}
    .v300-up {color:var(--v300-green);font-weight:850;}.v300-down {color:var(--v300-red);font-weight:850;}

    .v300-tag {display:inline-flex;align-items:center;margin-left:6px;padding:2px 5px;border-radius:4px;font-size:.58rem;font-weight:900;letter-spacing:.04em;vertical-align:2px;}
    .v300-tag.tc {background:var(--v300-red-soft);color:var(--v300-red);border:1px solid #E6BBB7;}
    .v300-tag.c {background:#E8EDF1;color:#455A6B;}
    .v300-tag.gold {background:var(--v300-gold-soft);color:#7B5710;}
    .v300-tag.live {background:var(--v300-green-soft);color:var(--v300-green);}

    .v300-live {background:var(--v300-ink);color:#fff;border-radius:var(--v300-radius-lg);overflow:hidden;margin:8px 0 20px;box-shadow:var(--v300-shadow);}
    .v300-live-head {display:flex;justify-content:space-between;align-items:flex-end;gap:18px;padding:16px 19px 13px;border-bottom:1px solid rgba(255,255,255,.09);}
    .v300-live-kicker {font-size:.62rem;color:#8291A0;letter-spacing:.11em;text-transform:uppercase;font-weight:900;}
    .v300-live-score {font-size:clamp(1.1rem,2.1vw,1.55rem);font-weight:900;letter-spacing:-.04em;margin-top:4px;color:#fff;}
    .v300-live-note {font-size:.76rem;color:#AEB9C4;text-align:right;}
    .v300-live-body {background:#fff;color:var(--v300-text);}
    .v300-live-player {display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;padding:11px 17px;border-bottom:1px solid #E7E7E2;}
    .v300-live-player:last-child {border-bottom:0;}
    .v300-live-name {font-weight:830;font-size:.9rem;}
    .v300-live-meta {font-size:.73rem;color:var(--v300-muted);margin-top:2px;}
    .v300-live-points {font-weight:900;font-size:.96rem;font-variant-numeric:tabular-nums;}

    .v300-stories {border-top:1px solid var(--v300-line);}
    .v300-story {display:grid;grid-template-columns:22px minmax(0,1fr);gap:10px;padding:10px 0;border-bottom:1px solid var(--v300-line);font-size:.9rem;line-height:1.35;}
    .v300-story-mark {font-weight:950;color:var(--v300-muted);text-align:center;}.v300-story-mark.hot{color:var(--v300-red)}.v300-story-mark.up{color:var(--v300-green)}.v300-story-mark.down{color:var(--v300-red)}

    .v300-alert {display:grid;grid-template-columns:4px minmax(0,1fr);border:1px solid var(--v300-line);background:#fff;border-radius:var(--v300-radius);overflow:hidden;margin:8px 0 14px;}
    .v300-alert-bar {background:var(--v300-red);}.v300-alert-body{padding:11px 13px;}
    .v300-alert-title {font-size:.59rem;color:var(--v300-red);text-transform:uppercase;letter-spacing:.1em;font-weight:900;}
    .v300-alert-main {font-size:.93rem;font-weight:800;margin-top:3px;}

    .v300-profile {background:var(--v300-ink);color:#fff;border-radius:var(--v300-radius-lg);padding:18px 20px;margin:7px 0 14px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:end;}
    .v300-profile-name {font-size:clamp(1.35rem,2.4vw,1.9rem);font-weight:900;letter-spacing:-.045em;line-height:1;}
    .v300-profile-team {color:#9EACBA;font-size:.8rem;margin-top:5px;}
    .v300-profile-rank {text-align:right;}.v300-profile-rank strong{display:block;font-size:1.85rem;letter-spacing:-.05em;}.v300-profile-rank span{display:block;color:#8F9DAA;font-size:.62rem;text-transform:uppercase;letter-spacing:.09em;}

    .v300-form {display:flex;gap:0;border-top:1px solid var(--v300-line);border-bottom:1px solid var(--v300-line);overflow:auto;margin:5px 0 16px;}
    .v300-form-item {min-width:76px;flex:1;padding:9px 12px;border-right:1px solid var(--v300-line);}.v300-form-item:last-child{border-right:0;}
    .v300-form-gw {font-size:.58rem;color:var(--v300-muted);text-transform:uppercase;letter-spacing:.08em;font-weight:850;}.v300-form-points{font-size:.95rem;font-weight:900;margin-top:2px;}

    .v300-merits {display:flex;gap:18px;flex-wrap:wrap;padding:4px 0 13px;border-bottom:1px solid var(--v300-line);}
    .v300-merit strong {font-size:1.1rem;}.v300-merit span {display:block;font-size:.68rem;color:var(--v300-muted);margin-top:1px;}

    .v300-squad {border-top:1px solid var(--v300-line);margin-bottom:15px;}
    .v300-squad-row {display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:9px 2px;border-bottom:1px solid var(--v300-line);align-items:center;}
    .v300-squad-name {font-size:.9rem;font-weight:780;}.v300-squad-meta {font-size:.74rem;color:var(--v300-muted);text-align:right;white-space:nowrap;}
    .v300-bench {opacity:.68;}

    .v300-table-wrap {width:100%;overflow:hidden;border-top:1px solid var(--v300-line);margin:5px 0 18px;}
    .v300-table {width:100%;border-collapse:collapse;background:transparent;font-size:.85rem;}
    .v300-table th {padding:8px 8px;text-align:left;font-size:.59rem;color:var(--v300-muted);text-transform:uppercase;letter-spacing:.085em;font-weight:900;border-bottom:1px solid var(--v300-line);}
    .v300-table td {padding:9px 8px;border-bottom:1px solid var(--v300-line);vertical-align:middle;}
    .v300-table tbody tr:hover {background:rgba(255,255,255,.45);}
    .v300-table .right {text-align:right;font-variant-numeric:tabular-nums;}.v300-table .strong{font-weight:840;}.v300-table .muted{display:block;color:var(--v300-muted);font-size:.72rem;margin-top:2px;}
    .v300-place {display:inline-flex;align-items:center;justify-content:center;width:25px;height:25px;border-radius:50%;font-size:.71rem;font-weight:900;background:#E4E3DE;color:#3D4852;}
    .v300-place.one{background:#EEDFB0;color:#79570F}.v300-place.two{background:#DFE2E5;color:#58616A}.v300-place.three{background:#E9D5C6;color:#7E4D2B}

    .v300-podium {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--v300-line);border-bottom:1px solid var(--v300-line);margin:6px 0 18px;}
    .v300-podium-item {padding:14px 16px;border-right:1px solid var(--v300-line);}.v300-podium-item:last-child{border-right:0}
    .v300-podium-place {font-size:.6rem;color:var(--v300-muted);text-transform:uppercase;letter-spacing:.085em;font-weight:900;}.v300-podium-name{font-size:.96rem;font-weight:840;margin-top:4px}.v300-podium-score{font-size:.73rem;color:var(--v300-muted);margin-top:2px}

    .v300-callout {background:#fff;border-left:3px solid var(--v300-gold);padding:12px 14px;margin:8px 0 14px;}
    .v300-callout strong{display:block;font-size:.91rem;}.v300-callout span{display:block;color:var(--v300-muted);font-size:.78rem;margin-top:3px;line-height:1.42;}
    .v300-callout.green{border-left-color:var(--v300-green)}.v300-callout.red{border-left-color:var(--v300-red)}

    .v300-rec {border-top:1px solid var(--v300-line);padding:13px 0 12px;}
    .v300-rec:first-child{margin-top:4px}.v300-rec-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.v300-rec-name{font-weight:900;font-size:1rem}.v300-rec-score{font-size:.68rem;text-transform:uppercase;letter-spacing:.07em;font-weight:900;color:var(--v300-green);}
    .v300-rec-meta{font-size:.76rem;color:var(--v300-muted);margin-top:3px}.v300-rec-reasons{font-size:.8rem;line-height:1.5;margin-top:7px;color:#313A43;}

    .v300-compare-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0;border-top:1px solid var(--v300-line);border-bottom:1px solid var(--v300-line);margin:7px 0 16px;}
    .v300-compare-person {padding:12px 14px;border-right:1px solid var(--v300-line);}.v300-compare-person:last-child{border-right:0}.v300-compare-name{font-weight:850}.v300-compare-score{font-size:1.12rem;font-weight:900;margin-top:3px}.v300-compare-meta{font-size:.7rem;color:var(--v300-muted);margin-top:2px}

    .v300-odds {border-top:1px solid var(--v300-line);margin:6px 0 16px;}
    .v300-odds-row {display:grid;grid-template-columns:minmax(0,1fr) repeat(3,90px);gap:9px;padding:9px 2px;border-bottom:1px solid var(--v300-line);font-size:.84rem;align-items:center;}.v300-odds-row.head{font-size:.58rem;text-transform:uppercase;letter-spacing:.08em;color:var(--v300-muted);font-weight:900}.v300-odds-row>div:not(:first-child){text-align:right;font-variant-numeric:tabular-nums}.v300-odds-name{font-weight:800}

    .stButton > button {border-radius:7px !important;border:1px solid #CFCFC8 !important;background:#fff !important;color:var(--v300-text) !important;font-weight:800 !important;box-shadow:none !important;min-height:39px;transition:background 150ms ease,border-color 150ms ease,color 150ms ease !important;}
    .stButton > button:hover {background:#EDEAE3 !important;border-color:#BBB9B2 !important;}
    .stButton > button[kind="primary"] {background:var(--v300-ink) !important;color:#fff !important;border-color:var(--v300-ink) !important;}
    .stButton > button[kind="primary"]:hover {background:var(--v300-deep) !important;border-color:var(--v300-deep) !important;}
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div, .stMultiSelect [data-baseweb="select"] > div {background:#fff !important;border:1px solid #CFCEC8 !important;border-radius:7px !important;box-shadow:none !important;min-height:41px;}
    .stTextInput input:focus {border-color:#9FA8B0 !important;box-shadow:0 0 0 3px rgba(49,95,132,.08) !important;}
    .stTextInput label,.stSelectbox label,.stMultiSelect label {font-size:.74rem !important;font-weight:790 !important;color:var(--v300-text) !important;}
    div[data-testid="stExpander"] {border:0 !important;border-top:1px solid var(--v300-line) !important;border-radius:0 !important;background:transparent !important;box-shadow:none !important;}
    div[data-testid="stExpander"] details summary {padding-left:0 !important;padding-right:0 !important;font-weight:800 !important;}
    [data-testid="stAlert"] {border-radius:7px !important;}
    div[data-testid="stDataFrame"] {border:1px solid var(--v300-line) !important;border-radius:7px !important;overflow:hidden;}

    @media(max-width:900px){
      .v300-head-status .v300-head-item:nth-child(1){display:none}.v300-compare-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.v300-compare-person:nth-child(2n){border-right:0}.v300-podium{grid-template-columns:1fr}.v300-podium-item{border-right:0;border-bottom:1px solid var(--v300-line)}.v300-podium-item:last-child{border-bottom:0}
    }
    @media(max-width:720px){
      .block-container{padding:.65rem .68rem 3rem !important}.v300-header{padding:15px 14px 14px}.v300-header-inner{display:block}.v300-head-status{margin-top:12px;text-align:left;justify-content:flex-start;gap:14px}.v300-page-title{font-size:1.65rem}.v300-page-sub{font-size:.83rem}.v300-section{margin-top:22px}.v300-section-note{display:none}.v300-profile{grid-template-columns:1fr auto;padding:16px 15px}.v300-stat{padding:10px 11px}.v300-row{grid-template-columns:29px minmax(0,1fr) auto}.v300-odds-row{grid-template-columns:minmax(0,1fr) 64px 64px 64px;gap:5px}.v300-table .col-team,.v300-table .col-gw,.v300-table .col-move{display:none}.v300-table{font-size:.81rem;table-layout:fixed}.v300-table .col-place{width:40px}.v300-table .col-points{width:65px}
    }
    @media(max-width:430px){
      .v300-brand{font-size:1.32rem}.v300-brand-sub{font-size:.64rem}.v300-head-item-value{font-size:.78rem}.v300-live-score{font-size:1.08rem}.v300-live-meta{font-size:.69rem}.v300-who{font-size:.86rem}.v300-num{font-size:.79rem}.v300-squad-meta{font-size:.68rem}.v300-compare-grid{grid-template-columns:1fr}.v300-compare-person{border-right:0;border-bottom:1px solid var(--v300-line)}.v300-compare-person:last-child{border-bottom:0}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def v300_num(value, default=0) -> int:
    try:
        if value is None or pd.isna(value):
            return int(default)
        return int(float(value))
    except Exception:
        return int(default)


def v300_float(value, default=0.0) -> float:
    try:
        if value is None or pd.isna(value) or str(value).strip() == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def v300_pct(value) -> str:
    return f"{max(0.0, min(100.0, v300_float(value))):.0f}%"


def v300_decimal_odds(pct) -> str:
    p = max(.2, min(99.0, v300_float(pct)))
    return f"{min(501.0, 100.0 / p):.2f}"


def v300_price(value) -> str:
    return f"£{v300_float(value):.1f}"


def v300_header(managers: list[dict]):
    event_id = current_fpl_event_id()
    season = _season_label_from_bootstrap() or "2026/27"
    live = False
    if event_id:
        try:
            live = bool(build_live_fixture_context(int(event_id)).get("active"))
        except Exception:
            live = False
    status = "Live nå" if live else (f"GW{event_id}" if event_id else "Sesongstart")
    dot = "<span class='v300-dot'></span>" if live else ""
    st.markdown(
        f"""
        <div class='v300-shell'>
          <div class='v300-header'>
            <div class='v300-header-inner'>
              <div><div class='v300-brand'>Lofthus Road Open</div><div class='v300-brand-sub'>Fantasy Football Club</div></div>
              <div class='v300-head-status'>
                <div class='v300-head-item'><div class='v300-head-item-label'>Sesong</div><div class='v300-head-item-value'>{html.escape(season)}</div></div>
                <div class='v300-head-item'><div class='v300-head-item-label'>Liga</div><div class='v300-head-item-value'>{len(managers)} managere</div></div>
                <div class='v300-head-item'><div class='v300-head-item-label'>Status</div><div class='v300-head-item-value'>{dot}{html.escape(status)}</div></div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def v300_nav(options: list[str], key: str, default: str) -> str:
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


def v300_page_head(title: str, sub: str = ""):
    st.markdown(
        "<div class='v300-page-head'><div>"
        f"<div class='v300-page-title'>{html.escape(title)}</div>"
        + (f"<div class='v300-page-sub'>{html.escape(sub)}</div>" if sub else "")
        + "</div></div>",
        unsafe_allow_html=True,
    )


def v300_section(title: str, note: str = ""):
    st.markdown(
        f"<div class='v300-section'><div class='v300-section-title'>{html.escape(title)}</div><div class='v300-section-note'>{html.escape(note)}</div></div>",
        unsafe_allow_html=True,
    )


def v300_statbar(items: list[tuple[str, str]]):
    bits = []
    for value, label in items:
        bits.append(f"<div class='v300-stat'><div class='v300-stat-value'>{html.escape(str(value))}</div><div class='v300-stat-label'>{html.escape(str(label))}</div></div>")
    if bits:
        st.markdown("<div class='v300-statbar'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def v300_rows(rows: list[dict]):
    bits = []
    for row in rows:
        rank = html.escape(str(row.get("rank", "")))
        who = html.escape(str(row.get("who", "")))
        meta = html.escape(str(row.get("meta", "")))
        num = html.escape(str(row.get("num", "")))
        tag = str(row.get("tag_html", ""))
        rank_class = html.escape(str(row.get("rank_class", "")))
        num_class = html.escape(str(row.get("num_class", "")))
        bits.append(f"<div class='v300-row'><div class='v300-rank {rank_class}'>{rank}</div><div class='v300-who'>{who}{tag}<span class='v300-meta'>{meta}</span></div><div class='v300-num {num_class}'>{num}</div></div>")
    if bits:
        st.markdown("<div class='v300-list'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def v300_alert(title: str, main: str):
    st.markdown(f"<div class='v300-alert'><div class='v300-alert-bar'></div><div class='v300-alert-body'><div class='v300-alert-title'>{html.escape(title)}</div><div class='v300-alert-main'>{html.escape(main)}</div></div></div>", unsafe_allow_html=True)


def v300_callout(title: str, text: str, tone: str = ""):
    cls = f" {tone}" if tone in {"green", "red"} else ""
    st.markdown(f"<div class='v300-callout{cls}'><strong>{html.escape(title)}</strong><span>{html.escape(text)}</span></div>", unsafe_allow_html=True)


@st.cache_data(ttl=900)
def v300_bootstrap_players() -> pd.DataFrame:
    bootstrap = get_bootstrap_static()
    teams = {v300_num(t.get("id")): str(t.get("short_name") or t.get("name") or "") for t in bootstrap.get("teams", []) or []}
    rows = []
    for p in bootstrap.get("elements", []) or []:
        pid = v300_num(p.get("id"))
        if not pid:
            continue
        pos_id = v300_num(p.get("element_type"))
        minutes = v300_float(p.get("minutes"))
        xgi = v300_float(p.get("expected_goal_involvements"), v300_float(p.get("expected_goals")) + v300_float(p.get("expected_assists")))
        xgi90 = (xgi * 90 / minutes) if minutes > 0 else 0.0
        chance_raw = p.get("chance_of_playing_next_round")
        chance = 100.0 if chance_raw is None and str(p.get("status") or "a") == "a" else v300_float(chance_raw, 65.0)
        rows.append({
            "element": pid,
            "player": str(p.get("web_name") or p.get("second_name") or p.get("first_name") or pid),
            "full_name": f"{p.get('first_name') or ''} {p.get('second_name') or ''}".strip(),
            "team_id": v300_num(p.get("team")),
            "club": teams.get(v300_num(p.get("team")), ""),
            "position_id": pos_id,
            "position": POSITION_LABELS.get(pos_id, "Ukjent"),
            "price": v300_float(p.get("now_cost")) / 10.0,
            "form": v300_float(p.get("form")),
            "ppg": v300_float(p.get("points_per_game")),
            "season_points": v300_num(p.get("total_points")),
            "minutes": v300_num(p.get("minutes")),
            "starts": v300_num(p.get("starts")),
            "selected_pct": v300_float(p.get("selected_by_percent")),
            "transfers_in": v300_num(p.get("transfers_in_event")),
            "transfers_out": v300_num(p.get("transfers_out_event")),
            "xg": v300_float(p.get("expected_goals")),
            "xa": v300_float(p.get("expected_assists")),
            "xgi": xgi,
            "xgi90": xgi90,
            "ict": v300_float(p.get("ict_index")),
            "status": str(p.get("status") or ""),
            "news": str(p.get("news") or ""),
            "chance": chance,
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800)
def v300_all_fixtures() -> list[dict]:
    try:
        data = get_json("/fixtures/")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def v300_fixture_window(team_id: int, start_event: int, stop_event: int) -> tuple[float, str, int]:
    bootstrap = get_bootstrap_static()
    teams = {v300_num(t.get("id")): str(t.get("short_name") or t.get("name") or "") for t in bootstrap.get("teams", []) or []}
    fdrs = []
    labels = []
    count = 0
    for f in v300_all_fixtures():
        ev = v300_num(f.get("event"))
        if ev < start_event or ev > stop_event or bool(f.get("finished")):
            continue
        home_id, away_id = v300_num(f.get("team_h")), v300_num(f.get("team_a"))
        if team_id == home_id:
            opp = teams.get(away_id, "?")
            fdr = v300_float(f.get("team_h_difficulty"), 3)
            labels.append(f"{opp} H")
            fdrs.append(fdr)
            count += 1
        elif team_id == away_id:
            opp = teams.get(home_id, "?")
            fdr = v300_float(f.get("team_a_difficulty"), 3)
            labels.append(f"{opp} B")
            fdrs.append(fdr)
            count += 1
    avg = sum(fdrs) / len(fdrs) if fdrs else 3.0
    return avg, " · ".join(labels[:6]), count


def v300_period_events(period: str) -> tuple[int, int]:
    current = v300_num(current_fpl_event_id(), 1)
    bootstrap = get_bootstrap_static()
    max_event = max([v300_num(e.get("id")) for e in bootstrap.get("events", []) or []] or [38])
    if period == "Neste GW":
        return min(current + 1, max_event), min(current + 1, max_event)
    if period == "Neste 3 GW":
        return min(current + 1, max_event), min(current + 3, max_event)
    if period == "Neste 5 GW":
        return min(current + 1, max_event), min(current + 5, max_event)
    if period == "Resten av måneden":
        phase = current_month_phase(bootstrap)
        return min(current + 1, max_event), min(v300_num((phase or {}).get("stop_event"), max_event), max_event)
    return min(current + 1, max_event), max_event


def v300_player_pool(period: str) -> pd.DataFrame:
    df = v300_bootstrap_players().copy()
    if df.empty:
        return df
    start, stop = v300_period_events(period)
    fixtures = []
    for row in df.itertuples():
        avg, text, count = v300_fixture_window(v300_num(row.team_id), start, stop)
        fixtures.append((avg, text, count))
    df["avg_fdr"] = [x[0] for x in fixtures]
    df["fixtures"] = [x[1] for x in fixtures]
    df["fixture_count"] = [x[2] for x in fixtures]
    current = max(1, v300_num(current_fpl_event_id(), 1))
    df["start_rate"] = (pd.to_numeric(df["starts"], errors="coerce").fillna(0) / current).clip(0, 1)
    df["availability"] = (pd.to_numeric(df["chance"], errors="coerce").fillna(65) / 100.0).clip(0, 1)
    df.loc[df["status"].astype(str) == "u", "availability"] = 0.0
    df.loc[df["status"].astype(str).isin(["i", "s"]), "availability"] = df.loc[df["status"].astype(str).isin(["i", "s"]), "availability"].clip(upper=.55)
    easy = (6 - pd.to_numeric(df["avg_fdr"], errors="coerce").fillna(3)).clip(1, 5)
    value = (pd.to_numeric(df["ppg"], errors="coerce").fillna(0) / pd.to_numeric(df["price"], errors="coerce").replace(0, np.nan)).fillna(0).clip(0, 1.8)
    xgi = pd.to_numeric(df["xgi90"], errors="coerce").fillna(0).clip(0, 1.5)
    df["quality"] = (
        .28 * pd.to_numeric(df["form"], errors="coerce").fillna(0).clip(0, 12)
        + .22 * pd.to_numeric(df["ppg"], errors="coerce").fillna(0).clip(0, 12)
        + .18 * easy
        + .12 * (xgi * 5)
        + .10 * (df["start_rate"] * 5)
        + .10 * (value * 3)
    ) * df["availability"]
    return df


def v300_enrich_ownership(ownership: dict | None) -> dict | None:
    if not ownership:
        return ownership
    meta = v300_bootstrap_players()
    if meta.empty:
        return ownership
    keep = ["element","price","form","ppg","selected_pct","status","news","chance","xgi90","starts","minutes"]
    out = dict(ownership)
    for key in ["picks", "players"]:
        df = ownership.get(key, pd.DataFrame()).copy()
        if df.empty:
            out[key] = df
            continue
        drop = [c for c in keep if c != "element" and c in df.columns]
        if drop:
            df = df.drop(columns=drop)
        df = df.merge(meta[keep], on="element", how="left")
        out[key] = df
    return out


def v300_get_ownership(managers: list[dict]) -> dict | None:
    event_id = current_fpl_event_id()
    if not event_id:
        return None
    key = f"_v300_ownership_{event_id}"
    if key not in st.session_state:
        try:
            st.session_state[key] = v300_enrich_ownership(ownership_for_event(managers, int(event_id)))
        except Exception:
            st.session_state[key] = None
    return st.session_state.get(key)


def v300_live_section(managers: list[dict], ownership: dict | None = None, compact: bool = False) -> bool:
    event_id = current_fpl_event_id()
    if not event_id:
        return False
    try:
        context = build_live_fixture_context(int(event_id))
    except Exception:
        return False
    active = context.get("active", []) or []
    if not active:
        return False
    teams = context.get("teams", {}) or {}
    ownership = ownership or v300_get_ownership(managers)
    labels = [_fixture_label(f, teams) for f in active]
    scoreline = " · ".join(labels[:2]) + (f" +{len(labels)-2}" if len(labels) > 2 else "")
    team_ids = {v300_num(f.get(k)) for f in active for k in ("team_h", "team_a")}
    players = ownership.get("players", pd.DataFrame()).copy() if ownership else pd.DataFrame()
    if not players.empty:
        players = players[players["team_id"].isin(team_ids)].copy()
        players["relevance"] = (
            pd.to_numeric(players.get("triple_captain_count"), errors="coerce").fillna(0) * 10000
            + pd.to_numeric(players.get("captain_count"), errors="coerce").fillna(0) * 600
            + pd.to_numeric(players.get("ownership_count"), errors="coerce").fillna(0) * 10
            + pd.to_numeric(players.get("event_points"), errors="coerce").fillna(0) * 7
        )
        players = players.sort_values(["relevance","event_points","player"], ascending=[False,False,True]).head(4 if compact else 7)
    bits = []
    if not players.empty:
        for _, r in players.iterrows():
            c, tc, own, pts = v300_num(r.get("captain_count")), v300_num(r.get("triple_captain_count")), v300_num(r.get("ownership_count")), v300_num(r.get("event_points"))
            tags = (f"<span class='v300-tag tc'>{tc} TC</span>" if tc else "") + (f"<span class='v300-tag c'>{c} C</span>" if c else "")
            meta = f"{r.get('club','')} · {own} eiere"
            if tc and str(r.get("triple_captains_text") or "").strip():
                names = [canonical_hof_name(x.strip()) for x in str(r.get("triple_captains_text") or "").split(" · ") if x.strip()]
                meta += " · TC: " + ", ".join(names[:2])
            bits.append(f"<div class='v300-live-player'><div><div class='v300-live-name'>{html.escape(str(r.get('player','')))}{tags}</div><div class='v300-live-meta'>{html.escape(meta)}</div></div><div class='v300-live-points'>{pts} p</div></div>")
    st.markdown(
        f"<div class='v300-live'><div class='v300-live-head'><div><div class='v300-live-kicker'><span class='v300-dot'></span>Live nå</div><div class='v300-live-score'>{html.escape(scoreline)}</div></div><div class='v300-live-note'>GW{event_id}</div></div>"
        + ("<div class='v300-live-body'>" + "".join(bits) + "</div>" if bits else "") + "</div>",
        unsafe_allow_html=True,
    )
    return True


def v300_manager_frame(managers: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(managers or []).copy()
    if df.empty:
        return pd.DataFrame()
    for col in ["rank","last_rank","event_total","total","entry"]:
        if col not in df.columns:
            df[col] = pd.NA
    df["rank_num"] = pd.to_numeric(df["rank"], errors="coerce")
    df["last_rank_num"] = pd.to_numeric(df["last_rank"], errors="coerce")
    df["event_num"] = pd.to_numeric(df["event_total"], errors="coerce").fillna(0)
    df["total_num"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
    df["movement"] = df["last_rank_num"] - df["rank_num"]
    df["player_name"] = df.get("player_name", "").fillna("").astype(str).map(canonical_hof_name)
    df["entry_name"] = df.get("entry_name", "").fillna("").astype(str)
    return df


def v300_month_table(managers: list[dict], limit: int = 3) -> tuple[str, pd.DataFrame, bool]:
    phase, month = get_current_month_table(DEFAULT_LEAGUE_ID)
    name = str((phase or {}).get("name") or "Måneden")
    all_zero = month.empty or pd.to_numeric(month.get("points"), errors="coerce").fillna(0).sum() == 0
    if all_zero:
        names = sorted({canonical_hof_name(str(m.get("player_name") or "")) for m in managers if str(m.get("player_name") or "").strip()}, key=normalize_text)
        month = pd.DataFrame([{"rank": i+1, "manager": n, "team": "", "points": 0} for i, n in enumerate(names[:max(limit, 3)])])
    return name, month.head(limit).copy(), all_zero


def v300_month_podium(managers: list[dict], limit: int = 3):
    name, month, all_zero = v300_month_table(managers, limit)
    if month.empty:
        return
    bits = []
    medals = ["1.", "2.", "3."]
    for i, r in month.reset_index(drop=True).iterrows():
        bits.append(f"<div class='v300-podium-item'><div class='v300-podium-place'>{medals[i] if i < 3 else str(i+1)+'.'}</div><div class='v300-podium-name'>{html.escape(str(r.get('manager','')))}</div><div class='v300-podium-score'>{v300_num(r.get('points'))} poeng</div></div>")
    st.markdown("<div class='v300-podium'>" + "".join(bits) + "</div>", unsafe_allow_html=True)
    if all_zero:
        st.caption(f"Ingen {name.lower()}poeng ennå.")


def v300_captain_frame(ownership: dict | None) -> pd.DataFrame:
    if not ownership:
        return pd.DataFrame()
    players = ownership.get("players", pd.DataFrame()).copy()
    if players.empty:
        return players
    capt = players[pd.to_numeric(players.get("captain_count"), errors="coerce").fillna(0) > 0].copy()
    return capt.sort_values(["captain_count","triple_captain_count","ownership_count","player"], ascending=[False,False,False,True])


def v300_captains(ownership: dict | None, limit: int = 8):
    capt = v300_captain_frame(ownership)
    if capt.empty:
        st.caption("Ingen kapteinsdata ennå.")
        return
    tc = capt[pd.to_numeric(capt.get("triple_captain_count"), errors="coerce").fillna(0) > 0]
    for _, r in tc.iterrows():
        names = [canonical_hof_name(x.strip()) for x in str(r.get("triple_captains_text") or "").split(" · ") if x.strip()]
        if names:
            v300_alert("Triple Captain", f"{', '.join(names)} har Triple Captain på {r.get('player','')}.")
    rows = []
    for i, (_, r) in enumerate(capt.head(limit).iterrows(), 1):
        c, tc_n = v300_num(r.get("captain_count")), v300_num(r.get("triple_captain_count"))
        tag = f"<span class='v300-tag tc'>{tc_n} TC</span>" if tc_n else ""
        rows.append({"rank": i, "who": str(r.get("player","")), "meta": str(r.get("club","")), "num": f"{c} C", "tag_html": tag})
    v300_rows(rows)
    if len(capt) > limit:
        with st.expander(f"Se alle {len(capt)} kapteinsvalg"):
            extra = []
            for i, (_, r) in enumerate(capt.iterrows(), 1):
                extra.append({"rank": i, "who": str(r.get("player","")), "meta": str(r.get("club","")), "num": f"{v300_num(r.get('captain_count'))} C"})
            v300_rows(extra)


def v300_player_profile(row: pd.Series, ownership: dict | None):
    player = str(row.get("player") or "")
    own = v300_num(row.get("ownership_count")); loaded = v300_num((ownership or {}).get("loaded_managers"), 0)
    cap = v300_num(row.get("captain_count")); tc = v300_num(row.get("triple_captain_count")); bench = v300_num(row.get("bench_count")); pts = v300_num(row.get("event_points"))
    meta = v300_bootstrap_players()
    hit = meta[meta["element"] == v300_num(row.get("element"))]
    price = v300_float(hit.iloc[0].get("price")) if not hit.empty else v300_float(row.get("price"))
    pos = str(hit.iloc[0].get("position")) if not hit.empty else str(row.get("position") or "")
    club = str(hit.iloc[0].get("club")) if not hit.empty else str(row.get("club") or "")
    v300_statbar([(f"{own}/{loaded}" if loaded else str(own), "eier"), (str(cap), "kapteiner"), (str(tc), "Triple Captain"), (str(bench), "på benken"), (f"{pts} p", "GW"), (v300_price(price), pos)])
    st.caption(f"{club} · {pos}")
    tc_names = [canonical_hof_name(x.strip()) for x in str(row.get("triple_captains_text") or "").split(" · ") if x.strip()]
    cap_names = [canonical_hof_name(x.strip()) for x in str(row.get("captains_text") or "").split(" · ") if x.strip()]
    owner_names = [canonical_hof_name(x.strip()) for x in str(row.get("owners_text") or "").split(" · ") if x.strip()]
    if tc_names:
        v300_alert("Triple Captain", ", ".join(tc_names))
    if cap_names:
        v300_section("Kaptein hos")
        st.write(" · ".join(cap_names))
    if owner_names:
        v300_section("Hvem har ham?")
        st.write(" · ".join(owner_names[:5]))
        if len(owner_names) > 5:
            with st.expander(f"Se alle {len(owner_names)}"):
                st.write(" · ".join(owner_names))
    if loaded:
        normal = max(0, own - cap)
        no_own = max(0, loaded - own)
        pieces = []
        if tc: pieces.append(f"{tc} får trippel poeng")
        regular_c = max(0, cap - tc)
        if regular_c: pieces.append(f"{regular_c} får dobbelt")
        if normal: pieces.append(f"{normal} får vanlige poeng")
        if no_own: pieces.append(f"{no_own} har ham ikke")
        if pieces:
            v300_callout(f"Hvis {player} leverer", ". ".join(pieces) + ".")


def v300_player_search(ownership: dict | None, key: str = "v300_player_search"):
    players = ownership.get("players", pd.DataFrame()).copy() if ownership else pd.DataFrame()
    if players.empty:
        st.caption("Spillerdata er ikke tilgjengelig akkurat nå.")
        return
    query = st.text_input("Finn spiller", placeholder="Søk etter spiller …", key=key)
    if not query.strip():
        return
    q = normalize_text(query)
    matches = players[players.apply(lambda r: q in normalize_text(f"{r.get('player','')} {r.get('full_name','')} {r.get('club','')}"), axis=1)].copy()
    if matches.empty:
        st.caption("Fant ingen spiller.")
        return
    matches = matches.sort_values(["ownership_count","season_points"], ascending=[False,False]).head(15)
    if len(matches) == 1:
        row = matches.iloc[0]
    else:
        elements = matches["element"].astype(int).tolist()
        label_map = {v300_num(r.element): f"{r.player} · {r.club}" for r in matches.itertuples()}
        chosen = st.selectbox("Treff", elements, format_func=lambda e: label_map.get(v300_num(e), str(e)), key=f"{key}_result")
        row = matches[matches["element"] == int(chosen)].iloc[0]
    v300_section(str(row.get("player") or ""))
    v300_player_profile(row, ownership)


def v300_popular(ownership: dict | None, limit: int = 10):
    players = ownership.get("players", pd.DataFrame()).copy() if ownership else pd.DataFrame()
    if players.empty:
        st.caption("Ingen eierskapsdata ennå.")
        return
    loaded = max(1, v300_num(ownership.get("loaded_managers")))
    players = players.sort_values(["ownership_count","captain_count","season_points","player"], ascending=[False,False,False,True]).head(limit)
    rows = []
    for i, (_, r) in enumerate(players.iterrows(), 1):
        own = v300_num(r.get("ownership_count")); pct = own / loaded * 100
        rows.append({"rank": i, "who": str(r.get("player","")), "meta": str(r.get("club","")), "num": f"{own}/{loaded} · {pct:.0f}%"})
    v300_rows(rows)


def v300_differentials(ownership: dict | None, limit: int = 6):
    if not ownership:
        return
    players = ownership.get("players", pd.DataFrame()).copy()
    if players.empty:
        return
    pool = v300_player_pool("Neste 3 GW")
    if pool.empty:
        return
    df = players.merge(pool[["element","quality","fixtures","status","chance"]], on="element", how="left")
    df = df[(pd.to_numeric(df["ownership_count"], errors="coerce").fillna(0).between(1, 8)) & (pd.to_numeric(df["quality"], errors="coerce").fillna(0) > 1.5)].copy()
    if df.empty:
        st.caption("Ingen tydelige differensialer akkurat nå.")
        return
    df = df.sort_values(["quality","event_points","ownership_count"], ascending=[False,False,True]).head(limit)
    rows = []
    for _, r in df.iterrows():
        rows.append({"rank":"", "who":str(r.get("player","")), "meta":str(r.get("fixtures") or r.get("club") or ""), "num":f"{v300_num(r.get('ownership_count'))} eiere"})
    v300_rows(rows)


def v300_round_movement(managers: list[dict]):
    df = v300_manager_frame(managers)
    if df.empty:
        return
    rows = []
    gw = df.sort_values(["event_num","rank_num"], ascending=[False,True], na_position="last").iloc[0]
    rows.append({"rank":"GW", "who":str(gw.get("player_name","")), "meta":"Best denne runden", "num":f"{v300_num(gw.get('event_num'))} p"})
    movers = df[df["movement"].notna()]
    if not movers.empty:
        up = movers.sort_values(["movement","rank_num"], ascending=[False,True]).iloc[0]
        down = movers.sort_values(["movement","rank_num"], ascending=[True,True]).iloc[0]
        if v300_num(up.get("movement")) > 0:
            rows.append({"rank":"↑", "who":str(up.get("player_name","")), "meta":"Største klatrer", "num":f"+{v300_num(up.get('movement'))}", "num_class":"v300-up"})
        if v300_num(down.get("movement")) < 0:
            rows.append({"rank":"↓", "who":str(down.get("player_name","")), "meta":"Største fall", "num":str(v300_num(down.get("movement"))), "num_class":"v300-down"})
    v300_rows(rows)


def v300_stories(managers: list[dict], ownership: dict | None) -> list[tuple[str,str]]:
    stories = []
    if ownership:
        players = ownership.get("players", pd.DataFrame()).copy()
        if not players.empty:
            tc = players[pd.to_numeric(players.get("triple_captain_count"), errors="coerce").fillna(0) > 0]
            for _, r in tc.head(2).iterrows():
                names = [canonical_hof_name(x.strip()) for x in str(r.get("triple_captains_text") or "").split(" · ") if x.strip()]
                if names:
                    stories.append(("hot", f"{', '.join(names)} har Triple Captain på {r.get('player','')}."))
            most = players.sort_values(["ownership_count","captain_count"], ascending=[False,False]).iloc[0]
            loaded = v300_num(ownership.get("loaded_managers"))
            if loaded:
                missing = loaded - v300_num(most.get("ownership_count"))
                stories.append(("", f"Bare {missing} av {loaded} går uten {most.get('player','')}."))
    df = v300_manager_frame(managers)
    movers = df[df["movement"].notna()] if not df.empty else pd.DataFrame()
    if not movers.empty:
        up = movers.sort_values(["movement","rank_num"], ascending=[False,True]).iloc[0]
        down = movers.sort_values(["movement","rank_num"], ascending=[True,True]).iloc[0]
        if v300_num(up.get("movement")) >= 5:
            stories.append(("up", f"{up.get('player_name','')} klatret {v300_num(up.get('movement'))} plasser."))
        if v300_num(down.get("movement")) <= -5:
            stories.append(("down", f"{down.get('player_name','')} falt {abs(v300_num(down.get('movement')))} plasser."))
    return stories[:4]


def v300_story_list(stories: list[tuple[str,str]]):
    if not stories:
        st.caption("Rolig i Lofthus akkurat nå.")
        return
    bits = []
    marks = {"hot":"!", "up":"↑", "down":"↓", "":"•"}
    for tone, text in stories:
        bits.append(f"<div class='v300-story'><div class='v300-story-mark {tone}'>{marks.get(tone,'•')}</div><div>{html.escape(text)}</div></div>")
    st.markdown("<div class='v300-stories'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def v300_league_table(managers: list[dict]):
    df = v300_manager_frame(managers)
    if df.empty:
        st.caption("Ingen ligatabell ennå.")
        return
    df = df[df["rank_num"].notna()].sort_values(["rank_num","total_num","player_name"], ascending=[True,False,True])
    body = []
    for _, r in df.iterrows():
        rank = v300_num(r.get("rank_num")); cls = "one" if rank == 1 else "two" if rank == 2 else "three" if rank == 3 else ""
        move = "–"; mcls = ""
        if not pd.isna(r.get("movement")):
            m = v300_num(r.get("movement"))
            if m > 0: move, mcls = f"↑ {m}", "v300-up"
            elif m < 0: move, mcls = f"↓ {abs(m)}", "v300-down"
        body.append(f"<tr><td class='col-place'><span class='v300-place {cls}'>{rank}</span></td><td class='col-manager'><span class='strong'>{html.escape(str(r.get('player_name','')))}</span><span class='muted'>{html.escape(str(r.get('entry_name','')))}</span></td><td class='col-team'>{html.escape(str(r.get('entry_name','')))}</td><td class='right col-gw'>{v300_num(r.get('event_num'))}</td><td class='right strong col-points'>{v300_num(r.get('total_num'))}</td><td class='right col-move {mcls}'>{move}</td></tr>")
    st.markdown("<div class='v300-table-wrap'><table class='v300-table'><thead><tr><th class='col-place'>#</th><th class='col-manager'>Manager</th><th class='col-team'>Lag</th><th class='right col-gw'>GW</th><th class='right col-points'>Poeng</th><th class='right col-move'>Endring</th></tr></thead><tbody>" + "".join(body) + "</tbody></table></div>", unsafe_allow_html=True)


def v300_manager_merits(name: str) -> dict:
    hof = build_hof_people()
    if hof.empty:
        return {}
    hit = hof[hof["display_name"].map(hof_key) == hof_key(name)]
    return hit.iloc[0].to_dict() if not hit.empty else {}


def v300_manager_form(entry: int) -> pd.DataFrame:
    try:
        hist = get_entry_history(int(entry))
        df = pd.DataFrame(hist.get("current", []) or [])
        if df.empty:
            return df
        return df.tail(5).copy()
    except Exception:
        return pd.DataFrame()


def v300_render_form(entry: int):
    df = v300_manager_form(entry)
    if df.empty:
        st.caption("Ingen formdata ennå.")
        return
    bits = []
    for r in df.itertuples():
        bits.append(f"<div class='v300-form-item'><div class='v300-form-gw'>GW{v300_num(getattr(r,'event',0))}</div><div class='v300-form-points'>{v300_num(getattr(r,'points',0))} p</div></div>")
    st.markdown("<div class='v300-form'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def v300_render_merits(name: str):
    m = v300_manager_merits(name)
    if not m:
        st.caption("Ingen registrerte meritter ennå.")
        return
    items = [
        (v300_num(m.get("overall_count")), "ligagull"),
        (v300_num(m.get("overall_runner_up_count")), "seriesølv"),
        (v300_num(m.get("overall_third_count")), "seriebronse"),
        (v300_num(m.get("cup_count")), "cupgull"),
        (v300_num(m.get("monthly_titles")), "månedsseire"),
    ]
    bits = [f"<div class='v300-merit'><strong>{value}</strong><span>{html.escape(label)}</span></div>" for value, label in items if value > 0]
    if bits:
        st.markdown("<div class='v300-merits'>" + "".join(bits) + "</div>", unsafe_allow_html=True)
    else:
        st.caption("Ingen registrerte medaljer ennå.")


def v300_current_month_rank(name: str) -> str:
    phase, df = get_current_month_table(DEFAULT_LEAGUE_ID)
    if not phase or df.empty:
        return "–"
    hit = df[df["manager"].map(hof_key) == hof_key(name)]
    if hit.empty:
        return "–"
    r = hit.iloc[0]
    return f"{v300_num(r.get('rank'))}. · {v300_num(r.get('points'))} p"


def v300_squad_for_entry(entry: int, ownership: dict | None) -> pd.DataFrame:
    if not ownership:
        return pd.DataFrame()
    picks = ownership.get("picks", pd.DataFrame()).copy()
    if picks.empty:
        return picks
    mine = picks[picks["entry"] == int(entry)].copy()
    if mine.empty:
        return mine
    meta = v300_bootstrap_players()[["element","price","position","position_id","club"]].copy()
    for c in ["price","position","position_id","club"]:
        if c in mine.columns:
            mine = mine.drop(columns=[c])
    mine = mine.merge(meta, on="element", how="left")
    return mine.sort_values(["on_bench","position_id","squad_position"], ascending=[True,True,True])


def v300_render_squad(entry: int, ownership: dict | None):
    mine = v300_squad_for_entry(entry, ownership)
    if mine.empty:
        st.caption("Troppen er ikke tilgjengelig akkurat nå.")
        return
    bits = []
    for _, r in mine.iterrows():
        role = []
        if bool(r.get("is_captain")):
            role.append("TC" if v300_num(r.get("multiplier")) >= 3 else "C")
        elif bool(r.get("is_vice_captain")):
            role.append("VC")
        if bool(r.get("on_bench")):
            role.append("Benk")
        meta = f"{r.get('position','')} · {v300_price(r.get('price'))}"
        if role:
            meta += " · " + " · ".join(role)
        meta += f" · {v300_num(r.get('event_points'))} p"
        cls = " v300-bench" if bool(r.get("on_bench")) else ""
        bits.append(f"<div class='v300-squad-row{cls}'><span class='v300-squad-name'>{html.escape(str(r.get('player','')))}</span><span class='v300-squad-meta'>{html.escape(meta)}</span></div>")
    st.markdown("<div class='v300-squad'>" + "".join(bits) + "</div>", unsafe_allow_html=True)


def v300_history_prior(managers: list[dict]) -> dict[int, float]:
    try:
        ensure_history_for_page()
        summary = st.session_state.get("summary_df", pd.DataFrame())
        if summary.empty:
            return {}
        odds = build_preseason_odds(summary)
        if odds.empty or "entry" not in odds.columns:
            return {}
        odds = odds.sort_values("odds_float").reset_index(drop=True)
        n = max(1, len(odds) - 1)
        return {v300_num(r.entry): 1.0 - i / n for i, r in enumerate(odds.itertuples()) if v300_num(r.entry)}
    except Exception:
        return {}


def v300_model_inputs(managers: list[dict], ownership: dict | None, need_history: bool = True) -> pd.DataFrame:
    """Bygg styrkegrunnlag for oddsmodellen.

    Tidlig i sesongen får dokumentert FPL-historikk en tydelig prior. Etter hvert
    overtar inneværende sesong: poengsnitt, siste fem, lagverdi og kvaliteten i
    den faktiske troppen. Dette er et praktisk modellanslag, ikke kalibrerte odds.
    """
    df = v300_manager_frame(managers)
    if df.empty:
        return df
    current = max(1, v300_num(current_fpl_event_id(), 1))
    df["season_avg"] = df["total_num"] / current
    league_avg = v300_float(df["season_avg"].median(), 50)
    df["recent5"] = df["event_num"].where(df["event_num"] > 0, df["season_avg"])

    priors = v300_history_prior(managers) if need_history else {}
    df["hist_prior"] = df["entry"].map(lambda e: priors.get(v300_num(e), .5))

    # Når historikk allerede er hentet for odds, er get_entry_history cachet.
    # Da får modellen reell form siste fem uten nye 63 nettverksrunder.
    if need_history:
        recent_map = {}
        for m in managers:
            entry = v300_num(m.get("entry"))
            if not entry:
                continue
            try:
                current_rows = pd.DataFrame((get_entry_history(entry) or {}).get("current", []) or [])
                pts = pd.to_numeric(current_rows.tail(5).get("points"), errors="coerce").dropna() if not current_rows.empty else pd.Series(dtype=float)
                if len(pts):
                    recent_map[entry] = float(pts.mean())
            except Exception:
                pass
        if recent_map:
            df["recent5"] = df.apply(lambda r: recent_map.get(v300_num(r.get("entry")), v300_float(r.get("recent5"))), axis=1)

    hist_weight = max(.04, min(.55, (12 - current) / 12))
    df["mean_gw"] = .48 * df["season_avg"] + .34 * pd.to_numeric(df["recent5"], errors="coerce").fillna(df["season_avg"]) + .18 * league_avg
    df["mean_gw"] += (df["hist_prior"] - .5) * 9.0 * hist_weight

    events = ownership.get("manager_events", pd.DataFrame()).copy() if ownership else pd.DataFrame()
    if not events.empty:
        extra_cols = [c for c in ["entry","value","event_transfers_cost","points_on_bench"] if c in events.columns]
        extras = events[extra_cols].copy()
        if "value" in extras.columns:
            extras["value"] = pd.to_numeric(extras["value"], errors="coerce") / 10.0
        df = df.merge(extras, on="entry", how="left")
        if "value" in df.columns:
            med = pd.to_numeric(df["value"], errors="coerce").median()
            if not pd.isna(med):
                df["mean_gw"] += (pd.to_numeric(df["value"], errors="coerce").fillna(med) - med) * .18

        # Den faktiske 15-mannstroppen og kapteinen gir en liten framoverskuende
        # justering. Fem-GW-vinduet gjør at fint program og form får betydning.
        picks = ownership.get("picks", pd.DataFrame()).copy()
        try:
            pool = v300_player_pool("Neste 5 GW")[["element","quality"]].copy()
        except Exception:
            pool = pd.DataFrame()
        if not picks.empty and not pool.empty:
            q = picks.merge(pool, on="element", how="left")
            q["quality"] = pd.to_numeric(q["quality"], errors="coerce").fillna(0)
            squad = q.groupby("entry", as_index=False).agg(squad_quality=("quality","mean"))
            caps = q[q["is_captain"]].groupby("entry", as_index=False).agg(captain_quality=("quality","mean"))
            squad = squad.merge(caps, on="entry", how="left")
            df = df.merge(squad, on="entry", how="left")
            sq_med = pd.to_numeric(df.get("squad_quality"), errors="coerce").median()
            if not pd.isna(sq_med):
                df["mean_gw"] += (pd.to_numeric(df.get("squad_quality"), errors="coerce").fillna(sq_med) - sq_med) * .65
            cap_med = pd.to_numeric(df.get("captain_quality"), errors="coerce").median()
            if not pd.isna(cap_med):
                df["mean_gw"] += (pd.to_numeric(df.get("captain_quality"), errors="coerce").fillna(cap_med) - cap_med) * .18
    return df


def v300_simulate_league(managers: list[dict], ownership: dict | None, need_history: bool = True, sims: int = 6000) -> pd.DataFrame:
    df = v300_model_inputs(managers, ownership, need_history=need_history)
    if df.empty:
        return df
    current = max(1, v300_num(current_fpl_event_id(), 1))
    max_event = max([v300_num(e.get("id")) for e in get_bootstrap_static().get("events", []) or []] or [38])
    remaining = max(0, max_event - current)
    n = len(df)
    if remaining == 0:
        order = np.argsort(-df["total_num"].to_numpy())
        win = np.zeros(n); top3 = np.zeros(n); top10 = np.zeros(n)
        if n: win[order[0]] = 1
        top3[order[:min(3,n)]] = 1; top10[order[:min(10,n)]] = 1
    else:
        rng = np.random.default_rng(DEFAULT_LEAGUE_ID + current * 100)
        means = df["total_num"].to_numpy(dtype=float) + df["mean_gw"].to_numpy(dtype=float) * remaining
        sd = 10.5 * math.sqrt(max(1, remaining))
        samples = rng.normal(means, sd, size=(sims, n))
        winners = np.argmax(samples, axis=1)
        win = np.bincount(winners, minlength=n) / sims
        top3 = np.zeros(n); top10 = np.zeros(n)
        k3, k10 = min(3,n), min(10,n)
        idx3 = np.argpartition(samples, -k3, axis=1)[:, -k3:]
        idx10 = np.argpartition(samples, -k10, axis=1)[:, -k10:]
        for j in range(n):
            top3[j] = np.mean(np.any(idx3 == j, axis=1))
            top10[j] = np.mean(np.any(idx10 == j, axis=1))
    out = df[["entry","player_name","entry_name","rank_num","total_num","mean_gw"]].copy()
    out["win_pct"] = win * 100; out["top3_pct"] = top3 * 100; out["top10_pct"] = top10 * 100
    return out.sort_values(["win_pct","top3_pct","total_num"], ascending=[False,False,False]).reset_index(drop=True)


def v300_group_simulation(managers: list[dict], ownership: dict | None, entries: list[int], period: str, need_history: bool = True, sims: int = 5000) -> pd.DataFrame:
    base = v300_model_inputs(managers, ownership, need_history=need_history)
    if base.empty or not entries:
        return pd.DataFrame()
    base = base[base["entry"].astype(int).isin([int(e) for e in entries])].copy()
    if base.empty:
        return base
    current = max(1, v300_num(current_fpl_event_id(), 1))
    max_event = max([v300_num(e.get("id")) for e in get_bootstrap_static().get("events", []) or []] or [38])
    if period in {"Neste GW","Neste 3 GW","Neste 5 GW"}:
        horizon = {"Neste GW":1,"Neste 3 GW":3,"Neste 5 GW":5}[period]
        start_points = np.zeros(len(base))
    elif period == "Resten av måneden":
        phase, month = get_current_month_table(DEFAULT_LEAGUE_ID)
        stop = v300_num((phase or {}).get("stop_event"), current)
        horizon = max(1, stop - current)
        lookup = {hof_key(str(r.manager)): v300_num(r.points) for r in month.itertuples()} if not month.empty else {}
        start_points = np.array([lookup.get(hof_key(str(n)), 0) for n in base["player_name"].tolist()], dtype=float)
    else:
        horizon = max(1, max_event - current)
        start_points = base["total_num"].to_numpy(dtype=float)
    rng = np.random.default_rng(DEFAULT_LEAGUE_ID + current * 71 + len(base))
    means = start_points + base["mean_gw"].to_numpy(dtype=float) * horizon
    samples = rng.normal(means, 10.5 * math.sqrt(max(1,horizon)), size=(sims, len(base)))
    wins = np.argmax(samples, axis=1)
    probs = np.bincount(wins, minlength=len(base)) / sims * 100
    out = base[["entry","player_name"]].copy(); out["chance"] = probs
    return out.sort_values("chance", ascending=False).reset_index(drop=True)


def v300_odds_rows(model: pd.DataFrame, entries: list[int] | None = None):
    if model.empty:
        st.caption("Modellen har ikke nok data ennå.")
        return
    view = model.copy()
    if entries is not None:
        view = view[view["entry"].astype(int).isin([int(e) for e in entries])]
    bits = ["<div class='v300-odds-row head'><div>Manager</div><div>Gull</div><div>Topp 3</div><div>Topp 10</div></div>"]
    for _, r in view.iterrows():
        bits.append(f"<div class='v300-odds-row'><div class='v300-odds-name'>{html.escape(str(r.get('player_name','')))}</div><div>{v300_pct(r.get('win_pct'))}</div><div>{v300_pct(r.get('top3_pct'))}</div><div>{v300_pct(r.get('top10_pct'))}</div></div>")
    st.markdown("<div class='v300-odds'>" + "".join(bits) + "</div>", unsafe_allow_html=True)
    st.caption("Modellens anslag. Historikk veier mest tidlig i sesongen; inneværende sesong tar gradvis over.")


def v300_manager_profile(entry: int, managers: list[dict], ownership: dict | None):
    manager = next((m for m in managers if v300_num(m.get("entry")) == int(entry)), None)
    if not manager:
        return
    name = canonical_hof_name(str(manager.get("player_name") or "Ukjent manager")); team = str(manager.get("entry_name") or "")
    rank, total = v300_num(manager.get("rank")), v300_num(manager.get("total"))
    st.markdown(f"<div class='v300-profile'><div><div class='v300-profile-name'>{html.escape(name)}</div><div class='v300-profile-team'>{html.escape(team)}</div></div><div class='v300-profile-rank'><strong>{rank if rank else '–'}.</strong><span>{total} poeng</span></div></div>", unsafe_allow_html=True)
    v300_statbar([(f"{v300_num(manager.get('event_total'))} p","GW"),(v300_current_month_rank(name),"måneden"),(f"{total} p","totalt")])

    v300_section("Form")
    v300_render_form(int(entry))
    v300_section("Meritter")
    v300_render_merits(name)

    if ownership:
        events = ownership.get("manager_events", pd.DataFrame()).copy()
        ev = events[events["entry"] == int(entry)] if not events.empty else pd.DataFrame()
        if not ev.empty:
            chip = v200_chip_label(ev.iloc[0].get("active_chip")) or "Ingen"
            bank = v300_float(ev.iloc[0].get("bank")) / 10.0 if "bank" in ev.columns else 0.0
            value = v300_float(ev.iloc[0].get("value")) / 10.0 if "value" in ev.columns else 0.0
            extras = [(chip,"chip")]
            if value: extras.append((v300_price(value),"lagverdi"))
            if bank: extras.append((v300_price(bank),"i banken"))
            v300_statbar(extras)
    v300_section("Troppen")
    v300_render_squad(int(entry), ownership)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Åpne i Rivalradaren", key=f"v300_to_rivals_{entry}", use_container_width=True):
            st.session_state["v300_me"] = int(entry)
            st.session_state["v300_main_page"] = "Rivalradar"
            st.rerun()
    with c2:
        show_odds = st.toggle("Vis odds", key=f"v300_manager_odds_{entry}")
    if show_odds:
        with st.spinner("Regner på sjansene …"):
            model = v300_simulate_league(managers, ownership, need_history=True)
        hit = model[model["entry"].astype(int) == int(entry)] if not model.empty else pd.DataFrame()
        if not hit.empty:
            r = hit.iloc[0]
            all_entries = [v300_num(m.get("entry")) for m in managers if v300_num(m.get("entry"))]
            month_name = str((current_month_phase(get_bootstrap_static()) or {}).get("name") or "Måneden")
            month_chances = v300_group_simulation(managers, ownership, all_entries, "Resten av måneden", need_history=True, sims=5000)
            mh = month_chances[month_chances["entry"].astype(int) == int(entry)] if not month_chances.empty else pd.DataFrame()
            month_pct = v300_float(mh.iloc[0].get("chance")) if not mh.empty else 0.0
            v300_section("Modellens anslag")
            v300_statbar([
                (f"{v300_pct(r.get('win_pct'))} · {v300_decimal_odds(r.get('win_pct'))}","ligagull · odds"),
                (f"{v300_pct(r.get('top3_pct'))} · {v300_decimal_odds(r.get('top3_pct'))}","topp 3 · odds"),
                (f"{v300_pct(month_pct)} · {v300_decimal_odds(month_pct)}",f"{month_name} · odds"),
            ])
            st.caption("Et modellanslag, ikke en fasit. Historikk betyr mest tidlig; sesongdata betyr mer for hver runde.")


def v300_multi_compare(managers: list[dict], ownership: dict | None):
    if not ownership:
        st.caption("Lagene kan sammenlignes når picks er tilgjengelige.")
        return
    picks = ownership.get("picks", pd.DataFrame()).copy()
    if picks.empty:
        return
    mgr = picks[["entry","manager"]].drop_duplicates().sort_values("manager")
    labels = {v300_num(r.entry): str(r.manager) for r in mgr.itertuples()}; ids = list(labels)
    default = ids[:2]
    selected = st.multiselect("Velg 2–8 managere", ids, default=default, format_func=lambda e: labels.get(v300_num(e),str(e)), max_selections=8, key="v300_compare_entries")
    if len(selected) < 2:
        st.caption("Velg minst to managere.")
        return
    period = st.selectbox("Sammenlign", ["Denne GW","Resten av måneden","Sesongen"], key="v300_compare_period")
    events = ownership.get("manager_events", pd.DataFrame()).copy()
    month_phase, month_df = get_current_month_table(DEFAULT_LEAGUE_ID)
    month_lookup = {hof_key(str(r.manager)): v300_num(r.points) for r in month_df.itertuples()} if not month_df.empty else {}
    persons = []
    for e in selected:
        name = labels[int(e)]
        ev = events[events["entry"] == int(e)] if not events.empty else pd.DataFrame()
        gw = v300_num(ev.iloc[0].get("gw_points")) if not ev.empty else 0
        total = v300_num(ev.iloc[0].get("total_points")) if not ev.empty else 0
        score = gw if period == "Denne GW" else month_lookup.get(hof_key(name),0) if period == "Resten av måneden" else total
        cap = picks[(picks["entry"] == int(e)) & (picks["is_captain"])]
        cap_name = str(cap.iloc[0].get("player")) if not cap.empty else "–"
        tc = not cap.empty and v300_num(cap.iloc[0].get("multiplier")) >= 3
        persons.append((name, score, cap_name + (" · TC" if tc else "")))
    persons = sorted(persons, key=lambda x: x[1], reverse=True)
    bits = [f"<div class='v300-compare-person'><div class='v300-compare-name'>{html.escape(n)}</div><div class='v300-compare-score'>{s} p</div><div class='v300-compare-meta'>C: {html.escape(c)}</div></div>" for n,s,c in persons]
    st.markdown("<div class='v300-compare-grid'>"+"".join(bits)+"</div>", unsafe_allow_html=True)

    subset = picks[picks["entry"].isin([int(e) for e in selected])].copy()
    counts = subset.groupby(["element","player"], as_index=False)["entry"].nunique().rename(columns={"entry":"owners"})
    common = counts[counts["owners"] == len(selected)].sort_values("player")
    v300_section("Felles")
    if common.empty: st.caption("Ingen spillere er felles for alle.")
    else: st.write(" · ".join(common["player"].astype(str).tolist()))
    v300_section("Der de skiller seg")
    for e in selected:
        mine = subset[subset["entry"] == int(e)]
        unique = mine[~mine["element"].isin(common["element"])].sort_values(["is_captain","event_points"], ascending=[False,False])
        text = []
        for _, r in unique.iterrows():
            marker = " (TC)" if bool(r.get("is_captain")) and v300_num(r.get("multiplier")) >= 3 else " (C)" if bool(r.get("is_captain")) else ""
            text.append(str(r.get("player"))+marker)
        st.markdown(f"**{labels[int(e)]}:** " + (" · ".join(text) if text else "Ingen forskjeller"))

    event_id = current_fpl_event_id()
    if event_id:
        try:
            ctx = build_live_fixture_context(int(event_id)); active = ctx.get("active",[]) or []
        except Exception:
            active = []
        if active:
            active_ids = {v300_num(f.get(k)) for f in active for k in ("team_h","team_a")}
            live = subset[subset["team_id"].isin(active_ids)]
            if not live.empty:
                v300_section("Avgjør akkurat nå")
                live_counts = live.groupby(["element","player"],as_index=False).agg(owners=("entry","nunique"),points=("event_points","max"),captains=("is_captain","sum"))
                live_counts = live_counts.sort_values(["captains","owners","points"],ascending=[False,True,False]).head(8)
                v300_rows([{"rank":"", "who":str(r.player), "meta":f"{v300_num(r.owners)} av {len(selected)} har ham" + (f" · {v300_num(r.captains)} C" if v300_num(r.captains) else ""), "num":f"{v300_num(r.points)} p"} for r in live_counts.itertuples()])

    if st.toggle("Vis odds", key="v300_compare_odds"):
        odds_period = "Resten av måneden" if period == "Resten av måneden" else "Sesongen" if period == "Sesongen" else "Neste GW"
        with st.spinner("Regner …"):
            chances = v300_group_simulation(managers, ownership, [int(e) for e in selected], odds_period, need_history=True)
        v300_section("Modellens anslag")
        v300_rows([{"rank":i+1,"who":str(r.player_name),"meta":odds_period,"num":f"{v300_pct(r.chance)} · {v300_decimal_odds(r.chance)}"} for i,r in enumerate(chances.itertuples())])
        st.caption("Sjanse for å ende best av de valgte managerne i perioden.")


def v300_rival_base_tables(me: int, rivals: list[int], ownership: dict) -> dict:
    picks = ownership.get("picks", pd.DataFrame()).copy()
    players = ownership.get("players", pd.DataFrame()).copy()
    mine = picks[picks["entry"] == int(me)].copy()
    rp = picks[picks["entry"].isin([int(e) for e in rivals])].copy()
    my_ids = set(mine["element"].astype(int).tolist())
    rival_counts = rp.groupby(["element","player"],as_index=False)["entry"].nunique().rename(columns={"entry":"rival_owners"}) if not rp.empty else pd.DataFrame(columns=["element","player","rival_owners"])
    all_selected = set(rp["element"].astype(int).tolist()) | my_ids
    dangers = rival_counts[~rival_counts["element"].isin(my_ids)].copy() if not rival_counts.empty else rival_counts
    if not dangers.empty and not players.empty:
        dangers = dangers.merge(players[["element","ownership_count","season_points"]],on="element",how="left")
        dangers = dangers.sort_values(["rival_owners","season_points"],ascending=[False,False])
    mine_only = mine[~mine["element"].isin(set(rp["element"].astype(int).tolist()))].copy()
    common = mine[mine["element"].isin(set(rp["element"].astype(int).tolist()))].copy()
    return {"mine":mine,"rival_picks":rp,"dangers":dangers,"mine_only":mine_only,"common":common,"selected_ids":all_selected,"rival_counts":rival_counts}


def v300_rival_candidates(me: int, rivals: list[int], ownership: dict, period: str, risk: str, goal: str) -> pd.DataFrame:
    tables = v300_rival_base_tables(me, rivals, ownership)
    pool = v300_player_pool(period).copy()
    if pool.empty:
        return pool
    mine = tables["mine"]; my_ids = set(mine["element"].astype(int).tolist())
    rc = tables["rival_counts"]
    rival_map = dict(zip(rc["element"].astype(int), rc["rival_owners"].astype(int))) if not rc.empty else {}
    players = ownership.get("players", pd.DataFrame()).copy()
    lro_map = dict(zip(players["element"].astype(int), players["ownership_count"].astype(int))) if not players.empty else {}
    n_rivals = max(1,len(rivals))
    pool["rival_owners"] = pool["element"].map(lambda e: rival_map.get(v300_num(e),0))
    pool["rival_pct"] = pool["rival_owners"] / n_rivals
    pool["lro_owners"] = pool["element"].map(lambda e: lro_map.get(v300_num(e),0))
    pool["owned_by_me"] = pool["element"].isin(my_ids)
    aggression = {"Trygt":.2,"Balansert":.55,"Aggressivt":.9}.get(risk,.55)
    if goal in {"Ta igjen manageren foran","Vinn måneden"}: aggression = min(1.0, aggression + .12)
    if goal in {"Forsvar ledelsen"}: aggression = max(.05, aggression - .18)
    pool["attack_score"] = pool["quality"] + (1-pool["rival_pct"]) * (1.5 + 2.5*aggression) + (1-pool["selected_pct"].clip(0,100)/100)*.3
    pool["cover_score"] = pool["quality"] + pool["rival_pct"] * (2.0 + 2.0*(1-aggression))
    pool["safe_score"] = pool["quality"] + pool["rival_pct"]*.8 - (1-pool["availability"])*4
    pool["balanced_score"] = pool["quality"] + (1-pool["rival_pct"])*1.7 - (1-pool["availability"])*3
    pool["aggressive_score"] = pool["quality"] + (1-pool["rival_pct"])*3.2 - (1-pool["availability"])*2.5
    return pool


def v300_manager_budget(entry: int, ownership: dict | None) -> tuple[float, dict[int,float], float]:
    event_id = current_fpl_event_id()
    bank = 0.0; selling = {}; value = 0.0
    if event_id:
        try:
            payload = get_entry_event_picks(int(entry), int(event_id))
            hist = payload.get("entry_history") or {}
            bank = v300_float(hist.get("bank")) / 10.0
            value = v300_float(hist.get("value")) / 10.0
            for p in payload.get("picks",[]) or []:
                selling[v300_num(p.get("element"))] = v300_float(p.get("selling_price"), p.get("purchase_price")) / 10.0
        except Exception:
            pass
    return bank, selling, value


def v300_transfer_ideas(me: int, rivals: list[int], ownership: dict, period: str, risk: str, goal: str) -> list[dict]:
    pool = v300_rival_candidates(me,rivals,ownership,period,risk,goal)
    mine = v300_squad_for_entry(me, ownership)
    if pool.empty or mine.empty:
        return []
    bank, selling, _ = v300_manager_budget(me, ownership)
    club_counts = mine.groupby("team_id")["element"].nunique().to_dict() if "team_id" in mine.columns else {}
    # team_id may have been dropped by squad enrichment; recover it.
    if not club_counts:
        meta_team = v300_bootstrap_players().set_index("element")["team_id"].to_dict()
        club_counts = {}
        for e in mine["element"].astype(int):
            t = v300_num(meta_team.get(e)); club_counts[t] = club_counts.get(t,0)+1
    score_col = {"Trygt":"safe_score","Balansert":"balanced_score","Aggressivt":"aggressive_score"}.get(risk,"balanced_score")
    meta_idx = pool.set_index("element")
    suggestions = []
    for _, out in mine.iterrows():
        out_id = v300_num(out.get("element")); out_pos = v300_num(out.get("position_id")); out_price = selling.get(out_id, v300_float(out.get("price")))
        out_score = v300_float(meta_idx.loc[out_id, "quality"]) if out_id in meta_idx.index else 0.0
        budget = bank + out_price
        candidates = pool[(pool["position_id"] == out_pos) & (~pool["owned_by_me"]) & (pool["price"] <= budget + .001) & (pool["availability"] >= .45)].copy()
        for _, cand in candidates.iterrows():
            team = v300_num(cand.get("team_id")); out_team = v300_num(meta_idx.loc[out_id,"team_id"]) if out_id in meta_idx.index else 0
            count_after = club_counts.get(team,0) - (1 if team == out_team else 0)
            if count_after >= 3:
                continue
            improvement = v300_float(cand.get(score_col)) - out_score
            if improvement <= .15:
                continue
            suggestions.append({
                "out_element":out_id,"out_player":str(out.get("player","")),"out_price":out_price,
                "in_element":v300_num(cand.get("element")),"in_player":str(cand.get("player","")),"in_price":v300_float(cand.get("price")),
                "budget_after":budget-v300_float(cand.get("price")),"rival_owners":v300_num(cand.get("rival_owners")),"fixtures":str(cand.get("fixtures") or ""),
                "quality":v300_float(cand.get("quality")),"score":v300_float(cand.get(score_col)),"improvement":improvement,"news":str(cand.get("news") or ""),"chance":v300_float(cand.get("chance"),100),
            })
    suggestions = sorted(suggestions,key=lambda x:(x["improvement"],x["quality"]),reverse=True)
    out = []; used_in=set(); used_out=set()
    for s in suggestions:
        if s["in_element"] in used_in or s["out_element"] in used_out:
            continue
        out.append(s); used_in.add(s["in_element"]); used_out.add(s["out_element"])
        if len(out) >= 5: break
    return out


def v300_recommendation_block(title: str, df: pd.DataFrame, rivals_n: int, limit: int = 4, score_col: str = "attack_score"):
    if df.empty:
        st.caption("Ingen tydelige kandidater akkurat nå.")
        return
    for _, r in df.sort_values([score_col,"quality"],ascending=[False,False]).head(limit).iterrows():
        reasons = []
        ro = v300_num(r.get("rival_owners"))
        if ro == 0: reasons.append("Ingen av rivalene dine eier ham")
        elif ro == rivals_n: reasons.append("Alle rivalene dine eier ham")
        else: reasons.append(f"{ro} av {rivals_n} rivaler eier ham")
        if str(r.get("fixtures") or ""): reasons.append(f"Program: {r.get('fixtures')}")
        if v300_float(r.get("form")) >= 4: reasons.append(f"Form {v300_float(r.get('form')):.1f}")
        if v300_float(r.get("chance"),100) < 100: reasons.append(f"Spillesjanse {v300_float(r.get('chance')):.0f}%")
        st.markdown(f"<div class='v300-rec'><div class='v300-rec-head'><div><div class='v300-rec-name'>{html.escape(str(r.get('player','')))}</div><div class='v300-rec-meta'>{html.escape(str(r.get('club','')))} · {html.escape(str(r.get('position','')))} · {v300_price(r.get('price'))}</div></div><div class='v300-rec-score'>{html.escape(title)}</div></div><div class='v300-rec-reasons'>{html.escape(' · '.join(reasons[:4]))}</div></div>", unsafe_allow_html=True)


def v300_rivalradar(managers: list[dict]):
    v300_page_head("Rivalradar", "Finn trekk som faktisk kan hjelpe deg å slå de managerne du bryr deg om.")
    ownership = v300_get_ownership(managers)
    if not ownership:
        st.warning("FPL-lagene er ikke tilgjengelige akkurat nå.")
        return
    picks = ownership.get("picks", pd.DataFrame()).copy()
    if picks.empty:
        st.caption("Ingen picks tilgjengelig.")
        return
    mgr = picks[["entry","manager","rank"]].drop_duplicates().sort_values("manager")
    labels = {v300_num(r.entry):str(r.manager) for r in mgr.itertuples()}; ids=list(labels)
    if not ids: return
    if st.session_state.get("v300_me") not in ids:
        st.session_state["v300_me"] = ids[0]
    me = st.selectbox("Min manager", ids, index=ids.index(st.session_state["v300_me"]), format_func=lambda e:labels.get(v300_num(e),str(e)), key="v300_me_select")
    st.session_state["v300_me"] = int(me)
    my_rank_series = mgr[mgr["entry"] == int(me)]["rank"]
    my_rank = v300_num(my_rank_series.iloc[0]) if not my_rank_series.empty else 999
    default_rivals = mgr[mgr["entry"] != int(me)].assign(dist=lambda d:(pd.to_numeric(d["rank"],errors="coerce")-my_rank).abs()).sort_values(["dist","rank"]).head(3)["entry"].astype(int).tolist()
    rival_ids = [i for i in ids if i != int(me)]
    rivals = st.multiselect("Rivaler", rival_ids, default=[r for r in default_rivals if r in rival_ids], format_func=lambda e:labels.get(v300_num(e),str(e)), max_selections=8, key="v300_rivals")
    if not rivals:
        st.caption("Velg minst én rival.")
        return
    c1,c2,c3=st.columns(3)
    with c1: period=st.selectbox("Periode",["Neste GW","Neste 3 GW","Neste 5 GW","Resten av måneden","Sesongen"],index=1,key="v300_rival_period")
    with c2: goal=st.selectbox("Mål",["Slå disse managerne","Vinn måneden","Kom topp 3","Ta igjen manageren foran","Forsvar ledelsen","Vinn ligaen"],key="v300_rival_goal")
    with c3: risk=st.selectbox("Risiko",["Trygt","Balansert","Aggressivt"],index=1,key="v300_rival_risk")

    tables = v300_rival_base_tables(int(me),[int(r) for r in rivals],ownership)
    mine = tables["mine"]; dangers=tables["dangers"]
    pool = v300_rival_candidates(int(me),[int(r) for r in rivals],ownership,period,risk,goal)
    selected_ids=tables["selected_ids"]
    none_owned = pool[(~pool["element"].isin(selected_ids)) & (pool["availability"] >= .6)].copy().sort_values(["attack_score","quality"],ascending=[False,False])

    my_mgr = next((m for m in managers if v300_num(m.get("entry")) == int(me)),{})
    my_total=v300_num(my_mgr.get("total")); rival_totals=[v300_num(next((m for m in managers if v300_num(m.get("entry"))==int(r)),{}).get("total")) for r in rivals]
    best_rival=max(rival_totals) if rival_totals else my_total
    gap=my_total-best_rival
    if gap >= 20:
        v300_callout("Du ligger foran", f"Du har {gap} poeng til gode på den sterkeste av de valgte rivalene. Det taler for litt mer kontroll enn gambling.", "green")
    elif gap <= -20:
        v300_callout("Du jager", f"Du er {abs(gap)} poeng bak den sterkeste av de valgte rivalene. Da kan forskjeller bli viktigere.", "red")

    left,right=st.columns(2,gap="large")
    with left:
        v300_section("De har – du mangler")
        if dangers.empty: st.caption("Dere har svært like tropper.")
        else:
            view=dangers.head(8)
            v300_rows([{"rank":"", "who":str(r.player), "meta":"Potensiell fare", "num":f"{v300_num(r.rival_owners)}/{len(rivals)} rivaler"} for r in view.itertuples()])
    with right:
        v300_section("Ingen av dere har")
        if none_owned.empty: st.caption("Ingen tydelige kandidater akkurat nå.")
        else:
            v300_rows([{"rank":"", "who":str(r.player), "meta":str(r.fixtures or r.club), "num":v300_price(r.price)} for r in none_owned.head(8).itertuples()])

    v300_section("Angrip")
    attack = pool[(~pool["owned_by_me"]) & (pool["rival_pct"] <= .5) & (pool["availability"] >= .6)].copy()
    v300_recommendation_block("Interessant",attack,len(rivals),4,"attack_score")

    v300_section("Dekk deg")
    cover = pool[(~pool["owned_by_me"]) & (pool["rival_pct"] >= .5) & (pool["availability"] >= .65)].copy()
    v300_recommendation_block("Fare",cover,len(rivals),4,"cover_score")

    risky = pool[(~pool["owned_by_me"]) & ((pool["availability"] < .5) | (pool["status"].isin(["i","s","u"])))].copy().sort_values(["selected_pct","quality"],ascending=[False,False])
    if not risky.empty:
        v300_section("Styr unna")
        for _, r in risky.head(3).iterrows():
            reason = str(r.get("news") or "Usikker spilletid")
            v300_callout(str(r.get("player","")), reason[:180], "red")

    v300_section("Beste trekk")
    ideas = v300_transfer_ideas(int(me),[int(r) for r in rivals],ownership,period,risk,goal)
    if not ideas:
        st.caption("Ingen tydelig én-for-én-transfer slår gjennom modellen akkurat nå.")
    else:
        for idx,s in enumerate(ideas[:3],1):
            text=f"{s['out_player']} → {s['in_player']} · {v300_price(s['in_price'])} · {s['rival_owners']}/{len(rivals)} rivaler eier innspilleren"
            if s["fixtures"]: text += f" · {s['fixtures']}"
            v300_callout(f"{idx}. {s['out_player']} → {s['in_player']}", text, "green" if idx==1 else "")
        st.caption("FPL-API gir ikke alltid et sikkert tall for framtidige gratisbytter. Eventuell hit er derfor ikke diktet inn i anbefalingen.")
        choices={f"{s['out_player']} → {s['in_player']}":s for s in ideas[:5]}
        chosen=st.selectbox("Hva om?",list(choices),key="v300_whatif")
        s=choices[chosen]
        old_overlap=v300_num(tables["rival_counts"][tables["rival_counts"]["element"]==s["out_element"]]["rival_owners"].iloc[0]) if not tables["rival_counts"].empty and not tables["rival_counts"][tables["rival_counts"]["element"]==s["out_element"]].empty else 0
        v300_statbar([(f"{old_overlap}/{len(rivals)}","rivaler har ut"),(f"{s['rival_owners']}/{len(rivals)}","rivaler har inn"),(v300_price(s["budget_after"]),"igjen i bank")])

    v300_section("Kapteinsradar")
    own_ids=set(mine["element"].astype(int).tolist()); own_pool=pool[pool["element"].isin(own_ids)].copy()
    if not own_pool.empty:
        safe=own_pool.sort_values(["safe_score","quality"],ascending=[False,False]).iloc[0]
        aggressive=own_pool.sort_values(["aggressive_score","quality"],ascending=[False,False]).iloc[0]
        v300_rows([
            {"rank":"T", "who":str(safe.get("player","")), "meta":"Tryggere kapteinsvalg", "num":str(safe.get("fixtures") or "")},
            {"rank":"A", "who":str(aggressive.get("player","")), "meta":"Mer offensivt kapteinsvalg", "num":str(aggressive.get("fixtures") or "")},
        ])

    if st.toggle("Vis odds", key="v300_rival_odds"):
        with st.spinner("Regner …"):
            chances=v300_group_simulation(managers,ownership,[int(me)]+[int(r) for r in rivals],period,need_history=True)
        v300_section("Modellens anslag")
        v300_rows([{"rank":i+1,"who":str(r.player_name),"meta":period,"num":f"{v300_pct(r.chance)} · {v300_decimal_odds(r.chance)}"} for i,r in enumerate(chances.itertuples())])
        mine_chance=chances[chances["entry"].astype(int)==int(me)] if not chances.empty else pd.DataFrame()
        if not mine_chance.empty:
            st.caption(f"Din anslåtte sjanse til å ende best av denne gruppen i perioden: {v300_pct(mine_chance.iloc[0]['chance'])}.")
        st.caption("Dette er et beslutningsverktøy, ikke en spåkule.")


def v300_home(managers: list[dict]):
    ownership = v300_get_ownership(managers)
    live = v300_live_section(managers, ownership, compact=True)
    df = v300_manager_frame(managers)
    if not df.empty:
        leader = df.sort_values(["rank_num","total_num"],ascending=[True,False],na_position="last").iloc[0]
        gwbest = df.sort_values(["event_num","rank_num"],ascending=[False,True],na_position="last").iloc[0]
        month_name, month, zero = v300_month_table(managers,3)
        month_leader = str(month.iloc[0]["manager"]) if not month.empty else "–"
        cap = v300_captain_frame(ownership)
        cap_name = str(cap.iloc[0]["player"]) if not cap.empty else "–"
        cap_count = v300_num(cap.iloc[0]["captain_count"]) if not cap.empty else 0
        v300_statbar([(str(leader.get("player_name","–")),"ligaleder"),(f"{gwbest.get('player_name','–')} · {v300_num(gwbest.get('event_num'))} p","runden"),(month_leader,month_name),(f"{cap_name} · {cap_count} C","mest cappet")])
    v300_section("Snakkiser")
    v300_story_list(v300_stories(managers,ownership))
    left,right=st.columns([1.15,.85],gap="large")
    with left:
        v300_section("Topp 5")
        top=df.sort_values(["rank_num","total_num"],ascending=[True,False],na_position="last").head(5) if not df.empty else pd.DataFrame()
        v300_rows([{"rank":v300_num(r.rank_num),"who":str(r.player_name),"meta":str(r.entry_name),"num":f"{v300_num(r.total_num)} p"} for r in top.itertuples()])
    with right:
        month_name,_,_=v300_month_table(managers,3)
        v300_section(month_name)
        v300_month_podium(managers,3)


def v300_season(managers: list[dict]):
    v300_page_head("Sesong", "Live, kapteiner, spillere og det som faktisk flytter ligaen.")
    ownership = v300_get_ownership(managers)
    v300_live_section(managers,ownership,compact=False)
    v300_section("Hvem har cappet hvem?")
    v300_captains(ownership,8)
    c1,c2=st.columns([.9,1.1],gap="large")
    with c1:
        v300_section("Mest eide")
        v300_popular(ownership,10)
    with c2:
        v300_section("Finn spiller")
        v300_player_search(ownership,"v300_season_player")
    v300_section("Differensialer")
    v300_differentials(ownership,6)
    name,_,_=v300_month_table(managers,3)
    v300_section(name)
    v300_month_podium(managers,3)
    v300_section("Rundebevegelser")
    v300_round_movement(managers)
    with st.expander("Mer statistikk"):
        st.markdown("#### Sesongutvikling")
        try:
            render_round_by_round_league_history(managers)
        except Exception:
            st.caption("Sesongutviklingen kunne ikke lastes akkurat nå.")


def v300_league(managers: list[dict]):
    v300_page_head("Ligaen", "Tabell, managerprofiler og kampen mellom flere managere.")
    view=v300_nav(["Tabell","Manager","Sammenlign"],"v300_league_view","Tabell")
    if view=="Tabell":
        v300_league_table(managers)
        return
    ownership=v300_get_ownership(managers)
    if view=="Manager":
        opts=sorted([(v300_num(m.get("entry")),canonical_hof_name(str(m.get("player_name") or ""))) for m in managers if m.get("entry")],key=lambda x:normalize_text(x[1]))
        ids=[x[0] for x in opts]; labels=dict(opts)
        if ids:
            selected=st.selectbox("Finn manager",ids,format_func=lambda e:labels.get(v300_num(e),str(e)),key="v300_manager_select")
            v300_manager_profile(int(selected),managers,ownership)
    elif view=="Sammenlign":
        v300_multi_compare(managers,ownership)


def v300_hof_table():
    hof=build_hof_people()
    if hof.empty:
        st.caption("Ingen historikk funnet.")
        return
    hof=hof.copy()
    hof["gold"] = pd.to_numeric(hof["overall_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["cup_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["monthly_titles"],errors="coerce").fillna(0)
    hof["silver"] = pd.to_numeric(hof["overall_runner_up_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["cup_runner_up_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["monthly_silver"],errors="coerce").fillna(0)
    hof["bronze"] = pd.to_numeric(hof["overall_third_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["monthly_bronze"],errors="coerce").fillna(0)
    hof=hof.sort_values(["gold","silver","bronze","display_name"],ascending=[False,False,False,True]).reset_index(drop=True)
    body=[]
    for i,r in hof.head(30).iterrows():
        rank=i+1; cls="one" if rank==1 else "two" if rank==2 else "three" if rank==3 else ""
        body.append(f"<tr><td class='col-place'><span class='v300-place {cls}'>{rank}</span></td><td class='strong'>{html.escape(str(r.get('display_name','')))}</td><td class='right'>{v300_num(r.get('gold'))}</td><td class='right'>{v300_num(r.get('silver'))}</td><td class='right'>{v300_num(r.get('bronze'))}</td></tr>")
    st.markdown("<div class='v300-table-wrap'><table class='v300-table'><thead><tr><th>#</th><th>Manager</th><th class='right'>Gull</th><th class='right'>Sølv</th><th class='right'>Bronse</th></tr></thead><tbody>"+"".join(body)+"</tbody></table></div>",unsafe_allow_html=True)


def v300_history(managers: list[dict]):
    v300_page_head("Historikk")
    view=v300_nav(["Hall of Fame","Månedsvinnere","Sesonger","Rekorder"],"v300_history_view","Hall of Fame")
    if view=="Hall of Fame":
        v300_hof_table()
    elif view=="Månedsvinnere":
        medals=build_monthly_medal_table("Alle")
        if medals.empty:
            st.caption("Ingen månedshistorikk.")
        else:
            top=medals.head(30)
            v300_rows([{"rank":v300_num(r.monthly_rank),"who":str(r.manager),"meta":f"{v300_num(r.podiums)} pallplasser","num":f"{v300_num(r.gold)} gull · {v300_num(r.silver)} sølv · {v300_num(r.bronze)} bronse"} for r in top.itertuples()])
            with st.expander("Måned for måned"):
                cal=build_monthly_calendar_table("Alle")
                display_table(cal,["season","month","winner","second_place","third_place"],MONTHLY_CALENDAR_LABELS)
    elif view=="Sesonger":
        v300_section("Sammenlagt")
        display_table(pd.DataFrame(HOF_OVERALL),["season","winner","runner_up","third_place"],OVERALL_LABELS)
        v300_section("Cup")
        display_table(pd.DataFrame(HOF_CUP),["season","winner","runner_up"],CUP_LABELS)
    else:
        hof=build_hof_people()
        if hof.empty:
            st.caption("Ingen rekorddata.")
            return
        gold=hof.sort_values(["overall_count","overall_runner_up_count","display_name"],ascending=[False,False,True]).iloc[0]
        month=hof.sort_values(["monthly_titles","monthly_silver","display_name"],ascending=[False,False,True]).iloc[0]
        cup=hof.sort_values(["cup_count","cup_runner_up_count","display_name"],ascending=[False,False,True]).iloc[0]
        podium=hof.assign(podiums=pd.to_numeric(hof["overall_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["overall_runner_up_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["overall_third_count"],errors="coerce").fillna(0)+pd.to_numeric(hof["monthly_podiums"],errors="coerce").fillna(0)).sort_values(["podiums","display_name"],ascending=[False,True]).iloc[0]
        v300_rows([
            {"rank":"1","who":str(gold.get("display_name","")),"meta":"Flest ligagull","num":str(v300_num(gold.get("overall_count")))},
            {"rank":"M","who":str(month.get("display_name","")),"meta":"Flest månedsseire","num":str(v300_num(month.get("monthly_titles")))},
            {"rank":"C","who":str(cup.get("display_name","")),"meta":"Flest cupgull","num":str(v300_num(cup.get("cup_count")))},
            {"rank":"P","who":str(podium.get("display_name","")),"meta":"Flest pallplasser","num":str(v300_num(podium.get("podiums")))},
        ])


# Best-effort sesongarkiv. Aldri la arkivet velte appen.
try:
    if st.session_state.get("managers"):
        persist_season_archive(st.session_state.get("managers", []))
except Exception:
    pass

managers = st.session_state.get("managers", [])
v300_header(managers)
MAIN_PAGES = ["Forside", "Sesong", "Ligaen", "Rivalradar", "Historikk"]
main_page = v300_nav(MAIN_PAGES, "v300_main_page", "Forside")

if not managers:
    st.warning("FPL-data er midlertidig utilgjengelig.")
elif main_page == "Forside":
    v300_home(managers)
elif main_page == "Sesong":
    v300_season(managers)
elif main_page == "Ligaen":
    v300_league(managers)
elif main_page == "Rivalradar":
    v300_rivalradar(managers)
elif main_page == "Historikk":
    v300_history(managers)
