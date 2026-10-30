from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import FloatArray, IntArray

# A falling block drops this many stick heights a second
FALL = 2.5
# Once the bank is full it flashes this long before emptying
CLEAR = 0.5
WHITE = np.array((255.0, 255.0, 255.0))


class RamBlocks(CorsairEffect, GradientEffect):
    NAME = "RAM Blocks"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        block_size: CoercedInt = Field(2, description="LEDs in each block", ge=1, le=5)

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._ram = ram_layout(pixel_count)
        # The LEDs of a stick, from the bottom up, and how many there are
        heights = np.unique(self._ram.height)
        self._rows = heights.size
        self._row: IntArray = np.searchsorted(heights, self._ram.height)
        self._reset()

    def _reset(self) -> None:
        sticks = self._ram.sticks
        # How many LEDs of each stick are stacked, the color of each stacked LED, the block falling
        self._stacked: IntArray = np.zeros(sticks, dtype=int)
        self._colors: FloatArray = np.zeros((sticks, self._rows))
        self._falling: tuple[int, float, float] | None = None
        self._clearing = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        rows = self._rows
        size = min(self.config.block_size, rows)
        if self._clearing:
            self._clearing -= dt
            if self._clearing <= 0:
                self._reset()
        elif self._falling is None and self.beat():
            # A block drops on each beat, into the emptiest stick
            room = rows - self._stacked
            choices = np.flatnonzero(room == room.max())
            self._falling = (
                int(self._rng.choice(choices)),
                float(rows),
                float(self._rng.random()),
            )
        if self._falling is not None:
            stick, bottom, hue = self._falling
            bottom -= dt * FALL * rows
            floor = self._stacked[stick]
            if bottom <= floor:
                top = min(rows, floor + size)
                self._colors[stick, floor:top] = hue
                self._stacked[stick] = top
                self._falling = None
                if (self._stacked >= rows).all():
                    self._clearing = CLEAR
            else:
                self._falling = (stick, bottom, hue)

        ram = self._ram
        stacked = self._row < self._stacked[ram.stick]
        hues = self._colors[ram.stick, np.minimum(self._row, rows - 1)]
        level = np.where(stacked, 0.8, 0.0)
        if self._falling is not None:
            stick, bottom, hue = self._falling
            inside = (
                (ram.stick == stick)
                & (self._row >= np.floor(bottom))
                & (self._row < np.floor(bottom) + size)
            )
            hues = np.where(inside, hue, hues)
            level = np.where(inside, 1.0, level)
        pixels = (
            self.get_gradient_color_vectorized1d(np.clip(hues, 0, 0.999))
            * level[:, None]
        )
        if self._clearing:
            pixels = WHITE * (self._clearing / CLEAR) * np.ones((ram.height.size, 1))
        self.pixels = pixels
