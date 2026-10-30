from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.fields import CoercedInt
from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import FloatArray

UNLIT = 0.03
FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatTempoGauge(CorsairEffect, GradientEffect):
    NAME = "Mat Tempo Gauge"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        slowest: CoercedInt = Field(
            60, description="Tempo at the left tip, in beats a minute", ge=40, le=120
        )
        fastest: CoercedInt = Field(
            180, description="Tempo at the right tip, in beats a minute", ge=121, le=240
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._flash = 0.0

    def tempo(self) -> float:
        """The song's tempo as the gauge shows it, 0 at the slowest to 1 at the fastest."""
        bpm = 60 / self.song.beat_length()
        slowest, fastest = self.config.slowest, self.config.fastest
        return float(np.clip((bpm - slowest) / (fastest - slowest), 0, 1))

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        if self.beat():
            self._flash = 1.0
        along = self._along
        lit = along <= self.tempo() + 0.02
        colors = self.get_gradient_color_vectorized1d(along * 0.999)
        pixels = colors * np.where(lit, 0.35 + 0.65 * self._flash, UNLIT)[:, None]
        # The mouse ticks the beats
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(UNLIT, self._flash), pixels
        )
