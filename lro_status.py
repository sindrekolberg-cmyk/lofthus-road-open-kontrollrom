from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from lro_live import _parse_kickoff, inferred_fixture_status

DISPLAY_TZ = ZoneInfo("Europe/Oslo")


FIXTURE_LIVE = "live"
FIXTURE_PAUSE = "pause"
FIXTURE_FINISHED = "finished"
FIXTURE_UPCOMING = "not_started"
FIXTURE_POSTPONED = "postponed"

AUTOSUB_CONFIRMED = "confirmed"
AUTOSUB_PROJECTED = "pending"

_STRIP_RANK = {
    FIXTURE_LIVE: 0,
    FIXTURE_PAUSE: 1,
    FIXTURE_UPCOMING: 2,
    FIXTURE_FINISHED: 3,
    FIXTURE_POSTPONED: 4,
}


def fixture_status(raw: dict[str, Any], now: datetime | None = None) -> str:
    return inferred_fixture_status(raw, now=now)


def is_fixture_live(status: str) -> bool:
    return status in {FIXTURE_LIVE, FIXTURE_PAUSE}


def is_fixture_finished(status: str) -> bool:
    return status == FIXTURE_FINISHED


def is_fixture_upcoming(status: str) -> bool:
    return status == FIXTURE_UPCOMING


def is_player_playing(status: str) -> bool:
    return is_fixture_live(status)


def is_player_finished(status: str) -> bool:
    return is_fixture_finished(status)


def is_player_upcoming(status: str) -> bool:
    return is_fixture_upcoming(status)


def gw_is_active(is_live: bool, is_finished: bool, event_id: int) -> bool:
    return bool(event_id) and not bool(is_finished)


def story_is_current_gw(source_event: int, event_id: int) -> bool:
    return int(source_event or 0) == int(event_id or 0) and int(event_id or 0) > 0


def homepage_hero_story(stories: list[Any], event_id: int) -> Any | None:
    """Lead must belong to the current GW. Previous-round copy is never the live lead."""
    for story in stories:
        source = int((story.get("source_event") if isinstance(story, dict) else getattr(story, "source_event", 0)) or 0)
        if story_is_current_gw(source, event_id):
            return story
    return None


def _local_date(value: datetime | None) -> Any:
    if not value:
        return None
    return value.astimezone(DISPLAY_TZ).date()


def _kickoff_dt(raw: dict[str, Any] | None):
    if not raw:
        return None
    return _parse_kickoff(raw.get("kickoff_time") or raw.get("kickoff"))


def _kickoff_date(raw: dict[str, Any] | None) -> Any:
    return _local_date(_kickoff_dt(raw))


def keep_in_pulse_strip(raw: dict[str, Any], now: datetime | None = None) -> bool:
    """True if this fixture can appear in the current-match pulse (not the GW archive)."""
    return raw in ordered_pulse_fixtures([raw] if raw else [], now=now)


def ordered_pulse_fixtures(raw_fixtures: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    """Homepage/header pulse: live today, then upcoming today, then today's finished, else next matchday.

    Ordinary finished fixtures from a previous local calendar day (Europe/Oslo) are excluded.
    Fixture status stays canonical: a visible finished match is still Ferdig.
    """
    now = now or datetime.now(timezone.utc)
    today = _local_date(now)
    rows: list[tuple[dict[str, Any], str, Any, Any]] = []
    for raw in raw_fixtures or []:
        status = fixture_status(raw, now)
        kickoff = _kickoff_dt(raw)
        day = _local_date(kickoff)
        rows.append((raw, status, day, kickoff))

    live = [r for r in rows if is_fixture_live(r[1])]
    today_up = [r for r in rows if is_fixture_upcoming(r[1]) and r[2] == today]
    today_fin = [r for r in rows if is_fixture_finished(r[1]) and r[2] == today]
    later_up = [r for r in rows if is_fixture_upcoming(r[1]) and r[2] is not None and r[2] > today]
    later_up_undated = [r for r in rows if is_fixture_upcoming(r[1]) and r[2] is None]

    def kick_stamp(row: tuple[dict[str, Any], str, Any, Any]) -> str:
        kickoff = row[3]
        if kickoff:
            return kickoff.isoformat()
        return str(row[0].get("kickoff_time") or row[0].get("kickoff") or "")

    if live:
        picked = live + today_up
        picked.sort(key=lambda r: (_STRIP_RANK.get(r[1], 9), kick_stamp(r)))
    elif today_up:
        picked = sorted(today_up, key=kick_stamp)
    elif today_fin:
        picked = sorted(today_fin, key=lambda r: r[3] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    else:
        picked = sorted(later_up or later_up_undated, key=kick_stamp)[:6]
    return [r[0] for r in picked]


def talker_tier(player_fixture_status: str, kickoff: datetime | None, now: datetime | None = None) -> int | None:
    """Current relevance: playing, then upcoming, then today's finished haul. Yesterday is out."""
    now = now or datetime.now(timezone.utc)
    today = _local_date(now)
    if kickoff and _local_date(kickoff) and _local_date(kickoff) < today:
        return None
    if is_player_playing(player_fixture_status):
        return 3
    if is_player_upcoming(player_fixture_status):
        return 2
    if is_player_finished(player_fixture_status):
        if kickoff and _local_date(kickoff) == today:
            return 1
        return None
    return None
