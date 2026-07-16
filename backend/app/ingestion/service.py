from sqlmodel import Session

from app.ingestion.client import CricClubsClient
from app.ingestion.cricclubs_parser import CricClubsScorecardParser
from app.models.domain import BattingInnings, BowlingSpell, Match
from app.models.schemas import CricClubsImportRequest, ImportResultRead
from app.repositories.cricket_repository import CricketRepository


class CricClubsImportService:
    def __init__(
        self,
        session: Session,
        client: CricClubsClient,
        parser: CricClubsScorecardParser | None = None,
    ):
        self.session = session
        self.client = client
        self.parser = parser or CricClubsScorecardParser()
        self.repository = CricketRepository(session)

    async def import_scorecards(self, request: CricClubsImportRequest) -> ImportResultRead:
        league = self.repository.get_or_create_league(request.league_name)
        series = self.repository.get_or_create_series(league.id, request.series_name, request.season)
        imported = 0
        skipped = 0
        errors: list[str] = []

        for url in request.scorecard_urls:
            source_url = str(url)
            if self.repository.match_exists(source_url):
                skipped += 1
                continue
            try:
                html = await self.client.fetch_scorecard(source_url)
                parsed = self.parser.parse(source_url, html)
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
                    raw_payload={**parsed.raw_payload, "html": html[:250000]},
                )
                batting = [
                    BattingInnings(
                        match_id=0,
                        player_id=self.repository.get_or_create_player(
                            batter.name, batter.cricclubs_player_id
                        ).id,
                        batting_position=batter.position,
                        runs=batter.runs,
                        balls=batter.balls,
                        fours=batter.fours,
                        sixes=batter.sixes,
                        dismissal=batter.dismissal,
                        not_out=batter.not_out,
                    )
                    for batter in parsed.batters
                ]
                bowling = [
                    BowlingSpell(
                        match_id=0,
                        player_id=self.repository.get_or_create_player(
                            bowler.name, bowler.cricclubs_player_id
                        ).id,
                        overs=bowler.overs,
                        maidens=bowler.maidens,
                        runs_conceded=bowler.runs_conceded,
                        wickets=bowler.wickets,
                        wides=bowler.wides,
                        no_balls=bowler.no_balls,
                    )
                    for bowler in parsed.bowlers
                ]
                self.repository.add_match(match, batting, bowling)
                imported += 1
            except Exception as exc:
                errors.append(f"{source_url}: {exc}")

        self.session.commit()
        return ImportResultRead(imported=imported, skipped=skipped, errors=errors)

