import math
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

try:
    import pydeck as pdk
except ImportError:
    pdk = None


BASE_URL = "https://fantasy.premierleague.com/api"
DEFAULT_LEAGUE_ID = 25220
APP_VERSION = "lofthus-road-open-kontrollrom-v14-launch-polish"

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

        .block-container {padding-top: 1.8rem; padding-bottom: 3rem;}

        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            padding: 14px 16px;
            border-radius: 16px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
        }

        .lro-hero {
            background:
                radial-gradient(circle at 92% 18%, rgba(251, 191, 36, 0.22), transparent 24%),
                linear-gradient(135deg, #0b1220 0%, #111827 48%, #7f1d1d 100%);
            border-radius: 28px;
            padding: 32px 36px;
            color: white;
            margin-bottom: 22px;
            box-shadow: 0 16px 42px rgba(15, 23, 42, 0.22);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }

        .lro-hero h1 {
            font-size: clamp(2rem, 4vw, 3.35rem);
            line-height: 1.02;
            margin: 0 0 10px 0;
            color: white;
            letter-spacing: -0.04em;
        }

        .lro-eyebrow {
            display: inline-block;
            font-size: 0.78rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: #fecaca;
            font-weight: 800;
            margin-bottom: 12px;
        }

        .lro-hero p {
            margin: 0;
            color: #e5e7eb;
            font-size: 1.03rem;
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
            margin-bottom: 16px;
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
            font-size: 1.45rem;
            line-height: 1.1;
            font-weight: 850;
            letter-spacing: -0.025em;
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

        @media (max-width: 760px) {
            .lro-hero {padding: 24px 22px; border-radius: 22px;}
            .lro-hero h1 {font-size: 2.05rem;}
            .lro-card-grid {grid-template-columns: 1fr;}
        }
    </style>
    <div class="lro-hero">
        <div class="lro-beta">Beta · lanseringsklar prototype</div>
        <div class="lro-eyebrow">Lofthus Road Open</div>
        <h1>Lofthus Road Open - Kontrollrom</h1>
        <p>Live tabell · historikk · H2H · Hall of Fame · månedskonger · sesongradar · norgeskart</p>
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
    html = ['<div class="lro-card-grid">']
    for card in cards:
        variant = " dark" if card.get("dark") else ""
        html.append(
            f'''
            <div class="lro-card{variant}">
                <div class="lro-card-label">{card.get('label', '')}</div>
                <div class="lro-card-value">{card.get('value', '')}</div>
                <div class="lro-card-caption">{card.get('caption', '')}</div>
            </div>
            '''
        )
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


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


def merit_text(row: dict) -> str:
    parts = []

    if row.get("overall_count", 0):
        parts.append(f"{int(row['overall_count'])}x sammenlagt")

    if row.get("overall_runner_up_count", 0):
        parts.append(f"{int(row['overall_runner_up_count'])}x sølv sammenlagt")

    if row.get("overall_third_count", 0):
        parts.append(f"{int(row['overall_third_count'])}x bronse sammenlagt")

    if row.get("cup_count", 0):
        parts.append(f"{int(row['cup_count'])}x cupgull")

    if row.get("cup_runner_up_count", 0):
        parts.append(f"{int(row['cup_runner_up_count'])}x cupsølv")

    if row.get("random_count", 0):
        parts.append(f"{int(row['random_count'])}x random")

    if row.get("monthly_titles", 0):
        parts.append(f"{int(row['monthly_titles'])}x måned")

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

def build_preseason_odds(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty:
        return pd.DataFrame()

    df = summary_df.copy()
    df["total_rating"] = pd.to_numeric(df["total_rating"], errors="coerce").fillna(0)

    top_score = df["total_rating"].max()
    base_favorite_odds = 2.10
    max_outright_odds = 101.00

    df["odds_float"] = base_favorite_odds * ((top_score - df["total_rating"]) / 8.8).apply(math.exp)

    df.loc[df["seasons"] <= 2, "odds_float"] *= 1.15
    df.loc[df["last_season_rank_num"].fillna(999_999_999) > 2_000_000, "odds_float"] *= 1.20
    df.loc[df["avg_rank_last_3_num"].fillna(999_999_999) > 1_500_000, "odds_float"] *= 1.18

    df.loc[df["top_100k_seasons"] >= 4, "odds_float"] *= 0.95
    df.loc[df["top_500k_seasons"] >= 10, "odds_float"] *= 0.97

    if "hof_score" in df.columns:
        df.loc[df["hof_score"] >= 60, "odds_float"] *= 0.97
        df.loc[df["monthly_titles"] >= 4, "odds_float"] *= 0.98

    df["odds_float"] = df["odds_float"].clip(lower=2.00, upper=max_outright_odds)
    df["odds"] = df["odds_float"].apply(format_odds)

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


def reason_bits(a: pd.Series, b: pd.Series, max_items: int = 2) -> str:
    bits = []

    if num(a, "avg_rank_last_3_num") < num(b, "avg_rank_last_3_num"):
        bits.append(f"bedre snitt siste 3 ({a['avg_rank_last_3']} mot {b['avg_rank_last_3']})")

    if num(a, "last_season_rank_num") < num(b, "last_season_rank_num"):
        bits.append(f"bedre sist sesong ({a['last_season_rank']} mot {b['last_season_rank']})")

    if num(a, "best_rank_num") < num(b, "best_rank_num"):
        bits.append(f"bedre peak ({a['best_rank']} mot {b['best_rank']})")

    if int(a.get("top_100k_seasons") or 0) > int(b.get("top_100k_seasons") or 0):
        bits.append(f"flere topp 100k ({int(a['top_100k_seasons'])} mot {int(b['top_100k_seasons'])})")

    if not bits:
        bits.append("marginalt sterkere samlet profil")

    return "; ".join(bits[:max_items])


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
        return f"Sist: {previous_player['manager']} har {reason_bits(previous_player, player)}."

    above = ordered_players[index - 1]
    below = ordered_players[index + 1]

    return (
        f"Bak {above['manager']}: {reason_bits(above, player, 1)}. "
        f"Foran {below['manager']}: {reason_bits(player, below, 1)}."
    )


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
            "Lag": player["team"],
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
                    "Lag": player["team"],
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

    def tag_value(value: str) -> str:
        if not value or pd.isna(value):
            return ""
        return f"{TAG_SORT.get(str(value), 99):02d} · {value}"

    def tier_value(value: str) -> str:
        if not value or pd.isna(value):
            return ""
        return f"{TIER_SORT.get(str(value), 99):02d} · {value}"

    if "tag" in df.columns:
        df["tag_display"] = df["tag"].apply(tag_value)

    if "tier" in df.columns:
        df["tier_display"] = df["tier"].apply(tier_value)

    return df


def make_numeric_display(df: pd.DataFrame, source: str, target: str) -> pd.DataFrame:
    df = df.copy()
    df[target] = pd.to_numeric(df.get(source), errors="coerce")
    df.loc[df[target] >= 999_999_999, target] = pd.NA
    return df


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

def build_place_data() -> pd.DataFrame:
    df = read_csv_file("places.csv", ["manager", "place", "lat", "lon"])

    if df.empty:
        return pd.DataFrame(columns=["By", "lat", "lon", "Antall", "Deltakere", "Label", "radius"])

    df = df[(df["manager"] != "") & (df["place"] != "")].copy()
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])

    rows = []

    for (place, lat, lon), place_df in df.groupby(["place", "lat", "lon"], dropna=False):
        people = sorted(place_df["manager"].dropna().astype(str).unique().tolist())
        count = len(people)

        rows.append({
            "By": place,
            "lat": float(lat),
            "lon": float(lon),
            "Antall": count,
            "Deltakere": ", ".join(people),
            "Label": f"{place} ({count})",
            "radius": 12_000 + count * 5_500,
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
    "form_curve": "Formkurve",
    "player_name": "Manager",
    "entry_name": "Lag",
    "event_total_num": "Rundepoeng",
    "total_num": "Poeng",
    "odds_before": "Odds før sesongstart",
    "best_rank_numeric": "Beste plassering",
    "tag_display": "Merknad",
    "tier_display": "Nivå",
}

HISTORY_LABELS = {
    "manager": "Manager",
    "team": "Lag",
    "seasons": "Sesonger spilt",
    "last_season_rank_numeric": "Plassering sist",
    "best_rank_numeric": "Beste plassering",
    "best_season": "Beste sesong",
    "avg_rank_last_3_numeric": "Siste tre sesonger",
    "trend": "Utvikling siste 3",
    "monthly_titles": "Månedstitler",
    "merits": "Meritter",
    "top_100k_seasons": "Topp 100k",
    "top_500k_seasons": "Topp 500k",
    "tier_display": "Nivå",
    "tag_display": "Merknad",
}

SEASON_LABELS = {
    "manager": "Manager",
    "team": "Lag",
    "season_name": "Sesong",
    "total_points": "Poeng",
    "rank": "Plassering",
}

ERROR_LABELS = {
    "manager": "Manager",
    "team": "Lag",
    "entry": "Entry-ID",
    "error": "Feil",
}

HOF_LABELS = {
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
    "entry_name": "Lag",
    "rank_num": "Plassering",
    "rank_display": "Plassering",
    "form_curve": "Formkurve",
    "event_total_num": "Rundepoeng",
    "total_num": "Poeng",
    "odds": "Odds før sesongstart",
    "odds_rank": "Odds-rangering",
    "performance_vs_odds": "Avvik mot odds",
    "last_three_points": "Poeng siste tre runder",
    "last_three_avg": "Snitt siste tre runder",
    "last_three_detail": "Siste tre runder",
}

NUMERIC_CONFIG = {
    "odds_before": st.column_config.NumberColumn("Odds før sesongstart", format="%.2f"),
    "best_rank_numeric": st.column_config.NumberColumn("Beste plassering", format="%d"),
    "last_season_rank_numeric": st.column_config.NumberColumn("Plassering sist", format="%d"),
    "avg_rank_last_3_numeric": st.column_config.NumberColumn("Siste tre sesonger", format="%d"),
    "event_total_num": st.column_config.NumberColumn("Rundepoeng", format="%d"),
    "total_num": st.column_config.NumberColumn("Poeng", format="%d"),
    "rank_num": st.column_config.NumberColumn("Plassering", format="%d"),
    "odds": st.column_config.NumberColumn("Odds før sesongstart", format="%.2f"),
    "odds_rank": st.column_config.NumberColumn("Odds-rangering", format="%d"),
    "performance_vs_odds": st.column_config.NumberColumn("Avvik mot odds", format="%d"),
    "last_three_points": st.column_config.NumberColumn("Poeng siste tre runder", format="%d"),
    "last_three_avg": st.column_config.NumberColumn("Snitt siste tre runder", format="%.1f"),
}


# -----------------------------
# UI
# -----------------------------

tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Forside",
    "Ligatabell",
    "Historikk",
    "H2H",
    "Hall of Fame",
    "Sesongradar",
    "Norgeskart",
])


with tab0:
    st.header("Velkommen til kontrollrommet")
    lro_note(
        "Beta fram mot 1. august",
        "Dette er første lanserbare prototype. Målet er at ligaen skal finne feil i gamle meritter, navn, bosted og historikk før sesongen starter.",
        "gold",
    )

    hof_df_front = build_hof_people()
    place_df_front = build_place_data()
    monthly_df_front = build_monthly_podium_df()

    cards = [
        {
            "label": "Status",
            "value": "Beta",
            "caption": "Klar til intern test i gruppa.",
            "dark": True,
        },
        {
            "label": "Påmeldte lag",
            "value": str(len(st.session_state.get("managers", []))) if st.session_state.get("managers") else "Hent FPL-data",
            "caption": "Trykk Hent ligadata i Ligatabell-fanen.",
        },
        {
            "label": "Hall of Fame",
            "value": f"{len(HOF_OVERALL)} sesonger",
            "caption": "Sammenlagt, cup og gamle meritter.",
        },
        {
            "label": "Månedshistorikk",
            "value": f"{len(monthly_df_front)} podier" if not monthly_df_front.empty else "Ikke lastet",
            "caption": "Grunnlaget for månedskonger og månedsliga.",
        },
        {
            "label": "Norgeskart",
            "value": f"{int(place_df_front['Antall'].sum())} personer" if not place_df_front.empty else "Ikke lastet",
            "caption": "Geografien i Lofthus Road Open.",
        },
        {
            "label": "Mest merittert",
            "value": hof_df_front.iloc[0]["display_name"] if not hof_df_front.empty else "—",
            "caption": f"{int(hof_df_front.iloc[0]['hof_score'])} merittpoeng" if not hof_df_front.empty else "Kommer fra Hall of Fame-data.",
        },
    ]
    lro_cards(cards)

    st.subheader("Hva ligger her?")
    lro_cards([
        {"label": "Ligatabell", "value": "Nåtid", "caption": "Påmeldte lag, odds før sesongstart, beste historiske plassering og merknad."},
        {"label": "Historikk", "value": "Fortid", "caption": "Tidligere FPL-sesonger, beste plassering, siste tre sesonger og meritter."},
        {"label": "H2H", "value": "Rivaler", "caption": "Skriv inn dueller eller grupper og få banter-odds basert på historikk."},
        {"label": "Hall of Fame", "value": "Historiebok", "caption": "Sammenlagt, cup, månedsseiere, månedskonger og merittpoeng."},
        {"label": "Sesongradar", "value": "Live fortelling", "caption": "Klatrere, fall, form siste tre runder og over/underprestasjon mot odds."},
        {"label": "Norgeskart", "value": "Ligaidentitet", "caption": "Hvor folk i ligaen hører hjemme."},
    ])

    lro_note(
        "Meld feil i gruppa",
        "Gamle månedspremier, cupfinaler og bosted er hentet fra notater og gruppa. Finner du feil, meld det inn, så fikser vi før sesongstart.",
        "",
    )


with tab1:
    st.header("Ligatabell")
    lro_note("Sesongens inngang", "Her ligger påmeldte lag, odds før sesongstart og historisk merknad. Oddsene er banter/prognose, ikke fasit.", "")

    league_id = st.number_input("Liga-ID", value=DEFAULT_LEAGUE_ID, step=1, key="league_table_id_v11")

    if st.button("Hent ligadata"):
        ensure_history_loaded(int(league_id))

    if "managers" in st.session_state:
        managers = st.session_state["managers"]

        if not managers:
            st.warning("Fant ingen påmeldte/managers.")
        else:
            table_df = pd.DataFrame(managers)
            summary_df = st.session_state.get("summary_df", pd.DataFrame())

            if not summary_df.empty:
                odds_df = build_preseason_odds(summary_df)

                table_df = table_df.merge(
                    summary_df[["entry", "best_rank", "best_rank_num", "tier", "tag"]],
                    on="entry",
                    how="left",
                )

                if not odds_df.empty:
                    table_df = table_df.merge(
                        odds_df[["entry", "odds_float"]],
                        on="entry",
                        how="left",
                    )
                else:
                    table_df["odds_float"] = pd.NA
            else:
                table_df["best_rank"] = ""
                table_df["best_rank_num"] = pd.NA
                table_df["tier"] = ""
                table_df["tag"] = ""
                table_df["odds_float"] = pd.NA

            table_df["rank_num"] = pd.to_numeric(table_df["rank"], errors="coerce")
            table_df["last_rank_num"] = pd.to_numeric(table_df["last_rank"], errors="coerce")
            table_df["event_total_num"] = pd.to_numeric(table_df["event_total"], errors="coerce")
            table_df["total_num"] = pd.to_numeric(table_df["total"], errors="coerce")
            table_df["best_rank_numeric"] = pd.to_numeric(table_df["best_rank_num"], errors="coerce")
            table_df.loc[table_df["best_rank_numeric"] >= 999_999_999, "best_rank_numeric"] = pd.NA
            table_df["odds_before"] = pd.to_numeric(table_df["odds_float"], errors="coerce")

            table_df["rank_display"] = table_df["rank_num"].apply(format_rank)

            table_df["form_delta"] = table_df["last_rank_num"] - table_df["rank_num"]

            def form_curve(row):
                if pd.isna(row["rank_num"]) or pd.isna(row["last_rank_num"]):
                    return ""

                delta = int(row["last_rank_num"] - row["rank_num"])

                if delta > 0:
                    return f"🟢 ▲ {delta}"

                if delta < 0:
                    return f"🔴 ▼ {abs(delta)}"

                return "⚪ 0"

            table_df["form_curve"] = table_df.apply(form_curve, axis=1)
            table_df = add_sortable_display_columns(table_df)

            has_live_table = table_df["rank_num"].notna().any()

            if has_live_table:
                table_df = table_df.sort_values(["rank_num", "player_name"], ascending=[True, True], na_position="last")
            else:
                table_df = table_df.sort_values(["odds_before", "best_rank_numeric", "player_name"], ascending=[True, True, True], na_position="last")

            columns = [
                "rank_display",
                "form_curve",
                "player_name",
                "entry_name",
                "event_total_num",
                "total_num",
                "odds_before",
                "best_rank_numeric",
                "tag_display",
                "tier_display",
            ]

            display_table(table_df, columns, LIGATABELL_LABELS, column_config=NUMERIC_CONFIG)

            if not has_live_table:
                st.caption("Før sesongstart sorteres tabellen først etter odds. Trykk på kolonneoverskriftene for å sortere selv.")
            else:
                st.caption("Trykk på kolonneoverskriftene for å sortere tabellen.")

            with st.expander("Hva betyr Merknad og Nivå?"):
                st.write(
                    """
                    **Merknad** er en praktisk vurdering av managerprofilen: 01 · Tittelkandidat, 02 · Outsider, 03 · Dark horse, 04 · Stabil traver, 05 · Usikkert kort, 06 · Rookie. Tallene står der for at sortering ved kolonneklikk skal bli riktig.  
                    **Nivå** er en ren historikk-rating basert på tidligere FPL-ranker. 01 · Elite er best, deretter Meget sterk, Sterk, Solid, Midtable og Rookie.
                    """
                )

            st.caption(f"Fant {len(table_df)} lag.")

            st.download_button(
                label="Last ned ligadata som CSV",
                data=csv_bytes(table_df, columns, LIGATABELL_LABELS),
                file_name="lro_ligatabell.csv",
                mime="text/csv",
            )

    if "debug" in st.session_state:
        with st.expander("Debug"):
            st.json(st.session_state["debug"])


with tab2:
    st.header("Historikk")
    lro_note("Fortid, ikke framtid", "Historikken viser tidligere FPL-sesonger, beste plassering, siste tre sesonger og meritter fra Lofthus Road Open. Odds er flyttet til Ligatabell.", "")

    league_id_history = st.number_input("Liga-ID", value=DEFAULT_LEAGUE_ID, step=1, key="history_id_v11")

    if st.button("Hent historikk"):
        ensure_history_loaded(int(league_id_history))

    if "summary_df" in st.session_state:
        summary_df = st.session_state["summary_df"]
        seasons_df = st.session_state["seasons_df"]
        errors_df = st.session_state["errors_df"]

        if summary_df.empty:
            st.warning("Fant ingen historikk.")
        else:
            summary = summary_df.copy()
            summary = make_numeric_display(summary, "last_season_rank_num", "last_season_rank_numeric")
            summary = make_numeric_display(summary, "best_rank_num", "best_rank_numeric")
            summary = make_numeric_display(summary, "avg_rank_last_3_num", "avg_rank_last_3_numeric")
            summary = add_sortable_display_columns(summary)
            summary = summary.sort_values(["best_rank_numeric", "manager"], ascending=[True, True], na_position="last").reset_index(drop=True)

            columns = [
                "manager",
                "team",
                "seasons",
                "last_season_rank_numeric",
                "best_rank_numeric",
                "best_season",
                "avg_rank_last_3_numeric",
                "trend",
                "monthly_titles",
                "merits",
                "top_100k_seasons",
                "top_500k_seasons",
                "tier_display",
                "tag_display",
            ]

            display_table(summary, columns, HISTORY_LABELS, column_config=NUMERIC_CONFIG)

            st.download_button(
                label="Last ned historikk som CSV",
                data=csv_bytes(summary, columns, HISTORY_LABELS),
                file_name="lro_historikk.csv",
                mime="text/csv",
            )

            st.subheader("Radar")

            radar_cols = st.columns(4)

            with radar_cols[0]:
                peak = summary_df.sort_values("best_rank_num").iloc[0]
                st.metric("Beste all-time plassering", peak["manager"], peak["best_rank"])

            with radar_cols[1]:
                form = summary_df.sort_values("last_season_rank_num").iloc[0]
                st.metric("Best sist sesong", form["manager"], form["last_season_rank"])

            with radar_cols[2]:
                proven = summary_df.sort_values("top_100k_seasons", ascending=False).iloc[0]
                st.metric("Flest topp 100k", proven["manager"], int(proven["top_100k_seasons"]))

            with radar_cols[3]:
                hof = summary_df.sort_values("hof_score", ascending=False).iloc[0]
                st.metric("Mest merittert", hof["manager"], int(hof["hof_score"]))

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
    st.header("H2H")
    lro_note("Rivalgenerator", "Skriv én duell eller gruppe per linje. H2H-oddsen bygger på historikk, form og dokumentert toppnivå.", "")

    st.write("Skriv én duell eller gruppe per linje. Bruk `vs` mellom navnene.")

    league_id_markets = st.number_input("Liga-ID", value=DEFAULT_LEAGUE_ID, step=1, key="markets_id_v11")
    market_text = st.text_area("Dueller/grupper", value="", height=320)

    if st.button("Lag H2H-odds"):
        ensure_history_loaded(int(league_id_markets))
        summary_df = st.session_state["summary_df"]

        market_df, missing_df = analyze_markets(summary_df, market_text)

        if not market_df.empty:
            st.subheader("Odds")

            st.dataframe(market_df, use_container_width=True, hide_index=True)

            st.download_button(
                label="Last ned H2H-odds som CSV",
                data=market_df.to_csv(index=False).encode("utf-8"),
                file_name="lro_h2h_odds.csv",
                mime="text/csv",
            )
        else:
            st.warning("Fant ingen markeder å vise.")

        if not missing_df.empty:
            with st.expander("Navn appen ikke fant sikkert treff på"):
                st.dataframe(missing_df, use_container_width=True, hide_index=True)


with tab4:
    st.header("Hall of Fame")
    lro_note("Ligaens pokalskap", "Sammenlagtseier vektes tyngst, cupgull deretter, månedsseiere lavere. Månedspodier gir ekstra historisk krydder.", "gold")

    hof_df = build_hof_people()

    if hof_df.empty:
        st.warning("Fant ingen Hall of Fame-data.")
    else:
        most_decorated = hof_df.sort_values("hof_score", ascending=False).iloc[0]
        monthly_king = hof_df.sort_values("monthly_titles", ascending=False).iloc[0]
        overall_king = hof_df.sort_values("overall_count", ascending=False).iloc[0]

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric("Mest merittert", most_decorated["display_name"], int(most_decorated["hof_score"]))

        with c2:
            st.metric("Flest månedsseiere", monthly_king["display_name"], int(monthly_king["monthly_titles"]))

        with c3:
            st.metric("Flest sammenlagtseiere", overall_king["display_name"], int(overall_king["overall_count"]))

        st.subheader("Meritt-tabell")

        hof_columns = [
            "hof_rank",
            "display_name",
            "hof_score",
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
            "merits",
        ]

        display_table(hof_df, hof_columns, HOF_LABELS)

        st.download_button(
            label="Last ned Hall of Fame som CSV",
            data=csv_bytes(hof_df, hof_columns, HOF_LABELS),
            file_name="lro_hall_of_fame.csv",
            mime="text/csv",
        )

        with st.expander("Sesongdetaljer per manager"):
            detail_columns = [
                "display_name",
                "overall_seasons",
                "overall_runner_up_seasons",
                "overall_third_seasons",
                "cup_seasons",
                "cup_runner_up_seasons",
                "random_notes",
            ]
            display_table(hof_df, detail_columns, HOF_LABELS)

        st.subheader("Månedskonger")

        month_specialists = build_month_specialist_table()

        if month_specialists.empty:
            st.warning("Fant ingen månedskonge-data.")
        else:
            month_specialist_columns = [
                "month",
                "king",
                "leaders_count",
                "king_points",
                "month_merits",
                "podiums",
                "comment",
            ]

            display_table(month_specialists, month_specialist_columns, MONTH_SPECIALIST_LABELS)

        st.subheader("Månedsliga")

        monthly_df = build_monthly_podium_df()

        if monthly_df.empty:
            st.warning("Fant ingen månedspodier.")
        else:
            seasons = ["Alle"] + sorted(monthly_df["season"].dropna().unique().tolist())

            selected_season = st.selectbox("Velg sesong", seasons, key="monthly_season_filter_v11")
            monthly_medals = build_monthly_medal_table(selected_season)

            medal_columns = ["monthly_rank", "manager", "month_points", "gold", "silver", "bronze", "podiums"]
            display_table(monthly_medals, medal_columns, MONTHLY_MEDAL_LABELS)

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
        display_table(overall_df, ["season", "winner", "runner_up", "third_place", "note"], OVERALL_LABELS)

        st.subheader("Cupvinnere")
        cup_df = pd.DataFrame(HOF_CUP)
        display_table(cup_df, ["season", "winner", "runner_up"], CUP_LABELS)

        st.subheader("Random plassering")
        random_df = pd.DataFrame(HOF_RANDOM)
        display_table(random_df, ["season", "winner", "placement"], RANDOM_LABELS)


with tab5:
    st.header("Sesongradar")
    lro_note("Blir best når sesongen er i gang", "Her kommer største klatrere, største fall, form siste tre runder og hvem som over-/underpresterer mot før-sesong-odds.", "")

    league_id_radar = st.number_input("Liga-ID", value=DEFAULT_LEAGUE_ID, step=1, key="season_radar_id_v11")

    if st.button("Hent sesongradar"):
        ensure_history_loaded(int(league_id_radar))

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
    lro_note("Ligaen på kartet", "Geografisk fordeling av managerne i ligaen. Meld fra hvis bosted/sted er feil.", "")

    place_df = build_place_data()

    total_people = int(place_df["Antall"].sum())
    top_city = place_df.sort_values("Antall", ascending=False).iloc[0]

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Registrerte på kartet", total_people)

    with c2:
        st.metric("Byer/steder", len(place_df))

    with c3:
        st.metric("Største miljø", top_city["By"], int(top_city["Antall"]))

    if total_people != 37:
        st.info(f"Kartlista summerer til {total_people}. Sjekk om noen mangler sted i lista.")

    if pdk is not None:
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=place_df,
            get_position="[lon, lat]",
            get_radius="radius",
            get_fill_color="[255, 70, 70, 170]",
            get_line_color="[80, 0, 0]",
            line_width_min_pixels=1,
            pickable=True,
        )

        text_layer = pdk.Layer(
            "TextLayer",
            data=place_df,
            get_position="[lon, lat]",
            get_text="Label",
            get_size=16,
            get_color="[30, 30, 30]",
            get_text_anchor='"middle"',
            get_alignment_baseline='"bottom"',
        )

        view_state = pdk.ViewState(latitude=64.9, longitude=13.5, zoom=4.0, pitch=25)

        deck = pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=view_state,
            layers=[layer, text_layer],
            tooltip={
                "html": "<b>{By}</b><br/>{Antall} managers<br/>{Deltakere}",
                "style": {"backgroundColor": "white", "color": "black"},
            },
        )

        st.pydeck_chart(deck, use_container_width=True)

    else:
        map_df = place_df.rename(columns={"lat": "latitude", "lon": "longitude"})
        st.map(map_df, latitude="latitude", longitude="longitude")

    st.subheader("Byranking")

    city_rank = place_df.sort_values(["Antall", "By"], ascending=[False, True]).copy()

    st.bar_chart(city_rank.set_index("By")["Antall"])

    st.dataframe(city_rank[["By", "Antall", "Deltakere"]], use_container_width=True, hide_index=True)
