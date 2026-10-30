import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, ring_gap
from ledfx.effects.utils.custom import heat_colors

# Blobs on each fan, with how fast each creeps round, in turns per second
BLOB_SPEEDS = (0.07, -0.11)
BLOB_SIZE = 0.12


class FanLava(CorsairEffect):
    NAME = "Fan Lava"

    class Config(CorsairEffect.Config):
        swell: CoercedFloat = Field(
            1.0, description="How much the bass swells the blobs", ge=0.0, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._fans = fan_layout(pixel_count)
        self._time = 0.0

    @override
    def render(self) -> None:
        self._time += self.step()
        fans = self._fans
        size = BLOB_SIZE * (1 + self.config.swell * self.levels[0])
        heat = np.full(fans.angle.size, 0.12)
        for blob, speed in enumerate(BLOB_SPEEDS):
            # Every fan's blobs creep round from their own starting points
            at = np.asarray(
                (self._time * speed + fans.fan * 0.29 + blob * 0.5) % 1, dtype=float
            )
            np.maximum(
                heat, 0.85 * np.exp(-((ring_gap(fans.angle, at) / size) ** 2)), out=heat
            )
        self.pixels = heat_colors(heat * (0.75 + 0.25 * self.loudness))
