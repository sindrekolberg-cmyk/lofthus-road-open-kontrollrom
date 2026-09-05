"use client";

import Link from "next/link";
import type { ManagerRow, Story } from "@/lib/types";
import { PlayerImage } from "@/components/PlayerImage";

const CATEGORY: Record<string, string> = {
  live: "Live",
  leader: "Tabellen",
  movement: "Fall",
  movement_live: "Bevegelse",
  chip: "Kaptein",
  month: "Måneden",
  round: "Runden",
  ownership: "Eierskap",
};

type Props = {
  stories: Story[];
  monthName: string;
  monthTable: ManagerRow[];
};

export function Talkers({ stories, monthName, monthTable }: Props) {
  const lead = stories[0];
  const rest = stories.slice(1);
  const monthStory = stories.find((s) => s.category === "month");
  const side = rest.filter((s) => s !== monthStory).slice(0, 2);

  return (
    <section className="bg-paper text-ink">
      <div className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 sm:py-16">
        <div className="flex items-end justify-between gap-4 border-b border-ink pb-3">
          <h2 className="font-serif text-3xl leading-none sm:text-4xl">
            Snakkiser
          </h2>
          <p className="font-condensed text-[11px] tracking-[0.2em] text-muted uppercase">
            Redaksjonen · maks fire saker
          </p>
        </div>

        {!lead ? (
          <p className="mt-8 max-w-xl text-base leading-7 text-muted">
            Ingen gyldige saker akkurat nå. Når live-dataene er klare, fylles
            hullene med neste beste historie.
          </p>
        ) : (
          <div className="mt-8 grid gap-8 lg:grid-cols-12 lg:gap-10">
            <article className="lg:col-span-7">
              <Link
                href={lead.manager_entry ? `/manager/${lead.manager_entry}` : "/live"}
                className="block"
              >
                <div className="relative aspect-[16/10] overflow-hidden bg-ink sm:aspect-[16/9]">
                  <PlayerImage
                    src={lead.image_url}
                    alt={lead.headline}
                    variant="hero"
                    objectPosition="center 10%"
                  />
                </div>
                <p className="mt-4 font-condensed text-[12px] tracking-[0.2em] text-live uppercase">
                  {CATEGORY[lead.category] || lead.category}
                  {lead.status === "live" ? " · foreløpig" : ""}
                </p>
                <h3 className="mt-2 max-w-[20ch] font-serif text-4xl leading-[0.98] sm:text-5xl">
                  {lead.headline}
                </h3>
                <p className="mt-4 max-w-xl text-[1.05rem] leading-7 text-muted">
                  {lead.meta}
                </p>
              </Link>
            </article>

            <div className="flex flex-col gap-8 lg:col-span-5">
              {side.map((story) => (
                <article
                  key={story.key}
                  className="flex flex-1 flex-col justify-between border-t border-ink pt-6 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0"
                >
                  <div>
                    <p className="font-condensed text-[12px] tracking-[0.2em] text-muted uppercase">
                      {CATEGORY[story.category] || story.category}
                      {story.status === "live" ? " · foreløpig" : ""}
                    </p>
                    <h3 className="mt-4 font-serif text-3xl leading-tight">
                      {story.headline}
                    </h3>
                  </div>
                  <p className="mt-4 max-w-sm text-base leading-7 text-muted">
                    {story.meta}
                  </p>
                </article>
              ))}

              <article className="border-t border-rule pt-6">
                <p className="font-condensed text-[12px] tracking-[0.2em] text-muted uppercase">
                  {monthName || "Måneden"}
                </p>
                <h3 className="mt-2 font-serif text-2xl leading-tight sm:text-[1.7rem]">
                  {monthStory?.headline ||
                    (monthName ? `${monthName} er i spill` : "Månedsligaen")}
                </h3>
                <table className="mt-5 w-full text-left">
                  <tbody>
                    {monthTable.map((row) => (
                      <tr
                        key={row.entry}
                        className={row.rank === 1 || row.month_rank === 1 ? "text-ink" : "text-muted"}
                      >
                        <td className="w-8 border-t border-rule py-2.5 font-condensed text-lg">
                          {row.month_rank || row.rank}
                        </td>
                        <td className="border-t border-rule py-2.5 text-sm">
                          <Link href={`/manager/${row.entry}`} className="hover:underline">
                            {row.manager}
                          </Link>
                        </td>
                        <td className="border-t border-rule py-2.5 text-right font-condensed text-lg tabular-nums">
                          {row.month_points}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </article>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
