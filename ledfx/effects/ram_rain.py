import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, Color
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, color_array

# Drops falling at once, at most
MAX_DROPS = 16
# How long a drop's tail is, as a share of a stick
TAIL = 0.35
PUDDLE_FADE = 3.0
WHITE = np.array((255.0, 255.0, 255.0))


class RamRain(CorsairEffect):
    NAME = "RAM Rain"

    class Config(CorsairEffect.Config):
        color: Color = Field("#3070FF", description="Color of the rain")
        rain: CoercedFloat = Field(
            1.0, description="How hard the music makes it rain", ge=0.2, le=4.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        # Each drop: its stick, how high it is, and its speed
        self._drops: FloatArray = np.zeros((0, 3))
        # How much water lies at the bottom of each stick
        self._puddles: FloatArray = np.zeros(ram.sticks)
        self._bottom = float(ram.height.min()) if ram.height.size else 0.0

    @override
    def config_updated(self, config: object) -> None:
        self._color = color_array(self.config.color)

    def _drop(self, count: int) -> None:
        new = np.column_stack(
            (
                self._rng.integers(self._ram.sticks, size=count).astype(float),
                np.full(count, 1.05),
                1.0 + self._rng.random(count),
            )
        )
        self._drops = np.concatenate((self._drops, new))[-MAX_DROPS:]

    @override
    def render(self) -> None:
        dt = self.step()
        self._puddles *= float(np.exp(-dt * PUDDLE_FADE))
        # The treble keeps a drizzle going, each percussive hit a small shower
        if self._rng.random() < (1 + 8 * self.levels[2]) * self.config.rain * dt:
            self._drop(1)
        if self.hit():
            self._drop(2)
        if len(self._drops):
            self._drops[:, 1] -= dt * self._drops[:, 2] * (0.6 + self.loudness)
            landed = self._drops[:, 1] < self._bottom
            for stick in self._drops[landed, 0].astype(int):
                self._puddles[stick] = 1.0
            self._drops = self._drops[~landed]

        ram = self._ram
        level = np.full(ram.height.size, 0.02)
        for stick, height, _ in self._drops:
            above = ram.height - height
            on = (ram.stick == stick) & (above > -0.06) & (above < TAIL)
            np.maximum(
                level, np.where(on, 1 - np.clip(above, 0, TAIL) / TAIL, 0.0), out=level
            )
        # Each drop splashes white at the bottom of its stick
        splash = np.where(
            ram.height <= self._bottom + 1e-9, self._puddles[ram.stick], 0.0
        )
        pixels = self._color * level[:, None]
        self.pixels = np.clip(pixels + (WHITE - pixels) * splash[:, None], 0, 255)
