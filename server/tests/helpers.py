from __future__ import annotations

import hashlib
import io
import zipfile
from urllib.parse import quote

TOKEN = "test-token-0123456789abcdef"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def make_zip(files: dict[str, bytes] | None = None) -> bytes:
    files = files or {"mapping.yaml": b"name: test\n", "save/slot1.sav": b"hello"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def url_id(game_id: str) -> str:
    return quote(game_id, safe="")


def upload(
    client,
    game_id: str,
    content: bytes | None = None,
    *,
    sha256: str | None = None,
    machine: str = "desktop-win",
    modified_at: str = "2026-11-20T18:30:00+00:00",
    steam_app_id: int | None = None,
):
    content = make_zip() if content is None else content
    data = {
        "sha256": sha256 if sha256 is not None else sha256_hex(content),
        "modified_at": modified_at,
        "machine": machine,
    }
    if steam_app_id is not None:
        data["steam_app_id"] = str(steam_app_id)
    return client.post(
        f"/games/{url_id(game_id)}/upload",
        data=data,
        files={"archive": ("save.zip", content, "application/zip")},
    )
