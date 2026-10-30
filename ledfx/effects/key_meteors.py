from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# Meteors at once, at most
MAX_METEORS = 6
# A meteor's tail and the width of its head, as shares of the board's width
TAIL = 0.2
HEAD = 0.025
WHITE = np.array((255.0, 255.0, 255.0))
# They slant down the board, from the top left towards the front right
HEADING = np.array((0.8, 0.6))


class KeyMeteors(CorsairEffect, GradientEffect):
    NAME = "Key Meteors"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        speed: CoercedFloat = Field(
            0.6, description="Board widths a meteor crosses a second", ge=0.2, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._y: FloatArray = board.y * KEYBOARD_DEPTH
        # Each meteor: where across the light bar it starts, how far it has gone, and its color
        self._meteors: FloatArray = np.zeros((0, 3))

    @override
    def render(self) -> None:
        dt = self.step()
        # Each percussive hit sends a meteor slanting down the board
        if self.hit():
            meteor = np.array(
                [[self._rng.random() * 0.8 - 0.1, 0.0, self._rng.random()]]
            )
            self._meteors = np.concatenate((self._meteors, meteor))[-MAX_METEORS:]
        if len(self._meteors):
            self._meteors[:, 1] += dt * self.config.speed
            self._meteors = self._meteors[self._meteors[:, 1] < 0.8]
        size = self._x.size
        # A faint night sky behind them
        pixels = self.get_gradient_color_vectorized1d(np.zeros(size)) * 0.02
        for start, gone, hue in self._meteors:
            head = np.array((start, -0.02)) + HEADING * gone
            across, down = self._x - head[0], self._y - head[1]
            behind = -(across * HEADING[0] + down * HEADING[1])
            aside = np.abs(across * HEADING[1] - down * HEADING[0])
            on = (behind > -HEAD) & (behind < TAIL) & (aside < HEAD)
            level = np.where(on, 1 - np.clip(behind, 0, TAIL) / TAIL, 0.0)
            color = self.get_gradient_color_vectorized1d(np.full(size, hue))
            color = color + (WHITE - color) * (level**6)[:, None]
            np.maximum(pixels, color * level[:, None], out=pixels)
        self.pixels = np.clip(pixels, 0, 255)
