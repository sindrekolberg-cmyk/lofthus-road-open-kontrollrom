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


ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self, points: dict[int, int], phase_totals: dict[int, int] | None = None):
        self.points = points
        self.phase_totals = phase_totals or {}

    def bootstrap(self):
        return BOOTSTRAP

    def fixtures(self, event_id):
        return [{"event": event_id, "team_h": 1, "team_a": 2, "started": True, "finished": False, "team_h_score": 1, "team_a_score": 0}]

    def event_live(self, event_id):
        return {
            "elements": [
                {"id": e, "stats": {"total_points": p, "minutes": 70, "goals_scored": 1 if p >= 5 else 0, "assists": 0, "clean_sheets": 0, "bonus": 0}}
                for e, p in self.points.items()
            ]
        }

    def league_phase_standings(self, league_id, phase_id):
        return [{"entry": e, "total": p} for e, p in self.phase_totals.items()]

    def league_managers(self, league_id):
        return {}, managers(), {"errors": []}

    def histories_many(self, entries, max_workers=8):
        return {}, {}

    def invalidate_picks(self, event_id=None):
        return 0


BOOTSTRAP = {
    "events": [{"id": 3, "is_current": True, "is_next": False, "finished": False, "deadline_time": "2026-09-05T11:00:00Z"}],
    "phases": [{"id": 2, "name": "September", "start_event": 3, "stop_event": 6}],
    "teams": [{"id": 1, "name": "Newcastle", "short_name": "NEW"}, {"id": 2, "name": "City", "short_name": "MCI"}],
    "elements": [
        {"id": 10, "code": 123456, "web_name": "Isak", "first_name": "Alexander", "second_name": "Isak", "team": 1, "element_type": 4, "now_cost": 100, "total_points": 20, "selected_by_percent": "30.0"},
        {"id": 20, "code": 789012, "web_name": "Haaland", "first_name": "Erling", "second_name": "Haaland", "team": 2, "element_type": 4, "now_cost": 145, "total_points": 20, "selected_by_percent": "60.0"},
    ],
}


def managers():
    return [
        {"entry": 1, "player_name": "A", "entry_name": "Alpha", "rank": 1, "last_rank": 1, "event_total": 0, "total": 100},
        {"entry": 2, "player_name": "B", "entry_name": "Bravo", "rank": 2, "last_rank": 2, "event_total": 0, "total": 90},
        {"entry": 3, "player_name": "C", "entry_name": "Charlie", "rank": 3, "last_rank": 3, "event_total": 0, "total": 80},
    ]


def ownership():
    picks = pd.DataFrame([
        {"entry": 1, "manager": "A", "team": "Alpha", "rank": 1, "element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "position_id": 4, "position": "Angrep", "squad_position": 1, "multiplier": 1, "is_captain": False, "is_vice_captain": False, "on_bench": False, "active_chip": "", "is_triple_captain": False, "event_points": 0, "gw_contribution": 0, "image_url": ""},
        {"entry": 2, "manager": "B", "team": "Bravo", "rank": 2, "element": 10, "player": "Isak", "club": "NEW", "team_id": 1, "position_id": 4, "position": "Angrep", "squad_position": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False, "on_bench": False, "active_chip": "", "is_triple_captain": False, "event_points": 0, "gw_contribution": 0, "image_url": ""},
        {"entry": 3, "manager": "C", "team": "Charlie", "rank": 3, "element": 10, "player": "Isak", "club": "NEW", "team_id": 1, "position_id": 4, "position": "Angrep", "squad_position": 1, "multiplier": 3, "is_captain": True, "is_vice_captain": False, "on_bench": False, "active_chip": "Triple Captain", "is_triple_captain": True, "event_points": 0, "gw_contribution": 0, "image_url": ""},
    ])
    events = pd.DataFrame([
        {"entry": 1, "manager": "A", "team": "Alpha", "event_transfers_cost": 0, "team_value": 100.0, "bank": 0.0, "active_chip": ""},
        {"entry": 2, "manager": "B", "team": "Bravo", "event_transfers_cost": 4, "team_value": 100.0, "bank": 0.0, "active_chip": ""},
        {"entry": 3, "manager": "C", "team": "Charlie", "event_transfers_cost": 0, "team_value": 100.0, "bank": 0.0, "active_chip": "Triple Captain"},
    ])
    players = pd.DataFrame([
        {"element": 10, "player": "Isak", "club": "NEW", "team_id": 1, "ownership_count": 2, "ownership_pct": 66.7, "captain_count": 2, "captain_pct": 66.7, "triple_captain_count": 1, "effective_ownership_pct": 166.7, "live_minutes": 0, "event_points": 0, "image_url": ""},
        {"element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "ownership_count": 1, "ownership_pct": 33.3, "captain_count": 0, "captain_pct": 0.0, "triple_captain_count": 0, "effective_ownership_pct": 33.3, "live_minutes": 0, "event_points": 0, "image_url": ""},
    ])
    return {"event": 3, "picks": picks, "manager_events": events, "players": players, "loaded_managers": 3, "league_size": 3, "errors": []}


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        config = LeagueConfig(
            league_id=25220,
            name="Lofthus Road Open",
            season_fallback="2026/27",
            data_dir=ROOT / "data",
        )
        history = HistoryStore(config.data_dir)
        client = FakeClient({10: 10, 20: 0}, phase_totals={1: 20, 2: 10, 3: 5})
        state = build_live_state(client, managers(), history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        self.engine = AppEngine(config, client=client, eager=True)
        self.engine.seed(BOOTSTRAP, managers(), state=state, histories={})
        self.client = TestClient(create_app(self.engine))

    def tearDown(self):
        self.temp.cleanup()

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_league_uses_live_truth(self):
        r = self.client.get("/api/league")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        table = body["table"]
        self.assertEqual(len(table), 3)
        # C has TC on 10-point Isak = 30, B captain 20 minus 4 hits = 16, A Haaland 0.
        by_entry = {row["entry"]: row for row in table}
        self.assertEqual(by_entry[3]["gw"], 30)
        self.assertEqual(by_entry[2]["gw"], 16)
        self.assertEqual(by_entry[1]["gw"], 0)
        self.assertEqual(by_entry[3]["rank"], 1)
        self.assertTrue(body["status"]["provisional"])
        self.assertTrue(body["status"]["is_live"])

    def test_live(self):
        r = self.client.get("/api/live")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["live_ready"])
        self.assertEqual(body["status"]["event_id"], 3)
        self.assertTrue(any(p["player"] == "Isak" for p in body["player_impacts"]))

    def test_manager_squad_and_captain(self):
        r = self.client.get("/api/managers/3")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["manager"]["manager"], "C")
        self.assertEqual(body["manager"]["chip"], "Triple Captain")
        xi = body["squad"]["xi"]
        self.assertTrue(any(p["is_triple_captain"] for p in xi))
        cap = self.client.get("/api/managers/3/captain").json()
        self.assertEqual(cap["captain"]["player"], "Isak")
        self.assertTrue(cap["captain"]["is_triple_captain"])

    def test_rival(self):
        r = self.client.get("/api/rival", params={"manager_a": 2, "manager_b": 3})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["me"]["entry"], 2)
        self.assertEqual(body["rival"]["entry"], 3)
        self.assertIn("cheer_for", body)
        self.assertIn("hope_blank", body)
        self.assertIn("live_gap", body)

    def test_history_preserves_2024_25_bronze(self):
        r = self.client.get("/api/history")
        self.assertEqual(r.status_code, 200)
        overall = {row["season"]: row for row in r.json()["overall"]}
        self.assertEqual(overall["2024/25"]["third_place"], "Rasmus Grytvik-Skoglund")
        self.assertEqual(overall["2024/25"]["winner"], "Mats Øyvind Jacobsen Arntzen")

    def test_hall_of_fame_canonical_rasmus(self):
        r = self.client.get("/api/hall-of-fame")
        self.assertEqual(r.status_code, 200)
        rows = r.json()["rows"]
        names = [row["manager"] for row in rows]
        self.assertIn("Rasmus Grytvik-Skoglund", names)
        self.assertNotIn("Rasmus Skoglund", names)
        rasmus = next(row for row in rows if row["manager"] == "Rasmus Grytvik-Skoglund")
        self.assertGreaterEqual(rasmus["league_bronze"], 1)

    def test_unknown_manager_404(self):
        r = self.client.get("/api/managers/999999")
        self.assertEqual(r.status_code, 404)

    def test_home_uses_one_snapshot(self):
        r = self.client.get("/api/home")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        sid = body["status"]["snapshot_id"]
        self.assertTrue(sid)
        self.assertEqual(len(body["managers"]), 3)
        last = body["managers"][-1]
        self.assertIn(last["entry"], {1, 2, 3})
        keys = [s["key"] for s in body["news"]]
        self.assertEqual(len(keys), len(set(keys)))

    def test_min_lofthus_manager_outside_top5(self):
        r = self.client.get("/api/managers")
        entries = [m["entry"] for m in r.json()["managers"]]
        self.assertIn(3, entries)
        detail = self.client.get("/api/managers/1")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["manager"]["entry"], 1)

    def test_rival_does_not_invent_scoring(self):
        r = self.client.get("/api/rival", params={"manager_a": 1, "manager_b": 2})
        self.assertEqual(r.status_code, 200)
        headlines = [e["headline"] for e in r.json()["my_unique"] + r.json()["rival_unique"]]
        for h in headlines:
            self.assertNotIn("scoring", h.lower())

    def test_differentials_require_points(self):
        r = self.client.get("/api/analysis/differentials")
        self.assertEqual(r.status_code, 200)
        for p in r.json()["players"]:
            self.assertGreater(p["event_points"], 0)

    def test_compare(self):
        r = self.client.get("/api/compare", params={"manager_a": 1, "manager_b": 3})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["a"]["entry"], 1)
        self.assertEqual(r.json()["b"]["entry"], 3)

    def test_month_follows_current_event(self):
        from lro_fpl import current_month_phase
        august = {
            "events": [{"id": 2, "is_current": True, "finished": False, "deadline_time": "2026-08-22T10:00:00Z"}],
            "phases": [
                {"id": 1, "name": "August", "start_event": 1, "stop_event": 2},
                {"id": 2, "name": "September", "start_event": 3, "stop_event": 6},
            ],
        }
        self.assertEqual(current_month_phase(august, now_month=9)["name"], "August")
        sept = {
            "events": [{"id": 3, "is_current": True, "finished": False, "deadline_time": "2026-09-12T10:00:00Z"}],
            "phases": august["phases"],
        }
        self.assertEqual(current_month_phase(sept, now_month=8)["name"], "September")

    def test_fpl_picks_cache_can_be_invalidated(self):
        from lro_fpl import FPLClient
        client = FPLClient()
        client._set_cached("GET:/entry/1/event/3/picks/", {"picks": []}, ttl=900)
        self.assertGreater(client.invalidate_picks(3), 0)
        self.assertIsNone(client._get_cached("GET:/entry/1/event/3/picks/"))

    def test_membership_is_not_inferred(self):
        r = self.client.get("/api/managers/3")
        self.assertEqual(r.json()["lofthus_membership"], [])

    def test_news_and_archive(self):
        self.assertEqual(self.client.get("/api/news").status_code, 200)
        self.assertEqual(self.client.get("/api/archive").status_code, 200)
        self.assertEqual(self.client.get("/api/players/popular").status_code, 200)
        self.assertEqual(self.client.get("/api/analysis/captain").status_code, 200)
        self.assertEqual(self.client.get("/api/analysis/ownership").status_code, 200)
        self.assertEqual(self.client.get("/api/analysis/chips").status_code, 200)
        self.assertEqual(self.client.get("/api/month").status_code, 200)


if __name__ == "__main__":
    unittest.main()
