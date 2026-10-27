"""The local certificate authority a phone installs to trust the HTTPS port."""

import os

from aiohttp import web

from ledfx.api import RestEndpoint

# Written next to the HTTPS certificate by tools/phone_cert.py
CA_FILE = "ca.crt"


class PhoneCaEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/phone/ca.crt"

    async def get(self) -> web.StreamResponse:
        path = os.path.join(self._ledfx.config_dir, "ssl", CA_FILE)
        if not os.path.isfile(path):
            raise web.HTTPNotFound()
        return web.FileResponse(
            path, headers={"Content-Type": "application/x-x509-ca-cert"}
        )
