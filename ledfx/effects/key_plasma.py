from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray


class KeyPlasma(CorsairEffect, GradientEffect):
    NAME = "Key Plasma"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.5,
            description="How quickly the plasma churns when the music is quiet",
            ge=0.1,
            le=3.0,
        )
        scale: CoercedFloat = Field(
            1.0, description="How large the blobs of plasma are", ge=0.3, le=3.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self._time = 0.0

    @override
    def render(self) -> None:
        # The music speeds the plasma up, and the bass makes it glow brighter
        self._time += self.step() * self.config.speed * (1 + 3 * self.loudness)
        t = self._time
        x = self._x / self.config.scale
        y = self._y / self.config.scale
        field = (
            np.sin(x * 10 + t)
            + np.sin(y * 18 - t * 1.3)
            + np.sin((x + y) * 8 + t * 0.7)
            + np.sin(np.hypot(x - 0.5 + np.sin(t * 0.3) * 0.3, y - 0.15) * 20 - t * 1.7)
        )
        colors = self.get_gradient_color_vectorized1d((field + 4) / 8 * 0.999)
        self.pixels = colors * (0.35 + 0.65 * self.levels[0])
