from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.helpers import AUTH, TOKEN


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        api_token=TOKEN,
        data_dir=tmp_path / "data",
        db_dir=tmp_path / "db",
        max_upload_bytes=1024 * 1024,
        default_max_versions=5,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    """Authenticated client."""
    with TestClient(app, headers=AUTH) as c:
        yield c


@pytest.fixture
def anon_client(app):
    with TestClient(app) as c:
        yield c
