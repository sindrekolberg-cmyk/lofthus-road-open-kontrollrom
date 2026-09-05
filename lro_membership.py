from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from lro_history import clean_cell


MEMBERSHIP_COLUMNS = [
    "season",
    "league_id",
    "entry_id",
    "manager",
    "team",
    "final_rank",
    "points",
    "member",
]


def load_membership(data_dir: str | Path) -> list[dict[str, Any]]:
    """Documented Lofthus membership only. Never inferred from FPL past seasons."""
    path = Path(data_dir) / "membership.csv"
    if not path.exists():
        return []
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception:
        return []
    for col in MEMBERSHIP_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    rows = []
    for r in df.to_dict("records"):
        member = str(r.get("member") or "").strip().casefold() in {"1", "true", "yes", "ja"}
        if not member:
            continue
        rows.append({
            "season": clean_cell(r.get("season")),
            "league_id": clean_cell(r.get("league_id")),
            "entry_id": clean_cell(r.get("entry_id")),
            "manager": clean_cell(r.get("manager")),
            "team": clean_cell(r.get("team")),
            "final_rank": clean_cell(r.get("final_rank")),
            "points": clean_cell(r.get("points")),
            "member": True,
        })
    return rows


def membership_for(rows: list[dict[str, Any]], *, entry_id: int | None = None, manager: str = "") -> list[dict[str, Any]]:
    out = []
    entry = str(int(entry_id)) if entry_id else ""
    for r in rows:
        if entry and str(r.get("entry_id") or "") == entry:
            out.append(r)
        elif manager and str(r.get("manager") or "") == manager and not entry:
            out.append(r)
    return out
