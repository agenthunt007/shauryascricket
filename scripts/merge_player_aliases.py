from collections import defaultdict

from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import engine
from app.models.domain import Player


MANUAL_ALIASES = {
    "4978052": "6063963",  # Pbr Varma -> Rohit Varma
}


def merge_player(session: Session, source: Player, target: Player) -> bool:
    if source.id == target.id:
        return False

    for table in ("battinginnings", "bowlingspell"):
        session.exec(
            text(
                f"""
                update {table} source_row
                set player_id = :target_id
                where player_id = :source_id
                  and not exists (
                    select 1
                    from {table} target_row
                    where target_row.match_id = source_row.match_id
                      and target_row.player_id = :target_id
                  )
                """
            ).bindparams(source_id=source.id, target_id=target.id)
        )
        session.exec(
            text(
                f"""
                delete from {table} source_row
                where player_id = :source_id
                  and exists (
                    select 1
                    from {table} target_row
                    where target_row.match_id = source_row.match_id
                      and target_row.player_id = :target_id
                  )
                """
            ).bindparams(source_id=source.id, target_id=target.id)
        )

    session.delete(source)
    return True


def display_name_rank(player: Player) -> tuple[int, str]:
    name = player.display_name.lower()
    return (1 if "†" in name else 0, name)


def main() -> None:
    merged = 0
    with Session(engine) as session:
        players = session.exec(select(Player).order_by(Player.id)).all()
        by_cricclubs_id: dict[str, list[Player]] = defaultdict(list)
        for player in players:
            if player.cricclubs_player_id:
                by_cricclubs_id[player.cricclubs_player_id].append(player)

        for grouped_players in by_cricclubs_id.values():
            if len(grouped_players) < 2:
                continue
            target = sorted(grouped_players, key=display_name_rank)[0]
            for source in grouped_players:
                if merge_player(session, source, target):
                    merged += 1

        session.flush()
        for source_cricclubs_id, target_cricclubs_id in MANUAL_ALIASES.items():
            source = session.exec(
                select(Player).where(Player.cricclubs_player_id == source_cricclubs_id)
            ).first()
            target = session.exec(
                select(Player).where(Player.cricclubs_player_id == target_cricclubs_id)
            ).first()
            if source and target and merge_player(session, source, target):
                merged += 1

        session.commit()
    print({"merged": merged})


if __name__ == "__main__":
    main()
