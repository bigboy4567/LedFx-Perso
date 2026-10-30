from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# The spot's radius in the quiet and at full volume, as a share of the board's width
SMALLEST = 0.06
LARGEST = 0.22
UNLIT = 0.02


class KeySpotlight(CorsairEffect, GradientEffect):
    NAME = "Key Spotlight"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        wander: CoercedFloat = Field(
            0.3, description="How quickly the spot roams between beats", ge=0.05, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self._spot: FloatArray = np.array((0.5, 0.5 * KEYBOARD_DEPTH))
        self._aim: FloatArray = self._spot.copy()
        self._time = 0.0
        self._hue = 0.0
        self._radius = SMALLEST

    @override
    def render(self) -> None:
        dt = self.step()
        self._time += dt * self.config.wander
        # Between beats the spot drifts in slow loops; on a beat it jumps somewhere new
        drift = (
            np.array(
                (np.sin(self._time * 1.3), np.sin(self._time * 1.9) * KEYBOARD_DEPTH)
            )
            * 0.08
        )
        if self.beat():
            self._aim = np.array(
                (self._rng.random(), self._rng.random() * KEYBOARD_DEPTH)
            )
            self._hue = (self._hue + 0.17) % 1
        self._spot += (self._aim + drift - self._spot) * min(1.0, dt * 6)
        target = SMALLEST + (LARGEST - SMALLEST) * self.loudness
        self._radius += (target - self._radius) * min(1.0, dt * 8)

        distance = np.hypot(self._x - self._spot[0], self._y - self._spot[1])
        level = np.maximum(UNLIT, np.clip(1 - distance / self._radius, 0, 1) ** 0.7)
        colors = self.get_gradient_color_vectorized1d(np.full(distance.size, self._hue))
        self.pixels = colors * level[:, None]
