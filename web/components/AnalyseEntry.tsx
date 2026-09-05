import Link from "next/link";
import { analysisEntries } from "@/lib/types";

export function AnalyseEntry() {
  return (
    <section className="bg-paper text-ink">
      <div className="mx-auto max-w-[1400px] px-4 py-14 sm:px-6 sm:py-16">
        <p className="font-condensed text-[12px] tracking-[0.22em] text-muted uppercase">
          Dypere inn
        </p>
        <h2 className="mt-2 font-serif text-3xl leading-none sm:text-4xl">
          Analyse
        </h2>
        <p className="mt-3 max-w-xl text-base leading-7 text-muted">
          Verktøyene ligger her — bak redaksjonen. Forsiden forteller
          historien. Dette er der du graver.
        </p>

        <ul className="mt-10 divide-y divide-rule border-y border-rule">
          {analysisEntries.map((entry) => (
            <li key={entry.title}>
              <Link
                href={entry.href}
                className="group grid grid-cols-1 items-baseline gap-1 py-5 transition-colors hover:bg-black/[0.02] sm:grid-cols-12 sm:gap-6"
              >
                <span className="font-condensed text-[11px] tracking-[0.18em] text-muted uppercase sm:col-span-3">
                  {entry.kicker}
                </span>
                <span className="font-serif text-2xl leading-tight sm:col-span-3">
                  {entry.title}
                </span>
                <span className="text-sm leading-6 text-muted sm:col-span-5">
                  {entry.line}
                </span>
                <span className="hidden font-condensed text-sm tracking-widest text-ink/30 transition-colors group-hover:text-ink sm:col-span-1 sm:block sm:text-right">
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
