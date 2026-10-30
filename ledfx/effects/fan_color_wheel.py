import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import hue_colors

FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class FanColorWheel(CorsairEffect):
    NAME = "Fan Color Wheel"

    class Config(CorsairEffect.Config):
        turns_per_bar: CoercedFloat = Field(
            0.25, description="Turns of the wheels per bar of the song", ge=0.0, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self.turn = 0.0
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self.turn += self.song_moved() / 4 * self.config.turns_per_bar + dt * 0.02
        self._flash *= float(np.exp(-dt * FLASH))
        if self.beat():
            self._flash = 1.0
        fans = self._fans
        # Every rim is the whole color wheel, each fan a third of the way round from the last
        hues = (fans.angle + fans.fan / 3 + self.turn) % 1
        rim = hue_colors(hues) * (0.5 + 0.5 * self.loudness)
        # The hubs flash white on the beat
        hub = WHITE * max(0.05, self._flash)
        self.pixels = np.where((fans.ring == FAN_HUB)[:, None], hub, rim)
