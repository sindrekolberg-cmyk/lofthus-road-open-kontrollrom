from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from api.platform_store import platform_store
from lro_analysis import nint


class LeagueJournal:
    """Compact season journal for features that need league memory.

    We keep one frozen reveal and one final verdict per GW. That is enough to
    reconstruct captain patterns, hits, chip usage, squad similarity, ownership
    shifts, rival history and future manager-DNA features without storing every
    live poll.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.path = Path("/tmp/lofthus-league-journal.json")
        self._table_ready = False

    def _ensure_table(self) -> bool:
        if not platform_store._ensure_db():
            return False
        if self._table_ready:
            return True
        try:
            with platform_store._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS league_round_journal (
                            league_id BIGINT NOT NULL,
                            event_id INTEGER NOT NULL,
                            kind TEXT NOT NULL,
                            payload JSONB NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            PRIMARY KEY (league_id, event_id, kind)
                        );
                        CREATE INDEX IF NOT EXISTS league_round_journal_event_idx
                            ON league_round_journal (league_id, event_id);
                        """
                    )
                conn.commit()
            self._table_ready = True
            return True
        except Exception as exc:
            platform_store.last_db_error = str(exc)[:500]
            return False

    def _read_local(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_local(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _payload(engine: Any, state: Any, kind: str) -> dict[str, Any]:
        managers = [
            {
                "entry": row.entry,
                "manager": row.manager,
                "team": row.team,
                "rank": row.live_rank,
                "total": row.live_total_points,
                "gw": row.live_gw_points,
                "rank_change": row.live_rank_change,
                "month_rank": row.month_rank,
                "month_points": row.month_points,
                "captain": row.captain,
                "captain_element": row.captain_element,
                "chip": row.active_chip or "",
                "hits": nint(row.transfer_hits),
                "team_value": row.team_value,
                "bank": row.bank,
            }
            for row in state.managers_by_rank()
        ]
        picks = (state.ownership or {}).get("picks")
        raw_picks = []
        if picks is not None and hasattr(picks, "to_dict") and not getattr(picks, "empty", True):
            for row in picks.to_dict("records"):
                entry = nint(row.get("entry"))
                element = nint(row.get("element"))
                if not entry or not element:
                    continue
                raw_picks.append(
                    {
                        "entry": entry,
                        "element": element,
                        "player": str(row.get("player") or ""),
                        "multiplier": nint(row.get("multiplier")),
                        "captain": bool(row.get("is_captain")),
                        "vice": bool(row.get("is_vice_captain")),
                        "bench": bool(row.get("on_bench")) or nint(row.get("multiplier")) == 0,
                    }
                )
        return {
            "version": 1,
            "league_id": int(engine.config.league_id),
            "league_name": str(engine.config.name),
            "event_id": int(state.event_id),
            "kind": kind,
            "event_status": str(state.event_status),
            "source_updated_at": state.fetched_at.isoformat(),
            "managers": managers,
            "picks": raw_picks,
        }

    def record(self, engine: Any, state: Any, kind: str) -> bool:
        kind = str(kind or "").strip().lower()
        if kind not in {"reveal", "verdict"} or not state or not nint(state.event_id):
            return False
        payload = self._payload(engine, state, kind)
        league_id = int(engine.config.league_id)
        event_id = int(state.event_id)

        if self._ensure_table():
            try:
                with platform_store._connect() as conn:
                    with conn.cursor() as cur:
                        # Reveal is intentionally first-write-wins so late autosubs
                        # cannot rewrite what rivals actually revealed at deadline.
                        if kind == "reveal":
                            cur.execute(
                                """
                                INSERT INTO league_round_journal (league_id, event_id, kind, payload)
                                VALUES (%s, %s, %s, %s::jsonb)
                                ON CONFLICT (league_id, event_id, kind) DO NOTHING
                                """,
                                (league_id, event_id, kind, json.dumps(payload)),
                            )
                        else:
                            cur.execute(
                                """
                                INSERT INTO league_round_journal (league_id, event_id, kind, payload)
                                VALUES (%s, %s, %s, %s::jsonb)
                                ON CONFLICT (league_id, event_id, kind) DO UPDATE SET
                                    payload = EXCLUDED.payload,
                                    updated_at = NOW()
                                """,
                                (league_id, event_id, kind, json.dumps(payload)),
                            )
                    conn.commit()
                return True
            except Exception as exc:
                platform_store.last_db_error = str(exc)[:500]

        with self._lock:
            data = self._read_local()
            key = f"{league_id}:{event_id}:{kind}"
            if kind == "reveal" and key in data:
                return True
            data[key] = payload
            self._write_local(data)
        return True

    def get(self, league_id: int, event_id: int, kind: str) -> dict[str, Any] | None:
        if self._ensure_table():
            try:
                with platform_store._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT payload FROM league_round_journal WHERE league_id=%s AND event_id=%s AND kind=%s",
                            (int(league_id), int(event_id), str(kind)),
                        )
                        row = cur.fetchone()
                return dict(row[0] or {}) if row else None
            except Exception as exc:
                platform_store.last_db_error = str(exc)[:500]
        return self._read_local().get(f"{int(league_id)}:{int(event_id)}:{str(kind)}")

    def diagnostics(self) -> dict[str, Any]:
        return {
            "backend": "postgres" if self._ensure_table() else "local-json",
            "durable": bool(platform_store.durable and self._table_ready),
            "captures": ["reveal", "verdict"],
        }


league_journal = LeagueJournal()
