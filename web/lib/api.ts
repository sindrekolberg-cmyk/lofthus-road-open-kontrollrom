import type {
  HallOfFameRow,
  HistoryPayload,
  HomePayload,
  LeaguePayload,
  LivePayload,
  ManagerOption,
  ManagerProfile,
  MonthPayload,
  PlayerCard,
  RivalPayload,
  Status,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: { Accept: "application/json", ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Backend er ikke tilgjengelig.", 0);
  }
  if (!res.ok) {
    let detail = `API-feil (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => apiGet<{ ok: boolean }>("/api/health"),
  status: () => apiGet<Status>("/api/status"),
  home: () => apiGet<HomePayload>("/api/home"),
  league: () => apiGet<LeaguePayload>("/api/league"),
  live: () => apiGet<LivePayload>("/api/live"),
  month: () => apiGet<MonthPayload>("/api/month"),
  managers: () => apiGet<{ managers: ManagerOption[] }>("/api/managers"),
  manager: (entry: number) => apiGet<ManagerProfile>(`/api/managers/${entry}`),
  rival: (a: number, b: number) =>
    apiGet<RivalPayload>(`/api/rival?manager_a=${a}&manager_b=${b}`),
  history: () => apiGet<HistoryPayload>("/api/history"),
  hallOfFame: () => apiGet<{ rows: HallOfFameRow[] }>("/api/hall-of-fame"),
  news: () => apiGet<{ stories: HomePayload["news"] }>("/api/news"),
  popular: () => apiGet<{ players: PlayerCard[] }>("/api/players/popular"),
  analysisCaptain: () => apiGet<{ players: PlayerCard[] }>("/api/analysis/captain"),
  analysisOwnership: () =>
    apiGet<{ players: PlayerCard[] }>("/api/analysis/ownership"),
  analysisChips: () =>
    apiGet<{ chips: { entry: number; manager: string; chip: string; gw: number }[] }>(
      "/api/analysis/chips",
    ),
  analysisDifferentials: () =>
    apiGet<{ players: PlayerCard[] }>("/api/analysis/differentials"),
};
