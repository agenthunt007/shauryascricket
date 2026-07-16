from sqlmodel import Session, SQLModel, create_engine

from app.models.domain import BattingInnings, BowlingSpell, League, Match, Player, Series
from app.services.stats_service import StatsFilters, StatsService


def test_player_stats_aggregates_batting_and_bowling():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        league = League(name="Houston Cricket League")
        session.add(league)
        session.flush()
        series = Series(league_id=league.id, name="Spring")
        player = Player(display_name="Shaurya")
        session.add(series)
        session.add(player)
        session.flush()
        match = Match(series_id=series.id, source_url="https://example.test/match")
        session.add(match)
        session.flush()
        session.add(BattingInnings(match_id=match.id, player_id=player.id, runs=45, balls=30, fours=4, sixes=2))
        session.add(BowlingSpell(match_id=match.id, player_id=player.id, overs=4, runs_conceded=20, wickets=2))
        session.commit()

        stats = StatsService(session).player_stats(StatsFilters(series_id=series.id))

    assert len(stats) == 1
    assert stats[0].runs == 45
    assert stats[0].strike_rate == 150
    assert stats[0].wickets == 2
    assert stats[0].economy == 5

