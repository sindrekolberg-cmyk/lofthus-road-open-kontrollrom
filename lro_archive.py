from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _safe(value: Any) -> Any:
    """Convert pandas/numpy-ish values into plain JSON values."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class SnapshotStore:
    """Best-effort LRO archive stored as versionable JSON files.

    Streamlit Cloud's local filesystem is not a substitute for Git history. The
    important property here is that snapshots use a stable, repo-friendly format:
    when `data/snapshots/` is committed (or synced by a future persistence hook),
    the app can read old rounds without depending on FPL keeping private-league
    tables forever.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)

    @staticmethod
    def filename(season: str, event: int) -> str:
        clean_season = str(season or "season").replace("/", "-").replace(" ", "_")
        return f"{clean_season}_GW{int(event):02d}.json"

    def path_for(self, season: str, event: int) -> Path:
        return self.root / self.filename(season, event)

    def list_snapshots(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("*_GW*.json"))

    def final_path_for(self, season: str) -> Path:
        clean_season = str(season or "season").replace("/", "-").replace(" ", "_")
        return self.root / f"{clean_season}_FINAL.json"

    def freeze_season_final(self, payload: dict) -> Path | None:
        """Create an immutable season-final snapshot after GW38."""
        if int(payload.get("event") or 0) < 38:
            return None
        path = self.final_path_for(str(payload.get("season") or ""))
        if path.exists():
            return path
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            final_payload = dict(payload)
            final_payload["season_final"] = True
            body = json.dumps(_safe(final_payload), ensure_ascii=False, indent=2, sort_keys=False)
            fd, tmp_name = tempfile.mkstemp(prefix="lro_final_", suffix=".json", dir=str(self.root))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(body)
                    handle.write("\n")
                os.replace(tmp_name, path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            return path
        except Exception:
            return None

    def read(self, season: str, event: int) -> dict:
        path = self.path_for(season, event)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def write(self, payload: dict, *, replace: bool = False) -> Path | None:
        season = str(payload.get("season") or "")
        event = int(payload.get("event") or 0)
        if not season or event <= 0:
            return None
        path = self.path_for(season, event)
        if path.exists() and not replace:
            # Never rewrite sporting history merely because the app rerendered.
            return path
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            body = json.dumps(_safe(payload), ensure_ascii=False, indent=2, sort_keys=False)
            fd, tmp_name = tempfile.mkstemp(prefix="lro_snapshot_", suffix=".json", dir=str(self.root))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(body)
                    handle.write("\n")
                os.replace(tmp_name, path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
            return path
        except Exception:
            # Archiving must never take down the live product.
            return None

    def make_payload(
        self,
        *,
        season: str,
        event: int,
        managers: list[dict],
        ownership: dict | None = None,
        month_name: str = "",
        month_table: list[dict] | None = None,
    ) -> dict:
        ownership = ownership or {}
        manager_events = ownership.get("manager_events", pd.DataFrame())
        picks = ownership.get("picks", pd.DataFrame())
        event_by_entry = {}
        if isinstance(manager_events, pd.DataFrame) and not manager_events.empty:
            event_by_entry = {int(r.get("entry")): r for r in manager_events.to_dict("records") if r.get("entry")}

        table = []
        for m in sorted(managers, key=lambda r: (int(r.get("rank") or 10**9), -int(r.get("total") or 0))):
            entry = int(m.get("entry") or 0)
            ev = event_by_entry.get(entry, {})
            table.append({
                "entry": entry,
                "manager": m.get("canonical_name") or m.get("player_name") or "",
                "team": m.get("entry_name") or "",
                "rank": m.get("rank"),
                "last_rank": m.get("last_rank"),
                "gw_points": ev.get("gw_points", m.get("event_total")),
                "total_points": ev.get("total_points", m.get("total")),
                "chip": ev.get("active_chip") or "",
                "bank": ev.get("bank"),
                "team_value": ev.get("team_value"),
            })

        pick_rows = []
        if isinstance(picks, pd.DataFrame) and not picks.empty:
            keep = [
                "entry", "manager", "element", "player", "club", "position",
                "current_price", "selling_price", "squad_position", "multiplier",
                "is_captain", "is_vice_captain", "is_triple_captain", "on_bench",
                "event_points", "gw_contribution", "active_chip",
            ]
            available = [c for c in keep if c in picks.columns]
            pick_rows = picks[available].to_dict("records")

        return {
            "schema_version": 1,
            "season": season,
            "event": int(event),
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "complete_picks": bool(pick_rows) and int(ownership.get("loaded_managers") or 0) >= len(managers),
            "league_size": len(managers),
            "table": table,
            "picks": pick_rows,
            "month": {"name": month_name, "table": month_table or []},
        }
