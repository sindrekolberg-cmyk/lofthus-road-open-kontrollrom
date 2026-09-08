import threading

from api.engine import AppEngine


def test_light_snapshot_does_not_start_manager_history_sweep(monkeypatch):
    engine = AppEngine()
    monkeypatch.setattr(engine, "load_shell", lambda ttl=90.0: ({"events": []}, [], []))
    monkeypatch.setattr(engine, "live_state", lambda: None)

    def should_not_run():
        raise AssertionError("histories() should stay lazy")

    monkeypatch.setattr(engine, "histories", should_not_run)

    snapshot = engine.light_snapshot()

    assert snapshot.histories is None
    assert snapshot.state is None


def test_engine_schedules_one_reveal_journal_write_per_gameweek(monkeypatch):
    engine = AppEngine()
    written = []
    done = threading.Event()

    class State:
        event_id = 7
        is_finished = False
        is_live = True
        event_status = "live"

    def fake_record(_engine, _state, kind):
        written.append(kind)
        done.set()
        return True

    monkeypatch.setattr("api.engine.league_journal.record", fake_record)

    engine._schedule_journal(State())  # type: ignore[arg-type]
    engine._schedule_journal(State())  # type: ignore[arg-type]

    assert done.wait(timeout=1)
    assert written == ["reveal"]
