"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { ApiState, LoadingBlock } from "@/components/ApiState";
import { LeagueTable } from "@/components/LeagueTable";
import Link from "next/link";

export default function LigaPage() {
  const { data, error, loading } = useApi(() => api.league(), []);
  const month = useApi(() => api.month(), []);
  const [tab, setTab] = useState<"tabell" | "maned">("tabell");

  return (
    <main className="flex-1 bg-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-12 sm:px-6">
        <p className="font-condensed text-xs tracking-[0.22em] text-live uppercase">
          {data?.status.is_live ? "Live" : data?.status.event_status_label || "Liga"}
        </p>
        <h1 className="mt-3 font-serif text-5xl leading-none text-ink sm:text-6xl">
          Liga
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
          Én live-sannhet for hele Lofthus.
          {data
            ? ` Plasseringene er ${data.status.provisional ? "foreløpige" : "offisielle"} i GW${data.status.event_id}.`
            : ""}
        </p>

        <div className="mt-8 flex gap-6 border-b border-ink">
          <button
            type="button"
            onClick={() => setTab("tabell")}
            className={`pb-3 font-condensed text-[13px] tracking-[0.16em] uppercase ${
              tab === "tabell" ? "text-ink" : "text-muted"
            }`}
          >
            Tabell
          </button>
          <button
            type="button"
            onClick={() => setTab("maned")}
            className={`pb-3 font-condensed text-[13px] tracking-[0.16em] uppercase ${
              tab === "maned" ? "text-ink" : "text-muted"
            }`}
          >
            {month.data?.month_name || "Måned"}
          </button>
        </div>

        {tab === "tabell" ? (
          <div className="mt-8">
            {loading ? <LoadingBlock /> : null}
            {error ? <ApiState message={error} /> : null}
            {data ? <LeagueTable rows={data.table} status={data.status} /> : null}
          </div>
        ) : (
          <div className="mt-8">
            {month.loading ? <LoadingBlock /> : null}
            {month.error ? <ApiState message={month.error} /> : null}
            {month.data ? (
              <>
                <h2 className="font-serif text-3xl">
                  {month.data.month_name || "Aktiv måned"}
                </h2>
                <p className="mt-2 text-sm text-muted">
                  Når første runde i en ny måned går live, er den måneden aktiv.
                  Poengene under er live månedspoeng.
                </p>
                <div className="mt-6 overflow-x-auto">
                  <table className="w-full min-w-[520px] text-left">
                    <thead>
                      <tr className="border-b border-ink font-condensed text-[11px] tracking-[0.16em] text-muted uppercase">
                        <th className="py-3">#</th>
                        <th className="py-3">Manager</th>
                        <th className="py-3 text-right">Måned</th>
                        <th className="py-3 text-right">GW</th>
                      </tr>
                    </thead>
                    <tbody>
                      {month.data.table.map((row) => (
                        <tr key={row.entry} className="border-b border-rule">
                          <td className="py-3 font-condensed text-lg">
                            {row.month_rank}
                          </td>
                          <td className="py-3">
                            <Link href={`/manager/${row.entry}`} className="hover:underline">
                              {row.manager}
                            </Link>
                          </td>
                          <td className="py-3 text-right font-condensed text-lg tabular-nums">
                            {row.month_points}
                          </td>
                          <td className="py-3 text-right font-condensed tabular-nums text-muted">
                            {row.gw}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <h3 className="mt-12 font-serif text-2xl">Tidligere podier</h3>
                <ul className="mt-4 divide-y divide-rule border-y border-rule">
                  {month.data.previous.map((row) => (
                    <li
                      key={`${row.season}-${row.month}`}
                      className="grid gap-1 py-3 sm:grid-cols-12 sm:items-baseline"
                    >
                      <span className="font-condensed text-sm sm:col-span-3">
                        {row.month} {row.season}
                      </span>
                      <span className="sm:col-span-3">{row.winner || "ukjent"}</span>
                      <span className="text-muted sm:col-span-3">
                        {row.runner_up || ""}
                      </span>
                      <span className="text-muted sm:col-span-3">{row.third || ""}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
          </div>
        )}
      </div>
    </main>
  );
}
