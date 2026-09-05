"use client";

import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { ApiState, LoadingBlock } from "@/components/ApiState";
import Link from "next/link";

export default function HistorikkPage() {
  const { data, error, loading } = useApi(() => api.history(), []);

  return (
    <main className="flex-1 bg-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-12 sm:px-6">
        <p className="font-condensed text-xs tracking-[0.22em] text-live uppercase">
          Arkiv
        </p>
        <h1 className="mt-3 font-serif text-5xl leading-none sm:text-6xl">
          Historikk
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
          Sammenlagt, cup og måned fra den eksisterende Lofthus-arkivet. Tomme
          felt vises som ukjent — ingenting er funnet på.
        </p>
        <p className="mt-3">
          <Link href="/hall-of-fame" className="font-condensed text-[12px] tracking-[0.16em] uppercase hover:underline">
            Hall of Fame →
          </Link>
        </p>

        {loading ? <LoadingBlock /> : null}
        {error ? <ApiState message={error} /> : null}

        {data ? (
          <>
            <h2 className="mt-12 font-serif text-3xl">Sammenlagt</h2>
            <table className="mt-4 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink font-condensed text-[11px] tracking-[0.14em] text-muted uppercase">
                  <th className="py-2">Sesong</th>
                  <th className="py-2">Gull</th>
                  <th className="py-2">Sølv</th>
                  <th className="py-2">Bronse</th>
                </tr>
              </thead>
              <tbody>
                {data.overall.map((row) => (
                  <tr key={row.season} className="border-b border-rule">
                    <td className="py-3 font-condensed">{row.season}</td>
                    <td className="py-3">{row.winner || "ukjent"}</td>
                    <td className="py-3">{row.runner_up || "ukjent"}</td>
                    <td className="py-3">{row.third_place || "ukjent"}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h2 className="mt-12 font-serif text-3xl">Cup</h2>
            <ul className="mt-4 divide-y divide-rule border-y border-rule">
              {data.cup.map((row) => (
                <li key={row.season} className="grid gap-1 py-3 sm:grid-cols-12">
                  <span className="font-condensed sm:col-span-2">{row.season}</span>
                  <span className="sm:col-span-5">{row.winner || "ukjent"}</span>
                  <span className="text-muted sm:col-span-5">
                    {row.runner_up || "ukjent"}
                  </span>
                </li>
              ))}
            </ul>

            <h2 className="mt-12 font-serif text-3xl">Månedstitler</h2>
            <ul className="mt-4 divide-y divide-rule border-y border-rule">
              {data.monthly.map((row) => (
                <li key={`${row.season}-${row.month}`} className="grid gap-1 py-3 sm:grid-cols-12">
                  <span className="font-condensed sm:col-span-3">
                    {row.month} {row.season}
                  </span>
                  <span className="sm:col-span-3">{row.winner || "ukjent"}</span>
                  <span className="text-muted sm:col-span-3">{row.runner_up || ""}</span>
                  <span className="text-muted sm:col-span-3">{row.third || ""}</span>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </main>
  );
}
