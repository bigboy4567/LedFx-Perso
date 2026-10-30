import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# A firefly lights the keys this close to it, as a share of the board's width
GLOW = 0.065


class KeyFireflies(CorsairEffect):
    NAME = "Key Fireflies"

    class Config(CorsairEffect.Config):
        color: Color = Field("#C0FF40", description="Color of the fireflies")
        fireflies: CoercedInt = Field(
            8, description="Fireflies on the board", ge=1, le=20
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        self._release(self.config.fireflies)

    def _release(self, count: int) -> None:
        # Each firefly: where it is, where it drifts, its blinking pace and phase
        self._places: FloatArray = np.column_stack(
            (self._rng.random(count), self._rng.random(count) * KEYBOARD_DEPTH)
        )
        self._drift: FloatArray = (self._rng.random((count, 2)) - 0.5) * 0.1
        self._rates: FloatArray = 0.5 + self._rng.random(count)
        self._phases: FloatArray = self._rng.random(count)

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    @override
    def render(self) -> None:
        dt = self.step()
        if len(self._places) != self.config.fireflies:
            self._release(self.config.fireflies)
        # They wander, and the music makes them busier
        busy = 0.5 + 2 * self.loudness
        self._drift += (self._rng.random(self._drift.shape) - 0.5) * dt * 0.3
        self._drift = np.clip(self._drift, -0.12, 0.12)
        self._places += self._drift * dt * busy
        # Bouncing back off the edges of the board
        for axis, limit in enumerate((1.0, KEYBOARD_DEPTH)):
            out = (self._places[:, axis] < 0) | (self._places[:, axis] > limit)
            self._places[out, axis] = np.clip(self._places[out, axis], 0, limit)
            self._drift[out, axis] = -self._drift[out, axis]
        self._phases = (self._phases + dt * self._rates * busy * 0.5) % 1
        # Each blinks: a soft glow, then darkness
        blink = np.clip(np.sin(2 * np.pi * self._phases), 0, 1) ** 2
        level = np.zeros(self._x.size)
        for (x, y), glow in zip(self._places, blink, strict=True):
            near = np.clip(1 - np.hypot(self._x - x, self._y - y) / GLOW, 0, 1)
            np.maximum(level, near * glow, out=level)
        self.pixels = self._color * np.maximum(level, 0.01)[:, None]
