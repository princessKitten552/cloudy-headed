from __future__ import annotations

import logging
import re
import zipfile
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import Game, Version, utcnow
from app.deps import DbSession, GameId, SettingsDep, StorageDep, require_token
from app.errors import api_error
from app.schemas import GameOut, VersionOut, game_out, version_out
from app.storage import StorageError, UploadTooLarge
from app.validation import validate_machine

log = logging.getLogger("savesync.games")

router = APIRouter(dependencies=[Depends(require_token)])

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _find_game(db: Session, game_id: str) -> Game | None:
    return db.scalar(select(Game).where(Game.game_id == game_id))


def _game_or_404(db: Session, game_id: str) -> Game:
    game = _find_game(db, game_id)
    if game is None:
        raise api_error(404, "game_not_found", "Jeu inconnu sur le serveur.")
    return game


def _get_or_create_game(db: Session, game_id: str, steam_app_id: int | None) -> Game:
    game = _find_game(db, game_id)
    if game is None:
        game = Game(game_id=game_id, steam_app_id=steam_app_id)
        db.add(game)
        try:
            db.flush()
        except IntegrityError:
            # A concurrent upload created the same game first.
            db.rollback()
            game = _find_game(db, game_id)
            if game is None:
                raise
    if steam_app_id is not None and game.steam_app_id != steam_app_id:
        game.steam_app_id = steam_app_id
    return game


@router.get("/games", response_model=list[GameOut])
def list_games(db: DbSession) -> list[GameOut]:
    games = db.scalars(
        select(Game).options(selectinload(Game.versions)).order_by(Game.game_id)
    ).all()
    return [game_out(g) for g in games]


@router.post("/games/{game_id}/upload", response_model=VersionOut, status_code=201)
def upload_version(
    game_id: GameId,
    archive: Annotated[UploadFile, File()],
    sha256: Annotated[str, Form()],
    modified_at: Annotated[datetime, Form()],
    machine: Annotated[str, Form()],
    db: DbSession,
    storage: StorageDep,
    settings: SettingsDep,
    steam_app_id: Annotated[int | None, Form(ge=1)] = None,
) -> VersionOut:
    expected_sha = sha256.strip().lower()
    if not _SHA256_RE.match(expected_sha):
        raise api_error(422, "invalid_sha256", "Le sha256 doit contenir 64 caractères hexadécimaux.")
    if modified_at.tzinfo is None:
        raise api_error(
            422, "invalid_modified_at", "La date de modification doit inclure un fuseau horaire."
        )
    modified_at = modified_at.astimezone(UTC)
    try:
        machine = validate_machine(machine)
    except ValueError as exc:
        raise api_error(422, "invalid_machine", "Nom de machine invalide.") from exc

    try:
        stored = storage.save_stream(archive.file, settings.max_upload_bytes)
    except UploadTooLarge as exc:
        raise api_error(413, "payload_too_large", "Archive trop volumineuse pour ce serveur.") from exc

    rel_path: str | None = None
    try:
        if stored.size == 0:
            raise api_error(422, "empty_archive", "L'archive reçue est vide.")
        if stored.sha256 != expected_sha:
            log.warning("Hash mismatch on upload for %r from %s", game_id, machine)
            raise api_error(
                422,
                "hash_mismatch",
                "Le sha256 reçu ne correspond pas à l'archive : transfert corrompu.",
            )
        if not zipfile.is_zipfile(stored.path):
            raise api_error(422, "invalid_archive", "L'archive reçue n'est pas un fichier zip valide.")

        try:
            game = _get_or_create_game(db, game_id, steam_app_id)
            version = Version(
                game_pk=game.id,
                sha256=stored.sha256,
                size_bytes=stored.size,
                modified_at=modified_at,
                uploaded_at=utcnow(),
                machine=machine,
                storage_path="",
            )
            db.add(version)
            db.flush()  # assigns version.id, needed for the file name
            rel_path = storage.promote(stored.path, game_id, version.id)
            version.storage_path = rel_path
            db.commit()
        except BaseException:
            db.rollback()
            if rel_path is not None:
                storage.remove(rel_path)
            raise
    finally:
        stored.path.unlink(missing_ok=True)

    log.info("Stored version %d of %r (%d bytes) from %s", version.id, game_id, stored.size, machine)
    return version_out(version, game_id)


@router.get("/games/{game_id}/versions", response_model=list[VersionOut])
def list_versions(game_id: GameId, db: DbSession) -> list[VersionOut]:
    game = _game_or_404(db, game_id)
    versions = db.scalars(
        select(Version).where(Version.game_pk == game.id).order_by(Version.id.desc())
    ).all()
    return [version_out(v, game.game_id) for v in versions]


@router.get("/games/{game_id}/download")
def download_version(
    game_id: GameId,
    db: DbSession,
    storage: StorageDep,
    version: Annotated[str, Query()] = "latest",
) -> FileResponse:
    game = _game_or_404(db, game_id)

    if version == "latest":
        found = db.scalar(
            select(Version).where(Version.game_pk == game.id).order_by(Version.id.desc()).limit(1)
        )
    else:
        try:
            version_id = int(version)
        except ValueError as exc:
            raise api_error(
                422, "invalid_version", "Le paramètre version doit valoir 'latest' ou un identifiant."
            ) from exc
        found = db.get(Version, version_id)
        if found is not None and found.game_pk != game.id:
            found = None
    if found is None:
        raise api_error(404, "version_not_found", "Version introuvable pour ce jeu.")

    try:
        path = storage.resolve(found.storage_path)
    except StorageError as exc:
        log.error("%s", exc)
        raise api_error(500, "storage_error", "Erreur interne de stockage.") from exc
    if not path.is_file():
        log.error("Archive file missing on disk for version %d (%s)", found.id, found.storage_path)
        raise api_error(410, "archive_missing", "Le fichier d'archive est introuvable sur le serveur.")

    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"savesync-v{found.id}.zip",
        headers={"X-Content-SHA256": found.sha256, "X-Version-Id": str(found.id)},
    )


@router.delete("/games/{game_id}/versions/{version_id}", status_code=204)
def delete_version(game_id: GameId, version_id: int, db: DbSession, storage: StorageDep) -> Response:
    game = _game_or_404(db, game_id)
    version = db.get(Version, version_id)
    if version is None or version.game_pk != game.id:
        raise api_error(404, "version_not_found", "Version introuvable pour ce jeu.")

    rel_path = version.storage_path
    db.delete(version)
    db.flush()
    remaining = db.scalar(select(func.count()).select_from(Version).where(Version.game_pk == game.id))
    if remaining == 0:
        db.delete(game)  # a game without versions is simply "never backed up"
    db.commit()
    # Remove the file only after the DB commit: an orphan file is harmless, a dangling row is not.
    storage.remove(rel_path)
    log.info("Deleted version %d of %r", version_id, game_id)
    return Response(status_code=204)
