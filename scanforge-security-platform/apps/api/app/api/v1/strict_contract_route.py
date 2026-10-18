from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.services.evidence_contract import parse_strict_contract_json

if TYPE_CHECKING:
    from fastapi import Request


class StrictCompletionRoute(APIRoute):
    """Reject ambiguous JSON before FastAPI validates completion evidence."""

    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def strict_handler(request: Request):
            if request.method == "POST" and request.url.path.endswith("/complete"):
                try:
                    parsed_body = parse_strict_contract_json(await request.body())
                except (UnicodeDecodeError, ValueError) as exc:
                    return JSONResponse(status_code=422, content={"detail": str(exc)})
                # FastAPI reads Request.json() for the typed body parameter.
                request._json = parsed_body
            return await original_handler(request)

        return strict_handler
