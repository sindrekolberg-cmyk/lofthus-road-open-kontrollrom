"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { HomePayload, ManagerRow } from "@/lib/types";
import { moveLabel, place } from "@/lib/format";
import { useSelectedManager } from "@/lib/selected-manager";

type Props = {
  managers: HomePayload["managers"];
  top: ManagerRow[];
};

export function MinLofthus({ managers, top }: Props) {
  const { entryId, setEntryId } = useSelectedManager();
  const me = useMemo(
    () => top.find((m) => m.entry === entryId) || null,
    [top, entryId],
  );
  const rivals = useMemo(() => {
    if (!me) return [];
    return top
      .filter((m) => m.entry !== me.entry)
      .sort(
        (a, b) =>
          Math.abs(a.rank - me.rank) - Math.abs(b.rank - me.rank) ||
          a.rank - b.rank,
      )
      .slice(0, 2);
  }, [me, top]);

  return (
    <section className="border-y border-rule bg-[#e7e1d4] text-ink">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-5 px-4 py-5 sm:px-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-baseline gap-4">
            <p className="font-condensed text-[11px] tracking-[0.22em] text-muted uppercase">
              Min Lofthus
            </p>
            {me ? (
              <h2 className="font-serif text-2xl leading-none">{me.manager}</h2>
            ) : (
              <h2 className="font-serif text-2xl leading-none">Velg manager</h2>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <span className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              Manager
            </span>
            <select
              className="max-w-[16rem] border border-rule bg-paper px-2 py-1.5 text-sm"
              value={entryId || ""}
              onChange={(e) => setEntryId(Number(e.target.value) || 0)}
            >
              <option value="">Ingen valgt</option>
              {managers.map((m) => (
                <option key={m.entry} value={m.entry}>
                  {m.manager} · {m.team}
                </option>
              ))}
            </select>
          </label>
        </div>

        {me ? (
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <dl className="grid grid-cols-2 gap-x-8 gap-y-3 sm:flex sm:items-center sm:gap-10">
              <div>
                <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
                  Plass
                </dt>
                <dd className="font-condensed text-2xl font-semibold leading-none">
                  {place(me.rank)}
                </dd>
              </div>
              <div>
                <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
                  Poeng
                </dt>
                <dd className="font-condensed text-2xl font-semibold leading-none">
                  {me.total}
                </dd>
              </div>
              <div>
                <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
                  GW
                </dt>
                <dd className="font-condensed text-2xl font-semibold leading-none">
                  {me.gw}
                </dd>
              </div>
              <div>
                <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
                  Foreløpig
                </dt>
                <dd
                  className={`font-condensed text-2xl font-semibold leading-none ${
                    me.rank_change > 0
                      ? "text-[#2f6a32]"
                      : me.rank_change < 0
                        ? "text-live"
                        : ""
                  }`}
                >
                  {me.rank_change
                    ? `${moveLabel(me.rank_change, true)} plasser`
                    : "–"}
                </dd>
              </div>
            </dl>
            <div className="flex flex-wrap gap-4 font-condensed text-[12px] tracking-[0.14em] uppercase">
              <Link href={`/manager/${me.entry}`} className="hover:underline">
                Profil →
              </Link>
              {rivals.map((r) => (
                <Link
                  key={r.entry}
                  href={`/rivalradar?me=${me.entry}&rival=${r.entry}`}
                  className="hover:underline"
                >
                  vs {r.manager.split(" ")[0]} →
                </Link>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted">
            Valgt manager huskes i nettleseren og brukes på tvers av Liga,
            Rivalradar og profil.
          </p>
        )}
      </div>
    </section>
  );
}
