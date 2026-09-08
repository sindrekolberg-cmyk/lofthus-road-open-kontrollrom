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


def is_expo_push_token(token: str) -> bool:
    token = str(token or "").strip()
    return (
        (token.startswith("ExpoPushToken[") or token.startswith("ExponentPushToken["))
        and token.endswith("]")
        and len(token) > 24
    )


class PushStore:
    def __init__(self, path: str | None = None):
        self.path = Path(
            path
            or os.getenv("LRO_PUSH_STORE_PATH", "").strip()
            or "/tmp/lofthus-push-subscriptions.json"
        )
        self._lock = threading.Lock()

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

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_unlocked()

    def count(self) -> int:
        return len(self.list())

    def get(self, token: str) -> dict[str, Any] | None:
        token = str(token or "").strip()
        return next((row for row in self.list() if row.get("expo_push_token") == token), None)

    def upsert(
        self,
        token: str,
        *,
        platform: str = "",
        entry_id: int | None = None,
        prefs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = str(token or "").strip()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rows = self._read_unlocked()
            existing = next((row for row in rows if row.get("expo_push_token") == token), None)
            record = {
                "expo_push_token": token,
                "platform": str(platform or ""),
                "entry_id": int(entry_id) if entry_id is not None else None,
                "prefs": {
                    "league": bool((prefs or {}).get("league", True)),
                    "deadline": bool((prefs or {}).get("deadline", True)),
                    "personal": bool((prefs or {}).get("personal", True)),
                    "live_events": bool((prefs or {}).get("live_events", True)),
                },
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
