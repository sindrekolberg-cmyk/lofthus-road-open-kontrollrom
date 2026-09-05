"use client";

import type { Squad, SquadPlayer } from "@/lib/types";
import { PlayerImage } from "@/components/PlayerImage";

function Badge({ player }: { player: SquadPlayer }) {
  if (player.is_triple_captain) return <span className="text-live">TC</span>;
  if (player.is_captain) return <span className="text-live">C</span>;
  if (player.is_vice_captain) return <span className="text-paper/70">VC</span>;
  return null;
}

function Slot({ player }: { player: SquadPlayer }) {
  const unplayed = player.fixture_status === "not_started";
  return (
    <div className="flex w-[4.6rem] flex-col items-center sm:w-20">
      <div className="relative h-14 w-14 overflow-hidden rounded-full bg-[#1a1a1a] sm:h-16 sm:w-16">
        <PlayerImage
          src={player.image_url}
          alt={player.player}
          variant="squad"
          objectPosition="center 10%"
        />
      </div>
      <p className="mt-1 max-w-full truncate text-center text-[11px] leading-tight text-paper">
        {player.player}
      </p>
      <p className="font-condensed text-[11px] tabular-nums text-paper/70">
        {unplayed ? "–" : player.gw_contribution}
        {player.multiplier > 1 ? ` ×${player.multiplier}` : ""}
      </p>
      <p className="font-condensed text-[9px] tracking-wide text-paper/45 uppercase">
        <Badge player={player} /> {player.club} · {player.fixture_status_label}
      </p>
    </div>
  );
}

function Line({ players }: { players: SquadPlayer[] }) {
  if (!players.length) return null;
  return (
    <div className="flex justify-center gap-2 sm:gap-4">
      {players.map((p) => (
        <Slot key={p.element} player={p} />
      ))}
    </div>
  );
}

export function SquadPitch({ squad }: { squad: Squad }) {
  return (
    <div>
      <div className="relative overflow-hidden bg-[#17331d] px-3 py-8 sm:px-6">
        <div className="pointer-events-none absolute inset-y-8 left-1/2 w-px bg-white/15" />
        <div className="pointer-events-none absolute left-4 right-4 top-1/2 h-px bg-white/15" />
        <div className="relative flex flex-col gap-6">
          <Line players={squad.lines.fwd} />
          <Line players={squad.lines.mid} />
          <Line players={squad.lines.def} />
          <Line players={squad.lines.gk} />
        </div>
      </div>
      <div className="mt-4">
        <p className="font-condensed text-[11px] tracking-[0.18em] text-muted uppercase">
          Benk
        </p>
        <div className="mt-3 flex flex-wrap gap-4">
          {squad.bench.map((p) => (
            <div key={p.element} className="min-w-[7rem] border border-rule px-3 py-2">
              <p className="text-sm">{p.player}</p>
              <p className="font-condensed text-[11px] text-muted">
                {p.club} · {p.fixture_status_label} ·{" "}
                {p.fixture_status === "not_started" ? "ikke spilt" : `${p.event_points} p`}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
