import { AnalyseEntry } from "@/components/AnalyseEntry";
import { Hero } from "@/components/Hero";
import { MinLofthus } from "@/components/MinLofthus";
import { PlayersTalkedAbout } from "@/components/PlayersTalkedAbout";
import { Talkers } from "@/components/Talkers";

export default function Home() {
  return (
    <main className="flex-1">
      <Hero />
      <Talkers />
      <PlayersTalkedAbout />
      <MinLofthus />
      <AnalyseEntry />
    </main>
  );
}
