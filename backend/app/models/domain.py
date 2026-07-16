from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class MatchResult(str, Enum):
    won = "won"
    lost = "lost"
    tied = "tied"
    no_result = "no_result"
    unknown = "unknown"


class League(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    location: str | None = "Houston"


class Series(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("league_id", "name", name="uq_series_league_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    league_id: int = Field(foreign_key="league.id", index=True)
    name: str = Field(index=True)
    season: str | None = None


class Player(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    display_name: str = Field(index=True, unique=True)
    cricclubs_player_id: str | None = Field(default=None, index=True)


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: int = Field(foreign_key="series.id", index=True)
    source_url: str = Field(index=True, unique=True)
    source_match_id: str | None = Field(default=None, index=True)
    played_on: date | None = Field(default=None, index=True)
    opponent: str | None = Field(default=None, index=True)
    venue: str | None = None
    result: MatchResult = Field(default=MatchResult.unknown)
    toss: str | None = None
    summary: str | None = None
    raw_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BattingInnings(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_batting_match_player"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    player_id: int = Field(foreign_key="player.id", index=True)
    batting_position: int | None = None
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    dismissal: str | None = None
    not_out: bool = False


class BowlingSpell(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_bowling_match_player"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    player_id: int = Field(foreign_key="player.id", index=True)
    overs: float = 0
    maidens: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    wides: int = 0
    no_balls: int = 0


class ScorecardInnings(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("match_id", "innings_number", name="uq_scorecard_innings_match_number"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    innings_number: int = Field(index=True)
    batting_team: str = Field(index=True)
    total_runs: int | None = None
    total_wickets: int | None = None
    overs: float | None = None
    extras: int | None = None
    extras_detail: str | None = None
    did_not_bat: str | None = None
    fall_of_wickets: str | None = None


class ScorecardBattingLine(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("match_id", "innings_number", "position", "player_name", name="uq_scorecard_batting_line"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    innings_number: int = Field(index=True)
    batting_team: str = Field(index=True)
    position: int | None = None
    player_name: str = Field(index=True)
    cricclubs_player_id: str | None = Field(default=None, index=True)
    dismissal: str | None = None
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    strike_rate: float | None = None
    not_out: bool = False
    is_shauryas: bool = Field(default=False, index=True)


class ScorecardBowlingLine(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("match_id", "innings_number", "player_name", name="uq_scorecard_bowling_line"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    innings_number: int = Field(index=True)
    bowling_team: str | None = Field(default=None, index=True)
    player_name: str = Field(index=True)
    cricclubs_player_id: str | None = Field(default=None, index=True)
    overs: float = 0
    maidens: int = 0
    dots: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    wides: int = 0
    no_balls: int = 0
    economy: float | None = None
    is_shauryas: bool = Field(default=False, index=True)
