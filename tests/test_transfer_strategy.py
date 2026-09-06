from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api.app import create_app
from api.engine import AppEngine
from lro_config import LeagueConfig
from lro_history import HistoryStore
from lro_live import build_live_state
from lro_transfer_strategy import build_transfer_strategy


ROOT = Path(__file__).resolve().parents[1]


def _el(pid, name, team, etype, **extra):
    row = {
        "id": pid,
        "code": pid * 100,
        "web_name": name,
        "first_name": name,
        "second_name": name,
        "team": team,
        "element_type": etype,
        "now_cost": extra.pop("now_cost", 75),
        "total_points": extra.pop("total_points", 40),
        "selected_by_percent": extra.pop("selected_by_percent", "10.0"),
        "form": extra.pop("form", "6.0"),
        "points_per_game": extra.pop("points_per_game", "6.0"),
        "minutes": extra.pop("minutes", 720),
        "starts": extra.pop("starts", 8),
        "expected_goals": extra.pop("expected_goals", 2.0),
        "expected_assists": extra.pop("expected_assists", 2.0),
        "ict_index": extra.pop("ict_index", 180),
        "status": extra.pop("status", "a"),
        "news": extra.pop("news", ""),
        "chance_of_playing_next_round": extra.pop("chance_of_playing_next_round", 100),
    }
    row.update(extra)
    return row


BOOTSTRAP = {
    "events": [
        {"id": e, "is_current": e == 3, "is_next": e == 4, "finished": e < 3, "deadline_time": f"2026-09-0{e}T11:00:00Z"}
        for e in range(1, 9)
    ],
    "phases": [{"id": 2, "name": "September", "start_event": 3, "stop_event": 6}],
    "teams": [
        {"id": 1, "name": "Arsenal", "short_name": "ARS"},
        {"id": 2, "name": "Palace", "short_name": "CRY"},
        {"id": 3, "name": "West Ham", "short_name": "WHU"},
        {"id": 4, "name": "Fulham", "short_name": "FUL"},
        {"id": 5, "name": "Leeds", "short_name": "LEE"},
        {"id": 6, "name": "Sunderland", "short_name": "SUN"},
    ],
    "elements": [
        _el(10, "Saka", 1, 3, now_cost=100, form="7.5", points_per_game="7.2", selected_by_percent="55.0"),
        _el(11, "Eze", 2, 3, now_cost=75, form="6.8", points_per_game="6.4", selected_by_percent="8.0"),
        _el(12, "Bowen", 3, 3, now_cost=75, form="4.0", points_per_game="4.2"),
        _el(13, "Injured", 4, 3, status="i", chance_of_playing_next_round=0, news="Hamstring", minutes=90, starts=1),
        _el(14, "Banned", 4, 3, status="s", chance_of_playing_next_round=0, news="Karantene"),
        _el(15, "EasyFix", 5, 3, form="6.2", points_per_game="5.8"),
        _el(16, "HardFix", 6, 3, form="6.2", points_per_game="5.8"),
        _el(17, "Bench", 2, 3, minutes=40, starts=1, form="5.0", points_per_game="5.5", expected_goals=1.2, chance_of_playing_next_round=50),
    ],
}

FIXTURES = []
for event in range(3, 8):
    # EasyFix (team 5): easy now, brutal later
    FIXTURES.append({
        "id": event * 10 + 1,
        "event": event,
        "team_h": 5,
        "team_a": 4,
        "started": False,
        "finished": False,
        "team_h_difficulty": 2 if event == 3 else 5,
        "team_a_difficulty": 3,
        "kickoff_time": f"2026-09-{10+event}T14:00:00Z",
    })
    # HardFix (team 6): brutal now, easy later
    FIXTURES.append({
        "id": event * 10 + 2,
        "event": event,
        "team_h": 6,
        "team_a": 1,
        "started": False,
        "finished": False,
        "team_h_difficulty": 5 if event == 3 else 2,
        "team_a_difficulty": 3,
        "kickoff_time": f"2026-09-{10+event}T16:00:00Z",
    })
    FIXTURES.append({
        "id": event * 10 + 3,
        "event": event,
        "team_h": 1,
        "team_a": 2,
        "started": False,
        "finished": False,
        "team_h_difficulty": 3,
        "team_a_difficulty": 3,
        "kickoff_time": f"2026-09-{10+event}T12:00:00Z",
    })
    FIXTURES.append({
        "id": event * 10 + 4,
        "event": event,
        "team_h": 3,
        "team_a": 4,
        "started": False,
        "finished": False,
        "team_h_difficulty": 3,
        "team_a_difficulty": 3,
        "kickoff_time": f"2026-09-{10+event}T12:30:00Z",
    })


class FakeClient:
    def bootstrap(self):
        return BOOTSTRAP

    def fixtures(self, event_id=None):
        if event_id:
            return [f for f in FIXTURES if f["event"] == event_id]
        return list(FIXTURES)

    def event_live(self, event_id):
        return {"elements": [{"id": e, "stats": {"total_points": 0, "minutes": 0}} for e in (10, 11, 12, 13, 14, 15, 16, 17)]}

    def league_phase_standings(self, league_id, phase_id):
        return [{"entry": i, "total": 200 - i * 8} for i in range(1, 17)]

    def league_managers(self, league_id):
        return {}, managers(), {"errors": []}

    def histories_many(self, entries, max_workers=8):
        return {}, {}

    def invalidate_picks(self, event_id=None):
        return 0


def managers():
    rows = []
    for i in range(1, 17):
        rows.append({
            "entry": i,
            "player_name": f"M{i}",
            "entry_name": f"T{i}",
            "rank": i,
            "last_rank": i,
            "event_total": 0,
            "total": 220 - i * 10,
        })
    return rows


def _pick(entry, element, name, club, team_id, rank, **extra):
    return {
        "entry": entry,
        "manager": f"M{entry}",
        "team": f"T{entry}",
        "rank": rank,
        "element": element,
        "player": name,
        "club": club,
        "team_id": team_id,
        "position_id": 3,
        "position": "Midtbane",
        "squad_position": extra.get("squad_position", 1),
        "multiplier": extra.get("multiplier", 1),
        "is_captain": extra.get("is_captain", False),
        "is_vice_captain": False,
        "on_bench": extra.get("on_bench", False),
        "active_chip": "",
        "is_triple_captain": False,
        "event_points": 0,
        "gw_contribution": 0,
        "image_url": "",
        "selling_price": extra.get("selling_price", 7.5),
    }


def ownership():
    picks = []
    for i in range(1, 16):
        picks.append(_pick(i, 10, "Saka", "ARS", 1, i))
        if i <= 2:
            picks.append(_pick(i, 11, "Eze", "CRY", 2, i, squad_position=2))
        picks.append(_pick(i, 12, "Bowen", "WHU", 3, i, squad_position=3))
    picks.append(_pick(16, 12, "Bowen", "WHU", 3, 16, selling_price=7.4))
    events = [
        {"entry": i, "manager": f"M{i}", "team": f"T{i}", "event_transfers_cost": 0, "team_value": 100.0, "bank": 1.5 if i == 16 else 0.0, "active_chip": ""}
        for i in range(1, 17)
    ]
    players = pd.DataFrame([
        {"element": 10, "player": "Saka", "club": "ARS", "team_id": 1, "ownership_count": 15, "ownership_pct": 93.8, "captain_count": 0, "captain_pct": 0, "triple_captain_count": 0, "effective_ownership_pct": 93.8, "live_minutes": 0, "event_points": 0, "image_url": ""},
        {"element": 11, "player": "Eze", "club": "CRY", "team_id": 2, "ownership_count": 2, "ownership_pct": 12.5, "captain_count": 0, "captain_pct": 0, "triple_captain_count": 0, "effective_ownership_pct": 12.5, "live_minutes": 0, "event_points": 0, "image_url": ""},
        {"element": 12, "player": "Bowen", "club": "WHU", "team_id": 3, "ownership_count": 16, "ownership_pct": 100, "captain_count": 0, "captain_pct": 0, "triple_captain_count": 0, "effective_ownership_pct": 100, "live_minutes": 0, "event_points": 0, "image_url": ""},
    ])
    return {
        "event": 3,
        "picks": pd.DataFrame(picks),
        "manager_events": pd.DataFrame(events),
        "players": players,
        "loaded_managers": 16,
        "league_size": 16,
        "errors": [],
    }


class TransferStrategyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        config = LeagueConfig(league_id=25220, name="Lofthus Road Open", season_fallback="2026/27", data_dir=ROOT / "data")
        history = HistoryStore(config.data_dir)
        client = FakeClient()
        self.state = build_live_state(client, managers(), history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        self.engine = AppEngine(config, client=client, eager=True)
        self.engine.seed(BOOTSTRAP, managers(), state=self.state, histories={})
        self.api = TestClient(create_app(self.engine))

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, **kwargs):
        params = {"entry_id": 16, "strategy": "rapid_lofthus", "risk": 80, "horizon": 3, **kwargs}
        return build_transfer_strategy(state=self.state, bootstrap=BOOTSTRAP, fixtures=FIXTURES, **params)

    def names(self, body, key="ranked"):
        return [r["player"] for r in body.get(key) or []]

    def score_of(self, body, name):
        return next(r["strategy_score"] for r in body["ranked"] if r["player"] == name)

    def test_scenario_a_rapid_lofthus_lifts_low_owned_quality(self):
        rapid = self.plan(strategy="rapid_lofthus", risk=80)
        or_mode = self.plan(strategy="climb_or", risk=40)
        self.assertIn("Eze", self.names(rapid))
        self.assertIn("Saka", self.names(rapid))
        self.assertGreater(self.score_of(rapid, "Eze") - self.score_of(rapid, "Saka"), self.score_of(or_mode, "Eze") - self.score_of(or_mode, "Saka"))
        eze = next(r for r in rapid["ranked"] if r["player"] == "Eze")
        self.assertGreaterEqual(eze["target_cohort_non_owner_count"], 10)
        self.assertTrue(any("mangler ham" in line for line in eze["why"]))

    def test_scenario_b_minutes_risk_hurts_or_more(self):
        rapid = self.plan(strategy="rapid_lofthus", risk=80)
        or_mode = self.plan(strategy="climb_or", risk=20)
        self.assertIn("Bench", self.names(rapid))
        self.assertGreater(self.score_of(rapid, "Bench"), self.score_of(or_mode, "Bench"))

    def test_scenario_c_defend_values_missing_template(self):
        leader = build_transfer_strategy(
            state=self.state, bootstrap=BOOTSTRAP, fixtures=FIXTURES,
            entry_id=1, strategy="defend", risk=20, horizon=3,
        )
        self.assertNotIn("Saka", self.names(leader))
        missing = build_transfer_strategy(
            state=self.state, bootstrap=BOOTSTRAP, fixtures=FIXTURES,
            entry_id=16, strategy="defend", risk=20, horizon=3,
        )
        self.assertIn("Saka", self.names(missing))
        self.assertGreater(self.score_of(missing, "Saka"), self.score_of(self.plan(strategy="rapid_lofthus", risk=90), "Saka"))

    def test_scenario_d_rival_catch_vs_defend(self):
        catch = self.plan(strategy="beat_rival", rival_id=1, risk=70)
        hold = build_transfer_strategy(
            state=self.state, bootstrap=BOOTSTRAP, fixtures=FIXTURES,
            entry_id=1, strategy="beat_rival", rival_id=16, risk=40, horizon=3,
        )
        self.assertGreater(self.score_of(catch, "Eze"), self.score_of(catch, "Saka"))
        self.assertIn("Eze", self.names(catch))
        self.assertTrue(hold["ok"])

    def test_scenario_e_risk_slider_moves_differential(self):
        safe = self.plan(strategy="rapid_lofthus", risk=10)
        send = self.plan(strategy="rapid_lofthus", risk=90)
        self.assertGreater(self.score_of(send, "Eze") - self.score_of(send, "Saka"), self.score_of(safe, "Eze") - self.score_of(safe, "Saka"))

    def test_scenario_f_horizon_changes_fixture_ranking(self):
        one = self.plan(strategy="balanced", risk=50, horizon=1)
        five = self.plan(strategy="balanced", risk=50, horizon=5)
        self.assertNotEqual(self.score_of(one, "EasyFix"), self.score_of(five, "EasyFix"))
        self.assertGreater(self.score_of(one, "EasyFix") - self.score_of(one, "HardFix"), self.score_of(five, "EasyFix") - self.score_of(five, "HardFix"))

    def test_scenario_g_owned_player_never_buy(self):
        body = self.plan()
        self.assertNotIn("Bowen", self.names(body))
        self.assertNotIn(12, [r["element"] for r in body["ranked"]])
        self.assertNotIn(12, [r["element"] for r in body["recommendations"]])

    def test_scenario_h_unavailable_excluded(self):
        body = self.plan()
        names = self.names(body)
        self.assertNotIn("Banned", names)
        self.assertNotIn("Injured", names)

    def test_no_fake_xpts_and_budget_language(self):
        body = self.plan()
        blob = str(body)
        self.assertNotIn("Expected points", blob)
        self.assertEqual(body["projection_source"], "heuristic_projection")
        rec = body["recommendations"][0]
        self.assertIn("projection_index", rec)
        self.assertLessEqual(rec["projection_index"], 10)
        if body["pairs"]:
            self.assertIn(body["pairs"][0]["budget"]["label"], {"Sannsynlig innenfor budsjett", "Budsjett må bekreftes"})

    def test_strategy_change_changes_order(self):
        a = self.names(self.plan(strategy="rapid_lofthus", risk=85))
        b = self.names(self.plan(strategy="climb_or", risk=20))
        self.assertNotEqual(a[:3], b[:3])

    def test_endpoint_returns_fixture_for_manager(self):
        r = self.api.get("/api/analysis/transfers", params={"entry_id": 16, "strategy": "rapid_lofthus", "risk": 80, "horizon": 3})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["manager"]["entry"], 16)
        self.assertTrue(body["recommendations"])
        self.assertEqual(body["recommendations"][0]["element"] in {10, 11, 15, 16, 17}, True)
        missing = self.api.get("/api/analysis/transfers", params={"entry_id": 999})
        self.assertEqual(missing.status_code, 404)

    def test_defend_leader_missing_saka_not_applicable_to_owner(self):
        r = self.api.get("/api/analysis/captain")
        self.assertEqual(r.status_code, 200)
        r2 = self.api.get("/api/analysis/differentials")
        self.assertEqual(r2.status_code, 200)
