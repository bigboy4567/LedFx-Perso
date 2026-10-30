import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, aurora_colors, mat_layout
from ledfx.effects.utils.custom import FloatArray


class MatAurora(CorsairEffect):
    NAME = "Mat Aurora"

    class Config(CorsairEffect.Config):
        speed: CoercedFloat = Field(
            0.4, description="How quickly the curtains drift", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music stirs the curtains and makes them glow
        self._time += self.step() * self.config.speed * (1 + self.loudness)
        t = self._time
        along = self._along
        curtain = 0.5 + 0.5 * np.sin(along * 9 + t + 2 * np.sin(along * 3 - t * 0.6))
        shade = 0.5 + 0.5 * np.sin(along * 4 - t * 0.4)
        level = curtain**2 * (0.3 + 0.7 * self.loudness)
        pixels = aurora_colors(shade) * np.maximum(level, 0.04)[:, None]
        # The mouse glows with the sky's whole color
        mouse = aurora_colors(np.full(along.size, 0.5 + 0.5 * np.sin(t * 0.3))) * (
            0.2 + 0.5 * self.loudness
        )
        self.pixels = np.where(self._mouse[:, None], mouse, pixels)
