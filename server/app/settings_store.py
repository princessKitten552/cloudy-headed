"""Server-side settings shared by every machine (stored in SQLite)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db import Setting

MAX_VERSIONS_KEY = "max_versions"
MAX_VERSIONS_LIMIT = 1000


def read_max_versions(db: Session, default: int) -> int:
    row = db.get(Setting, MAX_VERSIONS_KEY)
    if row is None:
        return default
    try:
        return int(row.value)
    except ValueError:
        return default


def write_max_versions(db: Session, value: int) -> None:
    db.merge(Setting(key=MAX_VERSIONS_KEY, value=str(value)))
    db.commit()
