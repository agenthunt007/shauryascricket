from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.db.session import get_session
from app.models.schemas import (
    LeagueRead,
    MatchRead,
    MatchScorecardRead,
    PlayerRead,
    PlayerRecordsRead,
    PlayerStatsRead,
    SeriesRead,
)
from app.repositories.cricket_repository import CricketRepository
from app.services.stats_service import StatsFilters, StatsService

router = APIRouter(prefix="/api", tags=["cricket"])


@router.get("/leagues", response_model=list[LeagueRead])
def list_leagues(session: Session = Depends(get_session)):
    return CricketRepository(session).list_leagues()


@router.get("/series", response_model=list[SeriesRead])
def list_series(
    league_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return CricketRepository(session).list_series(league_id=league_id)


@router.get("/matches", response_model=list[MatchRead])
def list_matches(
    league_id: int | None = Query(default=None),
    series_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return CricketRepository(session).list_matches(league_id=league_id, series_id=series_id)


@router.get("/matches/{match_id}/scorecard", response_model=MatchScorecardRead)
def match_scorecard(match_id: int, session: Session = Depends(get_session)):
    repository = CricketRepository(session)
    match = repository.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return {
        "match": match,
        "innings": repository.list_scorecard_innings(match_id),
        "batting": repository.list_scorecard_batting(match_id),
        "bowling": repository.list_scorecard_bowling(match_id),
    }


@router.get("/players", response_model=list[PlayerRead])
def list_players(session: Session = Depends(get_session)):
    return CricketRepository(session).list_players()


@router.get("/stats/players", response_model=list[PlayerStatsRead])
def player_stats(
    league_id: int | None = Query(default=None),
    series_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return StatsService(session).player_stats(StatsFilters(league_id=league_id, series_id=series_id))


@router.get("/stats/player-records", response_model=PlayerRecordsRead)
def player_records(
    league_id: int | None = Query(default=None),
    series_id: int | None = Query(default=None),
    match_limit: int = Query(default=7, ge=1, le=50),
    session: Session = Depends(get_session),
):
    return StatsService(session).player_records(
        StatsFilters(league_id=league_id, series_id=series_id),
        match_limit=match_limit,
    )
