import pytest

from app.retention import purge_excess_versions
from tests.helpers import make_zip, upload


def _files(settings):
    return [p for p in settings.data_dir.rglob("*") if p.is_file()]


def _ids(client, game):
    return [v["id"] for v in client.get(f"/games/{game}/versions").json()]


def _upload_n(client, game, n):
    return [upload(client, game, make_zip({"a": str(i).encode()})).json()["id"] for i in range(n)]


def test_excess_versions_purged_after_upload(client, settings):
    ids = _upload_n(client, "Hades", 8)  # default max_versions = 5
    assert _ids(client, "Hades") == ids[:2:-1]  # newest 5, newest first
    assert len(_files(settings)) == 5
    assert client.get("/games").json()[0]["version_count"] == 5
    assert client.get("/games/Hades/download", params={"version": ids[0]}).status_code == 404


def test_nothing_purged_below_the_limit(client, settings):
    ids = _upload_n(client, "Hades", 5)
    assert len(_ids(client, "Hades")) == 5
    assert len(_files(settings)) == 5
    assert ids[0] in _ids(client, "Hades")


def test_limit_comes_from_server_settings(client, settings):
    client.put("/settings", json={"max_versions": 2})
    ids = _upload_n(client, "Hades", 4)
    assert _ids(client, "Hades") == [ids[3], ids[2]]
    assert len(_files(settings)) == 2


def test_max_versions_1_keeps_only_latest(client):
    client.put("/settings", json={"max_versions": 1})
    ids = _upload_n(client, "Hades", 3)
    assert _ids(client, "Hades") == [ids[2]]
    assert client.get("/games/Hades/download").status_code == 200


def test_retention_is_per_game(client):
    client.put("/settings", json={"max_versions": 2})
    a = _upload_n(client, "Hades", 4)
    b = _upload_n(client, "Celeste", 2)
    assert _ids(client, "Hades") == [a[3], a[2]]
    assert _ids(client, "Celeste") == [b[1], b[0]]


def test_latest_download_is_the_newest_after_purge(client):
    client.put("/settings", json={"max_versions": 2})
    _upload_n(client, "Hades", 3)
    newest = make_zip({"a": b"newest"})
    upload(client, "Hades", newest)
    assert client.get("/games/Hades/download").content == newest


def test_lowering_the_limit_deletes_nothing_until_next_upload(client):
    ids = _upload_n(client, "Hades", 4)
    client.put("/settings", json={"max_versions": 1})
    assert len(_ids(client, "Hades")) == 4  # changing a setting never deletes data by itself
    new_id = upload(client, "Hades", make_zip({"a": b"x"})).json()["id"]
    assert _ids(client, "Hades") == [new_id]
    assert ids[0] not in _ids(client, "Hades")


def test_raising_the_limit_keeps_everything(client):
    client.put("/settings", json={"max_versions": 100})
    _upload_n(client, "Hades", 8)
    assert len(_ids(client, "Hades")) == 8


def test_rejected_upload_never_purges(client):
    client.put("/settings", json={"max_versions": 2})
    ids = _upload_n(client, "Hades", 2)
    assert upload(client, "Hades", sha256="0" * 64).status_code == 422
    assert upload(client, "Hades", b"not a zip").status_code == 422
    assert _ids(client, "Hades") == [ids[1], ids[0]]


def test_purge_failure_does_not_fail_the_upload(client, monkeypatch):
    import app.routers.games as games_module

    def boom(*args, **kwargs):
        raise RuntimeError("purge exploded")

    monkeypatch.setattr(games_module, "purge_excess_versions", boom)
    client.put("/settings", json={"max_versions": 1})
    first = upload(client, "Hades").json()["id"]
    r = upload(client, "Hades", make_zip({"a": b"2"}))
    assert r.status_code == 201
    assert _ids(client, "Hades") == [r.json()["id"], first]  # nothing lost, purge retried next time


def test_purge_tolerates_a_missing_file(client, settings):
    client.put("/settings", json={"max_versions": 1})
    first = upload(client, "Hades").json()["id"]
    for p in settings.games_dir.rglob(f"{first}.zip"):
        p.unlink()
    r = upload(client, "Hades", make_zip({"a": b"2"}))
    assert r.status_code == 201
    assert _ids(client, "Hades") == [r.json()["id"]]


def test_purge_function_rejects_keep_below_one(app):
    with app.state.session_factory() as db:
        with pytest.raises(ValueError):
            purge_excess_versions(db, app.state.storage, game_pk=1, keep=0)


def test_purged_game_directory_still_contains_kept_files(client, settings):
    client.put("/settings", json={"max_versions": 2})
    ids = _upload_n(client, "Hades", 5)
    names = sorted(p.name for p in settings.games_dir.rglob("*.zip"))
    assert names == sorted(f"{i}.zip" for i in ids[-2:])
