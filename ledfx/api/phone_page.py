"""The phone remote page: the phone points at a strip and paints on it."""

import os

from aiohttp import web

from ledfx.api import RestEndpoint

PAGE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "phone", "index.html")


class PhonePageEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/phone"

    async def get(self) -> web.StreamResponse:
        return web.FileResponse(PAGE, headers={"Cache-Control": "no-cache"})
