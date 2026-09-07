"""Print every Snakkis candidate for the current Lofthus round, ranked by desk score.

Editorial sanity check: run this against live data and read the top of the list
before trusting what the homepage shows.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.engine import AppEngine
from lro_newsroom import desk_score, editorial_family, generate_candidates, homepage_feed


def main() -> int:
    engine = AppEngine(eager=True)
    snap = engine.snapshot()
    state = snap.state
    if not state:
        print("Ingen live state.")
        return 1
    print(f"GW{state.event_id} · live={state.is_live} · ferdig={state.is_finished} · {state.league_size} managere")

    candidates = generate_candidates(state, snap.managers, snap.bootstrap, engine.history, snap.histories)
    ranked = sorted(candidates, key=lambda s: desk_score(s, state.event_id), reverse=True)
    print(f"\nKANDIDATER ({len(ranked)}):")
    for story in ranked:
        tier, importance, freshness, _ = desk_score(story, state.event_id)
        print(f"  t{tier:>2} i{importance:>3} {editorial_family(story):<14} {story.headline} | {story.meta}")

    feed = homepage_feed(candidates, state.event_id, limit=6)
    print(f"\nFORSIDE ({len(feed)}):")
    for story in feed:
        print(f"  [{editorial_family(story)}] {story.headline}\n      {story.meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
