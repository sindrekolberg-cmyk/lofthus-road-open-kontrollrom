import time

from api.league_registry import LeagueRuntime, LeagueRuntimeRegistry


class DummyEngine:
    _pool = None


def _runtime(league_id: int) -> LeagueRuntime:
    now = time.time()
    return LeagueRuntime(
        league_id=league_id,
        name=f"Liga {league_id}",
        engine=DummyEngine(),  # type: ignore[arg-type]
        league_info={"id": league_id},
        created_at=now,
        last_used_at=now,
    )


def test_cached_read_at_capacity_does_not_evict_other_tenant():
    registry = LeagueRuntimeRegistry(max_leagues=2, idle_ttl_seconds=3600)
    registry._items[101] = _runtime(101)
    registry._items[102] = _runtime(102)

    result = registry.get(101)

    assert result.league_id == 101
    assert set(registry._items) == {101, 102}
    assert registry._evicted_total == 0


def test_diagnostics_at_capacity_is_read_only_for_fresh_tenants():
    registry = LeagueRuntimeRegistry(max_leagues=2, idle_ttl_seconds=3600)
    registry._items[101] = _runtime(101)
    registry._items[102] = _runtime(102)

    diagnostics = registry.diagnostics()

    assert diagnostics["active_tenants"] == 2
    assert set(registry._items) == {101, 102}
    assert registry._evicted_total == 0
