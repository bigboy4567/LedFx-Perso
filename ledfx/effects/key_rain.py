import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Drops falling at once, at most
MAX_DROPS = 40
# A drop lights the keys this far either side of its column, across the board
COLUMN = 0.022
# Its tail reaches this far up behind it, as a share of the board's depth
TAIL = 0.45
WHITE = np.array((255.0, 255.0, 255.0))


class KeyRain(CorsairEffect):
    NAME = "Key Rain"

    class Config(CorsairEffect.Config):
        color: Color = Field("#00FF40", description="Color of the falling code")
        rain: CoercedFloat = Field(
            1.0, description="How hard the music makes it rain", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y
        # Each drop: its column, how far down it has fallen, and its speed
        self._drops: FloatArray = np.zeros((0, 3))

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _drop(self, count: int) -> None:
        new = np.column_stack(
            (
                self._rng.choice(self._x, count),
                np.full(count, -0.05),
                0.8 + self._rng.random(count) * 1.2,
            )
        )
        self._drops = np.concatenate((self._drops, new))[-MAX_DROPS:]

    @override
    def render(self) -> None:
        dt = self.step()
        # The treble keeps a drizzle going, each percussive hit sends a few drops at once
        if self._rng.random() < (0.5 + 12 * self.levels[2]) * self.config.rain * dt:
            self._drop(1)
        if self.hit():
            self._drop(3)
        if len(self._drops):
            self._drops[:, 1] += dt * self._drops[:, 2] * (0.6 + self.loudness)
            self._drops = self._drops[self._drops[:, 1] < 1 + TAIL]

        pixels = np.zeros((self._x.size, 3))
        for column, head, _ in self._drops:
            behind = head - self._y
            on = (
                (np.abs(self._x - column) < COLUMN)
                & (behind >= -0.03)
                & (behind < TAIL)
            )
            level = np.where(on, 1 - np.clip(behind, 0, TAIL) / TAIL, 0.0)
            color = self._color + (WHITE - self._color) * (level**6)[:, None]
            np.maximum(pixels, color * level[:, None], out=pixels)
        self.pixels = np.clip(pixels, 0, 255)
