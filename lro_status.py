from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lro_live import _parse_kickoff, inferred_fixture_status


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


def _kickoff_date(raw: dict[str, Any] | None) -> Any:
    if not raw:
        return None
    kickoff = _parse_kickoff(raw.get("kickoff_time") or raw.get("kickoff"))
    if not kickoff:
        return None
    return kickoff.astimezone(timezone.utc).date()


def keep_in_pulse_strip(raw: dict[str, Any], now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()
    kickoff_day = _kickoff_date(raw)
    if kickoff_day and kickoff_day < today:
        return False
    status = fixture_status(raw, now)
    if is_fixture_live(status) or is_fixture_upcoming(status):
        return True
    if is_fixture_finished(status):
        return kickoff_day == today
    return False


def ordered_pulse_fixtures(raw_fixtures: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    kept = [f for f in raw_fixtures or [] if keep_in_pulse_strip(f, now)]
    kept.sort(
        key=lambda f: (
            _STRIP_RANK.get(fixture_status(f, now), 9),
            str(f.get("kickoff_time") or f.get("kickoff") or ""),
        )
    )
    return kept


def talker_tier(player_fixture_status: str, kickoff: datetime | None, now: datetime | None = None) -> int | None:
    """Current relevance: playing, then upcoming, then today's finished haul. Yesterday is out."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()
    if kickoff and kickoff.astimezone(timezone.utc).date() < today:
        return None
    if is_player_playing(player_fixture_status):
        return 3
    if is_player_upcoming(player_fixture_status):
        return 2
    if is_player_finished(player_fixture_status):
        if kickoff and kickoff.astimezone(timezone.utc).date() == now.astimezone(timezone.utc).date():
            return 1
        return None
    return None
