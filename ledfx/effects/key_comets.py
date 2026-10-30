from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout, keyboard_rows
from ledfx.effects.utils.custom import FloatArray, IntArray

# Comets in flight at once, at most
MAX_COMETS = 8
# How long a comet's tail is, as a share of the board's width
TAIL = 0.3
WHITE = np.array((255.0, 255.0, 255.0))


class KeyComets(CorsairEffect, GradientEffect):
    NAME = "Key Comets"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            1.5, description="Board widths a comet crosses a second", ge=0.3, le=5.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        rows, count = keyboard_rows(board)
        self._row: IntArray = rows
        self._rows = count
        # Each comet: its row, how far it has gone, its heading (1 rightward), its color
        self._comets: FloatArray = np.zeros((0, 4))

    @override
    def render(self) -> None:
        dt = self.step()
        # Each percussive hit shoots a comet along a row, from one side or the other
        if self.hit():
            heading = 1.0 if self._rng.random() < 0.5 else -1.0
            comet = np.array(
                [[self._rng.integers(self._rows), -0.02, heading, self._rng.random()]]
            )
            self._comets = np.concatenate((self._comets, comet))[-MAX_COMETS:]
        if len(self._comets):
            self._comets[:, 1] += dt * self.config.speed
            self._comets = self._comets[self._comets[:, 1] < 1 + TAIL]
        size = self._x.size
        pixels = np.zeros((size, 3))
        for row, gone, heading, hue in self._comets:
            place = self._x if heading > 0 else 1 - self._x
            behind = gone - place
            on = (self._row == row) & (behind > -0.03) & (behind < TAIL)
            level = np.where(on, 1 - np.clip(behind, 0, TAIL) / TAIL, 0.0)
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            # The head burns white
            color = color + (WHITE - color) * (level**6)[:, None]
            np.maximum(pixels, color * level[:, None], out=pixels)
        self.pixels = np.clip(pixels, 0, 255)
