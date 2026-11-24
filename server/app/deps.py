"""FastAPI dependencies: settings, DB session, storage, auth, game_id validation."""

from __future__ import annotations

import hmac
import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import api_error
from app.storage import Storage
from app.validation import InvalidGameId, validate_game_id

log = logging.getLogger("savesync.auth")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def require_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Static bearer token, compared in constant time."""
    expected: str = request.app.state.settings.api_token
    scheme, _, supplied = (authorization or "").partition(" ")
    candidate = supplied.strip() if scheme.lower() == "bearer" else ""
    if not hmac.compare_digest(candidate.encode("utf-8"), expected.encode("utf-8")):
        client = request.client.host if request.client else "unknown"
        log.warning("Rejected request with missing/invalid token from %s", client)
        raise api_error(
            401,
            "invalid_token",
            "Jeton d'API manquant ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def valid_game_id(game_id: str) -> str:
    try:
        return validate_game_id(game_id)
    except InvalidGameId as exc:
        raise api_error(400, "invalid_game_id", str(exc)) from exc


GameId = Annotated[str, Depends(valid_game_id)]
DbSession = Annotated[Session, Depends(get_db)]
StorageDep = Annotated[Storage, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
