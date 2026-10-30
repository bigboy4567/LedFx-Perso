from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

UNLIT = 0.03
# The peak marker falls back this fast, in pad edges a second
PEAK_FALL = 0.4
WHITE = np.array((255.0, 255.0, 255.0))


class MatLevel(CorsairEffect, GradientEffect):
    NAME = "Mat Level"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        sensitivity: CoercedFloat = Field(
            1.0, description="How far the volume fills the pad", ge=0.3, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self.level = 0.0
        self.peak = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        target = min(1.0, self.loudness * self.config.sensitivity)
        self.level += (target - self.level) * min(1.0, dt * 12)
        self.peak = max(self.level, self.peak - PEAK_FALL * dt)
        # The volume fills the pad from its left tip, round the U to its right tip
        along = self._along
        lit = along <= self.level + 1e-9
        colors = self.get_gradient_color_vectorized1d(along * 0.999)
        pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
        peak = np.abs(along - self.peak) < 0.04
        pixels = np.where((peak & (self.peak > 0.05))[:, None], WHITE, pixels)
        # The mouse turns from green to red as the volume rises
        mouse = self.get_gradient_color_vectorized1d(
            np.full(along.size, self.level * 0.999)
        )
        self.pixels = np.where(
            self._mouse[:, None], mouse * (0.2 + 0.8 * self.level), pixels
        )
