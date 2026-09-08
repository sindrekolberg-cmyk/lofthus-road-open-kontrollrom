from __future__ import annotations

from dataclasses import dataclass

from api.league_intelligence import _goal_for_rank, _simulate_table


@dataclass
class DummyManager:
    entry: int
    manager: str
    live_rank: int
    live_total_points: int


class DummyState:
    def __init__(self):
        self.event_id = 4
        self.manager_live = [
            DummyManager(1, "Leader", 1, 250),
            DummyManager(2, "Chaser", 2, 238),
            DummyManager(3, "Third", 3, 220),
        ]

    def manager(self, entry: int):
        return next((row for row in self.manager_live if row.entry == entry), None)


def _history(*points: int) -> dict:
    return {
        "current": [
            {"event": index + 1, "points": value, "event_transfers_cost": 0}
            for index, value in enumerate(points)
        ]
    }


def test_auto_goal_follows_table_position():
    assert _goal_for_rank(1) == "win"
    assert _goal_for_rank(5) == "win"
    assert _goal_for_rank(8) == "top3"
    assert _goal_for_rank(20) == "top10"


def test_forecast_is_deterministic_and_returns_core_probabilities():
    state = DummyState()
    histories = {
        1: _history(61, 58, 65, 55),
        2: _history(57, 64, 59, 67),
        3: _history(48, 52, 55, 50),
    }
    bootstrap = {"events": [{"id": event} for event in range(1, 9)]}

    first = _simulate_table(
        state=state,
        histories=histories,
        bootstrap=bootstrap,
        entry_id=2,
        next_entry=1,
        simulations=400,
    )
    second = _simulate_table(
        state=state,
        histories=histories,
        bootstrap=bootstrap,
        entry_id=2,
        next_entry=1,
        simulations=400,
    )

    assert first == second
    assert 0 <= first["win_pct"] <= 100
    assert 0 <= first["top3_pct"] <= 100
    assert 0 <= first["beat_next_pct"] <= 100
    assert first["top3_pct"] >= first["win_pct"]
    assert first["rounds_remaining"] == 4
