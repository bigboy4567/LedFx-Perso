from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, ram_layout
from ledfx.effects.utils.custom import IntArray

SHORTEST = 3
FLASH = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class RamSnake(CorsairEffect, GradientEffect):
    NAME = "RAM Snake"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        steps_per_beat: CoercedFloat = Field(
            4.0,
            description="LEDs the snake moves per beat of the song",
            ge=1.0,
            le=16.0,
        )
        longest: CoercedInt = Field(
            16,
            description="How long the snake grows before it starts again",
            ge=4,
            le=40,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        ram = ram_layout(pixel_count)
        self._ram = ram
        rows = np.unique(ram.height).size
        # Up the first stick, down the next, up the one after...
        row = np.round(ram.height * (rows - 1)).astype(int)
        self._path: IntArray = ram.stick * rows + np.where(
            ram.stick % 2 == 0, row, rows - 1 - row
        )
        self._cells = ram.sticks * rows
        self.head = 0.0
        self.length = SHORTEST
        self._flash = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        self.head += self.song_moved() * self.config.steps_per_beat + dt * 2
        self._flash *= float(np.exp(-dt * FLASH))
        # Each beat it grows; once it is as long as it gets, it flashes and starts again
        if self.beat():
            self.length += 1
            if self.length > min(self.config.longest, self._cells):
                self.length = SHORTEST
                self._flash = 1.0
        behind = (int(self.head) - self._path) % self._cells
        body = behind < self.length
        colors = self.get_gradient_color_vectorized1d(
            np.clip(behind / self.length, 0, 1) * 0.999
        )
        level = np.where(body, 1 - 0.7 * behind / self.length, 0.02)
        pixels = colors * level[:, None]
        self.pixels = pixels + (WHITE - pixels) * self._flash * 0.6
