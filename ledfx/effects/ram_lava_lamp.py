import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, heat_colors

BLOBS_PER_STICK = 2
# How tall a blob is, as a share of a stick
BLOB = 0.18


class RamLavaLamp(CorsairEffect):
    NAME = "RAM Lava Lamp"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.3, description="How quickly the wax rises and sinks", ge=0.05, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        # Every blob of wax drifts up and down at its own pace
        shape = (ram.sticks, BLOBS_PER_STICK)
        self._rates: FloatArray = 0.5 + self._rng.random(shape)
        self._phases: FloatArray = self._rng.random(shape) * 2 * np.pi
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music warms the lamps, and warm wax moves faster
        self._time += self.step() * self.config.speed * (0.5 + self.loudness)
        ram = self._ram
        blobs = 0.5 + 0.45 * np.sin(self._time * self._rates + self._phases)
        heights = blobs[ram.stick]
        wax = np.exp(-(((ram.height[:, None] - heights) / BLOB) ** 2)).sum(axis=1)
        heat = 0.15 + 0.6 * np.clip(wax, 0, 1) * (0.7 + 0.3 * self.levels[0])
        self.pixels = heat_colors(heat)
