import { CalendarDays, ExternalLink, Trophy, Users } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Filters } from "../components/Filters";
import { StatCard } from "../components/StatCard";
import {
  getLeagues,
  getMatches,
  getMatchScorecard,
  getPlayerRecords,
  getPlayerStats,
  getSeries,
  type League,
  type Match,
  type MatchScorecard,
  type PlayerRecords,
  type PlayerStats,
  type Series
} from "../lib/api";

const RECORD_MATCH_LIMITS = [7, 10, 14, 21];

type SortDirection = "asc" | "desc";
type SortConfig = {
  key: string;
  direction: SortDirection;
};

const SORT_LABELS: Record<string, string> = {
  batting_average: "batting average",
  bowling_average: "bowling average",
  boundaries: "4s/6s",
  display_name: "player",
  economy: "economy",
  innings: "innings",
  last_played: "last played",
  matches: "matches",
  overs: "overs",
  recent_scores: "scores",
  runs: "runs",
  strike_rate: "strike rate",
  wickets: "wickets"
};

export function Dashboard() {
  const [leagues, setLeagues] = useState<League[]>([]);
  const [series, setSeries] = useState<Series[]>([]);
  const [matches, setMatches] = useState<Match[]>([]);
  const [stats, setStats] = useState<PlayerStats[]>([]);
  const [playerRecords, setPlayerRecords] = useState<PlayerRecords | null>(null);
  const [recordMatchLimit, setRecordMatchLimit] = useState(7);
  const [recentBattingSort, setRecentBattingSort] = useState<SortConfig>({ key: "batting_average", direction: "desc" });
  const [recentBowlingSort, setRecentBowlingSort] = useState<SortConfig>({ key: "bowling_average", direction: "asc" });
  const [allBattingSort, setAllBattingSort] = useState<SortConfig>({ key: "runs", direction: "desc" });
  const [allBowlingSort, setAllBowlingSort] = useState<SortConfig>({ key: "wickets", direction: "desc" });
  const [selectedLeagueId, setSelectedLeagueId] = useState<number | undefined>();
  const [selectedSeriesId, setSelectedSeriesId] = useState<number | undefined>();
  const [selectedMatchId, setSelectedMatchId] = useState<number | undefined>();
  const [selectedInningsNumber, setSelectedInningsNumber] = useState(1);
  const [scorecard, setScorecard] = useState<MatchScorecard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const scorecardRef = useRef<HTMLElement | null>(null);
  const shouldScrollToScorecard = useRef(false);

  useEffect(() => {
    getLeagues().then(setLeagues).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getSeries(selectedLeagueId),
      getMatches(selectedLeagueId, selectedSeriesId),
      getPlayerStats(selectedLeagueId, selectedSeriesId),
      getPlayerRecords(selectedLeagueId, selectedSeriesId, recordMatchLimit)
    ])
      .then(([seriesData, matchData, statsData, recordsData]) => {
        setSeries(seriesData);
        setMatches(matchData);
        setStats(statsData);
        setPlayerRecords(recordsData);
        setSelectedMatchId(matchData[0]?.id);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedLeagueId, selectedSeriesId, recordMatchLimit]);

  useEffect(() => {
    if (!selectedMatchId) {
      setScorecard(null);
      return;
    }
    getMatchScorecard(selectedMatchId)
      .then((data) => {
        setScorecard(data);
        setSelectedInningsNumber(data.innings[0]?.innings_number ?? 1);
        if (shouldScrollToScorecard.current) {
          shouldScrollToScorecard.current = false;
          window.requestAnimationFrame(() => {
            scorecardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
          });
        }
      })
      .catch((err) => setError(err.message));
  }, [selectedMatchId]);

  const totals = useMemo(() => {
    const wins = matches.filter((match) => match.result === "won").length;
    return {
      matches: matches.length,
      players: stats.filter((player) => player.matches > 0).length,
      wins
    };
  }, [matches, stats]);

  const recentBatters = sortPlayers(playerRecords?.batting ?? [], recentBattingSort);
  const recentBowlers = sortPlayers(playerRecords?.bowling ?? [], recentBowlingSort);
  const allBatters = sortPlayers(stats.filter((player) => player.innings > 0), allBattingSort);
  const allBowlers = sortPlayers(stats.filter((player) => player.overs > 0), allBowlingSort);

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">Houston league cricket</p>
          <h1>Shauryas Cricket</h1>
          <p className="hero-copy">
            Match history and player performance by league and series, powered by public CricClubs scorecards.
          </p>
        </div>
        <Filters
          leagues={leagues}
          series={series}
          selectedLeagueId={selectedLeagueId}
          selectedSeriesId={selectedSeriesId}
          onLeagueChange={(leagueId) => {
            setSelectedLeagueId(leagueId);
            setSelectedSeriesId(undefined);
          }}
          onSeriesChange={setSelectedSeriesId}
        />
      </section>

      {error && <div className="notice">{error}</div>}
      {loading && <div className="notice">Loading latest stats...</div>}

      <section className="summary-grid" aria-label="Team summary">
        <StatCard label="Matches tracked" value={totals.matches} />
        <StatCard label="Players" value={totals.players} />
        <StatCard label="Wins" value={totals.wins} />
      </section>

      <section className="records-section" aria-label="Recent player records">
        <div className="records-toolbar">
          <div>
            <p className="eyebrow">Recent form</p>
            <h2>Player Average Records</h2>
            <p className="section-note">
              Only players with at least {recordMatchLimit} Shauryas matches are considered.
            </p>
          </div>
          <label>
            Match window
            <select
              value={recordMatchLimit}
              onChange={(event) => setRecordMatchLimit(Number(event.target.value))}
            >
              {RECORD_MATCH_LIMITS.map((limit) => (
                <option key={limit} value={limit}>Last {limit} matches</option>
              ))}
            </select>
          </label>
        </div>

        <div className="records-grid">
          <div className="panel records-panel">
            <div className="panel-heading">
              <Trophy size={20} />
              <div>
                <h2>Batting Averages</h2>
                <p className="sort-note">{sortDescription(recentBattingSort)}</p>
              </div>
            </div>
            <div className="records-table-wrap">
              <table>
                <thead>
                  <tr>
                    <SortableTh label="Player" sortKey="display_name" sort={recentBattingSort} onSort={setRecentBattingSort} />
                    <SortableTh label="Last Played" sortKey="last_played" sort={recentBattingSort} onSort={setRecentBattingSort} />
                    <SortableTh label="Mat" sortKey="matches" sort={recentBattingSort} onSort={setRecentBattingSort} />
                    <SortableTh label="Inn" sortKey="innings" sort={recentBattingSort} onSort={setRecentBattingSort} />
                    <SortableTh label="Runs" sortKey="runs" sort={recentBattingSort} onSort={setRecentBattingSort} />
                    <SortableTh label="Scores" sortKey="recent_scores" sort={recentBattingSort} onSort={setRecentBattingSort} />
                    <SortableTh label="Avg" sortKey="batting_average" sort={recentBattingSort} onSort={setRecentBattingSort} />
                    <SortableTh label="SR" sortKey="strike_rate" sort={recentBattingSort} onSort={setRecentBattingSort} />
                  </tr>
                </thead>
                <tbody>
                  {recentBatters.map((player) => (
                    <tr key={player.player_id}>
                      <td>{player.display_name}</td>
                      <td>{formatDate(player.last_played)}</td>
                      <td>{player.matches}</td>
                      <td>{player.innings}</td>
                      <td>{player.runs}</td>
                      <td className="scores-cell">{formatScores(player.recent_scores)}</td>
                      <td>{player.batting_average ?? "-"}</td>
                      <td>{player.strike_rate ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel records-panel">
            <div className="panel-heading">
              <Users size={20} />
              <div>
                <h2>Bowling Averages</h2>
                <p className="sort-note">{sortDescription(recentBowlingSort)}</p>
              </div>
            </div>
            <div className="records-table-wrap">
              <table>
                <thead>
                  <tr>
                    <SortableTh label="Player" sortKey="display_name" sort={recentBowlingSort} onSort={setRecentBowlingSort} />
                    <SortableTh label="Last Played" sortKey="last_played" sort={recentBowlingSort} onSort={setRecentBowlingSort} />
                    <SortableTh label="Mat" sortKey="matches" sort={recentBowlingSort} onSort={setRecentBowlingSort} />
                    <SortableTh label="Overs" sortKey="overs" sort={recentBowlingSort} onSort={setRecentBowlingSort} />
                    <SortableTh label="Wkts" sortKey="wickets" sort={recentBowlingSort} onSort={setRecentBowlingSort} />
                    <SortableTh label="Avg" sortKey="bowling_average" sort={recentBowlingSort} onSort={setRecentBowlingSort} />
                    <SortableTh label="Econ" sortKey="economy" sort={recentBowlingSort} onSort={setRecentBowlingSort} />
                  </tr>
                </thead>
                <tbody>
                  {recentBowlers.map((player) => (
                    <tr key={player.player_id}>
                      <td>{player.display_name}</td>
                      <td>{formatDate(player.last_played)}</td>
                      <td>{player.matches}</td>
                      <td>{player.overs}</td>
                      <td>{player.wickets}</td>
                      <td>{player.bowling_average ?? "-"}</td>
                      <td>{player.economy ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <section className="records-grid all-records-section" aria-label="All player records">
        <div className="panel">
          <div className="panel-heading">
            <Trophy size={20} />
            <div>
              <h2>All Batting Records</h2>
              <p className="sort-note">{sortDescription(allBattingSort)}</p>
            </div>
          </div>
          <div className="records-table-wrap">
            <table>
              <thead>
                <tr>
                  <SortableTh label="Player" sortKey="display_name" sort={allBattingSort} onSort={setAllBattingSort} />
                  <SortableTh label="Mat" sortKey="matches" sort={allBattingSort} onSort={setAllBattingSort} />
                  <SortableTh label="Runs" sortKey="runs" sort={allBattingSort} onSort={setAllBattingSort} />
                  <SortableTh label="Avg" sortKey="batting_average" sort={allBattingSort} onSort={setAllBattingSort} />
                  <SortableTh label="SR" sortKey="strike_rate" sort={allBattingSort} onSort={setAllBattingSort} />
                  <SortableTh label="4s/6s" sortKey="boundaries" sort={allBattingSort} onSort={setAllBattingSort} />
                </tr>
              </thead>
              <tbody>
                {allBatters.map((player) => (
                  <tr key={player.player_id}>
                    <td>{player.display_name}</td>
                    <td>{player.matches}</td>
                    <td>{player.runs}</td>
                    <td>{player.batting_average ?? "-"}</td>
                    <td>{player.strike_rate ?? "-"}</td>
                    <td>{player.fours}/{player.sixes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <Users size={20} />
            <div>
              <h2>All Bowling Records</h2>
              <p className="sort-note">{sortDescription(allBowlingSort)}</p>
            </div>
          </div>
          <div className="records-table-wrap">
            <table>
              <thead>
                <tr>
                  <SortableTh label="Player" sortKey="display_name" sort={allBowlingSort} onSort={setAllBowlingSort} />
                  <SortableTh label="Mat" sortKey="matches" sort={allBowlingSort} onSort={setAllBowlingSort} />
                  <SortableTh label="Wkts" sortKey="wickets" sort={allBowlingSort} onSort={setAllBowlingSort} />
                  <SortableTh label="Overs" sortKey="overs" sort={allBowlingSort} onSort={setAllBowlingSort} />
                  <SortableTh label="Econ" sortKey="economy" sort={allBowlingSort} onSort={setAllBowlingSort} />
                  <SortableTh label="Avg" sortKey="bowling_average" sort={allBowlingSort} onSort={setAllBowlingSort} />
                </tr>
              </thead>
              <tbody>
                {allBowlers.map((player) => (
                  <tr key={player.player_id}>
                    <td>{player.display_name}</td>
                    <td>{player.matches}</td>
                    <td>{player.wickets}</td>
                    <td>{player.overs}</td>
                    <td>{player.economy ?? "-"}</td>
                    <td>{player.bowling_average ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="match-browser" aria-label="Matches and scorecard">
        <section className="panel matches-panel">
          <div className="panel-heading">
            <CalendarDays size={20} />
            <h2>Matches</h2>
          </div>
          <div className="match-list">
            <div className="match-list-header" aria-hidden="true">
              <span>Date</span>
              <span>Match</span>
              <span>Result</span>
              <span>Scorecard</span>
            </div>
            {matches.map((match) => (
              <div
                className={`match-row ${selectedMatchId === match.id ? "active" : ""}`}
                key={match.id}
              >
                <button
                  className="match-row-select"
                  type="button"
                  onClick={() => {
                    shouldScrollToScorecard.current = true;
                    setSelectedMatchId(match.id);
                  }}
                >
                  <span>{match.played_on ?? "Date unavailable"}</span>
                  <strong>Shauryas vs {match.opponent ?? "Opponent"}</strong>
                  <small>{[match.venue, match.summary ?? formatResult(match.result)].filter(Boolean).join(" · ")}</small>
                  <span className="view-scorecard-chip">View</span>
                </button>
                <a className="match-scorecard-link" href={match.source_url} target="_blank" rel="noreferrer">
                  <ExternalLink size={16} />
                  <span>CricClubs</span>
                </a>
              </div>
            ))}
          </div>
        </section>

        {scorecard && (
          <ScorecardView
            sectionRef={scorecardRef}
            scorecard={scorecard}
            selectedInningsNumber={selectedInningsNumber}
            onInningsChange={setSelectedInningsNumber}
          />
        )}
      </section>
    </main>
  );
}

type SortableThProps = {
  label: string;
  sortKey: string;
  sort: SortConfig;
  onSort: (next: SortConfig | ((current: SortConfig) => SortConfig)) => void;
};

function SortableTh({ label, sortKey, sort, onSort }: SortableThProps) {
  const active = sort.key === sortKey;
  const indicator = active ? (sort.direction === "asc" ? "↑" : "↓") : "↕";

  return (
    <th>
      <button
        className={`sort-button ${active ? "active" : ""}`}
        type="button"
        onClick={() => {
          onSort((current) => ({
            key: sortKey,
            direction: current.key === sortKey ? toggleDirection(current.direction) : defaultDirection(sortKey)
          }));
        }}
      >
        <span>{label}</span>
        <span aria-hidden="true">{indicator}</span>
      </button>
    </th>
  );
}

function sortPlayers(players: PlayerStats[], sort: SortConfig) {
  return [...players].sort((a, b) => compareSortValues(sortValue(a, sort.key), sortValue(b, sort.key), sort.direction));
}

function sortValue(player: PlayerStats, key: string): string | number | null {
  switch (key) {
    case "boundaries":
      return player.fours + player.sixes;
    case "recent_scores":
      return player.recent_scores.join(" ");
    default:
      return player[key as keyof PlayerStats] as string | number | null;
  }
}

function compareSortValues(a: string | number | null, b: string | number | null, direction: SortDirection) {
  if (a === null && b === null) {
    return 0;
  }
  if (a === null) {
    return 1;
  }
  if (b === null) {
    return -1;
  }

  const result = typeof a === "string" && typeof b === "string"
    ? a.localeCompare(b)
    : Number(a) - Number(b);
  return direction === "asc" ? result : -result;
}

function sortDescription(sort: SortConfig) {
  const label = SORT_LABELS[sort.key] ?? sort.key;
  return `Sorted by ${label} ${sort.direction === "asc" ? "ascending" : "descending"}. Click a column header to sort.`;
}

function defaultDirection(key: string): SortDirection {
  return ["bowling_average", "economy", "display_name"].includes(key) ? "asc" : "desc";
}

function toggleDirection(direction: SortDirection): SortDirection {
  return direction === "asc" ? "desc" : "asc";
}

type ScorecardViewProps = {
  sectionRef: React.RefObject<HTMLElement | null>;
  scorecard: MatchScorecard;
  selectedInningsNumber: number;
  onInningsChange: (inningsNumber: number) => void;
};

function ScorecardView({ sectionRef, scorecard, selectedInningsNumber, onInningsChange }: ScorecardViewProps) {
  const selectedInnings = scorecard.innings.find((innings) => innings.innings_number === selectedInningsNumber)
    ?? scorecard.innings[0];

  if (!selectedInnings) {
    return null;
  }

  const batting = scorecard.batting.filter((line) => line.innings_number === selectedInnings.innings_number);
  const bowling = scorecard.bowling.filter((line) => line.innings_number === selectedInnings.innings_number);
  const inningsTotal = formatInningsTotal(selectedInnings.total_runs, selectedInnings.total_wickets, selectedInnings.overs);

  return (
    <section className="panel scorecard-panel" ref={sectionRef}>
      <div className="scorecard-header">
        <div>
          <p className="eyebrow">Full scorecard</p>
          <h2>Shauryas vs {scorecard.match.opponent ?? "Opponent"}</h2>
          <p>{scorecard.match.summary ?? scorecard.match.result.replace("_", " ")}</p>
        </div>
        <a className="source-link" href={scorecard.match.source_url} target="_blank" rel="noreferrer">
          <ExternalLink size={16} />
          CricClubs
        </a>
      </div>

      <div className="match-meta">
        <span>{scorecard.match.played_on ?? "Date unavailable"}</span>
        {scorecard.match.venue && <span>{scorecard.match.venue}</span>}
        <span>{scorecard.innings.map((innings) => `${innings.batting_team} ${formatInningsTotal(innings.total_runs, innings.total_wickets, innings.overs)}`).join(" · ")}</span>
      </div>

      <div className="innings-tabs" role="tablist" aria-label="Innings">
        {scorecard.innings.map((innings) => (
          <button
            className={selectedInnings.innings_number === innings.innings_number ? "active" : ""}
            key={innings.id}
            type="button"
            onClick={() => onInningsChange(innings.innings_number)}
          >
            <span>{innings.batting_team}</span>
            <strong>{formatInningsTotal(innings.total_runs, innings.total_wickets, innings.overs)}</strong>
          </button>
        ))}
      </div>

      <div className="innings-scoreline">
        <h3>{selectedInnings.batting_team} innings</h3>
        <strong>{inningsTotal}</strong>
      </div>

      <div className="scorecard-table-wrap">
        <table className="scorecard-table batting-table">
          <thead>
            <tr>
              <th>Batter</th>
              <th>How out</th>
              <th>R</th>
              <th>B</th>
              <th>4s</th>
              <th>6s</th>
              <th>SR</th>
            </tr>
          </thead>
          <tbody>
            {batting.map((line) => (
              <tr key={line.id} className={line.is_shauryas ? "highlight-row" : undefined}>
                <td><strong>{line.player_name}</strong></td>
                <td className="dismissal-cell">{line.dismissal || "-"}</td>
                <td><strong>{line.runs}</strong></td>
                <td>{line.balls}</td>
                <td>{line.fours}</td>
                <td>{line.sixes}</td>
                <td>{line.strike_rate ?? "-"}</td>
              </tr>
            ))}
            <tr className="total-row">
              <td>Extras</td>
              <td>{selectedInnings.extras_detail ?? "-"}</td>
              <td><strong>{selectedInnings.extras ?? 0}</strong></td>
              <td />
              <td />
              <td />
              <td />
            </tr>
            <tr className="total-row">
              <td>Total</td>
              <td>{selectedInnings.overs !== null ? `${selectedInnings.overs} overs` : "-"}</td>
              <td><strong>{selectedInnings.total_runs ?? 0}</strong></td>
              <td />
              <td />
              <td />
              <td />
            </tr>
          </tbody>
        </table>
      </div>

      {(selectedInnings.did_not_bat || selectedInnings.fall_of_wickets) && (
        <div className="scorecard-notes">
          {selectedInnings.did_not_bat && <p><strong>Did not bat:</strong> {stripLabel(selectedInnings.did_not_bat, "Did not bat:")}</p>}
          {selectedInnings.fall_of_wickets && <p><strong>Fall of wickets:</strong> {stripLabel(selectedInnings.fall_of_wickets, "Fall of Wickets")}</p>}
        </div>
      )}

      <div className="innings-scoreline secondary">
        <h3>Bowling</h3>
        <span>{bowling[0]?.bowling_team ?? "Bowling team"}</span>
      </div>

      <div className="scorecard-table-wrap">
        <table className="scorecard-table">
          <thead>
            <tr>
              <th>Bowler</th>
              <th>O</th>
              <th>M</th>
              <th>Dot</th>
              <th>R</th>
              <th>W</th>
              <th>Extras</th>
              <th>Econ</th>
            </tr>
          </thead>
          <tbody>
            {bowling.map((line) => (
              <tr key={line.id} className={line.is_shauryas ? "highlight-row" : undefined}>
                <td><strong>{line.player_name}</strong></td>
                <td>{line.overs}</td>
                <td>{line.maidens}</td>
                <td>{line.dots}</td>
                <td>{line.runs_conceded}</td>
                <td><strong>{line.wickets}</strong></td>
                <td>{formatBowlingExtras(line.wides, line.no_balls)}</td>
                <td>{line.economy ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatInningsTotal(runs: number | null, wickets: number | null, overs: number | null) {
  const score = `${runs ?? 0}/${wickets ?? 0}`;
  return overs !== null ? `${score} (${overs})` : score;
}

function formatBowlingExtras(wides: number, noBalls: number) {
  if (!wides && !noBalls) {
    return "-";
  }
  return [`${wides}w`, `${noBalls}nb`].filter((item) => !item.startsWith("0")).join(", ");
}

function formatResult(result: Match["result"]) {
  const labels: Record<Match["result"], string> = {
    won: "Shauryas won",
    lost: "Shauryas lost",
    tied: "Match tied",
    no_result: "No result",
    unknown: "Result not listed"
  };
  return labels[result];
}

function formatDate(value: string | null) {
  return value ?? "-";
}

function formatScores(scores: string[]) {
  return scores.length ? scores.join("  ") : "-";
}

function stripLabel(value: string, label: string) {
  return value.replace(label, "").trim();
}
