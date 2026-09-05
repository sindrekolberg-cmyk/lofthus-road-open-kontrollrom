"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { ApiState, LoadingBlock } from "@/components/ApiState";
import { LeagueTable } from "@/components/LeagueTable";
import { PlayerImage } from "@/components/PlayerImage";

export default function LivePage() {
  const { data, error, loading } = useApi(() => api.live(), []);

  return (
    <main className="flex-1 bg-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-12 sm:px-6">
        <p className="font-condensed text-xs tracking-[0.22em] text-live uppercase">
          {data?.status.is_live ? "Live" : data?.status.event_status_label || "Gameweek"}
        </p>
        <h1 className="mt-3 font-serif text-5xl leading-none sm:text-6xl">
          Live
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
          Samme live-sannhet som ligaen. Spillere som ikke har spilt, telles
          ikke som blanke.
        </p>

        {loading ? <LoadingBlock /> : null}
        {error ? <ApiState message={error} /> : null}

        {data ? (
          <>
            <div className="mt-8 flex flex-wrap gap-3">
              {data.fixtures.map((f) => (
                <div key={f.id || `${f.home}-${f.away}`} className="border border-rule px-3 py-2">
                  <p className="font-condensed text-[11px] tracking-[0.14em] text-muted uppercase">
                    {f.status_label}
                    {f.minutes ? ` · ${f.minutes}'` : ""}
                  </p>
                  <p className="mt-1 font-condensed text-lg">
                    {f.home}{" "}
                    {f.status === "not_started"
                      ? "–"
                      : `${f.home_score ?? 0}–${f.away_score ?? 0}`}{" "}
                    {f.away}
                  </p>
                </div>
              ))}
            </div>

            <h2 className="mt-12 font-serif text-3xl">GW-ranking</h2>
            <ul className="mt-4 divide-y divide-rule border-y border-rule">
              {data.gw_ranking.slice(0, 15).map((row, i) => (
                <li key={row.entry} className="flex items-baseline justify-between gap-4 py-2.5">
                  <span className="font-condensed text-muted">{i + 1}</span>
                  <Link href={`/manager/${row.entry}`} className="flex-1 hover:underline">
                    {row.manager}
                  </Link>
                  <span className="font-condensed text-lg tabular-nums">{row.gw}</span>
                </li>
              ))}
            </ul>

            <h2 className="mt-12 font-serif text-3xl">Spillere som preger runden</h2>
            <ul className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
              {data.player_impacts.slice(0, 8).map((p) => (
                <li key={p.element} className="relative aspect-[3/4] overflow-hidden bg-ink text-paper">
                  <PlayerImage src={p.image_url} alt={p.player} variant="card" />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 to-transparent" />
                  <div className="absolute inset-x-0 bottom-0 p-3">
                    <p className="font-serif text-xl">{p.player}</p>
                    <p className="font-condensed text-[11px] text-paper/70">
                      {p.fixture_status === "not_started"
                        ? "ikke spilt"
                        : `${p.event_points} p`}{" "}
                      · {Math.round(p.ownership_pct)}%
                    </p>
                  </div>
                </li>
              ))}
            </ul>

            <h2 className="mt-12 font-serif text-3xl">Sammenlagt</h2>
            <div className="mt-4">
              <LeagueTable rows={data.table} status={data.status} />
            </div>
          </>
        ) : null}
      </div>
    </main>
  );
}
