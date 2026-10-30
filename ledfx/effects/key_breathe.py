from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import (
    KEYBOARD_DEPTH,
    CorsairEffect,
    breath,
    keyboard_layout,
)
from ledfx.effects.utils.custom import FloatArray


class KeyBreathe(CorsairEffect, GradientEffect):
    NAME = "Key Breathe"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_breath: CoercedFloat = Field(
            4.0, description="Beats of the song for one breath", ge=1.0, le=16.0
        )
        spread: CoercedFloat = Field(
            0.6,
            description="How far behind the middle the edges of the board breathe, as a share of a breath",
            ge=0.0,
            le=2.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        # How far each key is from the middle of the board, 0 to about 1 at the corners
        self._distance: FloatArray = (
            np.hypot(board.x - 0.5, (board.y - 0.5) * KEYBOARD_DEPTH) * 2
        )
        self._breaths = 0.0

    @override
    def render(self) -> None:
        self._breaths += (
            self.song_moved() / self.config.beats_per_breath + self.step() * 0.03
        )
        # Each breath starts in the middle and spreads to the edges
        phase = self._breaths - self._distance * self.config.spread
        level = breath(phase) * (0.6 + 0.4 * self.loudness)
        colors = self.get_gradient_color_vectorized1d(
            np.clip(self._distance, 0, 1) * 0.999
        )
        self.pixels = colors * (0.03 + 0.97 * level)[:, None]
