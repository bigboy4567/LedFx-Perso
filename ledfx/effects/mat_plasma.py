from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray


class MatPlasma(CorsairEffect, GradientEffect):
    NAME = "Mat Plasma"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.5,
            description="How quickly the plasma churns when the music is quiet",
            ge=0.1,
            le=3.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._height: FloatArray = mat_height(mat)
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music speeds the plasma up, and the bass makes it glow brighter
        self._time += self.step() * self.config.speed * (1 + 3 * self.loudness)
        t = self._time
        a, h = self._along, self._height
        field = (
            np.sin(a * 9 + t)
            + np.sin(h * 6 - t * 1.3)
            + np.sin((a + h) * 5 + t * 0.7)
            + np.sin(a * 13 - t * 1.7)
        )
        colors = self.get_gradient_color_vectorized1d((field + 4) / 8 * 0.999)
        self.pixels = colors * (0.35 + 0.65 * self.levels[0])
