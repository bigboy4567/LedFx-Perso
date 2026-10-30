from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedFloat
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, breath, mat_height, mat_layout
from ledfx.effects.utils.custom import FloatArray

# The breath's edge fades over this share of the pad's sides
SOFT = 0.15


class MatBreathe(CorsairEffect, GradientEffect):
    NAME = "Mat Breathe"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_breath: CoercedFloat = Field(
            4.0, description="Beats of the song for one breath", ge=1.0, le=16.0
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._height: FloatArray = mat_height(mat)
        self._mouse = mat.mouse
        self._breaths = 0.0
        self.full = 0.0

    @override
    def render(self) -> None:
        self._breaths += (
            self.song_moved() / self.config.beats_per_breath + self.step() * 0.03
        )
        # Breathing in fills the pad up both sides from the bottom; breathing out drains it
        self.full = float(breath(self._breaths))
        level = np.clip((self.full * (1 + SOFT) - self._height) / SOFT, 0, 1)
        colors = self.get_gradient_color_vectorized1d(self._height * 0.999)
        pixels = colors * np.maximum(level, 0.03)[:, None]
        # The mouse swells and fades with the breath
        mouse = self.get_gradient_color_vectorized1d(np.zeros(level.size)) * max(
            0.05, self.full
        )
        self.pixels = np.where(self._mouse[:, None], mouse, pixels)
