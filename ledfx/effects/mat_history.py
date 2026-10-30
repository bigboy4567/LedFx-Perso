from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray, IntArray


class MatHistory(CorsairEffect, GradientEffect):
    NAME = "Mat History"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        steps_per_second: CoercedFloat = Field(
            8.0,
            description="How quickly the volume flows round the pad",
            ge=1.0,
            le=30.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._mouse = mat.mouse
        edge = int(np.count_nonzero(~mat.mouse))
        self._cells = max(edge, 1)
        # Each LED's place round the U, from the left tip
        self._cell: IntArray = np.round(mat.along * (self._cells - 1)).astype(int)
        # How loud it was, the newest at the left tip
        self.history: FloatArray = np.zeros(self._cells)
        self._due = 0.0

    @override
    def render(self) -> None:
        self._due += self.step() * self.config.steps_per_second
        level = self.loudness
        # The volume enters at the left tip and flows round the U to the right
        steps = min(int(self._due), self._cells)
        self._due -= int(self._due)
        if steps:
            self.history[steps:] = self.history[:-steps].copy()
            self.history[:steps] = level
        self.history[0] = level
        value = self.history[self._cell]
        value = np.where(self._mouse, level, value)
        colors = self.get_gradient_color_vectorized1d(np.clip(value, 0, 1) * 0.999)
        self.pixels = colors * np.maximum(value, 0.02)[:, None]
