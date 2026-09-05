import { septemberTable } from "@/lib/data";
import { PlayerImage } from "@/components/PlayerImage";

export function Talkers() {
  return (
    <section className="bg-paper text-ink">
      <div className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 sm:py-16">
        <div className="flex items-end justify-between gap-4 border-b border-ink pb-3">
          <h2 className="font-serif text-3xl leading-none sm:text-4xl">
            Snakkiser
          </h2>
          <p className="font-condensed text-[11px] tracking-[0.2em] text-muted uppercase">
            Runden som splitter feltet
          </p>
        </div>

        <div className="mt-8 grid gap-8 lg:grid-cols-12 lg:gap-10">
          <article className="lg:col-span-7">
            <div className="relative aspect-[16/10] overflow-hidden bg-ink sm:aspect-[16/9]">
              <PlayerImage
                src="/images/stories/haaland.jpg"
                alt="Erling Haaland"
                sizes="(min-width: 1024px) 55vw, 100vw"
                objectPosition="center 10%"
              />
            </div>
            <p className="mt-4 font-condensed text-[12px] tracking-[0.2em] text-live uppercase">
              Eierskap
            </p>
            <h3 className="mt-2 max-w-[18ch] font-serif text-4xl leading-[0.98] sm:text-5xl">
              Haaland straffer dem som gikk uten
            </h3>
            <p className="mt-4 max-w-xl text-[1.05rem] leading-7 text-muted">
              Tretten poeng, hat-trick-rykte og et felt som plutselig ser tynt
              ut. De som lot City-spissen stå over, merker det i hver
              oppdatering.
            </p>
          </article>

          <div className="flex flex-col gap-8 lg:col-span-5">
            <article className="flex min-h-[280px] flex-1 flex-col justify-between border-t border-ink pt-6 lg:border-t-0 lg:border-l lg:pl-8 lg:pt-0">
              <div>
                <p className="font-condensed text-[12px] tracking-[0.2em] text-muted uppercase">
                  Fall
                </p>
                <p className="mt-4 font-condensed text-[7.5rem] leading-[0.75] font-semibold tracking-tight text-live sm:text-[9rem]">
                  ↓43
                </p>
                <h3 className="mt-6 font-serif text-3xl leading-tight">
                  43 plasser rett ned
                </h3>
              </div>
              <p className="mt-4 max-w-sm text-base leading-7 text-muted">
                En blank kaptein og tre nullere. En manager raste gjennom
                Lofthus på én runde — og tabellen husker det.
              </p>
            </article>

            <article className="border-t border-rule pt-6">
              <p className="font-condensed text-[12px] tracking-[0.2em] text-muted uppercase">
                Måneden
              </p>
              <h3 className="mt-2 font-serif text-2xl leading-tight sm:text-[1.7rem]">
                September har fått en ny leder
              </h3>
              <table className="mt-5 w-full text-left">
                <tbody>
                  {septemberTable.map((row) => (
                    <tr
                      key={row.manager}
                      className={`border-t border-rule ${
                        row.rank === 1 ? "text-ink" : "text-muted"
                      }`}
                    >
                      <td className="w-8 py-2.5 font-condensed text-lg">
                        {row.rank}
                      </td>
                      <td className="py-2.5 text-sm">{row.manager}</td>
                      <td className="py-2.5 text-right font-condensed text-lg tabular-nums">
                        {row.points}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-sm leading-6 text-muted">
                Mats Arntzen tok over etter GW 4. To runder gjenstår av
                september-pokalen.
              </p>
            </article>
          </div>
        </div>
      </div>
    </section>
  );
}
