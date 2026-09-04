from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from lro_fpl import DEFAULT_LEAGUE_ID


@dataclass(frozen=True)
class LeagueConfig:
    league_id: int
    name: str
    season_fallback: str
    data_dir: Path
    expected_managers: int | None = None


def load_config(base_dir: Path | None = None) -> LeagueConfig:
    root = Path(base_dir or Path(__file__).resolve().parent)
    data_dir = root / os.getenv("LRO_DATA_DIR", "data")
    try:
        league_id = int(os.getenv("LRO_LEAGUE_ID", str(DEFAULT_LEAGUE_ID)))
    except Exception:
        league_id = DEFAULT_LEAGUE_ID
    raw_expected = os.getenv("LRO_EXPECTED_MANAGERS", "63").strip()
    try:
        expected = int(raw_expected) if raw_expected else None
    except Exception:
        expected = None
    return LeagueConfig(
        league_id=league_id,
        name=os.getenv("LRO_LEAGUE_NAME", "Lofthus Road Open").strip() or "Lofthus Road Open",
        season_fallback=os.getenv("LRO_SEASON", "2026/27").strip() or "2026/27",
        data_dir=data_dir,
        expected_managers=expected,
    )
