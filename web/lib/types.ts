export type EventStatus = "live" | "finished" | "between_matches" | "pre" | string;

export type Status = {
  name: string;
  season: string;
  event_id: number;
  event_status: EventStatus;
  event_status_label: string;
  is_live: boolean;
  is_finished: boolean;
  provisional: boolean;
  month_name: string;
  fetched_at: string | null;
  league_size: number;
  live_ready: boolean;
  histories_ready: boolean;
  data_quality: Record<string, unknown>;
  errors: string[];
};

export type ManagerRow = {
  entry: number;
  manager: string;
  team: string;
  rank: number;
  previous_rank: number;
  rank_change: number;
  captain: string;
  captain_element: number;
  vice_captain: string;
  vice_element: number;
  gw: number;
  gw_gross: number;
  hits: number;
  total: number;
  official_total: number;
  official_gw: number;
  chip: string;
  players_started: number;
  players_finished: number;
  players_live: number;
  players_remaining: number;
  month_points: number;
  month_rank: number;
  team_value: number;
  bank: number;
};

export type PlayerCard = {
  element: number;
  player: string;
  club: string;
  event_points: number;
  ownership_count: number;
  ownership_pct: number;
  captain_count: number;
  triple_captain_count: number;
  effective_ownership_pct: number;
  live_minutes: number;
  fixture_status: string;
  fixture_status_label: string;
  impact_score: number;
  image_url: string;
  kicker?: string;
  headline?: string;
  dek?: string;
};

export type SquadPlayer = {
  element: number;
  player: string;
  full_name: string;
  club: string;
  position: string;
  position_id: number;
  squad_position: number;
  event_points: number;
  gw_contribution: number;
  multiplier: number;
  is_captain: boolean;
  is_vice_captain: boolean;
  is_triple_captain: boolean;
  on_bench: boolean;
  fixture_status: string;
  fixture_status_label: string;
  image_url: string;
  minutes: number;
};

export type Squad = {
  xi: SquadPlayer[];
  bench: SquadPlayer[];
  lines: {
    gk: SquadPlayer[];
    def: SquadPlayer[];
    mid: SquadPlayer[];
    fwd: SquadPlayer[];
  };
};

export type Story = {
  key: string;
  category: string;
  headline: string;
  meta: string;
  importance: number;
  freshness: number;
  status: string;
  confidence: number;
  manager_entry: number;
  player_element: number;
  image_url?: string;
};

export type HomePayload = {
  status: Status;
  hero: PlayerCard | null;
  top5: ManagerRow[];
  news: Story[];
  popular: PlayerCard[];
  month: { name: string; table: ManagerRow[] };
  managers: { entry: number; manager: string; team: string }[];
};

export type LeaguePayload = {
  status: Status;
  table: ManagerRow[];
};

export type LivePayload = {
  status: Status;
  table: ManagerRow[];
  gw_ranking: ManagerRow[];
  fixtures: {
    id: number;
    kickoff: string;
    minutes: number;
    status: string;
    status_label: string;
    home: string;
    away: string;
    home_name: string;
    away_name: string;
    home_score: number | null;
    away_score: number | null;
  }[];
  player_impacts: PlayerCard[];
  live_ready: boolean;
};

export type MonthPayload = {
  status: Status;
  month_name: string;
  table: ManagerRow[];
  previous: {
    season: string;
    month: string;
    winner: string;
    runner_up: string;
    third: string;
  }[];
};

export type ManagerOption = {
  entry: number;
  manager: string;
  team: string;
  rank: number;
};

export type ManagerProfile = {
  manager: ManagerRow;
  story: string;
  squad: Squad;
  form: {
    event: number;
    points: number;
    total_points: number;
    round_rank: number;
    league_rank: number;
    is_live?: boolean;
  }[];
  chips: { chip: string; event: number; gw: string }[];
  fpl_career: { season: string; points: number; overall_rank: number | null }[];
  fpl_season: { overall_rank: number | null; total_points: number; value: number | null };
  lofthus_merits: {
    rank: number | null;
    league_gold: number;
    league_silver: number;
    league_bronze: number;
    cup_gold: number;
    cup_silver: number;
    monthly_gold: number;
    monthly_silver: number;
    monthly_bronze: number;
    league_seasons: string[];
    cup_seasons: string[];
  };
  lofthus_overall: { season: string; place: number }[];
  lofthus_best_finish: number | null;
  provisional: boolean;
  event_id: number;
  month_name: string;
  is_live: boolean;
};

export type RivalEdge = {
  element: number;
  player: string;
  my_multiplier: number;
  rival_multiplier: number;
  multiplier_edge: number;
  event_points: number;
  live_swing: number;
  status: string;
  status_label: string;
  headline: string;
};

export type RivalPayload = {
  me: ManagerRow;
  rival: ManagerRow;
  live_gap: number;
  total_gap: number;
  gw_gap: number;
  common_players: number;
  captains: { me: string; rival: string };
  players_remaining: { me: number; rival: number };
  cheer_for: RivalEdge[];
  hope_blank: RivalEdge[];
  my_unique: RivalEdge[];
  rival_unique: RivalEdge[];
  suggested_rivals: number[];
  provisional: boolean;
  is_live: boolean;
  event_id: number;
};

export type HistoryPayload = {
  overall: {
    season: string;
    winner: string;
    runner_up: string;
    third_place: string;
    note: string;
    status: string;
  }[];
  cup: {
    season: string;
    winner: string;
    runner_up: string;
    note: string;
    status: string;
  }[];
  random: {
    season: string;
    winner: string;
    placement: string;
    note: string;
  }[];
  monthly: {
    season: string;
    month: string;
    winner: string;
    runner_up: string;
    third: string;
  }[];
};

export type HallOfFameRow = {
  rank: number;
  manager: string;
  league_gold: number;
  league_silver: number;
  league_bronze: number;
  cup_gold: number;
  cup_silver: number;
  monthly_gold: number;
  monthly_silver: number;
  monthly_bronze: number;
  gold: number;
  silver: number;
  bronze: number;
  podiums: number;
  league_seasons: string[];
  cup_seasons: string[];
};

export const nav = [
  { href: "/", label: "Forside" },
  { href: "/liga", label: "Liga" },
  { href: "/live", label: "Live" },
  { href: "/rivalradar", label: "Rivalradar" },
  { href: "/historikk", label: "Historikk" },
  { href: "/hall-of-fame", label: "Hall of Fame" },
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
    href: "/analyse#kaptein",
    kicker: "Armbindet",
    title: "Kaptein",
    line: "Hvem bar C-en, og hvem fikk betalt for det.",
  },
  {
    href: "/analyse#ownership",
    kicker: "Feltet",
    title: "Ownership",
    line: "Differensialene som splittet Lofthus denne runden.",
  },
  {
    href: "/analyse#chips",
    kicker: "Timing",
    title: "Chips",
    line: "Wildcard, bench boost og de som fortsatt venter.",
  },
  {
    href: "/analyse#differensialer",
    kicker: "Skjevt",
    title: "Differensialer",
    line: "Lavt eierskap, høy smelle. Eller blank.",
  },
];
