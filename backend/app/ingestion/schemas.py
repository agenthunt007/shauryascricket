from dataclasses import dataclass, field
from datetime import date

from app.models.domain import MatchResult


@dataclass(frozen=True)
class ParsedBatter:
    name: str
    position: int | None
    runs: int
    balls: int
    fours: int
    sixes: int
    dismissal: str | None
    not_out: bool
    cricclubs_player_id: str | None = None


@dataclass(frozen=True)
class ParsedBowler:
    name: str
    overs: float
    maidens: int
    runs_conceded: int
    wickets: int
    wides: int = 0
    no_balls: int = 0
    cricclubs_player_id: str | None = None
    dots: int = 0
    economy: float | None = None


@dataclass(frozen=True)
class ParsedInnings:
    innings_number: int
    batting_team: str
    total_runs: int | None = None
    total_wickets: int | None = None
    overs: float | None = None
    extras: int | None = None
    extras_detail: str | None = None
    did_not_bat: str | None = None
    fall_of_wickets: str | None = None
    batters: list[ParsedBatter] = field(default_factory=list)
    bowlers: list[ParsedBowler] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedScorecard:
    source_url: str
    source_match_id: str | None
    played_on: date | None
    opponent: str | None
    venue: str | None
    result: MatchResult
    toss: str | None
    summary: str | None
    batters: list[ParsedBatter] = field(default_factory=list)
    bowlers: list[ParsedBowler] = field(default_factory=list)
    innings: list[ParsedInnings] = field(default_factory=list)
    raw_payload: dict = field(default_factory=dict)
