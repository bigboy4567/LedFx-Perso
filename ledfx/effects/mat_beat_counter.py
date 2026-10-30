from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

UNLIT = 0.04
WHITE = np.array((255.0, 255.0, 255.0))


class MatBeatCounter(CorsairEffect, GradientEffect):
    NAME = "Mat Beat Counter"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats_per_bar: CoercedInt = Field(
            4, description="Beats counted before the pad empties again", ge=2, le=16
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._bar = -1
        self._downbeat = 0.0

    @override
    def render(self) -> None:
        self._downbeat *= float(np.exp(-self.step() * 5))
        beats = self.config.beats_per_bar
        counted = self.song.beats
        bar = int(counted // beats)
        if bar != self._bar:
            self._bar = bar
            self._downbeat = 1.0
        # The pad fills from its left tip to its right, one stretch for each beat of the bar
        filled = (int(counted) % beats + 1) / beats
        lit = self._along < filled - 1e-9
        segment = np.minimum(np.floor(self._along * beats), beats - 1) / max(
            beats - 1, 1
        )
        colors = self.get_gradient_color_vectorized1d(segment * 0.999)
        pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
        # The mouse flashes on the first beat of each bar
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(0.05, self._downbeat), pixels
        )
