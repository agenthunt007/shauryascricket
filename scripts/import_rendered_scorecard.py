import argparse
from pathlib import Path

from sqlmodel import Session

from app.db.session import create_db_and_tables, engine
from app.ingestion.cricclubs_parser import CricClubsScorecardParser
from app.models.domain import BattingInnings, BowlingSpell, Match
from app.repositories.cricket_repository import CricketRepository
from import_cricclubs_from_chrome import _opponent_batting_team, build_scorecard_rows


def import_rendered_scorecard(html_path: Path, source_url: str, league_name: str, series_name: str) -> str:
    create_db_and_tables()
    body = html_path.read_text()
    parser = CricClubsScorecardParser()
    parsed = parser.parse(source_url, body)

    with Session(engine) as session:
        repository = CricketRepository(session)
        league = repository.get_or_create_league(league_name)
        series = repository.get_or_create_series(league.id, series_name)
        session.commit()

        existing_match = repository.get_match_by_source_url(source_url)
        innings_rows, scorecard_batting, scorecard_bowling = build_scorecard_rows(parsed, set())
        if existing_match and repository.match_has_scorecard(existing_match.id):
            return f"skipped existing match_id={existing_match.id}"

        if existing_match:
            existing_match.raw_payload = {**(existing_match.raw_payload or {}), **parsed.raw_payload, "html": body[:250000]}
            repository.add_scorecard(existing_match.id, innings_rows, scorecard_batting, scorecard_bowling)
            session.commit()
            return f"enriched match_id={existing_match.id}"

        match = Match(
            series_id=series.id,
            source_url=source_url,
            source_match_id=parsed.source_match_id,
            played_on=parsed.played_on,
            opponent=parsed.opponent,
            venue=parsed.venue,
            result=parsed.result,
            toss=parsed.toss,
            summary=parsed.summary,
            raw_payload={**parsed.raw_payload, "html": body[:250000]},
        )

        batting = []
        for innings in parsed.innings:
            if innings.batting_team.lower() != "shauryas":
                continue
            for batter in innings.batters:
                player = repository.get_or_create_player(batter.name, batter.cricclubs_player_id)
                batting.append(
                    BattingInnings(
                        match_id=0,
                        player_id=player.id,
                        batting_position=batter.position,
                        runs=batter.runs,
                        balls=batter.balls,
                        fours=batter.fours,
                        sixes=batter.sixes,
                        dismissal=batter.dismissal,
                        not_out=batter.not_out,
                    )
                )

        bowling = []
        batting_teams = {innings.innings_number: innings.batting_team for innings in parsed.innings}
        for innings in parsed.innings:
            bowling_team = _opponent_batting_team(innings.innings_number, batting_teams)
            if (bowling_team or "").lower() != "shauryas":
                continue
            for bowler in innings.bowlers:
                player = repository.get_or_create_player(bowler.name, bowler.cricclubs_player_id)
                bowling.append(
                    BowlingSpell(
                        match_id=0,
                        player_id=player.id,
                        overs=bowler.overs,
                        maidens=bowler.maidens,
                        runs_conceded=bowler.runs_conceded,
                        wickets=bowler.wickets,
                        wides=bowler.wides,
                        no_balls=bowler.no_balls,
                    )
                )

        repository.add_match(match, batting, bowling, innings_rows, scorecard_batting, scorecard_bowling)
        session.commit()
        return (
            f"imported match_id={match.id} played_on={match.played_on} opponent={match.opponent} "
            f"batting={len(batting)} bowling={len(bowling)} innings={len(innings_rows)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True, type=Path)
    parser.add_argument("--url", required=True)
    parser.add_argument("--league", required=True)
    parser.add_argument("--series", required=True)
    args = parser.parse_args()
    print(import_rendered_scorecard(args.html, args.url, args.league, args.series), flush=True)


if __name__ == "__main__":
    main()
