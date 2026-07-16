import type { League, Series } from "../lib/api";

type FiltersProps = {
  leagues: League[];
  series: Series[];
  selectedLeagueId?: number;
  selectedSeriesId?: number;
  onLeagueChange: (leagueId?: number) => void;
  onSeriesChange: (seriesId?: number) => void;
};

export function Filters({
  leagues,
  series,
  selectedLeagueId,
  selectedSeriesId,
  onLeagueChange,
  onSeriesChange
}: FiltersProps) {
  return (
    <div className="filters">
      <label>
        League
        <select
          value={selectedLeagueId ?? ""}
          onChange={(event) => onLeagueChange(event.target.value ? Number(event.target.value) : undefined)}
        >
          <option value="">All leagues</option>
          {leagues.map((league) => (
            <option key={league.id} value={league.id}>
              {league.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Series
        <select
          value={selectedSeriesId ?? ""}
          onChange={(event) => onSeriesChange(event.target.value ? Number(event.target.value) : undefined)}
        >
          <option value="">All series</option>
          {series.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

