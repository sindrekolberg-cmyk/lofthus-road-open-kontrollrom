from __future__ import annotations

import unittest

from lro_analysis import remaining_from_picks, resolve_effective_picks


def pick(
    element: int,
    position_id: int,
    squad_position: int,
    team_id: int,
    minutes: int,
    *,
    points: int = 0,
    name: str = "",
    cap: bool = False,
    vc: bool = False,
    tc: bool = False,
    chip: str = "",
    multiplier: int | None = None,
) -> dict:
    on_bench = squad_position > 11
    if multiplier is None:
        if on_bench:
            multiplier = 0
        elif tc:
            multiplier = 3
        elif cap:
            multiplier = 2
        else:
            multiplier = 1
    return {
        "entry": 1,
        "manager": "M",
        "element": element,
        "player": name or f"P{element}",
        "club": "X",
        "team_id": team_id,
        "position_id": position_id,
        "position": {1: "Keeper", 2: "Forsvar", 3: "Midtbane", 4: "Angrep"}[position_id],
        "squad_position": squad_position,
        "multiplier": multiplier,
        "is_captain": cap,
        "is_vice_captain": vc,
        "on_bench": on_bench,
        "active_chip": chip,
        "is_triple_captain": tc,
        "event_points": points,
        "live_minutes": minutes,
        "gw_contribution": points * max(multiplier, 0),
    }


def standard_343(
    *,
    oreilly_minutes: int = 0,
    oreilly_team: int = 1,
    first_bench_minutes: int = 0,
    first_bench_team: int = 2,
    extra: dict[int, dict] | None = None,
) -> list[dict]:
    """1 GK, 3 DEF, 4 MID, 3 FWD + bench MID/DEF/FWD/GK."""
    template = [
        pick(1, 1, 1, 1, 90, name="GK"),
        pick(2, 2, 2, 1, 90, name="DEF1"),
        pick(3, 2, 3, 1, 90, name="DEF2"),
        pick(4, 2, 4, 1, 90, name="DEF3"),
        pick(5, 3, 5, oreilly_team, oreilly_minutes, name="O'Reilly"),
        pick(6, 3, 6, 1, 90, name="MID2"),
        pick(7, 3, 7, 1, 90, name="MID3"),
        pick(8, 3, 8, 1, 90, name="MID4", cap=True),
        pick(9, 4, 9, 2, 0, name="FWD1"),
        pick(10, 4, 10, 2, 0, name="FWD2"),
        pick(11, 4, 11, 2, 0, name="FWD3"),
        pick(12, 3, 12, first_bench_team, first_bench_minutes, name="BenchMID"),
        pick(13, 2, 13, 2, 0, name="BenchDEF"),
        pick(14, 4, 14, 2, 0, name="BenchFWD"),
        pick(15, 1, 15, 2, 0, name="BenchGK"),
    ]
    extra = extra or {}
    by_el = {p["element"]: p for p in template}
    by_el.update(extra)
    return [by_el[i] for i in range(1, 16)]


TEAMS = {1: "finished", 2: "not_started", 3: "live", 4: "finished"}


def names_in(resolved, *, active: bool) -> set[str]:
    return {
        str(r["player"])
        for r in resolved
        if (r.get("multiplier", 0) > 0) is active
    }


class AutosubTests(unittest.TestCase):
    def test_dnp_starter_first_valid_bench_comes_in(self):
        rows = standard_343()
        resolved = resolve_effective_picks(rows, TEAMS)
        self.assertIn("BenchMID", names_in(resolved, active=True))
        self.assertNotIn("O'Reilly", names_in(resolved, active=True))
        incoming = next(r for r in resolved if r["player"] == "BenchMID")
        self.assertTrue(incoming["autosub_in"])
        self.assertEqual(incoming["autosub_status"], "confirmed")
        self.assertEqual(incoming["replaced_player"], "O'Reilly")
        self.assertEqual(remaining_from_picks(rows, TEAMS), 4)

    def test_invalid_formation_skips_to_next_bench(self):
        rows = standard_343(oreilly_minutes=90, oreilly_team=1)
        rows[3] = pick(4, 2, 4, 1, 0, name="DEF3")
        rows[11] = pick(12, 4, 12, 2, 0, name="BenchFWD-first")
        rows[12] = pick(13, 2, 13, 2, 0, name="BenchDEF")
        resolved = resolve_effective_picks(rows, TEAMS)
        active = names_in(resolved, active=True)
        self.assertIn("BenchDEF", active)
        self.assertNotIn("BenchFWD-first", active)
        self.assertNotIn("DEF3", active)

    def test_keeper_autosub(self):
        rows = standard_343(oreilly_minutes=90, oreilly_team=1)
        rows[0] = pick(1, 1, 1, 4, 0, name="GK")
        resolved = resolve_effective_picks(rows, {**TEAMS, 4: "finished"})
        active = names_in(resolved, active=True)
        self.assertIn("BenchGK", active)
        self.assertNotIn("GK", active)
        self.assertNotIn("BenchMID", active)

    def test_multiple_dnp(self):
        rows = standard_343()
        rows[5] = pick(6, 3, 6, 1, 0, name="MID2")
        resolved = resolve_effective_picks(rows, TEAMS)
        active = names_in(resolved, active=True)
        self.assertIn("BenchMID", active)
        self.assertIn("BenchDEF", active)
        self.assertNotIn("O'Reilly", active)
        self.assertNotIn("MID2", active)

    def test_bench_already_finished_does_not_count_as_remaining(self):
        rows = standard_343(first_bench_minutes=90, first_bench_team=1)
        self.assertEqual(remaining_from_picks(rows, TEAMS), 3)
        incoming = next(r for r in resolve_effective_picks(rows, TEAMS) if r["player"] == "BenchMID")
        self.assertTrue(incoming["autosub_in"])
        self.assertEqual(incoming["autosub_status"], "confirmed")

    def test_bench_with_match_left_counts_as_remaining(self):
        rows = standard_343(first_bench_minutes=0, first_bench_team=2)
        self.assertEqual(remaining_from_picks(rows, TEAMS), 4)

    def test_vice_takes_captain_multiplier(self):
        rows = standard_343(oreilly_minutes=90, oreilly_team=1)
        rows[7] = pick(8, 3, 8, 1, 0, name="Kaptein", cap=True)
        rows[8] = pick(9, 4, 9, 2, 0, name="VC", vc=True)
        resolved = resolve_effective_picks(rows, TEAMS)
        cap = next(r for r in resolved if r["player"] == "Kaptein")
        vice = next(r for r in resolved if r["player"] == "VC")
        self.assertEqual(cap["multiplier"], 0)
        self.assertEqual(vice["multiplier"], 2)
        self.assertTrue(vice["captain_fallback"])
        self.assertEqual(remaining_from_picks(rows, TEAMS), 4)

    def test_pending_blank_does_not_count_bench_as_remaining(self):
        rows = standard_343(oreilly_team=3, oreilly_minutes=0)
        resolved = resolve_effective_picks(rows, TEAMS)
        oreilly = next(r for r in resolved if r["player"] == "O'Reilly")
        bench = next(r for r in resolved if r["player"] == "BenchMID")
        self.assertGreater(oreilly["multiplier"], 0)
        self.assertFalse(bench["autosub_in"])
        self.assertEqual(bench["autosub_status"], "pending")
        self.assertEqual(remaining_from_picks(rows, TEAMS), 3)

    def test_triple_captain_dnp_gives_vice_double_not_triple(self):
        rows = standard_343(oreilly_minutes=90, oreilly_team=1)
        rows[7] = pick(8, 3, 8, 1, 0, name="Kaptein", cap=True, tc=True, chip="Triple Captain")
        rows[8] = pick(9, 4, 9, 2, 0, name="VC", vc=True)
        resolved = resolve_effective_picks(rows, TEAMS)
        vice = next(r for r in resolved if r["player"] == "VC")
        self.assertEqual(vice["multiplier"], 2)
        self.assertFalse(vice["is_triple_captain"])


if __name__ == "__main__":
    unittest.main()
