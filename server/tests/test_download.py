import pytest

from tests.helpers import make_zip, sha256_hex, upload


def test_download_latest_returns_exact_bytes(client):
    old = make_zip({"a": b"old"})
    new = make_zip({"a": b"new"})
    upload(client, "Hades", old)
    upload(client, "Hades", new)

    r = client.get("/games/Hades/download")
    assert r.status_code == 200
    assert r.content == new
    assert r.headers["content-type"] == "application/zip"
    assert r.headers["x-content-sha256"] == sha256_hex(new)


def test_download_specific_version(client):
    old = make_zip({"a": b"old"})
    new = make_zip({"a": b"new"})
    v1 = upload(client, "Hades", old).json()["id"]
    upload(client, "Hades", new)

    r = client.get("/games/Hades/download", params={"version": v1})
    assert r.status_code == 200
    assert r.content == old
    assert r.headers["x-version-id"] == str(v1)


def test_download_unknown_game(client):
    r = client.get("/games/Nope/download")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "game_not_found"


def test_download_unknown_version(client):
    upload(client, "Hades")
    r = client.get("/games/Hades/download", params={"version": 9999})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "version_not_found"


def test_download_version_of_another_game_is_not_found(client):
    upload(client, "Hades")
    other = upload(client, "Celeste").json()["id"]
    r = client.get("/games/Hades/download", params={"version": other})
    assert r.status_code == 404


@pytest.mark.parametrize("bad", ["abc", "1.5", "", "../1"])
def test_download_invalid_version_param(client, bad):
    upload(client, "Hades")
    r = client.get("/games/Hades/download", params={"version": bad})
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_version"


def test_download_missing_file_on_disk_returns_410(client, settings):
    upload(client, "Hades")
    for p in settings.games_dir.rglob("*.zip"):
        p.unlink()
    r = client.get("/games/Hades/download")
    assert r.status_code == 410
    assert r.json()["detail"]["code"] == "archive_missing"


def test_versions_of_unknown_game(client):
    assert client.get("/games/Nope/versions").status_code == 404
