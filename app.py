import math
import re
import unicodedata
import json
import html
from difflib import SequenceMatcher
from typing import Any
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    import pydeck as pdk
except ImportError:
    pdk = None


BASE_URL = "https://fantasy.premierleague.com/api"
DEFAULT_LEAGUE_ID = 25220
APP_VERSION = "lofthus-road-open-kontrollrom-v23-launch-tightening"

HEADERS = {"User-Agent": "Mozilla/5.0 Lofthus Road Open Kontrollrom"}

st.set_page_config(page_title="Lofthus Road Open - Kontrollrom", layout="wide")

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
            background:
                radial-gradient(circle at 92% 18%, rgba(251, 191, 36, 0.18), transparent 22%),
                linear-gradient(135deg, #0b1220 0%, #111827 52%, #7f1d1d 100%);
            border-radius: 24px;
            padding: 30px 34px;
            color: white;
            margin-bottom: 20px;
            box-shadow: 0 14px 36px rgba(15, 23, 42, 0.20);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .lro-hero h1 {
            font-size: clamp(2.2rem, 4.3vw, 4.1rem);
            line-height: 1.0;
            margin: 0;
            color: white;
            letter-spacing: -0.05em;
        }

        .lro-beta {
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

        @media (max-width: 760px) {
            .lro-hero {padding: 24px 22px; border-radius: 20px;}
            .lro-hero h1 {font-size: 2.4rem;}
            .lro-card-grid {grid-template-columns: 1fr;}
        }
    </style>
    <div class="lro-hero">
        <div class="lro-beta">Beta · lanseringsklar prototype</div>
        <h1>Lofthus Road Open</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Kontrollrom")
    st.caption(f"Liga-ID: {DEFAULT_LEAGUE_ID}")
    if st.session_state.get("last_updated"):
        st.caption(f"Sist hentet: {st.session_state['last_updated']}")
    if st.button("Oppdater fra FPL nå"):
        for cached_func in ["get_json", "get_entry_history", "get_league_managers"]:
            try:
                globals()[cached_func].clear()
            except Exception:
                pass
        st.session_state.clear()
        st.rerun()
    st.markdown("---")
    st.caption("Beta fram mot 1. august. Meld feil i gruppa, særlig på gamle meritter, navn og bosted.")


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
    "Kevin Jørgensen": ["Kevin Jørgensen", "Kevin Andre Dybfest Jørgensen"],
    "Mattias Pettersen": ["Mattias Pettersen", "Matias Pettersen"],
    "Oskar Brun": ["Oskar Brun", "Oskar Kristensen Brun"],
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

    monthly_titles = []
    merits = []
    hof_scores = []

    for _, row in summary_df.iterrows():
        key = hof_key(row["manager"])

        if key in hof_index.index:
            hof_row = hof_index.loc[key]
            monthly_titles.append(int(hof_row["monthly_titles"]))
            merits.append(hof_row["merits"])
            hof_scores.append(int(hof_row["hof_score"]))
        else:
            monthly_titles.append(0)
            merits.append("")
            hof_scores.append(0)

    summary_df = summary_df.copy()
    summary_df["monthly_titles"] = monthly_titles
    summary_df["merits"] = merits
    summary_df["hof_score"] = hof_scores

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


def build_preseason_odds(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()

    df = summary_df.copy()
    df["total_rating"] = pd.to_numeric(df["total_rating"], errors="coerce").fillna(0)

    n = max(len(df), 1)
    max_score = df["total_rating"].max()

    # Før-sesongodds i en privat FPL-liga skal ha mye varians.
    # Modellen bruker historisk styrke, men blander kraftig inn usikkerhet slik at
    # topp 3-markedet ikke blir kunstig lavt på halve feltet.
    temperature = 10.8
    skill_weights = ((df["total_rating"] - max_score) / temperature).apply(math.exp)
    skill_probs = skill_weights / skill_weights.sum()
    equal_probs = pd.Series([1 / n] * n, index=df.index)

    random_blend = 0.46
    win_probs = random_blend * equal_probs + (1 - random_blend) * skill_probs

    adj = pd.Series([1.0] * n, index=df.index)
    adj.loc[df["seasons"] <= 2] *= 0.94
    adj.loc[df["last_season_rank_num"].fillna(999_999_999) > 2_000_000] *= 0.94
    adj.loc[df["avg_rank_last_3_num"].fillna(999_999_999) > 1_500_000] *= 0.95
    adj.loc[df["top_100k_seasons"] >= 4] *= 1.04
    adj.loc[df["top_500k_seasons"] >= 10] *= 1.025

    if "hof_score" in df.columns:
        adj.loc[df["hof_score"] >= 60] *= 1.02
        adj.loc[df["monthly_titles"] >= 4] *= 1.01

    win_probs = win_probs * adj
    win_probs = win_probs / win_probs.sum()

    margin_win = 1.07
    df["odds_float"] = (1 / (win_probs * margin_win)).clip(lower=2.75, upper=251.00)
    df["odds"] = df["odds_float"].apply(format_odds)

    top3_probs = pd.Series(plackett_luce_top3_probs(win_probs.tolist()), index=df.index)
    margin_top3 = 1.06
    df["top3_odds_float"] = (1 / (top3_probs * margin_top3)).clip(lower=1.85, upper=101.00)
    df["top3_odds"] = df["top3_odds_float"].apply(format_odds)

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

    for _, row in table_df.reset_index(drop=True).iterrows():
        form_text, form_sort = form_curve_badge(row.get("form_delta"), big_threshold)
        rows.append({
            "rank": clean_cell(row.get("rank_display")),
            "rankValue": None if pd.isna(row.get("rank_num")) else float(row.get("rank_num")),
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
            <th data-key="eventPoints" class="sortable col-gw">Rundepoeng</th>
            <th data-key="totalPoints" class="sortable col-total">Poeng totalt</th>
            <th data-key="formSort" class="sortable">Formkurve</th>
          </tr>
        </thead>
        <tbody id="lro-table-body"></tbody>
      </table>
    </div>
    <style>
      .lro-table-wrap {{font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}}
      .lro-table-note {{font-size: 13px; color: #64748b; margin: 0 0 10px 0;}}
      .lro-table {{border-collapse: collapse; width: 100%; font-size: 14px; border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden;}}
      .lro-table th {{text-align: left; background: #f8fafc; color: #334155; padding: 12px 10px; border-bottom: 1px solid #e5e7eb; cursor: pointer; user-select: none; white-space: nowrap;}}
      .lro-table td {{padding: 11px 10px; border-bottom: 1px solid #eef2f7; color: #0f172a; vertical-align: top;}}
      .lro-table tr:hover td {{background: #fafafa;}}
      .lro-table .col-gw {{background: #eff6ff;}}
      .lro-table .col-total {{background: #fff7ed;}}
      .lro-table td.col-gw {{background: #dbeafe; font-weight: 800;}}
      .lro-table td.col-total {{background: #ffedd5; font-weight: 800;}}
      .rank-cell {{font-weight: 850; white-space: nowrap;}}
      .sort-mark {{margin-left: 6px; font-size: 11px; color: #b91c1c;}}
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

      function rankCell(row) {{
        const rankNumber = Number(row.rankValue);
        const medal = rankNumber === 1 ? '🥇 ' : rankNumber === 2 ? '🥈 ' : rankNumber === 3 ? '🥉 ' : '';
        const label = row.rank || '';
        return `<span class="rank-cell">${{medal}}${{esc(label)}}</span>`;
      }}

      function render() {{
        const sorted = [...rows].sort(compareRows);
        tbody.innerHTML = '';
        sorted.forEach((row) => {{
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${{rankCell(row)}}</td>
            <td><strong>${{esc(row.manager)}}</strong></td>
            <td>${{esc(row.team)}}</td>
            <td class="col-gw">${{fmtNum(row.eventPoints)}}</td>
            <td class="col-total">${{fmtNum(row.totalPoints)}}</td>
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
            "tag": clean_cell(row.get("tag")),
            "tagSort": 99 if pd.isna(row.get("tag_sort")) else int(row.get("tag_sort")),
        })

    rows_json = json.dumps(rows, ensure_ascii=False)
    component_html = f"""
    <div class="lro-table-wrap">
      <div class="lro-table-note">Trykk på kolonneoverskriftene for å sortere. Merknad sorteres i riktig intern rekkefølge.</div>
      <table class="lro-table lro-odds-table">
        <thead>
          <tr>
            <th data-key="rank" class="sortable">Odds-rangering</th>
            <th data-key="manager" class="sortable">Manager</th>
            <th data-key="team" class="sortable">Lagnavn</th>
            <th data-key="winOdds" class="sortable col-gw">Vinnerodds før sesongstart</th>
            <th data-key="top3Odds" class="sortable col-total">Topp 3-odds før sesongstart</th>
            <th data-key="avg3" class="sortable">Snitt siste tre sesonger</th>
            <th data-key="bestRank" class="sortable">Beste FPL-plassering</th>
            <th data-key="tagSort" class="sortable">Merknad</th>
          </tr>
        </thead>
        <tbody id="lro-odds-body"></tbody>
      </table>
    </div>
    <style>
      .lro-table-wrap {{font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}}
      .lro-table-note {{font-size: 13px; color: #64748b; margin: 0 0 10px 0;}}
      .lro-table {{border-collapse: collapse; width: 100%; font-size: 14px; border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden;}}
      .lro-table th {{text-align: left; background: #f8fafc; color: #334155; padding: 12px 10px; border-bottom: 1px solid #e5e7eb; cursor: pointer; user-select: none; white-space: nowrap;}}
      .lro-table td {{padding: 11px 10px; border-bottom: 1px solid #eef2f7; color: #0f172a; vertical-align: top;}}
      .lro-table tr:hover td {{background: #fafafa;}}
      .lro-table .col-gw {{background: #eff6ff;}}
      .lro-table .col-total {{background: #fff7ed;}}
      .lro-table td.col-gw {{background: #dbeafe; font-weight: 850;}}
      .lro-table td.col-total {{background: #ffedd5; font-weight: 850;}}
      .sort-mark {{margin-left: 6px; font-size: 11px; color: #b91c1c;}}
      .badge-tag {{display:inline-block; border-radius:999px; padding:3px 8px; background:#f1f5f9; color:#334155; font-weight:700; font-size:12px;}}
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
        const numericKeys = new Set(['rank','winOdds','top3Odds','avg3','bestRank','tagSort']);
        let av = a[sortKey]; let bv = b[sortKey];
        if (numericKeys.has(sortKey)) {{
          const am = av === null || av === undefined || Number.isNaN(av);
          const bm = bv === null || bv === undefined || Number.isNaN(bv);
          if (am && bm) return String(a.manager).localeCompare(String(b.manager), 'nb');
          if (am) return 1; if (bm) return -1;
          const diff = sortDir === 'asc' ? av - bv : bv - av;
          if (diff !== 0) return diff;
          if (sortKey === 'tagSort') return (a.winOdds || 999) - (b.winOdds || 999);
          return String(a.manager).localeCompare(String(b.manager), 'nb');
        }}
        av = String(av || '').toLowerCase(); bv = String(bv || '').toLowerCase();
        return sortDir === 'asc' ? av.localeCompare(bv, 'nb') : bv.localeCompare(av, 'nb');
      }}
      function render() {{
        const sorted = [...oddsRows].sort(compareRows); tbody.innerHTML = '';
        sorted.forEach(row => {{
          const tr = document.createElement('tr');
          tr.innerHTML = `<td><strong>${{fmtNum(row.rank)}}</strong></td><td><strong>${{esc(row.manager)}}</strong></td><td>${{esc(row.team)}}</td><td class="col-gw">${{fmtOdds(row.winOdds)}}</td><td class="col-total">${{fmtOdds(row.top3Odds)}}</td><td>${{fmtNum(row.avg3)}}</td><td>${{fmtNum(row.bestRank)}}</td><td><span class="badge-tag">${{esc(row.tag)}}</span></td>`;
          tbody.appendChild(tr);
        }});
        document.querySelectorAll('.lro-odds-table th.sortable').forEach(th => {{
          const key = th.getAttribute('data-key'); th.querySelectorAll('.sort-mark').forEach(s => s.remove());
          if (key === sortKey) {{ const span = document.createElement('span'); span.className = 'sort-mark'; span.textContent = sortDir === 'asc' ? '▲' : '▼'; th.appendChild(span); }}
        }});
      }}
      document.querySelectorAll('.lro-odds-table th.sortable').forEach(th => {{ th.addEventListener('click', () => {{ const key = th.getAttribute('data-key'); if (sortKey === key) {{ sortDir = sortDir === 'asc' ? 'desc' : 'asc'; }} else {{ sortKey = key; sortDir = (key === 'manager' || key === 'team' || key === 'tagSort') ? 'asc' : 'asc'; }} render(); }}); }});
      render();
    </script>
    """
    components.html(component_html, height=820, scrolling=True)




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
            "tag": clean_invisible(row.get("tag_display") or row.get("tag") or ""),
            "tagSort": 99 if pd.isna(row.get("tag_sort")) else int(row.get("tag_sort")),
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
          <th data-key="lastRank" class="sortable col-last">Plassering forrige sesong</th>
          <th data-key="bestRank" class="sortable col-best">Beste FPL-plassering gjennom tidene</th>
          <th data-key="avg3" class="sortable col-avg">Snitt siste tre sesonger</th>
          <th data-key="hofScore" class="sortable col-merit">Merittpoeng</th>
          <th data-key="merits" class="sortable">Meritter</th>
          <th data-key="tagSort" class="sortable">Merknad</th>
        </tr></thead>
        <tbody id="lro-history-body"></tbody>
      </table>
    </div>
    <style>
      .lro-history-wrap {{font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}}
      .lro-table-note {{font-size:13px;color:#64748b;margin:0 0 10px 0;}}
      .lro-table {{border-collapse:collapse;width:100%;font-size:13.5px;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;}}
      .lro-table th {{text-align:left;background:#f8fafc;color:#334155;padding:12px 10px;border-bottom:1px solid #e5e7eb;cursor:pointer;user-select:none;white-space:nowrap;}}
      .lro-table td {{padding:10px 10px;border-bottom:1px solid #eef2f7;color:#0f172a;vertical-align:top;}}
      .lro-table tr:hover td {{background:#fafafa;}}
      .lro-table .col-last {{background:#eff6ff;}}
      .lro-table .col-best {{background:#fff7ed;}}
      .lro-table .col-avg {{background:#f0fdf4;}}
      .lro-table .col-merit {{background:#fffbeb;}}
      .lro-table td.col-last {{background:#dbeafe;font-weight:750;}}
      .lro-table td.col-best {{background:#ffedd5;font-weight:750;}}
      .lro-table td.col-avg {{background:#dcfce7;font-weight:750;}}
      .lro-table td.col-merit {{background:#fef3c7;font-weight:850;}}
      .manager-link {{font-weight:850;color:#7f1d1d;cursor:pointer;text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:3px;}}
      .badge-tag {{display:inline-block;border-radius:999px;padding:3px 8px;background:#f1f5f9;color:#334155;font-weight:700;font-size:12px;white-space:nowrap;}}
      .history-detail {{background:#0f172a!important;color:white!important;padding:14px!important;}}
      .history-detail table {{width:100%;border-collapse:collapse;margin-top:8px;}}
      .history-detail th,.history-detail td {{color:white;border-bottom:1px solid rgba(255,255,255,0.12);padding:6px 8px;text-align:left;}}
      .sort-mark {{margin-left:6px;font-size:11px;color:#b91c1c;}}
      .merits-cell {{max-width:460px;line-height:1.35;}}
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
        const numericKeys = new Set(['meritRank','seasons','lastRank','bestRank','avg3','hofScore','tagSort']);
        let av=a[sortKey]; let bv=b[sortKey];
        if (numericKeys.has(sortKey)) {{
          const am=av===null||av===undefined||Number.isNaN(av); const bm=bv===null||bv===undefined||Number.isNaN(bv);
          if(am&&bm) return String(a.manager).localeCompare(String(b.manager),'nb');
          if(am) return 1; if(bm) return -1;
          const diff=sortDir==='asc'?av-bv:bv-av;
          if(diff!==0) return diff;
          if(sortKey==='tagSort') return a.hofScore===b.hofScore ? String(a.manager).localeCompare(String(b.manager),'nb') : b.hofScore-a.hofScore;
          return String(a.manager).localeCompare(String(b.manager),'nb');
        }}
        av=String(av||'').toLowerCase(); bv=String(bv||'').toLowerCase();
        return sortDir==='asc'?av.localeCompare(bv,'nb'):bv.localeCompare(av,'nb');
      }}
      function detailRow(row) {{
        const data=histories[row.entry]||[];
        const rows=data.map(item=>`<tr><td>${{esc(item.season)}}</td><td>${{fmtNum(item.points)}}</td><td>${{fmtNum(item.rank)}}</td></tr>`).join('');
        const empty=data.length?'':'<div>Fant ikke tidligere sesonger.</div>';
        return `<tr><td colspan="10" class="history-detail"><strong>Full FPL-historikk: ${{esc(row.manager)}}</strong>${{empty}}<table><thead><tr><th>Sesong</th><th>Poeng</th><th>FPL-plassering</th></tr></thead><tbody>${{rows}}</tbody></table></td></tr>`;
      }}
      function render() {{
        const sorted=[...historyRows].sort(compareRows); tbody.innerHTML='';
        sorted.forEach(row=>{{
          const tr=document.createElement('tr');
          tr.innerHTML=`<td><strong>${{esc(row.rankLabel)}}</strong></td><td><span class="manager-link" data-entry="${{esc(row.entry)}}">${{esc(row.manager)}}</span></td><td>${{esc(row.team)}}</td><td>${{fmtNum(row.seasons)}}</td><td class="col-last">${{fmtNum(row.lastRank)}}</td><td class="col-best">${{fmtBest(row)}}</td><td class="col-avg">${{fmtNum(row.avg3)}}</td><td class="col-merit">${{fmtNum(row.hofScore)}}</td><td class="merits-cell">${{esc(row.merits)}}</td><td><span class="badge-tag">${{esc(row.tag)}}</span></td>`;
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
        <thead><tr><th data-key="rank" class="sortable">#</th><th data-key="manager" class="sortable">Manager</th><th data-key="hofScore" class="sortable col-merit">Merittpoeng</th><th data-key="overall" class="sortable">Sammenlagtseiere</th><th data-key="cupGold" class="sortable">Cupgull</th><th data-key="cupSilver" class="sortable">Cupsølv</th><th data-key="monthly" class="sortable">Månedsseiere</th><th data-key="merits" class="sortable">Meritter</th></tr></thead>
        <tbody id="lro-hof-body"></tbody>
      </table>
    </div>
    <style>
      .lro-hof-wrap {{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}}
      .lro-table {{border-collapse:collapse;width:100%;font-size:13.5px;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;}}
      .lro-table th {{text-align:left;background:#f8fafc;color:#334155;padding:12px 10px;border-bottom:1px solid #e5e7eb;cursor:pointer;white-space:nowrap;}}
      .lro-table td {{padding:10px 10px;border-bottom:1px solid #eef2f7;color:#0f172a;vertical-align:top;}}
      .lro-table tr:hover td {{background:#fafafa;}}
      .lro-table .col-merit {{background:#fffbeb;}}
      .lro-table td.col-merit {{background:#fef3c7;font-weight:900;}}
      .manager-strong {{font-weight:850;}}
      .merits-cell {{max-width:560px;line-height:1.35;}}
      .sort-mark {{margin-left:6px;font-size:11px;color:#b91c1c;}}
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

    cols = st.columns(2)

    for index, row in ordered.iterrows():
        count = int(row.get("Antall", 0))
        label = "manager" if count == 1 else "managere"
        people = str(row.get("Deltakere", ""))

        with cols[index % 2]:
            with st.container(border=True):
                st.markdown(f"**{row.get('By', '')} · {count} {label}**")
                st.caption(people)

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
    "odds_before": "Vinnerodds før sesongstart",
    "top3_odds": "Topp 3-odds før sesongstart",
    "top3_odds_float": "Topp 3-odds før sesongstart",
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
    "tag_display": "Merknad",
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
    "total_titles": "Titler totalt",
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
    "gold": "Gull",
    "silver": "Sølv",
    "bronze": "Bronse",
    "podiums": "Podier",
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
    "leaders_count": "Antall på topp",
    "king_points": "Poeng",
    "month_merits": "Meritter i måneden",
    "podiums": "Podier",
    "comment": "Vurdering",
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
    "odds": "Vinnerodds før sesongstart",
    "top3_odds": "Topp 3-odds før sesongstart",
    "odds_rank": "Odds-rangering",
    "performance_vs_odds": "Avvik mot odds",
    "last_three_points": "Poeng siste tre runder",
    "last_three_avg": "Snitt siste tre runder",
    "last_three_detail": "Siste tre runder",
}

NUMERIC_CONFIG = {
    "odds_before": st.column_config.NumberColumn("Vinnerodds før sesongstart", format="%.2f"),
    "best_rank_numeric": st.column_config.NumberColumn("Beste FPL-plassering gjennom tidene", format="%d"),
    "last_season_rank_display": st.column_config.TextColumn("Plassering forrige sesong", width="medium"),
    "avg_rank_last_3_display": st.column_config.TextColumn("Snitt siste tre sesonger", width="medium"),
    "event_total_num": st.column_config.NumberColumn("Rundepoeng", format="%d"),
    "total_num": st.column_config.NumberColumn("Poeng", format="%d"),
    "rank_num": st.column_config.NumberColumn("Plassering", format="%d"),
    "odds": st.column_config.NumberColumn("Vinnerodds før sesongstart", format="%.2f"),
    "top3_odds_float": st.column_config.NumberColumn("Topp 3-odds før sesongstart", format="%.2f"),
    "odds_rank": st.column_config.NumberColumn("Odds-rangering", format="%d"),
    "performance_vs_odds": st.column_config.NumberColumn("Avvik mot odds", format="%d"),
    "last_three_points": st.column_config.NumberColumn("Poeng siste tre runder", format="%d"),
    "last_three_avg": st.column_config.NumberColumn("Snitt siste tre runder", format="%.1f"),
}


# -----------------------------
# UI
# -----------------------------

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Ligatabell",
    "Historikk",
    "Odds",
    "Hall of Fame",
    "Sesongradar",
    "Norgeskart",
])

with tab1:
    st.header("Ligatabell")
    lro_note("Sesongens inngang", "Påmeldte lag, rundepoeng, totalpoeng og formkurve. Odds og dueller ligger i Odds-fanen.", "")

    if st.button("Hent ligadata"):
        ensure_history_loaded(DEFAULT_LEAGUE_ID)

    if "managers" in st.session_state:
        managers = st.session_state["managers"]

        if not managers:
            st.warning("Fant ingen påmeldte/managers.")
        else:
            table_df = pd.DataFrame(managers)
            summary_df = st.session_state.get("summary_df", pd.DataFrame())

            if not summary_df.empty:
                table_df = table_df.merge(
                    summary_df[["entry", "tier", "tag"]],
                    on="entry",
                    how="left",
                )
            else:
                table_df["tier"] = ""
                table_df["tag"] = ""

            table_df["rank_num"] = pd.to_numeric(table_df["rank"], errors="coerce")
            table_df["last_rank_num"] = pd.to_numeric(table_df["last_rank"], errors="coerce")
            table_df["event_total_num"] = pd.to_numeric(table_df["event_total"], errors="coerce")
            table_df["total_num"] = pd.to_numeric(table_df["total"], errors="coerce")
            table_df["rank_display"] = table_df["rank_num"].apply(format_rank)
            table_df["form_delta"] = table_df["last_rank_num"] - table_df["rank_num"]

            has_live_table = table_df["rank_num"].notna().any()
            if has_live_table:
                table_df = table_df.sort_values(["rank_num", "player_name"], ascending=[True, True], na_position="last")
            else:
                table_df = table_df.sort_values(["player_name"], ascending=[True], na_position="last")

            render_league_table_component(table_df, has_live_table)

            with st.expander("Hva betyr formkurven?"):
                st.write(
                    """
                    **🟢 ↑** kraftig opp.  
                    **🔵 ↗** litt opp.  
                    **⚪ ━** omtrent på stedet hvil / før sesongstart.  
                    **🟡 ↘** litt ned.  
                    **🔴 ↓** kraftig ned.
                    """
                )

            st.caption(f"Fant {len(table_df)} lag.")

            download_columns = ["rank_display", "player_name", "entry_name", "event_total_num", "total_num", "form_delta"]
            st.download_button(
                label="Last ned ligadata som CSV",
                data=csv_bytes(table_df, download_columns, LIGATABELL_LABELS),
                file_name="lro_ligatabell.csv",
                mime="text/csv",
            )



with tab2:
    st.header("Historikk")
    lro_note("Fortid, ikke framtid", "Historikken viser tidligere FPL-sesonger, beste plassering, siste tre sesonger og meritter fra Lofthus Road Open. Tabellen er sortert på merittpoeng som standard.", "")

    if st.button("Hent historikk"):
        ensure_history_loaded(DEFAULT_LEAGUE_ID)

    if "summary_df" in st.session_state:
        summary_df = st.session_state["summary_df"]
        seasons_df = st.session_state["seasons_df"]
        errors_df = st.session_state["errors_df"]

        if summary_df.empty:
            st.warning("Fant ingen historikk.")
        else:
            summary = summary_df.copy()
            summary = add_sortable_display_columns(summary)
            summary = summary.sort_values(["hof_score", "manager"], ascending=[False, True], na_position="last").reset_index(drop=True)
            summary["merit_rank"] = range(1, len(summary) + 1)
            summary["merits"] = summary["merits"].fillna("")

            st.subheader("Historikktabell")
            render_history_table_component(summary, seasons_df)

            history_download = summary[[
                "merit_rank", "manager", "team", "seasons", "last_season_rank_num",
                "best_rank_num", "best_season", "avg_rank_last_3_num", "hof_score", "merits", "tag"
            ]].rename(columns={
                "merit_rank": "Rangering",
                "manager": "Manager",
                "team": "Lagnavn",
                "seasons": "Sesonger spilt",
                "last_season_rank_num": "Plassering forrige sesong",
                "best_rank_num": "Beste FPL-plassering gjennom tidene",
                "best_season": "Beste sesong",
                "avg_rank_last_3_num": "Snitt siste tre sesonger",
                "hof_score": "Merittpoeng",
                "merits": "Meritter",
                "tag": "Merknad",
            })

            st.download_button(
                label="Last ned historikk som CSV",
                data=history_download.to_csv(index=False).encode("utf-8"),
                file_name="lro_historikk.csv",
                mime="text/csv",
            )

            with st.expander("Utvikling siste tre sesonger"):
                trend_columns = ["manager", "team", "trend"]
                display_table(summary, trend_columns, HISTORY_LABELS)

            with st.expander("Hvordan regnes merittpoeng?"):
                weights = pd.DataFrame([
                    {"Meritt": "Sammenlagt-seier", "Poeng": 60},
                    {"Meritt": "Sammenlagt-sølv", "Poeng": 30},
                    {"Meritt": "Sammenlagt-bronse", "Poeng": 16},
                    {"Meritt": "Cupgull", "Poeng": 20},
                    {"Meritt": "Cupsølv", "Poeng": 8},
                    {"Meritt": "Månedsseier", "Poeng": 6},
                    {"Meritt": "Månedssølv", "Poeng": 2},
                    {"Meritt": "Månedsbronse", "Poeng": 1},
                    {"Meritt": "Random plassering", "Poeng": 4},
                ])
                st.dataframe(weights, use_container_width=True, hide_index=True)

            with st.expander("Merknad-forklaring"):
                st.write(
                    """
                    **Tittelkandidat:** høy rating, lav før-sesong-odds eller sterk historikk.  
                    **Outsider:** mange gode sesonger eller flere topp 100k / topp 500k.  
                    **Dark horse:** høy peak, men svakere/rotete nyere historikk, eller to gode sesonger på rad etter svakere historikk.  
                    **Stabil traver:** mye historikk og jevnt OK nivå, men ikke åpenbar vinnerprofil.  
                    **Usikkert kort:** svakere historikk, lavere modellstyrke eller svak siste periode.  
                    **Rookie:** for få sesonger.
                    """
                )

            with st.expander("Alle tidligere sesonger"):
                season_columns = ["manager", "team", "season_name", "total_points", "rank"]
                display_table(seasons_df, season_columns, SEASON_LABELS)

                st.download_button(
                    label="Last ned alle sesonger som CSV",
                    data=csv_bytes(seasons_df, season_columns, SEASON_LABELS),
                    file_name="lro_alle_sesonger.csv",
                    mime="text/csv",
                )

        if not errors_df.empty:
            st.warning("Noen feilet ved historikkhenting.")
            display_table(errors_df, ["manager", "team", "entry", "error"], ERROR_LABELS)


with tab3:
    st.header("Odds")
    lro_note("Før sesongstart", "Her ligger vinnerodds, topp 3-odds og egen duellgenerator. Oddsene er laget for intern banter, men modellen er justert for at FPL-miniligaer har høy varians.", "")

    if "summary_df" in st.session_state and not st.session_state["summary_df"].empty:
        summary_df = st.session_state["summary_df"]
        odds_df = build_preseason_odds(summary_df)
        odds_view = odds_df.copy()
        odds_view["top3_odds_float"] = pd.to_numeric(odds_view["top3_odds_float"], errors="coerce")
        odds_view = add_sortable_display_columns(odds_view)
        render_odds_table_component(odds_view)

        st.download_button(
            label="Last ned odds som CSV",
            data=odds_view[["odds_rank", "manager", "team", "odds", "top3_odds"]].rename(columns={"team": "lagnavn"}).to_csv(index=False).encode("utf-8"),
            file_name="lro_odds.csv",
            mime="text/csv",
        )
    else:
        st.info("Hent ligadata/historikk først. Da fylles oddsgrunnlaget automatisk her.")

    st.subheader("Lag egne dueller")
    st.write("Skriv én duell eller gruppe per linje. Bruk `vs` mellom navnene.")
    market_text = st.text_area("Dueller/grupper", value="", height=260)

    if st.button("Lag duellodds"):
        ensure_history_loaded(DEFAULT_LEAGUE_ID)
        summary_df = st.session_state["summary_df"]

        market_df, missing_df = analyze_markets(summary_df, market_text)

        if not market_df.empty:
            st.dataframe(market_df, use_container_width=True, hide_index=True)
            st.download_button(
                label="Last ned duellodds som CSV",
                data=market_df.to_csv(index=False).encode("utf-8"),
                file_name="lro_duellodds.csv",
                mime="text/csv",
            )
        else:
            st.warning("Fant ingen markeder å vise.")

        if not missing_df.empty:
            with st.expander("Navn appen ikke fant sikkert treff på"):
                st.dataframe(missing_df, use_container_width=True, hide_index=True)


with tab4:
    st.header("Hall of Fame")
    lro_note("Ligaens pokalskap", "Sammenlagt-seier vektes tyngst, cupgull deretter, månedsseiere lavere. Månedspodier gir ekstra historisk krydder.", "gold")

    hof_df = build_hof_people()

    if hof_df.empty:
        st.warning("Fant ingen Hall of Fame-data.")
    else:
        hof_df = hof_df.sort_values(["hof_score", "display_name"], ascending=[False, True]).reset_index(drop=True)
        hof_df["rank_display"] = [f"{medal_for_position(i + 1)} {i + 1}".strip() for i in range(len(hof_df))]

        st.subheader("Meritt-tabell")
        render_hof_table_component(hof_df)

        hof_main = hof_df[[
            "rank_display",
            "display_name",
            "hof_score",
            "overall_count",
            "cup_count",
            "cup_runner_up_count",
            "monthly_titles",
            "merits",
        ]].rename(columns={
            "rank_display": "Rangering",
            "display_name": "Manager",
            "hof_score": "Merittpoeng",
            "overall_count": "Sammenlagt-seiere",
            "cup_count": "Cupgull",
            "cup_runner_up_count": "Cupsølv",
            "monthly_titles": "Månedsseiere",
            "merits": "Meritter",
        })

        st.download_button(
            label="Last ned Hall of Fame som CSV",
            data=hof_main.to_csv(index=False).encode("utf-8"),
            file_name="lro_hall_of_fame.csv",
            mime="text/csv",
        )

        with st.expander("Detaljert meritt-tabell"):
            detailed_hof = hof_df[[
                "rank_display",
                "display_name",
                "total_titles",
                "overall_count",
                "overall_runner_up_count",
                "overall_third_count",
                "cup_count",
                "cup_runner_up_count",
                "monthly_titles",
                "monthly_silver",
                "monthly_bronze",
                "monthly_podiums",
                "random_count",
                "merits",
            ]].rename(columns={
                "rank_display": "Rangering",
                "display_name": "Manager",
                "total_titles": "Titler totalt",
                "overall_count": "Sammenlagt-seiere",
                "overall_runner_up_count": "Sammenlagt-sølv",
                "overall_third_count": "Sammenlagt-bronse",
                "cup_count": "Cupgull",
                "cup_runner_up_count": "Cupsølv",
                "monthly_titles": "Månedsseiere",
                "monthly_silver": "Månedssølv",
                "monthly_bronze": "Månedsbronse",
                "monthly_podiums": "Månedspodier",
                "random_count": "Random",
                "merits": "Meritter",
            })
            st.dataframe(detailed_hof, use_container_width=True, hide_index=True)

        st.subheader("Sesongdetaljer per manager")
        detail_columns = [
            "display_name",
            "overall_seasons",
            "overall_runner_up_seasons",
            "overall_third_seasons",
            "cup_seasons",
            "cup_runner_up_seasons",
        ]
        display_table(hof_df, detail_columns, HOF_LABELS, column_config={"display_name": st.column_config.TextColumn("Manager", width="large")})

        st.subheader("Månedskonger")
        month_specialists = build_month_specialist_table()

        if month_specialists.empty:
            st.warning("Fant ingen månedskonge-data.")
        else:
            month_specialist_columns = ["month", "king", "leaders_count", "king_points", "month_merits", "podiums", "comment"]
            display_table(month_specialists, month_specialist_columns, MONTH_SPECIALIST_LABELS)

        st.subheader("Hvem gjør det best i hvilken måned?")
        monthly_df = build_monthly_podium_df()

        if monthly_df.empty:
            st.warning("Fant ingen månedspodier.")
        else:
            seasons = ["Alle"] + sorted(monthly_df["season"].dropna().unique().tolist())
            selected_season = st.selectbox("Velg sesong", seasons, key="monthly_season_filter_v23")
            monthly_medals = build_monthly_medal_table(selected_season)

            medal_columns = ["monthly_rank", "manager", "month_points", "gold", "silver", "bronze", "podiums"]
            display_table(monthly_medals, medal_columns, MONTHLY_MEDAL_LABELS)

            lro_note(
                "Ufullstendig sølv/bronse-historikk",
                "Jeg har alle månedsvinnerne, men ikke full oversikt over 2. og 3. plass i hver eneste måned tilbake til september 2020. Tabellen under viser det som er dokumentert.",
                "gold",
            )

            with st.expander("Måned for måned"):
                calendar_df = build_monthly_calendar_table(selected_season)
                calendar_columns = ["season", "month", "winner", "second_place", "third_place"]
                display_table(calendar_df, calendar_columns, MONTHLY_CALENDAR_LABELS)

            with st.expander("Månedspodier"):
                podium_view = monthly_df.copy()
                if selected_season != "Alle":
                    podium_view = podium_view[podium_view["season"] == selected_season]
                podium_columns = ["season", "month", "place", "manager", "points"]
                display_table(podium_view, podium_columns, MONTHLY_PODIUM_LABELS)

        st.subheader("Sammenlagtvinnere")
        overall_df = pd.DataFrame(HOF_OVERALL)
        display_table(overall_df, ["season", "winner", "runner_up", "third_place"], OVERALL_LABELS)

        st.subheader("Cupvinnere")
        cup_df = pd.DataFrame(HOF_CUP)
        display_table(cup_df, ["season", "winner", "runner_up"], CUP_LABELS)

        st.subheader("Random plassering")
        random_df = pd.DataFrame(HOF_RANDOM)
        display_table(random_df, ["season", "winner", "placement"], RANDOM_LABELS)


with tab5:
    st.header("Sesongradar")
    lro_note("Blir best når sesongen er i gang", "Her kommer største klatrere, største fall, form siste tre runder og hvem som over-/underpresterer mot før-sesong-odds.", "")

    if st.button("Hent sesongradar"):
        ensure_history_loaded(DEFAULT_LEAGUE_ID)

    if "managers" in st.session_state:
        summary_df = st.session_state.get("summary_df", pd.DataFrame())
        radar = build_season_radar_tables(st.session_state["managers"], summary_df)

        if not radar:
            st.info("Sesongradaren våkner for alvor når FPL-sesongen er i gang og ligaen har live plasseringer/rundedata.")
        else:
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("Største klatrere")
                if radar["climbers"].empty:
                    st.caption("Ingen live-bevegelse ennå.")
                else:
                    display_table(radar["climbers"], ["player_name", "entry_name", "rank_num", "form_curve", "total_num"], RADAR_LABELS, column_config=NUMERIC_CONFIG)

            with c2:
                st.subheader("Største fall")
                if radar["fallers"].empty:
                    st.caption("Ingen live-bevegelse ennå.")
                else:
                    display_table(radar["fallers"], ["player_name", "entry_name", "rank_num", "form_curve", "total_num"], RADAR_LABELS, column_config=NUMERIC_CONFIG)

            st.subheader("Form siste tre runder")
            if radar["form_three"].empty:
                st.caption("Ikke nok runde-data ennå.")
            else:
                display_table(radar["form_three"], ["player_name", "entry_name", "last_three_points", "last_three_avg", "last_three_detail", "rank_num"], RADAR_LABELS, column_config=NUMERIC_CONFIG)

            c3, c4 = st.columns(2)

            with c3:
                st.subheader("Overpresterer mot før-sesong-odds")
                if radar["over"].empty:
                    st.caption("Trenger live-tabell og oddsdata.")
                else:
                    display_table(radar["over"], ["player_name", "entry_name", "rank_num", "odds_rank", "performance_vs_odds", "odds"], RADAR_LABELS, column_config=NUMERIC_CONFIG)

            with c4:
                st.subheader("Underpresterer mot før-sesong-odds")
                if radar["under"].empty:
                    st.caption("Trenger live-tabell og oddsdata.")
                else:
                    display_table(radar["under"], ["player_name", "entry_name", "rank_num", "odds_rank", "performance_vs_odds", "odds"], RADAR_LABELS, column_config=NUMERIC_CONFIG)


with tab6:
    st.header("Norgeskart")
    lro_note("Ligaen på kartet", "Geografisk fordeling av managerne i ligaen. Kartet viser klynger; bruk tabellen under for full navneliste.", "")

    active_manager_names = []
    if "managers" in st.session_state:
        active_manager_names = [manager.get("player_name", "") for manager in st.session_state.get("managers", [])]

    place_df = build_place_data(active_manager_names if active_manager_names else None)

    if place_df.empty:
        st.warning("Fant ingen steder i data/places.csv.")
    else:
        total_people = int(place_df["Antall"].sum())
        top_city = place_df.sort_values("Antall", ascending=False).iloc[0]

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric("Registrerte på kartet", total_people)

        with c2:
            st.metric("Byer/steder", len(place_df))

        with c3:
            st.metric("Største miljø", top_city["By"], int(top_city["Antall"]))

        raw_places = read_csv_file("places.csv", ["manager", "place", "lat", "lon"])
        mapped_keys = set(raw_places["manager"].map(hof_key).tolist()) if not raw_places.empty else set()

        with st.expander("Kartdata-kontroll"):
            if "managers" in st.session_state:
                missing = []
                for manager in st.session_state.get("managers", []):
                    manager_name = manager.get("player_name", "")
                    if manager_name and hof_key(manager_name) not in mapped_keys:
                        missing.append(manager_name)

                if missing:
                    st.warning("Mangler kartplassering/alias for: " + ", ".join(sorted(set(missing))))
                    st.caption("Hvis personen egentlig finnes på kartet, legg navnevarianten inn i data/aliases.csv. Hvis personen mangler helt, legg vedkommende inn i data/places.csv.")
                elif total_people != len(st.session_state.get("managers", [])):
                    st.info(f"Kartet har {total_people} personer, mens FPL-lista har {len(st.session_state.get('managers', []))}. Sjekk mulige alias/duplikater.")
                else:
                    st.success("Kartdata matcher FPL-lista.")
            else:
                st.info("Trykk Hent ligadata i Ligatabell for å sjekke om noen påmeldte mangler kartplassering.")

        if pdk is not None:
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=place_df,
                get_position="[lon, lat]",
                get_radius="radius",
                get_fill_color="[185, 28, 28, 210]",
                get_line_color="[15, 23, 42]",
                line_width_min_pixels=1,
                pickable=True,
            )

            view_state = pdk.ViewState(latitude=64.9, longitude=13.5, zoom=3.85, pitch=20)

            deck = pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=view_state,
                layers=[layer],
                tooltip={
                    "text": "{By}\n{Antall} managere\n{Deltakere}",
                    "style": {
                        "backgroundColor": "white",
                        "color": "black",
                        "padding": "14px",
                        "borderRadius": "12px",
                        "maxWidth": "760px",
                        "fontSize": "13px",
                    },
                },
            )

            st.pydeck_chart(deck, use_container_width=True)

        else:
            map_df = place_df.rename(columns={"lat": "latitude", "lon": "longitude"})
            st.map(map_df, latitude="latitude", longitude="longitude")

        st.subheader("Steder og deltakere")
        render_city_cards(place_df)
