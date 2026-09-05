"use client";

import type { PlayerCard } from "@/lib/types";
import { PlayerImage } from "@/components/PlayerImage";

export function PlayersTalkedAbout({ players }: { players: PlayerCard[] }) {
  const shown = players.slice(0, 4);
  if (!shown.length) return null;

  return (
    <section className="bg-ink text-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 sm:py-16">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <h2 className="font-serif text-3xl leading-none sm:text-4xl">
            Spillerne alle snakker om
          </h2>
          <p className="font-condensed text-[11px] tracking-[0.2em] text-paper/45 uppercase">
            Lofthus-eierskap · denne GW
          </p>
        </div>

        <ul className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          {shown.map((player, index) => (
            <li
              key={player.element}
              className={`group relative overflow-hidden bg-[#1a1a1a] ${
                index === 0
                  ? "col-span-2 aspect-[5/4] md:col-span-1 md:aspect-[3/4]"
                  : "aspect-[3/4]"
              }`}
            >
              <PlayerImage
                src={player.image_url}
                alt={player.player}
                variant="card"
                objectPosition="center 15%"
                className="transition-transform duration-500 group-hover:scale-[1.04]"
              />
              <div className="absolute inset-0 bg-[linear-gradient(to_top,rgba(0,0,0,0.88)_0%,rgba(0,0,0,0.15)_48%,transparent_70%)]" />
              <div className="absolute inset-x-0 bottom-0 p-4 sm:p-5">
                <p className="font-condensed text-[11px] tracking-[0.16em] text-paper/55 uppercase">
                  {player.club}
                </p>
                <h3 className="mt-1 font-serif text-2xl leading-[1.05] sm:text-[1.65rem]">
                  {player.player}
                </h3>
                <p className="mt-3 flex gap-5 font-condensed text-[12px] tracking-[0.12em] text-paper/70">
                  <span>{Math.round(player.ownership_pct)}% eid</span>
                  <span>
                    {player.fixture_status === "not_started"
                      ? "ikke spilt"
                      : `${player.event_points} p`}
                  </span>
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
