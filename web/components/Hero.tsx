import Link from "next/link";
import { liveTable } from "@/lib/data";
import { PlayerImage } from "@/components/PlayerImage";

export function Hero() {
  return (
    <section className="bg-ink text-paper">
      <div className="mx-auto grid max-w-[1400px] lg:grid-cols-12 lg:items-stretch">
        <article className="relative min-h-[78vh] lg:col-span-8 lg:min-h-[86vh]">
          <PlayerImage
            src="/images/stories/hero.jpg"
            alt="Alexander Isak"
            sizes="(min-width: 1024px) 66vw, 100vw"
            priority
            objectPosition="center 12%"
          />
          <div className="absolute inset-0 bg-[linear-gradient(to_top,rgba(8,8,8,0.92)_0%,rgba(8,8,8,0.55)_42%,rgba(8,8,8,0.18)_70%,rgba(8,8,8,0.28)_100%)]" />

          <div className="absolute inset-0 flex flex-col justify-end px-4 pb-8 pt-16 sm:px-8 sm:pb-10">
            <p className="font-condensed text-[13px] font-semibold tracking-[0.28em] text-live">
              LIVE
            </p>
            <h1 className="mt-3 max-w-[16ch] font-serif text-[2.6rem] leading-[0.95] tracking-tight text-paper sm:text-6xl lg:text-[4.4rem]">
              Isak setter fyr på Lofthus
            </h1>
            <p className="mt-5 max-w-[38rem] text-[1.05rem] leading-7 text-paper/85 sm:text-lg">
              Alexander Isak har levert stort. Fire managere med kapteinsbindet
              får et kraftig løft i live-tabellen.
            </p>

            <dl className="mt-8 flex max-w-xl items-end gap-8 border-t border-white/20 pt-5 sm:gap-12">
              <div>
                <dd className="font-condensed text-4xl font-semibold leading-none tracking-tight">
                  12
                </dd>
                <dt className="mt-1.5 font-condensed text-[11px] tracking-[0.16em] text-paper/55 uppercase">
                  Poeng
                </dt>
              </div>
              <div>
                <dd className="font-condensed text-4xl font-semibold leading-none tracking-tight">
                  4
                </dd>
                <dt className="mt-1.5 font-condensed text-[11px] tracking-[0.16em] text-paper/55 uppercase">
                  Kapteiner
                </dt>
              </div>
              <div>
                <dd className="font-condensed text-4xl font-semibold leading-none tracking-tight">
                  +8
                </dd>
                <dt className="mt-1.5 font-condensed text-[11px] tracking-[0.16em] text-paper/55 uppercase">
                  Største live-swing
                </dt>
              </div>
            </dl>
          </div>
        </article>

        <aside className="flex flex-col justify-between border-t border-white/10 px-4 py-7 sm:px-7 lg:col-span-4 lg:border-t-0 lg:border-l lg:py-8">
          <div>
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="font-condensed text-[13px] tracking-[0.22em] text-paper/70 uppercase">
                Live topp 5
              </h2>
              <p className="font-condensed text-[11px] tracking-[0.16em] text-live uppercase">
                GW 4 · pågår
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
                {liveTable.map((row) => (
                  <tr
                    key={row.manager}
                    className="border-t border-white/10 transition-colors hover:bg-white/[0.04]"
                  >
                    <td className="w-8 py-3.5 font-condensed text-lg leading-none text-paper/50">
                      {row.rank}
                    </td>
                    <td className="py-3.5 pr-3">
                      <span className="block text-[0.95rem] leading-tight text-paper">
                        {row.manager}
                      </span>
                      <span
                        className={`mt-0.5 block font-condensed text-[11px] tracking-wide ${
                          row.swing > 0
                            ? "text-[#9dcc8a]"
                            : row.swing < 0
                              ? "text-live/80"
                              : "text-paper/35"
                        }`}
                      >
                        {row.swing > 0 ? `↑${row.swing}` : row.swing < 0 ? `↓${Math.abs(row.swing)}` : "–"}
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
