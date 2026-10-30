import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, fan_xy, stack_height
from ledfx.effects.utils.custom import FloatArray, color_array

# Drops falling at once, at most
MAX_DROPS = 20
# In fan widths: how far across a drop lights, and how long its tail is
WIDTH = 0.2
TAIL = 0.6


class FanRain(CorsairEffect):
    NAME = "Fan Rain"

    class Config(CorsairEffect.Config):
        color: Color = Field("#3070FF", description="Color of the rain")
        rain: CoercedFloat = Field(
            1.0, description="How hard the music makes it rain", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        fans = fan_layout(pixel_count)
        x, _ = fan_xy(fans)
        # Across each fan and up the stack, both in fan widths
        self._across: FloatArray = x * 0.42
        self._up: FloatArray = stack_height(fans) * fans.count
        self._top = float(fans.count)
        # Each drop: where across it falls, how high it is, and how fast it goes
        self._drops: FloatArray = np.zeros((0, 3))

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _drop(self, count: int) -> None:
        new = np.column_stack(
            (
                (self._rng.random(count) - 0.5) * 0.8,
                np.full(count, self._top + 0.1),
                1.5 + self._rng.random(count),
            )
        )
        self._drops = np.concatenate((self._drops, new))[-MAX_DROPS:]

    @override
    def render(self) -> None:
        dt = self.step()
        # The treble keeps a drizzle going, each percussive hit a small shower
        if self._rng.random() < (1 + 10 * self.levels[2]) * self.config.rain * dt:
            self._drop(1)
        if self.hit():
            self._drop(3)
        if len(self._drops):
            self._drops[:, 1] -= dt * self._drops[:, 2] * (0.6 + self.loudness)
            self._drops = self._drops[self._drops[:, 1] > -TAIL]

        level = np.zeros(self._up.size)
        for across, height, _ in self._drops:
            above = self._up - height
            on = (
                (np.abs(self._across - across) < WIDTH)
                & (above > -0.1)
                & (above < TAIL)
            )
            np.maximum(
                level, np.where(on, 1 - np.clip(above, 0, TAIL) / TAIL, 0.0), out=level
            )
        self.pixels = self._color * np.maximum(level, 0.02)[:, None]
