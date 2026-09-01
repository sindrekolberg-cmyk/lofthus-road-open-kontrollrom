from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd

MONTH_ORDER = {
    "August": 1, "September": 2, "Oktober": 3, "November": 4, "Desember": 5,
    "Januar": 6, "Februar": 7, "Mars": 8, "April": 9, "Mai": 10,
}

# Bekreftet i LRO for august 2026. Brukes kun dersom denne måneden ikke finnes i CSV/API.

# FPL-historikk for tidligere LRO-managere som ikke lenger finnes i dagens liga.
# Kun sesonger fra Lofthus Road Open startet (2020/21) tas med.
# Kilde: managerens FPL "Previous Seasons"-side, dokumentert 1. september 2026.
ALUMNI_SEASON_HISTORY = [
    {"manager": "Øyvind Nordmo Sivertsen", "season": "2020/21", "total_points": 2515, "overall_rank": 4759, "source": "FPL Previous Seasons"},
    {"manager": "Øyvind Nordmo Sivertsen", "season": "2021/22", "total_points": 2599, "overall_rank": 19100, "source": "FPL Previous Seasons"},
    {"manager": "Øyvind Nordmo Sivertsen", "season": "2022/23", "total_points": 2429, "overall_rank": 477228, "source": "FPL Previous Seasons"},
    {"manager": "Øyvind Nordmo Sivertsen", "season": "2023/24", "total_points": 2557, "overall_rank": 17663, "source": "FPL Previous Seasons"},
    {"manager": "Øyvind Nordmo Sivertsen", "season": "2024/25", "total_points": 2488, "overall_rank": 158118, "source": "FPL Previous Seasons"},
    {"manager": "Øyvind Nordmo Sivertsen", "season": "2025/26", "total_points": 2244, "overall_rank": 496413, "source": "FPL Previous Seasons"},
]

CURRENT_SEASON_FALLBACK_PODIUMS = [
    {"season": "2026/27", "month": "August", "place": 1, "manager": "Vegard Røstby", "status": "Bekreftet", "source": "LRO"},
    {"season": "2026/27", "month": "August", "place": 2, "manager": "Edward Stenlund", "status": "Bekreftet", "source": "LRO"},
    {"season": "2026/27", "month": "August", "place": 3, "manager": "Kristoffer W Pettersen", "status": "Bekreftet", "source": "LRO"},
]

FALLBACK_ALIASES = {
    "Adrian Auke": ["Adrian Auke", "Adrian Tangen Auke"],
    "Kevin Jørgensen": ["Kevin Jørgensen", "Kevin Andre Dybfest Jørgensen", "Kevin André Dybfest Jørgensen"],
    "Mattias Pettersen": ["Mattias Pettersen", "Matias Pettersen", "Matias Leander Pettersen"],
    "Oskar Kristensen Brun": ["Oskar Brun", "Oskar Kristensen Brun"],
    "Kristoffer W Pettersen": ["Kristoffer W Pettersen", "Kristoffer Wollvik Pettersen"],
    "Mats Arntzen": ["Mats Arntzen", "Mats Øyvind Jacobsen Arntzen"],
    "Mikael Eliassen": ["Mikael Eliassen", "Mikael Andre Eliassen", "Mikael André Eliassen"],
    "Remi Kristiansen": ["Remi Kristiansen", "Remi Andre Kristiansen", "Remi André Kristiansen"],
    "Andreas Løkås": ["Andreas Løkås", "Andreas Nikolai Løkås"],
    "Øyvind Nordmo Sivertsen": ["Nordmo Sivertsen", "Øyvind Nordmo", "Øyvind Nordmo Sivertsen"],
}


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


class HistoryStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.aliases = self._load_aliases()
        self._alias_index = self._build_alias_index()

    def _read(self, filename: str, columns: list[str]) -> pd.DataFrame:
        path = self.data_dir / filename
        if not path.exists():
            return pd.DataFrame(columns=columns)
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False)
        except Exception:
            return pd.DataFrame(columns=columns)
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df[columns].copy()
        for col in columns:
            df[col] = df[col].map(clean_cell)
        return df

    def _load_aliases(self) -> dict[str, list[str]]:
        df = self._read("aliases.csv", ["canonical_name", "alias"])
        out: dict[str, list[str]] = {}
        for row in df.to_dict("records"):
            canonical = clean_cell(row.get("canonical_name"))
            alias = clean_cell(row.get("alias"))
            if canonical and alias:
                out.setdefault(canonical, [])
                if alias not in out[canonical]:
                    out[canonical].append(alias)
        for canonical, aliases in FALLBACK_ALIASES.items():
            out.setdefault(canonical, [])
            for alias in aliases:
                if alias not in out[canonical]:
                    out[canonical].append(alias)
        return out

    def _build_alias_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for canonical, aliases in self.aliases.items():
            index[normalize_text(canonical)] = canonical
            for alias in aliases:
                index[normalize_text(alias)] = canonical
        return index

    def canonical(self, name: str) -> str:
        raw = str(name or "").strip()
        return self._alias_index.get(normalize_text(raw), raw)

    def key(self, name: str) -> str:
        return normalize_text(self.canonical(name))

    def overall_results(self) -> pd.DataFrame:
        df = self._read("overall_results.csv", ["season", "winner", "runner_up", "third_place", "note", "status", "source"])
        if not df.empty:
            df = df[df["winner"] != ""].copy()
        return df

    def cup_results(self) -> pd.DataFrame:
        df = self._read("cup_results.csv", ["season", "winner", "runner_up", "note", "status", "source"])
        if not df.empty:
            df = df[df["winner"] != ""].copy()
        return df

    def random_results(self) -> pd.DataFrame:
        df = self._read("random_results.csv", ["season", "winner", "placement", "note", "status", "source"])
        if not df.empty:
            df = df[df["winner"] != ""].copy()
        return df

    def static_monthly_podiums(self) -> pd.DataFrame:
        df = self._read("monthly_podiums.csv", ["season", "month", "place", "manager", "status", "source"])
        if df.empty:
            return df
        df = df[(df["season"] != "") & (df["month"] != "") & (df["manager"] != "")].copy()
        df["place"] = pd.to_numeric(df["place"], errors="coerce").fillna(0).astype(int)
        return df[df["place"].between(1, 3)].copy()

    def official_monthly_titles(self) -> dict[str, int]:
        df = self._read("official_monthly_titles.csv", ["manager", "monthly_titles", "status", "source"])
        out: dict[str, int] = {}
        for row in df.to_dict("records"):
            manager = clean_cell(row.get("manager"))
            if not manager:
                continue
            try:
                count = int(float(row.get("monthly_titles") or 0))
            except Exception:
                count = 0
            out[self.key(manager)] = count
        return out

    def monthly_podiums(self, auto_rows: list[dict] | None = None) -> pd.DataFrame:
        static = self.static_monthly_podiums()
        rows = static.to_dict("records") if not static.empty else []
        static_keys = {
            (str(r.get("season") or ""), str(r.get("month") or ""), int(r.get("place") or 0))
            for r in rows
        }
        for row in CURRENT_SEASON_FALLBACK_PODIUMS:
            key = (row["season"], row["month"], int(row["place"]))
            if key not in static_keys:
                rows.append(dict(row))
        for row in auto_rows or []:
            try:
                key = (str(row.get("season") or ""), str(row.get("month") or ""), int(row.get("place") or 0))
            except Exception:
                continue
            # API result wins over the fallback, but not an explicit static CSV record.
            if key in static_keys:
                continue
            rows = [r for r in rows if (str(r.get("season") or ""), str(r.get("month") or ""), int(r.get("place") or 0)) != key]
            rows.append(dict(row))
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["season", "month", "place", "manager", "status", "source", "month_order"])
        for col in ["season", "month", "manager", "status", "source"]:
            if col not in df.columns:
                df[col] = ""
        df["place"] = pd.to_numeric(df.get("place"), errors="coerce").fillna(0).astype(int)
        df = df[df["place"].between(1, 3)].copy()
        df["manager"] = df["manager"].map(self.canonical)
        df["month_order"] = df["month"].map(MONTH_ORDER).fillna(99).astype(int)
        return df.drop_duplicates(["season", "month", "place"], keep="last").sort_values(["season", "month_order", "place", "manager"]).reset_index(drop=True)

    def monthly_medals(self, auto_rows: list[dict] | None = None, season: str | None = None) -> pd.DataFrame:
        df = self.monthly_podiums(auto_rows)
        if season and season != "Alle":
            df = df[df["season"] == season]
        if df.empty:
            return pd.DataFrame(columns=["rank", "manager", "gold", "silver", "bronze", "podiums"])
        grouped = df.groupby("manager").agg(
            gold=("place", lambda s: int((s == 1).sum())),
            silver=("place", lambda s: int((s == 2).sum())),
            bronze=("place", lambda s: int((s == 3).sum())),
            podiums=("place", "count"),
        ).reset_index()
        # Olympic order: gold, then silver, then bronze.
        grouped = grouped.sort_values(["gold", "silver", "bronze", "manager"], ascending=[False, False, False, True]).reset_index(drop=True)
        grouped.insert(0, "rank", range(1, len(grouped) + 1))
        return grouped

    def monthly_calendar(self, auto_rows: list[dict] | None = None, season: str | None = None) -> pd.DataFrame:
        df = self.monthly_podiums(auto_rows)
        if season and season != "Alle":
            df = df[df["season"] == season]
        if df.empty:
            return pd.DataFrame(columns=["season", "month", "winner", "runner_up", "third"])
        rows = []
        for (season_name, order, month), block in df.groupby(["season", "month_order", "month"]):
            item = {"season": season_name, "month_order": order, "month": month, "winner": "", "runner_up": "", "third": ""}
            for r in block.to_dict("records"):
                place = int(r["place"])
                if place == 1:
                    item["winner"] = r["manager"]
                elif place == 2:
                    item["runner_up"] = r["manager"]
                elif place == 3:
                    item["third"] = r["manager"]
            rows.append(item)
        return pd.DataFrame(rows).sort_values(["season", "month_order"]).reset_index(drop=True)

    def hall_of_fame(self, auto_rows: list[dict] | None = None) -> pd.DataFrame:
        people: dict[str, dict] = {}

        def ensure(name: str) -> dict | None:
            if not str(name or "").strip():
                return None
            canonical = self.canonical(name)
            key = self.key(canonical)
            if key not in people:
                people[key] = {
                    "key": key,
                    "display_name": canonical,
                    "league_gold": 0, "league_silver": 0, "league_bronze": 0,
                    "cup_gold": 0, "cup_silver": 0,
                    "monthly_gold_detail": 0, "monthly_silver": 0, "monthly_bronze": 0,
                    "monthly_podiums": 0,
                    "league_seasons": [], "cup_seasons": [],
                }
            return people[key]

        for r in self.overall_results().to_dict("records"):
            for field, metric in [("winner", "league_gold"), ("runner_up", "league_silver"), ("third_place", "league_bronze")]:
                p = ensure(r.get(field, ""))
                if p:
                    p[metric] += 1
                    if field == "winner":
                        p["league_seasons"].append(str(r.get("season") or ""))

        for r in self.cup_results().to_dict("records"):
            p = ensure(r.get("winner", ""))
            if p:
                p["cup_gold"] += 1
                p["cup_seasons"].append(str(r.get("season") or ""))
            p = ensure(r.get("runner_up", ""))
            if p:
                p["cup_silver"] += 1

        monthly = self.monthly_podiums(auto_rows)
        static_monthly = self.static_monthly_podiums()
        static_gold_by_key: dict[str, int] = {}
        if not static_monthly.empty:
            for r in static_monthly.to_dict("records"):
                if int(r.get("place") or 0) == 1:
                    k = self.key(str(r.get("manager") or ""))
                    static_gold_by_key[k] = static_gold_by_key.get(k, 0) + 1

        for r in monthly.to_dict("records"):
            p = ensure(r.get("manager", ""))
            if not p:
                continue
            place = int(r.get("place") or 0)
            if place == 1:
                p["monthly_gold_detail"] += 1
            elif place == 2:
                p["monthly_silver"] += 1
            elif place == 3:
                p["monthly_bronze"] += 1
            p["monthly_podiums"] += 1

        official = self.official_monthly_titles()
        for key in official:
            if key not in people:
                # Preserve official counts even if the person is absent from other CSVs.
                display = next((c for c in self.aliases if self.key(c) == key), key.title())
                ensure(display)

        rows = []
        for p in people.values():
            # `official_monthly_titles.csv` can contain historical wins that are not
            # fully detailed in monthly_podiums.csv. Add only newly reconstructed /
            # current-season wins on top of that official baseline.
            static_gold = int(static_gold_by_key.get(p["key"], 0))
            dynamic_gold = max(0, int(p["monthly_gold_detail"]) - static_gold)
            monthly_gold = int(official.get(p["key"], static_gold)) + dynamic_gold
            gold = int(p["league_gold"] + p["cup_gold"] + monthly_gold)
            silver = int(p["league_silver"] + p["cup_silver"] + p["monthly_silver"])
            bronze = int(p["league_bronze"] + p["monthly_bronze"])
            rows.append({
                **p,
                "monthly_gold": monthly_gold,
                "gold": gold,
                "silver": silver,
                "bronze": bronze,
                "podiums": gold + silver + bronze,
            })
        if not rows:
            return pd.DataFrame()
        # Hall of Fame hierarchy: season championships are the premier honour.
        # Cup wins and monthly wins separate managers after league titles, followed
        # by the remaining podium record. This avoids treating every "gold" as
        # equal and ensures the most successful league champions rank highest.
        sort_cols = [
            "league_gold",
            "cup_gold",
            "monthly_gold",
            "league_silver",
            "league_bronze",
            "cup_silver",
            "monthly_silver",
            "monthly_bronze",
            "display_name",
        ]
        ascending = [False, False, False, False, False, False, False, False, True]
        df = pd.DataFrame(rows).sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
        return df

    def alumni_season_history(self) -> pd.DataFrame:
        """Known previous-season FPL history for former LRO managers.

        This is intentionally small and source-backed. It must never invent
        membership or points for a season we have not documented.
        """
        rows = []
        for row in ALUMNI_SEASON_HISTORY:
            item = dict(row)
            item["manager"] = self.canonical(str(item.get("manager") or ""))
            rows.append(item)
        return pd.DataFrame(rows, columns=["manager", "season", "total_points", "overall_rank", "source"])

    def merits_for(self, name: str, auto_rows: list[dict] | None = None) -> dict:
        hof = self.hall_of_fame(auto_rows)
        if hof.empty:
            return {}
        key = self.key(name)
        row = hof[hof["key"] == key]
        return row.iloc[0].to_dict() if not row.empty else {}

    def overall_for(self, name: str) -> list[dict]:
        key = self.key(name)
        out = []
        for r in self.overall_results().to_dict("records"):
            if self.key(r.get("winner", "")) == key:
                out.append({"season": r.get("season"), "place": 1})
            elif self.key(r.get("runner_up", "")) == key:
                out.append({"season": r.get("season"), "place": 2})
            elif self.key(r.get("third_place", "")) == key:
                out.append({"season": r.get("season"), "place": 3})
        return out

    def best_finish(self, name: str) -> int | None:
        results = self.overall_for(name)
        return min((int(r["place"]) for r in results), default=None)
