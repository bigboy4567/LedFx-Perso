from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, IntArray

# In stick heights: how hard the balls fall, and how big they are
GRAVITY = 4.0
SIZE = 0.12
# The share of its speed a ball keeps when it bounces
BOUNCE = 0.55


class RamBounce(CorsairEffect, GradientEffect):
    NAME = "RAM Bounce"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        kick: CoercedFloat = Field(
            2.5,
            description="How hard a beat throws the balls up, in stick heights a second",
            ge=0.5,
            le=5.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        # The bass throws the left stick's ball, the treble the right one's
        self._band: IntArray = np.round(np.linspace(0, 2, ram.sticks)).astype(int)
        self.balls: FloatArray = np.zeros(ram.sticks)
        self._speeds: FloatArray = np.zeros(ram.sticks)

    @override
    def render(self) -> None:
        dt = self.step()
        if self.beat():
            strength = 0.4 + 0.6 * self.levels[self._band]
            self._speeds = np.maximum(self._speeds, 0) + self.config.kick * strength
        self._speeds -= GRAVITY * dt
        self.balls += self._speeds * dt
        floor = self.balls < 0
        self.balls[floor] = 0.0
        self._speeds[floor] = -self._speeds[floor] * BOUNCE
        ceiling = self.balls > 1
        self.balls[ceiling] = 1.0
        self._speeds[ceiling] = -np.abs(self._speeds[ceiling]) * BOUNCE
        ram = self._ram
        ball = self.balls[ram.stick]
        near = np.clip(1 - np.abs(ram.height - ball) / SIZE, 0, 1)
        colors = self.get_gradient_color_vectorized1d(ball * 0.999)
        self.pixels = colors * np.maximum(near, 0.02)[:, None]
