import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout, ring_gap
from ledfx.effects.utils.custom import color_array

# How wide the beam is, as a share of a turn
BEAM = 0.12
FLASH = 8.0


class FanSiren(CorsairEffect):
    NAME = "Fan Siren"

    class Config(CorsairEffect.Config):
        first_color: Color = Field(
            "#FF0000", description="Color of the fans in odd places"
        )
        second_color: Color = Field(
            "#0030FF", description="Color of the fans in even places"
        )
        top_speed: CoercedFloat = Field(
            2.0, description="Turns a second at full volume", ge=0.5, le=6.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._turn = 0.0
        self._flash = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._first = color_array(self.config.first_color)
        self._second = color_array(self.config.second_color)

    @override
    def render(self) -> None:
        dt = self.step()
        # The beacons spin faster as the music gets louder
        self._turn += dt * (0.3 + self.loudness * self.config.top_speed)
        self._flash *= float(np.exp(-dt * FLASH))
        if self.beat():
            self._flash = 1.0
        fans = self._fans
        first = (fans.fan % 2 == 0)[:, None]
        heading = np.where(fans.fan % 2 == 0, 1.0, -1.0)
        beam = np.exp(-((ring_gap(fans.angle, self._turn * heading) / BEAM) ** 2))
        rim = (
            np.where(first, self._first, self._second) * np.maximum(beam, 0.03)[:, None]
        )
        # Each beat flashes the hubs in the other color
        hub = np.where(first, self._second, self._first) * max(0.03, self._flash)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
