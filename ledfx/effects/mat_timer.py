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
FLASH = 4.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatTimer(CorsairEffect, GradientEffect):
    NAME = "Mat Timer"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        beats: CoercedInt = Field(
            8, description="Beats of the song for the pad to run down", ge=2, le=64
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._along: FloatArray = mat.along
        self._mouse = mat.mouse
        self._round = -1
        self._flash = 0.0

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        beats = self.config.beats
        counted = self.song.beats
        if int(counted // beats) != self._round:
            self._round = int(counted // beats)
            self._flash = 1.0
        # The pad runs down from its right tip to its left
        left = 1 - (counted % beats) / beats
        lit = self._along <= left
        colors = self.get_gradient_color_vectorized1d(self._along * 0.999)
        pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
        # The mouse flashes as the pad fills up again
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(0.03, self._flash), pixels
        )
