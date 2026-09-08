from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
DEFAULT_LEAGUE_ID = 25220


def is_expo_push_token(token: str) -> bool:
    token = str(token or "").strip()
    return (
        (token.startswith("ExpoPushToken[") or token.startswith("ExponentPushToken["))
        and token.endswith("]")
        and len(token) > 24
    )


class PushStore:
    """Push subscription store with Postgres-first persistence.

    `DATABASE_URL` turns persistence on. If Postgres is unavailable the service
    deliberately falls back to the previous local JSON store so push endpoints
    keep functioning instead of taking the whole API down.
    """

    def __init__(self, path: str | None = None, database_url: str | None = None):
        self.path = Path(
            path
            or os.getenv("LRO_PUSH_STORE_PATH", "").strip()
            or "/tmp/lofthus-push-subscriptions.json"
        )
        self.database_url = str(database_url or os.getenv("DATABASE_URL", "")).strip()
        self._lock = threading.Lock()
        self._db_init_lock = threading.Lock()
        self._db_initialized = False
        self.last_db_error = ""

    def _connect(self):
        if not self.database_url:
            raise RuntimeError("DATABASE_URL er ikke satt.")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise RuntimeError("psycopg er ikke installert.") from exc
        return psycopg.connect(self.database_url, connect_timeout=5)

    def _ensure_db(self) -> bool:
        if not self.database_url:
            return False
        if self._db_initialized:
            return True
        with self._db_init_lock:
            if self._db_initialized:
                return True
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            CREATE TABLE IF NOT EXISTS push_subscriptions (
                                expo_push_token TEXT PRIMARY KEY,
                                platform TEXT NOT NULL DEFAULT '',
                                entry_id BIGINT,
                                league_id BIGINT NOT NULL DEFAULT 25220,
                                prefs JSONB NOT NULL DEFAULT '{}'::jsonb,
                                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                            )
                            """
                        )
                    conn.commit()
                self._db_initialized = True
                self.last_db_error = ""
                return True
            except Exception as exc:  # pragma: no cover - network/database guard
                self.last_db_error = str(exc)[:500]
                return False

    @property
    def backend(self) -> str:
        return "postgres" if self._ensure_db() else "local-json"

    @property
    def durable(self) -> bool:
        return self.backend == "postgres"

    def _read_unlocked(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [row for row in data if isinstance(row, dict)]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return []

    def _write_unlocked(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    @staticmethod
    def _prefs(prefs: dict[str, Any] | None) -> dict[str, bool]:
        return {
            "league": bool((prefs or {}).get("league", True)),
            "deadline": bool((prefs or {}).get("deadline", True)),
            "personal": bool((prefs or {}).get("personal", True)),
            "live_events": bool((prefs or {}).get("live_events", True)),
        }

    @staticmethod
    def _row_from_db(row: tuple[Any, ...]) -> dict[str, Any]:
        token, platform, entry_id, league_id, prefs, enabled, created_at, updated_at = row
        return {
            "expo_push_token": str(token or ""),
            "platform": str(platform or ""),
            "entry_id": int(entry_id) if entry_id is not None else None,
            "league_id": int(league_id or DEFAULT_LEAGUE_ID),
            "prefs": dict(prefs or {}),
            "enabled": bool(enabled),
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or ""),
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at or ""),
        }

    def list(self) -> list[dict[str, Any]]:
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT expo_push_token, platform, entry_id, league_id,
                                   prefs, enabled, created_at, updated_at
                            FROM push_subscriptions
                            ORDER BY updated_at DESC
                            """
                        )
                        return [self._row_from_db(row) for row in cur.fetchall()]
            except Exception as exc:  # pragma: no cover - database guard
                self.last_db_error = str(exc)[:500]
        with self._lock:
            return self._read_unlocked()

    def count(self) -> int:
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM push_subscriptions WHERE enabled = TRUE")
                        row = cur.fetchone()
                        return int((row or [0])[0] or 0)
            except Exception as exc:  # pragma: no cover
                self.last_db_error = str(exc)[:500]
        return len([row for row in self.list() if row.get("enabled", True)])

    def get(self, token: str) -> dict[str, Any] | None:
        token = str(token or "").strip()
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT expo_push_token, platform, entry_id, league_id,
                                   prefs, enabled, created_at, updated_at
                            FROM push_subscriptions WHERE expo_push_token = %s
                            """,
                            (token,),
                        )
                        row = cur.fetchone()
                        return self._row_from_db(row) if row else None
            except Exception as exc:  # pragma: no cover
                self.last_db_error = str(exc)[:500]
        return next((row for row in self.list() if row.get("expo_push_token") == token), None)

    def upsert(
        self,
        token: str,
        *,
        platform: str = "",
        entry_id: int | None = None,
        league_id: int | None = None,
        prefs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = str(token or "").strip()
        now = datetime.now(timezone.utc).isoformat()
        league_id = int(league_id or DEFAULT_LEAGUE_ID)
        normalized_prefs = self._prefs(prefs)

        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO push_subscriptions (
                                expo_push_token, platform, entry_id, league_id,
                                prefs, enabled, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s::jsonb, TRUE, NOW(), NOW())
                            ON CONFLICT (expo_push_token) DO UPDATE SET
                                platform = EXCLUDED.platform,
                                entry_id = EXCLUDED.entry_id,
                                league_id = EXCLUDED.league_id,
                                prefs = EXCLUDED.prefs,
                                enabled = TRUE,
                                updated_at = NOW()
                            RETURNING expo_push_token, platform, entry_id, league_id,
                                      prefs, enabled, created_at, updated_at
                            """,
                            (
                                token,
                                str(platform or ""),
                                int(entry_id) if entry_id is not None else None,
                                league_id,
                                json.dumps(normalized_prefs),
                            ),
                        )
                        row = cur.fetchone()
                    conn.commit()
                if row:
                    return self._row_from_db(row)
            except Exception as exc:  # pragma: no cover
                self.last_db_error = str(exc)[:500]

        with self._lock:
            rows = self._read_unlocked()
            existing = next((row for row in rows if row.get("expo_push_token") == token), None)
            record = {
                "expo_push_token": token,
                "platform": str(platform or ""),
                "entry_id": int(entry_id) if entry_id is not None else None,
                "league_id": league_id,
                "prefs": normalized_prefs,
                "enabled": True,
                "updated_at": now,
                "created_at": (existing or {}).get("created_at") or now,
            }
            rows = [row for row in rows if row.get("expo_push_token") != token]
            rows.append(record)
            self._write_unlocked(rows)
            return record

    def remove(self, token: str) -> bool:
        token = str(token or "").strip()
        if self._ensure_db():
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM push_subscriptions WHERE expo_push_token = %s", (token,))
                        changed = cur.rowcount > 0
                    conn.commit()
                return changed
            except Exception as exc:  # pragma: no cover
                self.last_db_error = str(exc)[:500]
        with self._lock:
            rows = self._read_unlocked()
            kept = [row for row in rows if row.get("expo_push_token") != token]
            changed = len(kept) != len(rows)
            if changed:
                self._write_unlocked(kept)
            return changed


def send_expo_push(
    tokens: list[str],
    *,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    clean = list(dict.fromkeys(token for token in tokens if is_expo_push_token(token)))
    if not clean:
        return []

    output: list[dict[str, Any]] = []
    access_token = os.getenv("EXPO_ACCESS_TOKEN", "").strip()

    for offset in range(0, len(clean), 100):
        chunk = clean[offset : offset + 100]
        messages = [
            {
                "to": token,
                "sound": "default",
                "title": title[:100],
                "body": body[:1000],
                "data": data or {},
            }
            for token in chunk
        ]
        raw = json.dumps(messages).encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        req = urllib.request.Request(
            EXPO_PUSH_URL,
            data=raw,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Expo Push svarte {exc.code}: {detail[:300]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Kunne ikke nå Expo Push: {exc}") from exc

        if isinstance(payload, dict):
            result = payload.get("data")
            if isinstance(result, list):
                output.extend(row for row in result if isinstance(row, dict))
            else:
                output.append(payload)
        elif isinstance(payload, list):
            output.extend(row for row in payload if isinstance(row, dict))

    return output
