"""Input validation. `game_id` is never used as a path, but is still validated strictly."""

from __future__ import annotations

import unicodedata

MAX_GAME_ID_LENGTH = 255
MAX_MACHINE_LENGTH = 100
_FORBIDDEN_CHARS = {"/", "\\"}
_FORBIDDEN_CATEGORIES = {"Cc", "Cs", "Zl", "Zp"}  # control, surrogate, line/paragraph separators


class InvalidGameId(ValueError):
    pass


def _has_bad_chars(value: str) -> bool:
    return any(ch in _FORBIDDEN_CHARS or unicodedata.category(ch) in _FORBIDDEN_CATEGORIES for ch in value)


def validate_game_id(value: str) -> str:
    """Return `value` if it is an acceptable game identifier, else raise InvalidGameId.

    Ludusavi names legitimately contain spaces, colons, accents, etc., so we do not
    restrict to a slug. We reject anything that could act as a path component.
    """
    if not value:
        raise InvalidGameId("game_id must not be empty")
    if len(value) > MAX_GAME_ID_LENGTH:
        raise InvalidGameId(f"game_id must be at most {MAX_GAME_ID_LENGTH} characters")
    if value != value.strip():
        raise InvalidGameId("game_id must not start or end with whitespace")
    if value in {".", ".."}:
        raise InvalidGameId("game_id must not be a relative path component")
    if _has_bad_chars(value):
        raise InvalidGameId("game_id contains forbidden characters")
    return value


def validate_machine(value: str) -> str:
    value = value.strip()
    if not value or len(value) > MAX_MACHINE_LENGTH or _has_bad_chars(value):
        raise ValueError("invalid machine name")
    return value
