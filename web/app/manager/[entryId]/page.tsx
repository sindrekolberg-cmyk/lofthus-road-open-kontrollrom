"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { moveLabel, place } from "@/lib/format";
import { ApiState, LoadingBlock } from "@/components/ApiState";
import { SquadPitch } from "@/components/SquadPitch";

export default function ManagerPage() {
  const params = useParams<{ entryId: string }>();
  const entry = Number(params.entryId);
  const { data, error, loading } = useApi(
    () => api.manager(entry),
    [entry],
  );

  if (loading) {
    return (
      <main className="flex-1">
        <LoadingBlock label="Henter manager…" />
      </main>
    );
  }
  if (error || !data) {
    return (
      <main className="flex-1 px-4 py-16">
        <div className="mx-auto max-w-[1400px]">
          <ApiState title="Manager ikke funnet" message={error || ""} />
        </div>
      </main>
    );
  }

  const m = data.manager;
  const merits = data.lofthus_merits;

  return (
    <main className="flex-1 bg-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-12 sm:px-6">
        <Link
          href="/liga"
          className="font-condensed text-[12px] tracking-[0.16em] uppercase text-muted hover:text-ink"
        >
          ← Tilbake til tabellen
        </Link>
        <p className="mt-6 font-condensed text-xs tracking-[0.22em] text-live uppercase">
          {data.is_live ? "Live" : data.provisional ? "Foreløpig" : "Manager"}
        </p>
        <h1 className="mt-2 font-serif text-5xl leading-none sm:text-6xl">
          {m.manager}
        </h1>
        <p className="mt-3 text-lg text-muted">{m.team}</p>

        <dl className="mt-8 grid grid-cols-2 gap-6 border-t border-ink pt-6 sm:grid-cols-5">
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              Plass
            </dt>
            <dd className="font-condensed text-3xl font-semibold">{place(m.rank)}</dd>
          </div>
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              Total
            </dt>
            <dd className="font-condensed text-3xl font-semibold">{m.total}</dd>
          </div>
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              GW live
            </dt>
            <dd className="font-condensed text-3xl font-semibold">{m.gw}</dd>
          </div>
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              Bevegelse
            </dt>
            <dd className="font-condensed text-3xl font-semibold">
              {moveLabel(m.rank_change, data.provisional)}
            </dd>
          </div>
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              {data.month_name || "Måned"}
            </dt>
            <dd className="font-condensed text-3xl font-semibold">
              {m.month_rank ? place(m.month_rank) : "–"}
            </dd>
          </div>
        </dl>

        {data.story ? (
          <p className="mt-8 max-w-2xl font-serif text-2xl leading-snug">{data.story}</p>
        ) : null}

        <h2 className="mt-12 font-serif text-3xl">
          Laget · GW{data.event_id}
          {data.provisional ? " · live" : ""}
        </h2>
        <p className="mt-2 text-sm text-muted">
          {m.players_remaining} spillere gjenstår · {m.chip || "ingen chip"} · hits {m.hits}
        </p>
        <div className="mt-6">
          <SquadPitch squad={data.squad} />
        </div>

        <div className="mt-6">
          <Link
            href={`/rivalradar?me=${m.entry}`}
            className="font-condensed text-[12px] tracking-[0.16em] uppercase hover:underline"
          >
            Åpne Rivalradar →
          </Link>
        </div>

        <h2 className="mt-14 font-serif text-3xl">Form</h2>
        <div className="mt-4 flex flex-wrap gap-3">
          {data.form.map((row) => (
            <div key={row.event} className="border border-rule px-3 py-2">
              <p className="font-condensed text-[10px] tracking-[0.14em] text-muted uppercase">
                GW{row.event}
                {row.is_live ? " · live" : ""}
              </p>
              <p className="font-condensed text-2xl">{row.points}</p>
              <p className="text-xs text-muted">{place(row.league_rank)} i Lofthus</p>
            </div>
          ))}
        </div>

        <div className="mt-14 grid gap-10 lg:grid-cols-2">
          <section>
            <h2 className="font-serif text-3xl">Lofthus-karriere</h2>
            <p className="mt-2 text-sm text-muted">
              Meritter i Lofthus Road Open. Dette er ikke FPL-historikk.
            </p>
            <dl className="mt-5 grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs text-muted">Beste plassering</dt>
                <dd className="font-condensed text-2xl">
                  {data.lofthus_best_finish ? place(data.lofthus_best_finish) : "ukjent"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Ligatitler</dt>
                <dd className="font-condensed text-2xl">{merits.league_gold}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Cup</dt>
                <dd className="font-condensed text-2xl">{merits.cup_gold}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Månedstitler</dt>
                <dd className="font-condensed text-2xl">{merits.monthly_gold}</dd>
              </div>
            </dl>
            {data.lofthus_overall.length ? (
              <ul className="mt-4 text-sm">
                {data.lofthus_overall.map((row) => (
                  <li key={row.season}>
                    {row.season}: {place(row.place)} sammenlagt
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-sm text-muted">Ingen registrerte sesongplasseringer.</p>
            )}
            {data.chips.length ? (
              <ul className="mt-6 text-sm">
                {data.chips.map((c) => (
                  <li key={`${c.chip}-${c.event}`}>
                    {c.chip} · {c.gw}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-6 text-sm text-muted">Ingen registrerte chips ennå.</p>
            )}
          </section>

          <section>
            <h2 className="font-serif text-3xl">FPL-karriere</h2>
            <p className="mt-2 text-sm text-muted">
              Offisiell Fantasy Premier League-historikk for denne entryen. Antall
              FPL-sesonger er ikke det samme som Lofthus-sesonger.
            </p>
            {data.fpl_season?.total_points ? (
              <p className="mt-4 text-sm">
                Denne FPL-sesongen: {data.fpl_season.total_points} poeng
                {data.fpl_season.overall_rank
                  ? ` · OR ${data.fpl_season.overall_rank.toLocaleString("nb-NO")}`
                  : ""}
              </p>
            ) : null}
            {data.fpl_career.length ? (
              <table className="mt-4 w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-ink font-condensed text-[11px] tracking-[0.14em] text-muted uppercase">
                    <th className="py-2">Sesong</th>
                    <th className="py-2 text-right">Poeng</th>
                    <th className="py-2 text-right">OR</th>
                  </tr>
                </thead>
                <tbody>
                  {data.fpl_career.map((row) => (
                    <tr key={row.season} className="border-b border-rule">
                      <td className="py-2">{row.season}</td>
                      <td className="py-2 text-right font-condensed">{row.points}</td>
                      <td className="py-2 text-right font-condensed">
                        {row.overall_rank ? row.overall_rank.toLocaleString("nb-NO") : "–"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="mt-4 text-sm text-muted">Ingen FPL-historikk lastet ennå.</p>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
