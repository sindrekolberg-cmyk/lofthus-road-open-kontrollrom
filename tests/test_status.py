from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from api.app import create_app
from api.engine import AppEngine
from api.serialize import fixture_status_label, live_events_payload, talkers_payload
from lro_config import LeagueConfig
from lro_history import HistoryStore
from lro_live import LiveState, ManagerLiveState, PlayerImpact, inferred_fixture_status
from lro_newsroom import _story, merge_persistent_stories
from lro_status import (
    homepage_hero_story,
    is_player_finished,
    is_player_playing,
    is_player_upcoming,
    ordered_pulse_fixtures,
    talker_tier,
)
from tests.test_api import BOOTSTRAP, FakeClient, managers, ownership
from lro_live import build_live_state
from lro_analysis import remaining_from_picks


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
YDAY = (NOW - timedelta(days=1)).strftime("%Y-%m-%dT14:00:00Z")
TODAY_KO = NOW.strftime("%Y-%m-%dT11:00:00Z")
LATER_KO = NOW.strftime("%Y-%m-%dT16:30:00Z")


def _manager(**kwargs):
    base = dict(
        entry=1, manager="A", team="Alpha", previous_rank=1, live_rank=1, live_rank_change=0,
        official_total=100, official_event_points=0, official_total_before_gw=100,
        live_gw_points=10, live_gw_gross=10, transfer_hits=0, live_total_points=110,
        captain="Isak", captain_element=10, vice_captain="", vice_element=0, active_chip="",
        players_started=1, players_finished=0, players_live=1, players_remaining=1,
        month_points=10, month_rank=1, team_value=100.0, bank=0.0,
    )
    base.update(kwargs)
    return ManagerLiveState(**base)


def _impact(**kwargs):
    base = dict(
        element=10, player="Isak", club="NEW", event_points=8, ownership_count=2,
        ownership_pct=20.0, captain_count=1, triple_captain_count=0, effective_ownership_pct=30.0,
        live_minutes=40, fixture_status="live", impact_score=20.0, image_url="",
    )
    base.update(kwargs)
    return PlayerImpact(**base)


def _state(fixtures, players):
    return LiveState(
        event_id=3,
        event_status="live",
        is_live=True,
        is_finished=False,
        fetched_at=NOW,
        fixtures=fixtures,
        manager_live=[_manager()],
        player_impacts=players,
        ownership={},
        month_name="September",
    )


YESTERDAY = {
    "id": 101,
    "kickoff_time": YDAY,
    "started": True,
    "finished": True,
    "minutes": 90,
    "team_h": 7,
    "team_a": 8,
    "team_h_score": 2,
    "team_a_score": 0,
}
UPCOMING = {
    "id": 102,
    "kickoff_time": LATER_KO,
    "started": False,
    "finished": False,
    "minutes": 0,
    "team_h": 3,
    "team_a": 4,
}
LIVE = {
    "id": 103,
    "kickoff_time": TODAY_KO,
    "started": True,
    "finished": False,
    "minutes": 38,
    "team_h": 1,
    "team_a": 2,
    "team_h_score": 1,
    "team_a_score": 0,
}


class StatusModelTests(unittest.TestCase):
    def test_finished_fixture_never_displays_pagar(self):
        status = inferred_fixture_status(YESTERDAY, now=NOW)
        self.assertEqual(status, "finished")
        self.assertNotIn("pågår", fixture_status_label(status).casefold())

    def test_yesterdays_finished_fixture_absent_from_header_pulse(self):
        ordered = ordered_pulse_fixtures([YESTERDAY, UPCOMING, LIVE], now=NOW)
        ids = [f["id"] for f in ordered]
        self.assertNotIn(101, ids)
        self.assertIn(102, ids)
        self.assertIn(103, ids)
        self.assertEqual(ids[0], 103)

    def test_upcoming_current_gw_fixture_remains_visible(self):
        ordered = ordered_pulse_fixtures([YESTERDAY, UPCOMING], now=NOW)
        self.assertEqual([f["id"] for f in ordered], [102])

    def test_stale_live_flag_from_yesterday_is_absent(self):
        stale = {
            "id": 109,
            "kickoff_time": YDAY,
            "started": True,
            "finished": False,
            "minutes": 67,
            "team_h": 7,
            "team_a": 8,
        }
        ordered = ordered_pulse_fixtures([stale, UPCOMING, LIVE], now=NOW)
        self.assertEqual([f["id"] for f in ordered], [103, 102])

    def test_live_fixture_appears(self):
        ordered = ordered_pulse_fixtures([LIVE], now=NOW)
        self.assertEqual(ordered[0]["id"], 103)
        self.assertEqual(inferred_fixture_status(LIVE, now=NOW), "live")

    def test_completed_player_is_not_currently_playing(self):
        self.assertFalse(is_player_playing("finished"))
        self.assertTrue(is_player_finished("finished"))
        self.assertTrue(is_player_upcoming("not_started"))
        self.assertTrue(is_player_playing("pause"))

    def test_stale_story_cannot_become_homepage_live_lead(self):
        old = {"source_event": 2, "headline": "falt 43 plasser forrige runde", "key": "old"}
        live = {"source_event": 3, "headline": "Isak herjer", "key": "now"}
        self.assertEqual(homepage_hero_story([old, live], 3)["key"], "now")
        self.assertIsNone(homepage_hero_story([old], 3))

    def test_live_events_drop_stale_headlines_on_finished(self):
        bootstrap = {
            "teams": [
                {"id": 1, "name": "Newcastle", "short_name": "NEW"},
                {"id": 2, "name": "City", "short_name": "MCI"},
                {"id": 3, "name": "Forest", "short_name": "NFO"},
                {"id": 4, "name": "Spurs", "short_name": "TOT"},
                {"id": 7, "name": "Brentford", "short_name": "BRE"},
                {"id": 8, "name": "Sunderland", "short_name": "SUN"},
            ]
        }
        state = _state(
            [YESTERDAY, UPCOMING, LIVE],
            [
                _impact(fixture_status="finished", event_points=13, club="NEW"),
                _impact(element=20, player="Haaland", club="MCI", fixture_status="live", event_points=2),
            ],
        )
        events = live_events_payload(state, bootstrap, now=NOW)
        ids = [e["id"] for e in events]
        self.assertNotIn(101, ids)
        live_row = next(e for e in events if e["id"] == 103)
        self.assertEqual(live_row["status"], "live")
        upcoming_row = next(e for e in events if e["id"] == 102)
        self.assertEqual(upcoming_row["lofthus_headline"], "")
        self.assertEqual(upcoming_row["status_label"], "Ikke startet")

    def test_talkers_prefer_playing_over_yesterdays_finished(self):
        bootstrap = {
            "teams": [
                {"id": 1, "name": "Newcastle", "short_name": "NEW"},
                {"id": 2, "name": "City", "short_name": "MCI"},
                {"id": 7, "name": "Brentford", "short_name": "BRE"},
                {"id": 8, "name": "Sunderland", "short_name": "SUN"},
            ]
        }
        yesterday_player = _impact(event_points=15, fixture_status="finished", club="BRE", ownership_count=50)
        live_player = _impact(element=20, player="Haaland", club="MCI", event_points=2, fixture_status="live", ownership_count=5)
        state = _state([YESTERDAY, LIVE], [yesterday_player, live_player])
        talkers = talkers_payload(state, bootstrap, now=NOW)
        names = [p["player"] for p in talkers]
        self.assertIn("Haaland", names)
        self.assertNotIn("Isak", names)
        self.assertIsNone(talker_tier("finished", NOW - timedelta(days=1), NOW))

    def test_newsroom_previous_round_not_lead(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        history = HistoryStore(Path(tmp.name))
        state = build_live_state(FakeClient({10: 10, 20: 0}), managers(), history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        old = _story("old-move", "movement", "falt 43 plasser forrige runde", "", 96, "settled", 60, source_event=2)
        now = _story("now-live", "live", "Isak herjer: 10 poeng", "", 84, "live", 25, source_event=3)
        merged = merge_persistent_stories([now], [old.to_dict()], state, limit=4)
        self.assertEqual(homepage_hero_story([s.to_dict() for s in merged], 3)["key"], "now-live")


class StatusApiTests(unittest.TestCase):
    def setUp(self):
        config = LeagueConfig(
            league_id=25220,
            name="Lofthus Road Open",
            season_fallback="2026/27",
            data_dir=Path(__file__).resolve().parents[1] / "data",
        )
        history = HistoryStore(config.data_dir)
        client = FakeClient({10: 10, 20: 0}, phase_totals={1: 20, 2: 10, 3: 5})
        state = build_live_state(client, managers(), history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        self.engine = AppEngine(config, client=client, eager=True)
        self.engine.seed(BOOTSTRAP, managers(), state=state, histories={})
        self.client = TestClient(create_app(self.engine))

    def test_correct_current_gw_number(self):
        status = self.client.get("/api/status").json()
        self.assertEqual(status["event_id"], 3)
        self.assertTrue(status["gw_active"])

    def test_same_manager_total_across_league_profile_rivalradar(self):
        league = {row["entry"]: row["total"] for row in self.client.get("/api/league").json()["table"]}
        profile = self.client.get("/api/managers/3").json()["manager"]["total"]
        rival = self.client.get("/api/rival", params={"manager_a": 3, "manager_b": 1}).json()
        self.assertEqual(league[3], profile)
        self.assertEqual(profile, rival["me"]["total"])

    def test_autosub_remaining_matches_effective_squad(self):
        from tests.test_autosubs import TEAMS, standard_343
        rows = standard_343()
        remaining = remaining_from_picks(rows, TEAMS)
        self.assertEqual(remaining, 4)


if __name__ == "__main__":
    unittest.main()
