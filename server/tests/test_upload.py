import pytest

from tests.helpers import make_zip, sha256_hex, upload


def test_upload_creates_game_and_version(client):
    content = make_zip()
    r = upload(client, "Elden Ring", content, machine="pop-os", steam_app_id=1245620)
    assert r.status_code == 201
    body = r.json()
    assert body["game_id"] == "Elden Ring"
    assert body["sha256"] == sha256_hex(content)
    assert body["size_bytes"] == len(content)
    assert body["machine"] == "pop-os"
    assert body["modified_at"].startswith("2026-11-20T18:30:00")

    games = client.get("/games").json()
    assert len(games) == 1
    assert games[0]["game_id"] == "Elden Ring"
    assert games[0]["steam_app_id"] == 1245620
    assert games[0]["version_count"] == 1
    assert games[0]["latest_version"]["id"] == body["id"]


def test_upload_appends_versions(client):
    v1 = upload(client, "Hades", make_zip({"a": b"1"})).json()
    v2 = upload(client, "Hades", make_zip({"a": b"2"})).json()
    assert v2["id"] > v1["id"]
    versions = client.get("/games/Hades/versions").json()
    assert [v["id"] for v in versions] == [v2["id"], v1["id"]]  # newest first


def test_game_names_with_special_characters(client):
    names = ["The Witcher 3: Wild Hunt", "Pokémon Légendes", "Half-Life 2: Episode One", "ゲーム", "A&B?#%"]
    for name in names:
        assert upload(client, name).status_code == 201, name
    assert sorted(g["game_id"] for g in client.get("/games").json()) == sorted(names)
    for name in names:
        from tests.helpers import url_id

        assert client.get(f"/games/{url_id(name)}/versions").status_code == 200


def test_archive_stored_atomically_inside_games_dir(client, settings):
    upload(client, "Hades")
    files = [p for p in settings.data_dir.rglob("*") if p.is_file()]
    assert len(files) == 1
    assert files[0].is_relative_to(settings.games_dir)
    assert files[0].suffix == ".zip"
    assert list(settings.tmp_dir.iterdir()) == []  # no leftover temp file
    assert "Hades" not in str(files[0])  # game name never used as a path


def test_steam_app_id_is_updated_when_provided(client):
    upload(client, "Hades")
    assert client.get("/games").json()[0]["steam_app_id"] is None
    upload(client, "Hades", steam_app_id=1145360)
    assert client.get("/games").json()[0]["steam_app_id"] == 1145360


def test_hash_mismatch_rejected_and_nothing_stored(client, settings):
    r = upload(client, "Hades", sha256="0" * 64)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "hash_mismatch"
    assert client.get("/games").json() == []
    assert [p for p in settings.data_dir.rglob("*") if p.is_file()] == []


def test_hash_comparison_is_case_insensitive(client):
    content = make_zip()
    assert upload(client, "Hades", content, sha256=sha256_hex(content).upper()).status_code == 201


@pytest.mark.parametrize("bad", ["", "abc", "z" * 64, "0" * 63, "0" * 65])
def test_malformed_sha256_rejected(client, bad):
    r = upload(client, "Hades", sha256=bad)
    assert r.status_code == 422
    assert client.get("/games").json() == []


def test_not_a_zip_rejected(client, settings):
    data = b"this is definitely not a zip file"
    r = upload(client, "Hades", data)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_archive"
    assert [p for p in settings.data_dir.rglob("*") if p.is_file()] == []


def test_empty_archive_rejected(client):
    r = upload(client, "Hades", b"")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "empty_archive"


def test_naive_modified_at_rejected(client):
    r = upload(client, "Hades", modified_at="2026-11-20T18:30:00")
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_modified_at"


def test_modified_at_normalised_to_utc(client):
    r = upload(client, "Hades", modified_at="2026-11-20T19:30:00+01:00")
    assert r.status_code == 201
    assert r.json()["modified_at"].startswith("2026-11-20T18:30:00")


def test_invalid_modified_at_rejected(client):
    assert upload(client, "Hades", modified_at="yesterday").status_code == 422


@pytest.mark.parametrize("machine", ["", "   ", "x" * 101, "bad\nname"])
def test_invalid_machine_rejected(client, machine):
    assert upload(client, "Hades", machine=machine).status_code == 422


def test_missing_archive_field_rejected(client):
    r = client.post(
        "/games/Hades/upload",
        data={"sha256": "0" * 64, "modified_at": "2026-11-20T18:30:00+00:00", "machine": "pc"},
    )
    assert r.status_code == 422


def test_invalid_steam_app_id_rejected(client):
    assert upload(client, "Hades", steam_app_id=0).status_code == 422


def test_oversized_archive_rejected_by_streaming_check(client, settings):
    # Just above the limit, but within the multipart overhead margin of the middleware.
    data = b"0" * (settings.max_upload_bytes + 1)
    r = upload(client, "Hades", data)
    assert r.status_code == 413
    assert [p for p in settings.data_dir.rglob("*") if p.is_file()] == []


def test_oversized_request_rejected_by_content_length(client, settings):
    data = b"0" * (settings.max_upload_bytes * 3)
    r = upload(client, "Hades", data)
    assert r.status_code == 413
    assert r.json()["detail"]["code"] == "payload_too_large"


def test_failed_db_commit_leaves_no_file(app, client, settings, monkeypatch):
    from sqlalchemy.orm import Session

    def boom(self):
        raise RuntimeError("disk full")

    monkeypatch.setattr(Session, "commit", boom)
    from fastapi.testclient import TestClient

    from tests.helpers import AUTH

    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        r = upload(c, "Hades")
    assert r.status_code == 500
    assert [p for p in settings.data_dir.rglob("*") if p.is_file()] == []
