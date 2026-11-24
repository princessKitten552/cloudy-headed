"""Version retention: keep only the N most recent versions of a game."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import Version
from app.storage import Storage


def purge_excess_versions(db: Session, storage: Storage, game_pk: int, keep: int) -> list[int]:
    """Delete all but the `keep` newest versions of one game. Returns the deleted version ids.

    "Newest" is upload order (highest id). `keep` must be >= 1 so a purge can never wipe a game.
    Rows are removed and committed first, files afterwards: an orphan file is harmless,
    a database row pointing to a missing file is not.
    """
    if keep < 1:
        raise ValueError("keep must be >= 1")

    excess = db.execute(
        select(Version.id, Version.storage_path)
        .where(Version.game_pk == game_pk)
        .order_by(Version.id.desc())
        .offset(keep)
    ).all()
    if not excess:
        return []

    ids = [row.id for row in excess]
    db.execute(delete(Version).where(Version.id.in_(ids)))
    db.commit()
    for row in excess:
        storage.remove(row.storage_path)
    return ids
