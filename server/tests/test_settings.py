import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import AUTH


def test_default_value_comes_from_config(client):
    assert client.get("/settings").json() == {"max_versions": 5}


def test_put_then_get(client):
    r = client.put("/settings", json={"max_versions": 12})
    assert r.status_code == 200
    assert r.json() == {"max_versions": 12}
    assert client.get("/settings").json() == {"max_versions": 12}


def test_value_persists_across_restart(settings):
    with TestClient(create_app(settings), headers=AUTH) as c:
        c.put("/settings", json={"max_versions": 7})
    with TestClient(create_app(settings), headers=AUTH) as c:
        assert c.get("/settings").json() == {"max_versions": 7}


@pytest.mark.parametrize("bad", [0, -1, 1001, "ten", None, 1.5])
def test_invalid_max_versions_rejected(client, bad):
    r = client.put("/settings", json={"max_versions": bad})
    assert r.status_code == 422
    assert client.get("/settings").json() == {"max_versions": 5}


def test_missing_body_rejected(client):
    assert client.put("/settings", json={}).status_code == 422
