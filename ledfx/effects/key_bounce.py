import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, hue_colors

# In board widths: how hard the balls fall, and how big they are
GRAVITY = 1.5
BALL = 0.06
# The share of its speed a ball keeps when it bounces
BOUNCE = 0.75


class KeyBounce(CorsairEffect):
    NAME = "Key Bounce"

    class Config(CorsairEffect.Config):
        balls: CoercedInt = Field(
            3, description="Balls bouncing on the board", ge=1, le=6
        )
        kick: CoercedFloat = Field(
            0.6, description="How hard each beat throws the balls up", ge=0.2, le=1.5
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        # Height above the front row, in board widths
        self._up: FloatArray = (1 - board.y) * KEYBOARD_DEPTH
        self._throw(self.config.balls)

    def _throw(self, count: int) -> None:
        """Start again with this many balls, dropped from the light bar."""
        # Each ball: across, up, and its speed across and up
        self.balls: FloatArray = np.column_stack(
            (
                self._rng.random(count),
                np.full(count, KEYBOARD_DEPTH),
                (self._rng.random(count) - 0.5) * 0.6,
                np.zeros(count),
            )
        )
        self._hues: FloatArray = np.arange(count) / count

    @override
    def render(self) -> None:
        dt = self.step()
        if len(self.balls) != self.config.balls:
            self._throw(self.config.balls)
        balls = self.balls
        if self.beat():
            balls[:, 3] = np.maximum(balls[:, 3], 0) + self.config.kick * (
                0.6 + 0.4 * self._rng.random(len(balls))
            )
        balls[:, 3] -= GRAVITY * dt
        balls[:, 0] += balls[:, 2] * dt
        balls[:, 1] += balls[:, 3] * dt
        # Off the front row, the light bar and the ends of the board
        floor = balls[:, 1] < 0
        balls[floor, 1] = 0.0
        balls[floor, 3] = -balls[floor, 3] * BOUNCE
        ceiling = balls[:, 1] > KEYBOARD_DEPTH
        balls[ceiling, 1] = KEYBOARD_DEPTH
        balls[ceiling, 3] = -np.abs(balls[ceiling, 3])
        sides = (balls[:, 0] < 0) | (balls[:, 0] > 1)
        balls[sides, 0] = np.clip(balls[sides, 0], 0, 1)
        balls[sides, 2] = -balls[sides, 2]
        size = self._x.size
        pixels = np.zeros((size, 3))
        for (x, up, _, _), hue in zip(balls, self._hues, strict=True):
            near = np.clip(1 - np.hypot(self._x - x, self._up - up) / BALL, 0, 1)
            np.maximum(
                pixels, hue_colors(np.full(size, hue)) * near[:, None], out=pixels
            )
        self.pixels = np.maximum(pixels, 2.0)
