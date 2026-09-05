"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { analysisEntries } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { ApiState, LoadingBlock } from "@/components/ApiState";
import { PlayerImage } from "@/components/PlayerImage";

export default function AnalysePage() {
  const captain = useApi(() => api.analysisCaptain(), []);
  const ownership = useApi(() => api.analysisOwnership(), []);
  const chips = useApi(() => api.analysisChips(), []);
  const diffs = useApi(() => api.analysisDifferentials(), []);

  return (
    <main className="flex-1 bg-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-12 sm:px-6">
        <p className="font-condensed text-xs tracking-[0.22em] text-muted uppercase">
          Verktøy
        </p>
        <h1 className="mt-3 font-serif text-5xl leading-none sm:text-6xl">
          Analyse
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">
          Nerdete lesning bak redaksjonen. Forsiden forteller historien. Her
          graver du i kapteiner, eierskap, chips og differensialer.
        </p>

        <ul className="mt-10 divide-y divide-rule border-y border-rule">
          {analysisEntries.map((entry) => (
            <li key={entry.title}>
              <Link
                href={entry.href}
                className="grid grid-cols-1 py-4 sm:grid-cols-12 sm:gap-6"
              >
                <span className="font-condensed text-[11px] tracking-[0.16em] text-muted uppercase sm:col-span-3">
                  {entry.kicker}
                </span>
                <span className="font-serif text-2xl sm:col-span-3">{entry.title}</span>
                <span className="text-sm text-muted sm:col-span-6">{entry.line}</span>
              </Link>
            </li>
          ))}
        </ul>

        <section id="kaptein" className="mt-16">
          <h2 className="font-serif text-3xl">Kaptein</h2>
          {captain.loading ? <LoadingBlock /> : null}
          {captain.error ? <ApiState message={captain.error} /> : null}
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-ink font-condensed text-[11px] tracking-[0.14em] text-muted uppercase">
                  <th className="py-2">Spiller</th>
                  <th className="py-2 text-right">C</th>
                  <th className="py-2 text-right">TC</th>
                  <th className="py-2 text-right">Poeng</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(captain.data?.players || []).slice(0, 20).map((p) => (
                  <tr key={p.element} className="border-b border-rule">
                    <td className="py-2">{p.player}</td>
                    <td className="py-2 text-right font-condensed">{p.captain_count}</td>
                    <td className="py-2 text-right font-condensed">{p.triple_captain_count}</td>
                    <td className="py-2 text-right font-condensed">
                      {p.fixture_status === "not_started" ? "–" : p.event_points}
                    </td>
                    <td className="py-2">{p.fixture_status_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section id="ownership" className="mt-16">
          <h2 className="font-serif text-3xl">Ownership</h2>
          {ownership.loading ? <LoadingBlock /> : null}
          <ul className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-4">
            {(ownership.data?.players || []).slice(0, 8).map((p) => (
              <li key={p.element} className="relative aspect-[3/4] overflow-hidden bg-ink text-paper">
                <PlayerImage src={p.image_url} alt={p.player} variant="card" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/85 to-transparent" />
                <div className="absolute inset-x-0 bottom-0 p-3">
                  <p className="font-serif text-xl">{p.player}</p>
                  <p className="font-condensed text-[11px] text-paper/70">
                    {Math.round(p.ownership_pct)}% · {p.ownership_count} eiere
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section id="chips" className="mt-16">
          <h2 className="font-serif text-3xl">Chips</h2>
          {chips.loading ? <LoadingBlock /> : null}
          {chips.error ? <ApiState message={chips.error} /> : null}
          <ul className="mt-4 divide-y divide-rule border-y border-rule">
            {(chips.data?.chips || []).length ? (
              (chips.data?.chips || []).map((c) => (
                <li key={`${c.entry}-${c.chip}`} className="flex justify-between py-3">
                  <Link href={`/manager/${c.entry}`} className="hover:underline">
                    {c.manager}
                  </Link>
                  <span className="font-condensed">{c.chip}</span>
                </li>
              ))
            ) : (
              <li className="py-3 text-sm text-muted">Ingen aktive chips denne runden.</li>
            )}
          </ul>
        </section>

        <section id="differensialer" className="mt-16">
          <h2 className="font-serif text-3xl">Differensialer</h2>
          {diffs.loading ? <LoadingBlock /> : null}
          <table className="mt-4 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink font-condensed text-[11px] tracking-[0.14em] text-muted uppercase">
                <th className="py-2">Spiller</th>
                <th className="py-2 text-right">Eid</th>
                <th className="py-2 text-right">GW</th>
              </tr>
            </thead>
            <tbody>
              {(diffs.data?.players || []).slice(0, 20).map((p) => (
                <tr key={p.element} className="border-b border-rule">
                  <td className="py-2">{p.player}</td>
                  <td className="py-2 text-right font-condensed">{p.ownership_pct}%</td>
                  <td className="py-2 text-right font-condensed">
                    {p.fixture_status === "not_started" ? "ikke spilt" : p.event_points}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </main>
  );
}
