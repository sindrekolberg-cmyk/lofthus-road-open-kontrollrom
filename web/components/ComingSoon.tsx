type ComingSoonProps = {
  title: string;
  kicker?: string;
};

export function ComingSoon({ title, kicker = "Neste fase" }: ComingSoonProps) {
  return (
    <main className="flex-1 bg-paper">
      <div className="mx-auto max-w-[1400px] px-4 py-20 sm:px-6">
        <p className="font-condensed text-xs tracking-[0.22em] text-live uppercase">
          {kicker}
        </p>
        <h1 className="mt-3 font-serif text-5xl leading-none text-ink sm:text-6xl">
          {title}
        </h1>
        <p className="mt-5 max-w-xl text-base leading-7 text-muted">
          Denne seksjonen er ikke en del av den visuelle prototypen. Forsiden
          er der vi beviser at Lofthus kan se ut som et sportsprodukt — ikke et
          dashboard.
        </p>
      </div>
    </main>
  );
}
