from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from lro_history import HistoryStore
from lro_live import build_live_state, _rank_min
from lro_league import form_rows
from lro_rival import compare_managers
from lro_newsroom import generate_candidates, merge_persistent_stories, _story
from lro_routes import parse_route, manager_href
from lro_fpl import player_catalog


class FakeClient:
    def __init__(self, points: dict[int, int], phase_totals: dict[int, int] | None = None):
        self.points = points
        self.phase_totals = phase_totals or {}

    def fixtures(self, event_id):
        return [{"event": event_id, "team_h": 1, "team_a": 2, "started": True, "finished": False, "team_h_score": 1, "team_a_score": 0}]

    def event_live(self, event_id):
        return {"elements": [{"id": e, "stats": {"total_points": p, "minutes": 70, "goals_scored": 1 if p >= 5 else 0, "assists": 0, "clean_sheets": 0, "bonus": 0}} for e, p in self.points.items()]}

    def league_phase_standings(self, league_id, phase_id):
        return [{"entry": e, "total": p} for e, p in self.phase_totals.items()]


BOOTSTRAP = {
    "events": [{"id": 3, "is_current": True, "is_next": False, "finished": False}],
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
        {"entry": 1, "manager": "A", "team": "Alpha", "rank": 1, "element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "position_id": 4, "position": "Angrep", "squad_position": 1, "multiplier": 1, "is_captain": False, "is_vice_captain": False, "on_bench": False, "active_chip": "", "is_triple_captain": False, "event_points": 0, "gw_contribution": 0},
        {"entry": 2, "manager": "B", "team": "Bravo", "rank": 2, "element": 10, "player": "Isak", "club": "NEW", "team_id": 1, "position_id": 4, "position": "Angrep", "squad_position": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False, "on_bench": False, "active_chip": "", "is_triple_captain": False, "event_points": 0, "gw_contribution": 0},
        {"entry": 3, "manager": "C", "team": "Charlie", "rank": 3, "element": 10, "player": "Isak", "club": "NEW", "team_id": 1, "position_id": 4, "position": "Angrep", "squad_position": 1, "multiplier": 3, "is_captain": True, "is_vice_captain": False, "on_bench": False, "active_chip": "Triple Captain", "is_triple_captain": True, "event_points": 0, "gw_contribution": 0},
    ])
    events = pd.DataFrame([
        {"entry": 1, "manager": "A", "team": "Alpha", "event_transfers_cost": 0, "team_value": 100.0, "bank": 0.0},
        {"entry": 2, "manager": "B", "team": "Bravo", "event_transfers_cost": 4, "team_value": 100.0, "bank": 0.0},
        {"entry": 3, "manager": "C", "team": "Charlie", "event_transfers_cost": 0, "team_value": 100.0, "bank": 0.0},
    ])
    players = pd.DataFrame([
        {"element": 10, "player": "Isak", "club": "NEW", "team_id": 1, "ownership_count": 2, "ownership_pct": 66.7, "captain_count": 2, "captain_pct": 66.7, "triple_captain_count": 1, "effective_ownership_pct": 166.7, "live_minutes": 0, "event_points": 0},
        {"element": 20, "player": "Haaland", "club": "MCI", "team_id": 2, "ownership_count": 1, "ownership_pct": 33.3, "captain_count": 0, "captain_pct": 0.0, "triple_captain_count": 0, "effective_ownership_pct": 33.3, "live_minutes": 0, "event_points": 0},
    ])
    return {"event": 3, "picks": picks, "manager_events": events, "players": players, "loaded_managers": 3, "league_size": 3, "errors": []}


class V810CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.history = HistoryStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_captain_triple_captain_hits_and_live_rank_are_one_truth(self):
        state = build_live_state(FakeClient({10: 10, 20: 0}), managers(), self.history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        a, b, c = (state.manager(i) for i in (1, 2, 3))
        self.assertEqual(a.live_gw_points, 0)
        self.assertEqual(b.live_gw_gross, 20)
        self.assertEqual(b.transfer_hits, 4)
        self.assertEqual(b.live_gw_points, 16)
        self.assertEqual(c.live_gw_points, 30)
        self.assertEqual(b.captain, "Isak (C)")
        self.assertEqual(c.captain, "Isak (TC)")
        self.assertEqual(c.live_rank, 1)
        self.assertEqual(b.live_rank, 2)
        self.assertEqual(a.live_rank, 3)
        self.assertEqual(c.live_total_points, 110)
        self.assertEqual(state.month_ranking()[0].entry, 3)


    def test_integration_same_live_score_reaches_form_and_rival(self):
        state = build_live_state(FakeClient({10: 10, 20: 0}), managers(), self.history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        histories = {
            1: {"current": [{"event": 1, "points": 50, "total_points": 50, "overall_rank": 100}]},
            2: {"current": [{"event": 1, "points": 45, "total_points": 45, "overall_rank": 200}]},
            3: {"current": [{"event": 1, "points": 40, "total_points": 40, "overall_rank": 300}]},
        }
        rows = form_rows(managers(), histories, 2, state, last_n=5)
        live_row = next(r for r in rows if r.get("is_live"))
        self.assertEqual(live_row["points"], state.manager(2).live_gw_points)
        self.assertEqual(live_row["league_rank"], state.manager(2).live_rank)
        duel = compare_managers(state, 2, 1)
        self.assertIsNotNone(duel)
        self.assertEqual(duel.me.live_gw_points, state.manager(2).live_gw_points)
        self.assertEqual(duel.me.live_total_points, state.manager(2).live_total_points)

    def test_rank_ties_use_competition_min_rank(self):
        self.assertEqual(_rank_min({1: 100, 2: 100, 3: 90}), {1: 1, 2: 1, 3: 3})

    def test_unplayed_zero_is_not_called_failure(self):
        state = build_live_state(FakeClient({10: 10, 20: 0}), managers(), self.history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        stories = generate_candidates(state, managers(), BOOTSTRAP, self.history, histories={})
        text = " ".join(s.headline + " " + s.meta for s in stories).casefold()
        self.assertNotIn("haaland fikk 0", text)
        self.assertNotIn("haaland endte på 0", text)

    def test_live_movement_language_is_provisional(self):
        state = build_live_state(FakeClient({10: 10, 20: 0}), managers(), self.history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        stories = generate_candidates(state, managers(), BOOTSTRAP, self.history, histories={})
        movement = [s for s in stories if s.category == "movement_live"]
        for story in movement:
            self.assertIn("foreløpig", story.headline.casefold())

    def test_newsroom_keeps_stronger_existing_story(self):
        state = build_live_state(FakeClient({10: 10, 20: 0}), managers(), self.history, 25220, bootstrap=BOOTSTRAP, ownership=ownership())
        old = _story("king", "record", "Stor historie", "", 90, "settled", 60)
        weak = _story("hole", "ownership", "Liten historie", "", 45, "context", 60)
        merged = merge_persistent_stories([weak], [old.to_dict()], state, limit=4)
        self.assertEqual(merged[0].key, "king")

    def test_rasmus_2024_25_third_place_fills_only_missing_field(self):
        p = Path(self.temp.name) / "overall_results.csv"
        p.write_text("season,winner,runner_up,third_place,note,status,source\n2024/25,Winner,Runner,,,,\n", encoding="utf-8")
        store = HistoryStore(Path(self.temp.name))
        row = store.overall_results().iloc[0]
        self.assertEqual(row["third_place"], "Rasmus Grytvik-Skoglund")
        self.assertEqual(store.merits_for("Rasmus Grytvik-Skoglund")["league_bronze"], 1)

    def test_rasmus_correction_never_overwrites_explicit_archive_value(self):
        p = Path(self.temp.name) / "overall_results.csv"
        p.write_text("season,winner,runner_up,third_place,note,status,source\n2024/25,Winner,Runner,Someone Else,,,\n", encoding="utf-8")
        store = HistoryStore(Path(self.temp.name))
        self.assertEqual(store.overall_results().iloc[0]["third_place"], "Someone Else")


    def test_player_catalog_exposes_premier_league_image_url(self):
        catalog = player_catalog(BOOTSTRAP)
        self.assertEqual(catalog[10]["code"], 123456)
        self.assertTrue(catalog[10]["image_url"].endswith("/p123456.png"))

    def test_routes_roundtrip_manager_and_backlink_shape(self):
        route = parse_route({"page": "Manager", "manager": "42", "me": "7"})
        self.assertEqual(route.manager, 42)
        self.assertEqual(route.me, 7)
        self.assertIn("page=Manager", manager_href(42, me=7))
        self.assertIn("manager=42", manager_href(42, me=7))


if __name__ == "__main__":
    unittest.main()
