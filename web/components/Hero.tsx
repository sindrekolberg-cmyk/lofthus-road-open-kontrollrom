"use client";

import Link from "next/link";
import type { ManagerRow, PlayerCard, Status } from "@/lib/types";
import { moveLabel } from "@/lib/format";
import { PlayerImage } from "@/components/PlayerImage";

type Props = {
  hero: PlayerCard | null;
  top5: ManagerRow[];
  status: Status | null;
};

export function Hero({ hero, top5, status }: Props) {
  const live = Boolean(status?.is_live);
  const gw = status?.event_id || 0;

  return (
    <section className="bg-ink text-paper">
      <div className="mx-auto grid max-w-[1400px] lg:grid-cols-12 lg:items-stretch">
        <article className="relative min-h-[78vh] lg:col-span-8 lg:min-h-[86vh]">
          <PlayerImage
            src={hero?.image_url}
            alt={hero?.player || "Lofthus Road Open"}
            variant="hero"
            priority
            objectPosition="center 12%"
          />
          <div className="absolute inset-0 bg-[linear-gradient(to_top,rgba(8,8,8,0.92)_0%,rgba(8,8,8,0.55)_42%,rgba(8,8,8,0.18)_70%,rgba(8,8,8,0.28)_100%)]" />

          <div className="absolute inset-0 flex flex-col justify-end px-4 pb-8 pt-16 sm:px-8 sm:pb-10">
            <p className="font-condensed text-[13px] font-semibold tracking-[0.28em] text-live">
              {hero?.kicker || (live ? "LIVE" : gw ? `GW${gw}` : "LOFTHUS")}
            </p>
            <h1 className="mt-3 max-w-[16ch] font-serif text-[2.6rem] leading-[0.95] tracking-tight text-paper sm:text-6xl lg:text-[4.4rem]">
              {hero?.headline || "Lofthus venter på den neste store svingen"}
            </h1>
            <p className="mt-5 max-w-[38rem] text-[1.05rem] leading-7 text-paper/85 sm:text-lg">
              {hero?.dek ||
                "Når live-sannheten er klar, tar den største historien forsiden."}
            </p>

            {hero ? (
              <dl className="mt-8 flex max-w-xl items-end gap-8 border-t border-white/20 pt-5 sm:gap-12">
                <div>
                  <dd className="font-condensed text-4xl font-semibold leading-none tracking-tight">
                    {hero.event_points}
                  </dd>
                  <dt className="mt-1.5 font-condensed text-[11px] tracking-[0.16em] text-paper/55 uppercase">
                    Poeng
                  </dt>
                </div>
                <div>
                  <dd className="font-condensed text-4xl font-semibold leading-none tracking-tight">
                    {hero.captain_count}
                  </dd>
                  <dt className="mt-1.5 font-condensed text-[11px] tracking-[0.16em] text-paper/55 uppercase">
                    Kapteiner
                  </dt>
                </div>
                <div>
                  <dd className="font-condensed text-4xl font-semibold leading-none tracking-tight">
                    {Math.round(hero.ownership_pct)}%
                  </dd>
                  <dt className="mt-1.5 font-condensed text-[11px] tracking-[0.16em] text-paper/55 uppercase">
                    Lofthus-eid
                  </dt>
                </div>
              </dl>
            ) : null}
          </div>
        </article>

        <aside className="flex flex-col justify-between border-t border-white/10 px-4 py-7 sm:px-7 lg:col-span-4 lg:border-t-0 lg:border-l lg:py-8">
          <div>
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="font-condensed text-[13px] tracking-[0.22em] text-paper/70 uppercase">
                Live topp 5
              </h2>
              <p className="font-condensed text-[11px] tracking-[0.16em] text-live uppercase">
                {gw ? `GW ${gw}` : "–"}
                {live ? " · pågår" : status?.event_status_label ? ` · ${status.event_status_label}` : ""}
              </p>
            </div>

            <table className="mt-5 w-full border-collapse text-left">
              <thead>
                <tr className="font-condensed text-[10px] tracking-[0.18em] text-paper/40 uppercase">
                  <th className="pb-3 font-medium">#</th>
                  <th className="pb-3 font-medium">Manager</th>
                  <th className="pb-3 text-right font-medium">GW</th>
                  <th className="pb-3 text-right font-medium">Tot</th>
                </tr>
              </thead>
              <tbody>
                {top5.map((row) => (
                  <tr
                    key={row.entry}
                    className="border-t border-white/10 transition-colors hover:bg-white/[0.04]"
                  >
                    <td className="w-8 py-3.5 font-condensed text-lg leading-none text-paper/50">
                      {row.rank}
                    </td>
                    <td className="py-3.5 pr-3">
                      <Link
                        href={`/manager/${row.entry}`}
                        className="block text-[0.95rem] leading-tight text-paper hover:underline"
                      >
                        {row.manager}
                      </Link>
                      <span
                        className={`mt-0.5 block font-condensed text-[11px] tracking-wide ${
                          row.rank_change > 0
                            ? "text-[#9dcc8a]"
                            : row.rank_change < 0
                              ? "text-live/80"
                              : "text-paper/35"
                        }`}
                      >
                        {status?.provisional && row.rank_change
                          ? `foreløpig ${moveLabel(row.rank_change, true)}`
                          : moveLabel(row.rank_change, Boolean(status?.provisional))}
                      </span>
                    </td>
                    <td className="py-3.5 text-right font-condensed text-lg leading-none tabular-nums">
                      {row.gw}
                    </td>
                    <td className="py-3.5 text-right font-condensed text-lg font-semibold leading-none tabular-nums">
                      {row.total}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Link
            href="/liga"
            className="mt-8 inline-block font-condensed text-[12px] tracking-[0.18em] text-paper/55 uppercase transition-colors hover:text-paper"
          >
            Hele tabellen →
          </Link>
        </aside>
      </div>
    </section>
  );
}
