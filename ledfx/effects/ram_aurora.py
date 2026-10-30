import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aurora_colors, ram_layout
from ledfx.effects.utils.custom import FloatArray


class RamAurora(CorsairEffect):
    NAME = "RAM Aurora"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.4, description="How quickly the curtains drift", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        self._across: FloatArray = ram.stick / max(ram.sticks - 1, 1)
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music stirs the curtains and makes them glow
        self._time += self.step() * self.config.speed * (1 + self.loudness)
        t = self._time
        across, up = self._across, self._ram.height
        curtain = 0.5 + 0.5 * np.sin(across * 4 + t + 2 * np.sin(up * 3 + t * 0.7))
        shade = 0.5 + 0.5 * np.sin(up * 2.5 - t * 0.5 + across * 1.5)
        # The curtains hang from the top of the sticks
        level = curtain**2 * (0.4 + 0.6 * up) * (0.3 + 0.7 * self.loudness)
        self.pixels = aurora_colors(shade) * np.maximum(level, 0.04)[:, None]
