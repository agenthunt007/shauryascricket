from sqlmodel import Session, select

from app.db.session import engine
from app.ingestion.cricclubs_parser import CricClubsScorecardParser
from app.models.domain import Match


def main() -> None:
    parser = CricClubsScorecardParser()
    updated = 0
    with Session(engine) as session:
        matches = session.exec(select(Match).order_by(Match.id)).all()
        for match in matches:
            html = (match.raw_payload or {}).get("html")
            if not html:
                continue
            parsed = parser.parse(match.source_url, html)
            changed = False
            if parsed.played_on and match.played_on != parsed.played_on:
                match.played_on = parsed.played_on
                changed = True
            if parsed.opponent and match.opponent != parsed.opponent:
                match.opponent = parsed.opponent
                changed = True
            if parsed.venue and match.venue != parsed.venue:
                match.venue = parsed.venue
                changed = True
            if parsed.result and match.result != parsed.result:
                match.result = parsed.result
                changed = True
            if parsed.summary and match.summary != parsed.summary:
                match.summary = parsed.summary
                changed = True
            if changed:
                updated += 1
        session.commit()
    print({"updated": updated})


if __name__ == "__main__":
    main()
