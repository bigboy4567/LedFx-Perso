from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout

# How far the ball lights, across in sticks and up in stick heights
REACH_ACROSS = 0.6
REACH_UP = 0.18
# A beat speeds the ball up by this much, which then wears off
BOOST = 1.8
BOOST_FADE = 2.0


class RamPong(CorsairEffect, GradientEffect):
    NAME = "RAM Pong"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.0, description="How fast the ball travels", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        # The ball, across in sticks and up in stick heights, and its heading
        self.across = 0.0
        self.up = 0.3
        self._heading = np.array((1.3, 1.0))
        self._boost = 1.0
        self._hue = 0.0

    def _recolor(self) -> None:
        self._hue = (self._hue + 0.13) % 1

    @override
    def render(self) -> None:
        dt = self.step()
        if self.beat():
            self._boost = BOOST
        self._boost = 1 + (self._boost - 1) * float(np.exp(-dt * BOOST_FADE))
        ram = self._ram
        move = self._heading * dt * self.config.speed * self._boost
        self.across += float(move[0])
        self.up += float(move[1])
        # The ball bounces off the outer sticks and the tops and bottoms, changing color
        last = ram.sticks - 1
        if self.across < 0 or self.across > last:
            self.across = float(np.clip(self.across, 0, last))
            self._heading[0] = -self._heading[0]
            self._recolor()
        if self.up < 0 or self.up > 1:
            self.up = float(np.clip(self.up, 0, 1))
            self._heading[1] = -self._heading[1]
            self._recolor()
        distance = np.hypot(
            (ram.stick - self.across) / REACH_ACROSS, (ram.height - self.up) / REACH_UP
        )
        level = np.clip(1 - distance, 0, 1)
        colors = self.get_gradient_color_vectorized1d(np.full(level.size, self._hue))
        self.pixels = colors * np.maximum(level, 0.02)[:, None]
