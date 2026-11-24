from tests.helpers import upload


def _files(settings):
    return [p for p in settings.data_dir.rglob("*") if p.is_file()]


def test_delete_version_removes_row_and_file(client, settings):
    v1 = upload(client, "Hades").json()["id"]
    v2 = upload(client, "Hades").json()["id"]
    assert len(_files(settings)) == 2

    r = client.delete(f"/games/Hades/versions/{v1}")
    assert r.status_code == 204
    assert [v["id"] for v in client.get("/games/Hades/versions").json()] == [v2]
    assert len(_files(settings)) == 1
    assert client.get("/games/Hades/download", params={"version": v1}).status_code == 404


def test_delete_last_version_removes_game(client, settings):
    v = upload(client, "Hades").json()["id"]
    assert client.delete(f"/games/Hades/versions/{v}").status_code == 204
    assert client.get("/games").json() == []
    assert _files(settings) == []
    assert list(settings.games_dir.iterdir()) == []  # empty game directory cleaned up


def test_delete_unknown_version(client):
    upload(client, "Hades")
    r = client.delete("/games/Hades/versions/9999")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "version_not_found"


def test_delete_unknown_game(client):
    assert client.delete("/games/Nope/versions/1").status_code == 404


def test_delete_version_through_wrong_game_is_refused(client, settings):
    upload(client, "Hades")
    other = upload(client, "Celeste").json()["id"]
    assert client.delete(f"/games/Hades/versions/{other}").status_code == 404
    assert len(_files(settings)) == 2  # nothing deleted
    assert client.get("/games/Celeste/versions").json()[0]["id"] == other
