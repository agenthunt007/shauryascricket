const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export type League = {
  id: number;
  name: string;
  location: string | null;
};

export type Series = {
  id: number;
  league_id: number;
  name: string;
  season: string | null;
};

export type Match = {
  id: number;
  series_id: number;
  played_on: string | null;
  opponent: string | null;
  venue: string | null;
  result: "won" | "lost" | "tied" | "no_result" | "unknown";
  summary: string | null;
  source_url: string;
};

export type ScorecardInnings = {
  id: number;
  match_id: number;
  innings_number: number;
  batting_team: string;
  total_runs: number | null;
  total_wickets: number | null;
  overs: number | null;
  extras: number | null;
  extras_detail: string | null;
  did_not_bat: string | null;
  fall_of_wickets: string | null;
};

export type ScorecardBattingLine = {
  id: number;
  innings_number: number;
  batting_team: string;
  position: number | null;
  player_name: string;
  dismissal: string | null;
  runs: number;
  balls: number;
  fours: number;
  sixes: number;
  strike_rate: number | null;
  is_shauryas: boolean;
};

export type ScorecardBowlingLine = {
  id: number;
  innings_number: number;
  bowling_team: string | null;
  player_name: string;
  overs: number;
  maidens: number;
  dots: number;
  runs_conceded: number;
  wickets: number;
  wides: number;
  no_balls: number;
  economy: number | null;
  is_shauryas: boolean;
};

export type MatchScorecard = {
  match: Match;
  innings: ScorecardInnings[];
  batting: ScorecardBattingLine[];
  bowling: ScorecardBowlingLine[];
};

export type PlayerStats = {
  player_id: number;
  display_name: string;
  last_played: string | null;
  recent_scores: string[];
  matches: number;
  innings: number;
  runs: number;
  balls: number;
  fours: number;
  sixes: number;
  not_outs: number;
  batting_average: number | null;
  strike_rate: number | null;
  overs: number;
  wickets: number;
  runs_conceded: number;
  maidens: number;
  economy: number | null;
  bowling_average: number | null;
};

export type PlayerRecords = {
  match_limit: number;
  batting: PlayerStats[];
  bowling: PlayerStats[];
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getLeagues() {
  return getJson<League[]>("/api/leagues");
}

export function getSeries(leagueId?: number) {
  const query = leagueId ? `?league_id=${leagueId}` : "";
  return getJson<Series[]>(`/api/series${query}`);
}

export function getMatches(leagueId?: number, seriesId?: number) {
  const params = new URLSearchParams();
  if (leagueId) {
    params.set("league_id", String(leagueId));
  }
  if (seriesId) {
    params.set("series_id", String(seriesId));
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  return getJson<Match[]>(`/api/matches${query}`);
}

export function getPlayerStats(leagueId?: number, seriesId?: number) {
  const params = new URLSearchParams();
  if (leagueId) {
    params.set("league_id", String(leagueId));
  }
  if (seriesId) {
    params.set("series_id", String(seriesId));
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  return getJson<PlayerStats[]>(`/api/stats/players${query}`);
}

export function getPlayerRecords(leagueId?: number, seriesId?: number, matchLimit = 7) {
  const params = new URLSearchParams();
  if (leagueId) {
    params.set("league_id", String(leagueId));
  }
  if (seriesId) {
    params.set("series_id", String(seriesId));
  }
  params.set("match_limit", String(matchLimit));
  return getJson<PlayerRecords>(`/api/stats/player-records?${params.toString()}`);
}

export function getMatchScorecard(matchId: number) {
  return getJson<MatchScorecard>(`/api/matches/${matchId}/scorecard`);
}
