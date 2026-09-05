"use client";

import Link from "next/link";
import type { ManagerRow, Status } from "@/lib/types";
import { moveLabel } from "@/lib/format";

type Props = {
  rows: ManagerRow[];
  status: Status | null;
  compact?: boolean;
};

export function LeagueTable({ rows, status, compact }: Props) {
  const provisional = Boolean(status?.provisional);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-left">
        <thead>
          <tr className="border-b border-ink font-condensed text-[11px] tracking-[0.16em] text-muted uppercase">
            <th className="py-3 pr-3 font-medium">Plass</th>
            <th className="py-3 pr-3 font-medium">Manager</th>
            <th className="py-3 pr-3 font-medium">Lag</th>
            <th className="py-3 pr-3 font-medium">Kaptein</th>
            <th className="py-3 pr-3 text-right font-medium">GW</th>
            <th className="py-3 pr-3 text-right font-medium">Total</th>
            <th className="py-3 text-right font-medium">+/-</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.entry}
              className="border-b border-rule transition-colors hover:bg-black/[0.03]"
            >
              <td className="py-3 pr-3 font-condensed text-lg tabular-nums">
                {row.rank}
              </td>
              <td className="py-3 pr-3">
                <Link
                  href={`/manager/${row.entry}`}
                  className="text-[0.95rem] leading-tight hover:underline"
                >
                  {row.manager}
                </Link>
                {row.chip ? (
                  <span className="mt-0.5 block font-condensed text-[10px] tracking-[0.12em] text-live uppercase">
                    {row.chip}
                  </span>
                ) : null}
              </td>
              <td className="py-3 pr-3 text-sm text-muted">{row.team}</td>
              <td className="py-3 pr-3 text-sm">{row.captain || "–"}</td>
              <td className="py-3 pr-3 text-right font-condensed text-lg tabular-nums">
                {row.gw}
              </td>
              <td className="py-3 pr-3 text-right font-condensed text-lg font-semibold tabular-nums">
                {row.total}
              </td>
              <td
                className={`py-3 text-right font-condensed text-lg tabular-nums ${
                  row.rank_change > 0
                    ? "text-[#2f6a32]"
                    : row.rank_change < 0
                      ? "text-live"
                      : "text-muted"
                }`}
              >
                {provisional && row.rank_change
                  ? moveLabel(row.rank_change, true)
                  : moveLabel(row.rank_change, provisional)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {provisional && !compact ? (
        <p className="mt-3 font-condensed text-[11px] tracking-[0.14em] text-muted uppercase">
          Plasseringene er foreløpige så lenge runden pågår.
        </p>
      ) : null}
    </div>
  );
}
