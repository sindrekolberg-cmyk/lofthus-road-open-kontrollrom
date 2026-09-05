"use client";

import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { ApiState, LoadingBlock } from "@/components/ApiState";

export default function HallOfFamePage() {
  const { data, error, loading } = useApi(() => api.hallOfFame(), []);

  return (
    <main className="flex-1 bg-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-12 sm:px-6">
        <p className="font-condensed text-xs tracking-[0.22em] text-live uppercase">
          Meritter
        </p>
        <h1 className="mt-3 font-serif text-5xl leading-none sm:text-6xl">
          Hall of Fame
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
          Ligatitler først, deretter cup- og månedsgull, så sølv og bronse.
          Canonical navn og alias kommer fra det eksisterende arkivet.
        </p>

        {loading ? <LoadingBlock /> : null}
        {error ? <ApiState message={error} /> : null}

        {data ? (
          <div className="mt-10 overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr className="border-b border-ink font-condensed text-[11px] tracking-[0.14em] text-muted uppercase">
                  <th className="py-3">#</th>
                  <th className="py-3">Manager</th>
                  <th className="py-3 text-right">Liga</th>
                  <th className="py-3 text-right">Cup</th>
                  <th className="py-3 text-right">Måned</th>
                  <th className="py-3 text-right">Sølv</th>
                  <th className="py-3 text-right">Bronse</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.manager} className="border-b border-rule">
                    <td className="py-3 font-condensed">{row.rank}</td>
                    <td className="py-3">{row.manager}</td>
                    <td className="py-3 text-right font-condensed">{row.league_gold}</td>
                    <td className="py-3 text-right font-condensed">{row.cup_gold}</td>
                    <td className="py-3 text-right font-condensed">{row.monthly_gold}</td>
                    <td className="py-3 text-right font-condensed">{row.silver}</td>
                    <td className="py-3 text-right font-condensed">{row.bronze}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </main>
  );
}
