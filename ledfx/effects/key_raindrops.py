import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Drops on the board at once, at most
MAX_DROPS = 12
# A drop's ripple spreads this far, as a share of the board's width, over this long
REACH = 0.12
LIFE = 0.7
RING = 0.025
WHITE = np.array((255.0, 255.0, 255.0))


class KeyRaindrops(CorsairEffect):
    NAME = "Key Raindrops"

    class Config(CorsairEffect.Config):
        color: Color = Field("#3080FF", description="Color of the ripples")
        rain: CoercedFloat = Field(
            1.0, description="How hard the music makes it rain", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        # Each drop: where it landed, across and down, and its age
        self._drops: FloatArray = np.zeros((0, 3))

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _land(self) -> None:
        key = self._rng.integers(self._x.size)
        drop = np.array([[self._x[key], self._y[key], 0.0]])
        self._drops = np.concatenate((self._drops, drop))[-MAX_DROPS:]

    @override
    def render(self) -> None:
        dt = self.step()
        # Drops land on random keys, more with the treble, a few on each percussive hit
        if self._rng.random() < (1 + 10 * self.levels[2]) * self.config.rain * dt:
            self._land()
        if self.hit():
            for _ in range(2):
                self._land()
        if len(self._drops):
            self._drops[:, 2] += dt
            self._drops = self._drops[self._drops[:, 2] < LIFE]
        size = self._x.size
        level = np.zeros(size)
        splash = np.zeros(size)
        for x, y, age in self._drops:
            distance = np.hypot(self._x - x, self._y - y)
            ring = np.exp(-(((distance - age / LIFE * REACH) / RING) ** 2)) * (
                1 - age / LIFE
            )
            np.maximum(level, ring, out=level)
            # The key the drop lands on flashes white
            np.maximum(
                splash,
                np.where(distance < 1e-6, max(0.0, 1 - age * 8), 0.0),
                out=splash,
            )
        pixels = self._color * np.maximum(level, 0.02)[:, None]
        self.pixels = pixels + (WHITE - pixels) * splash[:, None]
