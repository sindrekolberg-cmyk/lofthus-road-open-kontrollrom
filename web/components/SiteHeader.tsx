"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { nav } from "@/lib/data";

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 bg-ink text-paper">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-6 px-4 sm:px-6">
        <Link
          href="/"
          className="shrink-0 font-condensed text-[15px] font-semibold tracking-[0.18em] text-paper"
        >
          LOFTHUS ROAD OPEN
        </Link>

        <nav className="hidden items-center gap-7 md:flex" aria-label="Hovedmeny">
          {nav.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`font-condensed text-[13px] tracking-[0.14em] uppercase transition-colors ${
                  active ? "text-paper" : "text-paper/55 hover:text-paper"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center md:hidden"
          aria-expanded={open}
          aria-label={open ? "Lukk meny" : "Åpne meny"}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="sr-only">Meny</span>
          <span className="flex flex-col gap-1.5">
            <span className="block h-px w-5 bg-paper" />
            <span className="block h-px w-5 bg-paper" />
          </span>
        </button>
      </div>

      {open ? (
        <nav
          className="border-t border-white/10 px-4 py-4 md:hidden"
          aria-label="Mobilmeny"
        >
          <ul className="flex flex-col gap-3">
            {nav.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="font-condensed text-sm tracking-[0.14em] uppercase text-paper/80"
                  onClick={() => setOpen(false)}
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
    </header>
  );
}
