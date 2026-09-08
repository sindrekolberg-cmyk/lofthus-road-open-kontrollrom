from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from api.push import EXPO_PUSH_URL, is_expo_push_token


def _post_chunk(messages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, str | None]:
    raw = json.dumps(messages).encode("utf-8")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    access_token = os.getenv("EXPO_ACCESS_TOKEN", "").strip()
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    last_error = ""
    for attempt in range(2):
        req = urllib.request.Request(EXPO_PUSH_URL, data=raw, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
            data = payload.get("data") if isinstance(payload, dict) else payload
            if isinstance(data, list):
                return [row if isinstance(row, dict) else {"status": "error", "message": "Ugyldig Expo-svar"} for row in data], None
            if isinstance(data, dict) and len(messages) == 1:
                return [data], None
            return None, "Expo Push ga et uventet svarformat."
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = f"Expo Push svarte {exc.code}: {detail[:240]}"
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= 1:
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = f"Kunne ikke nå Expo Push: {exc}"
            if attempt >= 1:
                break
        time.sleep(0.4 * (attempt + 1))
    return None, last_error or "Expo Push feilet."


def send_expo_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Send personalized Expo messages in batches of 100.

    Unlike the simple broadcast helper, every message can have its own title,
    body and data payload. This keeps a goal from creating one HTTP request per
    subscriber when the product grows beyond a single mini-league.
    """
    normalized: list[dict[str, Any]] = []
    for raw in messages:
        token = str((raw or {}).get("to") or "").strip()
        if not is_expo_push_token(token):
            continue
        normalized.append(
            {
                "to": token,
                "sound": str((raw or {}).get("sound") or "default"),
                "title": str((raw or {}).get("title") or "Lofthus Road Open")[:100],
                "body": str((raw or {}).get("body") or "")[:1000],
                "data": (raw or {}).get("data") if isinstance((raw or {}).get("data"), dict) else {},
            }
        )

    deliveries: list[dict[str, Any]] = []
    http_batches = 0
    for offset in range(0, len(normalized), 100):
        chunk = normalized[offset : offset + 100]
        http_batches += 1
        tickets, error = _post_chunk(chunk)
        if tickets is None:
            for message in chunk:
                deliveries.append(
                    {
                        "expo_push_token": message["to"],
                        "status": "transport_error",
                        "message": error or "Expo Push feilet.",
                        "details": {},
                    }
                )
            continue

        for index, message in enumerate(chunk):
            ticket = tickets[index] if index < len(tickets) else {"status": "error", "message": "Mangler Expo-ticket"}
            deliveries.append(
                {
                    "expo_push_token": message["to"],
                    "status": str(ticket.get("status") or "error"),
                    "ticket_id": ticket.get("id"),
                    "message": str(ticket.get("message") or ""),
                    "details": dict(ticket.get("details") or {}) if isinstance(ticket.get("details"), dict) else {},
                }
            )

    accepted = sum(1 for row in deliveries if row.get("status") == "ok")
    failed = len(deliveries) - accepted
    invalid_tokens = sorted(
        {
            str(row.get("expo_push_token") or "")
            for row in deliveries
            if str((row.get("details") or {}).get("error") or "") == "DeviceNotRegistered"
        }
    )
    return {
        "requested": len(messages),
        "valid": len(normalized),
        "accepted": accepted,
        "failed": failed,
        "http_batches": http_batches,
        "invalid_tokens": invalid_tokens,
        "deliveries": deliveries,
    }
