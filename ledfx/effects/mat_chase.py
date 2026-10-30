from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

# The runner leaves a trail this long behind it, as a share of the pad's edge
TRAIL = 0.3
WHITE = np.array((255.0, 255.0, 255.0))


class MatChase(CorsairEffect, GradientEffect):
    NAME = "Mat Chase"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_lap: CoercedFloat = Field(
            2.0,
            description="Beats of the song for the runner to go from one tip to the other",
            ge=0.5,
            le=8.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._laps = 0.0
        self._crossed = 0.0

    @override
    def render(self) -> None:
        dt = self.step()
        before = self._laps
        self._laps += self.song_moved() / self.config.beats_per_lap + dt * 0.05
        # Tip to tip and back, like a runner doing shuttle runs
        going_right = np.floor(self._laps) % 2 == 0
        within = self._laps % 1
        runner = within if going_right else 1 - within
        behind = (runner - self._along) if going_right else (self._along - runner)
        level = np.where(
            (behind >= -0.04) & (behind < TRAIL),
            1 - np.clip(behind, 0, TRAIL) / TRAIL,
            0.0,
        )
        colors = self.get_gradient_color_vectorized1d(
            np.full(self._along.size, runner * 0.999)
        )
        pixels = colors * np.maximum(level**1.5, 0.03)[:, None]
        # The mouse flashes each time the runner passes the middle of the pad, under it
        self._crossed *= float(np.exp(-dt * 6))
        if np.floor(before + 0.5) != np.floor(self._laps + 0.5):
            self._crossed = 1.0
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(0.05, self._crossed), pixels
        )
