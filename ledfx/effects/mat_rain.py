import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Drops running down at once, at most
MAX_DROPS = 10
# How long a drop's tail is, as a share of a side of the pad
TAIL = 0.35
# Each drop raises the pool at the bottom this much, which then drains this fast
POOL_RISE = 0.12
POOL_DRAIN = 0.2


class MatRain(CorsairEffect):
    NAME = "Mat Rain"

    class Config(CorsairEffect.Config):
        color: Color = Field("#3070FF", description="Color of the rain")
        rain: CoercedFloat = Field(
            1.0, description="How hard the music makes it rain", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._right = mat.along > 0.5
        self._mouse = mat.mouse
        # Each drop: its side (1 the right), how high it is, and its speed
        self._drops: FloatArray = np.zeros((0, 3))
        self.pool = 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _drop(self, count: int) -> None:
        new = np.column_stack(
            (
                self._rng.integers(2, size=count).astype(float),
                np.full(count, 1.05),
                1.0 + self._rng.random(count),
            )
        )
        self._drops = np.concatenate((self._drops, new))[-MAX_DROPS:]

    @override
    def render(self) -> None:
        dt = self.step()
        self.pool = max(0.0, self.pool - dt * POOL_DRAIN)
        # The treble keeps a drizzle going down the sides, each percussive hit a small shower
        if self._rng.random() < (1 + 6 * self.levels[2]) * self.config.rain * dt:
            self._drop(1)
        if self.hit():
            self._drop(2)
        if len(self._drops):
            self._drops[:, 1] -= dt * self._drops[:, 2] * (0.6 + self.loudness)
            landed = self._drops[:, 1] < 0
            self.pool = min(1.0, self.pool + POOL_RISE * int(landed.sum()))
            self._drops = self._drops[~landed]

        height = self._height
        # The rain pools at the bottom of the U
        level = np.where(height <= self.pool * 0.6, 0.5, 0.02)
        for side, drop, _ in self._drops:
            above = height - drop
            on = (self._right == (side > 0)) & (above > -0.06) & (above < TAIL)
            np.maximum(
                level, np.where(on, 1 - np.clip(above, 0, TAIL) / TAIL, 0.0), out=level
            )
        # The mouse sits in the pool
        level = np.where(self._mouse, max(0.03, self.pool), level)
        self.pixels = self._color * level[:, None]
