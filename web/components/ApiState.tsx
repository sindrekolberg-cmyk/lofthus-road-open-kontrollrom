type Props = {
  title?: string;
  message?: string;
};

export function ApiState({
  title = "Lofthus venter på data",
  message = "Backend er nede eller live-sannheten er ikke klar ennå. Streamlit-backupen er urørt.",
}: Props) {
  return (
    <div className="border border-rule bg-[#e7e1d4] px-5 py-6">
      <p className="font-condensed text-[11px] tracking-[0.2em] text-live uppercase">
        Midlertidig
      </p>
      <h2 className="mt-2 font-serif text-2xl leading-tight">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-muted">{message}</p>
    </div>
  );
}

export function LoadingBlock({ label = "Laster…" }: { label?: string }) {
  return (
    <div className="px-4 py-16 text-center font-condensed text-sm tracking-[0.18em] text-muted uppercase">
      {label}
    </div>
  );
}
