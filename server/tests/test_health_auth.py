import pytest

from tests.helpers import TOKEN

PROTECTED = [
    ("GET", "/games"),
    ("GET", "/games/Foo/versions"),
    ("GET", "/games/Foo/download"),
    ("DELETE", "/games/Foo/versions/1"),
    ("GET", "/settings"),
    ("PUT", "/settings"),
    ("POST", "/games/Foo/upload"),
]


def test_health_is_public(anon_client):
    r = anon_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_missing_token_rejected(anon_client, method, path):
    r = anon_client.request(method, path)
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "invalid_token"
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "header",
    [
        "Bearer wrong-token-0123456789",
        "Bearer ",
        f"Basic {TOKEN}",
        TOKEN,  # no scheme
        f"Bearer {TOKEN}x",
        f"Bearer {TOKEN[:-1]}",
    ],
)
def test_bad_token_rejected(anon_client, header):
    r = anon_client.get("/games", headers={"Authorization": header})
    assert r.status_code == 401


def test_valid_token_accepted(anon_client):
    r = anon_client.get("/games", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200
    assert r.json() == []


def test_docs_disabled_by_default(anon_client):
    assert anon_client.get("/docs").status_code == 404
    assert anon_client.get("/openapi.json").status_code == 404
