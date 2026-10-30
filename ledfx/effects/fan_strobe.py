from typing import Literal

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import FAN_HUB, CorsairEffect, fan_layout
from ledfx.effects.utils.custom import FloatArray, color_array

Order = Literal["Top to bottom", "Bottom to top", "Random", "All"]
# How quickly a flash dies
FLASH = 18.0


class FanStrobe(CorsairEffect):
    NAME = "Fan Strobe"

    class Config(CorsairEffect.Config):
        color: Color = Field("#FFFFFF", description="Color of the flashes")
        order: Order = Field(
            "Top to bottom", description="Which fan flashes on each beat"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._flash: FloatArray = np.zeros(self._fans.count)
        self._flashes = 0
        self._hubs = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _next_fan(self) -> int:
        count = self._fans.count
        self._flashes += 1
        match self.config.order:
            case "Top to bottom":
                return self._flashes % count
            case "Bottom to top":
                return count - 1 - self._flashes % count
            case _:
                return int(self._rng.integers(count))

    @override
    def render(self) -> None:
        fade = float(np.exp(-self.step() * FLASH))
        self._flash *= fade
        self._hubs *= fade
        if self.beat():
            if self.config.order == "All":
                self._flash[:] = 1.0
            else:
                self._flash[self._next_fan()] = 1.0
        # Each percussive hit flashes every hub
        if self.hit():
            self._hubs = 1.0
        fans = self._fans
        level = self._flash[fans.fan]
        level = np.where(fans.ring == FAN_HUB, np.maximum(level, self._hubs), level)
        self.pixels = self._color * level[:, None]
