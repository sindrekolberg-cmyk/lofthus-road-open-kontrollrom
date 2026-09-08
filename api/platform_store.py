from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PlatformStore:
    """Postgres-first persistence for product state outside FPL itself.

    FPL remains the source of truth for scores and squads. This store owns the
    things the product needs to survive restarts: connected leagues, anonymous
    app profiles and durable cursors for background jobs. Local JSON is only a
    development/fallback mode.
    """

    def __init__(self, database_url: str | None = None, path: str | None = None):
        self.database_url = str(database_url or os.getenv("DATABASE_URL", "")).strip()
        self.path = Path(path or os.getenv("LRO_PLATFORM_STORE_PATH", "").strip() or "/tmp/lofthus-platform-state.json")
        self._lock = threading.RLock()
        self._db_lock = threading.Lock()
        self._db_initialized = False
        self.last_db_error = ""

    def _connect(self):
        if not self.database_url:
            raise RuntimeError("DATABASE_URL er ikke satt.")
        import psycopg
        return psycopg.connect(self.database_url, connect_timeout=5)

    def _ensure_db(self) -> bool:
        if not self.database_url:
            return False
        if self._db_initialized:
            return True
        with self._db_lock:
            if self._db_initialized:
                return True
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            CREATE TABLE IF NOT EXISTS app_leagues (
                                league_id BIGINT PRIMARY KEY,
                                name TEXT NOT NULL,
                                season TEXT NOT NULL DEFAULT '',
                                manager_count INTEGER NOT NULL DEFAULT 0,
                                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            );
                            CREATE TABLE IF NOT EXISTS app_profiles (
                                installation_id TEXT PRIMARY KEY,
                                league_id BIGINT NOT NULL,
                                entry_id BIGINT NOT NULL,
                                goal TEXT NOT NULL DEFAULT 'auto',
                                app_version TEXT NOT NULL DEFAULT '',
                                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            );
                            CREATE TABLE IF NOT EXISTS runtime_cursors (
                                cursor_key TEXT PRIMARY KEY,
                                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            );
                            CREATE INDEX IF NOT EXISTS app_profiles_league_entry_idx
                                ON app_profiles (league_id, entry_id);
                            """
                        )
                    conn.commit()
                self._db_initialized = True
                self.last_db_error = ""
                return True
            except Exception as exc:
                self.last_db_error = str(exc)[:500]
                return False

    @property
    def backend(self) -> str:
        return "postgres" if self._ensure_db() else "local-json"

    @property
    def durable(self) -> bool:
        return self.backend == "postgres"

    def _read_local(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _write_local(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.path)

    def upsert_league(
        self,
        league_id: int,
        *,
        name: str,
        season: str = "",
        manager_count: int = 0,
        is_default: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        league_id = int(league_id)
        payload = dict(metadata or {})
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO app_leagues (
                                league_id, name, season, manager_count, is_default,
                                metadata, created_at, last_seen_at
                            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                            ON CONFLICT (league_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                season = EXCLUDED.season,
                                manager_count = EXCLUDED.manager_count,
                                is_default = EXCLUDED.is_default,
                                metadata = app_leagues.metadata || EXCLUDED.metadata,
                                last_seen_at = NOW()
                            """,
                            (league_id, str(name), str(season), int(manager_count), bool(is_default), json.dumps(payload)),
                        )
                    conn.commit()
                return
            except Exception as exc:
                self.last_db_error = str(exc)[:500]
        with self._lock:
            data = self._read_local()
            leagues = data.setdefault("leagues", {})
            existing = leagues.get(str(league_id), {}) if isinstance(leagues, dict) else {}
            leagues[str(league_id)] = {
                **existing,
                "league_id": league_id,
                "name": str(name),
                "season": str(season),
                "manager_count": int(manager_count),
                "is_default": bool(is_default),
                "metadata": {**dict(existing.get("metadata") or {}), **payload},
                "created_at": existing.get("created_at") or _now(),
                "last_seen_at": _now(),
            }
            self._write_local(data)

    def upsert_profile(
        self,
        installation_id: str,
        *,
        league_id: int,
        entry_id: int,
        goal: str = "auto",
        app_version: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        installation_id = str(installation_id or "").strip()
        if len(installation_id) < 12 or len(installation_id) > 160:
            raise ValueError("Ugyldig installation_id.")
        payload = dict(metadata or {})
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO app_profiles (
                                installation_id, league_id, entry_id, goal,
                                app_version, metadata, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                            ON CONFLICT (installation_id) DO UPDATE SET
                                league_id = EXCLUDED.league_id,
                                entry_id = EXCLUDED.entry_id,
                                goal = EXCLUDED.goal,
                                app_version = EXCLUDED.app_version,
                                metadata = app_profiles.metadata || EXCLUDED.metadata,
                                updated_at = NOW()
                            RETURNING installation_id, league_id, entry_id, goal,
                                      app_version, metadata, created_at, updated_at
                            """,
                            (installation_id, int(league_id), int(entry_id), str(goal or "auto"), str(app_version or ""), json.dumps(payload)),
                        )
                        row = cur.fetchone()
                    conn.commit()
                if row:
                    return {
                        "installation_id": row[0], "league_id": int(row[1]), "entry_id": int(row[2]),
                        "goal": row[3], "app_version": row[4], "metadata": dict(row[5] or {}),
                        "created_at": row[6].isoformat(), "updated_at": row[7].isoformat(),
                    }
            except Exception as exc:
                self.last_db_error = str(exc)[:500]
        with self._lock:
            data = self._read_local()
            profiles = data.setdefault("profiles", {})
            existing = profiles.get(installation_id, {}) if isinstance(profiles, dict) else {}
            record = {
                **existing,
                "installation_id": installation_id,
                "league_id": int(league_id),
                "entry_id": int(entry_id),
                "goal": str(goal or "auto"),
                "app_version": str(app_version or ""),
                "metadata": {**dict(existing.get("metadata") or {}), **payload},
                "created_at": existing.get("created_at") or _now(),
                "updated_at": _now(),
            }
            profiles[installation_id] = record
            self._write_local(data)
            return record

    def get_profile(self, installation_id: str) -> dict[str, Any] | None:
        installation_id = str(installation_id or "").strip()
        if not installation_id:
            return None
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT installation_id, league_id, entry_id, goal,
                                   app_version, metadata, created_at, updated_at
                            FROM app_profiles WHERE installation_id = %s
                            """,
                            (installation_id,),
                        )
                        row = cur.fetchone()
                if not row:
                    return None
                return {
                    "installation_id": row[0], "league_id": int(row[1]), "entry_id": int(row[2]),
                    "goal": row[3], "app_version": row[4], "metadata": dict(row[5] or {}),
                    "created_at": row[6].isoformat(), "updated_at": row[7].isoformat(),
                }
            except Exception as exc:
                self.last_db_error = str(exc)[:500]
        with self._lock:
            return (self._read_local().get("profiles") or {}).get(installation_id)

    def set_cursor(self, key: str, payload: dict[str, Any]) -> None:
        key = str(key or "").strip()
        if not key:
            return
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO runtime_cursors (cursor_key, payload, updated_at)
                            VALUES (%s, %s::jsonb, NOW())
                            ON CONFLICT (cursor_key) DO UPDATE SET
                                payload = EXCLUDED.payload,
                                updated_at = NOW()
                            """,
                            (key, json.dumps(payload or {})),
                        )
                    conn.commit()
                return
            except Exception as exc:
                self.last_db_error = str(exc)[:500]
        with self._lock:
            data = self._read_local()
            cursors = data.setdefault("cursors", {})
            cursors[key] = {"payload": dict(payload or {}), "updated_at": _now()}
            self._write_local(data)

    def get_cursor(self, key: str) -> dict[str, Any] | None:
        key = str(key or "").strip()
        if not key:
            return None
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT payload FROM runtime_cursors WHERE cursor_key = %s", (key,))
                        row = cur.fetchone()
                return dict(row[0] or {}) if row else None
            except Exception as exc:
                self.last_db_error = str(exc)[:500]
        with self._lock:
            row = ((self._read_local().get("cursors") or {}).get(key) or {})
            return dict(row.get("payload") or {}) if row else None

    def diagnostics(self) -> dict[str, Any]:
        local = self._read_local() if not self._ensure_db() else {}
        return {
            "backend": self.backend,
            "durable": self.durable,
            "database_configured": bool(self.database_url),
            "database_error": self.last_db_error or None,
            "local_leagues": len(local.get("leagues") or {}),
            "local_profiles": len(local.get("profiles") or {}),
            "local_cursors": len(local.get("cursors") or {}),
        }


platform_store = PlatformStore()
