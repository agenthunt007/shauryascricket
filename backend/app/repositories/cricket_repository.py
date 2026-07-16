from typing import Iterable

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.domain import (
    BattingInnings,
    BowlingSpell,
    League,
    Match,
    Player,
    ScorecardBattingLine,
    ScorecardBowlingLine,
    ScorecardInnings,
    Series,
)


CRICCLUBS_PLAYER_ID_ALIASES = {
    "4978052": "6063963",  # Pbr Varma -> Rohit Varma
}

CANONICAL_PLAYER_NAMES = {
    "4978038": "Sarath Chaganti",
    "6063963": "Rohit Varma",
}


class CricketRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_league(self, name: str) -> League:
        league = self.session.exec(select(League).where(League.name == name)).first()
        if league:
            return league
        league = League(name=name)
        self.session.add(league)
        self.session.flush()
        return league

    def get_or_create_series(self, league_id: int, name: str, season: str | None = None) -> Series:
        series = self.session.exec(
            select(Series).where(Series.league_id == league_id, Series.name == name)
        ).first()
        if series:
            return series
        series = Series(league_id=league_id, name=name, season=season)
        self.session.add(series)
        self.session.flush()
        return series

    def get_or_create_player(self, display_name: str, cricclubs_player_id: str | None = None) -> Player:
        if cricclubs_player_id:
            cricclubs_player_id = CRICCLUBS_PLAYER_ID_ALIASES.get(cricclubs_player_id, cricclubs_player_id)
            display_name = CANONICAL_PLAYER_NAMES.get(cricclubs_player_id, display_name)
        if cricclubs_player_id:
            player = self.session.exec(
                select(Player).where(Player.cricclubs_player_id == cricclubs_player_id)
            ).first()
            if player:
                if player.display_name != display_name and cricclubs_player_id in CANONICAL_PLAYER_NAMES:
                    player.display_name = display_name
                return player
        player = self.session.exec(select(Player).where(Player.display_name == display_name)).first()
        if player:
            if cricclubs_player_id and not player.cricclubs_player_id:
                player.cricclubs_player_id = cricclubs_player_id
            return player
        player = Player(display_name=display_name, cricclubs_player_id=cricclubs_player_id)
        self.session.add(player)
        self.session.flush()
        return player

    def match_exists(self, source_url: str) -> bool:
        return self.session.exec(select(Match.id).where(Match.source_url == source_url)).first() is not None

    def get_match_by_source_url(self, source_url: str) -> Match | None:
        return self.session.exec(select(Match).where(Match.source_url == source_url)).first()

    def match_has_scorecard(self, match_id: int) -> bool:
        return (
            self.session.exec(select(ScorecardInnings.id).where(ScorecardInnings.match_id == match_id)).first()
            is not None
        )

    def add_match(
        self,
        match: Match,
        batting: Iterable[BattingInnings],
        bowling: Iterable[BowlingSpell],
        innings: Iterable[ScorecardInnings] = (),
        scorecard_batting: Iterable[ScorecardBattingLine] = (),
        scorecard_bowling: Iterable[ScorecardBowlingLine] = (),
    ) -> Match:
        self.session.add(match)
        self.session.flush()
        for batting_innings in batting:
            batting_innings.match_id = match.id
            self.session.add(batting_innings)
        for spell in bowling:
            spell.match_id = match.id
            self.session.add(spell)
        self.add_scorecard(match.id, innings, scorecard_batting, scorecard_bowling)
        return match

    def add_scorecard(
        self,
        match_id: int,
        innings: Iterable[ScorecardInnings],
        scorecard_batting: Iterable[ScorecardBattingLine],
        scorecard_bowling: Iterable[ScorecardBowlingLine],
    ) -> None:
        for innings_item in innings:
            innings_item.match_id = match_id
            self.session.add(innings_item)
        for line in scorecard_batting:
            line.match_id = match_id
            self.session.add(line)
        for line in scorecard_bowling:
            line.match_id = match_id
            self.session.add(line)

    def list_leagues(self) -> list[League]:
        return list(self.session.exec(select(League).order_by(League.name)).all())

    def list_series(self, league_id: int | None = None) -> list[Series]:
        statement = select(Series).order_by(Series.name)
        if league_id:
            statement = statement.where(Series.league_id == league_id)
        return list(self.session.exec(statement).all())

    def list_matches(self, league_id: int | None = None, series_id: int | None = None) -> list[Match]:
        statement = select(Match).order_by(Match.played_on.desc(), Match.id.desc())
        if series_id:
            statement = statement.where(Match.series_id == series_id)
        elif league_id:
            statement = statement.join(Series).where(Series.league_id == league_id)
        return list(self.session.exec(statement).all())

    def get_match(self, match_id: int) -> Match | None:
        return self.session.get(Match, match_id)

    def list_scorecard_innings(self, match_id: int) -> list[ScorecardInnings]:
        statement = (
            select(ScorecardInnings)
            .where(ScorecardInnings.match_id == match_id)
            .order_by(ScorecardInnings.innings_number)
        )
        return list(self.session.exec(statement).all())

    def list_scorecard_batting(self, match_id: int) -> list[ScorecardBattingLine]:
        statement = (
            select(ScorecardBattingLine)
            .where(ScorecardBattingLine.match_id == match_id)
            .order_by(ScorecardBattingLine.innings_number, ScorecardBattingLine.position)
        )
        return list(self.session.exec(statement).all())

    def list_scorecard_bowling(self, match_id: int) -> list[ScorecardBowlingLine]:
        statement = (
            select(ScorecardBowlingLine)
            .where(ScorecardBowlingLine.match_id == match_id)
            .order_by(ScorecardBowlingLine.innings_number, ScorecardBowlingLine.player_name)
        )
        return list(self.session.exec(statement).all())

    def list_players(self) -> list[Player]:
        return list(self.session.exec(select(Player).order_by(Player.display_name)).all())

    def count_matches_by_player(self, player_id: int, series_id: int | None = None) -> int:
        statement = select(func.count(func.distinct(BattingInnings.match_id))).where(
            BattingInnings.player_id == player_id
        )
        if series_id:
            statement = statement.join(Match).where(Match.series_id == series_id)
        return int(self.session.exec(statement).one())
