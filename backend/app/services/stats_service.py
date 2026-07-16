from dataclasses import dataclass
import re

from sqlalchemy import desc
from sqlmodel import Session, select

from app.models.domain import BattingInnings, BowlingSpell, Match, Player, ScorecardInnings, Series
from app.models.schemas import PlayerRecordsRead, PlayerStatsRead


@dataclass(frozen=True)
class StatsFilters:
    league_id: int | None = None
    series_id: int | None = None
    match_ids: set[int] | None = None


class StatsService:
    def __init__(self, session: Session):
        self.session = session

    def player_stats(self, filters: StatsFilters) -> list[PlayerStatsRead]:
        players = self.session.exec(select(Player).order_by(Player.display_name)).all()
        return [self._stats_for_player(player, filters) for player in players]

    def player_records(self, filters: StatsFilters, match_limit: int) -> PlayerRecordsRead:
        players = self.session.exec(select(Player).order_by(Player.display_name)).all()
        stats = []
        for player in players:
            match_ids = self._recent_player_match_ids(player, filters, match_limit)
            stats.append(
                self._stats_for_player(
                    player,
                    StatsFilters(league_id=filters.league_id, series_id=filters.series_id, match_ids=match_ids),
                )
            )
        batting = sorted(
            (player for player in stats if player.innings > 0),
            key=lambda player: (
                player.batting_average is None,
                -(player.batting_average or 0),
                -player.runs,
                -player.innings,
                player.display_name,
            ),
        )
        bowling = sorted(
            (player for player in stats if player.overs > 0),
            key=lambda player: (
                player.bowling_average is None,
                player.bowling_average if player.bowling_average is not None else 9999,
                -player.wickets,
                player.economy if player.economy is not None else 9999,
                player.display_name,
            ),
        )
        return PlayerRecordsRead(match_limit=match_limit, batting=batting, bowling=bowling)

    def _stats_for_player(self, player: Player, filters: StatsFilters) -> PlayerStatsRead:
        batting = self._filtered_batting(player.id, filters)
        bowling = self._filtered_bowling(player.id, filters)
        match_ids = (
            {row.match_id for row in batting}
            | {row.match_id for row in bowling}
            | self._filtered_did_not_bat_match_ids(player, filters)
        )

        runs = sum(row.runs for row in batting)
        balls = sum(row.balls for row in batting)
        dismissals = sum(1 for row in batting if not row.not_out)
        overs = sum(row.overs for row in bowling)
        runs_conceded = sum(row.runs_conceded for row in bowling)
        wickets = sum(row.wickets for row in bowling)

        return PlayerStatsRead(
            player_id=player.id,
            display_name=player.display_name,
            last_played=self._last_played(match_ids),
            matches=len(match_ids),
            innings=len(batting),
            runs=runs,
            balls=balls,
            fours=sum(row.fours for row in batting),
            sixes=sum(row.sixes for row in batting),
            not_outs=sum(1 for row in batting if row.not_out),
            batting_average=round(runs / dismissals, 2) if dismissals else None,
            strike_rate=round((runs / balls) * 100, 2) if balls else None,
            overs=round(overs, 1),
            wickets=wickets,
            runs_conceded=runs_conceded,
            maidens=sum(row.maidens for row in bowling),
            economy=round(runs_conceded / overs, 2) if overs else None,
            bowling_average=round(runs_conceded / wickets, 2) if wickets else None,
        )

    def _filtered_batting(self, player_id: int, filters: StatsFilters) -> list[BattingInnings]:
        statement = select(BattingInnings).join(Match).where(BattingInnings.player_id == player_id)
        if filters.match_ids is not None:
            statement = statement.where(BattingInnings.match_id.in_(filters.match_ids))
        if filters.series_id:
            statement = statement.where(Match.series_id == filters.series_id)
        elif filters.league_id:
            statement = statement.join(Series).where(Series.league_id == filters.league_id)
        return list(self.session.exec(statement).all())

    def _filtered_bowling(self, player_id: int, filters: StatsFilters) -> list[BowlingSpell]:
        statement = select(BowlingSpell).join(Match).where(BowlingSpell.player_id == player_id)
        if filters.match_ids is not None:
            statement = statement.where(BowlingSpell.match_id.in_(filters.match_ids))
        if filters.series_id:
            statement = statement.where(Match.series_id == filters.series_id)
        elif filters.league_id:
            statement = statement.join(Series).where(Series.league_id == filters.league_id)
        return list(self.session.exec(statement).all())

    def _filtered_did_not_bat_match_ids(self, player: Player, filters: StatsFilters) -> set[int]:
        statement = (
            select(ScorecardInnings)
            .join(Match)
            .where(
                ScorecardInnings.batting_team == "Shauryas",
                ScorecardInnings.did_not_bat.is_not(None),
            )
        )
        if filters.match_ids is not None:
            statement = statement.where(ScorecardInnings.match_id.in_(filters.match_ids))
        if filters.series_id:
            statement = statement.where(Match.series_id == filters.series_id)
        elif filters.league_id:
            statement = statement.join(Series).where(Series.league_id == filters.league_id)

        player_name = self._normalize_name(player.display_name)
        match_ids = set()
        for innings in self.session.exec(statement).all():
            did_not_bat_names = self._did_not_bat_names(innings.did_not_bat or "")
            if player_name in did_not_bat_names:
                match_ids.add(innings.match_id)
        return match_ids

    def _recent_player_match_ids(self, player: Player, filters: StatsFilters, match_limit: int) -> set[int]:
        match_ids = (
            self._batting_match_ids(player.id, filters)
            | self._bowling_match_ids(player.id, filters)
            | self._filtered_did_not_bat_match_ids(player, filters)
        )
        if not match_ids:
            return set()
        statement = (
            select(Match)
            .where(Match.id.in_(match_ids))
            .order_by(Match.played_on.is_(None), desc(Match.played_on), desc(Match.id))
            .limit(match_limit)
        )
        return {match.id for match in self.session.exec(statement).all() if match.id is not None}

    def _batting_match_ids(self, player_id: int, filters: StatsFilters) -> set[int]:
        return {row.match_id for row in self._filtered_batting(player_id, filters)}

    def _bowling_match_ids(self, player_id: int, filters: StatsFilters) -> set[int]:
        return {row.match_id for row in self._filtered_bowling(player_id, filters)}

    def _last_played(self, match_ids: set[int]):
        if not match_ids:
            return None
        statement = (
            select(Match.played_on)
            .where(Match.id.in_(match_ids), Match.played_on.is_not(None))
            .order_by(desc(Match.played_on), desc(Match.id))
            .limit(1)
        )
        return self.session.exec(statement).first()

    def _did_not_bat_names(self, value: str) -> set[str]:
        value = re.sub(r"^did not bat:\s*", "", value, flags=re.IGNORECASE).strip()
        if not value:
            return set()
        return {self._normalize_name(name) for name in value.split(",") if name.strip()}

    def _normalize_name(self, value: str) -> str:
        return " ".join(
            value.replace("†", "")
            .replace("*", "")
            .replace("(c)", "")
            .replace("(wk)", "")
            .split()
        ).lower()
