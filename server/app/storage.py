"""Archive storage on disk. Writes are atomic: temp file in the same volume, then rename."""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.config import Settings

log = logging.getLogger("savesync.storage")

CHUNK_SIZE = 1024 * 1024


class UploadTooLarge(Exception):
    pass


class StorageError(Exception):
    pass


@dataclass(frozen=True)
class StoredUpload:
    path: Path
    size: int
    sha256: str


def game_dir_key(game_id: str) -> str:
    """Directory name derived from a hash, so the game name never touches the filesystem."""
    return hashlib.sha256(game_id.encode("utf-8")).hexdigest()[:32]


class Storage:
    def __init__(self, settings: Settings) -> None:
        self.data_dir = settings.data_dir
        self.games_dir = settings.games_dir
        self.tmp_dir = settings.tmp_dir

    def init(self) -> None:
        self.games_dir.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        # Leftovers from a crashed upload are never valid: drop them.
        for leftover in self.tmp_dir.glob("upload-*.part"):
            leftover.unlink(missing_ok=True)

    def save_stream(self, src: BinaryIO, max_bytes: int) -> StoredUpload:
        """Copy `src` to a temp file, computing size and sha256 on the fly."""
        tmp = self.tmp_dir / f"upload-{uuid.uuid4().hex}.part"
        hasher = hashlib.sha256()
        size = 0
        try:
            with open(tmp, "wb") as out:
                while chunk := src.read(CHUNK_SIZE):
                    size += len(chunk)
                    if size > max_bytes:
                        raise UploadTooLarge
                    hasher.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return StoredUpload(path=tmp, size=size, sha256=hasher.hexdigest())

    def promote(self, tmp_path: Path, game_id: str, version_id: int) -> str:
        """Atomically move a validated temp file to its final place. Returns the relative path."""
        rel = Path("games") / game_dir_key(game_id) / f"{version_id}.zip"
        dest = self.data_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, dest)
        return rel.as_posix()

    def resolve(self, rel_path: str) -> Path:
        """Absolute path of a stored archive, guaranteed to be inside the games directory."""
        candidate = (self.data_dir / rel_path).resolve()
        if not candidate.is_relative_to(self.games_dir.resolve()):
            raise StorageError(f"stored path escapes the games directory: {rel_path!r}")
        return candidate

    def remove(self, rel_path: str) -> None:
        try:
            path = self.resolve(rel_path)
        except StorageError:
            log.error("Refusing to delete suspicious path %r", rel_path)
            return
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()  # only succeeds when the game directory is empty
        except OSError:
            pass
