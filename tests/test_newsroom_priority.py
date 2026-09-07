from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from lro_history import HistoryStore
from lro_live import LiveState, ManagerLiveState, PlayerImpact
from lro_newsroom import (
    _decision_stories,
    _story,
    desk_score,
    generate_candidates,
    homepage_feed,
)


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _mgr(**kwargs) -> ManagerLiveState:
    base = dict(
        entry=1, manager="Nils", team="Nils FC", previous_rank=8, live_rank=1, live_rank_change=7,
        official_total=100, official_event_points=0, official_total_before_gw=100,
        live_gw_points=66, live_gw_gross=66, transfer_hits=0, live_total_points=166,
        captain="Salah", captain_element=10, vice_captain="", vice_element=0, active_chip="",
        players_started=11, players_finished=11, players_live=0, players_remaining=0,
        month_points=10, month_rank=1, team_value=100.0, bank=0.0,
    )
    base.update(kwargs)
    return ManagerLiveState(**base)


def _impact(**kwargs) -> PlayerImpact:
    base = dict(
        element=10, player="Salah", club="LIV", event_points=1, ownership_count=20,
        ownership_pct=40.0, captain_count=8, triple_captain_count=0, effective_ownership_pct=50.0,
        live_minutes=90, fixture_status="finished", impact_score=10.0, image_url="",
    )
    base.update(kwargs)
    return PlayerImpact(**base)


def _state(managers, impacts, picks) -> LiveState:
    return LiveState(
        event_id=3,
        event_status="live",
        is_live=True,
        is_finished=False,
        fetched_at=NOW,
        fixtures=[],
        manager_live=managers,
        player_impacts=impacts,
        ownership={"picks": picks, "league_size": len(managers), "loaded_managers": len(managers)},
        month_name="September",
    )


class NewsroomPriorityTests(unittest.TestCase):
    def test_tc_smell_beats_generic_free_hit(self):
        tc = _story("tc-3-1", "chip", "Triple Captain-smell for Ola", "Salah endte på 1 poeng før trippelen", 98, "settled", 60, source_event=3)
        fh = _story("chipplay-3-2", "chip", "Nils kjører Free Hit", "66 poeng · 7 plasser opp", 87, "live", 60, source_event=3)
        feed = homepage_feed([fh, tc], 3, limit=4)
        self.assertEqual(feed[0].key, "tc-3-1")
        self.assertGreater(desk_score(tc, 3), desk_score(fh, 3))

    def test_unique_haul_beats_generic_free_hit(self):
        unique = _story("unique-3-99", "unique", "Eneste eier traff jackpot", "Kun Ingrid eier X – som leverte 15 poeng", 90, "settled", 60, source_event=3)
        fh = _story("chipplay-3-2", "chip", "Nils kjører Free Hit", "66 poeng", 87, "live", 60, source_event=3)
        feed = homepage_feed([fh, unique], 3, limit=4)
        self.assertEqual(feed[0].key, "unique-3-99")

    def test_confirmed_bench_haul_beats_generic_free_hit(self):
        bench = _story("bench-3-4", "bench", "12 poeng råtner på benken", "Mats benket Mitchell", 85, "settled", 60, source_event=3)
        fh = _story("chipplay-3-2", "chip", "Nils kjører Free Hit", "66 poeng", 87, "live", 60, source_event=3)
        feed = homepage_feed([fh, bench], 3, limit=4)
        self.assertEqual(feed[0].key, "bench-3-4")

    def test_two_free_hit_managers_do_not_take_two_top_stories(self):
        a = _story("chipplay-3-1", "chip", "Nils kjører Free Hit", "66 poeng", 87, "live", 60, source_event=3)
        b = _story("chipplay-3-2", "chip", "Stian kjører Free Hit", "68 poeng", 87, "live", 60, source_event=3)
        unique = _story("unique-3-9", "unique", "Eneste eier traff jackpot", "15 poeng", 90, "settled", 60, source_event=3)
        bench = _story("bench-3-4", "bench", "12 poeng råtner på benken", "Mats", 85, "settled", 60, source_event=3)
        cap = _story("capfail-3-5", "captain", "Kapteinsmell for Ola", "0 poeng", 82, "settled", 60, source_event=3)
        feed = homepage_feed([a, b, unique, bench, cap], 3, limit=4)
        keys = [s.key for s in feed]
        chip_keys = [k for k in keys if k.startswith("chipplay-")]
        self.assertLessEqual(len(chip_keys), 1)
        self.assertIn("unique-3-9", keys)
        self.assertIn("bench-3-4", keys)
        self.assertIn("capfail-3-5", keys)

    def test_movement_stories_are_not_snakkiser(self):
        move = {"key": "move", "category": "movement", "source_event": 3, "importance": 96, "headline": "Nils klatrer syv plasser"}
        live = {"key": "now", "category": "live", "source_event": 3, "importance": 84, "headline": "Isak herjer"}
        feed = homepage_feed([move, live], 3, limit=5)
        self.assertEqual([s["key"] for s in feed], ["now"])

    def test_stale_previous_gw_ranks_below_current(self):
        stale = _story("old", "captain", "Kapteinsmell for i går", "0 poeng", 98, "settled", 60, source_event=2)
        now = _story("now", "differential", "Mitchell er runden sin differensial: 15 poeng", "2 %", 86, "settled", 60, source_event=3)
        self.assertGreater(desk_score(now, 3), desk_score(stale, 3))
        feed = homepage_feed([stale, now], 3, limit=4)
        self.assertEqual(feed[0].key, "now")
        self.assertFalse(any(s.key == "old" for s in feed))

    def test_no_bench_smell_while_autosub_pending(self):
        picks = pd.DataFrame([
            {
                "entry": 1, "manager": "Mats", "element": 30, "player": "Mitchell", "multiplier": 0,
                "on_bench": True, "event_points": 12, "gw_contribution": 0, "autosub_status": "pending",
                "autosub_in": False, "is_captain": False, "is_vice_captain": False, "is_triple_captain": False,
            }
        ])
        state = _state(
            [_mgr(entry=1, manager="Mats", active_chip="")],
            [_impact(element=30, player="Mitchell", event_points=12, ownership_count=4, ownership_pct=8.0)],
            picks,
        )
        stories = _decision_stories(state, True)
        self.assertFalse(any(s.category == "bench" for s in stories))

    def test_confirmed_bench_smell_after_autosub_settled(self):
        picks = pd.DataFrame([
            {
                "entry": 1, "manager": "Mats", "element": 30, "player": "Mitchell", "multiplier": 0,
                "on_bench": True, "event_points": 12, "gw_contribution": 0, "autosub_status": "",
                "autosub_in": False, "is_captain": False, "is_vice_captain": False, "is_triple_captain": False,
            }
        ])
        state = _state(
            [_mgr(entry=1, manager="Mats", active_chip="")],
            [_impact(element=30, player="Mitchell", event_points=12, ownership_count=4, ownership_pct=8.0)],
            picks,
        )
        stories = _decision_stories(state, True)
        self.assertTrue(any(s.category == "bench" and "råtner" in s.headline for s in stories))

    def test_generate_candidates_scans_all_managers_for_tc(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        history = HistoryStore(Path(tmp.name))
        picks = pd.DataFrame([
            {
                "entry": 1, "manager": "Ola", "element": 10, "player": "Salah", "multiplier": 3,
                "on_bench": False, "event_points": 1, "gw_contribution": 3, "autosub_status": "",
                "autosub_in": False, "is_captain": True, "is_vice_captain": False, "is_triple_captain": True,
                "active_chip": "Triple Captain",
            },
            {
                "entry": 2, "manager": "Nils", "element": 20, "player": "Palmer", "multiplier": 1,
                "on_bench": False, "event_points": 6, "gw_contribution": 6, "autosub_status": "",
                "autosub_in": False, "is_captain": True, "is_vice_captain": False, "is_triple_captain": False,
                "active_chip": "Free Hit",
            },
            {
                "entry": 3, "manager": "Ingrid", "element": 99, "player": "Mitchell", "multiplier": 1,
                "on_bench": False, "event_points": 15, "gw_contribution": 15, "autosub_status": "",
                "autosub_in": False, "is_captain": False, "is_vice_captain": False, "is_triple_captain": False,
                "active_chip": "",
            },
        ])
        state = _state(
            [
                _mgr(entry=1, manager="Ola", active_chip="Triple Captain", live_gw_points=40, live_rank_change=1),
                _mgr(entry=2, manager="Nils", active_chip="Free Hit", live_gw_points=66, live_rank_change=7),
                _mgr(entry=3, manager="Ingrid", active_chip="", live_gw_points=50, live_rank_change=2, live_rank=3),
            ],
            [
                _impact(element=10, player="Salah", event_points=1, triple_captain_count=1, captain_count=1),
                _impact(element=20, player="Palmer", event_points=6, captain_count=1),
                _impact(element=99, player="Mitchell", event_points=15, ownership_count=1, ownership_pct=2.0, captain_count=0),
            ],
            picks,
        )
        stories = generate_candidates(state, [], {"events": [{"id": 3, "finished": False}]}, history, {})
        feed = homepage_feed(stories, 3, limit=4)
        headlines = [s.headline for s in feed]
        self.assertTrue(any("Triple Captain-smell" in h for h in headlines))
        self.assertFalse(sum("kjører Free Hit" in h for h in headlines) >= 1)


class TableAndMonthStoryTests(unittest.TestCase):
    def test_big_live_climb_becomes_a_snakkis(self):
        from lro_newsroom import _table_stories
        state = _state([_mgr(entry=1, manager="Nils", previous_rank=20, live_rank=13, live_rank_change=7)], [], pd.DataFrame())
        stories = _table_stories(state)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0].category, "table")
        self.assertIn("klatrer kraftig", stories[0].headline)
        self.assertIn("opp 7 plasser", stories[0].meta)

    def test_taking_the_lead_is_the_bigger_story(self):
        from lro_newsroom import _table_stories
        state = _state([_mgr(entry=1, manager="Nils", previous_rank=8, live_rank=1, live_rank_change=7)], [], pd.DataFrame())
        stories = _table_stories(state)
        self.assertEqual(len(stories), 1)
        self.assertIn("tar tabelltoppen", stories[0].headline)

    def test_ordinary_rank_churn_is_not_a_snakkis(self):
        from lro_newsroom import _table_stories
        state = _state([_mgr(entry=1, previous_rank=6, live_rank=4, live_rank_change=2)], [], pd.DataFrame())
        self.assertEqual(_table_stories(state), [])

    def test_losing_the_lead_outranks_a_climb(self):
        from lro_newsroom import _table_stories
        state = _state(
            [
                _mgr(entry=1, manager="Ola", previous_rank=1, live_rank=4, live_rank_change=-3),
                _mgr(entry=2, manager="Nils", previous_rank=9, live_rank=2, live_rank_change=7),
            ],
            [], pd.DataFrame(),
        )
        stories = sorted(_table_stories(state), key=lambda s: desk_score(s, 3), reverse=True)
        self.assertIn("mister tabelltoppen", stories[0].headline)

    def test_captain_drama_still_outranks_table_movement(self):
        cap = _story("capfail-3-1", "captain", "Kapteinssmell for Ola", "O'Reilly endte på 0 poeng", 82, "settled", 60, source_event=3)
        table = _story("table-up-3-2", "table", "Nils klatrer kraftig live", "Opp 7 plasser", 85, "live", 60, source_event=3)
        self.assertGreater(desk_score(cap, 3), desk_score(table, 3))
        self.assertEqual(homepage_feed([table, cap], 3, limit=4)[0].key, "capfail-3-1")

    def test_month_race_ranks_below_differential(self):
        month = _story("month-chase", "month", "Stian jager månedsseieren", "3 poeng bak", 80, "live", 60, source_event=3)
        diff = _story("diff-3-9", "differential", "Mitchell er runden sin differensial: 15 poeng", "2 %", 86, "settled", 60, source_event=3)
        feed = homepage_feed([month, diff], 3, limit=4)
        self.assertEqual([s.key for s in feed], ["diff-3-9", "month-chase"])

    def test_only_one_month_story_reaches_the_homepage(self):
        lead = _story("month-lead", "month", "Andreas leder september", "88 poeng", 79, "live", 60, source_event=3)
        chase = _story("month-chase", "month", "Stian jager månedsseieren", "3 poeng bak", 80, "live", 60, source_event=3)
        feed = homepage_feed([lead, chase], 3, limit=4)
        self.assertEqual([s.key for s in feed], ["month-chase"])

    def test_thin_data_gives_fewer_stories_instead_of_filler(self):
        weak = _story("own", "ownership", "Eierskap", "", 40, "settled", 60, source_event=3)
        diff = _story("diff-3-9", "differential", "Mitchell 15 poeng", "2 %", 86, "settled", 60, source_event=3)
        feed = homepage_feed([diff, weak], 3, limit=4)
        self.assertEqual(len(feed), 1)

    def test_hot_streak_needs_three_finished_rounds(self):
        from lro_newsroom import _momentum_stories
        state = _state([_mgr(entry=1, manager="Ola"), _mgr(entry=2, manager="Nils")], [], pd.DataFrame())
        histories = {
            1: {"current": [{"event": e, "points": 90} for e in (1, 2)]},
            2: {"current": [{"event": e, "points": 40} for e in (1, 2)]},
        }
        self.assertEqual(_momentum_stories(state, histories), [])
        histories[1]["current"].append({"event": 3, "points": 90})
        histories[2]["current"].append({"event": 3, "points": 40})
        state = _state([_mgr(entry=1, manager="Ola"), _mgr(entry=2, manager="Nils")], [], pd.DataFrame())
        state.event_id = 4
        stories = _momentum_stories(state, histories)
        self.assertTrue(any("heit periode" in s.headline for s in stories))


class CupHistoryTests(unittest.TestCase):
    def test_robin_has_one_cup_gold_and_nickolai_won_2021_22(self):
        from lro_config import LeagueConfig
        config = LeagueConfig(
            league_id=25220, name="Lofthus Road Open", season_fallback="2026/27",
            data_dir=Path(__file__).resolve().parents[1] / "data",
        )
        store = HistoryStore(config.data_dir)
        cup = store.cup_results()
        by_season = {str(r.get("season")): str(r.get("winner")) for r in cup.to_dict("records")}
        self.assertEqual(by_season.get("2021/22"), "Nickolai Macpherson")
        self.assertEqual(sum(1 for w in by_season.values() if w == "Robin Andersen"), 1)
        self.assertEqual(store.merits_for("Robin Andersen")["cup_gold"], 1)
        self.assertEqual(store.merits_for("Nickolai Macpherson")["cup_gold"], 1)


class CrestPayloadTests(unittest.TestCase):
    def test_hull_and_coventry_use_verified_pl_badge_codes(self):
        from api.serialize import fixture_payload
        bootstrap = {
            "teams": [
                {"id": 11, "name": "Hull City", "short_name": "HUL", "code": 88},
                {"id": 7, "name": "Coventry City", "short_name": "COV", "code": 9},
            ]
        }
        state = LiveState(
            event_id=3, event_status="pre", is_live=False, is_finished=False, fetched_at=NOW,
            fixtures=[], manager_live=[], player_impacts=[], ownership={}, month_name="September",
        )
        rows = fixture_payload(state, bootstrap, fixtures=[{
            "id": 1, "event": 3, "team_h": 11, "team_a": 7, "started": False, "finished": False,
            "kickoff_time": "2026-09-12T14:00:00Z", "minutes": 0,
        }])
        self.assertEqual(rows[0]["home"], "HUL")
        self.assertEqual(rows[0]["away"], "COV")
        self.assertEqual(rows[0]["home_code"], 88)
        self.assertEqual(rows[0]["away_code"], 9)
        self.assertIn("t88.png", rows[0]["home_badge"])
        self.assertIn("t9.png", rows[0]["away_badge"])


if __name__ == "__main__":
    unittest.main()
