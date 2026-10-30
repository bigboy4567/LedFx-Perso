from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, fan_layout, stack_height
from ledfx.effects.utils.custom import FloatArray

# The beam leaves a trail this long behind it, as a share of the stack's height
TRAIL = 0.3
WIDTH = 0.04


class FanScanner(CorsairEffect, GradientEffect):
    NAME = "Fan Scanner"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_sweep: CoercedFloat = Field(
            1.0,
            description="Beats of the song for the beam to cross the stack once",
            ge=0.25,
            le=8.0,
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        self._height: FloatArray = stack_height(fan_layout(pixel_count))
        self.sweeps = 0.0

    @override
    def render(self) -> None:
        self.sweeps += (
            self.song_moved() / self.config.beats_per_sweep + self.step() * 0.05
        )
        # Up the stack, then back down, the beam's color following its height
        going_up = np.floor(self.sweeps) % 2 == 0
        within = self.sweeps % 1
        beam = within if going_up else 1 - within
        behind = (beam - self._height) if going_up else (self._height - beam)
        level = np.where(
            (behind >= -WIDTH) & (behind < TRAIL),
            1 - np.clip(behind, 0, TRAIL) / TRAIL,
            0.0,
        )
        colors = self.get_gradient_color_vectorized1d(np.full(level.size, beam * 0.999))
        self.pixels = colors * np.maximum(level**1.5, 0.02)[:, None]
