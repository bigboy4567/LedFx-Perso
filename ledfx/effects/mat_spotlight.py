from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

# The spot's half width in the quiet and at full volume, as shares of the pad's edge
SMALLEST = 0.06
LARGEST = 0.2


class MatSpotlight(CorsairEffect, GradientEffect):
    NAME = "Mat Spotlight"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        glide: CoercedFloat = Field(
            6.0,
            description="How quickly the spot glides to its new place",
            ge=1.0,
            le=20.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self.spot = 0.5
        self._aim = 0.5
        self._hue = 0.0
        self._width = SMALLEST

    @override
    def render(self) -> None:
        dt = self.step()
        # Each beat the spot glides somewhere new on the pad, in a new color
        if self.beat():
            self._aim = float(self._rng.random())
            self._hue = (self._hue + 0.17) % 1
        self.spot += (self._aim - self.spot) * min(1.0, dt * self.config.glide)
        target = SMALLEST + (LARGEST - SMALLEST) * self.loudness
        self._width += (target - self._width) * min(1.0, dt * 8)
        level = np.clip(1 - np.abs(self._along - self.spot) / self._width, 0, 1) ** 0.7
        # The mouse lights up when the spot passes over the bottom of the U
        under = max(0.0, 1 - abs(self.spot - 0.5) / self._width)
        level = np.where(self._mouse, under, level)
        colors = self.get_gradient_color_vectorized1d(np.full(level.size, self._hue))
        self.pixels = colors * np.maximum(level, 0.02)[:, None]
