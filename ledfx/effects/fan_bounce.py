from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, stack_height
from ledfx.effects.utils.custom import FloatArray

# In heights of the stack of fans: how hard the ball falls, and how big it is
GRAVITY = 3.0
SIZE = 0.1
# The share of its speed the ball keeps when it bounces
BOUNCE = 0.6


class FanBounce(CorsairEffect, GradientEffect):
    NAME = "Fan Bounce"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        kick: CoercedFloat = Field(
            1.8,
            description="How hard each beat throws the ball up, in stack heights a second",
            ge=0.5,
            le=4.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._height: FloatArray = stack_height(fan_layout(pixel_count))
        self.ball = 1.0
        self._speed = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        if self.beat():
            self._speed = max(self._speed, 0.0) + self.config.kick
        self._speed -= GRAVITY * dt
        self.ball += self._speed * dt
        if self.ball < 0:
            self.ball = 0.0
            self._speed = -self._speed * BOUNCE
        elif self.ball > 1:
            self.ball = 1.0
            self._speed = -abs(self._speed) * BOUNCE
        near = np.clip(1 - np.abs(self._height - self.ball) / SIZE, 0, 1)
        colors = self.get_gradient_color_vectorized1d(
            np.full(near.size, self.ball * 0.999)
        )
        self.pixels = colors * np.maximum(near, 0.02)[:, None]
