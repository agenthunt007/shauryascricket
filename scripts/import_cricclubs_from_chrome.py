import asyncio
import html
import json
import re
import time
import urllib.request
from urllib.parse import urljoin, urlparse

import websockets
from bs4 import BeautifulSoup
from sqlmodel import Session

from app.db.session import create_db_and_tables, engine
from app.ingestion.cricclubs_parser import CricClubsScorecardParser
from app.models.domain import (
    BattingInnings,
    BowlingSpell,
    Match,
    ScorecardBattingLine,
    ScorecardBowlingLine,
    ScorecardInnings,
)
from app.repositories.cricket_repository import CricketRepository


TEAM_PAGES = {
    "HoustonPremierT20League": {
        "league": "Houston Premier T20 League",
        "series": "HPT20L_SERIES_24",
        "url": "https://cricclubs.com/HoustonPremierT20League/teamResults.do?teamId=666&clubId=1366",
    },
    "HoustonPremierT20League_2023": {
        "league": "Houston Premier T20 League",
        "series": "HPT20L_SERIES_23",
        "url": "https://cricclubs.com/HoustonPremierT20League/teamResults.do?teamId=655&clubId=1366",
    },
    "HoustonUnitedPremierLeague_S12D4": {
        "league": "Houston United Premier League",
        "series": "Challenger Division (S12D4)",
        "url": "https://cricclubs.com/HoustonUnitedPremierLeague/teamResults.do?teamId=333&clubId=13647",
    },
    "HoustonUnitedPremierLeague_Practice": {
        "league": "Houston United Premier League",
        "series": "HUPL Practice Games",
        "url": "https://cricclubs.com/HoustonUnitedPremierLeague/teamResults.do?teamId=301&clubId=13647",
    },
    "HoustonUnitedPremierLeague_S11D5": {
        "league": "Houston United Premier League",
        "series": "Contender Division (S11D5)",
        "url": "https://cricclubs.com/HoustonUnitedPremierLeague/teamResults.do?teamId=296&clubId=13647",
    },
    "HTBC": {
        "league": "Houston Taped Ball Cricket",
        "series": "Division I",
        "url": "https://cricclubs.com/HTBC/teamResults.do?teamId=119&clubId=8755",
    },
    "SSCLHouston_S27D3": {
        "league": "Saturday Super Cricket League - Houston",
        "series": "S27 - Division III",
        "url": "https://cricclubs.com/SSCLHouston/teamResults.do?teamId=840&clubId=4110",
    },
    "SSCLHouston_S26": {
        "league": "Saturday Super Cricket League - Houston",
        "series": "CRICHUB SSCL 26 - SPRING 2026",
        "url": "https://cricclubs.com/SSCLHouston/teamResults.do?teamId=754&clubId=4110",
    },
    "SSCLHouston_S25": {
        "league": "Saturday Super Cricket League - Houston",
        "series": "SIMPLEX LENDING SSCL 25 - SUMMER 2025",
        "url": "https://cricclubs.com/SSCLHouston/teamResults.do?teamId=663&clubId=4110",
    },
    "TCC_Fall2025D2": {
        "league": "Triggers Tapedball Cricket League",
        "series": "Fall 2025 Divn II",
        "url": "https://cricclubs.com/3T/teamResults.do?teamId=1293&clubId=8675",
    },
}


def chrome_json(path: str):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:9222{path}"))


def open_tab(url: str) -> None:
    request = urllib.request.Request(f"http://127.0.0.1:9222/json/new?{url}", method="PUT")
    urllib.request.urlopen(request).read()


def close_tab(page_id: str) -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9222/json/close/{page_id}").read()
    except Exception:
        pass


async def page_html(page: dict) -> str:
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "document.documentElement.outerHTML",
                        "returnByValue": True,
                    },
                }
            )
        )
        while True:
            message = json.loads(await ws.recv())
            if message.get("id") == 1:
                return message["result"]["result"].get("value", "")


async def rendered_html_for_url(url: str, timeout_seconds: int = 45, close_when_done: bool = True) -> str | None:
    existing_page_id = None
    for page in chrome_json("/json"):
        if page.get("type") == "page" and _same_cricclubs_page(page.get("url", ""), url):
            existing_page_id = page.get("id")
            body = await page_html(page)
            if "Just a moment" not in body and _is_expected_page(url, body):
                return body
    open_tab(url)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        pages = chrome_json("/json")
        for page in pages:
            if page.get("type") == "page" and _same_cricclubs_page(page.get("url", ""), url) and page.get("title"):
                body = await page_html(page)
                if "Just a moment" not in body and _is_expected_page(url, body):
                    if close_when_done and page.get("id") != existing_page_id:
                        close_tab(page["id"])
                    return body
        time.sleep(1)
    return None


def _is_expected_page(url: str, body: str) -> bool:
    if "teamResults.do" in url:
        return "viewScorecard.do" in body or "match" in body.lower()
    if "viewScorecard.do" in url:
        return "scorecard-inner" in body or "match-table-innings" in body
    return True


def _same_cricclubs_page(actual_url: str, expected_url: str) -> bool:
    actual = urlparse(actual_url)
    expected = urlparse(expected_url)
    if actual.netloc != expected.netloc or actual.path != expected.path:
        return False
    actual_query = parse_query(actual.query)
    expected_query = parse_query(expected.query)
    for key in ("matchId", "teamId"):
        if key in expected_query and actual_query.get(key) == expected_query[key]:
            return True
    return actual_url == expected_url


def parse_query(query: str) -> dict[str, str]:
    pairs = {}
    for part in query.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        pairs[key] = value
    return pairs


async def collect_rendered_pages() -> dict[str, str]:
    pages = [
        page
        for page in chrome_json("/json")
        if page.get("type") == "page" and "cricclubs.com" in page.get("url", "")
    ]
    html_by_url = await asyncio.gather(*(page_html(page) for page in pages))
    return {page["url"]: body for page, body in zip(pages, html_by_url)}


def discover_scorecards(rendered_pages: dict[str, str]) -> list[str]:
    scorecards: set[str] = set()
    for url, body in rendered_pages.items():
        if "teamResults.do" not in url:
            continue
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        for link in re.findall(r"""href=["']([^"']*viewScorecard\.do[^"']+)""", body):
            scorecards.add(urljoin(base, html.unescape(link)))
    return sorted(scorecards)


def discover_scorecards_from_page(url: str, body: str) -> list[str]:
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    soup = BeautifulSoup(body, "html.parser")
    scorecards = set()
    for link in soup.find_all("a", href=re.compile(r"viewScorecard\.do")):
        href = link.get("href")
        if href:
            scorecards.add(urljoin(base, html.unescape(href)))
    return sorted(scorecards)


def discover_shauryas_scorecards_from_page(url: str, body: str) -> list[str]:
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    soup = BeautifulSoup(body, "html.parser")
    scorecards = set()
    for link in soup.find_all("a", href=re.compile(r"viewScorecard\.do")):
        container = link.find_parent(class_=re.compile(r"team-vs-team|match|list|score", re.IGNORECASE))
        text = container.get_text(" ", strip=True) if container else link.get_text(" ", strip=True)
        if "shauryas" not in text.lower():
            continue
        href = link.get("href")
        if href:
            scorecards.add(urljoin(base, html.unescape(href)))
    return sorted(scorecards)


def shauryas_roster(rendered_pages: dict[str, str]) -> set[str]:
    names: set[str] = set()
    for url, body in rendered_pages.items():
        if "viewTeam.do" not in url and "teamResults.do" not in url:
            continue
        soup = BeautifulSoup(body, "html.parser")
        for heading in soup.find_all("h4"):
            if not heading.find_next("a", href=re.compile(r"viewPlayer\.do")):
                print(f"missing rendered body: {url}")
                continue
            name = " ".join(heading.get_text(" ", strip=True).replace("*", "").split())
            name = re.sub(r"\b(Verified|Not Verified)\b", "", name).strip()
            if name and "..." not in name:
                names.add(name)
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2 or "Shauryas" not in row.get_text(" ", strip=True):
                continue
            first_link = row.find("a", href=re.compile(r"viewPlayer\.do"))
            if first_link:
                name = " ".join(first_link.get_text(" ", strip=True).replace("*", "").split())
                if name and name.lower() != "view profile":
                    names.add(name)
    return names


def league_config_for_url(url: str) -> dict:
    slug = urlparse(url).path.strip("/").split("/", 1)[0]
    return TEAM_PAGES[slug]


def build_scorecard_rows(parsed, roster: set[str]):
    innings_rows = []
    batting_rows = []
    bowling_rows = []
    batting_teams = {innings.innings_number: innings.batting_team for innings in parsed.innings}
    for innings in parsed.innings:
        bowling_team = _opponent_batting_team(innings.innings_number, batting_teams)
        innings_rows.append(
            ScorecardInnings(
                match_id=0,
                innings_number=innings.innings_number,
                batting_team=innings.batting_team,
                total_runs=innings.total_runs,
                total_wickets=innings.total_wickets,
                overs=innings.overs,
                extras=innings.extras,
                extras_detail=innings.extras_detail,
                did_not_bat=innings.did_not_bat,
                fall_of_wickets=innings.fall_of_wickets,
            )
        )
        for batter in innings.batters:
            batting_rows.append(
                ScorecardBattingLine(
                    match_id=0,
                    innings_number=innings.innings_number,
                    batting_team=innings.batting_team,
                    position=batter.position,
                    player_name=batter.name,
                    cricclubs_player_id=batter.cricclubs_player_id,
                    dismissal=batter.dismissal,
                    runs=batter.runs,
                    balls=batter.balls,
                    fours=batter.fours,
                    sixes=batter.sixes,
                    strike_rate=round((batter.runs / batter.balls) * 100, 2) if batter.balls else None,
                    not_out=batter.not_out,
                    is_shauryas=innings.batting_team.lower() == "shauryas" or batter.name in roster,
                )
            )
        for bowler in innings.bowlers:
            bowling_rows.append(
                ScorecardBowlingLine(
                    match_id=0,
                    innings_number=innings.innings_number,
                    bowling_team=bowling_team,
                    player_name=bowler.name,
                    cricclubs_player_id=bowler.cricclubs_player_id,
                    overs=bowler.overs,
                    maidens=bowler.maidens,
                    dots=bowler.dots,
                    runs_conceded=bowler.runs_conceded,
                    wickets=bowler.wickets,
                    wides=bowler.wides,
                    no_balls=bowler.no_balls,
                    economy=bowler.economy,
                    is_shauryas=(bowling_team or "").lower() == "shauryas" or bowler.name in roster,
                )
            )
    return innings_rows, batting_rows, bowling_rows


def _opponent_batting_team(innings_number: int, batting_teams: dict[int, str]) -> str | None:
    for other_innings_number, team in batting_teams.items():
        if other_innings_number != innings_number:
            return team
    return None


async def main() -> None:
    create_db_and_tables()
    parser = CricClubsScorecardParser()

    imported = 0
    skipped = 0
    enriched = 0
    failed = 0
    with Session(engine) as session:
        repository = CricketRepository(session)
        for config in TEAM_PAGES.values():
            print(f"league start: {config['league']}", flush=True)
            team_body = await rendered_html_for_url(config["url"])
            if not team_body:
                print(f"league failed: {config['league']} no team results page", flush=True)
                continue
            if config.get("filter_shauryas"):
                scorecards = discover_shauryas_scorecards_from_page(config["url"], team_body)
            else:
                scorecards = discover_scorecards_from_page(config["url"], team_body)
            roster = shauryas_roster({config["url"]: team_body})
            league = repository.get_or_create_league(config["league"])
            series = repository.get_or_create_series(league.id, config["series"])
            session.commit()
            print(f"league scorecards: {config['league']} count={len(scorecards)} roster={len(roster)}", flush=True)
            for index, url in enumerate(scorecards, start=1):
                print(f"match start: {config['league']} {index}/{len(scorecards)} {url}", flush=True)
                existing_match = repository.get_match_by_source_url(url)
                if existing_match and repository.match_has_scorecard(existing_match.id):
                    skipped += 1
                    print("match skipped: scorecard already saved", flush=True)
                    continue
                body = await rendered_html_for_url(url)
                if not body:
                    failed += 1
                    print("match failed: rendered body unavailable", flush=True)
                    continue
                parsed = parser.parse(url, body)
                innings_rows, scorecard_batting, scorecard_bowling = build_scorecard_rows(parsed, roster)
                if not innings_rows and not parsed.batters and not parsed.bowlers:
                    failed += 1
                    print("match failed: no scorecard rows parsed", flush=True)
                    continue
                if existing_match:
                    existing_match.raw_payload = {**(existing_match.raw_payload or {}), **parsed.raw_payload, "html": body[:250000]}
                    repository.add_scorecard(existing_match.id, innings_rows, scorecard_batting, scorecard_bowling)
                    session.commit()
                    enriched += 1
                    print(
                        f"match enriched: innings={len(innings_rows)} batting={len(scorecard_batting)} bowling={len(scorecard_bowling)}",
                        flush=True,
                    )
                    continue
                match = Match(
                    series_id=series.id,
                    source_url=url,
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
                imported += 1
                print(
                    f"match imported: stats_batting={len(batting)} stats_bowling={len(bowling)} "
                    f"innings={len(innings_rows)} scorecard_batting={len(scorecard_batting)} "
                    f"scorecard_bowling={len(scorecard_bowling)}",
                    flush=True,
                )
    print(json.dumps({"imported": imported, "enriched": enriched, "skipped": skipped, "failed": failed}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
