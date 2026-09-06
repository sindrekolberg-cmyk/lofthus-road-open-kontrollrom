from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import pandas as pd
from fastapi.testclient import TestClient

from api.app import create_app
from api.engine import AppEngine
from lro_config import LeagueConfig
from lro_live import LiveState, ManagerLiveState, PlayerImpact, inferred_fixture_status
from lro_pulse import diff_live_states, is_newer_snapshot, is_stale, round_kicker


def manager(**kwargs):
    base = dict(
        entry=1,
        manager="A",
        team="Alpha",
        previous_rank=1,
        live_rank=1,
        live_rank_change=0,
        official_total=100,
        official_event_points=0,
        official_total_before_gw=100,
        live_gw_points=0,
        live_gw_gross=0,
        transfer_hits=0,
        live_total_points=100,
        captain="Haaland",
        captain_element=20,
        vice_captain="Isak",
        vice_element=10,
        active_chip="",
        players_started=1,
        players_finished=0,
        players_live=1,
        players_remaining=0,
        month_points=0,
        month_rank=1,
        team_value=100.0,
        bank=0.0,
    )
    base.update(kwargs)
    return ManagerLiveState(**base)


def impact(**kwargs):
    base = dict(
        element=20,
        player="Haaland",
        club="MCI",
        event_points=2,
        ownership_count=1,
        ownership_pct=50.0,
        captain_count=0,
        triple_captain_count=0,
        effective_ownership_pct=50.0,
        live_minutes=70,
        fixture_status="live",
        impact_score=2.0,
        image_url="",
    )
    base.update(kwargs)
    return PlayerImpact(**base)


def state(players, managers, picks=None, fetched=None):
    return LiveState(
        event_id=3,
        event_status="live",
        is_live=True,
        is_finished=False,
        fetched_at=fetched or datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc),
        fixtures=[{"id": 1, "team_h": 1, "team_a": 2, "started": True, "finished": False, "minutes": 67, "team_h_score": 1, "team_a_score": 0}],
        manager_live=managers,
        player_impacts=players,
        ownership={"picks": picks if picks is not None else pd.DataFrame()},
        month_name="September",
        data_quality={},
    )


class PulseTests(unittest.TestCase):
    def test_points_change_does_not_invent_goal(self):
        old = state([impact(event_points=2)], [manager(live_gw_points=2, live_total_points=102)])
        new = state([impact(event_points=8)], [manager(live_gw_points=8, live_total_points=108)])
        events = diff_live_states(old, new, "snap-1")
        self.assertTrue(events)
        self.assertEqual(events[0].event_type, "player_points_changed")
        self.assertEqual(events[0].point_delta, 6)
        self.assertNotEqual(events[0].event_type, "goal")
        self.assertIn("Haaland", events[0].label)

    def test_goal_only_when_stat_increases(self):
        old_picks = pd.DataFrame([{"element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "live_goals": 0, "event_points": 2}])
        new_picks = pd.DataFrame([{"element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "live_goals": 1, "event_points": 8}])
        old = state([impact(event_points=2)], [manager()], old_picks)
        new = state([impact(event_points=8)], [manager(live_gw_points=8, live_total_points=108)], new_picks)
        events = diff_live_states(old, new, "snap-2")
        self.assertEqual(events[0].event_type, "goal")
        self.assertEqual(events[0].banner, "Mål")
        self.assertEqual(events[0].fixture_id, 1)

    def test_clean_sheet_not_emitted_at_minute_12(self):
        old_picks = pd.DataFrame([{"element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "live_cs": 0, "live_minutes": 12, "event_points": 2}])
        new_picks = pd.DataFrame([{"element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "live_cs": 1, "live_minutes": 12, "event_points": 6}])
        old = state([impact(event_points=2)], [manager()], old_picks)
        new = state([impact(event_points=6)], [manager(live_gw_points=6, live_total_points=106)], new_picks)
        events = diff_live_states(old, new, "snap-cs")
        self.assertTrue(events)
        self.assertEqual(events[0].event_type, "player_points_changed")
        self.assertEqual(events[0].fixture_id, 1)

    def test_autosub_event(self):
        old_picks = pd.DataFrame([{"element": 30, "player": "Mendy", "club": "CRY", "autosub_in": False, "event_points": 0}])
        new_picks = pd.DataFrame([{"element": 30, "player": "Mendy", "club": "CRY", "autosub_in": True, "event_points": 8}])
        old = state([], [manager()], old_picks)
        new = state([impact(element=30, player="Mendy", club="CRY", event_points=8)], [manager(live_gw_points=8)], new_picks)
        kinds = {e.event_type for e in diff_live_states(old, new, "snap-3")}
        self.assertIn("autosub", kinds)

    def test_vc_activation(self):
        old = state([], [manager(captain_element=20, captain="Haaland")])
        new = state([], [manager(captain_element=10, captain="Isak (C)")])
        kinds = {e.event_type for e in diff_live_states(old, new, "snap-4")}
        self.assertIn("captain_fallback", kinds)

    def test_no_noise_when_unchanged(self):
        s = state([impact()], [manager()])
        self.assertEqual(diff_live_states(s, s, "snap-5"), [])

    def test_never_apply_older_seq(self):
        self.assertTrue(is_newer_snapshot(4, 3))
        self.assertFalse(is_newer_snapshot(3, 3))
        self.assertFalse(is_newer_snapshot(2, 4))

    def test_stale_only_while_live(self):
        fresh = state([impact()], [manager()], fetched=datetime.now(timezone.utc))
        self.assertFalse(is_stale(fresh))
        old = state([impact()], [manager()], fetched=datetime(2026, 9, 6, 6, 0, tzinfo=timezone.utc))
        now = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)
        self.assertTrue(is_stale(old, now=now))
        finished = LiveState(
            event_id=3, event_status="finished", is_live=False, is_finished=True,
            fetched_at=datetime(2026, 9, 6, 6, 0, tzinfo=timezone.utc),
            fixtures=[], manager_live=[], player_impacts=[], ownership={}, month_name="September",
        )
        self.assertFalse(is_stale(finished, now=now))

    def test_round_kicker(self):
        self.assertEqual(round_kicker(3, True, False, "live"), "Live · Runde 3 pågår")
        self.assertEqual(round_kicker(3, False, True, "finished"), "Runde 3 ferdig")
        self.assertEqual(round_kicker(4, False, False, "pre"), "Runde 4")

    def test_pause_and_finished_fixtures(self):
        now = datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc)
        self.assertEqual(
            inferred_fixture_status({"started": True, "finished": False, "minutes": 45, "kickoff_time": "2026-09-06T15:00:00Z"}, now=now),
            "pause",
        )
        self.assertEqual(
            inferred_fixture_status({"started": True, "finished": False, "minutes": 90, "kickoff_time": "2026-09-05T14:00:00Z"}, now=now),
            "finished",
        )

    def test_atomic_adopt_and_sse_hello(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        config = LeagueConfig(
            league_id=1,
            name="Lofthus Road Open",
            season_fallback="2026/27",
            data_dir=Path(tmp.name),
        )
        engine = AppEngine(config, eager=True, refresh_seconds=10)
        engine.seed({"events": [], "elements": [], "teams": []}, [], state([impact()], [manager()]))
        engine._adopt_live(state([impact(event_points=9)], [manager(live_gw_points=9, live_total_points=109, live_rank=1)]))
        self.assertEqual(engine.pulse.seq, 1)
        self.assertEqual(engine.pulse.last_payload["events"][0]["event_type"], "player_points_changed")
        app = create_app(engine)
        client = TestClient(app)
        r = client.get("/api/live/pulse")
        self.assertEqual(r.status_code, 200)
        pulse = r.json()
        self.assertEqual(pulse["seq"], 1)
        self.assertTrue(pulse["event_history"])
        self.assertIn("snapshot_id", pulse["status"] or pulse)


if __name__ == "__main__":
    unittest.main()
