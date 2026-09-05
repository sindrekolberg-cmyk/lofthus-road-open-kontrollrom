from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from lro_analysis import build_ownership, manager_squad, transfer_suggestions
from lro_fpl import current_month_phase, player_catalog
from lro_history import HistoryStore
from lro_odds import history_weight


class FakeClient:
    def __init__(self, bootstrap, picks, live=None, fixtures=None):
        self._bootstrap = bootstrap
        self._picks = picks
        self._live = live or {"elements": []}
        self._fixtures = fixtures or []

    def bootstrap(self):
        return self._bootstrap

    def event_live(self, event_id):
        return self._live

    def picks_many(self, entries, event_id, max_workers=8):
        return ({int(e): self._picks[int(e)] for e in entries if int(e) in self._picks}, {})

    def fixtures(self, event_id=None):
        return self._fixtures


def bootstrap_fixture():
    return {
        "events": [
            {"id": 1, "finished": True, "is_current": False, "deadline_time": "2026-08-15T10:00:00Z"},
            {"id": 2, "finished": False, "is_current": True, "deadline_time": "2026-08-22T10:00:00Z"},
            {"id": 3, "finished": False, "is_next": True, "deadline_time": "2026-09-12T10:00:00Z"},
        ],
        "phases": [
            {"id": 1, "name": "August", "start_event": 1, "stop_event": 2},
            {"id": 2, "name": "September", "start_event": 3, "stop_event": 6},
        ],
        "teams": [
            {"id": 1, "name": "Alpha", "short_name": "ALP", "strength": 4},
            {"id": 2, "name": "Beta", "short_name": "BET", "strength": 3},
            {"id": 3, "name": "Gamma", "short_name": "GAM", "strength": 3},
        ],
        "elements": [
            {"id": 10, "web_name": "Mid A", "first_name": "Mid", "second_name": "A", "team": 1, "element_type": 3, "now_cost": 71, "total_points": 20, "event_points": 8, "form": "7.0", "points_per_game": "6.5", "minutes": 180, "starts": 2, "expected_goals": "0.8", "expected_assists": "0.5", "expected_goal_involvements": "1.3", "selected_by_percent": "20.0", "transfers_in_event": 1000, "transfers_out_event": 100, "status": "a"},
            {"id": 11, "web_name": "Mid B", "first_name": "Mid", "second_name": "B", "team": 2, "element_type": 3, "now_cost": 82, "total_points": 18, "event_points": 6, "form": "6.0", "points_per_game": "6.0", "minutes": 180, "starts": 2, "expected_goals": "0.7", "expected_assists": "0.4", "expected_goal_involvements": "1.1", "selected_by_percent": "10.0", "transfers_in_event": 1000, "transfers_out_event": 100, "status": "a"},
            {"id": 12, "web_name": "Mid C", "first_name": "Mid", "second_name": "C", "team": 3, "element_type": 3, "now_cost": 83, "total_points": 18, "event_points": 6, "form": "6.0", "points_per_game": "6.0", "minutes": 180, "starts": 2, "expected_goals": "0.7", "expected_assists": "0.4", "expected_goal_involvements": "1.1", "selected_by_percent": "10.0", "transfers_in_event": 1000, "transfers_out_event": 100, "status": "a"},
        ],
    }


def test_prices_and_captain_math(tmpdir: Path):
    store = HistoryStore(tmpdir)
    managers = [
        {"entry": 1, "player_name": "Manager One", "entry_name": "One", "rank": 1, "last_rank": 2, "event_total": 70, "total": 140},
        {"entry": 2, "player_name": "Manager Two", "entry_name": "Two", "rank": 2, "last_rank": 1, "event_total": 65, "total": 135},
    ]
    picks = {
        1: {"active_chip": "3xc", "entry_history": {"points": 70, "total_points": 140, "bank": 5, "value": 1005}, "picks": [
            {"element": 10, "position": 1, "multiplier": 3, "is_captain": True, "is_vice_captain": False, "purchase_price": 70, "selling_price": 69},
        ]},
        2: {"active_chip": None, "entry_history": {"points": 65, "total_points": 135, "bank": 10, "value": 1000}, "picks": [
            {"element": 10, "position": 1, "multiplier": 2, "is_captain": True, "is_vice_captain": False, "purchase_price": 71, "selling_price": 71},
        ]},
    }
    live = {"elements": [{"id": 10, "stats": {"total_points": 8, "minutes": 90}}]}
    client = FakeClient(bootstrap_fixture(), picks, live=live)
    ownership = build_ownership(client, managers, store, event_id=2)
    player = ownership["players"].iloc[0]
    assert player["current_price"] == 7.1, player
    assert int(player["captain_count"]) == 2
    assert int(player["triple_captain_count"]) == 1
    squad = manager_squad(ownership, 1)
    assert float(squad.iloc[0]["current_price"]) == 7.1
    assert float(squad.iloc[0]["selling_price"]) == 6.9
    assert float(squad.iloc[0]["purchase_price"]) == 7.0


def test_transfer_budget():
    player_df = pd.DataFrame([
        {"element_id": 1, "web_name": "Out", "team_id": 1, "position_id": 3, "position": "Midtbane", "current_price": 8.0, "outlook_score": 50, "outlook_label": "Greit program", "outlook_expected_low": 12, "outlook_expected_high": 18, "status": "a", "fixture_window": []},
        {"element_id": 2, "web_name": "In 8.2", "team_id": 2, "position_id": 3, "position": "Midtbane", "current_price": 8.2, "outlook_score": 70, "outlook_label": "Sterkt program", "outlook_expected_low": 16, "outlook_expected_high": 22, "status": "a", "fixture_window": []},
        {"element_id": 3, "web_name": "In 8.3", "team_id": 3, "position_id": 3, "position": "Midtbane", "current_price": 8.3, "outlook_score": 75, "outlook_label": "Sterkt program", "outlook_expected_low": 17, "outlook_expected_high": 23, "status": "a", "fixture_window": []},
    ])
    my_squad = pd.DataFrame([{"element": 1, "player": "Out", "team_id": 1, "position_id": 3, "current_price": 8.0, "selling_price": 7.7}])
    out = transfer_suggestions(player_df, my_squad, {}, 3, bank=0.5, risk="Balansert", goal="Slå disse managerne")
    assert "In 8.2" in out["in_player"].tolist()
    assert "In 8.3" not in out["in_player"].tolist()
    row = out[out["in_player"] == "In 8.2"].iloc[0]
    assert float(row["budget"]) == 8.2


def test_month_calendar_and_aliases(tmpdir: Path):
    store = HistoryStore(tmpdir)
    assert current_month_phase(bootstrap_fixture(), now_month=9)["name"] == "August"
    assert store.canonical("Oskar Brun") == "Oskar Kristensen Brun"
    assert store.canonical("Kristoffer Wollvik Pettersen") == "Kristoffer W Pettersen"


def test_olympic_hof(tmpdir: Path):
    # 4 gold must beat 3 gold + more silvers.
    pd.DataFrame([
        {"season": "A", "winner": "Remi", "runner_up": "Robin", "third_place": "", "note": "", "status": "", "source": ""},
        {"season": "B", "winner": "Remi", "runner_up": "Robin", "third_place": "", "note": "", "status": "", "source": ""},
        {"season": "C", "winner": "Remi", "runner_up": "", "third_place": "", "note": "", "status": "", "source": ""},
        {"season": "D", "winner": "Remi", "runner_up": "", "third_place": "", "note": "", "status": "", "source": ""},
        {"season": "E", "winner": "Robin", "runner_up": "", "third_place": "", "note": "", "status": "", "source": ""},
        {"season": "F", "winner": "Robin", "runner_up": "", "third_place": "", "note": "", "status": "", "source": ""},
        {"season": "G", "winner": "Robin", "runner_up": "", "third_place": "", "note": "", "status": "", "source": ""},
    ]).to_csv(tmpdir / "overall_results.csv", index=False)
    store = HistoryStore(tmpdir)
    hof = store.hall_of_fame([])
    assert hof.iloc[0]["display_name"] == "Remi"
    assert int(hof.iloc[0]["gold"]) == 4


def test_history_weight():
    assert history_weight(1) > history_weight(10) > history_weight(20) > history_weight(30)


def run():
    cat = player_catalog(bootstrap_fixture())
    assert cat[10]["current_price"] == 7.1
    assert cat[10]["position"] == "Midtbane"
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        test_prices_and_captain_math(p)
        test_month_calendar_and_aliases(p)
    test_transfer_budget()
    with tempfile.TemporaryDirectory() as td:
        test_olympic_hof(Path(td))
    test_history_weight()
    print("V400 core tests: OK")


if __name__ == "__main__":
    run()

# Extra regression test kept below the main runner intentionally; invoked by the
# packaging test script as well.
def test_rivalradar_selected_only(tmpdir: Path):
    from lro_analysis import rival_analysis
    bs = bootstrap_fixture()
    fixtures = [
        {"event": 3, "team_h": 2, "team_a": 1, "team_h_difficulty": 2, "team_a_difficulty": 4},
        {"event": 4, "team_h": 2, "team_a": 3, "team_h_difficulty": 2, "team_a_difficulty": 4},
        {"event": 5, "team_h": 1, "team_a": 2, "team_h_difficulty": 3, "team_a_difficulty": 3},
    ]
    picks = {
        1: {"active_chip": None, "entry_history": {"points": 60, "total_points": 120, "bank": 5, "value": 1000}, "picks": [
            {"element": 10, "position": 1, "multiplier": 1, "is_captain": False, "is_vice_captain": False, "selling_price": 69},
        ]},
        2: {"active_chip": None, "entry_history": {"points": 65, "total_points": 130, "bank": 5, "value": 1000}, "picks": [
            {"element": 11, "position": 1, "multiplier": 1, "is_captain": False, "is_vice_captain": False, "selling_price": 82},
        ]},
        999: {"active_chip": None, "entry_history": {"points": 99, "total_points": 999}, "picks": [
            {"element": 12, "position": 1, "multiplier": 1, "is_captain": False, "is_vice_captain": False},
        ]},
    }
    class TrackingClient(FakeClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.requested = None
        def picks_many(self, entries, event_id, max_workers=8):
            self.requested = sorted(int(e) for e in entries)
            return super().picks_many(entries, event_id, max_workers)
    client = TrackingClient(bs, picks, live={"elements": []}, fixtures=fixtures)
    store = HistoryStore(tmpdir)
    managers = [
        {"entry": 1, "player_name": "Me", "entry_name": "Me FC", "rank": 2, "last_rank": 2, "event_total": 60, "total": 120},
        {"entry": 2, "player_name": "Rival", "entry_name": "Rival FC", "rank": 1, "last_rank": 1, "event_total": 65, "total": 130},
        {"entry": 999, "player_name": "Other", "entry_name": "Other FC", "rank": 3, "last_rank": 3, "event_total": 55, "total": 110},
    ]
    result = rival_analysis(client, managers, store, 1, [2], "Neste 3 GW", "Balansert", "Slå disse managerne")
    assert client.requested == [1, 2], client.requested
    assert result["error"] == ""
    assert 11 in result["they_have_i_lack"]["element_id"].astype(int).tolist()
    assert 12 in result["nobody_has"]["element_id"].astype(int).tolist()


def test_63_manager_ownership(tmpdir: Path):
    bs = bootstrap_fixture()
    managers = []
    picks = {}
    for i in range(1, 64):
        managers.append({"entry": i, "player_name": f"Manager {i:02d}", "entry_name": f"Team {i:02d}", "rank": i, "last_rank": i, "event_total": 60, "total": 120})
        picks[i] = {
            "active_chip": "3xc" if i == 1 else None,
            "entry_history": {"points": 60, "total_points": 120, "bank": 5, "value": 1000},
            "picks": [{"element": 10, "position": 1, "multiplier": 3 if i == 1 else (2 if i <= 20 else 1), "is_captain": i <= 20, "is_vice_captain": False, "selling_price": 71}],
        }
    client = FakeClient(bs, picks, live={"elements": [{"id": 10, "stats": {"total_points": 8, "minutes": 90}}]})
    store = HistoryStore(tmpdir)
    own = build_ownership(client, managers, store, event_id=2)
    assert own["loaded_managers"] == 63
    p = own["players"].iloc[0]
    assert int(p["ownership_count"]) == 63
    assert int(p["captain_count"]) == 20
    assert int(p["triple_captain_count"]) == 1
