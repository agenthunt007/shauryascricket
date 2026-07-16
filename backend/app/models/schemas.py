from datetime import date

from pydantic import BaseModel, HttpUrl

from app.models.domain import MatchResult


class LeagueRead(BaseModel):
    id: int
    name: str
    location: str | None


class SeriesRead(BaseModel):
    id: int
    league_id: int
    name: str
    season: str | None


class MatchRead(BaseModel):
    id: int
    series_id: int
    played_on: date | None
    opponent: str | None
    venue: str | None
    result: MatchResult
    summary: str | None
    source_url: str


class ScorecardInningsRead(BaseModel):
    id: int
    match_id: int
    innings_number: int
    batting_team: str
    total_runs: int | None
    total_wickets: int | None
    overs: float | None
    extras: int | None
    extras_detail: str | None
    did_not_bat: str | None
    fall_of_wickets: str | None


class ScorecardBattingLineRead(BaseModel):
    id: int
    match_id: int
    innings_number: int
    batting_team: str
    position: int | None
    player_name: str
    cricclubs_player_id: str | None
    dismissal: str | None
    runs: int
    balls: int
    fours: int
    sixes: int
    strike_rate: float | None
    not_out: bool
    is_shauryas: bool


class ScorecardBowlingLineRead(BaseModel):
    id: int
    match_id: int
    innings_number: int
    bowling_team: str | None
    player_name: str
    cricclubs_player_id: str | None
    overs: float
    maidens: int
    dots: int
    runs_conceded: int
    wickets: int
    wides: int
    no_balls: int
    economy: float | None
    is_shauryas: bool


class MatchScorecardRead(BaseModel):
    match: MatchRead
    innings: list[ScorecardInningsRead]
    batting: list[ScorecardBattingLineRead]
    bowling: list[ScorecardBowlingLineRead]


class PlayerRead(BaseModel):
    id: int
    display_name: str
    cricclubs_player_id: str | None


class PlayerStatsRead(BaseModel):
    player_id: int
    display_name: str
    matches: int
    innings: int
    runs: int
    balls: int
    fours: int
    sixes: int
    not_outs: int
    batting_average: float | None
    strike_rate: float | None
    overs: float
    wickets: int
    runs_conceded: int
    maidens: int
    economy: float | None
    bowling_average: float | None


class CricClubsImportRequest(BaseModel):
    league_name: str
    series_name: str
    season: str | None = None
    scorecard_urls: list[HttpUrl]


class ImportResultRead(BaseModel):
    imported: int
    skipped: int
    errors: list[str]
