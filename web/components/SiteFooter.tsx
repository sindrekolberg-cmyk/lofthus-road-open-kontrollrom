import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="border-t border-rule bg-ink text-paper/70">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-3 px-4 py-8 sm:flex-row sm:items-end sm:justify-between sm:px-6">
        <div>
          <p className="font-condensed text-sm tracking-[0.18em] text-paper">
            LOFTHUS ROAD OPEN
          </p>
          <p className="mt-1 max-w-md text-sm leading-relaxed">
            En Fantasy Premier League-miniliga, redigert som et sportsmedium.
          </p>
        </div>
        <p className="text-xs tracking-wide">
          Prototype · Gameweek 4 ·{" "}
          <Link href="/" className="text-paper/90 hover:text-paper">
            Forside
          </Link>
        </p>
      </div>
    </footer>
  );
}
