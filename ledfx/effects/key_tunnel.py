from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray


class KeyTunnel(CorsairEffect, GradientEffect):
    NAME = "Key Tunnel"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        rings: CoercedFloat = Field(
            3.0,
            description="Rings of the tunnel from the middle to the edge",
            ge=1.0,
            le=8.0,
        )
        speed: CoercedFloat = Field(
            0.5, description="Rings rushing past per beat of the song", ge=0.1, le=2.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        # How far out each key is, in rectangles the shape of the board, 0 middle to 1 edge
        self._depth: FloatArray = (
            np.maximum(np.abs(board.x - 0.5), np.abs(board.y - 0.5)) * 2
        )
        self._travel = 0.0

    @override
    def render(self) -> None:
        self._travel += self.song_moved() * self.config.speed + self.step() * 0.1
        # Rings of the tunnel rush out from the middle to the edges of the board
        place = self._depth * self.config.rings - self._travel
        ring = (0.5 + 0.5 * np.cos(2 * np.pi * place)) ** 3
        colors = self.get_gradient_color_vectorized1d(np.floor(place) % 6 / 6)
        level = 0.03 + 0.97 * ring * (0.4 + 0.6 * self.loudness)
        self.pixels = colors * level[:, None]
