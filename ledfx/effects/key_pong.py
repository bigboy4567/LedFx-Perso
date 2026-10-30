from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# The paddles are the keys this close to the left and right edges
PADDLE_EDGE = 0.06
# Half a paddle's height, and the ball's size, as shares of the board's width
PADDLE = 0.05
BALL = 0.055
# A beat speeds the ball up by this much, which then wears off
BOOST = 1.8
BOOST_FADE = 2.0
WHITE = np.array((255.0, 255.0, 255.0))


class KeyPong(CorsairEffect, GradientEffect):
    NAME = "Key Pong"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.6, description="Board widths the ball crosses a second", ge=0.2, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self._top, self._bottom = (
            (float(self._y.min()), float(self._y.max())) if self._y.size else (0.0, 0.0)
        )
        self.ball: FloatArray = np.array((0.5, (self._top + self._bottom) / 2))
        self._heading: FloatArray = np.array((1.0, 0.45))
        # Where each paddle is, up and down the board
        self.paddles: FloatArray = np.full(2, self.ball[1])
        self._boost = 1.0
        self._hue = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        if self.beat():
            self._boost = BOOST
        self._boost = 1 + (self._boost - 1) * float(np.exp(-dt * BOOST_FADE))
        self.ball += self._heading * dt * self.config.speed * self._boost
        # The ball bounces off the paddles and the edges of the board, changing color off a paddle
        if not PADDLE_EDGE <= self.ball[0] <= 1 - PADDLE_EDGE:
            self.ball[0] = np.clip(self.ball[0], PADDLE_EDGE, 1 - PADDLE_EDGE)
            self._heading[0] = -self._heading[0]
            self._hue = (self._hue + 0.17) % 1
        if not self._top <= self.ball[1] <= self._bottom:
            self.ball[1] = np.clip(self.ball[1], self._top, self._bottom)
            self._heading[1] = -self._heading[1]
        # The paddles follow the ball, not quite keeping up
        self.paddles += (self.ball[1] - self.paddles) * min(1.0, dt * 5)
        size = self._x.size
        ball = np.clip(
            1 - np.hypot(self._x - self.ball[0], self._y - self.ball[1]) / BALL, 0, 1
        )
        colors = self.get_gradient_color_vectorized1d(np.full(size, self._hue))
        pixels = colors * np.maximum(ball, 0.02)[:, None]
        left = (self._x < PADDLE_EDGE) & (np.abs(self._y - self.paddles[0]) < PADDLE)
        right = (self._x > 1 - PADDLE_EDGE) & (
            np.abs(self._y - self.paddles[1]) < PADDLE
        )
        self.pixels = np.where((left | right)[:, None], WHITE * 0.8, pixels)
