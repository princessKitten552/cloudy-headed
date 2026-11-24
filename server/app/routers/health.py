from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.deps import DbSession
from app.errors import api_error

router = APIRouter()


@router.get("/health")
def health(db: DbSession) -> dict[str, str]:
    """Unauthenticated liveness check (used by Docker healthcheck). Reveals nothing sensitive."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise api_error(503, "db_unavailable", "Base de données indisponible.") from exc
    return {"status": "ok", "version": __version__}
