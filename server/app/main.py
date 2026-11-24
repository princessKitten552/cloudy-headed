"""Application factory. Run with: uvicorn app.main:create_app --factory"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from app import __version__
from app.config import Settings
from app.db import Base, create_db_engine
from app.middleware import MaxBodySizeMiddleware
from app.routers import games, health
from app.routers import settings as settings_router
from app.storage import Storage

log = logging.getLogger("savesync")

# Multipart framing adds a little overhead on top of the archive itself.
_BODY_OVERHEAD_BYTES = 64 * 1024


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or Settings.from_env()

    settings.db_dir.mkdir(parents=True, exist_ok=True)
    storage = Storage(settings)
    storage.init()
    engine = create_db_engine(settings.db_path)
    Base.metadata.create_all(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        log.info("SaveSync server %s started (data=%s, db=%s)", __version__, settings.data_dir, settings.db_path)
        yield
        engine.dispose()

    app = FastAPI(
        title="SaveSync",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings = settings
    app.state.storage = storage
    app.state.engine = engine
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)

    app.add_middleware(MaxBodySizeMiddleware, max_bytes=settings.max_upload_bytes + _BODY_OVERHEAD_BYTES)
    app.include_router(health.router)
    app.include_router(games.router)
    app.include_router(settings_router.router)
    return app
