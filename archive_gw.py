from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lro_analysis import build_ownership, canonical_managers, nint
from lro_archive import SnapshotStore
from lro_fpl import DEFAULT_LEAGUE_ID, FPLClient, finished_event_ids, month_phases, season_label
from lro_history import HistoryStore

DATA = ROOT / "data"


def month_table(histories: dict[int, dict], managers: list[dict], start: int, stop: int) -> list[dict]:
    rows = []
    names = {nint(m.get("entry")): str(m.get("canonical_name") or m.get("player_name") or "") for m in managers}
    teams = {nint(m.get("entry")): str(m.get("entry_name") or "") for m in managers}
    for entry, history in histories.items():
        points = sum(nint(r.get("points")) for r in history.get("current", []) or [] if start <= nint(r.get("event")) <= stop)
        rows.append({"entry": entry, "manager": names.get(entry, ""), "team": teams.get(entry, ""), "points": points})
    rows.sort(key=lambda r: (-r["points"], r["manager"]))
    rank = 0; prev = None
    for idx, row in enumerate(rows, start=1):
        if prev is None or row["points"] != prev:
            rank = idx
        row["rank"] = rank; prev = row["points"]
    return rows



def managers_at_event(managers: list[dict], histories: dict[int, dict], event: int) -> list[dict]:
    rows = []
    for manager in managers:
        entry = nint(manager.get("entry"))
        hist = histories.get(entry, {}) or {}
        current = hist.get("current", []) or []
        hit = next((r for r in current if nint(r.get("event")) == int(event)), None)
        if not hit:
            continue
        prev = next((r for r in current if nint(r.get("event")) == int(event) - 1), None)
        row = dict(manager)
        row["event_total"] = nint(hit.get("points"))
        row["total"] = nint(hit.get("total_points"))
        row["_prev_total"] = nint((prev or {}).get("total_points"))
        rows.append(row)
    rows.sort(key=lambda r: (-nint(r.get("total")), str(r.get("player_name") or "")))
    last_groups = {}
    if event > 1:
        previous = sorted(rows, key=lambda r: (-nint(r.get("_prev_total")), str(r.get("player_name") or "")))
        prev_rank = 0; prev_points = None
        for idx, row in enumerate(previous, start=1):
            pts = nint(row.get("_prev_total"))
            if prev_points is None or pts != prev_points:
                prev_rank = idx
            last_groups[nint(row.get("entry"))] = prev_rank
            prev_points = pts
    rank = 0; prev_points = None
    for idx, row in enumerate(rows, start=1):
        pts = nint(row.get("total"))
        if prev_points is None or pts != prev_points:
            rank = idx
        row["rank"] = rank
        row["last_rank"] = last_groups.get(nint(row.get("entry")), rank)
        row.pop("_prev_total", None)
        prev_points = pts
    return rows

def main() -> None:
    client = FPLClient(timeout=30)
    bootstrap = client.bootstrap()
    finished = finished_event_ids(bootstrap)
    if not finished:
        print("No completed GW yet.")
        return
    history = HistoryStore(DATA)
    _, managers, _ = client.league_managers(DEFAULT_LEAGUE_ID)
    managers = canonical_managers(managers, history)
    store = SnapshotStore(DATA / "snapshots")
    entries = [nint(m.get("entry")) for m in managers if nint(m.get("entry"))]
    histories, _ = client.histories_many(entries, max_workers=10)
    season = season_label(bootstrap)
    written = 0
    for event in finished:
        target = store.path_for(season, event)
        if target.exists():
            continue
        event_managers = managers_at_event(managers, histories, event)
        event_entries = [nint(m.get("entry")) for m in event_managers if nint(m.get("entry"))]
        ownership = build_ownership(client, event_managers, history, event_id=event, only_entries=event_entries, max_workers=10)
        phase = next((p for p in month_phases(bootstrap) if nint(p.get("start_event")) <= event <= nint(p.get("stop_event"))), None)
        month_name = str((phase or {}).get("name") or "")
        month_rows = month_table(histories, managers, nint((phase or {}).get("start_event"), event), event) if phase else []
        payload = store.make_payload(season=season, event=event, managers=event_managers, ownership=ownership, month_name=month_name, month_table=month_rows)
        path = store.write(payload)
        if path:
            written += 1
            print(f"Wrote {path}")
        if event >= 38:
            store.freeze_season_final(payload)
    if not written:
        print("All completed gameweeks are already archived.")


if __name__ == "__main__":
    main()
