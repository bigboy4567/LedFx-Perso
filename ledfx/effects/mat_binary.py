from typing import ClassVar

import numpy as np
from pydantic import Field
from typing_extensions import override

from ledfx.configuration.plugin import TypedConfig
from ledfx.effects.gradient import GradientEffect
from ledfx.effects.utils.corsair import CorsairEffect, mat_layout
from ledfx.effects.utils.custom import IntArray

# Bits a 64-bit count can show
BITS = 62
UNLIT = 0.03
FLASH = 6.0
WHITE = np.array((255.0, 255.0, 255.0))


class MatBinary(CorsairEffect, GradientEffect):
    NAME = "Mat Binary"
    # Effect declares HIDDEN_KEYS = None, so every list override trips bad-override.
    HIDDEN_KEYS: ClassVar[list[str]] = ["gradient_roll"]  # pyrefly: ignore[bad-override]

    class Config(GradientEffect.Config):
        count_bars: bool = Field(
            False, description="Count the bars instead of the beats"
        )

    config = TypedConfig(Config)

    def on_activate(self, pixel_count: int) -> None:
        mat = mat_layout(pixel_count)
        self._mouse = mat.mouse
        # Each LED of the pad is a bit of the count, the lowest at the left tip
        order = np.argsort(np.where(mat.mouse, np.inf, mat.along), kind="stable")
        bit = np.empty(pixel_count, dtype=int)
        bit[order] = np.arange(pixel_count)
        self._bit: IntArray = bit
        self._shift: IntArray = np.minimum(bit, BITS)
        self._place = mat.along
        self._flash = 0.0

    @override
    def render(self) -> None:
        self._flash *= float(np.exp(-self.step() * FLASH))
        if self.beat():
            self._flash = 1.0
        # The beats of the song, or its bars, counted in binary
        beats = self.song.beats / 4 if self.config.count_bars else self.song.beats
        count = np.int64(max(0, int(beats)))
        lit = (self._bit < BITS) & ((np.right_shift(count, self._shift) & 1) == 1)
        colors = self.get_gradient_color_vectorized1d(self._place * 0.999)
        pixels = colors * np.where(lit, 1.0, UNLIT)[:, None]
        # The mouse ticks with each beat
        self.pixels = np.where(
            self._mouse[:, None], WHITE * max(UNLIT, self._flash), pixels
        )
