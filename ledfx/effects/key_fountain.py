from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# Drops in the air at once, at most, and how many a beat throws
MAX_DROPS = 40
DROPS_PER_BEAT = 8
# In board widths: how hard the drops fall, and how big they are
GRAVITY = 1.2
DROP = 0.03


class KeyFountain(CorsairEffect, GradientEffect):
    NAME = "Key Fountain"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        pressure: CoercedFloat = Field(
            1.0, description="How high the beat throws the water", ge=0.3, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        # Height above the front row, in board widths
        self._up: FloatArray = (1 - board.y) * KEYBOARD_DEPTH
        # Each drop: across, up, its speed across and up, and its color
        self._drops: FloatArray = np.zeros((0, 5))

    @override
    def render(self) -> None:
        dt = self.step()
        # Each beat throws a spray of drops up from the middle of the front row
        if self.beat():
            count = DROPS_PER_BEAT
            rise = np.sqrt(2 * GRAVITY * KEYBOARD_DEPTH) * self.config.pressure
            spray = np.column_stack(
                (
                    np.full(count, 0.5),
                    np.zeros(count),
                    (self._rng.random(count) - 0.5) * 0.6,
                    rise * (0.6 + 0.4 * self._rng.random(count)),
                    self._rng.random(count),
                )
            )
            self._drops = np.concatenate((self._drops, spray))[-MAX_DROPS:]
        if len(self._drops):
            self._drops[:, 3] -= GRAVITY * dt
            self._drops[:, 0] += self._drops[:, 2] * dt
            self._drops[:, 1] += self._drops[:, 3] * dt
            self._drops = self._drops[self._drops[:, 1] > -DROP]
        size = self._x.size
        pixels = np.zeros((size, 3))
        for x, up, _, _, hue in self._drops:
            near = np.clip(1 - np.hypot(self._x - x, self._up - up) / DROP, 0, 1)
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            np.maximum(pixels, color * near[:, None], out=pixels)
        self.pixels = np.maximum(pixels, 2.0)
