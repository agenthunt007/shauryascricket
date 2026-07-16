from datetime import date

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
    assert stats[0].last_played is None
    assert stats[0].strike_rate == 150
    assert stats[0].wickets == 2
    assert stats[0].economy == 5


def test_player_records_use_each_players_recent_match_window():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        league = League(name="Houston United Premier League")
        session.add(league)
        session.flush()
        series = Series(league_id=league.id, name="Summer")
        batter = Player(display_name="Batter")
        bowler = Player(display_name="Bowler")
        teammate = Player(display_name="Teammate")
        session.add(series)
        session.add(batter)
        session.add(bowler)
        session.add(teammate)
        session.flush()

        for index, runs in enumerate([1, 2, 3, 4, 5, 6, 10, 40], start=1):
            match = Match(
                series_id=series.id,
                source_url=f"https://example.test/match-{index}",
                played_on=date(2026, 1, index),
            )
            session.add(match)
            session.flush()
            session.add(BattingInnings(match_id=match.id, player_id=batter.id, runs=runs, balls=20))
            session.add(BowlingSpell(match_id=match.id, player_id=bowler.id, overs=4, runs_conceded=20, wickets=index))

        for index in [9, 10]:
            match = Match(
                series_id=series.id,
                source_url=f"https://example.test/match-{index}",
                played_on=date(2026, 1, index),
            )
            session.add(match)
            session.flush()
            session.add(BattingInnings(match_id=match.id, player_id=teammate.id, runs=20, balls=20))
        session.commit()

        records = StatsService(session).player_records(StatsFilters(series_id=series.id), match_limit=2)

    assert records.match_limit == 2
    assert records.batting[0].display_name == "Batter"
    assert records.batting[0].last_played == date(2026, 1, 8)
    assert records.batting[0].recent_scores == ["10", "40"]
    assert records.batting[0].runs == 50
    assert records.batting[0].matches == 2
    assert all(player.display_name != "Teammate" for player in records.batting)
    assert records.bowling[0].display_name == "Bowler"
    assert records.bowling[0].last_played == date(2026, 1, 8)
    assert records.bowling[0].wickets == 15
