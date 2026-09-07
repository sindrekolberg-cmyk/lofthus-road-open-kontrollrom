from datetime import datetime, timezone

from lro_league import effective_states
from lro_live import LiveState, ManagerLiveState


def manager(entry: int, name: str, rank: int, total: int) -> ManagerLiveState:
    return ManagerLiveState(
        entry=entry,
        manager=name,
        team=f"{name} XI",
        previous_rank=rank,
        live_rank=rank,
        live_rank_change=0,
        official_total=total,
        official_event_points=0,
        official_total_before_gw=total,
        live_gw_points=0,
        live_gw_gross=0,
        transfer_hits=0,
        live_total_points=total,
        captain="–",
        captain_element=0,
        vice_captain="",
        vice_element=0,
        active_chip="",
        players_started=0,
        players_finished=0,
        players_live=0,
        players_remaining=0,
        month_points=0,
        month_rank=0,
        team_value=0.0,
        bank=0.0,
    )


def test_effective_states_uses_canonical_live_rank_order():
    state = LiveState(
        event_id=3,
        event_status="between_matches",
        is_live=False,
        is_finished=False,
        fetched_at=datetime.now(timezone.utc),
        fixtures=[],
        manager_live=[
            manager(2, "Ingrid", 6, 150),
            manager(1, "Stian", 5, 151),
            manager(3, "Nils", 1, 180),
        ],
        player_impacts=[],
        ownership={},
        month_name="September",
    )

    rows = effective_states([], state)

    assert [row.manager for row in rows] == ["Nils", "Stian", "Ingrid"]
    assert [row.live_rank for row in rows] == [1, 5, 6]
