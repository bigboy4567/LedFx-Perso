from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import BAR, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

UNLIT = 0.03
# The peak marker falls back this fast, in board depths a second
PEAK_FALL = 0.4
WHITE = np.array((255.0, 255.0, 255.0))


class KeyLevel(CorsairEffect, GradientEffect):
    NAME = "Key Level"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        sensitivity: CoercedFloat = Field(
            1.0, description="How high the volume fills the board", ge=0.3, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._bar = board.zone == BAR
        # How far up the board each key is, 0 at the front row, 1 at the light bar
        keys = ~self._bar
        bottom = board.y[keys].max() if keys.any() else 1.0
        top = board.y[keys].min() if keys.any() else 0.0
        self._height: FloatArray = np.clip(
            (bottom - board.y) / max(bottom - top, 1e-6), 0, 1
        )
        self.level = 0.0
        self.peak = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        target = min(1.0, self.loudness * self.config.sensitivity)
        self.level += (target - self.level) * min(1.0, dt * 12)
        self.peak = max(self.level, self.peak - PEAK_FALL * dt)
        # The rows fill up from the front with the volume
        height = self._height
        lit = height <= self.level + 1e-9
        colors = self.get_gradient_color_vectorized1d(height * 0.999)
        pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
        # The light bar marks the recent peak, white once the board is full
        bar = (
            colors * (0.2 + 0.8 * self.peak)
            if self.peak < 0.95
            else np.tile(WHITE, (height.size, 1))
        )
        self.pixels = np.where(self._bar[:, None], bar, pixels)
