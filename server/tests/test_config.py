import pytest

from app.config import ConfigError, Settings


def test_token_required():
    with pytest.raises(ConfigError):
        Settings.from_env({})


def test_short_token_rejected():
    with pytest.raises(ConfigError):
        Settings.from_env({"SAVESYNC_API_TOKEN": "short"})


def test_defaults_and_overrides():
    s = Settings.from_env(
        {"SAVESYNC_API_TOKEN": "a" * 32, "SAVESYNC_MAX_UPLOAD_MB": "10", "SAVESYNC_DEFAULT_MAX_VERSIONS": "3"}
    )
    assert s.max_upload_bytes == 10 * 1024 * 1024
    assert s.default_max_versions == 3
    assert str(s.data_dir) == "/data" and str(s.db_dir) == "/db"
    assert s.enable_docs is False


def test_invalid_integer_rejected():
    with pytest.raises(ConfigError):
        Settings.from_env({"SAVESYNC_API_TOKEN": "a" * 32, "SAVESYNC_MAX_UPLOAD_MB": "abc"})
