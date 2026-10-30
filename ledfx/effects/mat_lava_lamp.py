import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, heat_colors

BLOBS = 3
# How long a blob is, as a share of the pad's edge
BLOB = 0.12


class MatLavaLamp(CorsairEffect):
    NAME = "Mat Lava Lamp"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.3, description="How quickly the wax drifts", ge=0.05, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # Every blob of wax slides round the U at its own pace
        self._rates: FloatArray = 0.4 + self._rng.random(BLOBS)
        self._phases: FloatArray = self._rng.random(BLOBS) * 2 * np.pi
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music warms the lamp, and warm wax moves faster
        self._time += self.step() * self.config.speed * (0.5 + self.loudness)
        blobs = 0.5 + 0.48 * np.sin(self._time * self._rates + self._phases)
        wax = np.exp(-(((self._along[:, None] - blobs) / BLOB) ** 2)).sum(axis=1)
        field = np.clip(wax, 0, 1) * (0.7 + 0.3 * self.levels[0])
        # The mouse is the lamp's warm base
        heat = np.where(self._mouse, 0.3 + 0.3 * self.loudness, 0.12 + 0.6 * field)
        self.pixels = heat_colors(heat)
