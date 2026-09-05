"use client";

import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { AnalyseEntry } from "@/components/AnalyseEntry";
import { ApiState, LoadingBlock } from "@/components/ApiState";
import { Hero } from "@/components/Hero";
import { MinLofthus } from "@/components/MinLofthus";
import { PlayersTalkedAbout } from "@/components/PlayersTalkedAbout";
import { Talkers } from "@/components/Talkers";

export function HomePage() {
  const { data, error, loading } = useApi(() => api.home(), []);

  if (loading && !data) {
    return (
      <main className="flex-1">
        <LoadingBlock label="Henter Lofthus…" />
      </main>
    );
  }

  if (error && !data) {
    return (
      <main className="flex-1 px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-[1400px]">
          <ApiState title="Forsiden venter på motoren" message={error} />
        </div>
      </main>
    );
  }

  const home = data;
  if (!home) return null;

  return (
    <main className="flex-1">
      <Hero hero={home.hero} top5={home.top5} status={home.status} />
      <Talkers
        stories={home.news}
        monthName={home.month.name}
        monthTable={home.month.table}
      />
      <PlayersTalkedAbout players={home.popular} />
      <MinLofthus managers={home.managers} top={home.top5} />
      <AnalyseEntry />
    </main>
  );
}
