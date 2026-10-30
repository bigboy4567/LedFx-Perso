from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

# How long the snake is to start with, how much each beat adds, and how long it gets
SHORTEST = 0.1
GROWTH = 0.06
LONGEST = 0.9
FLASH = 5.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatSnake(CorsairEffect, GradientEffect):
    NAME = "Mat Snake"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.5, description="Pad edges the snake slithers a second", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        # The head's place on a there-and-back trip of the U, 0 to 2
        self.head = 0.0
        self.length = SHORTEST
        self._flash = 0.0
        self._passing = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        before = self.head
        self.head = (self.head + dt * self.config.speed * (0.5 + self.loudness)) % 2
        self._flash *= float(np.exp(-dt * FLASH))
        self._passing *= float(np.exp(-dt * FLASH))
        # Each beat it grows; once it is as long as it gets, it flashes and starts again
        if self.beat():
            self.length += GROWTH
            if self.length > LONGEST:
                self.length = SHORTEST
                self._flash = 1.0
        # The mouse lights as the head slithers past the bottom of the U
        if np.floor((before + 0.5) % 2) != np.floor((self.head + 0.5) % 2):
            self._passing = 1.0
        # A place on the U is passed twice on the trip, once each way
        behind = np.minimum(
            (self.head - self._along) % 2, (self.head - (2 - self._along)) % 2
        )
        body = behind < self.length
        colors = self.get_gradient_color_vectorized1d(
            np.clip(behind / self.length, 0, 1) * 0.999
        )
        pixels = colors * np.where(body, 1 - 0.7 * behind / self.length, 0.02)[:, None]
        pixels = pixels + (WHITE - pixels) * self._flash * 0.6
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(0.04, self._passing), pixels
        )
