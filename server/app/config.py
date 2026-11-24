"""Server configuration, read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

MIN_TOKEN_LENGTH = 16


class ConfigError(RuntimeError):
    """Raised when the server configuration is invalid or incomplete."""


def _int_env(env: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be >= {minimum}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    api_token: str
    data_dir: Path
    db_dir: Path
    max_upload_bytes: int
    default_max_versions: int
    enable_docs: bool = False

    @property
    def games_dir(self) -> Path:
        return self.data_dir / "games"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def db_path(self) -> Path:
        return self.db_dir / "savesync.db"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        token = env.get("SAVESYNC_API_TOKEN", "").strip()
        if len(token) < MIN_TOKEN_LENGTH:
            raise ConfigError(
                f"SAVESYNC_API_TOKEN must be set and at least {MIN_TOKEN_LENGTH} characters long"
            )
        return cls(
            api_token=token,
            data_dir=Path(env.get("SAVESYNC_DATA_DIR", "/data")),
            db_dir=Path(env.get("SAVESYNC_DB_DIR", "/db")),
            max_upload_bytes=_int_env(env, "SAVESYNC_MAX_UPLOAD_MB", 1024) * 1024 * 1024,
            default_max_versions=_int_env(env, "SAVESYNC_DEFAULT_MAX_VERSIONS", 10),
            enable_docs=env.get("SAVESYNC_ENABLE_DOCS", "").strip().lower() in {"1", "true", "yes"},
        )
