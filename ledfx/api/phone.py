"""The phone remote: the /phone page, and the socket that feeds Phone Paint."""

import logging
import uuid
from typing import Annotated, Literal

from aiohttp import WSMsgType, web
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ledfx.api import RestEndpoint
from ledfx.configuration.fields import Color
from ledfx.configuration.paths import get_ssl_certs
from ledfx.effects.phone_paint import Clear, Command, Fill, Mark, PhonePaint, Stroke
from ledfx.effects.utils.custom import color_array
from ledfx.utils import get_local_ip

_LOGGER = logging.getLogger(__name__)

# A pointer update is a few dozen bytes; anything bigger is not from the page
MAX_MESSAGE = 4096


class StrokeMessage(BaseModel):
    t: Literal["p"]
    v: str
    x: Annotated[float, Field(ge=0.0, le=1.0)] | None
    d: bool = False
    c: Color = "#FFFFFF"
    s: Annotated[float, Field(ge=0.0, le=1.0)] = 0.03
    e: bool = False


class ClearMessage(BaseModel):
    t: Literal["clear"]
    v: str


class FillMessage(BaseModel):
    t: Literal["fill"]
    v: str
    c: Color


class MarkMessage(BaseModel):
    t: Literal["mark"]
    v: str
    x: Annotated[float, Field(ge=0.0, le=1.0)] | None


Message = Annotated[
    StrokeMessage | ClearMessage | FillMessage | MarkMessage,
    Field(discriminator="t"),
]
MESSAGE = TypeAdapter(Message)


def command_for(
    message: StrokeMessage | ClearMessage | FillMessage | MarkMessage, client: str
) -> Command:
    if isinstance(message, StrokeMessage):
        return Stroke(
            client=client,
            x=message.x,
            down=message.d,
            color=color_array(message.c),
            size=message.s,
            erase=message.e,
        )
    if isinstance(message, FillMessage):
        return Fill(color_array(message.c))
    if isinstance(message, MarkMessage):
        return Mark(message.x)
    return Clear()


class PhoneEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/phone"

    async def get(self, request: web.Request) -> web.StreamResponse:
        """List the strips for the phone page, or open its socket on an upgrade."""
        socket = web.WebSocketResponse(heartbeat=10, max_msg_size=MAX_MESSAGE)
        if not socket.can_prepare(request).ok:
            return await self.bare_request_success(self.status())
        await socket.prepare(request)
        client = uuid.uuid4().hex[:8]
        # Strips whose effect is not Phone Paint, already reported to the phone
        idle: set[str] = set()
        async for message in socket:
            if message.type != WSMsgType.TEXT:
                continue
            virtual_id = self.dispatch(client, message.data)
            if virtual_id is None:
                continue
            if self.painting(virtual_id):
                idle.discard(virtual_id)
            elif virtual_id not in idle:
                # Once per change, so the page can offer to take the strip back
                idle.add(virtual_id)
                await socket.send_json({"t": "idle", "v": virtual_id})
        return socket

    def painting(self, virtual_id: str) -> bool:
        virtual = self._ledfx.virtuals.get(virtual_id)
        return virtual is not None and isinstance(virtual.active_effect, PhonePaint)

    def dispatch(self, client: str, data: str) -> str | None:
        """Hand one message to its strip's Phone Paint; returns the strip it named."""
        try:
            message = MESSAGE.validate_json(data)
        except ValidationError:
            _LOGGER.debug("Ignoring a malformed phone message: %.80s", data)
            return None
        virtual = self._ledfx.virtuals.get(message.v)
        effect = virtual.active_effect if virtual is not None else None
        if isinstance(effect, PhonePaint):
            effect.send(command_for(message, client))
        return message.v

    def status(self) -> dict[str, object]:
        strips = [
            {
                "id": virtual.id,
                "name": virtual.name,
                "pixels": virtual.pixel_count,
                "active": virtual.active,
                "effect": getattr(virtual.active_effect, "type", None),
            }
            for virtual in self._ledfx.virtuals.values()
        ]
        secure = get_ssl_certs(self._ledfx.config_dir) is not None
        url = f"https://{get_local_ip()}:{self._ledfx.port_s}/phone" if secure else None
        return {"virtuals": strips, "phone_url": url}
