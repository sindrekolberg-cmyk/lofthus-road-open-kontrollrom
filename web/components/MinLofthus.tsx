import { me } from "@/lib/data";

export function MinLofthus() {
  return (
    <section className="border-y border-rule bg-[#e7e1d4] text-ink">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-5 px-4 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-baseline gap-4">
          <p className="font-condensed text-[11px] tracking-[0.22em] text-muted uppercase">
            Min Lofthus
          </p>
          <h2 className="font-serif text-2xl leading-none">{me.name}</h2>
        </div>

        <dl className="grid grid-cols-2 gap-x-8 gap-y-3 sm:flex sm:items-center sm:gap-10">
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              Plass
            </dt>
            <dd className="font-condensed text-2xl font-semibold leading-none">
              {me.rank}.
            </dd>
          </div>
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              Poeng
            </dt>
            <dd className="font-condensed text-2xl font-semibold leading-none">
              {me.total}
            </dd>
          </div>
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              GW
            </dt>
            <dd className="font-condensed text-2xl font-semibold leading-none">
              {me.gw}
            </dd>
          </div>
          <div>
            <dt className="font-condensed text-[10px] tracking-[0.16em] text-muted uppercase">
              Foreløpig
            </dt>
            <dd className="font-condensed text-2xl font-semibold leading-none text-[#2f6a32]">
              +{me.places} plasser
            </dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
