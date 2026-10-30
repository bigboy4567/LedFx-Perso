from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray


class KeyKaleidoscope(CorsairEffect, GradientEffect):
    NAME = "Key Kaleidoscope"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.5,
            description="How quickly the pattern changes when the music is quiet",
            ge=0.1,
            le=3.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        # Folded into one quarter of the board, so the four quarters mirror each other
        self._u: FloatArray = np.abs(board.x - 0.5)
        self._v: FloatArray = np.abs(board.y - 0.5) * KEYBOARD_DEPTH
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music turns the kaleidoscope faster, and each beat gives it a twist
        self._time += self.step() * self.config.speed * (1 + 2 * self.loudness)
        if self.beat():
            self._time += 0.4
        t = self._time
        u, v = self._u, self._v
        field = (
            np.sin(u * 14 + t)
            + np.sin(v * 30 - t * 1.2)
            + np.sin((u + v) * 18 + t * 0.6)
            + np.sin(np.hypot(u, v) * 25 - t * 1.5)
        )
        colors = self.get_gradient_color_vectorized1d((field + 4) / 8 * 0.999)
        self.pixels = colors * (0.4 + 0.6 * self.loudness)
