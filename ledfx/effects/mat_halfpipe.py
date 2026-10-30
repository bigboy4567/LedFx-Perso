from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

# Half the length of the ball, as a share of the pad's edge
BALL = 0.12
# The ball swings this many times a second, and loses this share of its swing a second
SWINGS = 0.6
FRICTION = 0.5
# The ball leaves a short trail
TRAIL = 0.15


class MatHalfpipe(CorsairEffect, GradientEffect):
    NAME = "Mat Halfpipe"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        kick: CoercedFloat = Field(
            0.35,
            description="How much higher each beat sends the ball up the sides",
            ge=0.05,
            le=1.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # The ball rolls in the U like a skater in a halfpipe: its swing and where in it it is
        self._swing = 0.3
        self._phase = 0.0
        self._before = 0.5

    @override
    def render(self) -> None:
        dt = self.step()
        self._swing *= float(np.exp(-dt * FRICTION))
        if self.beat():
            self._swing = min(1.0, self._swing + self.config.kick)
        self._phase += dt * SWINGS * 2 * np.pi
        # Out from the middle, up to the height of its swing, and back
        ball = 0.5 + 0.5 * self._swing * np.sin(self._phase)
        before, self._before = self._before, ball

        span_low, span_high = min(before, ball) - BALL, max(before, ball) + BALL
        streak = (self._along >= span_low) & (self._along <= span_high)
        near = np.clip(1 - np.abs(self._along - ball) / BALL, 0, 1)
        level = np.maximum(near, np.where(streak, 0.4, 0.0))
        # Its color shows how high up the sides it is
        height = abs(ball - 0.5) * 2
        colors = self.get_gradient_color_vectorized1d(
            np.full(self._along.size, height * 0.999)
        )
        pixels = colors * np.maximum(level, 0.03)[:, None]
        # The mouse at the bottom of the U lights as the ball rolls through under it
        under = max(0.05, 1 - abs(ball - 0.5) / TRAIL)
        self.pixels = np.where(self._mouse[:, None], colors * under, pixels)
