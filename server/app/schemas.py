"""Pydantic response/request models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db import Game, Version
from app.settings_store import MAX_VERSIONS_LIMIT


class VersionOut(BaseModel):
    id: int
    game_id: str
    sha256: str
    size_bytes: int
    modified_at: datetime
    uploaded_at: datetime
    machine: str


class GameOut(BaseModel):
    game_id: str
    steam_app_id: int | None
    version_count: int
    latest_version: VersionOut | None


class SettingsModel(BaseModel):
    max_versions: int = Field(ge=1, le=MAX_VERSIONS_LIMIT)


def version_out(version: Version, game_id: str) -> VersionOut:
    return VersionOut(
        id=version.id,
        game_id=game_id,
        sha256=version.sha256,
        size_bytes=version.size_bytes,
        modified_at=version.modified_at,
        uploaded_at=version.uploaded_at,
        machine=version.machine,
    )


def game_out(game: Game) -> GameOut:
    latest = game.versions[0] if game.versions else None  # relationship is ordered newest first
    return GameOut(
        game_id=game.game_id,
        steam_app_id=game.steam_app_id,
        version_count=len(game.versions),
        latest_version=version_out(latest, game.game_id) if latest else None,
    )
