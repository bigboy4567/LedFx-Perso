from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat, CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import KEYBOARD_DEPTH, CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray


class KeySpiral(CorsairEffect, GradientEffect):
    NAME = "Key Spiral"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        arms: CoercedInt = Field(3, description="Arms of the spiral", ge=1, le=6)
        twist: CoercedFloat = Field(
            3.0, description="How tightly the arms wind", ge=0.0, le=10.0
        )
        turns_per_beat: CoercedFloat = Field(
            0.25,
            description="Turns of the spiral per beat of the song",
            ge=0.02,
            le=2.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        across = board.x - 0.5
        down = (board.y - 0.5) * KEYBOARD_DEPTH
        # Each key's angle round the middle of the board, in turns, and how far out it is
        self._angle: FloatArray = np.arctan2(down, across) / (2 * np.pi)
        self._distance: FloatArray = np.hypot(across, down) * 2
        self._turn = 0.0

    @override
    def render(self) -> None:
        self._turn += (
            self.song_moved() * self.config.turns_per_beat + self.step() * 0.05
        )
        phase = (
            self._angle * self.config.arms
            + self._distance * self.config.twist
            - self._turn
        )
        arms = (0.5 + 0.5 * np.cos(2 * np.pi * phase)) ** 2
        colors = self.get_gradient_color_vectorized1d(
            np.clip(self._distance, 0, 1) * 0.999
        )
        level = 0.03 + 0.97 * arms * (0.5 + 0.5 * self.loudness)
        self.pixels = colors * level[:, None]
