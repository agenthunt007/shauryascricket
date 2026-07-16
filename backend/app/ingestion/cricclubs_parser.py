from datetime import datetime
import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from app.ingestion.schemas import ParsedBatter, ParsedBowler, ParsedInnings, ParsedScorecard
from app.models.domain import MatchResult


class CricClubsScorecardParser:
    """Best-effort parser for public CricClubs scorecards.

    CricClubs markup differs across league templates. This parser uses headings and
    table column names instead of brittle CSS chains where possible.
    """

    batting_markers = {"batter", "batsman", "runs", "balls", "4s", "6s", "sr"}
    bowling_markers = {"bowler", "overs", "maidens", "runs", "wickets", "wides", "nbs"}

    def parse(self, source_url: str, html: str) -> ParsedScorecard:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        tables = soup.find_all("table")
        batters: list[ParsedBatter] = []
        bowlers: list[ParsedBowler] = []

        for table in tables:
            headers = self._headers(table)
            normalized = {self._normalize(header) for header in headers}
            if self._looks_like_batting_table(normalized):
                batters.extend(self._parse_batting_table(table, headers))
            elif self._looks_like_bowling_table(normalized):
                bowlers.extend(self._parse_bowling_table(table, headers))

        if not batters:
            batters = self._parse_cricclubs_batting_tables(tables)
        if not bowlers:
            bowlers = self._parse_cricclubs_bowling_tables(tables)
        innings = self._parse_cricclubs_innings(soup)
        if innings:
            batters = [batter for innings_item in innings for batter in innings_item.batters]
            bowlers = [bowler for innings_item in innings for bowler in innings_item.bowlers]

        summary = self._extract_summary(soup, text)

        return ParsedScorecard(
            source_url=source_url,
            source_match_id=self._match_id_from_url(source_url),
            played_on=self._extract_date(soup, text),
            opponent=self._extract_opponent(soup, text),
            venue=self._extract_venue(soup, text),
            result=self._extract_result(summary or text),
            toss=self._extract_after_label(text, "Toss"),
            summary=summary,
            batters=batters,
            bowlers=bowlers,
            innings=innings,
            raw_payload={
                "title": soup.title.string.strip() if soup.title and soup.title.string else None,
                "scorecard_url": source_url,
                "batters_found": len(batters),
                "bowlers_found": len(bowlers),
                "innings_found": len(innings),
            },
        )

    def _parse_cricclubs_innings(self, soup: BeautifulSoup) -> list[ParsedInnings]:
        innings: list[ParsedInnings] = []
        tab_pattern = re.compile(r"^ballByBallTeam\d+$")
        for tab in soup.find_all("div", id=tab_pattern):
            batting_table = self._find_batting_table(tab)
            if not batting_table:
                continue
            innings_number = len(innings) + 1
            batting_team = self._batting_team_from_table(batting_table) or f"Innings {innings_number}"
            batters, extras, extras_detail, total_runs, total_wickets, overs = self._parse_scorecard_batting_table(
                batting_table
            )
            bowling_table = self._find_bowling_table(tab)
            bowlers = self._parse_scorecard_bowling_table(bowling_table) if bowling_table else []
            innings.append(
                ParsedInnings(
                    innings_number=innings_number,
                    batting_team=batting_team,
                    total_runs=total_runs,
                    total_wickets=total_wickets,
                    overs=overs,
                    extras=extras,
                    extras_detail=extras_detail,
                    did_not_bat=self._extract_did_not_bat(tab),
                    fall_of_wickets=self._extract_fall_of_wickets(tab),
                    batters=batters,
                    bowlers=bowlers,
                )
            )
        return innings

    def _find_batting_table(self, root):
        for table in root.find_all("table"):
            headers = " ".join(self._headers(table))
            if "innings" in self._normalize(headers) and " r " in f" {self._normalize(headers)} ":
                return table
        return None

    def _find_bowling_table(self, root):
        for table in root.find_all("table"):
            headers = " ".join(self._headers(table))
            if "bowling" in self._normalize(headers) and " o" in f" {self._normalize(headers)}":
                return table
        return None

    def _batting_team_from_table(self, table) -> str | None:
        header = " ".join(self._headers(table))
        match = re.search(r"(.+?)\s+innings", " ".join(header.split()), flags=re.IGNORECASE)
        return match.group(1).strip() if match else None

    def _parse_scorecard_batting_table(
        self, table
    ) -> tuple[list[ParsedBatter], int | None, str | None, int | None, int | None, float | None]:
        batters: list[ParsedBatter] = []
        extras = None
        extras_detail = None
        total_runs = None
        total_wickets = None
        overs = None
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(" ", strip=True)
            lower_label = label.lower()
            if lower_label.startswith("extras"):
                extras = self._safe_int(cells[2].get_text(" ", strip=True) if len(cells) > 2 else "")
                extras_detail = cells[1].get_text(" ", strip=True) if len(cells) > 1 else None
                continue
            if lower_label.startswith("total"):
                total_runs = self._safe_int(cells[2].get_text(" ", strip=True) if len(cells) > 2 else "")
                total_detail = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""
                wickets_match = re.search(r"(\d+)\s+wickets?", total_detail, flags=re.IGNORECASE)
                overs_match = re.search(r"(\d+(?:\.\d+)?)\s+overs?", total_detail, flags=re.IGNORECASE)
                total_wickets = int(wickets_match.group(1)) if wickets_match else None
                overs = self._safe_float(overs_match.group(1)) if overs_match else None
                continue
            player_link = cells[0].find("a", href=True)
            if not player_link or len(cells) < 7:
                continue
            dismissal = cells[1].get_text(" ", strip=True) if len(cells) > 1 else None
            batters.append(
                ParsedBatter(
                    name=self._clean_name(player_link.get_text(" ", strip=True).replace("*", "")),
                    position=len(batters) + 1,
                    runs=self._safe_int(cells[2].get_text(" ", strip=True)),
                    balls=self._safe_int(cells[3].get_text(" ", strip=True)),
                    fours=self._safe_int(cells[4].get_text(" ", strip=True)),
                    sixes=self._safe_int(cells[5].get_text(" ", strip=True)),
                    dismissal=dismissal,
                    not_out=bool(dismissal and "not out" in dismissal.lower()),
                    cricclubs_player_id=self._player_id(row),
                )
            )
        return batters, extras, extras_detail, total_runs, total_wickets, overs

    def _parse_scorecard_bowling_table(self, table) -> list[ParsedBowler]:
        bowlers: list[ParsedBowler] = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) < 8:
                continue
            player_cell = cells[1] if len(cells) > 1 and cells[1].find("a", href=True) else cells[0]
            player_link = player_cell.find("a", href=True)
            if not player_link:
                continue
            extras = cells[8].get_text(" ", strip=True) if len(cells) > 8 else ""
            bowlers.append(
                ParsedBowler(
                    name=self._clean_name(player_link.get_text(" ", strip=True).replace("*", "")),
                    overs=self._safe_float(cells[2].get_text(" ", strip=True)),
                    maidens=self._safe_int(cells[3].get_text(" ", strip=True)),
                    dots=self._safe_int(cells[4].get_text(" ", strip=True)),
                    runs_conceded=self._safe_int(cells[5].get_text(" ", strip=True)),
                    wickets=self._safe_int(cells[6].get_text(" ", strip=True)),
                    economy=self._safe_float(cells[7].get_text(" ", strip=True)),
                    wides=self._extract_extra_count(extras, "w"),
                    no_balls=self._extract_extra_count(extras, "nb"),
                    cricclubs_player_id=self._player_id(row),
                )
            )
        return bowlers

    def _extract_did_not_bat(self, root) -> str | None:
        for table in root.find_all("table"):
            text = table.get_text(" ", strip=True)
            if text.lower().startswith("did not bat"):
                return " ".join(text.split())
        return None

    def _extract_fall_of_wickets(self, root) -> str | None:
        heading = root.find(lambda tag: tag.name in {"h4", "h3"} and "fall of wickets" in tag.get_text(" ", strip=True).lower())
        if not heading:
            return None
        container = heading.find_parent()
        if not container:
            return None
        text = " ".join(container.get_text(" ", strip=True).split())
        return text if text.lower() != "fall of wickets" else None

    def _headers(self, table) -> list[str]:
        header_row = table.find("tr")
        if not header_row:
            return []
        return [cell.get_text(" ", strip=True) for cell in header_row.find_all(["th", "td"])]

    def _parse_batting_table(self, table, headers: list[str]) -> list[ParsedBatter]:
        rows: list[ParsedBatter] = []
        header_map = self._header_map(headers)
        for position, row in enumerate(table.find_all("tr")[1:], start=1):
            values = self._row_values(row)
            if not values:
                continue
            name = self._value(values, header_map, ["batter", "batsman", "player", "name"])
            if not name or name.lower() in {"extras", "total"}:
                continue
            dismissal = self._value(values, header_map, ["dismissal", "how out", "out"])
            rows.append(
                ParsedBatter(
                    name=self._clean_name(name),
                    position=position,
                    runs=self._int_value(values, header_map, ["runs", "r"]),
                    balls=self._int_value(values, header_map, ["balls", "b"]),
                    fours=self._int_value(values, header_map, ["4s", "4"]),
                    sixes=self._int_value(values, header_map, ["6s", "6"]),
                    dismissal=dismissal,
                    not_out=bool(dismissal and "not out" in dismissal.lower()),
                    cricclubs_player_id=self._player_id(row),
                )
            )
        return rows

    def _parse_bowling_table(self, table, headers: list[str]) -> list[ParsedBowler]:
        rows: list[ParsedBowler] = []
        header_map = self._header_map(headers)
        for row in table.find_all("tr")[1:]:
            values = self._row_values(row)
            if not values:
                continue
            name = self._value(values, header_map, ["bowler", "player", "name"])
            if not name:
                continue
            rows.append(
                ParsedBowler(
                    name=self._clean_name(name),
                    overs=self._float_value(values, header_map, ["overs", "o"]),
                    maidens=self._int_value(values, header_map, ["maidens", "m"]),
                    runs_conceded=self._int_value(values, header_map, ["runs", "r"]),
                    wickets=self._int_value(values, header_map, ["wickets", "w"]),
                    wides=self._int_value(values, header_map, ["wides", "wd"]),
                    no_balls=self._int_value(values, header_map, ["nbs", "nb", "no balls"]),
                    cricclubs_player_id=self._player_id(row),
                )
            )
        return rows

    def _looks_like_batting_table(self, headers: set[str]) -> bool:
        return bool(headers & {"batter", "batsman"}) and bool(headers & {"balls", "b"})

    def _looks_like_bowling_table(self, headers: set[str]) -> bool:
        return bool(headers & {"bowler"}) and bool(headers & {"overs", "o"})

    def _parse_cricclubs_batting_tables(self, tables) -> list[ParsedBatter]:
        batters: list[ParsedBatter] = []
        for table in tables:
            header_text = self._normalize(" ".join(self._headers(table)))
            if "innings" not in header_text or " r " not in f" {header_text} ":
                continue
            for position, row in enumerate(table.find_all("tr")[1:], start=len(batters) + 1):
                cells = row.find_all(["th", "td"])
                if len(cells) < 7:
                    continue
                first_text = cells[0].get_text(" ", strip=True)
                if first_text.lower().startswith(("extras", "total", "did not bat")):
                    continue
                player_link = cells[0].find("a", href=True)
                if not player_link:
                    continue
                name = self._clean_name(player_link.get_text(" ", strip=True).replace("*", ""))
                dismissal = cells[1].get_text(" ", strip=True) if len(cells) > 1 else None
                batters.append(
                    ParsedBatter(
                        name=name,
                        position=position,
                        runs=self._safe_int(cells[2].get_text(" ", strip=True)),
                        balls=self._safe_int(cells[3].get_text(" ", strip=True)),
                        fours=self._safe_int(cells[4].get_text(" ", strip=True)),
                        sixes=self._safe_int(cells[5].get_text(" ", strip=True)),
                        dismissal=dismissal,
                        not_out=bool(dismissal and "not out" in dismissal.lower()),
                        cricclubs_player_id=self._player_id(row),
                    )
                )
        return batters

    def _parse_cricclubs_bowling_tables(self, tables) -> list[ParsedBowler]:
        bowlers: list[ParsedBowler] = []
        for table in tables:
            headers = [self._normalize(header) for header in self._headers(table)]
            if not headers or "bowling" not in headers[0] or " o" not in f" {' '.join(headers)}":
                continue
            for row in table.find_all("tr")[1:]:
                cells = row.find_all(["th", "td"])
                if len(cells) < 8:
                    continue
                player_cell = cells[1] if len(cells) > 1 and cells[1].find("a", href=True) else cells[0]
                player_link = player_cell.find("a", href=True)
                if not player_link:
                    continue
                name = self._clean_name(player_link.get_text(" ", strip=True).replace("*", ""))
                extras = cells[8].get_text(" ", strip=True) if len(cells) > 8 else ""
                bowlers.append(
                    ParsedBowler(
                        name=name,
                        overs=self._safe_float(cells[2].get_text(" ", strip=True)),
                        maidens=self._safe_int(cells[3].get_text(" ", strip=True)),
                        runs_conceded=self._safe_int(cells[5].get_text(" ", strip=True)),
                        wickets=self._safe_int(cells[6].get_text(" ", strip=True)),
                        wides=self._extract_extra_count(extras, "w"),
                        no_balls=self._extract_extra_count(extras, "nb"),
                        cricclubs_player_id=self._player_id(row),
                    )
                )
        return bowlers

    def _header_map(self, headers: list[str]) -> dict[str, int]:
        return {self._normalize(header): index for index, header in enumerate(headers)}

    def _row_values(self, row) -> list[str]:
        return [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]

    def _value(self, values: list[str], header_map: dict[str, int], names: list[str]) -> str | None:
        for name in names:
            index = header_map.get(self._normalize(name))
            if index is not None and index < len(values):
                return values[index]
        return None

    def _int_value(self, values: list[str], header_map: dict[str, int], names: list[str]) -> int:
        value = self._value(values, header_map, names)
        if not value:
            return 0
        return self._safe_int(value)

    def _float_value(self, values: list[str], header_map: dict[str, int], names: list[str]) -> float:
        value = self._value(values, header_map, names)
        return self._safe_float(value)

    def _safe_int(self, value: str | None) -> int:
        if not value:
            return 0
        digits = "".join(character for character in value if character.isdigit())
        return int(digits) if digits else 0

    def _safe_float(self, value: str | None) -> float:
        if not value:
            return 0
        try:
            return float(value)
        except ValueError:
            return 0

    def _extract_extra_count(self, value: str, key: str) -> int:
        match = re.search(rf"(\d+)\s*{re.escape(key)}\b", value, flags=re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _normalize(self, value: str) -> str:
        return value.strip().lower().replace(".", "")

    def _clean_name(self, value: str) -> str:
        return " ".join(
            value.replace("(c)", "")
            .replace("(wk)", "")
            .replace("†", "")
            .split()
        )

    def _player_id(self, row) -> str | None:
        link = row.find("a", href=True)
        if not link:
            return None
        query = parse_qs(urlparse(link["href"]).query)
        for key in ("playerId", "playerID", "player_id"):
            if key in query:
                return query[key][0]
        return None

    def _match_id_from_url(self, url: str) -> str | None:
        query = parse_qs(urlparse(url).query)
        for key in ("matchId", "matchID", "match_id"):
            if key in query:
                return query[key][0]
        return None

    def _extract_date(self, soup: BeautifulSoup, text: str):
        summary = soup.select_one(".match-summary .ms-league-name")
        if summary:
            match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", summary.get_text(" ", strip=True))
            if match:
                return datetime.strptime(match.group(1), "%m/%d/%Y").date()
        match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
        if match:
            return datetime.strptime(match.group(1), "%m/%d/%Y").date()
        for fmt in ("%m/%d/%Y", "%d-%b-%Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:10], fmt).date()
            except ValueError:
                continue
        return None

    def _extract_after_label(self, text: str, label: str) -> str | None:
        marker = f"{label}:"
        if marker not in text:
            return None
        tail = text.split(marker, 1)[1].strip()
        return tail.split("  ", 1)[0][:120] or None

    def _extract_venue(self, soup: BeautifulSoup, text: str) -> str | None:
        venue = self._extract_after_label(text, "Venue") or self._extract_after_label(text, "Ground")
        if venue and "Grounds Documents" not in venue:
            return venue
        return None

    def _extract_opponent(self, soup: BeautifulSoup, text: str) -> str | None:
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        match = re.search(r"League:\s*(.+?)\s+vs\s+(.+?)\s+-", title, flags=re.IGNORECASE)
        if match:
            teams = [self._clean_name(match.group(1)), self._clean_name(match.group(2))]
            for team in teams:
                if team.lower() != "shauryas":
                    return team
        names = [self._clean_name(node.get_text(" ", strip=True)) for node in soup.select(".teamName")]
        for name in names:
            if name and name.lower() != "shauryas":
                return name
        if "Shauryas" not in text or " vs " not in text:
            return None
        segment = text.split(" vs ", 1)[1]
        return segment.split(" ", 8)[0][:120] or None

    def _extract_summary(self, soup: BeautifulSoup, text: str) -> str | None:
        score_top = soup.select_one(".score-top")
        if score_top:
            headings = [" ".join(heading.get_text(" ", strip=True).split()) for heading in score_top.find_all("h3")]
            for heading in reversed(headings):
                if re.search(r"\bwon by\b|\btied\b|\bno result\b", heading, flags=re.IGNORECASE):
                    return heading
        for marker in ("won by", "lost by", "Match tied", "No Result"):
            index = text.lower().find(marker.lower())
            if index >= 0:
                return text[max(0, index - 80) : index + 120].strip()
        return None

    def _extract_result(self, text: str) -> MatchResult:
        lower_text = text.lower()
        if "shauryas won" in lower_text or "shauryas win" in lower_text:
            return MatchResult.won
        if "won by" in lower_text and "shauryas won" not in lower_text:
            return MatchResult.lost
        if "shauryas lost" in lower_text:
            return MatchResult.lost
        if "tied" in lower_text:
            return MatchResult.tied
        if "no result" in lower_text:
            return MatchResult.no_result
        return MatchResult.unknown
