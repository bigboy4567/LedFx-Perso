from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, keyboard_layout
from ledfx.effects.utils.custom import FloatArray

# The beam leaves a fading trail this long behind it, as a share of the board's width
TRAIL = 0.25
WIDTH = 0.03


class KeyScanner(CorsairEffect, GradientEffect):
    NAME = "Key Scanner"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_sweep: CoercedFloat = Field(
            2.0,
            description="Beats of the song for the beam to cross the board once",
            ge=0.5,
            le=8.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        board = keyboard_layout(pixel_count)
        self._x: FloatArray = board.x
        self._sweeps = 0.0

    @override
    def render(self) -> None:
        self._sweeps += (
            self.song_moved() / self.config.beats_per_sweep + self.step() * 0.05
        )
        # Left to right, then back, the beam's color following where it is
        going_right = np.floor(self._sweeps) % 2 == 0
        within = self._sweeps % 1
        beam = within if going_right else 1 - within
        behind = (beam - self._x) if going_right else (self._x - beam)
        level = np.where(
            (behind >= -WIDTH) & (behind < TRAIL),
            1 - np.clip(behind, 0, TRAIL) / TRAIL,
            0.0,
        )
        # The beam swells with the volume
        level = level**1.5 * (0.5 + 0.5 * self.loudness)
        colors = self.get_gradient_color_vectorized1d(
            np.full(self._x.size, beam * 0.999)
        )
        self.pixels = colors * np.maximum(level, 0.02)[:, None]
