"""Reject oversized requests early, based on Content-Length."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            for name, value in scope["headers"]:
                if name == b"content-length":
                    try:
                        length = int(value)
                    except ValueError:
                        length = 0
                    if length > self.max_bytes:
                        response = JSONResponse(
                            status_code=413,
                            content={
                                "detail": {
                                    "code": "payload_too_large",
                                    "message": "Archive trop volumineuse pour ce serveur.",
                                }
                            },
                        )
                        await response(scope, receive, send)
                        return
        await self.app(scope, receive, send)
