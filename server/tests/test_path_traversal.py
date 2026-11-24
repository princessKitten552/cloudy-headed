import pytest

from app.validation import InvalidGameId, validate_game_id
from tests.helpers import upload

BAD_IDS = [
    "..",
    ".",
    "",
    "../etc/passwd",
    "..\\..\\windows\\system32",
    "a/b",
    "a\\b",
    "/absolute",
    "C:\\Users\\me",
    " leading",
    "trailing ",
    "nul\x00byte",
    "new\nline",
    "tab\there",
    "x" * 256,
]

GOOD_IDS = ["Elden Ring", "The Witcher 3: Wild Hunt", "Pokémon", "ゲーム", "a..b", "...", "Half-Life 2", "A&B?#%"]


@pytest.mark.parametrize("value", BAD_IDS)
def test_validator_rejects(value):
    with pytest.raises(InvalidGameId):
        validate_game_id(value)


@pytest.mark.parametrize("value", GOOD_IDS)
def test_validator_accepts(value):
    assert validate_game_id(value) == value


@pytest.mark.parametrize("raw", ["..%5C..%5Cevil", "a%5Cb", "%5C", "x%0Ay", "x%00y"])
def test_http_rejects_dangerous_game_ids(client, settings, raw):
    # Percent-encoded so the server receives the dangerous characters after URL decoding.
    r = client.post(
        f"/games/{raw}/upload",
        data={"sha256": "0" * 64, "modified_at": "2026-11-20T18:30:00+00:00", "machine": "pc"},
        files={"archive": ("save.zip", b"x", "application/zip")},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_game_id"
    assert client.get(f"/games/{raw}/versions").status_code == 400
    assert client.get(f"/games/{raw}/download").status_code == 400
    assert client.delete(f"/games/{raw}/versions/1").status_code == 400
    assert [p for p in settings.data_dir.rglob("*") if p.is_file()] == []


@pytest.mark.parametrize("raw", ["..%2F..%2Fetc%2Fpasswd", "a%2Fb", "%2e%2e%2Fsecret"])
def test_encoded_slashes_never_reach_a_handler(client, settings, raw):
    # An encoded slash is decoded before routing, so the path no longer matches any route.
    r = client.get(f"/games/{raw}/versions")
    assert r.status_code in (400, 404)
    assert [p for p in settings.data_dir.rglob("*") if p.is_file()] == []


def test_nothing_is_ever_written_outside_data_dir(client, settings, tmp_path):
    upload(client, "Hades")
    upload(client, "The Witcher 3: Wild Hunt")
    allowed = (settings.data_dir.resolve(), settings.db_dir.resolve())
    for p in tmp_path.rglob("*"):
        assert p.resolve().is_relative_to(allowed[0]) or p.resolve().is_relative_to(allowed[1]) or p == tmp_path


def test_stored_path_escape_is_refused(app, settings):
    from app.storage import StorageError

    with pytest.raises(StorageError):
        app.state.storage.resolve("../db/savesync.db")
    with pytest.raises(StorageError):
        app.state.storage.resolve("games/../../etc/passwd")
