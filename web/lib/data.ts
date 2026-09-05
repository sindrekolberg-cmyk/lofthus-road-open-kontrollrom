export type LiveRow = {
  rank: number;
  manager: string;
  gw: number;
  total: number;
  swing: number;
};

export const liveTable: LiveRow[] = [
  { rank: 1, manager: "Mats Arntzen", gw: 68, total: 214, swing: 2 },
  { rank: 2, manager: "Sindre Kolberg", gw: 61, total: 208, swing: 3 },
  { rank: 3, manager: "Rasmus Grytvik-Skoglund", gw: 64, total: 205, swing: -1 },
  { rank: 4, manager: "Edward Stenlund", gw: 59, total: 199, swing: 0 },
  { rank: 5, manager: "Robin Andersen", gw: 57, total: 196, swing: -2 },
];

export const me = {
  name: "Sindre Kolberg",
  rank: 2,
  total: 208,
  gw: 61,
  places: 3,
};

export const playersInFocus = [
  {
    name: "Erling Haaland",
    club: "Manchester City",
    ownership: "78%",
    lastGw: 13,
    src: "/images/players/haaland.jpg",
    position: "center 18%",
  },
  {
    name: "João Pedro",
    club: "Chelsea",
    ownership: "31%",
    lastGw: 11,
    src: "/images/players/pedro.jpg",
    position: "center 22%",
  },
  {
    name: "Riccardo Calafiori",
    club: "Arsenal",
    ownership: "18%",
    lastGw: 9,
    src: "/images/players/calafiori.jpg",
    position: "center 12%",
  },
  {
    name: "Alexander Isak",
    club: "Liverpool",
    ownership: "44%",
    lastGw: 12,
    src: "/images/players/isak.jpg",
    position: "center 15%",
  },
];

export const septemberTable = [
  { rank: 1, manager: "Mats Arntzen", points: 148 },
  { rank: 2, manager: "Edward Stenlund", points: 141 },
  { rank: 3, manager: "Sindre Kolberg", points: 136 },
];

export const nav = [
  { href: "/", label: "Forside" },
  { href: "/liga", label: "Liga" },
  { href: "/live", label: "Live" },
  { href: "/rivalradar", label: "Rivalradar" },
  { href: "/historikk", label: "Historikk" },
  { href: "/analyse", label: "Analyse" },
];

export const analysisEntries = [
  {
    href: "/rivalradar",
    kicker: "Hvem jakter deg",
    title: "Rivalradar",
    line: "Avstanden til de som puster deg i nakken — og de du selv jakter.",
  },
  {
    href: "/analyse",
    kicker: "Armbindet",
    title: "Kaptein",
    line: "Hvem bar C-en, og hvem fikk betalt for det.",
  },
  {
    href: "/analyse",
    kicker: "Feltet",
    title: "Ownership",
    line: "Differensialene som splittet Lofthus denne runden.",
  },
  {
    href: "/analyse",
    kicker: "Timing",
    title: "Chips",
    line: "Wildcard, bench boost og de som fortsatt venter.",
  },
  {
    href: "/analyse",
    kicker: "Hode mot hode",
    title: "Compare",
    line: "Sett to managere mot hverandre. Se hvor sesongen ble avgjort.",
  },
];
